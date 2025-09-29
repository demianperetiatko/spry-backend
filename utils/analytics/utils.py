from datetime import datetime
from datetime import timedelta
from typing import Tuple

from sqlalchemy.orm import Session

from models.repositories.organization_member_repository import OrganizationMemberCalendarRepository
from utils.calendar.factory import CalendarHandlerFactory


def count_weekdays(start, end):
    count = 0
    current = start
    while current <= end:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return count


def calculate_chance(new, old):
    if old == 0:
        if new == 0:
            return 0
        elif new > 0:
            return 100
        else:
            return -100
    return round(((new - old) / old) * 100)


def get_periods(start_date_str: str, end_date_str: str) -> Tuple[Tuple[datetime, datetime], Tuple[datetime, datetime]]:
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    current_start = datetime.combine(start_date.date(), datetime.min.time())
    current_end = datetime.combine(end_date.date(), datetime.max.time())

    delta = current_end - current_start

    prev_end = current_start - timedelta(days=1)
    prev_start = prev_end - delta

    prev_start = datetime.combine(prev_start.date(), datetime.min.time())
    prev_end = datetime.combine(prev_end.date(), datetime.max.time())

    return (current_start, current_end), (prev_start, prev_end)


def get_member_calendar_events(member_id: str, start_date: datetime, end_date: datetime, db: Session):
    events = []
    member_calendar_repository = OrganizationMemberCalendarRepository(db)
    calendars = member_calendar_repository.find_by_member_id(member_id)
    if len(calendars) == 0:
        raise ValueError("No calendar events found.")
    for calendar in calendars:
        handler = CalendarHandlerFactory.get_handler(calendar, db)
        events.extend(handler.get_events(start_date, end_date))
    return events
