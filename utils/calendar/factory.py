from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from models.organization_member import OrganizationMemberCalendar, CalendarTypeEnum
from models.repositories.organization_member_repository import OrganizationMemberCalendarRepository
from .base import BaseCalendarHandler
from .google_account import GoogleAccountCalendarHandler
from .google_account_service import GoogleAccountServiceCalendarHandler


class CalendarHandlerFactory:
    @staticmethod
    def get_handler(calendar: OrganizationMemberCalendar, db: Session) -> BaseCalendarHandler:
        if calendar.type == CalendarTypeEnum.google:
            return GoogleAccountCalendarHandler(calendar, db)
        elif calendar.type == CalendarTypeEnum.google_service:
            return GoogleAccountServiceCalendarHandler(calendar, db)
        raise NotImplementedError(f"Calendar type {calendar.type} not supported")
