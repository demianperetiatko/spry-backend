from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database.transaction import atomic
from src.modules.calendar.models import UserCalendar
from src.modules.calendar.repository import CalendarRepository
from src.modules.enums import CalendarSyncStatusEnum
from src.shared.notifications import send_token_expiry_notification

logger = logging.getLogger(__name__)

TOKEN_REFRESH_TIMEOUT_SECONDS = 30


class TokenRefreshTimeoutError(Exception):
    """Raised when token refresh operation times out."""

    pass


class TokenInvalidError(Exception):
    """Raised when a token is invalid and cannot be refreshed."""

    pass


class GoogleTokenService:
    """Manages Google OAuth token operations for calendar sync."""

    def __init__(self, calendar_repo: CalendarRepository, session: AsyncSession) -> None:
        self.calendar_repo = calendar_repo
        self.session = session

    async def get_valid_credentials(self, user_calendar: UserCalendar) -> Credentials:
        """Get valid credentials for the user calendar, refreshing if needed."""
        info = user_calendar.user_access_info

        expiry = info.access_token_expiry
        if expiry:
            if expiry.tzinfo is not None:
                expiry = expiry.astimezone(timezone.utc).replace(tzinfo=None)

        creds = Credentials(
            token=info.access_token,
            refresh_token=info.refresh_token,
            token_uri=settings.GOOGLE_TOKEN_ENDPOINT,
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            scopes=settings.GOOGLE_SCOPE,
            expiry=expiry,
        )

        if creds.expired and creds.refresh_token:
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(creds.refresh, Request()),
                    timeout=TOKEN_REFRESH_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError as e:
                logger.error(
                    f"Token refresh timed out for user_calendar {user_calendar.id} after {TOKEN_REFRESH_TIMEOUT_SECONDS}s"
                )
                raise TokenRefreshTimeoutError("Token refresh timed out") from e
            except RefreshError as e:
                logger.error(f"Token refresh failed for user_calendar {user_calendar.id}: {e}")
                await self.invalidate_access(user_calendar, "token_refresh_failed")
                raise TokenInvalidError("Token refresh failed") from e

            new_expiry = creds.expiry
            if new_expiry:
                if new_expiry.tzinfo is None:
                    new_expiry = new_expiry.replace(tzinfo=timezone.utc)
                else:
                    new_expiry = new_expiry.astimezone(timezone.utc)

            await self.calendar_repo.update_user_access_info_tokens(
                info, access_token=creds.token, access_token_expiry=new_expiry
            )

        return creds

    async def refresh_access_token(self, user_calendar: UserCalendar) -> Credentials | None:
        """Refresh the access token for a user calendar. Returns None if refresh fails."""
        info = user_calendar.user_access_info
        if not info.refresh_token:
            return None

        creds = Credentials(
            token=None,
            refresh_token=info.refresh_token,
            token_uri=settings.GOOGLE_TOKEN_ENDPOINT,
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            scopes=settings.GOOGLE_SCOPE,
        )
        try:
            await asyncio.wait_for(
                asyncio.to_thread(creds.refresh, Request()),
                timeout=TOKEN_REFRESH_TIMEOUT_SECONDS,
            )
        except (RefreshError, asyncio.TimeoutError):
            return None

        new_expiry = creds.expiry
        if new_expiry:
            if new_expiry.tzinfo is None:
                new_expiry = new_expiry.replace(tzinfo=timezone.utc)
            else:
                new_expiry = new_expiry.astimezone(timezone.utc)

        await self.calendar_repo.update_user_access_info_tokens(info, access_token=creds.token, access_token_expiry=new_expiry)
        return creds

    async def invalidate_access(self, user_calendar: UserCalendar, reason: str) -> None:
        """Mark a calendar sync as failed due to invalid token and notify the user."""
        user_id = user_calendar.user_access_info.user_id
        await self.mark_sync_status(user_calendar.id, CalendarSyncStatusEnum.FAILED, sync_error=reason)
        try:
            send_token_expiry_notification(user_id)
        except (Exception,):
            logger.warning("Failed to send token expiry notification for user %s", user_id, exc_info=True)

    async def mark_sync_status(
        self,
        user_calendar_id,
        status: CalendarSyncStatusEnum,
        sync_error: str | None = None,
    ) -> None:
        """Update the sync status for a user calendar."""
        async with atomic(self.session):
            await self.calendar_repo.update_sync_state(
                user_calendar_id=user_calendar_id,
                sync_status=status,
                sync_error=sync_error,
                last_sync_at=datetime.now(timezone.utc),
            )
