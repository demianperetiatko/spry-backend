from __future__ import annotations

import asyncio
import logging
import uuid

from sqlalchemy import select

from src.core.database.session import sessionmanager
from src.modules.user.model import User
from src.shared.email import get_email_service

logger = logging.getLogger(__name__)


async def _send_token_expiry_email(user_id: uuid.UUID) -> None:
    """Send token expiry email notification asynchronously."""
    async with sessionmanager.session() as session:
        result = await session.execute(select(User.email, User.name).where(User.id == user_id))
        row = result.first()
        if not row:
            logger.warning(f"User {user_id} not found for token expiry notification")
            return

        email, user_name = row
        email_service = get_email_service()
        try:
            await email_service.send_token_expiry_notification(
                email=email,
                user_name=user_name,
            )
            logger.info(f"Token expiry notification sent to {email}")
        except Exception as e:
            logger.error(f"Failed to send token expiry notification to {email}: {e}", exc_info=True)


def send_token_expiry_notification(user_id: uuid.UUID) -> None:
    """
    Send notification to user about token expiry.
    Schedules async email sending in background.
    """
    logger.info(f"Scheduling token expiry notification for user {user_id}")
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_send_token_expiry_email(user_id))
    except RuntimeError:
        # No running event loop - run synchronously
        asyncio.run(_send_token_expiry_email(user_id))
