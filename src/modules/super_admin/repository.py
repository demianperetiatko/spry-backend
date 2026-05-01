from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.repository import CRUDRepository, CRUDRepositorySQLAlchemy
from src.core.database.session import get_session
from src.modules.organization.model import Organization
from src.modules.super_admin.model import SuperAdmin


class SuperAdminRepository(CRUDRepository[SuperAdmin, uuid.UUID], ABC):
    @abstractmethod
    async def get_by_user_id(self, user_id: uuid.UUID) -> SuperAdmin | None:
        raise NotImplementedError()

    @abstractmethod
    async def get_all_organizations(self) -> list[Organization]:
        raise NotImplementedError()


class SuperAdminRepositorySQLAlchemy(
    SuperAdminRepository,
    CRUDRepositorySQLAlchemy[SuperAdmin, uuid.UUID],
):
    def get_entity_class(self) -> type[SuperAdmin]:
        return SuperAdmin

    async def get_by_user_id(self, user_id: uuid.UUID) -> SuperAdmin | None:
        stmt = select(SuperAdmin).where(SuperAdmin.user_id == user_id).limit(1)
        return await self._scalar(stmt)

    async def get_all_organizations(self) -> list[Organization]:
        stmt = select(Organization).distinct(Organization.id).execution_options(populate_existing=True)
        result = await self._execute(stmt)
        seen: set[uuid.UUID] = set()
        organizations = []
        for org in result.unique().scalars().all():
            if org.id not in seen:
                seen.add(org.id)
                organizations.append(org)
        return organizations


async def get_super_admin_repository(session: AsyncSession = Depends(get_session)) -> SuperAdminRepository:
    return SuperAdminRepositorySQLAlchemy(session)
