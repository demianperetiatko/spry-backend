from __future__ import annotations

import uuid

from fastapi import Depends

from src.modules.enums import OrganizationMemberRoleEnum, OrganizationMemberStatusEnum
from src.modules.permissions.enums import OrganizationPermission
from src.modules.super_admin.repository import SuperAdminRepository, get_super_admin_repository
from src.modules.user.schemas import OrganizationMemberInfo

_ALL_PERMISSIONS = [p.value for p in OrganizationPermission]


class SuperAdminService:
    def __init__(self, super_admin_repo: SuperAdminRepository) -> None:
        self.super_admin_repo = super_admin_repo

    async def is_super_admin(self, user_id: uuid.UUID) -> bool:
        return await self.super_admin_repo.get_by_user_id(user_id) is not None

    async def get_all_organizations(self) -> list[OrganizationMemberInfo]:
        organizations = await self.super_admin_repo.get_all_organizations()
        return [
            OrganizationMemberInfo(
                organization_id=org.id,
                organization_name=org.name,
                role=OrganizationMemberRoleEnum.ADMIN,
                status=OrganizationMemberStatusEnum.ACTIVE,
                permissions=_ALL_PERMISSIONS,
            )
            for org in organizations
        ]


async def get_super_admin_service(
    super_admin_repo: SuperAdminRepository = Depends(get_super_admin_repository),
) -> SuperAdminService:
    return SuperAdminService(super_admin_repo=super_admin_repo)
