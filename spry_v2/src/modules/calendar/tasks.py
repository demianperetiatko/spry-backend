from __future__ import annotations

import asyncio
import logging
import uuid

from src.core.database.session import sessionmanager
from src.modules.calendar.client import GoogleCalendarClient
from src.modules.calendar.repository import CalendarRepository
from src.modules.calendar.service import CalendarService

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 2.0


async def task_connect_calendar_wrapper(user_id: uuid.UUID, member_id: uuid.UUID, user_email: str) -> None:
    logger.info(f"Starting background calendar connection for {user_email}")

    for attempt in range(MAX_RETRIES):
        async with sessionmanager.session() as session:
            try:
                calendar_repo = CalendarRepository(session)
                user_access_info = await calendar_repo.get_user_access_info(user_id)

                if not user_access_info:
                    logger.debug(f"User {user_id} has no Google access info, skipping calendar connection")
                    return

                google_client = GoogleCalendarClient()
                calendar_service = CalendarService(
                    calendar_repo=calendar_repo,
                    session=session,
                    google_client=google_client,
                )

                await calendar_service.connect_calendar(
                    user_id=user_id,
                    member_id=member_id,
                    user_email=user_email,
                )
                logger.info(f"Successfully connected calendar for {user_email}")
                return

            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    backoff = BASE_BACKOFF_SECONDS * (2**attempt)
                    logger.warning(
                        f"Failed to connect calendar for {user_email} (attempt {attempt + 1}/{MAX_RETRIES}), "
                        f"retrying in {backoff}s: {e}"
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.error(
                        f"Failed to connect calendar in background for {user_email} after {MAX_RETRIES} attempts: {e}",
                        exc_info=True,
                    )


async def background_resync_organization_task(organization_id: uuid.UUID) -> None:
    logger.info(f"Starting background organization resync for org={organization_id}")

    for attempt in range(MAX_RETRIES):
        async with sessionmanager.session() as session:
            try:
                calendar_repo = CalendarRepository(session)
                google_client = GoogleCalendarClient()
                calendar_service = CalendarService(
                    calendar_repo=calendar_repo,
                    session=session,
                    google_client=google_client,
                )
                await calendar_service.manual_resync_for_organization(organization_id)
                logger.info(f"Finished background organization resync for org={organization_id}")
                return
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    backoff = BASE_BACKOFF_SECONDS * (2**attempt)
                    logger.warning(
                        f"Failed organization resync for org={organization_id} (attempt {attempt + 1}/{MAX_RETRIES}), "
                        f"retrying in {backoff}s: {e}"
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.error(
                        f"Failed background organization resync for org={organization_id} after {MAX_RETRIES} attempts: {e}",
                        exc_info=True,
                    )


async def background_incremental_sync_task(user_calendar_id: uuid.UUID) -> None:
    """Background task for webhook-triggered incremental sync with its own session."""
    logger.info(f"Starting background incremental sync for user_calendar={user_calendar_id}")

    for attempt in range(MAX_RETRIES):
        async with sessionmanager.session() as session:
            try:
                calendar_repo = CalendarRepository(session)
                google_client = GoogleCalendarClient()
                calendar_service = CalendarService(
                    calendar_repo=calendar_repo,
                    session=session,
                    google_client=google_client,
                )
                await calendar_service.synchronize_calendar_by_user_calendar_id(user_calendar_id, "incremental")
                logger.info(f"Finished background incremental sync for user_calendar={user_calendar_id}")
                return
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    backoff = BASE_BACKOFF_SECONDS * (2**attempt)
                    logger.warning(
                        f"Failed incremental sync for user_calendar={user_calendar_id} "
                        f"(attempt {attempt + 1}/{MAX_RETRIES}), retrying in {backoff}s: {e}"
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.error(
                        f"Failed background incremental sync for user_calendar={user_calendar_id} "
                        f"after {MAX_RETRIES} attempts: {e}",
                        exc_info=True,
                    )
