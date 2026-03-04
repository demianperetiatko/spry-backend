from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated

from fastapi import Depends, HTTPException, Path, status

from src.modules.analytics.personal.repository import (
    PersonalAnalyticsRepository,
    get_personal_analytics_repository,
)
from src.modules.analytics.personal.schemas import AnalyticsDateRangeParams, PersonalAnalyticsParams
from src.modules.auth.dependency import OrganizationContext, PermissionChecker
from src.modules.organization.model import Organization
from src.modules.organization_member.model import OrganizationMember
from src.modules.organization_member.repository import (
    OrganizationMemberRepository,
    get_organization_member_repository,
)
from src.modules.permissions.enums import OrganizationPermission

MemberRepoDep = Annotated[OrganizationMemberRepository, Depends(get_organization_member_repository)]


@dataclass(frozen=True)
class AnalyticsContext:
    member: OrganizationMember
    email: str
    calendar_ids: list[uuid.UUID]
    params: PersonalAnalyticsParams
    auth_member: OrganizationMember
    org: Organization
    workday_hours: Decimal


async def get_personal_analytics_context(
    user_id: Annotated[uuid.UUID, Path(...)],
    params: Annotated[AnalyticsDateRangeParams, Depends()],
    org_ctx: Annotated[OrganizationContext, Depends(PermissionChecker(OrganizationPermission.ANALYTICS_MEMBERS_VIEW))],
    member_repo: MemberRepoDep,
    analytics_repo: Annotated[PersonalAnalyticsRepository, Depends(get_personal_analytics_repository)],
) -> AnalyticsContext:
    member = await member_repo.get_by_user_id_and_organization_id(user_id, org_ctx.organization.id)
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    if member.organization_id != org_ctx.member.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this organization",
        )

    email = await member_repo.get_user_email_by_member_id(member.id)
    if not email:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User email not found")

    calendar_ids = list(await analytics_repo.get_calendar_ids_for_member(member.id))
    if not calendar_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No calendars found for this member",
        )

    analytics_params = PersonalAnalyticsParams(
        start_date=params.start_date,
        end_date=params.end_date,
    )

    return AnalyticsContext(
        member=member,
        email=email,
        calendar_ids=calendar_ids,
        params=analytics_params,
        auth_member=org_ctx.member,
        org=org_ctx.organization,
        workday_hours=Decimal("8"),
    )
