from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from decimal import Decimal

from fastapi import Depends
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, joinedload, selectinload

from src.core.database.repository import CRUDRepository, CRUDRepositorySQLAlchemy
from src.core.database.session import get_session
from src.modules.enums import OrganizationMemberRoleEnum, OrganizationTeamMemberTypeEnum
from src.modules.organization_member.model import OrganizationMember
from src.modules.organization_team.model import OrganizationTeamMember
from src.modules.user.model import User


class OrganizationMemberRepository(CRUDRepository[OrganizationMember, uuid.UUID], ABC):
    @abstractmethod
    async def is_user_admin_in_any_organization(self, user_id: uuid.UUID) -> bool:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_user_id_and_organization_id(
        self,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> OrganizationMember | None:
        raise NotImplementedError()

    @abstractmethod
    async def update_organization_members_cost(
        self,
        organization_id: uuid.UUID,
        hourly_cost: Decimal | None,
    ) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def is_manager_of_organization(
        self,
        member: OrganizationMember,
    ) -> bool:
        raise NotImplementedError()

    @abstractmethod
    async def get_user_email_by_member_id(self, member_id: uuid.UUID) -> str | None:
        raise NotImplementedError()

    @abstractmethod
    async def get_active_members_by_user_id(self, user_id: uuid.UUID) -> list[OrganizationMember]:
        raise NotImplementedError()

    @abstractmethod
    async def get_members_by_organization_id(
        self,
        organization_id: uuid.UUID,
        search_query: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[OrganizationMember], int]:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_email_and_organization_id(self, email: str, organization_id: uuid.UUID) -> OrganizationMember | None:
        raise NotImplementedError()

    @abstractmethod
    async def count_members_in_org(self, member_ids: list[uuid.UUID], organization_id: uuid.UUID) -> int:
        raise NotImplementedError()

    @abstractmethod
    async def are_members_in_same_team(self, member_a_id: uuid.UUID, member_b_id: uuid.UUID) -> bool:
        raise NotImplementedError()


class OrganizationMemberRepositorySQLAlchemy(
    OrganizationMemberRepository,
    CRUDRepositorySQLAlchemy[OrganizationMember, uuid.UUID],
):
    def get_entity_class(self) -> type[OrganizationMember]:
        return OrganizationMember

    async def is_user_admin_in_any_organization(self, user_id: uuid.UUID) -> bool:
        statement = (
            select(OrganizationMember)
            .where(
                OrganizationMember.user_id == user_id,
                OrganizationMember.role == OrganizationMemberRoleEnum.ADMIN,
            )
            .limit(1)
            .execution_options(populate_existing=True)
        )
        result = await self._scalar(statement)
        return result is not None

    async def get_by_user_id_and_organization_id(
        self,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> OrganizationMember | None:
        statement = (
            select(OrganizationMember)
            .options(
                selectinload(OrganizationMember.user),
                joinedload(OrganizationMember.team_members).joinedload(OrganizationTeamMember.team),
            )
            .where(
                OrganizationMember.user_id == user_id,
                OrganizationMember.organization_id == organization_id,
            )
            .limit(1)
            .execution_options(populate_existing=True)
        )
        result = await self.db.execute(statement)
        return result.unique().scalar_one_or_none()

    async def update_organization_members_cost(
        self,
        organization_id: uuid.UUID,
        hourly_cost: Decimal | None,
    ) -> None:
        async with self._autocommit() as session:
            stmt = (
                update(OrganizationMember)
                .where(OrganizationMember.organization_id == organization_id)
                .values(hourly_cost=hourly_cost)
            )
            await session.execute(stmt)

    async def is_manager_of_organization(
        self,
        member: OrganizationMember,
    ) -> bool:
        statement = (
            select(OrganizationTeamMember)
            .join(OrganizationMember, OrganizationTeamMember.organization_member_id == OrganizationMember.id)
            .where(
                OrganizationMember.id == member.id,
                OrganizationMember.organization_id == member.organization_id,
                OrganizationTeamMember.type == OrganizationTeamMemberTypeEnum.MANAGER,
            )
            .limit(1)
            .execution_options(populate_existing=True)
        )
        result = await self._execute(statement)
        return result.scalar_one_or_none() is not None

    async def get_user_email_by_member_id(self, member_id: uuid.UUID) -> str | None:
        stmt = (
            select(User.email)
            .join(OrganizationMember, OrganizationMember.user_id == User.id)
            .where(OrganizationMember.id == member_id)
        )
        return await self._scalar(stmt)

    async def get_active_members_by_user_id(self, user_id: uuid.UUID) -> list[OrganizationMember]:
        from src.modules.enums import OrganizationMemberStatusEnum

        statement = (
            select(OrganizationMember)
            .options(joinedload(OrganizationMember.organization))
            .where(
                OrganizationMember.user_id == user_id,
                OrganizationMember.status == OrganizationMemberStatusEnum.ACTIVE,
            )
            .execution_options(populate_existing=True)
        )
        result = await self._execute(statement)
        return list(result.unique().scalars().all())

    async def get_members_by_organization_id(
        self,
        organization_id: uuid.UUID,
        search_query: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[OrganizationMember], int]:
        base = (
            select(OrganizationMember.id)
            .join(User, OrganizationMember.user_id == User.id)
            .where(OrganizationMember.organization_id == organization_id)
        )

        if search_query:
            term = f"%{search_query.strip()}%"
            base = base.where(
                or_(
                    User.name.ilike(term),
                    User.email.ilike(term),
                )
            )

        total = await self._scalar(select(func.count()).select_from(base.subquery())) or 0

        stmt = (
            select(OrganizationMember)
            .join(OrganizationMember.user)
            .options(
                contains_eager(OrganizationMember.user),
                selectinload(OrganizationMember.team_members).selectinload(OrganizationTeamMember.team),
            )
            .where(OrganizationMember.organization_id == organization_id)
            .order_by(User.email)
        )

        if search_query:
            term = f"%{search_query.strip()}%"
            stmt = stmt.where(
                or_(
                    User.name.ilike(term),
                    User.email.ilike(term),
                )
            )

        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)

        result = await self.db.execute(stmt)
        members = list(result.unique().scalars().all())

        return members, total

    async def get_by_email_and_organization_id(
        self,
        email: str,
        organization_id: uuid.UUID,
    ) -> OrganizationMember | None:
        statement = (
            select(OrganizationMember)
            .join(User, OrganizationMember.user_id == User.id)
            .where(User.email == email.lower(), OrganizationMember.organization_id == organization_id)
            .limit(1)
            .execution_options(populate_existing=True)
        )
        return await self._scalar(statement)

    async def count_members_in_org(self, member_ids: list[uuid.UUID], organization_id: uuid.UUID) -> int:
        if not member_ids:
            return 0
        statement = (
            select(func.count())
            .select_from(OrganizationMember)
            .where(
                OrganizationMember.id.in_(member_ids),
                OrganizationMember.organization_id == organization_id,
            )
        )
        result = await self._execute(statement)
        return result.scalar_one() or 0

    async def are_members_in_same_team(self, member_a_id: uuid.UUID, member_b_id: uuid.UUID) -> bool:
        editor_teams_stmt = select(OrganizationTeamMember.team_id).where(
            OrganizationTeamMember.organization_member_id == member_a_id,
            OrganizationTeamMember.type == OrganizationTeamMemberTypeEnum.MANAGER,
        )
        editor_result = await self._execute(editor_teams_stmt)
        editor_team_ids = set(editor_result.scalars().all())

        if not editor_team_ids:
            return False

        target_teams_stmt = (
            select(OrganizationTeamMember.team_id)
            .where(
                OrganizationTeamMember.organization_member_id == member_b_id,
                OrganizationTeamMember.team_id.in_(list(editor_team_ids)),
            )
            .limit(1)
        )
        target_result = await self._execute(target_teams_stmt)
        return target_result.scalar_one_or_none() is not None


async def get_organization_member_repository(session: AsyncSession = Depends(get_session)) -> OrganizationMemberRepository:
    return OrganizationMemberRepositorySQLAlchemy(session)
