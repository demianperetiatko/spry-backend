from __future__ import annotations

import logging
import uuid

from google.oauth2.credentials import Credentials
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.calendar.client import GoogleCalendarClient
from src.modules.calendar.clients.google_gateway import GoogleCalendarGateway
from src.modules.calendar.models import UserCalendar
from src.modules.calendar.repository import CalendarRepository
from src.modules.calendar.services.connect_service import CalendarConnectService
from src.modules.calendar.services.health_service import CalendarHealthService
from src.modules.calendar.services.sync_service import CalendarSyncEngine
from src.modules.calendar.services.token_service import GoogleTokenService
from src.modules.calendar.services.webhook_service import CalendarWebhookService

# Re-export for backwards compatibility
from src.modules.calendar.services.token_service import TokenInvalidError  # noqa: F401


class CalendarService:
    """
    Facade for calendar operations.

    This class delegates to focused services while preserving the original public API.
    """

    def __init__(
        self,
        calendar_repo: CalendarRepository,
        session: AsyncSession,
        google_client: GoogleCalendarClient,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.calendar_repo = calendar_repo
        self.session = session
        self.google_client = google_client

        self._token_service = GoogleTokenService(calendar_repo, session)
        self._gateway = GoogleCalendarGateway(google_client, self._token_service)
        self._webhook_service = CalendarWebhookService(calendar_repo, self._gateway, self._token_service, session)
        self._sync_engine = CalendarSyncEngine(calendar_repo, self._gateway, self._token_service, session)
        self._connect_service = CalendarConnectService(calendar_repo, self._sync_engine, self._webhook_service)
        self._health_service = CalendarHealthService(
            calendar_repo,
            self._sync_engine,
            self._webhook_service,
            self._connect_service,
            self._gateway,
            self._token_service,
            session,
        )

    # === Public API (10 methods) ===

    async def connect_calendar(self, user_id: uuid.UUID, member_id: uuid.UUID, user_email: str) -> dict[str, object]:
        """Connect a calendar to an organization member."""
        return await self._connect_service.connect_calendar(user_id, member_id, user_email)

    async def synchronize_calendar(self, calendar_id: uuid.UUID, check_type: str = "incremental") -> None:
        """Synchronize a calendar by its organization calendar ID."""
        return await self._sync_engine.synchronize_calendar(calendar_id, check_type)

    async def synchronize_calendar_by_user_calendar_id(
        self, user_calendar_id: uuid.UUID, check_type: str = "incremental"
    ) -> None:
        """Synchronize calendar by user_calendar_id. Used for webhooks."""
        return await self._sync_engine.synchronize_calendar_by_user_calendar_id(user_calendar_id, check_type)

    async def manual_resync_for_organization(self, organization_id: uuid.UUID) -> dict[str, object]:
        """Manually resync all calendars for an organization."""
        return await self._health_service.manual_resync_for_organization(organization_id)

    async def manual_resync_for_user(self, user_id: uuid.UUID) -> dict[str, object]:
        """Manually resync all calendars for a user."""
        return await self._health_service.manual_resync_for_user(user_id)

    async def validate_webhook_request(self, channel_id: str | None, resource_id: str | None) -> uuid.UUID | None:
        """Validate a webhook request and return the user_calendar_id if valid."""
        return await self._webhook_service.validate_webhook_request(channel_id, resource_id)

    async def enable_push_notifications(self, calendar_id: uuid.UUID) -> None:
        """Enable push notifications for a calendar."""
        return await self._webhook_service.enable_push_notifications(calendar_id)

    async def disable_push_notifications(self, calendar_id: uuid.UUID) -> None:
        """Disable push notifications for a calendar."""
        return await self._webhook_service.disable_push_notifications(calendar_id)

    async def ensure_calendar_health(self, user_id: uuid.UUID) -> None:
        """Ensure calendar health for a user across all their organizations."""
        return await self._health_service.ensure_calendar_health(user_id)

    async def get_valid_credentials(self, user_calendar: UserCalendar) -> Credentials:
        """Get valid credentials for the user calendar, refreshing if needed."""
        return await self._token_service.get_valid_credentials(user_calendar)

    async def create_event(self, user_calendar: UserCalendar, body: dict) -> dict:
        """Create an event in the given user calendar and trigger an incremental sync."""
        credentials = await self.get_valid_credentials(user_calendar)
        event, _ = await self._gateway.create_event_with_retry(credentials, user_calendar, body)
        try:
            await self._sync_engine.synchronize_calendar_by_user_calendar_id(user_calendar.id)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Event created but sync failed for calendar %s: %s", user_calendar.id, exc)
        return event

    async def update_event(self, user_calendar: UserCalendar, event_id: str, body: dict) -> dict | None:
        """Update an event in the given user calendar and refresh cache."""
        credentials = await self.get_valid_credentials(user_calendar)
        event, _ = await self._gateway.update_event_with_retry(credentials, user_calendar, event_id, body)
        if event is not None:
            try:
                await self._sync_engine.synchronize_calendar_by_user_calendar_id(user_calendar.id)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("Event updated but sync failed for calendar %s: %s", user_calendar.id, exc)
        return event
