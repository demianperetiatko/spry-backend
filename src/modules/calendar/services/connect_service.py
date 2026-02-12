from __future__ import annotations

import logging
import uuid

from src.core.exceptions import ServiceException
from src.modules.calendar.repository import CalendarRepository
from src.modules.calendar.services.sync_service import CalendarSyncEngine
from src.modules.calendar.services.webhook_service import CalendarWebhookService

logger = logging.getLogger(__name__)


class CalendarConnectService:
    """Service for connecting calendars to organizations."""

    def __init__(
        self,
        calendar_repo: CalendarRepository,
        sync_engine: CalendarSyncEngine,
        webhook_service: CalendarWebhookService,
    ) -> None:
        self.calendar_repo = calendar_repo
        self.sync_engine = sync_engine
        self.webhook_service = webhook_service

    async def connect_calendar(self, user_id: uuid.UUID, member_id: uuid.UUID, user_email: str) -> dict[str, object]:
        """Connect a calendar to an organization member."""
        user_access_info = await self.calendar_repo.get_user_access_info(user_id)
        if not user_access_info:
            raise ServiceException(
                "User has not connected Google account. Please authenticate with Google first.",
                code="google_auth_missing",
                status_code=400,
            )

        existing_calendars = await self.calendar_repo.get_calendars_for_member(member_id)
        if existing_calendars:
            return {
                "status": "ok",
                "message": "Calendar already connected",
                "calendar_id": str(existing_calendars[0].id),
            }

        calendar_email = user_access_info.calendar_email or user_email

        user_calendar = await self.calendar_repo.get_user_calendar_by_email(
            user_access_info_id=user_access_info.id,
            calendar_email=calendar_email,
        )

        org_calendar = await self.calendar_repo.create_calendar_for_member(
            organization_member_id=member_id,
            user_access_info_id=user_access_info.id,
            calendar_email=calendar_email,
            is_primary=True,
        )

        if user_calendar:
            logger.info(f"Calendar already synced on user level. Created organization link only for member {member_id}.")
            return {"status": "ok", "message": "Calendar connected", "calendar_id": str(org_calendar.id)}

        result: dict[str, object] = {
            "status": "ok",
            "message": "Calendar connected",
            "calendar_id": str(org_calendar.id),
            "warnings": [],
        }
        warnings: list[str] = []

        try:
            logger.info(f"Starting initial sync for {org_calendar.id}")
            await self.sync_engine.synchronize_calendar(org_calendar.id, check_type="full")
        except Exception as e:
            logger.error(f"Initial sync failed for {org_calendar.id}: {e}", exc_info=True)
            warnings.append("initial_sync_failed")

        try:
            await self.webhook_service.enable_push_notifications(org_calendar.id)
        except Exception as e:
            logger.error(f"Failed to enable push notifications for {org_calendar.id}: {e}", exc_info=True)
            warnings.append("webhook_setup_failed")

        if warnings:
            result["status"] = "partial"
            result["warnings"] = warnings

        return result
