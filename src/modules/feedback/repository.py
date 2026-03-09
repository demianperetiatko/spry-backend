from __future__ import annotations

import uuid

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.repository import CRUDRepositorySQLAlchemy
from src.core.database.session import get_session
from src.modules.feedback.model import Feedback


class FeedbackRepository(CRUDRepositorySQLAlchemy[Feedback, uuid.UUID]):
    def get_entity_class(self) -> type[Feedback]:
        return Feedback


async def get_feedback_repository(session: AsyncSession = Depends(get_session)) -> FeedbackRepository:
    return FeedbackRepository(session)
