from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from src.modules.enums import OrganizationCostVisibilityEnum, OrganizationMemberRoleEnum
from src.modules.organization.model import OrganizationCurrency
from src.modules.organization.repository import (
    OrganizationCurrencyRepository,
    get_organization_currency_repository,
)
from src.modules.organization_member.model import OrganizationMember
from src.modules.organization_member.repository import (
    OrganizationMemberRepository,
    get_organization_member_repository,
)
from src.modules.permissions.enums import OrganizationPermission

MemberRepoDep = Annotated[OrganizationMemberRepository, Depends(get_organization_member_repository)]
CurrencyRepoDep = Annotated[OrganizationCurrencyRepository, Depends(get_organization_currency_repository)]


class Permissions:
    @classmethod
    async def get_member_permissions(
        cls,
        member: OrganizationMember,
        currency: OrganizationCurrency,
        member_repo: MemberRepoDep,
    ) -> list[str]:
        permissions = set()

        is_manager = await member_repo.is_manager_of_organization(member)

        if member.role == OrganizationMemberRoleEnum.ADMIN:
            permissions.update(
                {
                    OrganizationPermission.MEMBERS_VIEW,
                    OrganizationPermission.MEMBERS_CREATE,
                    OrganizationPermission.MEMBERS_EDIT,
                    OrganizationPermission.MEMBERS_DELETE,
                },
            )
        elif is_manager:
            permissions.update(
                {
                    OrganizationPermission.MEMBERS_VIEW,
                    OrganizationPermission.MEMBERS_EDIT,
                },
            )
        else:
            permissions.add(OrganizationPermission.MEMBERS_VIEW)

        if member.role == OrganizationMemberRoleEnum.ADMIN:
            permissions.update(
                {
                    OrganizationPermission.TEAMS_VIEW,
                    OrganizationPermission.TEAMS_CREATE,
                    OrganizationPermission.TEAMS_EDIT,
                    OrganizationPermission.TEAMS_DELETE,
                },
            )
        elif is_manager:
            permissions.update(
                {
                    OrganizationPermission.TEAMS_VIEW,
                    OrganizationPermission.TEAMS_EDIT,
                },
            )
        else:
            permissions.add(OrganizationPermission.TEAMS_VIEW)

        if member.role == OrganizationMemberRoleEnum.ADMIN:
            permissions.add(OrganizationPermission.MEETINGS_COSTS_VIEW)

        permissions.update(
            {
                OrganizationPermission.ANALYTICS_ORGANIZATION_VIEW,
                OrganizationPermission.ANALYTICS_MEMBERS_VIEW,
            },
        )

        if member.role == OrganizationMemberRoleEnum.ADMIN:
            permissions.add(OrganizationPermission.FINANCE_VIEW)
        elif currency.cost_is_active:
            if currency.cost_visibility == OrganizationCostVisibilityEnum.MANAGER and is_manager:
                permissions.add(OrganizationPermission.FINANCE_VIEW)
            elif currency.cost_visibility == OrganizationCostVisibilityEnum.ALL:
                permissions.add(OrganizationPermission.FINANCE_VIEW)

        return list(permissions)

    @classmethod
    async def member_has_permission(
        cls,
        member: OrganizationMember,
        permission: OrganizationPermission,
        currency: OrganizationCurrency,
        member_repo: MemberRepoDep,
    ) -> bool:
        current_permissions = await cls.get_member_permissions(member, currency, member_repo)
        return permission in current_permissions


def get_permissions() -> type[Permissions]:
    return Permissions
