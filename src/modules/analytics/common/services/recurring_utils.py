from __future__ import annotations

import logging
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.calendar.models import CalendarEvent

logger = logging.getLogger(__name__)

ALL_DAYS = {"MO", "TU", "WE", "TH", "FR", "SA", "SU"}
BUSINESS_DAYS = {"MO", "TU", "WE", "TH", "FR"}
MULTI_DAY_THRESHOLD = 2
BI_WEEKLY_INTERVAL = 2


def extract_master_event_id(recurring_event_id: str) -> str:
    if not recurring_event_id:
        return recurring_event_id
    if "_R" in recurring_event_id:
        base_id = recurring_event_id.split("_R")[0]
        return base_id
    return recurring_event_id


def parse_recurring_type(event: CalendarEvent | Any | None) -> str:
    if not event:
        return ""

    recurrence: Iterable[str] | None = getattr(event, "recurrence", None)
    if not recurrence:
        return ""

    for rule in recurrence:
        if isinstance(rule, str) and rule.startswith("RRULE:"):
            try:
                rule_parts = rule[6:].split(";")
                freq = None
                interval = 1
                days_of_week: list[str] = []

                for part in rule_parts:
                    if part.startswith("FREQ="):
                        freq = part[5:].upper()
                    elif part.startswith("INTERVAL="):
                        interval = int(part[9:])
                    elif part.startswith("BYDAY="):
                        days_of_week = [d.strip() for d in part[6:].split(",")]

                if freq == "WEEKLY":
                    day_set = set(days_of_week)
                    num_days = len(days_of_week)

                    if interval == 1:
                        if day_set == ALL_DAYS or day_set == BUSINESS_DAYS:
                            return "Daily"
                        if num_days >= MULTI_DAY_THRESHOLD:
                            return f"{num_days}x Weekly"
                        return "Weekly"

                    if interval == BI_WEEKLY_INTERVAL:
                        if num_days >= MULTI_DAY_THRESHOLD:
                            return f"{num_days}x Bi-weekly"
                        return "Bi-weekly"

                    if num_days >= MULTI_DAY_THRESHOLD:
                        return f"{num_days}x Every {interval} weeks"
                    return f"Every {interval} weeks"

                if freq == "DAILY":
                    if interval == 1:
                        return "Daily"
                    return f"Every {interval} days"

                if freq == "MONTHLY":
                    if interval == 1:
                        return "Monthly"
                    return f"Every {interval} months"

                if freq == "YEARLY":
                    if interval == 1:
                        return "Yearly"
                    return f"Every {interval} years"

                if freq:
                    return freq.capitalize()

            except Exception as exc:
                logger.debug("Failed to parse recurrence rule %s: %s", rule, exc)
                continue

    return ""


async def resolve_recurrence_fallback(
    session: AsyncSession,
    grouped: dict[str, list[CalendarEvent]],
    master_event_map: dict[str, CalendarEvent | Any | None],
    calendar_ids: list[UUID],
) -> dict[str, list[str]]:
    missing_recurrence_ids: set[str] = set()
    for recurring_id in grouped:
        master = master_event_map.get(recurring_id)
        if not master or not getattr(master, "recurrence", None):
            missing_recurrence_ids.add(recurring_id)

    recurrence_fallback: dict[str, list[str]] = {}
    if not missing_recurrence_ids:
        return recurrence_fallback

    stmt = select(
        CalendarEvent.google_event_id,
        CalendarEvent.recurring_event_id,
        CalendarEvent.recurrence,
    ).where(
        or_(
            CalendarEvent.google_event_id.in_(list(missing_recurrence_ids)),
            CalendarEvent.recurring_event_id.in_(list(missing_recurrence_ids)),
        ),
        CalendarEvent.recurrence.isnot(None),
        CalendarEvent.user_calendar_id.in_(calendar_ids),
    )
    result = await session.execute(stmt)
    for gid, rid, rec in result.all():
        key = gid if gid in missing_recurrence_ids else rid
        if key and key not in recurrence_fallback:
            recurrence_fallback[key] = rec

    return recurrence_fallback


def get_sort_value(row: Any, full_path: str) -> Any:
    try:
        if "." in full_path:
            parts = full_path.split(".")
            obj = row
            for part in parts:
                if isinstance(obj, dict):
                    obj = obj.get(part)
                else:
                    obj = getattr(obj, part, None)
                if obj is None:
                    return 0
            return obj
        if isinstance(row, dict):
            return row.get(full_path, 0)
        return getattr(row, full_path, 0)
    except (AttributeError, TypeError):
        return 0
