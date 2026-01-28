from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.modules.auth.dependency import OrganizationContext, require_permission
from src.modules.organization.repository import (
    OrganizationCurrencyRepository,
    get_organization_currency_repository,
)
from src.modules.organization_member.schemas import (
    AddMembersRequest,
    MemberResponse,
    PaginatedMembersResponse,
    UpdateMemberRequest,
)
from src.modules.organization_member.service import (
    OrganizationMemberService,
    get_organization_member_service,
)
from src.modules.permissions.enums import OrganizationPermission

router = APIRouter(prefix="/organizations/{organization_id}/members", tags=["organization-members"])


@router.get("", response_model=PaginatedMembersResponse)
async def get_organization_members(
    ctx: Annotated[OrganizationContext, require_permission(OrganizationPermission.MEMBERS_VIEW)],
    service: OrganizationMemberService = Depends(get_organization_member_service),
    currency_repo: OrganizationCurrencyRepository = Depends(get_organization_currency_repository),
    search_query: str | None = Query(None, description="Search by member name or email"),
    limit: int = Query(20, ge=1, le=100, description="Number of items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> PaginatedMembersResponse:
    currency = await currency_repo.find_by_id(ctx.organization.organizations_currency_id)
    return await service.get_organization_members(
        organization_id=ctx.organization.id,
        auth_member=ctx.member,
        currency=currency,
        search_query=search_query,
        limit=limit,
        offset=offset,
    )


@router.post("", status_code=201)
async def add_members_to_organization(
    ctx: Annotated[OrganizationContext, require_permission(OrganizationPermission.MEMBERS_CREATE)],
    request: AddMembersRequest,
    service: OrganizationMemberService = Depends(get_organization_member_service),
) -> dict[str, str]:
    await service.add_members_to_organization(
        organization_id=ctx.organization.id,
        emails=[str(email) for email in request.emails],
        auth_member=ctx.member,
        organization_name=ctx.organization.name,
    )
    return {"status": "ok"}


@router.put("/{user_id}", response_model=MemberResponse)
async def update_member(
    ctx: Annotated[OrganizationContext, require_permission(OrganizationPermission.MEMBERS_EDIT)],
    user_id: uuid.UUID,
    update_data: UpdateMemberRequest,
    service: OrganizationMemberService = Depends(get_organization_member_service),
    currency_repo: OrganizationCurrencyRepository = Depends(get_organization_currency_repository),
) -> MemberResponse:
    currency = await currency_repo.find_by_id(ctx.organization.organizations_currency_id)
    return await service.update_member(
        user_id=user_id,
        organization_id=ctx.organization.id,
        update_data=update_data,
        auth_member=ctx.member,
        currency=currency,
    )


@router.delete("/{user_id}", status_code=204)
async def delete_member(
    ctx: Annotated[OrganizationContext, require_permission(OrganizationPermission.MEMBERS_DELETE)],
    user_id: uuid.UUID,
    service: OrganizationMemberService = Depends(get_organization_member_service),
) -> None:
    await service.delete_member(
        user_id=user_id,
        organization_id=ctx.organization.id,
    )


@router.post("/{user_id}/resend-invitation", status_code=200)
async def resend_invitation(
    ctx: Annotated[OrganizationContext, require_permission(OrganizationPermission.MEMBERS_CREATE)],
    user_id: uuid.UUID,
    service: OrganizationMemberService = Depends(get_organization_member_service),
) -> dict[str, str]:
    await service.resend_invitation(
        user_id=user_id,
        organization_id=ctx.organization.id,
        auth_member=ctx.member,
        organization_name=ctx.organization.name or "",
    )
    return {"status": "ok"}
