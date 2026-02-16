from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated

from fastapi import Depends, HTTPException, Path, Query, status

from src.modules.analytics.organization.repository import (
    OrganizationAnalyticsRepository,
    get_organization_analytics_repository,
)
from src.modules.analytics.organization.schemas import OrganizationAnalyticsParams
from src.modules.analytics.common.schemas import AnalyticsDateRangeParams
from src.modules.auth.dependency import OrganizationContext, PermissionChecker
from src.modules.organization.model import Organization
from src.modules.organization_team.model import OrganizationTeam
from src.modules.organization_team.repository import (
    OrganizationTeamRepository,
    get_organization_team_repository,
)
from src.modules.organization_member.model import OrganizationMember
from src.modules.organization_member.repository import (
    OrganizationMemberRepository,
    get_organization_member_repository,
)
from src.modules.permissions.enums import OrganizationPermission

MemberRepoDep = Annotated[OrganizationMemberRepository, Depends(get_organization_member_repository)]
TeamRepoDep = Annotated[OrganizationTeamRepository, Depends(get_organization_team_repository)]
AnalyticsRepoDep = Annotated[OrganizationAnalyticsRepository, Depends(get_organization_analytics_repository)]


@dataclass(frozen=True)
class OrganizationAnalyticsContext:
    org: Organization
    auth_member: OrganizationMember
    team: OrganizationTeam | None
    members: list[OrganizationMember]
    params: OrganizationAnalyticsParams
    workday_hours: Decimal


async def get_organization_analytics_context(
    organization_id: Annotated[uuid.UUID, Path(...)],
    params: Annotated[AnalyticsDateRangeParams, Depends()],
    org_ctx: Annotated[
        OrganizationContext,
        Depends(PermissionChecker(OrganizationPermission.ANALYTICS_ORGANIZATION_VIEW)),
    ],
    member_repo: MemberRepoDep,
    team_repo: TeamRepoDep,
    analytics_repo: AnalyticsRepoDep,
    team_id: uuid.UUID | None = Query(None, description="Filter by team ID"),
) -> OrganizationAnalyticsContext:
    # Ensure organization matches context
    if org_ctx.organization.id != organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this organization")

    team: OrganizationTeam | None = None
    members: list[OrganizationMember]

    if team_id:
        team = await team_repo.get_by_id_and_organization_id(team_id, organization_id)
        if not team:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
        members = [tm.member for tm in team.team_members if tm.member]
    else:
        members, _ = await member_repo.get_members_by_organization_id(organization_id)

    if not members:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No members found for analytics")

    # Filter out members without calendars to avoid unnecessary queries
    members_with_calendars = await analytics_repo.filter_members_with_calendars([m.id for m in members])
    members = [m for m in members if m.id in members_with_calendars]
    if not members:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No calendars found for selected members",
        )

    analytics_params = OrganizationAnalyticsParams(
        start_date=params.start_date,
        end_date=params.end_date,
        team_id=team.id if team else None,
    )

    return OrganizationAnalyticsContext(
        org=org_ctx.organization,
        auth_member=org_ctx.member,
        team=team,
        members=members,
        params=analytics_params,
        workday_hours=Decimal("8"),
    )
