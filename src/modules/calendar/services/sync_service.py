from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.transaction import atomic
from src.core.exceptions import ServiceException
from src.modules.calendar.client import StaleSyncTokenError
from src.modules.calendar.clients.google_gateway import GoogleCalendarGateway
from src.modules.calendar.domain.event_mapper import GoogleEventMapper
from src.modules.calendar.domain.sync_window import compute_sync_window
from src.modules.calendar.models import CalendarEvent, OrganizationMemberCalendar, UserCalendar
from src.modules.calendar.repository import CalendarRepository
from src.modules.calendar.services.token_service import GoogleTokenService, TokenInvalidError
from src.modules.enums import CalendarSyncStatusEnum

logger = logging.getLogger(__name__)

MIN_EXPECTED_PARSED_EVENTS = 5
SUSPICIOUS_RAW_EVENT_COUNT = 20


class CalendarSyncEngine:
    MASTER_EVENT_CONCURRENCY = 3

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

    # TODO: [Webhooks TTL] Implement auto-renewal for Google Calendar webhooks (7-day limit).
    #  Currently, webhooks are only renewed on user login (via ensure_calendar_health).
    #  If a user doesn't log in for 8+ days, Google will stop sending push notifications.

    async def synchronize_calendar(self, calendar_id: uuid.UUID, check_type: str = "incremental") -> None:
        org_calendar = await self.calendar_repo.get_calendar(calendar_id)
        if not org_calendar:
            raise ServiceException("Calendar not found", status_code=404)

        try:
            await self._execute_sync(org_calendar, check_type=check_type)
        except StaleSyncTokenError:
            logger.warning(f"Stale token for {calendar_id}, performing safe full resync")
            await self._safe_full_resync(org_calendar)
        except Exception as exc:
            logger.error(f"Sync failed for {calendar_id}: {exc}")
            await self.token_service.mark_sync_status(
                org_calendar.user_calendar.id, CalendarSyncStatusEnum.FAILED, sync_error=str(exc)
            )
            raise

    async def synchronize_calendar_by_user_calendar_id(
        self, user_calendar_id: uuid.UUID, check_type: str = "incremental"
    ) -> None:
        """Synchronize calendar by user_calendar_id. Used for webhooks."""
        org_calendar = await self.calendar_repo.get_calendar_by_user_calendar_id(user_calendar_id)
        if not org_calendar:
            logger.warning(f"No OrganizationMemberCalendar found for user_calendar_id {user_calendar_id}")
            return

        try:
            await self._execute_sync(org_calendar, check_type=check_type)
        except StaleSyncTokenError:
            logger.warning(f"Stale token for user_calendar {user_calendar_id}, performing safe full resync")
            await self._safe_full_resync(org_calendar)
        except Exception as exc:
            logger.error(f"Sync failed for user_calendar {user_calendar_id}: {exc}")
            await self.token_service.mark_sync_status(user_calendar_id, CalendarSyncStatusEnum.FAILED, sync_error=str(exc))
            raise

    async def _execute_sync(
        self,
        org_calendar: OrganizationMemberCalendar,
        *,
        check_type: str,
    ) -> None:
        user_calendar = org_calendar.user_calendar

        async with CalendarRepository.sync_lock(user_calendar.id) as acquired:
            if not acquired:
                logger.warning(f"Sync already in progress for user calendar {user_calendar.id}, skipping")
                return

            async with atomic(self.session):
                metadata = await self.calendar_repo.ensure_sync_state(user_calendar.id, with_lock=True)
                await self.token_service.mark_sync_status(user_calendar.id, CalendarSyncStatusEnum.IN_PROGRESS)

            credentials = await self.token_service.get_valid_credentials(user_calendar)

            use_sync_token = metadata.sync_token if check_type != "full" else None
            if use_sync_token is None:
                earliest = await self.calendar_repo.get_earliest_event_start(user_calendar.id)
                time_min, time_max = compute_sync_window(earliest)
            else:
                time_min, time_max = None, None

            try:
                events, next_sync_token, credentials = await self.gateway.list_events_with_retry(
                    credentials,
                    user_calendar,
                    sync_token=use_sync_token,
                    full_sync=use_sync_token is None,
                    time_min=time_min,
                    time_max=time_max,
                )
            except TokenInvalidError:
                logger.warning("Token invalid for user_calendar %s during _execute_sync", user_calendar.id)
                await self.token_service.mark_sync_status(
                    user_calendar.id, CalendarSyncStatusEnum.FAILED, sync_error="token_invalid"
                )
                return

            to_delete, to_upsert, attendees = GoogleEventMapper.process_events_payload(
                events, user_calendar.id, metadata.timezone
            )

            # Guard: Don't delete if we got no events to upsert (possible API/parsing error)
            if not to_upsert and events:
                logger.error(
                    f"All {len(events)} events failed to parse for user_calendar {user_calendar.id}, "
                    "skipping sync to prevent data loss"
                )
                # Mark as failed and clear sync_token to force full sync next time
                async with atomic(self.session):
                    await self.calendar_repo.update_sync_state(
                        user_calendar_id=user_calendar.id,
                        sync_token=None,
                        sync_status=CalendarSyncStatusEnum.FAILED,
                        sync_error="all_events_parse_failed",
                    )
                return

            # Warn if suspiciously few events parsed during full sync
            if (
                use_sync_token is None
                and len(to_upsert) < MIN_EXPECTED_PARSED_EVENTS
                and len(events) > SUSPICIOUS_RAW_EVENT_COUNT
            ):
                logger.warning(
                    f"Full sync for user_calendar {user_calendar.id}: only {len(to_upsert)}/{len(events)} "
                    "events parsed successfully, possible parsing issue"
                )

            google_event_ids_in_upsert = {event.get("google_event_id") for event in to_upsert if event.get("google_event_id")}
            master_events_to_upsert = await self.get_master_events_to_upsert(
                events,
                credentials,
                user_calendar,
                metadata.timezone,
                google_event_ids_in_upsert,
            )

            google_ids_seen: set[str] = {
                event.get("google_event_id") for event in to_upsert + master_events_to_upsert if event.get("google_event_id")
            }
            missing_google_ids: set[str] = set()
            if use_sync_token is None:
                existing_google_ids = await self.calendar_repo.get_google_event_ids(
                    user_calendar.id, start_dt=time_min, end_dt=time_max
                )
                missing_google_ids = existing_google_ids - google_ids_seen - set(to_delete)

            async with atomic(self.session):
                if to_delete:
                    await self.calendar_repo.delete_events_by_google_ids(to_delete, user_calendar_id=user_calendar.id)
                if missing_google_ids:
                    await self.calendar_repo.delete_events_by_google_ids(
                        list(missing_google_ids), user_calendar_id=user_calendar.id
                    )
                if use_sync_token is None and time_min is not None:
                    await self.calendar_repo.delete_events_before(user_calendar.id, time_min)
                if use_sync_token is None and time_max is not None:
                    await self.calendar_repo.delete_events_after(user_calendar.id, time_max)
                await self.calendar_repo.upsert_events(to_upsert, attendees)

                if master_events_to_upsert:
                    await self.calendar_repo.upsert_events(master_events_to_upsert, None)

                sync_token_update = next_sync_token  # Don't fall back to stale token; None forces full sync next time
                await self.calendar_repo.update_sync_state(
                    user_calendar_id=user_calendar.id,
                    sync_token=sync_token_update,
                    sync_status=CalendarSyncStatusEnum.SUCCESS,
                    last_sync_at=datetime.now(timezone.utc),
                    sync_error=None,
                )

    async def _safe_full_resync(self, org_calendar: OrganizationMemberCalendar) -> None:
        user_calendar = org_calendar.user_calendar

        async with CalendarRepository.sync_lock(user_calendar.id) as acquired:
            if not acquired:
                logger.warning(f"Sync lock not available for {user_calendar.id}, skipping safe resync")
                return

            async with atomic(self.session):
                metadata = await self.calendar_repo.ensure_sync_state(user_calendar.id, with_lock=True)
                await self.token_service.mark_sync_status(user_calendar.id, CalendarSyncStatusEnum.IN_PROGRESS)

            credentials = await self.token_service.get_valid_credentials(user_calendar)

            earliest = await self.calendar_repo.get_earliest_event_start(user_calendar.id)
            time_min, time_max = compute_sync_window(earliest)

            try:
                events, next_sync_token, credentials = await self.gateway.list_events_with_retry(
                    credentials,
                    user_calendar,
                    sync_token=None,
                    full_sync=True,
                    time_min=time_min,
                    time_max=time_max,
                )
            except TokenInvalidError:
                logger.warning("Token invalid for user_calendar %s during safe resync", user_calendar.id)
                await self.token_service.mark_sync_status(
                    user_calendar.id, CalendarSyncStatusEnum.FAILED, sync_error="token_invalid"
                )
                return

            _, to_upsert, attendees = GoogleEventMapper.process_events_payload(events, user_calendar.id, metadata.timezone)

            # Guard: Don't delete if we got no events to upsert (possible API/parsing error)
            if not to_upsert and events:
                logger.error(
                    f"All {len(events)} events failed to parse during safe resync for user_calendar {user_calendar.id}, "
                    "skipping to prevent data loss"
                )
                async with atomic(self.session):
                    await self.calendar_repo.update_sync_state(
                        user_calendar_id=user_calendar.id,
                        sync_token=None,
                        sync_status=CalendarSyncStatusEnum.FAILED,
                        sync_error="safe_resync_all_events_parse_failed",
                    )
                return

            google_event_ids_in_upsert = {event.get("google_event_id") for event in to_upsert if event.get("google_event_id")}
            master_events_to_upsert = await self.get_master_events_to_upsert(
                events,
                credentials,
                user_calendar,
                metadata.timezone,
                google_event_ids_in_upsert,
            )

            async with atomic(self.session):
                await self.calendar_repo.delete_events_by_user_calendar_id(user_calendar.id)
                await self.calendar_repo.upsert_events(to_upsert, attendees)

                if master_events_to_upsert:
                    await self.calendar_repo.upsert_events(master_events_to_upsert, None)

                sync_token_update = next_sync_token  # Don't fall back to stale token; None forces full sync next time
                await self.calendar_repo.update_sync_state(
                    user_calendar_id=user_calendar.id,
                    sync_token=sync_token_update,
                    sync_status=CalendarSyncStatusEnum.SUCCESS,
                    last_sync_at=datetime.now(timezone.utc),
                    sync_error=None,
                )

    async def get_master_events_to_upsert(
        self,
        events: list[dict],
        credentials: Credentials,
        user_calendar: UserCalendar,
        default_tz: str,
        exclude_google_event_ids: set[str],
    ) -> list[dict]:
        """Get master events that need to be upserted."""
        master_event_ids = {event.get("recurringEventId") for event in events if event.get("recurringEventId")}
        if not master_event_ids:
            return []
        logger.debug(f"Master events to sync: {len(master_event_ids)}")
        return await self._fetch_master_events(
            master_event_ids=list(master_event_ids),
            credentials=credentials,
            user_calendar=user_calendar,
            default_tz=default_tz,
            exclude_google_event_ids=exclude_google_event_ids,
        )

    async def _fetch_master_events(
        self,
        master_event_ids: list[str],
        credentials: Credentials,
        user_calendar: UserCalendar,
        default_tz: str,
        exclude_google_event_ids: set[str] | None = None,
    ) -> list[dict]:
        synced_at = datetime.now(timezone.utc)

        statement = select(CalendarEvent.google_event_id).where(
            CalendarEvent.google_event_id.in_(master_event_ids),
            CalendarEvent.user_calendar_id == user_calendar.id,
        )
        result = await self.session.execute(statement)
        existing_ids = {row[0] for row in result.all()}

        exclude_set = existing_ids.copy()
        if exclude_google_event_ids:
            exclude_set.update(exclude_google_event_ids)

        ids_to_fetch = [eid for eid in master_event_ids if eid not in exclude_set]

        if not ids_to_fetch:
            logger.debug(f"_fetch_master_events: All {len(master_event_ids)} master events already exist in DB")
            return []

        logger.info(f"_fetch_master_events: Fetching {len(ids_to_fetch)} master events from Google Calendar API")

        semaphore = asyncio.Semaphore(self.MASTER_EVENT_CONCURRENCY)
        creds_lock = asyncio.Lock()
        current_creds = credentials

        async def fetch_one(event_id: str) -> dict | None:
            nonlocal current_creds
            async with semaphore:
                try:
                    async with creds_lock:
                        creds_to_use = current_creds

                    event_data, new_creds = await self.gateway.get_event_with_retry(creds_to_use, user_calendar, event_id)

                    if new_creds is not creds_to_use:
                        async with creds_lock:
                            current_creds = new_creds

                    if event_data:
                        mapped, _ = GoogleEventMapper.map_event(event_data, user_calendar.id, default_tz, synced_at)
                        return mapped
                except TokenInvalidError:
                    return None
                except Exception as e:
                    logger.warning(f"_fetch_master_events: Failed to fetch master event {event_id}: {e}")
                return None

        results = await asyncio.gather(*[fetch_one(eid) for eid in ids_to_fetch])
        master_events_to_upsert = [evt for evt in results if evt is not None]

        logger.info(f"_fetch_master_events: Successfully fetched {len(master_events_to_upsert)} master events")
        return master_events_to_upsert
