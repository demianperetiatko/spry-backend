from __future__ import annotations

import dataclasses
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.session import get_session
from src.modules.analytics.personal.dependency import AnalyticsContext, get_personal_analytics_context
from src.modules.analytics.personal.repository import (
    PersonalAnalyticsRepository,
    get_personal_analytics_repository,
)
from src.modules.analytics.personal.schemas import PersonalAnalyticsParams
from src.modules.analytics.personal.services.data_loader import AnalyticsDataLoaderService
from src.modules.auth.dependency import OrganizationContext, PermissionChecker
from src.modules.insights.models import InsightSettings
from src.modules.insights.schemas import (
    DEFAULT_SETTINGS,
    FREQUENCY_LABELS,
    HORIZON_LABELS,
    DataHorizon,
    GenerationFrequency,
    InsightSettingsResponse,
    InsightTabSettings,
    InsightsResponse,
    UpdateInsightTabSettings,
)
from src.modules.insights.service import InsightsService, OrgInsightsService, TeamInsightsService
from src.modules.organization.model import Organization
from src.modules.organization_member.model import OrganizationMember
from src.modules.organization_team.model import OrganizationTeam
from src.modules.permissions.enums import OrganizationPermission
from src.modules.user.model import User

personal_router = APIRouter(
    prefix="/organizations/{organization_id}/members/{user_id}/insights",
    tags=["insights"],
)
settings_router = APIRouter(
    prefix="/organizations/{organization_id}/insights/settings",
    tags=["insights"],
)
team_insights_router = APIRouter(
    prefix="/organizations/{organization_id}/teams/{team_id}/insights",
    tags=["insights"],
)
org_insights_router = APIRouter(
    prefix="/organizations/{organization_id}/insights",
    tags=["insights"],
)

AnalyticsContextDep = Annotated[AnalyticsContext, Depends(get_personal_analytics_context)]


async def get_insights_service(
    analytics_repo: PersonalAnalyticsRepository = Depends(get_personal_analytics_repository),
) -> InsightsService:
    return InsightsService(data_loader=AnalyticsDataLoaderService(analytics_repo), repo=analytics_repo)


InsightsServiceDep = Annotated[InsightsService, Depends(get_insights_service)]


def _resolve_date_range(horizon: DataHorizon) -> tuple[datetime, datetime, datetime, datetime]:
    """Повертає (start, end, prev_start, prev_end) на основі DataHorizon.

    prev_* — попередній період такої ж тривалості, для розрахунку трендів.
    """
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    def _add_months(d: datetime, months: int) -> datetime:
        month_index = d.month - 1 + months
        year = d.year + month_index // 12
        month = month_index % 12 + 1
        return d.replace(year=year, month=month, day=1)

    if horizon == DataHorizon.current_month:
        start = today.replace(day=1)
        next_month = _add_months(start, 1)
        end = next_month - timedelta(seconds=1)
        prev_end = start - timedelta(seconds=1)
        prev_start = prev_end.replace(day=1)
    elif horizon == DataHorizon.current_week:
        start = today - timedelta(days=today.weekday())  # понеділок
        end = start + timedelta(days=7) - timedelta(seconds=1)
        prev_start = start - timedelta(weeks=1)
        prev_end = start
    elif horizon == DataHorizon.last_and_next_2_weeks:
        start = today - timedelta(weeks=2)
        end = today + timedelta(weeks=2)
        prev_start = start - timedelta(weeks=4)
        prev_end = start
    elif horizon == DataHorizon.last_3m:
        start = _add_months(today, -3)
        end = now
        prev_start = _add_months(start, -3)
        prev_end = start
    elif horizon == DataHorizon.last_6m:
        start = _add_months(today, -6)
        end = now
        prev_start = _add_months(start, -6)
        prev_end = start
    elif horizon == DataHorizon.next_3m:
        start = today
        end = _add_months(today, 3)
        prev_start = _add_months(today, -3)
        prev_end = start
    elif horizon == DataHorizon.next_6m:
        start = today
        end = _add_months(today, 6)
        prev_start = _add_months(today, -6)
        prev_end = start
    else:  # last_and_next_4_weeks (default)
        start = today - timedelta(weeks=4)
        end = today + timedelta(weeks=4)
        prev_start = start - timedelta(weeks=8)
        prev_end = start

    return start, end, prev_start, prev_end


