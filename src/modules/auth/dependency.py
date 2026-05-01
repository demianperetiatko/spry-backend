from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Path, Request, status

from src.core.exceptions import NotFoundException
from src.modules.enums import OrganizationMemberRoleEnum
from src.modules.organization.model import Organization
from src.modules.organization.repository import (
    OrganizationCurrencyRepository,
    OrganizationRepository,
    get_organization_currency_repository,
    get_organization_repository,
)
from src.modules.organization_member.model import OrganizationMember
from src.modules.organization_member.repository import (
    OrganizationMemberRepository,
    get_organization_member_repository,
)
from src.modules.permissions.enums import OrganizationPermission
from src.modules.permissions.service import Permissions, get_permissions
from src.modules.super_admin.service import SuperAdminService, get_super_admin_service
from src.modules.user.model import User
from src.modules.user.repository import UserRepository, get_user_repository

UserRepoDep = Annotated[UserRepository, Depends(get_user_repository)]
OrgRepoDep = Annotated[OrganizationRepository, Depends(get_organization_repository)]
MemberRepoDep = Annotated[OrganizationMemberRepository, Depends(get_organization_member_repository)]
CurrencyRepoDep = Annotated[OrganizationCurrencyRepository, Depends(get_organization_currency_repository)]
PermissionsServiceDep = Annotated[type[Permissions], Depends(get_permissions)]


async def get_auth_user(
    request: Request,
    user_repo: UserRepoDep,
) -> User:
    user_id_str = request.session.get("user_id")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format",
        )

    try:
        user = await user_repo.find_by_id(user_id)
    except NotFoundException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


@dataclass(frozen=True)
class OrganizationContext:
    user: User
    organization: Organization
    member: OrganizationMember


async def get_organization_context(
    organization_id: Annotated[uuid.UUID, Path(...)],
    org_repo: OrgRepoDep,
    member_repo: MemberRepoDep,
    super_admin_service: Annotated[SuperAdminService, Depends(get_super_admin_service)],
    user: User = Depends(get_auth_user),
) -> OrganizationContext:
    org = await org_repo.get_by_id(organization_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    member = await member_repo.get_by_user_id_and_organization_id(user.id, organization_id)
    if member:
        return OrganizationContext(user=user, organization=org, member=member)

    if not await super_admin_service.is_super_admin(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of this organization",
        )

    all_members, _ = await member_repo.get_members_by_organization_id(organization_id)
    admin_members = [m for m in all_members if m.role == OrganizationMemberRoleEnum.ADMIN]
    proxy_member = admin_members[0] if admin_members else (all_members[0] if all_members else None)
    if not proxy_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No members found in organization",
        )

    return OrganizationContext(user=user, organization=org, member=proxy_member)


class PermissionChecker:
    def __init__(self, required_permission: OrganizationPermission):
        self.required_permission = required_permission

    async def __call__(
        self,
        org_ctx: Annotated[OrganizationContext, Depends(get_organization_context)],
        currency_repo: CurrencyRepoDep,
        member_repo: MemberRepoDep,
        permissions_service: PermissionsServiceDep,
    ) -> OrganizationContext:
        currency = await currency_repo.find_by_id(org_ctx.organization.organizations_currency_id)

        has_permission = await permissions_service.member_has_permission(
            member=org_ctx.member,
            permission=self.required_permission,
            currency=currency,
            member_repo=member_repo,
        )

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )

        return org_ctx


def require_permission(permission: OrganizationPermission) -> Depends:
    return Depends(PermissionChecker(permission))
