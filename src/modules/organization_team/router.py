from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.modules.analytics.common.schemas import SortOrderType
from src.modules.auth.dependency import OrganizationContext, require_permission
from src.modules.organization_team.schemas import (
    CreateTeamRequest,
    TeamResponse,
    TeamSortByEnum,
    TeamsListResponse,
    UpdateTeamRequest,
)
from src.modules.organization_team.service import (
    OrganizationTeamService,
    get_organization_team_service,
)
from src.modules.permissions.enums import OrganizationPermission

router = APIRouter(prefix="/organizations/{organization_id}/teams", tags=["organization-teams"])


@router.get("", response_model=TeamsListResponse)
async def get_teams(
    ctx: Annotated[OrganizationContext, require_permission(OrganizationPermission.TEAMS_VIEW)],
    service: OrganizationTeamService = Depends(get_organization_team_service),
    sort_by: TeamSortByEnum = Query(TeamSortByEnum.NAME, description="Field to sort by"),
    sort_order: SortOrderType = Query(SortOrderType.ASC, description="Sort order"),
) -> TeamsListResponse:
    return await service.get_teams(
        organization_id=ctx.organization.id,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team_by_id(
    ctx: Annotated[OrganizationContext, require_permission(OrganizationPermission.TEAMS_VIEW)],
    team_id: uuid.UUID,
    service: OrganizationTeamService = Depends(get_organization_team_service),
) -> TeamResponse:
    return await service.get_team_by_id(
        team_id=team_id,
        organization_id=ctx.organization.id,
    )


@router.post("", response_model=TeamResponse, status_code=201)
async def create_team(
    ctx: Annotated[OrganizationContext, require_permission(OrganizationPermission.TEAMS_CREATE)],
    payload: CreateTeamRequest,
    service: OrganizationTeamService = Depends(get_organization_team_service),
) -> TeamResponse:
    return await service.create_team(
        organization_id=ctx.organization.id,
        payload=payload,
    )


@router.put("/{team_id}", response_model=TeamResponse)
async def update_team(
    ctx: Annotated[OrganizationContext, require_permission(OrganizationPermission.TEAMS_EDIT)],
    team_id: uuid.UUID,
    payload: UpdateTeamRequest,
    service: OrganizationTeamService = Depends(get_organization_team_service),
) -> TeamResponse:
    return await service.update_team(
        team_id=team_id,
        organization_id=ctx.organization.id,
        payload=payload,
        auth_member=ctx.member,
    )


@router.delete("/{team_id}", status_code=204)
async def delete_team(
    ctx: Annotated[OrganizationContext, require_permission(OrganizationPermission.TEAMS_DELETE)],
    team_id: uuid.UUID,
    service: OrganizationTeamService = Depends(get_organization_team_service),
) -> None:
    await service.delete_team(
        team_id=team_id,
        organization_id=ctx.organization.id,
        auth_member=ctx.member,
    )
