from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Sequence

from src.modules.calendar.models import CalendarEvent


class AnalyticsDataLoaderBase:
    @staticmethod
    def get_unique_events(events: Sequence[CalendarEvent] | None) -> list[CalendarEvent]:
        if not events:
            return []
        seen_ids = set()
        unique_events: list[CalendarEvent] = []
        for event in events:
            if event.id not in seen_ids:
                seen_ids.add(event.id)
                unique_events.append(event)
        return unique_events

    @staticmethod
    def get_attendee_emails(event: CalendarEvent) -> set[str]:
        if not event.attendees:
            return set()
        return {att.email for att in event.attendees if att.email}

    @staticmethod
    def group_events_by_date(
        events: Sequence[CalendarEvent],
        start_date: datetime,
        end_date: datetime,
    ) -> dict[date, list[CalendarEvent]]:
        grouped: dict[date, list[CalendarEvent]] = defaultdict(list)

        for event in events:
            if not event.start_datetime:
                continue
            event_date = event.start_datetime.date()
            grouped[event_date].append(event)

        result: dict[date, list[CalendarEvent]] = {}
        current = start_date.date()
        end_date_only = end_date.date()

        while current <= end_date_only:
            result[current] = grouped.get(current, [])
            current += timedelta(days=1)

        return result
