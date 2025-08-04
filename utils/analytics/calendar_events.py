from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from utils.google_api import refresh_google_access_token, get_calendar_events

from models.organization_member import CalendarTypeEnum
from models.repositories.organization_member_repository import OrganizationMemberCalendarRepository

def get_member_calendar_events(member_id: str, start_date: datetime, end_date: datetime, db: Session):
    events = []
    member_calendar_repository = OrganizationMemberCalendarRepository(db)
    calendars = member_calendar_repository.find_by_member_id(member_id)
    if len(calendars) == 0:
        raise ValueError("No calendar events found.")
    for calendar in calendars:
        if calendar.type == CalendarTypeEnum.GOOGLE:
            if calendar.access_token and calendar.access_token_expiry and calendar.access_token_expiry > datetime.utcnow():
                access_token = calendar.access_token
            else:
                data = refresh_google_access_token(calendar.refresh_token)
                if isinstance(data, dict) and 'access_token' in data:
                    access_token = data['access_token']
                    expires_in_seconds = data.get('expires_in', 3600)
                    calendar.access_token = access_token
                    calendar.access_token_expiry = datetime.utcnow() + timedelta(seconds=expires_in_seconds)
                    member_calendar_repository.update(calendar)
                else:
                    raise ValueError(f"Failed to refresh access token")
            events.extend(
                get_calendar_events(access_token, start_date, end_date)
            )

    return events