from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.transaction import atomic
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
DATA_LOSS_GUARD_THRESHOLD = 0.1


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

    async def synchronize_calendar(self, calendar_id: uuid.UUID, check_type: str = "incremental") -> None:
        org_calendar = await self.calendar_repo.get_calendar(calendar_id)
        if not org_calendar:
            logger.warning(f"Calendar {calendar_id} not found")
            return

        if check_type == "full":
            await self._run_full_sync(org_calendar)
        else:
            await self._run_incremental_sync(org_calendar)

    async def synchronize_calendar_by_user_calendar_id(
        self, user_calendar_id: uuid.UUID, check_type: str = "incremental"
    ) -> None:
        org_calendar = await self.calendar_repo.get_calendar_by_user_calendar_id(user_calendar_id)
        if not org_calendar:
            logger.warning(f"No OrganizationMemberCalendar found for user_calendar_id {user_calendar_id}")
            return

        if check_type == "full":
            await self._run_full_sync(org_calendar)
        else:
            await self._run_incremental_sync(org_calendar)

    async def _run_incremental_sync(self, org_calendar: OrganizationMemberCalendar) -> None:
        user_calendar = org_calendar.user_calendar
        metadata = await self.calendar_repo.get_sync_state(user_calendar.id)

        if not metadata or not metadata.sync_token:
            logger.info(f"No sync token for {user_calendar.id}, falling back to full sync")
            await self._run_full_sync(org_calendar)
            return

        # Phase 1: Fetch from Google (no lock, no transaction)
        credentials = await self.token_service.get_valid_credentials(user_calendar)

        try:
            events, next_sync_token, credentials = await self.gateway.list_events_with_retry(
                credentials,
                user_calendar,
                sync_token=metadata.sync_token,
                full_sync=False,
                time_min=None,
                time_max=None,
            )
        except StaleSyncTokenError:
            logger.warning(f"Stale token for {user_calendar.id}, falling back to full sync")
            await self._run_full_sync(org_calendar)
            return
        except TokenInvalidError:
            logger.warning(f"Token invalid for {user_calendar.id} during incremental sync")
            await self.token_service.mark_sync_status(user_calendar.id, CalendarSyncStatusEnum.FAILED, sync_error="token_invalid")
            return

        to_delete, to_upsert, attendees = GoogleEventMapper.process_events_payload(events, user_calendar.id, metadata.timezone)

        if not to_upsert and not to_delete:
            async with atomic(self.session):
                await CalendarRepository.acquire_sync_lock(self.session, user_calendar.id)
                await self.calendar_repo.update_sync_state(
                    user_calendar_id=user_calendar.id,
                    sync_token=next_sync_token,
                    sync_status=CalendarSyncStatusEnum.SUCCESS,
                    last_sync_at=datetime.now(timezone.utc),
                    sync_error=None,
                )
            return

        google_event_ids_in_upsert = {e.get("google_event_id") for e in to_upsert if e.get("google_event_id")}
        master_events = await self.get_master_events_to_upsert(
            events, credentials, user_calendar, metadata.timezone, google_event_ids_in_upsert
        )
        await self.propagate_recurrence_to_instances(to_upsert, master_events, user_calendar.id)

        async with atomic(self.session):
            await CalendarRepository.acquire_sync_lock(self.session, user_calendar.id)

            if to_delete:
                await self.calendar_repo.delete_events_by_google_ids(to_delete, user_calendar_id=user_calendar.id)

            await self.calendar_repo.upsert_events(to_upsert, attendees)

            if master_events:
                await self.calendar_repo.upsert_events(master_events, None)

            await self.calendar_repo.update_sync_state(
                user_calendar_id=user_calendar.id,
                sync_token=next_sync_token,
                sync_status=CalendarSyncStatusEnum.SUCCESS,
                last_sync_at=datetime.now(timezone.utc),
                sync_error=None,
            )

    async def _run_full_sync(self, org_calendar: OrganizationMemberCalendar) -> None:
        user_calendar = org_calendar.user_calendar

        try:
            credentials = await self.token_service.get_valid_credentials(user_calendar)
        except TokenInvalidError:
            logger.warning(f"Token invalid for {user_calendar.id} during full sync credential fetch")
            await self.token_service.mark_sync_status(user_calendar.id, CalendarSyncStatusEnum.FAILED, sync_error="token_invalid")
            return

        metadata = await self.calendar_repo.ensure_sync_state(user_calendar.id)

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
            logger.warning(f"Token invalid for {user_calendar.id} during full sync")
            await self.token_service.mark_sync_status(user_calendar.id, CalendarSyncStatusEnum.FAILED, sync_error="token_invalid")
            return

        to_delete, to_upsert, attendees = GoogleEventMapper.process_events_payload(events, user_calendar.id, metadata.timezone)

        if not to_upsert and events:
            logger.error(f"All {len(events)} events failed to parse for {user_calendar.id}, skipping sync to prevent data loss")
            async with atomic(self.session):
                await self.calendar_repo.update_sync_state(
                    user_calendar_id=user_calendar.id,
                    sync_token=None,
                    sync_status=CalendarSyncStatusEnum.FAILED,
                    sync_error="all_events_parse_failed",
                )
            return

        if len(to_upsert) < MIN_EXPECTED_PARSED_EVENTS and len(events) > SUSPICIOUS_RAW_EVENT_COUNT:
            logger.warning(
                f"Full sync for {user_calendar.id}: only {len(to_upsert)}/{len(events)} "
                "events parsed successfully, possible parsing issue"
            )

        google_event_ids_in_upsert = {e.get("google_event_id") for e in to_upsert if e.get("google_event_id")}
        master_events = await self.get_master_events_to_upsert(
            events, credentials, user_calendar, metadata.timezone, google_event_ids_in_upsert
        )
        await self.propagate_recurrence_to_instances(to_upsert, master_events, user_calendar.id)

        all_api_google_ids: list[str] = [
            e.get("google_event_id") for e in to_upsert + master_events if e.get("google_event_id")
        ] + to_delete  # Cancelled IDs existed in the API response too

        async with atomic(self.session):
            await CalendarRepository.acquire_sync_lock(self.session, user_calendar.id)

            locked_count = await self.calendar_repo.count_events_since(user_calendar.id)
            if locked_count > SUSPICIOUS_RAW_EVENT_COUNT and len(to_upsert) < locked_count * DATA_LOSS_GUARD_THRESHOLD:
                logger.error(
                    f"Full sync for {user_calendar.id}: API returned {len(to_upsert)} events "
                    f"but DB has {locked_count}. Aborting to prevent data loss."
                )
                await self.calendar_repo.update_sync_state(
                    user_calendar_id=user_calendar.id,
                    sync_token=None,
                    sync_status=CalendarSyncStatusEnum.FAILED,
                    sync_error="full_sync_data_loss_guard",
                )
                return

            deleted_count = await self.calendar_repo.delete_orphaned_events(
                user_calendar.id,
                all_api_google_ids,
                time_min=time_min,
                time_max=time_max,
            )
            if deleted_count:
                logger.info(f"Full sync for {user_calendar.id}: deleted {deleted_count} orphaned events")

            if time_min:
                await self.calendar_repo.delete_events_before(user_calendar.id, time_min)
            if time_max:
                await self.calendar_repo.delete_events_after(user_calendar.id, time_max)

            if to_delete:
                await self.calendar_repo.delete_events_by_google_ids(to_delete, user_calendar_id=user_calendar.id)

            # Upsert with RETURNING → real DB IDs for attendees
            await self.calendar_repo.upsert_events(to_upsert, attendees)

            if master_events:
                await self.calendar_repo.upsert_events(master_events, None)

            await self.calendar_repo.update_sync_state(
                user_calendar_id=user_calendar.id,
                sync_token=next_sync_token,
                sync_status=CalendarSyncStatusEnum.SUCCESS,
                last_sync_at=datetime.now(timezone.utc),
                sync_error=None,
            )

    async def propagate_recurrence_to_instances(
        self,
        to_upsert: list[dict],
        master_events_to_upsert: list[dict],
        user_calendar_id: uuid.UUID,
    ) -> None:
        recurrence_map: dict[str, list[str]] = {}
        for master in master_events_to_upsert:
            gid = master.get("google_event_id")
            rec = master.get("recurrence")
            if gid and rec:
                recurrence_map[gid] = rec

        needed_ids = {
            evt["recurring_event_id"]
            for evt in to_upsert
            if evt.get("recurring_event_id") and evt["recurring_event_id"] not in recurrence_map
        }

        if needed_ids:
            stmt = select(CalendarEvent.google_event_id, CalendarEvent.recurrence).where(
                CalendarEvent.google_event_id.in_(list(needed_ids)),
                CalendarEvent.user_calendar_id == user_calendar_id,
                CalendarEvent.recurrence.isnot(None),
            )
            result = await self.session.execute(stmt)
            for gid, rec in result.all():
                recurrence_map[gid] = rec

        for evt in to_upsert:
            rid = evt.get("recurring_event_id")
            if rid and not evt.get("recurrence") and rid in recurrence_map:
                evt["recurrence"] = recurrence_map[rid]

    async def get_master_events_to_upsert(
        self,
        events: list[dict],
        credentials: Credentials,
        user_calendar: UserCalendar,
        default_tz: str,
        exclude_google_event_ids: set[str],
    ) -> list[dict]:
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
