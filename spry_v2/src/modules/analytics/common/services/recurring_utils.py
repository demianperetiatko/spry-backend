from __future__ import annotations

import logging
from typing import Any, Iterable

from src.modules.calendar.models import CalendarEvent

logger = logging.getLogger(__name__)


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
                day = None
                for part in rule_parts:
                    if part.startswith("FREQ="):
                        freq = part[5:].lower()
                    elif part.startswith("BYDAY="):
                        day = part[6:]

                day_abbreviations = {
                    "MO": "Mon",
                    "TU": "Tue",
                    "WE": "Wed",
                    "TH": "Thu",
                    "FR": "Fri",
                    "SA": "Sat",
                    "SU": "Sun",
                }

                if freq == "weekly" and day and day in day_abbreviations:
                    return f"Weekly on {day_abbreviations[day]}"
                if freq == "daily":
                    return "Daily"
                if freq == "monthly":
                    return "Monthly"
                if freq == "yearly":
                    return "Yearly"
                if freq:
                    return freq.capitalize()
            except Exception as exc:  # noqa: BLE001
                logger.debug("Failed to parse recurrence rule %s: %s", rule, exc)
                continue

    return ""


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
