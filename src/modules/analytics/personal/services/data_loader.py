from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from src.modules.analytics.common.data_loader import AnalyticsDataLoaderBase
from src.modules.analytics.personal.dependency import AnalyticsContext
from src.modules.calendar.models import CalendarEvent

if TYPE_CHECKING:
    from collections.abc import Sequence
    from src.modules.analytics.personal.repository import PersonalAnalyticsRepository


class AnalyticsDataLoaderService(AnalyticsDataLoaderBase):
    def __init__(self, analytics_repo: PersonalAnalyticsRepository) -> None:
        self.repo = analytics_repo

    async def get_comparative_events(
        self, ctx: AnalyticsContext, include_all: bool = False
    ) -> tuple[list[CalendarEvent], list[CalendarEvent], list[CalendarEvent] | None, list[CalendarEvent] | None]:
        (start, end), (prev_start, prev_end) = ctx.params.parse_periods()

        events = await self.repo.get_meeting_events_for_period(ctx.calendar_ids, start, end, ctx.email)
        prev_events = await self.repo.get_meeting_events_for_period(ctx.calendar_ids, prev_start, prev_end, ctx.email)

        unique_events = self.get_unique_events(events)
        unique_prev = self.get_unique_events(prev_events)

        all_events = None
        all_prev_events = None
        if include_all:
            all_events = await self.repo.get_events_for_period(ctx.calendar_ids, start, end)
            all_prev_events = await self.repo.get_events_for_period(ctx.calendar_ids, prev_start, prev_end)

        return unique_events, unique_prev, all_events, all_prev_events

    async def get_analyzable_events(self, ctx: AnalyticsContext) -> list[CalendarEvent]:
        start_dt = ctx.params.parse_start_datetime().replace(hour=0, minute=0, second=0)
        end_dt = ctx.params.parse_end_datetime()

        events = await self.repo.get_meeting_events_for_period(ctx.calendar_ids, start_dt, end_dt, ctx.email)
        return self.get_unique_events(events)

    async def get_events_for_chart(self, ctx: AnalyticsContext) -> list[CalendarEvent]:
        start_dt = ctx.params.parse_start_datetime()
        end_dt = ctx.params.parse_end_datetime()

        events = await self.repo.get_meeting_events_for_period(ctx.calendar_ids, start_dt, end_dt, ctx.email)
        return self.get_unique_events(events)
