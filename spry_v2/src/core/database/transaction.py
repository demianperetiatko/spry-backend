import contextlib
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession


@contextlib.asynccontextmanager
async def atomic(session: AsyncSession) -> AsyncGenerator[None, None]:
    session.info["__explicit_transaction__"] = True
    try:
        yield
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        session.info.pop("__explicit_transaction__", None)
