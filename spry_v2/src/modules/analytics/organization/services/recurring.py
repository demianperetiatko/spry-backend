from __future__ import annotations

import logging
from collections import defaultdict
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.modules.analytics.common.schemas import MeetingInfoDTO
from src.modules.analytics.common.services.recurring_utils import extract_master_event_id, get_sort_value, parse_recurring_type
from src.modules.analytics.organization.dependency import OrganizationAnalyticsContext
from src.modules.analytics.organization.repository import OrganizationAnalyticsRepository
from src.modules.analytics.organization.schemas import RecurringMeetingTableRow, TableResponse, UserProfileDTO
from src.modules.analytics.organization.services.data_loader import OrganizationAnalyticsDataLoader
from src.modules.analytics.personal.calculator import AnalyticsCalculator, format_duration
from src.modules.calendar.models import CalendarEvent, UserCalendar
from src.modules.organization.repository import OrganizationCurrencyRepositorySQLAlchemy
from src.modules.organization_member.repository import OrganizationMemberRepository
from src.modules.permissions.enums import OrganizationPermission
from src.modules.permissions.service import Permissions

logger = logging.getLogger(__name__)


class RecurringMeetingServiceTeam:
    def __init__(
        self,
        repo: OrganizationAnalyticsRepository,
        session: AsyncSession,
        data_loader: OrganizationAnalyticsDataLoader,
        member_repo: OrganizationMemberRepository,
        permissions_service: type[Permissions],
        calendar_service: Any | None = None,
    ) -> None:
        self.repo = repo
        self.session = session
        self.data_loader = data_loader
        self.member_repo = member_repo
        self.permissions_service = permissions_service
        self.calendar_service = calendar_service

    async def _resolve_hourly_cost_map(self, ctx: OrganizationAnalyticsContext) -> dict[str, Decimal] | None:
        if not ctx.org.organizations_currency_id:
            return None
        currency_repo = OrganizationCurrencyRepositorySQLAlchemy(self.session)
        currency = await currency_repo.find_by_id(ctx.org.organizations_currency_id)
        has_access = await self.permissions_service.member_has_permission(
            member=ctx.auth_member,
            permission=OrganizationPermission.FINANCE_VIEW,
            currency=currency,
            member_repo=self.member_repo,
        )
        if not has_access:
            return None
        mapping: dict[str, Decimal] = {}
        for member in ctx.members:
            email = getattr(member.user, "email", None)
            if email and member.hourly_cost:
                mapping[email] = Decimal(str(member.hourly_cost))
        return mapping

    async def resolve_master_events(
        self,
        master_event_ids: set[str],
        user_calendar_ids: list[UUID] | None = None,
    ) -> dict[str, CalendarEvent | None]:
        if not master_event_ids:
            return {}

        master_events_list = await self.repo.get_events_by_ids(list(master_event_ids), user_calendar_ids)
        master_event_map: dict[str, CalendarEvent | None] = {evt.google_event_id: evt for evt in master_events_list}

        missing_ids = set(master_event_ids) - set(master_event_map.keys())
        if missing_ids and self.calendar_service:
            logger.debug(f"Resolving {len(missing_ids)} missing master events via API")
            for master_id in missing_ids:
                instance_event = await self._find_instance_event(master_id, user_calendar_ids)
                if instance_event:
                    api_event = await self._fetch_from_api(instance_event, master_id)
                    if api_event:
                        master_event_map[master_id] = api_event

        return master_event_map

    async def _find_instance_event(
        self,
        master_event_id: str,
        user_calendar_ids: list[UUID] | None = None,
    ) -> CalendarEvent | None:
        statement = select(CalendarEvent).where(CalendarEvent.recurring_event_id == master_event_id).limit(1)

        if user_calendar_ids:
            statement = statement.where(CalendarEvent.user_calendar_id.in_(user_calendar_ids))

        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def _fetch_from_api(
        self,
        instance_event: CalendarEvent,
        master_event_id: str,
    ) -> Any:
        if not self.calendar_service:
            return None

        try:
            statement = (
                select(CalendarEvent)
                .where(CalendarEvent.id == instance_event.id)
                .options(selectinload(CalendarEvent.user_calendar).selectinload(UserCalendar.user_access_info))
            )
            result = await self.session.execute(statement)
            event_with_calendar: CalendarEvent = result.scalar_one_or_none()

            if not event_with_calendar or not event_with_calendar.user_calendar:
                logger.warning(f"Could not find user calendar for event {instance_event.google_event_id}")
                return None

            user_calendar: UserCalendar = event_with_calendar.user_calendar
            calendar_email = user_calendar.calendar_email

            credentials = await self.calendar_service.get_valid_credentials(user_calendar)

            master_event_data = await self.calendar_service.google_client.get_event(
                access_token=credentials.token,
                calendar_email=calendar_email,
                event_id=master_event_id,
            )

            if not master_event_data:
                logger.debug(f"Master event {master_event_id} not found in Google Calendar API")
                return None

            recurrence = master_event_data.get("recurrence")
            if recurrence:
                temp_event = SimpleNamespace(recurrence=recurrence, id=master_event_id)
                return temp_event
            else:
                logger.debug(f"Master event {master_event_id} has no recurrence field")
                return None

        except Exception as e:
            logger.warning(
                f"Error fetching master event {master_event_id} from API: {e}",
                exc_info=True,
            )
            return None

    async def build_recurring_table(
        self,
        ctx: OrganizationAnalyticsContext,
        start_dt,
        end_dt,
        sort_by: str,
        reverse: bool,
    ) -> TableResponse:
        hourly_cost_map = await self._resolve_hourly_cost_map(ctx)
        member_ctx = await self.data_loader.get_member_contexts(ctx)
        calendar_ids = [cid for mc in member_ctx for cid in mc.calendar_ids]

        events = await self.repo.get_events_for_period(
            calendar_ids, start_dt, end_dt, include_attendees=True, include_cancelled=True
        )
        unique_events = self.data_loader.get_unique_events(events)

        grouped, master_event_ids, organizer_emails = self._group_recurring_events(unique_events)
        master_event_map = await self.resolve_master_events(master_event_ids, calendar_ids)

        users = await self.repo.get_users_by_emails(list(organizer_emails))
        user_map = {u.email: u for u in users}
        finance_access = hourly_cost_map is not None
        hourly_cost_map = hourly_cost_map or {}

        results = []
        for recurring_id, group in grouped.items():
            row = self._create_recurring_row(
                recurring_id=recurring_id,
                group=group,
                master_event=master_event_map.get(recurring_id),
                user_map=user_map,
                hourly_cost_map=hourly_cost_map,
                finance_access=finance_access,
            )
            row_dict = row.model_dump()
            row_dict.update(
                {
                    "meeting_name": row.meeting.name,
                    "recurring_type": row.meeting.recurring_type,
                    "duration": row.meeting.duration,
                    "attendees": len(group[0].attendees) if group and group[0].attendees else 0,
                    "total_cost": row.total_cost if finance_access else None,
                }
            )
            results.append(row_dict)

        results.sort(key=lambda x: get_sort_value(x, sort_by), reverse=reverse)
        return TableResponse(total_count=len(results), data=results)

    @staticmethod
    def _group_recurring_events(events: list[CalendarEvent]) -> tuple[dict[str, list[CalendarEvent]], set[str], set[str]]:
        grouped = defaultdict(list)
        organizer_emails = set()
        master_ids = set()

        for event in events:
            if not event.recurring_event_id:
                continue
            master_id = extract_master_event_id(event.recurring_event_id)
            grouped[master_id].append(event)
            master_ids.add(master_id)
            if event.organizer_email:
                organizer_emails.add(event.organizer_email)

        return grouped, master_ids, organizer_emails

    @staticmethod
    def _create_recurring_row(
        recurring_id: str,
        group: list[CalendarEvent],
        master_event: CalendarEvent | Any | None,
        user_map: dict[str, Any],
        hourly_cost_map: dict[str, Decimal],
        finance_access: bool,
    ) -> RecurringMeetingTableRow:
        first_event = group[0]
        total_duration = Decimal("0")
        for event in group:
            status_val = getattr(event.status, "value", str(event.status))
            if status_val == "cancelled":
                continue
            total_duration += AnalyticsCalculator.duration_hours(event)
        parsed_recurring_type = parse_recurring_type(master_event)

        cancelled_count = sum(1 for event in group if getattr(event.status, "value", "") == "cancelled")
        cancellation_rate = (
            (Decimal(str(cancelled_count)) / Decimal(str(len(group))) * Decimal("100")).quantize(Decimal("0.01"))
            if group
            else Decimal("0")
        )

        organizer_dto = None
        if first_event.organizer_email and first_event.organizer_email in user_map:
            organizer_dto = UserProfileDTO.model_validate(user_map[first_event.organizer_email])

        def _event_cost(event: CalendarEvent) -> Decimal:
            if not hourly_cost_map:
                return Decimal("0")
            attendees = {att.email for att in event.attendees if att.email}
            duration = AnalyticsCalculator.duration_hours(event)
            attendee_cost = sum((hourly_cost_map.get(email, Decimal("0")) for email in attendees), start=Decimal("0"))
            return duration * attendee_cost

        total_cost = sum((_event_cost(e) for e in group), start=Decimal("0")) if finance_access else Decimal("0")

        meeting_info = MeetingInfoDTO(
            name=first_event.summary or "",
            duration=format_duration(AnalyticsCalculator.duration_hours(first_event)),
            recurring_type=parsed_recurring_type,
        )

        return RecurringMeetingTableRow(
            id=recurring_id,
            meeting=meeting_info,
            cancellation_rate=cancellation_rate,
            total_time=total_duration,
            organizer=organizer_dto,
            total_cost=total_cost if finance_access else None,
        )
