from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.session import get_session
from src.modules.analytics.personal.dependency import AnalyticsContext, get_personal_analytics_context
from src.modules.analytics.personal.repository import (
    PersonalAnalyticsRepository,
    get_personal_analytics_repository,
)
from src.modules.analytics.personal.schemas import (
    DistributionResponse,
    MeetingChartResponse,
    ParticipantsResponse,
    PersonalKPIsResponse,
    ProductivityResponse,
    SortByType,
    SortOrderType,
    TableResponse,
    TableType,
)
from src.modules.analytics.personal.services.data_loader import AnalyticsDataLoaderService
from src.modules.analytics.personal.services.metrics import PersonalMetricsService
from src.modules.analytics.personal.services.recurring import RecurringMeetingService
from src.modules.calendar.client import GoogleCalendarClient
from src.modules.calendar.repository import CalendarRepository
from src.modules.calendar.service import CalendarService
from src.modules.organization_member.repository import (
    OrganizationMemberRepository,
    get_organization_member_repository,
)
from src.modules.permissions.service import Permissions, get_permissions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/organizations/{organization_id}/members/{user_id}/analytics/personal", tags=["analytics-personal"])

AnalyticsContextDep = Annotated[AnalyticsContext, Depends(get_personal_analytics_context)]


async def get_optional_calendar_service(session: AsyncSession = Depends(get_session)) -> CalendarService | None:
    try:
        calendar_repo = CalendarRepository(session=session)
        google_client = GoogleCalendarClient()
        return CalendarService(calendar_repo=calendar_repo, session=session, google_client=google_client)
    except (ImportError, Exception) as e:
        logger.warning(f"CalendarService unavailable: {e}")
        return None


async def get_data_loader_service(
    analytics_repo: PersonalAnalyticsRepository = Depends(get_personal_analytics_repository),
) -> AnalyticsDataLoaderService:
    return AnalyticsDataLoaderService(analytics_repo)


async def get_metrics_service(
    data_loader: AnalyticsDataLoaderService = Depends(get_data_loader_service),
    member_repo: OrganizationMemberRepository = Depends(get_organization_member_repository),
    permissions_service: type[Permissions] = Depends(get_permissions),
    session: AsyncSession = Depends(get_session),
) -> PersonalMetricsService:
    return PersonalMetricsService(
        data_loader=data_loader,
        member_repo=member_repo,
        permissions_service=permissions_service,
        session=session,
    )


async def get_recurring_service(
    analytics_repo: PersonalAnalyticsRepository = Depends(get_personal_analytics_repository),
    session: AsyncSession = Depends(get_session),
    data_loader: AnalyticsDataLoaderService = Depends(get_data_loader_service),
    member_repo: OrganizationMemberRepository = Depends(get_organization_member_repository),
    permissions_service: type[Permissions] = Depends(get_permissions),
    calendar_service: CalendarService | None = Depends(get_optional_calendar_service),
) -> RecurringMeetingService:
    return RecurringMeetingService(
        repo=analytics_repo,
        session=session,
        data_loader=data_loader,
        member_repo=member_repo,
        permissions_service=permissions_service,
        calendar_service=calendar_service,
    )


MetricsServiceDep = Annotated[PersonalMetricsService, Depends(get_metrics_service)]
RecurringServiceDep = Annotated[RecurringMeetingService, Depends(get_recurring_service)]


@router.get("/meeting", response_model=MeetingChartResponse)
async def get_personal_meetings_chart(
    ctx: AnalyticsContextDep,
    metrics_service: MetricsServiceDep,
) -> MeetingChartResponse:
    return await metrics_service.get_meeting_chart(ctx)


@router.get("/meeting/kpi", response_model=PersonalKPIsResponse)
async def get_personal_kpi(
    ctx: AnalyticsContextDep,
    metrics_service: MetricsServiceDep,
) -> PersonalKPIsResponse:
    kpis = await metrics_service.get_personal_kpis(ctx)
    return PersonalKPIsResponse(data=kpis)


@router.get("/meeting/participants", response_model=ParticipantsResponse)
async def get_personal_meeting_participants(
    ctx: AnalyticsContextDep,
    metrics_service: MetricsServiceDep,
) -> ParticipantsResponse:
    participants = await metrics_service.get_meeting_participants(ctx)
    return ParticipantsResponse(data=participants)


@router.get("/meeting/distribution", response_model=DistributionResponse)
async def get_personal_meeting_distribution(
    ctx: AnalyticsContextDep,
    metrics_service: MetricsServiceDep,
) -> DistributionResponse:
    distribution = await metrics_service.get_meeting_distribution(ctx)
    return DistributionResponse(data=distribution)


@router.get("/meeting/table", response_model=TableResponse)
async def get_personal_table(
    ctx: AnalyticsContextDep,
    metrics_service: MetricsServiceDep,
    recurring_service: RecurringServiceDep,
    sort_by: SortByType = Query(...),
    sort_order: SortOrderType = Query(SortOrderType.ASC),
    table_type: TableType = Query(TableType.COLLABORATION),
) -> TableResponse:
    start_dt = ctx.params.parse_start_datetime()
    end_dt = ctx.params.parse_end_datetime()
    reverse = sort_order == SortOrderType.DESC

    if table_type == TableType.COLLABORATION:
        return await metrics_service.get_collaboration_table(ctx, start_dt, end_dt, sort_by.value, reverse)

    return await recurring_service.build_recurring_table(ctx, start_dt, end_dt, sort_by.value, reverse)


@router.get("/productivity", response_model=ProductivityResponse)
async def get_personal_productivity(
    ctx: AnalyticsContextDep,
    metrics_service: MetricsServiceDep,
) -> ProductivityResponse:
    productivity = await metrics_service.get_productivity(ctx)
    return ProductivityResponse(productivity=productivity)
