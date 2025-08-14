import os
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from models import OrganizationMemberCalendar
from models.repositories.organization_member_repository import OrganizationMemberCalendarRepository
from .base import BaseCalendarHandler

from utils.google_api import (
    create_google_calendar_event,
    update_google_calendar_event,
    get_google_calendar_events,
    get_google_calendar_event_info,
    get_google_calendar_timezone,
)

from google.oauth2 import service_account
import google.auth.transport.requests


SCOPES = ['https://www.googleapis.com/auth/calendar']


class GoogleAccountServiceCalendarHandler(BaseCalendarHandler):
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

        credentials_path = self._get_credentials_path_from_email(self.calendar.calendar_email)
        print(credentials_path)
        if not os.path.exists(credentials_path):
            raise FileNotFoundError(f"Service account file not found at: {credentials_path}")

        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=SCOPES
        )
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)

        self.calendar.access_token = credentials.token
        self.calendar.access_token_expiry = datetime.utcnow() + timedelta(seconds=3600)
        self.repo.update(self.calendar)

        return self.calendar.access_token

    def _get_credentials_path_from_email(self, email: str) -> str:
        prefix = email.split('@')[0]
        safe_name = prefix.replace('-', '_').replace('.', '_')
        filename = f"spry_{safe_name}.json"
        directory = os.getenv("DEMO_GOOGLE_ACCOUNT_SERVICE_FOLDER", "demo_google_account_service_key")
        return os.path.join(directory, filename)

    def create_event(self, summary, start_date, end_date, description="", location=""):
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
