from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from models.organization_member import OrganizationMemberCalendar, CalendarTypeEnum
from models.repositories.organization_member_repository import OrganizationMemberCalendarRepository
from .base import BaseCalendarHandler
from .google import GoogleCalendarHandler


class CalendarHandlerFactory:
    @staticmethod
    def get_handler(calendar: OrganizationMemberCalendar, db: Session) -> BaseCalendarHandler:
        if calendar.type == CalendarTypeEnum.google:
            return GoogleCalendarHandler(calendar, db)
        raise NotImplementedError(f"Calendar type {calendar.type} not supported")
