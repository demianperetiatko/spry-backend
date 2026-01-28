from __future__ import annotations

import uuid
from abc import ABC

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.repository import CRUDRepository, CRUDRepositorySQLAlchemy
from src.core.database.session import get_session
from src.modules.organization.model import Organization, OrganizationCurrency


class OrganizationCurrencyRepository(CRUDRepository[OrganizationCurrency, uuid.UUID], ABC): ...


class OrganizationCurrencyRepositorySQLAlchemy(
    OrganizationCurrencyRepository,
    CRUDRepositorySQLAlchemy[OrganizationCurrency, uuid.UUID],
):
    def get_entity_class(self) -> type[OrganizationCurrency]:
        return OrganizationCurrency


class OrganizationRepository(CRUDRepository[Organization, uuid.UUID], ABC):
    async def get_by_name(self, name: str) -> Organization | None:
        raise NotImplementedError


class OrganizationRepositorySQLAlchemy(
    OrganizationRepository,
    CRUDRepositorySQLAlchemy[Organization, uuid.UUID],
):
    def get_entity_class(self) -> type[Organization]:
        return Organization

    async def get_by_name(self, name: str) -> Organization | None:
        return await self.db.scalar(select(Organization).where(Organization.name == name).limit(1))


async def get_organization_repository(session: AsyncSession = Depends(get_session)) -> OrganizationRepository:
    return OrganizationRepositorySQLAlchemy(session)


async def get_organization_currency_repository(session: AsyncSession = Depends(get_session)) -> OrganizationCurrencyRepository:
    return OrganizationCurrencyRepositorySQLAlchemy(session)
