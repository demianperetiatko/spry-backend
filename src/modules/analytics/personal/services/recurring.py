from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace
from typing import Any, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.modules.analytics.common.services.recurring_utils import extract_master_event_id, get_sort_value, parse_recurring_type
from src.modules.analytics.personal.calculator import AnalyticsCalculator, format_duration
from src.modules.analytics.personal.dependency import AnalyticsContext
from src.modules.analytics.personal.repository import PersonalAnalyticsRepository
from src.modules.analytics.personal.schemas import MeetingInfoDTO, RecurringMeetingTableRow, TableResponse, UserProfileDTO
from src.modules.analytics.personal.services.data_loader import AnalyticsDataLoaderService
from src.modules.calendar.models import CalendarEvent, UserCalendar
from src.modules.organization.repository import OrganizationCurrencyRepositorySQLAlchemy
from src.modules.organization_member.repository import OrganizationMemberRepository
from src.modules.permissions.enums import OrganizationPermission
from src.modules.permissions.service import Permissions

if TYPE_CHECKING:
    from src.modules.calendar.service import CalendarService
    from src.modules.user.model import User

logger = logging.getLogger(__name__)


class RecurringMeetingService:
    def __init__(
        self,
        repo: PersonalAnalyticsRepository,
        session: AsyncSession,
        data_loader: AnalyticsDataLoaderService,
        member_repo: OrganizationMemberRepository,
        permissions_service: type[Permissions],
        calendar_service: CalendarService | None = None,
    ) -> None:
        self.repo = repo
        self.session = session
        self.data_loader = data_loader
        self.member_repo = member_repo
        self.permissions_service = permissions_service
        self.calendar_service = calendar_service

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

    async def _resolve_hourly_cost(self, ctx: AnalyticsContext) -> Decimal | None:
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

        if has_access and ctx.member.hourly_cost:
            return ctx.member.hourly_cost
        return None

    async def build_recurring_table(
        self,
        ctx: AnalyticsContext,
        start_dt: datetime,
        end_dt: datetime,
        sort_by: str,
        reverse: bool,
    ) -> TableResponse:
        hourly_cost = await self._resolve_hourly_cost(ctx)

        # include_cancelled=True to count cancellation_rate, but exclude from time/cost
        events = await self.repo.get_events_for_period(ctx.calendar_ids, start_dt, end_dt, include_cancelled=True)
        unique_events = self.data_loader.get_unique_events(events)

        grouped, master_event_ids, organizer_emails = self._group_recurring_events(unique_events)

        master_event_map = await self.resolve_master_events(master_event_ids, ctx.calendar_ids)

        users = await self.repo.get_users_by_emails(list(organizer_emails))
        user_map = {u.email: u for u in users}

        results = []
        for recurring_id, group in grouped.items():
            row = self._create_recurring_row(
                recurring_id=recurring_id,
                group=group,
                master_event=master_event_map.get(recurring_id),
                user_map=user_map,
                hourly_cost=hourly_cost,
                member_email=ctx.email,
            )
            results.append(row)

        results.sort(key=lambda x: get_sort_value(x, sort_by), reverse=reverse)
        return TableResponse(total_count=len(results), data=[row.model_dump() for row in results])

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
        user_map: dict[str, User],
        hourly_cost: Decimal | None,
        member_email: str | None = None,
    ) -> RecurringMeetingTableRow:
        first_event = group[0]
        total_duration = Decimal("0")
        for event in group:
            status_val = getattr(event.status, "value", str(event.status))
            if status_val == "cancelled":
                continue
            if member_email:
                declined = any(
                    att.email == member_email and getattr(att.response_status, "value", att.response_status) == "declined"
                    for att in (event.attendees or [])
                )
                if declined:
                    continue
            total_duration += AnalyticsCalculator.duration_hours(event)
        parsed_recurring_type = parse_recurring_type(master_event)

        cancelled_count = 0
        for event in group:
            if event.status.value == "cancelled":
                cancelled_count += 1
                continue
            if member_email:
                for attendee in event.attendees:
                    if attendee.email == member_email and attendee.response_status.value == "declined":
                        cancelled_count += 1
                        break

        cancellation_rate = (
            (Decimal(str(cancelled_count)) / Decimal(str(len(group))) * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if group
            else Decimal("0")
        )

        organizer_dto = None
        if first_event.organizer_email and first_event.organizer_email in user_map:
            organizer_dto = UserProfileDTO.model_validate(user_map[first_event.organizer_email])

        return RecurringMeetingTableRow(
            id=recurring_id,
            meeting=MeetingInfoDTO(
                name=first_event.summary or "",
                duration=format_duration(AnalyticsCalculator.duration_hours(first_event)),
                recurring_type=parsed_recurring_type,
            ),
            cancellation_rate=cancellation_rate,
            total_time=total_duration,
            organizer=organizer_dto,
            total_cost=total_duration * hourly_cost if hourly_cost else None,
        )
