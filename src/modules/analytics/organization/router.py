from __future__ import annotations

import logging
from typing import Annotated, TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from src.modules.calendar.service import CalendarService

from src.core.database.session import get_session
from src.modules.analytics.organization.dependency import OrganizationAnalyticsContext, get_organization_analytics_context
from src.modules.analytics.organization.repository import (
    OrganizationAnalyticsRepository,
    get_organization_analytics_repository,
)
from src.modules.analytics.organization.schemas import (
    AnalyticsType,
    DistributionResponse,
    KPIsResponse,
    ListType,
    MeetingChartResponse,
    ParticipantsResponse,
    ProductivityResponse,
    SortByType,
    SortOrderType,
    TableResponse,
    TableType,
)
from src.modules.analytics.organization.services.data_loader import OrganizationAnalyticsDataLoader
from src.modules.analytics.organization.services.metrics import OrganizationMetricsService
from src.modules.analytics.organization.services.recurring import RecurringMeetingServiceTeam
from src.modules.organization_member.repository import OrganizationMemberRepository, get_organization_member_repository
from src.modules.permissions.service import Permissions, get_permissions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/organizations/{organization_id}/analytics/organization", tags=["analytics-organization"])

AnalyticsCtxDep = Annotated[OrganizationAnalyticsContext, Depends(get_organization_analytics_context)]


async def get_optional_calendar_service(session: AsyncSession = Depends(get_session)) -> CalendarService | None:
    try:
        from src.modules.calendar.client import GoogleCalendarClient
        from src.modules.calendar.repository import CalendarRepository
        from src.modules.calendar.service import CalendarService

        calendar_repo = CalendarRepository(session=session)
        google_client = GoogleCalendarClient()
        return CalendarService(calendar_repo=calendar_repo, session=session, google_client=google_client)
    except (ImportError, Exception) as e:
        logger.warning(f"CalendarService unavailable: {e}")
        return None


async def get_data_loader_service(
    analytics_repo: OrganizationAnalyticsRepository = Depends(get_organization_analytics_repository),
) -> OrganizationAnalyticsDataLoader:
    return OrganizationAnalyticsDataLoader(analytics_repo)


async def get_metrics_service(
    data_loader: OrganizationAnalyticsDataLoader = Depends(get_data_loader_service),
    analytics_repo: OrganizationAnalyticsRepository = Depends(get_organization_analytics_repository),
    member_repo: OrganizationMemberRepository = Depends(get_organization_member_repository),
    permissions_service: type[Permissions] = Depends(get_permissions),
    session: AsyncSession = Depends(get_session),
) -> OrganizationMetricsService:
    return OrganizationMetricsService(
        data_loader=data_loader,
        analytics_repo=analytics_repo,
        member_repo=member_repo,
        permissions_service=permissions_service,
        session=session,
    )


async def get_recurring_service(
    analytics_repo: OrganizationAnalyticsRepository = Depends(get_organization_analytics_repository),
    session: AsyncSession = Depends(get_session),
    data_loader: OrganizationAnalyticsDataLoader = Depends(get_data_loader_service),
    member_repo: OrganizationMemberRepository = Depends(get_organization_member_repository),
    permissions_service: type[Permissions] = Depends(get_permissions),
    calendar_service: CalendarService | None = Depends(get_optional_calendar_service),
) -> RecurringMeetingServiceTeam:
    return RecurringMeetingServiceTeam(
        repo=analytics_repo,
        session=session,
        data_loader=data_loader,
        member_repo=member_repo,
        permissions_service=permissions_service,
        calendar_service=calendar_service,
    )


MetricsServiceDep = Annotated[OrganizationMetricsService, Depends(get_metrics_service)]
RecurringServiceDep = Annotated[RecurringMeetingServiceTeam, Depends(get_recurring_service)]


@router.get("/meeting/kpi", response_model=KPIsResponse)
async def get_organization_kpi(ctx: AnalyticsCtxDep, metrics_service: MetricsServiceDep) -> KPIsResponse:
    return await metrics_service.get_kpis(ctx)


@router.get("/meeting", response_model=MeetingChartResponse)
async def get_organization_meetings(
    ctx: AnalyticsCtxDep,
    metrics_service: MetricsServiceDep,
    analytics_type: AnalyticsType = Query(AnalyticsType.TIME),
) -> MeetingChartResponse:
    return await metrics_service.get_meeting_chart(ctx, analytics_type)


@router.get("/meeting/participants", response_model=ParticipantsResponse)
async def get_organization_meeting_participants(
    ctx: AnalyticsCtxDep,
    metrics_service: MetricsServiceDep,
) -> ParticipantsResponse:
    participants = await metrics_service.get_meeting_participants(ctx)
    return ParticipantsResponse(data=participants)


@router.get("/meeting/distribution", response_model=DistributionResponse)
async def get_organization_meeting_distribution(
    ctx: AnalyticsCtxDep,
    metrics_service: MetricsServiceDep,
) -> DistributionResponse:
    return await metrics_service.get_meeting_distribution(ctx)


@router.get("/productivity", response_model=ProductivityResponse)
async def get_organization_productivity(
    ctx: AnalyticsCtxDep,
    metrics_service: MetricsServiceDep,
    list_type: ListType = Query(ListType.MEMBERS),
    sort_by: SortByType = Query(SortByType.MEETINGS_TIME),
    sort_order: SortOrderType = Query(SortOrderType.ASC),
) -> ProductivityResponse:
    return await metrics_service.get_productivity(ctx, list_type, sort_by, sort_order)


@router.get("/meeting/table", response_model=TableResponse)
async def get_organization_meeting_table(
    ctx: AnalyticsCtxDep,
    metrics_service: MetricsServiceDep,
    recurring_service: RecurringServiceDep,
    sort_by: SortByType | None = Query(None),
    sort_order: SortOrderType = Query(SortOrderType.ASC),
    table_type: TableType = Query(TableType.ATTENDEES),
) -> TableResponse:
    start_dt = ctx.params.parse_start_datetime()
    end_dt = ctx.params.parse_end_datetime()
    reverse = sort_order == SortOrderType.DESC

    if table_type == TableType.ATTENDEES:
        return await metrics_service.get_attendees_table(ctx, start_dt, end_dt, sort_by, reverse)
    if table_type == TableType.ORGANIZERS:
        return await metrics_service.get_organizers_table(ctx, start_dt, end_dt, sort_by, reverse)
    if table_type == TableType.TEAMS_COLLAB:
        return await metrics_service.get_teams_collab_table(ctx, start_dt, end_dt, sort_by, reverse)

    return await recurring_service.build_recurring_table(
        ctx, start_dt, end_dt, sort_by.value if sort_by else "total_time", reverse
    )
