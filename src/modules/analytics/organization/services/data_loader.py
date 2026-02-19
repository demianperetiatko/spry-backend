from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, TYPE_CHECKING
from uuid import UUID

from src.modules.analytics.common.data_loader import AnalyticsDataLoaderBase
from src.modules.analytics.organization.repository import OrganizationAnalyticsRepository
from src.modules.calendar.models import CalendarEvent

if TYPE_CHECKING:
    from src.modules.analytics.organization.dependency import OrganizationAnalyticsContext


@dataclass(frozen=True)
class MemberContext:
    user_id: UUID
    email: str
    calendar_ids: list[UUID]


class OrganizationAnalyticsDataLoader(AnalyticsDataLoaderBase):
    def __init__(self, repo: OrganizationAnalyticsRepository) -> None:
        self.repo = repo

    async def get_member_contexts(self, ctx: OrganizationAnalyticsContext) -> list[MemberContext]:
        calendar_map = await self.repo.get_calendar_ids_for_members([m.id for m in ctx.members])
        contexts: list[MemberContext] = []
        for member in ctx.members:
            email = getattr(member.user, "email", None)
            calendars = calendar_map.get(member.id, [])
            if email and calendars:
                contexts.append(MemberContext(user_id=member.user_id, email=email, calendar_ids=calendars))
        return contexts

    async def get_comparative_events(
        self,
        ctx: OrganizationAnalyticsContext,
        include_all: bool = False,
    ) -> tuple[list[CalendarEvent], list[CalendarEvent], list[CalendarEvent] | None, list[CalendarEvent] | None]:
        (start, end), (prev_start, prev_end) = ctx.params.parse_periods()

        member_ctx = await self.get_member_contexts(ctx)
        events: list[CalendarEvent] = []
        prev_events: list[CalendarEvent] = []

        all_events: list[CalendarEvent] | None = [] if include_all else None
        all_prev_events: list[CalendarEvent] | None = [] if include_all else None

        for mc in member_ctx:
            member_events = await self.repo.get_meeting_events_for_period(mc.calendar_ids, start, end, mc.email)
            events.extend(member_events)
            member_prev_events = await self.repo.get_meeting_events_for_period(mc.calendar_ids, prev_start, prev_end, mc.email)
            prev_events.extend(member_prev_events)

            if include_all:
                all_events.extend(await self.repo.get_events_for_period(mc.calendar_ids, start, end, include_attendees=True))
                all_prev_events.extend(
                    await self.repo.get_events_for_period(mc.calendar_ids, prev_start, prev_end, include_attendees=True)
                )

        unique_events = self.get_unique_events(events)
        unique_prev = self.get_unique_events(prev_events)

        all_unique_events = self.get_unique_events(all_events) if all_events is not None else None
        all_unique_prev = self.get_unique_events(all_prev_events) if all_prev_events is not None else None

        return unique_events, unique_prev, all_unique_events, all_unique_prev

    async def get_analyzable_events(self, ctx: OrganizationAnalyticsContext) -> list[CalendarEvent]:
        start_dt = ctx.params.parse_start_datetime().replace(hour=0, minute=0, second=0)
        end_dt = ctx.params.parse_end_datetime()

        member_ctx = await self.get_member_contexts(ctx)
        events: list[CalendarEvent] = []
        for mc in member_ctx:
            events.extend(await self.repo.get_meeting_events_for_period(mc.calendar_ids, start_dt, end_dt, mc.email))
        return self.get_unique_events(events)

    async def get_events_for_chart(self, ctx: OrganizationAnalyticsContext) -> list[CalendarEvent]:
        start_dt = ctx.params.parse_start_datetime()
        end_dt = ctx.params.parse_end_datetime()

        member_ctx = await self.get_member_contexts(ctx)
        events: list[CalendarEvent] = []
        for mc in member_ctx:
            events.extend(await self.repo.get_meeting_events_for_period(mc.calendar_ids, start_dt, end_dt, mc.email))
        return self.get_unique_events(events)

    @staticmethod
    def to_legacy_event(event: CalendarEvent) -> dict:
        return {
            "id": event.id,
            "recurringEventId": event.recurring_event_id,
            "attendees": [{"email": att.email} for att in event.attendees] if event.attendees else [],
            "start": {"dateTime": event.start_datetime.isoformat()} if event.start_datetime else {},
            "end": {"dateTime": event.end_datetime.isoformat()} if event.end_datetime else {},
            "status": event.status.value if hasattr(event.status, "value") else str(event.status),
            "organizer": {"email": event.organizer_email} if event.organizer_email else {},
            "creator": {"self": event.is_self_created},
            "description": event.description or "",
            "summary": event.summary or "",
        }

    @classmethod
    def to_legacy_events(cls, events: Sequence[CalendarEvent]) -> list[dict]:
        return [cls.to_legacy_event(event) for event in events]
