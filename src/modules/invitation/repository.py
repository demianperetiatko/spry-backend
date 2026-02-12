from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.repository import CRUDRepository, CRUDRepositorySQLAlchemy
from src.core.database.session import get_session
from src.modules.invitation.model import Invitation


class InvitationRepository(CRUDRepository[Invitation, uuid.UUID], ABC):
    @abstractmethod
    async def get_by_token(self, token: str) -> Invitation | None:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_token_for_update(self, token: str) -> Invitation | None:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_user_id_and_organization_id(
        self,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Invitation | None:
        raise NotImplementedError()


class InvitationRepositorySQLAlchemy(
    InvitationRepository,
    CRUDRepositorySQLAlchemy[Invitation, uuid.UUID],
):
    def get_entity_class(self) -> type[Invitation]:
        return Invitation

    async def get_by_token(self, token: str) -> Invitation | None:
        return await self._scalar(select(Invitation).where(Invitation.token == token).limit(1))

    async def get_by_token_for_update(self, token: str) -> Invitation | None:
        stmt = select(Invitation).where(Invitation.token == token).with_for_update().limit(1)
        return await self._scalar(stmt)

    async def get_by_user_id_and_organization_id(
        self,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Invitation | None:
        stmt = (
            select(Invitation)
            .where(
                Invitation.user_id == user_id,
                Invitation.organization_id == organization_id,
            )
            .limit(1)
        )
        return await self._scalar(stmt)


async def get_invitation_repository(session: AsyncSession = Depends(get_session)) -> InvitationRepository:
    return InvitationRepositorySQLAlchemy(session)
