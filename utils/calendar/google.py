from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from models import OrganizationMemberCalendar
from models.repositories.organization_member_repository import OrganizationMemberCalendarRepository
from .base import BaseCalendarHandler

from utils.google_api import (
    refresh_google_access_token,
    create_google_calendar_event,
    update_google_calendar_event,
    get_google_calendar_events,
    get_google_calendar_event_info,
    get_google_calendar_timezone,
)


class GoogleCalendarHandler(BaseCalendarHandler):
    def __init__(self, calendar: OrganizationMemberCalendar, db: Session):
        self.calendar = calendar
        self.db = db
        self.repo = OrganizationMemberCalendarRepository(db)
        self.access_token = self._get_valid_access_token()

    def _get_valid_access_token(self) -> str:
        if (
            self.calendar.access_token
            and self.calendar.access_token_expiry is not None
            and self.calendar.access_token_expiry > datetime.utcnow()
        ):
            return self.calendar.access_token
        data = refresh_google_access_token(self.calendar.refresh_token)
        if not isinstance(data, dict) or 'access_token' not in data:
            raise ValueError("Failed to refresh access token")
        self.calendar.access_token = data['access_token']
        self.calendar.access_token_expiry = datetime.utcnow() + timedelta(seconds=data.get('expires_in', 3600))
        self.repo.update(self.calendar)
        return self.calendar.access_token

    def create_event(self, summary, start_date, end_date, description, location):
        time_zone = get_google_calendar_timezone(self.access_token)
        return create_google_calendar_event(
            access_token=self.access_token,
            summary=summary,
            start_time=start_date,
            end_time=end_date,
            calendar_id="primary",
            time_zone=time_zone,
            description=description,
            location=location,
        )

    def update_event(self, event_id, description):
        return update_google_calendar_event(
            access_token=self.access_token,
            calendar_id="primary",
            event_id=event_id,
            description=description,
        )

    def get_event_info(self, event_id):
        return get_google_calendar_event_info(
            access_token=self.access_token,
            event_id=event_id,
            calendar_id="primary",
        )

    def get_events(self, start_date, end_date):
        return get_google_calendar_events(
            access_token=self.access_token,
            start_time=start_date,
            end_time=end_date,
        )

    def get_timezone(self):
        return get_google_calendar_timezone(self.access_token)
