from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.session import get_session
from src.modules.auth.dependency import OrganizationContext, get_organization_context
from src.modules.calendar.client import GoogleCalendarClient
from src.modules.calendar.repository import CalendarRepository
from src.modules.calendar.service import CalendarService
from src.modules.home.repository import HomeRepository
from src.modules.home.schemas import AgendaDescriptionRequest, AgendaResponse, DeepWorkSlotsResponse, KPIResponse, TimeSlot
from src.modules.home.service import HomeService

router = APIRouter(prefix="/organizations/{organization_id}/home", tags=["home"])


async def get_home_service(session: AsyncSession = Depends(get_session)) -> HomeService:
    calendar_repo = CalendarRepository(session=session)
    calendar_service = CalendarService(calendar_repo=calendar_repo, session=session, google_client=GoogleCalendarClient())
    repo = HomeRepository(session)
    return HomeService(repo, calendar_service)


@router.get("/kpi", response_model=KPIResponse)
async def get_home_kpi(
    ctx: Annotated[OrganizationContext, Depends(get_organization_context)],
    service: HomeService = Depends(get_home_service),
) -> KPIResponse:
    return await service.get_kpis(ctx)


@router.get("/deep-work/time-slot", response_model=DeepWorkSlotsResponse)
async def get_deep_work_slots(
    ctx: Annotated[OrganizationContext, Depends(get_organization_context)],
    service: HomeService = Depends(get_home_service),
) -> DeepWorkSlotsResponse:
    return await service.get_deep_work_slots(ctx)


@router.post("/deep-work/time-slot")
async def create_deep_work_slots(
    timeslots: list[TimeSlot],
    ctx: Annotated[OrganizationContext, Depends(get_organization_context)],
    service: HomeService = Depends(get_home_service),
) -> list[dict]:
    return await service.create_deep_work_slots(ctx, timeslots)


@router.get("/agenda-beta", response_model=AgendaResponse)
async def get_agenda_beta(
    ctx: Annotated[OrganizationContext, Depends(get_organization_context)],
    service: HomeService = Depends(get_home_service),
) -> AgendaResponse:
    return await service.get_agenda(ctx)


@router.post("/agenda-beta/{event_id}/notify")
async def notify_agenda_completed(
    event_id: str,
    ctx: Annotated[OrganizationContext, Depends(get_organization_context)],
    service: HomeService = Depends(get_home_service),
) -> dict:
    return await service.notify_agenda(ctx, event_id)


@router.post("/agenda-beta/{event_id}/add")
async def add_agenda_description(
    event_id: str,
    data: AgendaDescriptionRequest,
    ctx: Annotated[OrganizationContext, Depends(get_organization_context)],
    service: HomeService = Depends(get_home_service),
) -> dict:
    return await service.add_agenda_description(ctx, event_id, data)
