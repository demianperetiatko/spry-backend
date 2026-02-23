from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database.transaction import atomic
from src.core.exceptions import ServiceException
from src.modules.calendar.clients.google_gateway import GoogleCalendarGateway
from src.modules.calendar.models import CalendarCacheMetadata
from src.modules.calendar.repository import CalendarRepository
from src.modules.calendar.services.token_service import GoogleTokenService, TokenInvalidError
from src.shared.notifications import send_token_expiry_notification

logger = logging.getLogger(__name__)


class WebhookValidationError(Exception):
    """Raised when webhook validation fails due to security mismatch."""

    pass


class CalendarWebhookService:
    """Manages Google Calendar push notification webhooks."""

    def __init__(
        self,
        calendar_repo: CalendarRepository,
        gateway: GoogleCalendarGateway,
        token_service: GoogleTokenService,
        session: AsyncSession,
    ) -> None:
        self.calendar_repo = calendar_repo
        self.gateway = gateway
        self.token_service = token_service
        self.session = session

    @staticmethod
    def is_channel_valid(metadata: CalendarCacheMetadata) -> bool:
        """Check if a webhook channel is valid and not expiring soon."""
        if not (metadata.channel_id and metadata.resource_id and metadata.channel_expiration):
            return False

        expiration = metadata.channel_expiration
        if expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=timezone.utc)

        return expiration > datetime.now(timezone.utc) + timedelta(hours=24)

    async def enable_push_notifications(self, calendar_id: uuid.UUID) -> None:
        """Enable push notifications for a calendar."""
        org_calendar = await self.calendar_repo.get_calendar(calendar_id)
        if not org_calendar:
            raise ServiceException("Calendar not found", status_code=404)

        user_calendar = org_calendar.user_calendar
        lock_acquired = await self.calendar_repo.acquire_sync_lock(user_calendar.id)
        if not lock_acquired:
            logger.warning(f"Sync lock already held for user calendar {user_calendar.id}, skipping push notifications")
            return

        metadata = await self.calendar_repo.ensure_sync_state(user_calendar.id, with_lock=True)

        if self.is_channel_valid(metadata):
            return

        credentials = await self.token_service.get_valid_credentials(user_calendar)

        # Stop existing channel if any
        if metadata.channel_id and metadata.resource_id:
            try:
                credentials = await self.gateway.stop_channel_with_retry(
                    credentials, user_calendar, metadata.channel_id, metadata.resource_id
                )
            except TokenInvalidError:
                user_id = user_calendar.user_access_info.user_id
                send_token_expiry_notification(user_id)
                return
            except Exception:
                pass  # Ignore errors when stopping old channel

        new_channel_id = str(uuid.uuid4())
        webhook_url = f"{settings.backend_domain.rstrip('/')}/integrations/google/webhook"

        if not webhook_url.startswith("https://"):
            raise ServiceException("Webhook URL must use HTTPS", code="invalid_config")

        try:
            c_id, r_id, exp_ts, credentials = await self.gateway.watch_events_with_retry(
                credentials, user_calendar, new_channel_id, webhook_url
            )
        except TokenInvalidError:
            user_id = user_calendar.user_access_info.user_id
            send_token_expiry_notification(user_id)
            return

        expiration_dt = None
        if exp_ts:
            try:
                expiration_dt = datetime.fromtimestamp(int(exp_ts) / 1000, tz=timezone.utc)
            except (ValueError, TypeError):
                pass

        async with atomic(self.session):
            await self.calendar_repo.update_sync_state(
                user_calendar_id=user_calendar.id,
                channel_id=c_id,
                resource_id=r_id,
                channel_expiration=expiration_dt,
            )

    async def disable_push_notifications(self, calendar_id: uuid.UUID) -> None:
        """Disable push notifications for a calendar."""
        org_calendar = await self.calendar_repo.get_calendar(calendar_id)
        if not org_calendar:
            return

        user_calendar = org_calendar.user_calendar
        metadata = await self.calendar_repo.get_sync_state(user_calendar.id)
        if not metadata or not metadata.channel_id:
            return

        credentials = await self.token_service.get_valid_credentials(user_calendar)
        channel_stopped = False
        try:
            await self.gateway.stop_channel_with_retry(credentials, user_calendar, metadata.channel_id, metadata.resource_id)
            channel_stopped = True
        except TokenInvalidError:
            user_id = user_calendar.user_access_info.user_id
            send_token_expiry_notification(user_id)
            # Still clear metadata since token is invalid - can't stop channel anyway
            channel_stopped = True
        except Exception as e:
            # Don't clear metadata if we failed to stop the channel on Google's side
            # This allows retry later
            logger.warning(f"Failed to stop webhook channel {metadata.channel_id} for calendar {calendar_id}: {e}")
            return

        if channel_stopped:
            async with atomic(self.session):
                await self.calendar_repo.update_sync_state(
                    user_calendar_id=user_calendar.id,
                    channel_id=None,
                    resource_id=None,
                    channel_expiration=None,
                )

    async def validate_webhook_request(self, channel_id: str | None, resource_id: str | None) -> uuid.UUID | None:
        """Validate a webhook request and return the user_calendar_id if valid.

        Raises:
            WebhookValidationError: If resource_id doesn't match (potential spoofing attempt).
        """
        if not channel_id or not resource_id:
            return None

        metadata = await self.calendar_repo.get_metadata_by_channel_id(channel_id)
        if not metadata:
            logger.warning(f"Metadata not found for channel: {channel_id}")
            return None

        if metadata.resource_id and metadata.resource_id != resource_id:
            logger.error(f"Resource mismatch for channel {channel_id}: expected={metadata.resource_id}, got={resource_id}")
            raise WebhookValidationError(f"Resource ID mismatch for channel {channel_id}")

        if not metadata.resource_id:
            async with atomic(self.session):
                await self.calendar_repo.update_sync_state(user_calendar_id=metadata.user_calendar_id, resource_id=resource_id)
        return metadata.user_calendar_id
