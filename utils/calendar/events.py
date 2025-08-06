from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from .event import get_calendar_events

from models.repositories.organization_member_repository import OrganizationMemberCalendarRepository


def get_member_calendar_events(member_id: str, start_date: datetime, end_date: datetime, db: Session):
    events = []
    member_calendar_repository = OrganizationMemberCalendarRepository(db)
    calendars = member_calendar_repository.find_by_member_id(member_id)
    if len(calendars) == 0:
        raise ValueError("No calendar events found.")
    for calendar in calendars:
        events.extend(get_calendar_events(calendar, start_date, end_date, db))
    return events
