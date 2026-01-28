from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.session import get_session
from src.modules.calendar.client import GoogleCalendarClient
from src.modules.calendar.repository import CalendarRepository
from src.modules.calendar.service import CalendarService


def get_google_calendar_client() -> GoogleCalendarClient:
    return GoogleCalendarClient()


async def get_calendar_repository(
    session: AsyncSession = Depends(get_session),
) -> CalendarRepository:
    return CalendarRepository(session)


async def get_calendar_service(
    calendar_repo: Annotated[CalendarRepository, Depends(get_calendar_repository)],
    session: Annotated[AsyncSession, Depends(get_session)],
    google_client: Annotated[GoogleCalendarClient, Depends(get_google_calendar_client)],
) -> CalendarService:
    return CalendarService(
        calendar_repo=calendar_repo,
        session=session,
        google_client=google_client,
    )


CalendarRepoDep = Annotated[CalendarRepository, Depends(get_calendar_repository)]
CalendarServiceDep = Annotated[CalendarService, Depends(get_calendar_service)]
