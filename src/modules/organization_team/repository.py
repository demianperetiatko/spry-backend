from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Type

from fastapi import Depends
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from src.core.database.repository import CRUDRepository, CRUDRepositorySQLAlchemy
from src.core.database.session import get_session
from src.modules.enums import OrganizationTeamMemberTypeEnum
from src.modules.organization_member.model import OrganizationMember
from src.modules.organization_team.model import OrganizationTeam, OrganizationTeamMember


class OrganizationTeamRepository(CRUDRepository[OrganizationTeam, uuid.UUID], ABC):
    @abstractmethod
    async def get_teams_by_organization_id(self, organization_id: uuid.UUID) -> list[OrganizationTeam]:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_id_and_organization_id(self, team_id: uuid.UUID, organization_id: uuid.UUID) -> OrganizationTeam | None:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_organization_id_and_name(self, organization_id: uuid.UUID, name: str) -> OrganizationTeam | None:
        raise NotImplementedError()


class OrganizationTeamRepositorySQLAlchemy(
    OrganizationTeamRepository,
    CRUDRepositorySQLAlchemy[OrganizationTeam, uuid.UUID],
):
    def get_entity_class(self) -> Type[OrganizationTeam]:
        return OrganizationTeam

    async def get_teams_by_organization_id(self, organization_id: uuid.UUID) -> list[OrganizationTeam]:
        query = (
            select(OrganizationTeam)
            .options(
                selectinload(OrganizationTeam.team_members)
                .selectinload(OrganizationTeamMember.member)
                .selectinload(OrganizationMember.user)
            )
            .where(OrganizationTeam.organization_id == organization_id)
            .order_by(OrganizationTeam.name)
        )
        result = await self._execute(query)
        return list(result.unique().scalars().all())

    async def get_by_id_and_organization_id(self, team_id: uuid.UUID, organization_id: uuid.UUID) -> OrganizationTeam | None:
        statement = (
            select(OrganizationTeam)
            .options(
                selectinload(OrganizationTeam.team_members)
                .selectinload(OrganizationTeamMember.member)
                .selectinload(OrganizationMember.user)
            )
            .where(
                OrganizationTeam.id == team_id,
                OrganizationTeam.organization_id == organization_id,
            )
            .limit(1)
        )
        return await self._scalar(statement)

    async def get_by_organization_id_and_name(self, organization_id: uuid.UUID, name: str) -> OrganizationTeam | None:
        statement = (
            select(OrganizationTeam)
            .where(
                OrganizationTeam.organization_id == organization_id,
                OrganizationTeam.name == name,
            )
            .limit(1)
        )
        return await self._scalar(statement)


class OrganizationTeamMemberRepository(CRUDRepository[OrganizationTeamMember, uuid.UUID], ABC):
    @abstractmethod
    async def get_by_team_id(self, team_id: uuid.UUID) -> list[OrganizationTeamMember]:
        raise NotImplementedError()

    @abstractmethod
    async def delete_by_team_id(self, team_id: uuid.UUID) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def is_manager(self, team_id: uuid.UUID, organization_member_id: uuid.UUID) -> bool:
        raise NotImplementedError()

    @abstractmethod
    async def get_manager_by_team_id(self, team_id: uuid.UUID) -> OrganizationTeamMember | None:
        raise NotImplementedError()

    @abstractmethod
    async def get_managers_by_team_ids(self, team_ids: list[uuid.UUID]) -> dict[uuid.UUID, uuid.UUID]:
        raise NotImplementedError()

    @abstractmethod
    async def delete_by_member_id(self, member_id: uuid.UUID) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def find_manager_id(self, team_id: uuid.UUID) -> uuid.UUID | None:
        raise NotImplementedError()

    @abstractmethod
    async def bulk_create(self, team_members: list[OrganizationTeamMember]) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_member_id(self, member_id: uuid.UUID) -> list[OrganizationTeamMember]:
        raise NotImplementedError()

    @abstractmethod
    async def update_member_type(
        self,
        team_id: uuid.UUID,
        member_id: uuid.UUID,
        member_type: OrganizationTeamMemberTypeEnum,
    ) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def delete_by_member_and_team_ids(self, member_id: uuid.UUID, team_ids: list[uuid.UUID]) -> None:
        raise NotImplementedError()


