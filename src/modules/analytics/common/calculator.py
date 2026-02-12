from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from src.modules.calendar.models import CalendarEvent

if TYPE_CHECKING:
    from collections.abc import Sequence

WORKDAY_DEFAULT_HOURS = Decimal("8")
BUFFER_PER_SIDE_HOURS = Decimal(str(10 / 60))
MAX_TRANSITION_TIME_HOURS = Decimal(str(90 / 60))


def duration_hours(event: CalendarEvent) -> Decimal:
    """Event duration in hours (Decimal)."""
    if not (event.start_datetime and event.end_datetime):
        return Decimal("0")
    delta = event.end_datetime - event.start_datetime
    return Decimal(str(delta.total_seconds())) / Decimal("3600")


def sum_duration(events: Sequence[CalendarEvent]) -> Decimal:
    """Sum of all event durations in hours."""
    return sum((duration_hours(e) for e in events), start=Decimal("0"))


def calculate_change(new_value: Decimal, old_value: Decimal) -> Decimal:
    """Percentage change new vs old."""
    if old_value == Decimal("0"):
        if new_value > Decimal("0"):
            return Decimal("100")
        if new_value == Decimal("0"):
            return Decimal("0")
        return Decimal("-100")
    result = ((new_value - old_value) / old_value) * Decimal("100")
    return result.quantize(Decimal("0.1"))


def format_duration(duration_hours_val: Decimal) -> str:
    """Format duration as 'Xh Ym'."""
    duration_minutes = int(Decimal(duration_hours_val) * 60)
    hours = duration_minutes // 60
    minutes = duration_minutes % 60
    if hours == 0 and minutes == 0:
        return ""
    if hours == 0:
        return f"{minutes}m"
    if minutes == 0:
        return f"{hours}h"
    return f"{hours}h {minutes}m"


def count_weekdays(start: datetime, end: datetime) -> int:
    """Count of weekdays between dates inclusive."""
    count = 0
    current = start.date()
    end_date = end.date()
    while current <= end_date:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return count
