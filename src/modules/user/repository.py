from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.repository import CRUDRepository, CRUDRepositorySQLAlchemy
from src.core.database.session import get_session
from src.modules.user.model import User, UserAccessInfo


class UserRepository(CRUDRepository[User, uuid.UUID], ABC):
    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        raise NotImplementedError()

    @abstractmethod
    async def find_by_email(self, email: str) -> User:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_emails(self, emails: list[str]) -> list[User]:
        raise NotImplementedError()


class UserRepositorySQLAlchemy(UserRepository, CRUDRepositorySQLAlchemy[User, uuid.UUID]):
    def get_entity_class(self) -> type[User]:
        return User

    async def get_by_email(self, email: str) -> User | None:
        return await self.db.scalar(select(User).where(User.email == email).limit(1))

    async def find_by_email(self, email: str) -> User:
        user = await self.get_by_email(email)
        if user is None:
            raise self.not_found_exception()
        return user

    async def get_by_emails(self, emails: list[str]) -> list[User]:
        if not emails:
            return []
        # Normalize emails to lowercase for comparison
        emails_lower = [email.lower() for email in emails]
        result = await self.db.scalars(select(User).where(User.email.in_(emails_lower)))
        return list(result.all())


class UserAccessInfoRepository(
    CRUDRepository[UserAccessInfo, uuid.UUID],
    ABC,
):
    @abstractmethod
    async def get_by_user_id(self, user_id: uuid.UUID) -> UserAccessInfo | None:
        raise NotImplementedError()


class UserAccessInfoRepositorySQLAlchemy(
    UserAccessInfoRepository,
    CRUDRepositorySQLAlchemy[UserAccessInfo, uuid.UUID],
):
    async def get_by_user_id(self, user_id: uuid.UUID) -> UserAccessInfo | None:
        return await self.db.scalar(select(UserAccessInfo).where(UserAccessInfo.user_id == user_id).limit(1))

    def get_entity_class(self) -> type[UserAccessInfo]:
        return UserAccessInfo


async def get_user_repository(session: AsyncSession = Depends(get_session)) -> UserRepository:
    return UserRepositorySQLAlchemy(session)


async def get_user_access_info_repository(session: AsyncSession = Depends(get_session)) -> UserAccessInfoRepository:
    return UserAccessInfoRepositorySQLAlchemy(session)
