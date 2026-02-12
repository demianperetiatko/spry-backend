from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import AsyncIterator, Generic, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundException

T = TypeVar("T")
ID = TypeVar("ID")


class Repository(ABC): ...


class CRUDRepository(Repository, Generic[T, ID], ABC):
    @abstractmethod
    async def get_by_id(self, id: ID) -> T | None:
        raise NotImplementedError()

    @abstractmethod
    async def find_by_id(self, id: ID) -> T:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_ids(self, ids: list[ID]) -> list[T]:
        raise NotImplementedError()

    @abstractmethod
    async def find_by_ids(self, ids: list[ID]) -> list[T]:
        raise NotImplementedError()

    @abstractmethod
    async def get_all(self) -> list[T]:
        raise NotImplementedError()

    @abstractmethod
    async def has(self, id: ID) -> bool:
        raise NotImplementedError()

    @abstractmethod
    async def create(self, entity: T) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def update(self, entity: T) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def update_many(self, entities: list[T]) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def remove(self, entity: T) -> None:
        raise NotImplementedError()


class RepositorySQLAlchemy(Repository, ABC):
    def __init__(self, session: AsyncSession) -> None:
        self._session_instance = session

    @property
    def db(self) -> AsyncSession:
        return self._session_instance

    @asynccontextmanager
    async def _autocommit(self) -> AsyncIterator[AsyncSession]:
        session = self.db

        info: dict = session.info
        in_transaction = session.in_transaction() and info.get("__explicit_transaction__") is not None
        try:
            yield session
            if not in_transaction and session.in_transaction():
                await session.commit()
        except Exception as e:
            if not in_transaction and session.in_transaction():
                await session.rollback()
            raise e

    async def _scalars(self, *args, **kwargs):
        async with self._autocommit() as session:
            return await session.scalars(*args, **kwargs)

    async def _scalar(self, *args, **kwargs):
        async with self._autocommit() as session:
            return await session.scalar(*args, **kwargs)

    async def _execute(self, *args, **kwargs):
        async with self._autocommit() as session:
            return await session.execute(*args, **kwargs)


class CRUDRepositorySQLAlchemy(CRUDRepository[T, ID], RepositorySQLAlchemy, ABC):
    async def get_by_id(self, id: ID) -> T | None:
        entity_class = self.get_entity_class()
        statement = select(entity_class).where(entity_class.id == id).execution_options(populate_existing=True)

        return await self._scalar(statement)

    async def find_by_id(self, id: ID) -> T:
        entity = await self.get_by_id(id)
        if entity is None:
            raise self.not_found_exception()

        return entity

    async def get_by_ids(self, ids: list[ID]) -> list[T]:
        if len(ids) == 0:
            return []

        entity_class = self.get_entity_class()
        statement = select(entity_class).where(entity_class.id.in_(ids)).execution_options(populate_existing=True)

        return list(await self._scalars(statement))

    async def find_by_ids(self, ids: list[ID]) -> list[T]:
        entities = await self.get_by_ids(ids)
        if len(entities) != len(set(ids)):
            raise self.not_found_exception()

        return entities

    async def get_all(self) -> list[T]:
        return list(await self._scalars(select(self.get_entity_class()).execution_options(populate_existing=True)))

    async def has(self, id: ID) -> bool:
        entity_class = self.get_entity_class()
        entity_id: str | None = await self._scalar(select(entity_class).where(entity_class.id == id))

        return entity_id is not None

    async def create(self, entity: T) -> None:
        async with self._autocommit() as session:
            session.add(entity)
            await session.flush()

    async def update(self, entity: T) -> None:
        async with self._autocommit() as session:
            session.add(entity)
            await session.flush()

    async def update_many(self, entities: list[T]) -> None:
        if not entities:
            return

        async with self._autocommit() as session:
            session.add_all(entities)
            await session.flush()

    async def remove(self, entity: T) -> None:
        async with self._autocommit() as session:
            await session.delete(entity)
            await session.flush()

    @abstractmethod
    def get_entity_class(self) -> Type[T]:
        raise NotImplementedError()

    def not_found_exception(self) -> NotFoundException:
        entity_class = self.get_entity_class()

        return NotFoundException(f"Entity {entity_class.__name__} not found")
