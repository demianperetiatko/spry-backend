from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, delete, or_, select, text, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from src.modules.calendar.models import (
    CalendarCacheMetadata,
    CalendarEvent,
    CalendarEventAttendee,
    OrganizationMemberCalendar,
    UserCalendar,
)
from src.modules.enums import CalendarSyncStatusEnum, CalendarTypeEnum
from src.modules.organization_member.model import OrganizationMember
from src.modules.user.model import UserAccessInfo


class CalendarRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _build_lock_key(user_calendar_id: uuid.UUID) -> int:
        return user_calendar_id.int % (2**63 - 1)

    async def get_user_access_info(self, user_id: uuid.UUID) -> UserAccessInfo | None:
        stmt = select(UserAccessInfo).where(UserAccessInfo.user_id == user_id).limit(1)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_calendar(self, calendar_id: uuid.UUID) -> OrganizationMemberCalendar | None:
        statement = (
            select(OrganizationMemberCalendar)
            .options(
                joinedload(OrganizationMemberCalendar.member).joinedload(OrganizationMember.user),
                joinedload(OrganizationMemberCalendar.user_calendar).joinedload(UserCalendar.user_access_info),
                joinedload(OrganizationMemberCalendar.user_calendar).joinedload(UserCalendar.cache_metadata),
            )
            .where(OrganizationMemberCalendar.id == calendar_id)
            .limit(1)
        )
        result = await self.session.execute(statement)
        return result.scalars().first()

    async def get_metadata_by_channel_id(self, channel_id: str) -> CalendarCacheMetadata | None:
        statement = select(CalendarCacheMetadata).where(CalendarCacheMetadata.channel_id == channel_id).limit(1)
        result = await self.session.execute(statement)
        return result.scalars().first()

    async def get_user_calendar_by_email(self, user_access_info_id: uuid.UUID, calendar_email: str) -> UserCalendar | None:
        statement = (
            select(UserCalendar)
            .where(
                UserCalendar.user_access_info_id == user_access_info_id,
                UserCalendar.calendar_email == calendar_email,
            )
            .limit(1)
        )
        result = await self.session.execute(statement)
        return result.scalars().first()

    async def get_sync_state(self, user_calendar_id: uuid.UUID) -> CalendarCacheMetadata | None:
        statement = select(CalendarCacheMetadata).where(CalendarCacheMetadata.user_calendar_id == user_calendar_id).limit(1)
        result = await self.session.execute(statement)
        return result.scalars().first()

    async def ensure_sync_state(self, user_calendar_id: uuid.UUID, with_lock: bool = False) -> CalendarCacheMetadata:
        if with_lock:
            statement = (
                select(CalendarCacheMetadata)
                .where(CalendarCacheMetadata.user_calendar_id == user_calendar_id)
                .with_for_update()
                .limit(1)
            )
            result = await self.session.execute(statement)
            metadata = result.scalars().first()
        else:
            metadata = await self.get_sync_state(user_calendar_id)

        if metadata:
            return metadata

        metadata = CalendarCacheMetadata(
            user_calendar_id=user_calendar_id,
            last_sync_at=datetime.now(timezone.utc),
            sync_status=CalendarSyncStatusEnum.SUCCESS,
        )
        self.session.add(metadata)
        await self.session.flush()
        return metadata

    # Allowlist of fields that can be updated via update_sync_state
    SYNC_STATE_UPDATABLE_FIELDS = frozenset(
        {
            "timezone",
            "last_sync_at",
            "sync_status",
            "sync_error",
            "sync_token",
            "channel_id",
            "resource_id",
            "channel_expiration",
        }
    )

    async def update_sync_state(
        self,
        user_calendar_id: uuid.UUID,
        **kwargs,
    ) -> CalendarCacheMetadata:
        metadata = await self.ensure_sync_state(user_calendar_id)

        if "channel_expiration" in kwargs:
            expiration = kwargs["channel_expiration"]
            if expiration is not None and expiration.tzinfo is None:
                kwargs["channel_expiration"] = expiration.replace(tzinfo=timezone.utc)

        for key, value in kwargs.items():
            if key not in self.SYNC_STATE_UPDATABLE_FIELDS:
                raise ValueError(f"Field '{key}' is not allowed in update_sync_state")
            if value is not None:
                setattr(metadata, key, value)

        # Handle explicit None values for nullable fields
        if "channel_id" in kwargs and kwargs["channel_id"] is None:
            metadata.channel_id = None
        if "resource_id" in kwargs and kwargs["resource_id"] is None:
            metadata.resource_id = None
        if "channel_expiration" in kwargs and kwargs["channel_expiration"] is None:
            metadata.channel_expiration = None
        if "sync_token" in kwargs and kwargs["sync_token"] is None:
            metadata.sync_token = None
        if "sync_error" in kwargs and kwargs["sync_error"] is None:
            metadata.sync_error = None

        return metadata

    async def upsert_events(
        self,
        events: list[dict],
        attendees_by_event: dict[str, list[dict]] | None = None,
        chunk_size: int = 400,
    ) -> None:
        if not events:
            return

        attendees_by_event = attendees_by_event or {}

        for i in range(0, len(events), chunk_size):
            batch = events[i : i + chunk_size]

            stmt = insert(CalendarEvent).values(batch)
            update_cols = {
                c.name: getattr(stmt.excluded, c.name)
                for c in stmt.table.c
                if c.name not in {"id", "created_at", "user_calendar_id", "google_event_id"}
            }
            stmt = stmt.on_conflict_do_update(
                constraint="uq_event_calendar",
                set_=update_cols,
            ).returning(CalendarEvent.id, CalendarEvent.google_event_id)

            result = await self.session.execute(stmt)
            google_id_to_db_id: dict[str, uuid.UUID] = {row[1]: row[0] for row in result.all()}
            await self.session.flush()

            if attendees_by_event:
                batch_google_ids = {item.get("google_event_id") for item in batch if item.get("google_event_id")}
                batch_attendees = {gid: attendees_by_event[gid] for gid in batch_google_ids if gid in attendees_by_event}
                if batch_attendees:
                    await self._replace_attendees(batch_attendees, google_id_to_db_id)

    async def _replace_attendees(
        self,
        attendees_by_event: dict[str, list[dict]],
        google_id_to_db_id: dict[str, uuid.UUID],
    ) -> None:
        if not attendees_by_event or not google_id_to_db_id:
            return

        resolved_event_uuids: list[uuid.UUID] = []
        for google_id in attendees_by_event:
            db_id = google_id_to_db_id.get(google_id)
            if db_id:
                resolved_event_uuids.append(db_id)

        if not resolved_event_uuids:
            return

        existing_stmt = select(CalendarEventAttendee).where(CalendarEventAttendee.calendar_event_id.in_(resolved_event_uuids))
        existing_result = await self.session.execute(existing_stmt)
        existing_attendees = existing_result.scalars().all()

        existing_by_event: dict[uuid.UUID, set[str]] = {}
        for att in existing_attendees:
            if att.calendar_event_id not in existing_by_event:
                existing_by_event[att.calendar_event_id] = set()
            existing_by_event[att.calendar_event_id].add(att.email)

        new_by_event: dict[uuid.UUID, set[str]] = {}
        rows_to_insert: list[dict] = []
        for google_id, atts in attendees_by_event.items():
            event_uuid = google_id_to_db_id.get(google_id)
            if not event_uuid:
                continue
            new_by_event[event_uuid] = set()
            for att in atts:
                email = att.get("email")
                if email:
                    new_by_event[event_uuid].add(email)
                    rows_to_insert.append({"calendar_event_id": event_uuid, **att})

        to_delete: list[tuple[uuid.UUID, str]] = []
        for event_uuid, existing_emails in existing_by_event.items():
            new_emails = new_by_event.get(event_uuid, set())
            for email in existing_emails - new_emails:
                to_delete.append((event_uuid, email))

        if to_delete:
            att_chunk_size = 100
            for j in range(0, len(to_delete), att_chunk_size):
                chunk = to_delete[j : j + att_chunk_size]
                conditions = [
                    and_(
                        CalendarEventAttendee.calendar_event_id == event_uuid,
                        CalendarEventAttendee.email == email,
                    )
                    for event_uuid, email in chunk
                ]
                await self.session.execute(delete(CalendarEventAttendee).where(or_(*conditions)))

        if rows_to_insert:
            stmt = insert(CalendarEventAttendee).values(rows_to_insert)
            update_cols = {
                c.name: getattr(stmt.excluded, c.name)
                for c in stmt.table.c
                if c.name not in {"id", "created_at", "calendar_event_id", "email"}
            }
            stmt = stmt.on_conflict_do_update(
                constraint="idx_event_attendee_unique",
                set_=update_cols,
            )
            await self.session.execute(stmt)

    async def delete_events_by_google_ids(self, google_ids: list[str], user_calendar_id: uuid.UUID | None = None) -> None:
        if not google_ids:
            return
        stmt = delete(CalendarEvent).where(CalendarEvent.google_event_id.in_(google_ids))
        if user_calendar_id:
            stmt = stmt.where(CalendarEvent.user_calendar_id == user_calendar_id)
        await self.session.execute(stmt)

    async def delete_events_by_user_calendar_id(self, user_calendar_id: uuid.UUID) -> None:
        stmt = delete(CalendarEvent).where(CalendarEvent.user_calendar_id == user_calendar_id)
        await self.session.execute(stmt)

    async def get_earliest_event_start(self, user_calendar_id: uuid.UUID) -> datetime | None:
        stmt = (
            select(CalendarEvent.start_datetime)
            .where(CalendarEvent.user_calendar_id == user_calendar_id)
            .order_by(CalendarEvent.start_datetime.asc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_events_since(self, user_calendar_id: uuid.UUID, start_dt: datetime | None = None) -> int:
        stmt = select(func.count()).where(CalendarEvent.user_calendar_id == user_calendar_id)
        if start_dt:
            stmt = stmt.where(CalendarEvent.start_datetime >= start_dt)
        result = await self.session.execute(stmt)
        count_val = result.scalar()
        return int(count_val or 0)

    async def update_user_access_info_tokens(
        self, info: UserAccessInfo, access_token: str, access_token_expiry: datetime | None
    ) -> None:
        if access_token_expiry and access_token_expiry.tzinfo is None:
            access_token_expiry = access_token_expiry.replace(tzinfo=timezone.utc)

        info.access_token = access_token
        info.access_token_expiry = access_token_expiry
        self.session.add(info)

    async def create_calendar_for_member(
        self,
        organization_member_id: uuid.UUID,
        user_access_info_id: uuid.UUID,
        calendar_email: str,
        is_primary: bool = False,
    ) -> OrganizationMemberCalendar:
        stmt_uc_select = (
            select(UserCalendar)
            .where(
                UserCalendar.user_access_info_id == user_access_info_id,
                UserCalendar.calendar_email == calendar_email,
            )
            .limit(1)
        )
        uc = (await self.session.execute(stmt_uc_select)).scalars().first()

        if not uc:
            user_calendar_values = {
                "user_access_info_id": user_access_info_id,
                "calendar_email": calendar_email,
                "type": CalendarTypeEnum.GOOGLE,
                "is_primary": is_primary,
            }

            stmt_uc = insert(UserCalendar).values(user_calendar_values)
            stmt_uc = stmt_uc.on_conflict_do_update(
                constraint="uq_user_calendar_email",
                set_={"is_primary": stmt_uc.excluded.is_primary},
            ).returning(UserCalendar)

            try:
                # Use savepoint to isolate potential IntegrityError
                async with self.session.begin_nested():
                    result = await self.session.execute(stmt_uc)
                    uc = result.scalar_one()
            except IntegrityError:
                # Savepoint rolled back automatically, re-query to get existing record
                uc = (await self.session.execute(stmt_uc_select)).scalars().first()
                if not uc:
                    raise

        stmt_omc = (
            select(OrganizationMemberCalendar)
            .where(
                OrganizationMemberCalendar.organization_member_id == organization_member_id,
                OrganizationMemberCalendar.user_calendar_id == uc.id,
            )
            .limit(1)
        )
        omc = (await self.session.execute(stmt_omc)).scalars().first()

        if not omc:
            omc = OrganizationMemberCalendar(
                organization_member_id=organization_member_id,
                user_calendar_id=uc.id,
            )
            self.session.add(omc)
            await self.session.flush()

        return omc

    async def get_calendars_for_member(self, member_id: uuid.UUID) -> list[OrganizationMemberCalendar]:
        stmt = (
            select(OrganizationMemberCalendar)
            .where(OrganizationMemberCalendar.organization_member_id == member_id)
            .options(joinedload(OrganizationMemberCalendar.user_calendar))
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_calendars_for_members(self, member_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[OrganizationMemberCalendar]]:
        if not member_ids:
            return {}

        stmt = (
            select(OrganizationMemberCalendar)
            .where(OrganizationMemberCalendar.organization_member_id.in_(member_ids))
            .options(joinedload(OrganizationMemberCalendar.user_calendar))
        )
        result = await self.session.execute(stmt)
        calendars = result.scalars().all()

        # Group by member_id
        calendars_by_member: dict[uuid.UUID, list[OrganizationMemberCalendar]] = {}
        for calendar in calendars:
            member_id = calendar.organization_member_id
            if member_id not in calendars_by_member:
                calendars_by_member[member_id] = []
            calendars_by_member[member_id].append(calendar)

        return calendars_by_member

    async def get_calendar_by_user_calendar_id(self, user_calendar_id: uuid.UUID) -> OrganizationMemberCalendar | None:
        statement = (
            select(OrganizationMemberCalendar)
            .options(
                joinedload(OrganizationMemberCalendar.member).joinedload(OrganizationMember.user),
                joinedload(OrganizationMemberCalendar.user_calendar).joinedload(UserCalendar.user_access_info),
                joinedload(OrganizationMemberCalendar.user_calendar).joinedload(UserCalendar.cache_metadata),
            )
            .where(OrganizationMemberCalendar.user_calendar_id == user_calendar_id)
            .limit(1)
        )
        result = await self.session.execute(statement)
        return result.scalars().first()

    async def get_user_calendar_ids_for_member(
        self,
        organization_member_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        statement = select(OrganizationMemberCalendar.user_calendar_id).where(
            OrganizationMemberCalendar.organization_member_id == organization_member_id
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    @staticmethod
    async def acquire_sync_lock(session: AsyncSession, user_calendar_id: uuid.UUID) -> None:
        lock_key = CalendarRepository._build_lock_key(user_calendar_id)
        await session.execute(text("SELECT pg_advisory_xact_lock(:lock_key)").bindparams(lock_key=lock_key))

    async def delete_events_before(self, user_calendar_id: uuid.UUID, before_dt: datetime) -> None:
        if before_dt.tzinfo is None:
            before_dt = before_dt.replace(tzinfo=timezone.utc)
        stmt = delete(CalendarEvent).where(
            CalendarEvent.user_calendar_id == user_calendar_id, CalendarEvent.start_datetime < before_dt
        )
        await self.session.execute(stmt)

    async def delete_events_after(self, user_calendar_id: uuid.UUID, after_dt: datetime) -> None:
        if after_dt.tzinfo is None:
            after_dt = after_dt.replace(tzinfo=timezone.utc)
        stmt = delete(CalendarEvent).where(
            CalendarEvent.user_calendar_id == user_calendar_id, CalendarEvent.start_datetime > after_dt
        )
        await self.session.execute(stmt)

    async def delete_orphaned_events(
        self,
        user_calendar_id: uuid.UUID,
        google_event_ids_from_api: list[str],
        time_min: datetime | None = None,
        time_max: datetime | None = None,
    ) -> int:
        if not google_event_ids_from_api:
            return 0

        if time_min and time_min.tzinfo is None:
            time_min = time_min.replace(tzinfo=timezone.utc)
        if time_max and time_max.tzinfo is None:
            time_max = time_max.replace(tzinfo=timezone.utc)

        delete_stmt = text("""
            DELETE FROM calendar_events
            WHERE user_calendar_id = :uc_id
              AND google_event_id NOT IN (SELECT UNNEST(CAST(:api_ids AS varchar[])))
              AND (CAST(:time_min AS timestamptz) IS NULL OR start_datetime >= :time_min)
              AND (CAST(:time_max AS timestamptz) IS NULL OR start_datetime <= :time_max)
        """)

        result = await self.session.execute(
            delete_stmt,
            {
                "uc_id": user_calendar_id,
                "api_ids": google_event_ids_from_api,
                "time_min": time_min,
                "time_max": time_max,
            },
        )
        return result.rowcount
