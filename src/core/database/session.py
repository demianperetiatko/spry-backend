from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.core.config import settings


class Base(DeclarativeBase):
    pass


class DatabaseSessionManager:
    def __init__(self, host: str, engine_kwargs: dict[str, Any] | None = None) -> None:
        if engine_kwargs is None:
            engine_kwargs = {}
        self._engine: AsyncEngine = create_async_engine(host, **engine_kwargs)
        self._sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(
            autocommit=False, bind=self._engine, expire_on_commit=False
        )

    async def close(self) -> None:
        if self._engine is None:
            return
        await self._engine.dispose()
        self._engine = None  # type: ignore
        self._sessionmaker = None  # type: ignore

    @contextlib.asynccontextmanager
    async def connect(self) -> AsyncIterator[AsyncConnection]:
        if self._engine is None:
            raise RuntimeError("DatabaseSessionManager is not initialized")

        async with self._engine.begin() as connection:
            try:
                yield connection
            except Exception:
                await connection.rollback()
                raise

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        if self._sessionmaker is None:
            raise RuntimeError("DatabaseSessionManager is not initialized")

        session = self._sessionmaker()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


sessionmanager = DatabaseSessionManager(settings.DATABASE_URL, {"echo": settings.DEBUG, "pool_pre_ping": True})


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with sessionmanager.session() as session:
        yield session
