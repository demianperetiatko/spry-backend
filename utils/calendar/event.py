from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from utils.google_api import (
    refresh_google_access_token,
    create_google_calendar_event,
    update_google_calendar_event,
    get_google_calendar_events,
    get_google_calendar_event_info,
    get_google_calendar_timezone,
)

from models.organization_member import OrganizationMemberCalendar, CalendarTypeEnum
from models.repositories.organization_member_repository import OrganizationMemberCalendarRepository


def create_calendar_event(
        calendar: OrganizationMemberCalendar,
        start_date: datetime,
        end_date: datetime,
        summary: str,
        db: Session,
        description: str = "",
        location: str = "",
):
    member_calendar_repository = OrganizationMemberCalendarRepository(db)
    if calendar.type == CalendarTypeEnum.google:
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
        time_zone = get_google_calendar_timezone(access_token)
        return create_google_calendar_event(
            token=access_token,
            summary=summary,
            start_time=start_date,
            end_time=end_date,
            calendar_id="primary",
            time_zone=time_zone,
            description=description,
            location=location,
        )


def update_calendar_event(
        calendar: OrganizationMemberCalendar,
        event_id: str,
        description: str,
        db: Session
):
    member_calendar_repository = OrganizationMemberCalendarRepository(db)
    if calendar.type == CalendarTypeEnum.google:
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
        return update_google_calendar_event(
            access_token=access_token,
            calendar_id="primary",
            event_id=event_id,
            description=description,
        )


def get_calendar_event_info(
        calendar: OrganizationMemberCalendar,
        event_id: str,
        db: Session
):
    member_calendar_repository = OrganizationMemberCalendarRepository(db)
    if calendar.type == CalendarTypeEnum.google:
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
        return get_google_calendar_event_info(
            access_token,
            event_id,
            calendar_id="primary",
        )


def get_calendar_events(
        calendar: OrganizationMemberCalendar,
        start_date: datetime,
        end_date: datetime,
        db: Session):
    member_calendar_repository = OrganizationMemberCalendarRepository(db)

    if calendar.type == CalendarTypeEnum.google:
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
        return get_google_calendar_events(access_token, start_date, end_date)
