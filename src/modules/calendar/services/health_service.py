from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.transaction import atomic
from src.core.exceptions import ServiceException
from src.modules.calendar.clients.google_gateway import GoogleCalendarGateway
from src.modules.calendar.domain.event_mapper import GoogleEventMapper
from src.modules.calendar.domain.sync_window import compute_sync_window
from src.modules.calendar.models import UserCalendar
from src.modules.calendar.repository import CalendarRepository
from src.modules.calendar.services.connect_service import CalendarConnectService
from src.modules.calendar.services.sync_service import CalendarSyncEngine
from src.modules.calendar.services.token_service import GoogleTokenService
from src.modules.calendar.services.webhook_service import CalendarWebhookService
from src.modules.enums import CalendarSyncStatusEnum, OrganizationMemberStatusEnum
from src.modules.organization_member.repository import OrganizationMemberRepositorySQLAlchemy

logger = logging.getLogger(__name__)


class CalendarHealthService:
    """Service for calendar health checks and manual resyncs."""

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
        """Ensure calendar health for a user across all their organizations."""
        org_member_repo = OrganizationMemberRepositorySQLAlchemy(self.session)
        active_members = await org_member_repo.get_active_members_by_user_id(user_id)

        if not active_members:
            logger.debug(f"No active organization members found for user {user_id}")
            return

        logger.info(f"Ensuring calendar health for user {user_id} with {len(active_members)} active organizations")

        # Batch fetch all calendars for all members in one query
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
                        logger.debug(f"Updated webhook channel for calendar {calendar.id}")
                    except Exception as e:
                        logger.error(
                            f"Failed to update webhook channel for calendar {calendar.id} (member {member.id}): {e}",
                            exc_info=True,
                        )
            except Exception as e:
                logger.error(f"Error processing calendars for member {member.id}: {e}", exc_info=True)

    async def manual_resync_for_organization(self, organization_id: uuid.UUID) -> dict[str, object]:
        """Manually resync all calendars for an organization."""
        org_member_repo = OrganizationMemberRepositorySQLAlchemy(self.session)
        members, _ = await org_member_repo.get_members_by_organization_id(organization_id)

        if not members:
            raise ServiceException("No members found for organization", status_code=404)

        results = await self._process_members_resync(members)

        if not results:
            raise ServiceException("No calendars found for organization", status_code=404)

        return {"status": "ok", "results": results}

    async def manual_resync_for_user(self, user_id: uuid.UUID) -> dict[str, object]:
        """Manually resync all calendars for a user."""
        org_member_repo = OrganizationMemberRepositorySQLAlchemy(self.session)
        members = await org_member_repo.get_active_members_by_user_id(user_id)
        if not members:
            raise ServiceException("No active memberships found for user", status_code=404)

        results = await self._process_members_resync(members)

        if not results:
            raise ServiceException("No calendars found for user", status_code=404)

        return {"status": "ok", "results": results}

    async def _process_members_resync(self, members: list) -> list[dict]:
        """Process resync for a list of members."""
        results: list[dict] = []
        seen_user_calendar_ids: set[uuid.UUID] = set()

        # Filter active members
        active_members = [m for m in members if not getattr(m, "status", None) or m.status == OrganizationMemberStatusEnum.ACTIVE]

        if not active_members:
            return results

        # Batch fetch all calendars for all members in one query
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
                    res = await self._manual_resync_user_calendar(uc_id)
                    res.update(
                        {
                            "organization_id": str(member.organization_id),
                            "member_id": str(member.id),
                            "status": "success",
                        }
                    )
                    results.append(res)
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

    async def _manual_resync_user_calendar(self, user_calendar_id: uuid.UUID) -> dict[str, object]:
        """Manually resync a specific user calendar."""
        org_calendar = await self.calendar_repo.get_calendar_by_user_calendar_id(user_calendar_id)
        if not org_calendar:
            raise ServiceException("Calendar not found", status_code=404)

        user_calendar = org_calendar.user_calendar
        lock_acquired = await self.calendar_repo.acquire_sync_lock(user_calendar.id)
        if not lock_acquired:
            raise ServiceException("Sync already in progress", status_code=409)

        try:
            return await self._execute_manual_sync_logic(user_calendar)
        except Exception as exc:
            logger.error(f"Manual sync failed for {user_calendar.id}: {exc}")
            await self.token_service.mark_sync_status(user_calendar.id, CalendarSyncStatusEnum.FAILED, sync_error=str(exc))
            raise

    async def _execute_manual_sync_logic(self, user_calendar: UserCalendar) -> dict[str, object]:
        """Execute the manual sync logic for a user calendar."""
        fallback_used = False

        async with atomic(self.session):
            metadata = await self.calendar_repo.ensure_sync_state(user_calendar.id, with_lock=True)
            await self.token_service.mark_sync_status(user_calendar.id, CalendarSyncStatusEnum.IN_PROGRESS)

        credentials = await self.token_service.get_valid_credentials(user_calendar)
        earliest_start = await self.calendar_repo.get_earliest_event_start(user_calendar.id)
        db_count = await self.calendar_repo.count_events_since(user_calendar.id, earliest_start)

        window_start, window_end = compute_sync_window(earliest_start)

        result = await self.gateway.safe_list_events(credentials, user_calendar, window_start, window_end)
        if result is None:
            return {
                "user_calendar_id": str(user_calendar.id),
                "skipped": True,
                "reason": "token_invalid",
            }
        events, next_sync_token, credentials = result

        api_count = len(events)
        use_events = events
        use_sync_token = next_sync_token

        if earliest_start is not None and api_count != db_count:
            fallback_used = True
            result = await self.gateway.safe_list_events(credentials, user_calendar, None, window_end)
            if result is None:
                return {
                    "user_calendar_id": str(user_calendar.id),
                    "skipped": True,
                    "reason": "token_invalid",
                }
            use_events, use_sync_token, credentials = result

        to_delete, to_upsert, attendees = GoogleEventMapper.process_events_payload(
            use_events, user_calendar.id, metadata.timezone
        )

        google_event_ids_in_upsert = {event.get("google_event_id") for event in to_upsert if event.get("google_event_id")}
        master_events_to_upsert = await self.sync_engine.get_master_events_to_upsert(
            use_events,
            credentials,
            user_calendar,
            metadata.timezone,
            google_event_ids_in_upsert,
        )

        google_ids_seen: set[str] = {
            event.get("google_event_id") for event in to_upsert + master_events_to_upsert if event.get("google_event_id")
        }
        missing_google_ids: set[str] = set()
        if not fallback_used and earliest_start is not None:
            existing_google_ids = await self.calendar_repo.get_google_event_ids(
                user_calendar.id, start_dt=window_start, end_dt=window_end
            )
            missing_google_ids = existing_google_ids - google_ids_seen - set(to_delete)

        async with atomic(self.session):
            if fallback_used or earliest_start is None:
                await self.calendar_repo.delete_events_by_user_calendar_id(user_calendar.id)
            else:
                if to_delete:
                    await self.calendar_repo.delete_events_by_google_ids(to_delete, user_calendar_id=user_calendar.id)
                if missing_google_ids:
                    await self.calendar_repo.delete_events_by_google_ids(
                        list(missing_google_ids), user_calendar_id=user_calendar.id
                    )
                await self.calendar_repo.delete_events_before(user_calendar.id, window_start)
                await self.calendar_repo.delete_events_after(user_calendar.id, window_end)

            await self.calendar_repo.upsert_events(to_upsert, attendees)

            if master_events_to_upsert:
                await self.calendar_repo.upsert_events(master_events_to_upsert, None)

            sync_token_update = use_sync_token if use_sync_token is not None else metadata.sync_token
            await self.calendar_repo.update_sync_state(
                user_calendar_id=user_calendar.id,
                sync_token=sync_token_update,
                sync_status=CalendarSyncStatusEnum.SUCCESS,
                last_sync_at=datetime.now(timezone.utc),
                sync_error=None,
            )

        return {
            "user_calendar_id": str(user_calendar.id),
            "db_count_since_first": db_count,
            "api_count_since_first": api_count,
            "fallback_full_fetch": fallback_used,
        }
