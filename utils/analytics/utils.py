from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from utils.calendar.factory import CalendarHandlerFactory

from models.repositories.organization_member_repository import OrganizationMemberCalendarRepository


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
