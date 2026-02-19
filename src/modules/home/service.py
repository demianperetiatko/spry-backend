from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Sequence
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status

from src.modules.analytics.common.calculator import (
    SATURDAY_WEEKDAY,
    WORKDAY_DEFAULT_HOURS,
    calculate_change,
    sum_duration,
)
from src.modules.analytics.common.data_loader import AnalyticsDataLoaderBase
from src.modules.analytics.common.schemas import KPIMetric, KPIResultDTO
from src.modules.analytics.personal.calculator import AnalyticsCalculator, count_weekdays
from src.modules.calendar.models import CalendarEvent, UserCalendar
from src.modules.calendar.service import CalendarService
from src.modules.home.repository import HomeRepository
from src.modules.home.schemas import (
    AgendaDescriptionRequest,
    AgendaMeeting,
    AgendaResponse,
    DeepWorkSlotsResponse,
    KPIResponse,
    TimeSlot,
    TimeSlotDTO,
    UserProfile,
)
from src.modules.user.model import User
from src.shared.email import get_email_service


class HomeService:
    def __init__(self, repository: HomeRepository, calendar_service: CalendarService) -> None:
        self.repo = repository
        self.calendar_service = calendar_service

    async def get_kpis(self, user: User) -> KPIResponse:
        calendar_ids = await self._require_calendar_ids(user.id)
        tz = await self._get_timezone(user.id)

        now = datetime.now(tz)
        start_of_week = now - timedelta(days=now.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        start_date = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_of_week.replace(hour=23, minute=59, second=59, microsecond=999999)

        prev_start_date = start_date - timedelta(days=7)
        prev_end_date = end_date - timedelta(days=7)

        events = await self.repo.get_meeting_events_for_period(calendar_ids, start_date, end_date, user.email)
        prev_events = await self.repo.get_meeting_events_for_period(calendar_ids, prev_start_date, prev_end_date, user.email)

        unique_events = AnalyticsDataLoaderBase.get_unique_events(events)
        unique_prev_events = AnalyticsDataLoaderBase.get_unique_events(prev_events)

        work_days = count_weekdays(start_date, end_date)
        calc = AnalyticsCalculator(unique_events, unique_prev_events, work_days, workday_hours=WORKDAY_DEFAULT_HOURS)

        kpis: list[KPIMetric] = [
            self._build_kpi("time_on_meetings", "Time on meetings", calc.kpi_total_time()),
            self._build_kpi("meetings_count", "Meetings count", calc.kpi_meetings_count()),
        ]

        deep_work_current = self._calculate_deep_work_hours(unique_events, work_days)
        deep_work_previous = self._calculate_deep_work_hours(unique_prev_events, work_days)
        kpis.append(
            self._build_kpi("time_deep_work", "Deep work time", self._build_deep_work_kpi(deep_work_current, deep_work_previous))
        )

        return KPIResponse(data=kpis)

    async def get_deep_work_slots(self, user: User) -> DeepWorkSlotsResponse:
        calendar_ids = await self._require_calendar_ids(user.id)
        tz = await self._get_timezone(user.id)

        now = datetime.now(tz)
        start_date = now
        end_date = (now + timedelta(days=14)).replace(hour=23, minute=59, second=59, microsecond=999999)

        meetings = await self.repo.get_meeting_events_for_period(calendar_ids, start_date, end_date, user.email)
        all_events = await self.repo.get_events_for_period(calendar_ids, start_date, end_date, include_attendees=False)

        busy_slots: list[tuple[datetime, datetime]] = []
        for event in meetings:
            busy_slots.append((self._to_timezone(event.start_datetime, tz), self._to_timezone(event.end_datetime, tz)))

        for event in all_events:
            if event.summary == "Deep Work Time" and event.start_datetime and event.end_datetime:
                busy_slots.append((self._to_timezone(event.start_datetime, tz), self._to_timezone(event.end_datetime, tz)))

        free_slots = self._find_week_free_slots(start_date, end_date, busy_slots, tz)
        return DeepWorkSlotsResponse(
            slots=[
                TimeSlotDTO(
                    startTime=slot["startTime"],
                    endTime=slot["endTime"],
                    date=slot["date"],
                    duration=Decimal(str(slot["duration"])).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP),
                )
                for slot in free_slots
            ]
        )

    async def create_deep_work_slots(self, user: User, slots: list[TimeSlot]) -> list[dict]:
        calendar = await self._get_primary_calendar(user.id)
        if not calendar:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No calendar connected for user")

        if not calendar.user_access_info:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Calendar access info is missing")

        tz = await self._get_timezone(user.id)
        created_events = []
        for slot in slots:
            start_dt = self._ensure_timezone(slot.start_time, tz)
            end_dt = self._ensure_timezone(slot.end_time, tz)
            body = {
                "summary": "Deep Work Time",
                "start": {"dateTime": start_dt.isoformat(), "timeZone": tz.key},
                "end": {"dateTime": end_dt.isoformat(), "timeZone": tz.key},
            }
            event = await self.calendar_service.create_event(calendar, body)
            created_events.append(event)

        return created_events

    async def get_agenda(self, user: User) -> AgendaResponse:
        calendar_ids = await self._require_calendar_ids(user.id)
        tz = await self._get_timezone(user.id)

        now = datetime.now(tz)
        start_date = now
        end_date = (now + timedelta(days=14)).replace(hour=23, minute=59, second=59, microsecond=999999)

        events = await self.repo.get_meeting_events_for_period(calendar_ids, start_date, end_date, user.email)
        unique_events = AnalyticsDataLoaderBase.get_unique_events(events)

        event_ids = [event.google_event_id for event in unique_events if event.google_event_id]
        agenda_sent_ids = await self.repo.get_agenda_event_ids(user.id, event_ids)

        attendee_emails = {att.email for event in unique_events for att in (event.attendees or []) if att.email}
        organizer_emails = {event.organizer_email for event in unique_events if event.organizer_email}
        all_emails = {email for email in attendee_emails | organizer_emails if email}

        users = await self.repo.get_users_by_emails(list(all_emails))
        user_map = {user.email: user for user in users}

        meetings: list[AgendaMeeting] = []
        for event in unique_events:
            if event.description and str(event.description).strip():
                continue

            start_dt = self._to_timezone(event.start_datetime, tz)
            end_dt = self._to_timezone(event.end_datetime, tz)
            meeting = AgendaMeeting(
                id=event.google_event_id or event.id,
                name=event.summary or "No Title",
                start_time=start_dt.isoformat(),
                end_time=end_dt.isoformat(),
                date=start_dt.date().isoformat(),
                members=[self._build_profile(att.email, user_map) for att in event.attendees or [] if att.email],
                organizer=self._build_profile(event.organizer_email, user_map) if event.organizer_email else None,
                is_organizer=bool(event.organizer_email and event.organizer_email == user.email),
                invitation_sent=event.google_event_id in agenda_sent_ids if event.google_event_id else False,
            )
            meetings.append(meeting)

        return AgendaResponse(
            meetings=meetings,
            count_all_events=len(unique_events),
        )

    async def notify_agenda(self, user: User, event_id: str) -> dict:
        calendar_ids = await self._require_calendar_ids(user.id)
        tz = await self._get_timezone(user.id)

        event = await self.repo.get_event_by_google_id(event_id, calendar_ids)
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

        organizer_email = event.organizer_email
        if not organizer_email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organizer email not found")

        existing = await self.repo.get_agenda_entry(user.id, event_id)
        if not existing:
            await self.repo.create_agenda_entry(user.id, event_id)
            start_dt = self._to_timezone(event.start_datetime, tz)
            end_dt = self._to_timezone(event.end_datetime, tz)
            date_str = start_dt.strftime("%a, %b %d")
            time_str = f"{self._format_hour(start_dt)} - {self._format_hour(end_dt, with_meridiem=True)}"

            email_service = get_email_service()
            await email_service.send_agenda_request(
                email=organizer_email,
                calendar_event_name=event.summary or "No Title",
                calendar_event_date=date_str,
                calendar_event_time=time_str,
                calendar_event_count_attendee=str(len(event.attendees or [])),
                calendar_event_link=event.html_link or "#",
            )

        return {"status": "ok"}

    async def add_agenda_description(self, user: User, event_id: str, payload: AgendaDescriptionRequest) -> dict:
        calendar_ids = await self._require_calendar_ids(user.id)
        event: CalendarEvent | None = await self.repo.get_event_by_google_id(event_id, calendar_ids)
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

        user_calendar: UserCalendar | None = await self.repo.get_user_calendar_by_id(event.user_calendar_id)
        if not user_calendar:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calendar not found for event")

        updated = await self.calendar_service.update_event(
            user_calendar,
            event.google_event_id or event.id,
            {"description": payload.description},
        )

        event.description = payload.description
        await self.repo.session.flush()

        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Failed to update event in calendar")

        return updated

    async def _require_calendar_ids(self, user_id: uuid.UUID) -> Sequence[uuid.UUID]:
        calendar_ids = await self.repo.get_calendar_ids_for_user(user_id)
        if not calendar_ids:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No calendars found for this user")
        return calendar_ids

    async def _get_timezone(self, user_id: uuid.UUID) -> ZoneInfo:
        tz = await self.repo.get_user_timezone(user_id)
        return ZoneInfo(tz or "UTC")

    async def _get_primary_calendar(self, user_id: uuid.UUID) -> UserCalendar | None:
        return await self.repo.get_primary_calendar_for_user(user_id)

    @staticmethod
    def _build_kpi(key: str, title: str, result: KPIResultDTO) -> KPIMetric:
        return KPIMetric(
            key=key,
            title=title,
            value=result.value,
            change=result.change,
            positive=result.positive,
            type_value=result.type_value,
        )

    @staticmethod
    def _calculate_deep_work_hours(events: Sequence[CalendarEvent], work_days: int) -> Decimal:
        duration = sum_duration(events)
        buffer = AnalyticsCalculator._calc_buffer_time(events)
        transition = AnalyticsCalculator._calc_transition_time(events)
        capacity = Decimal(str(work_days)) * WORKDAY_DEFAULT_HOURS
        deep_work = capacity - duration - buffer - transition
        deep_work = deep_work if deep_work > Decimal("0") else Decimal("0")
        return deep_work.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _build_deep_work_kpi(current: Decimal, previous: Decimal) -> KPIResultDTO:
        change = calculate_change(current, previous)
        change_str = f"{'+' if change >= Decimal('0') else ''}{change}%"
        return KPIResultDTO(
            value=current,
            change=change_str,
            positive=change > Decimal("0"),
            type_value="time",
        )

    @staticmethod
    def _to_timezone(dt: datetime | None, tz: ZoneInfo) -> datetime:
        if dt is None:
            return datetime.now(tz)
        if dt.tzinfo:
            return dt.astimezone(tz)
        return dt.replace(tzinfo=timezone.utc).astimezone(tz)

    @staticmethod
    def _ensure_timezone(dt: datetime, tz: ZoneInfo) -> datetime:
        if dt.tzinfo:
            return dt.astimezone(tz)
        return dt.replace(tzinfo=tz)

    @staticmethod
    def _find_week_free_slots(
        start_date: datetime,
        end_date: datetime,
        busy_slots: list[tuple[datetime, datetime]],
        tz: ZoneInfo,
        work_start: str = "10:00",
        work_end: str = "18:00",
        min_duration: timedelta = timedelta(hours=2),
    ) -> list[dict]:
        free_slots: list[dict] = []
        busy_by_day: dict[str, list[tuple[datetime, datetime]]] = {}

        for start, end in busy_slots:
            day = start.astimezone(tz).date()
            busy_by_day.setdefault(day, []).append((start.astimezone(tz), end.astimezone(tz)))

        now = datetime.now(tz)
        current_date = start_date

        while current_date.date() <= end_date.date():
            if current_date.weekday() >= SATURDAY_WEEKDAY:
                current_date += timedelta(days=1)
                continue

            work_start_time = datetime.strptime(work_start, "%H:%M").time()
            work_end_time = datetime.strptime(work_end, "%H:%M").time()

            work_start_dt = datetime.combine(current_date.date(), work_start_time, tzinfo=tz)
            work_end_dt = datetime.combine(current_date.date(), work_end_time, tzinfo=tz)

            if current_date.date() == now.date():
                work_start_dt = max(work_start_dt, now)
                if work_start_dt >= work_end_dt:
                    current_date += timedelta(days=1)
                    continue

            busy = [
                (max(start, work_start_dt), min(end, work_end_dt))
                for start, end in busy_by_day.get(current_date.date(), [])
                if start < work_end_dt and end > work_start_dt
            ]
            busy.sort(key=lambda x: x[0])

            current = work_start_dt
            for b_start, b_end in busy:
                if b_start > current and b_start - current >= min_duration:
                    free_slots.append(
                        {
                            "startTime": current.strftime("%H:%M:%S"),
                            "endTime": b_start.strftime("%H:%M:%S"),
                            "date": current.date().isoformat(),
                            "duration": round((b_start - current).total_seconds() / 3600, 2),
                        }
                    )
                current = max(current, b_end)

            if work_end_dt - current >= min_duration:
                free_slots.append(
                    {
                        "startTime": current.strftime("%H:%M:%S"),
                        "endTime": work_end_dt.strftime("%H:%M:%S"),
                        "date": current.date().isoformat(),
                        "duration": round((work_end_dt - current).total_seconds() / 3600, 2),
                    }
                )

            current_date += timedelta(days=1)

        return free_slots

    @staticmethod
    def _format_hour(dt: datetime, with_meridiem: bool = False) -> str:
        fmt = "%I:%M %p" if with_meridiem else "%I:%M"
        formatted = dt.strftime(fmt)
        formatted = formatted.lstrip("0")
        return formatted.lower() if with_meridiem else formatted

    @staticmethod
    def _build_profile(email: str | None, user_map: dict[str, Any]) -> UserProfile:
        if not email:
            return UserProfile(id=None, name=None, email="", photo_url=None)

        user = user_map.get(email)
        if user:
            return UserProfile(
                id=getattr(user, "id", None),
                name=getattr(user, "name", None),
                email=getattr(user, "email", email),
                photo_url=getattr(user, "photo_url", None),
            )
        return UserProfile(id=None, name=None, email=email, photo_url=None)