def _parse_freq(value: str, tab: str) -> GenerationFrequency:
    """Безпечний парсинг: старі/видалені значення → дефолт вкладки."""
    try:
        return GenerationFrequency(value)
    except ValueError:
        return DEFAULT_SETTINGS[tab][0]


def _parse_horizon(value: str, tab: str) -> DataHorizon:
    try:
        return DataHorizon(value)
    except ValueError:
        return DEFAULT_SETTINGS[tab][1]


async def _get_org_settings(org_id: uuid.UUID, tab: str, session: AsyncSession) -> tuple[GenerationFrequency, DataHorizon]:
    stmt = select(InsightSettings).where(
        InsightSettings.organization_id == org_id,
        InsightSettings.tab == tab,
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row:
        return _parse_freq(row.generation_frequency, tab), _parse_horizon(row.data_horizon, tab)
    freq, horizon = DEFAULT_SETTINGS[tab]
    return freq, horizon


async def _get_member_name(member_id: uuid.UUID, session: AsyncSession) -> str:
    stmt = (
        select(User.name)
        .join(OrganizationMember, OrganizationMember.user_id == User.id)
        .where(OrganizationMember.id == member_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() or ""


# ── Personal insights ─────────────────────────────────────────────────────────

@personal_router.get("/", response_model=InsightsResponse)
async def get_insights(
    organization_id: uuid.UUID,
    ctx: AnalyticsContextDep,
    service: InsightsServiceDep,
    session: AsyncSession = Depends(get_session),
) -> InsightsResponse:
    # Date range comes from org settings, not query params
    _, horizon = await _get_org_settings(organization_id, "personal", session)
    start, end, _prev_start, _prev_end = _resolve_date_range(horizon)
    settings_params = PersonalAnalyticsParams(
        start_date=start.strftime("%Y-%m-%d"),
        end_date=end.strftime("%Y-%m-%d"),
    )
    ctx_with_settings = dataclasses.replace(ctx, params=settings_params)

    is_self = ctx.auth_member.id == ctx.member.id
    member_name = "" if is_self else await _get_member_name(ctx.member.id, session)
    insights = await service.generate_personal_insights(ctx_with_settings, is_self=is_self, member_name=member_name)
    return InsightsResponse(data=insights)


# ── Teams insights ────────────────────────────────────────────────────────────

@team_insights_router.get(
    "/",
    response_model=InsightsResponse,
    dependencies=[Depends(PermissionChecker(OrganizationPermission.ANALYTICS_MEMBERS_VIEW))],
)
async def get_team_insights(
    organization_id: uuid.UUID,
    team_id: uuid.UUID,
    org_ctx: Annotated[OrganizationContext, Depends(PermissionChecker(OrganizationPermission.ANALYTICS_MEMBERS_VIEW))],
    analytics_repo: PersonalAnalyticsRepository = Depends(get_personal_analytics_repository),
    session: AsyncSession = Depends(get_session),
) -> InsightsResponse:
    # Перевірити що команда належить org
    team_stmt = select(OrganizationTeam).where(
        OrganizationTeam.id == team_id,
        OrganizationTeam.organization_id == organization_id,
    )
    team_result = await session.execute(team_stmt)
    team = team_result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    _, horizon = await _get_org_settings(organization_id, "teams", session)
    start, end, prev_start, prev_end = _resolve_date_range(horizon)

    svc = TeamInsightsService(repo=analytics_repo, data_loader=AnalyticsDataLoaderService(analytics_repo))
    insights = await svc.generate(
        team_id=team_id,
        org=org_ctx.organization,
        auth_member=org_ctx.member,
        start=start,
        end=end,
        prev_start=prev_start,
        prev_end=prev_end,
        workday_hours=Decimal("8"),
    )
    return InsightsResponse(data=insights)


# ── Organization insights ─────────────────────────────────────────────────────

@org_insights_router.get(
    "/",
    response_model=InsightsResponse,
    dependencies=[Depends(PermissionChecker(OrganizationPermission.ANALYTICS_MEMBERS_VIEW))],
)
async def get_org_insights(
    organization_id: uuid.UUID,
    org_ctx: Annotated[OrganizationContext, Depends(PermissionChecker(OrganizationPermission.ANALYTICS_MEMBERS_VIEW))],
    analytics_repo: PersonalAnalyticsRepository = Depends(get_personal_analytics_repository),
    session: AsyncSession = Depends(get_session),
) -> InsightsResponse:
    _, horizon = await _get_org_settings(organization_id, "organization", session)
    start, end, prev_start, prev_end = _resolve_date_range(horizon)

    svc = OrgInsightsService(repo=analytics_repo, data_loader=AnalyticsDataLoaderService(analytics_repo))
    insights = await svc.generate(
        org=org_ctx.organization,
        start=start,
        end=end,
        prev_start=prev_start,
        prev_end=prev_end,
        workday_hours=Decimal("8"),
    )
    return InsightsResponse(data=insights)


# ── Insights settings ─────────────────────────────────────────────────────────

async def _load_settings(organization_id: uuid.UUID, session: AsyncSession) -> list[InsightTabSettings]:
    stmt = select(InsightSettings).where(InsightSettings.organization_id == organization_id)
    result = await session.execute(stmt)
    rows = {row.tab: row for row in result.scalars().all()}

    tabs = ["personal", "teams", "organization"]
    out: list[InsightTabSettings] = []
    for tab in tabs:
        if tab in rows:
            freq = _parse_freq(rows[tab].generation_frequency, tab)
            horizon = _parse_horizon(rows[tab].data_horizon, tab)
        else:
            freq, horizon = DEFAULT_SETTINGS[tab]
        out.append(InsightTabSettings(
            tab=tab,
            generation_frequency=freq,
            data_horizon=horizon,
            frequency_label=FREQUENCY_LABELS[freq],
            horizon_label=HORIZON_LABELS[horizon],
        ))
    return out


@settings_router.get(
    "/",
    response_model=InsightSettingsResponse,
    dependencies=[Depends(PermissionChecker(OrganizationPermission.ANALYTICS_MEMBERS_VIEW))],
)
async def get_insight_settings(
    organization_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> InsightSettingsResponse:
    return InsightSettingsResponse(data=await _load_settings(organization_id, session))


@settings_router.patch(
    "/{tab}",
    response_model=InsightSettingsResponse,
    dependencies=[Depends(PermissionChecker(OrganizationPermission.ANALYTICS_MEMBERS_VIEW))],
)
async def update_insight_settings(
    organization_id: uuid.UUID,
    tab: str,
    body: UpdateInsightTabSettings,
    session: AsyncSession = Depends(get_session),
) -> InsightSettingsResponse:
    current = await _load_settings(organization_id, session)
    current_tab = next((s for s in current if s.tab == tab), None)
    if current_tab is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tab not found")

    freq = body.generation_frequency or current_tab.generation_frequency
    horizon = body.data_horizon or current_tab.data_horizon

    stmt = (
        insert(InsightSettings)
        .values(
            id=uuid.uuid4(),
            organization_id=organization_id,
            tab=tab,
            generation_frequency=freq.value,
            data_horizon=horizon.value,
        )
        .on_conflict_do_update(
            constraint="uq_insight_settings_org_tab",
            set_={"generation_frequency": freq.value, "data_horizon": horizon.value},
        )
    )
    await session.execute(stmt)
    await session.commit()

    return InsightSettingsResponse(data=await _load_settings(organization_id, session))
