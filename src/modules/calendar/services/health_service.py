from __future__ import annotations

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ServiceException
from src.modules.calendar.clients.google_gateway import GoogleCalendarGateway
from src.modules.calendar.repository import CalendarRepository
from src.modules.calendar.services.connect_service import CalendarConnectService
from src.modules.calendar.services.sync_service import CalendarSyncEngine
from src.modules.calendar.services.token_service import GoogleTokenService
from src.modules.calendar.services.webhook_service import CalendarWebhookService
from src.modules.enums import OrganizationMemberStatusEnum
from src.modules.organization_member.repository import OrganizationMemberRepositorySQLAlchemy

logger = logging.getLogger(__name__)


class CalendarHealthService:
    RESYNC_MEMBER_DELAY = 0.25

    def __init__(
        self,
        calendar_repo: CalendarRepository,
        sync_engine: CalendarSyncEngine,
        webhook_service: CalendarWebhookService,
        connect_service: CalendarConnectService,
        gateway: GoogleCalendarGateway,
        token_service: GoogleTokenService,
        session: AsyncSession,
    ) -> None:
        self.calendar_repo = calendar_repo
        self.sync_engine = sync_engine
        self.webhook_service = webhook_service
        self.connect_service = connect_service
        self.gateway = gateway
        self.token_service = token_service
        self.session = session

    async def ensure_calendar_health(self, user_id: uuid.UUID) -> None:
        org_member_repo = OrganizationMemberRepositorySQLAlchemy(self.session)
        active_members = await org_member_repo.get_active_members_by_user_id(user_id)

        if not active_members:
            logger.debug(f"No active organization members found for user {user_id}")
            return

        logger.info(f"Ensuring calendar health for user {user_id} with {len(active_members)} active organizations")

        member_ids = [m.id for m in active_members]
        calendars_by_member = await self.calendar_repo.get_calendars_for_members(member_ids)

        for member in active_members:
            try:
                calendars = calendars_by_member.get(member.id, [])

                if not calendars:
                    logger.debug(
                        f"No calendars found for member {member.id} in organization {member.organization_id}. "
                        "Attempting to connect calendar."
                    )
                    try:
                        user_email = await org_member_repo.get_user_email_by_member_id(member.id)
                        if user_email:
                            await self.connect_service.connect_calendar(
                                user_id=user_id,
                                member_id=member.id,
                                user_email=user_email,
                            )
                            logger.info(f"Successfully connected calendar for member {member.id}")
                        else:
                            logger.warning(f"Could not get user email for member {member.id}")
                    except Exception as e:
                        logger.error(
                            f"Failed to connect calendar for member {member.id}: {e}",
                            exc_info=True,
                        )
                    continue

                for calendar in calendars:
                    try:
                        await self.webhook_service.enable_push_notifications(calendar.id)
                    except Exception as e:
                        logger.warning(
                            f"Failed to enable push notifications for calendar {calendar.id} "
                            f"(member {calendar.organization_member_id}): {e}",
                        )

                    try:
                        # Incremental sync when possible (fast, non-destructive).
                        # Falls back to full sync internally if no sync_token exists.
                        await self.sync_engine.synchronize_calendar_by_user_calendar_id(
                            calendar.user_calendar_id, check_type="incremental"
                        )
                        logger.debug(f"Resynced calendar {calendar.id}")
                    except Exception as e:
                        logger.error(
                            f"Failed to resync calendar {calendar.id} (member {calendar.organization_member_id}): {e}",
                            exc_info=True,
                        )
            except Exception as e:
                logger.error(f"Error processing calendars for member {member.id}: {e}", exc_info=True)

    async def manual_resync_for_organization(self, organization_id: uuid.UUID) -> dict[str, object]:
        org_member_repo = OrganizationMemberRepositorySQLAlchemy(self.session)
        members, _ = await org_member_repo.get_members_by_organization_id(organization_id)

        if not members:
            raise ServiceException("No members found for organization", status_code=404)

        results = await self._process_members_resync(members)

        if not results:
            raise ServiceException("No calendars found for organization", status_code=404)

        return {"status": "ok", "results": results}

    async def manual_resync_for_user(self, user_id: uuid.UUID) -> dict[str, object]:
        org_member_repo = OrganizationMemberRepositorySQLAlchemy(self.session)
        members = await org_member_repo.get_active_members_by_user_id(user_id)
        if not members:
            raise ServiceException("No active memberships found for user", status_code=404)

        results = await self._process_members_resync(members)

        if not results:
            raise ServiceException("No calendars found for user", status_code=404)

        return {"status": "ok", "results": results}

    async def _process_members_resync(self, members: list) -> list[dict]:
        results: list[dict] = []
        seen_user_calendar_ids: set[uuid.UUID] = set()

        active_members = [m for m in members if not getattr(m, "status", None) or m.status == OrganizationMemberStatusEnum.ACTIVE]

        if not active_members:
            return results

        member_ids = [m.id for m in active_members]
        calendars_by_member = await self.calendar_repo.get_calendars_for_members(member_ids)

        for member in active_members:
            calendars = calendars_by_member.get(member.id, [])
            for calendar in calendars:
                uc_id = calendar.user_calendar.id
                if uc_id in seen_user_calendar_ids:
                    continue
                seen_user_calendar_ids.add(uc_id)

                await asyncio.sleep(self.RESYNC_MEMBER_DELAY)

                try:
                    await self.sync_engine.synchronize_calendar_by_user_calendar_id(uc_id, check_type="full")
                    results.append(
                        {
                            "user_calendar_id": str(uc_id),
                            "organization_id": str(member.organization_id),
                            "member_id": str(member.id),
                            "status": "success",
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to resync user calendar {uc_id}: {e}")
                    results.append(
                        {
                            "user_calendar_id": str(uc_id),
                            "organization_id": str(member.organization_id),
                            "member_id": str(member.id),
                            "status": "failed",
                            "error": str(e),
                        }
                    )

        return results
