"""
Lightweight factory helpers — build CalendarEvent / CalendarEventAttendee
objects without touching the database.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

from src.modules.calendar.models import CalendarEvent, CalendarEventAttendee
from src.modules.enums import CalendarAttendeeResponseStatusEnum, CalendarEventStatusEnum


def dt(hour: int = 10, day: int = 2, month: int = 6, year: int = 2026) -> datetime:
    return datetime(year, month, day, hour, 0, 0, tzinfo=timezone.utc)


def make_attendee(
    email: str = "user@example.com",
    resource: bool = False,
    response_status: CalendarAttendeeResponseStatusEnum = CalendarAttendeeResponseStatusEnum.ACCEPTED,
) -> CalendarEventAttendee:
    a = MagicMock(spec=CalendarEventAttendee)
    a.email = email
    a.resource = resource
    a.response_status = response_status
    a.organizer = False
    a.optional = False
    return a


def make_event(
    *,
    duration_hours: float = 1.0,
    organizer_email: str = "user@example.com",
    attendees: list[Any] | None = None,
    description: str | None = None,
    recurring_event_id: str | None = None,
    status: CalendarEventStatusEnum = CalendarEventStatusEnum.CONFIRMED,
    start_hour: int = 10,
    day: int = 2,
    large: bool = False,
) -> CalendarEvent:
    """Build a mock CalendarEvent."""
    e = MagicMock(spec=CalendarEvent)
    e.id = uuid.uuid4()
    e.google_event_id = str(uuid.uuid4())
    start = dt(hour=start_hour, day=day)
    end = datetime(start.year, start.month, start.day, start.hour, 0, 0, tzinfo=timezone.utc)
    end = end.replace(hour=start.hour + int(duration_hours), minute=int((duration_hours % 1) * 60))
    e.start_datetime = start
    e.end_datetime = end
    e.organizer_email = organizer_email
    e.description = description
    e.recurring_event_id = recurring_event_id
    e.status = status
    e.summary = "Meeting"
    e.recurrence = None
    e.raw_data = None

    if attendees is None:
        n = 7 if large else 2
        attendees = [make_attendee(f"p{i}@example.com") for i in range(n)]
    e.attendees = attendees
    return e


def make_ctx(
    email: str = "user@example.com",
    start: datetime | None = None,
    end: datetime | None = None,
    workday_hours: Decimal = Decimal("8"),
    is_same_member: bool = True,
) -> Any:
    """Build a minimal AnalyticsContext mock."""
    ctx = MagicMock()
    ctx.email = email
    ctx.workday_hours = workday_hours

    start = start or dt(day=1)
    end = end or dt(day=20)

    params = MagicMock()
    params.parse_periods.return_value = ((start, end), (None, None))
    params.start_date = start.strftime("%Y-%m-%d")
    params.end_date = end.strftime("%Y-%m-%d")
    ctx.params = params

    member = MagicMock()
    member.id = uuid.uuid4()
    member.hourly_cost = Decimal("75")
    ctx.member = member

    auth_member = MagicMock()
    auth_member.id = member.id if is_same_member else uuid.uuid4()
    auth_member.role = "MANAGER"
    ctx.auth_member = auth_member

    org = MagicMock()
    org.id = uuid.uuid4()
    ctx.org = org

    return ctx