class OrganizationTeamMemberRepositorySQLAlchemy(
    OrganizationTeamMemberRepository,
    CRUDRepositorySQLAlchemy[OrganizationTeamMember, uuid.UUID],
):
    def get_entity_class(self) -> Type[OrganizationTeamMember]:
        return OrganizationTeamMember

    async def get_by_team_id(self, team_id: uuid.UUID) -> list[OrganizationTeamMember]:
        statement = (
            select(OrganizationTeamMember)
            .options(
                selectinload(OrganizationTeamMember.member).selectinload(OrganizationMember.user),
                joinedload(OrganizationTeamMember.team),
            )
            .where(OrganizationTeamMember.team_id == team_id)
            .order_by(OrganizationTeamMember.id)
        )
        result = await self._execute(statement)
        return list(result.unique().scalars().all())

    async def delete_by_team_id(self, team_id: uuid.UUID) -> None:
        stmt = delete(OrganizationTeamMember).where(OrganizationTeamMember.team_id == team_id)
        await self.db.execute(stmt)

    async def is_manager(self, team_id: uuid.UUID, organization_member_id: uuid.UUID) -> bool:
        statement = (
            select(OrganizationTeamMember)
            .where(
                OrganizationTeamMember.team_id == team_id,
                OrganizationTeamMember.organization_member_id == organization_member_id,
                OrganizationTeamMember.type == OrganizationTeamMemberTypeEnum.MANAGER,
            )
            .limit(1)
        )
        result = await self._scalar(statement)
        return result is not None

    async def get_manager_by_team_id(self, team_id: uuid.UUID) -> OrganizationTeamMember | None:
        statement = (
            select(OrganizationTeamMember)
            .options(
                selectinload(OrganizationTeamMember.member).selectinload(OrganizationMember.user),
                joinedload(OrganizationTeamMember.team),
            )
            .where(
                OrganizationTeamMember.team_id == team_id,
                OrganizationTeamMember.type == OrganizationTeamMemberTypeEnum.MANAGER,
            )
            .limit(1)
        )
        return await self._scalar(statement)

    async def get_managers_by_team_ids(self, team_ids: list[uuid.UUID]) -> dict[uuid.UUID, uuid.UUID]:
        if not team_ids:
            return {}
        statement = (
            select(
                OrganizationTeamMember.team_id,
                OrganizationMember.user_id,
            )
            .join(OrganizationMember, OrganizationMember.id == OrganizationTeamMember.organization_member_id)
            .where(
                OrganizationTeamMember.team_id.in_(team_ids),
                OrganizationTeamMember.type == OrganizationTeamMemberTypeEnum.MANAGER,
            )
        )
        result = await self._execute(statement)
        return {team_id: manager_id for team_id, manager_id in result.all()}

    async def delete_by_member_id(self, member_id: uuid.UUID) -> None:
        stmt = delete(OrganizationTeamMember).where(
            OrganizationTeamMember.organization_member_id == member_id,
        )
        await self.db.execute(stmt)

    async def find_manager_id(self, team_id: uuid.UUID) -> uuid.UUID | None:
        statement = (
            select(OrganizationMember.user_id)
            .join(OrganizationTeamMember, OrganizationTeamMember.organization_member_id == OrganizationMember.id)
            .where(
                OrganizationTeamMember.team_id == team_id,
                OrganizationTeamMember.type == OrganizationTeamMemberTypeEnum.MANAGER,
            )
            .limit(1)
        )
        return await self._scalar(statement)

    async def bulk_create(self, team_members: list[OrganizationTeamMember]) -> None:
        if not team_members:
            return
        self.db.add_all(team_members)
        await self.db.flush()

    async def get_by_member_id(self, member_id: uuid.UUID) -> list[OrganizationTeamMember]:
        statement = (
            select(OrganizationTeamMember)
            .options(
                selectinload(OrganizationTeamMember.team),
                selectinload(OrganizationTeamMember.member).selectinload(OrganizationMember.user),
            )
            .where(OrganizationTeamMember.organization_member_id == member_id)
            .order_by(OrganizationTeamMember.id)
        )
        result = await self._execute(statement)
        return list(result.unique().scalars().all())

    async def update_member_type(
        self,
        team_id: uuid.UUID,
        member_id: uuid.UUID,
        member_type: OrganizationTeamMemberTypeEnum,
    ) -> None:
        stmt = (
            update(OrganizationTeamMember)
            .where(
                OrganizationTeamMember.team_id == team_id,
                OrganizationTeamMember.organization_member_id == member_id,
            )
            .values(type=member_type)
        )
        await self.db.execute(stmt)

    async def delete_by_member_and_team_ids(self, member_id: uuid.UUID, team_ids: list[uuid.UUID]) -> None:
        if not team_ids:
            return
        stmt = delete(OrganizationTeamMember).where(
            OrganizationTeamMember.organization_member_id == member_id,
            OrganizationTeamMember.team_id.in_(team_ids),
        )
        await self.db.execute(stmt)


async def get_organization_team_repository(
    session: AsyncSession = Depends(get_session),
) -> OrganizationTeamRepository:
    return OrganizationTeamRepositorySQLAlchemy(session)


async def get_organization_team_member_repository(
    session: AsyncSession = Depends(get_session),
) -> OrganizationTeamMemberRepository:
    return OrganizationTeamMemberRepositorySQLAlchemy(session)
