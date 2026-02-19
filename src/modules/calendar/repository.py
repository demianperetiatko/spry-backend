from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, delete, func, or_, select, text
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

    async def upsert_events(self, events: list[dict], attendees_by_event: dict | None = None, chunk_size: int = 400) -> None:
        if not events:
            return

        attendees_by_event = attendees_by_event or {}

        for i in range(0, len(events), chunk_size):
            batch = events[i : i + chunk_size]

            stmt = insert(CalendarEvent).values(batch)
            update_cols = {c.name: getattr(stmt.excluded, c.name) for c in stmt.table.c if c.name not in {"id", "created_at"}}
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_=update_cols,
            )
            await self.session.execute(stmt)
            await self.session.flush()

            if attendees_by_event:
                batch_google_ids = {item.get("google_event_id") for item in batch if item.get("google_event_id")}
                batch_attendees = {gid: attendees_by_event[gid] for gid in batch_google_ids if gid in attendees_by_event}
                if batch_attendees:
                    await self._replace_attendees(batch_attendees)

    async def _replace_attendees(self, attendees_by_event: dict[str, list[dict]]) -> None:
        google_event_ids = list(attendees_by_event.keys())
        if not google_event_ids:
            return

        stmt = select(CalendarEvent.id, CalendarEvent.google_event_id).where(CalendarEvent.google_event_id.in_(google_event_ids))
        result = await self.session.execute(stmt)
        google_id_to_uuid = {row[1]: row[0] for row in result.all()}

        if not google_id_to_uuid:
            return

        event_uuids = list(google_id_to_uuid.values())
        existing_stmt = select(CalendarEventAttendee).where(CalendarEventAttendee.calendar_event_id.in_(event_uuids))
        existing_result = await self.session.execute(existing_stmt)
        existing_attendees = existing_result.scalars().all()

        existing_by_event: dict[uuid.UUID, set[str]] = {}
        for att in existing_attendees:
            if att.calendar_event_id not in existing_by_event:
                existing_by_event[att.calendar_event_id] = set()
            existing_by_event[att.calendar_event_id].add(att.email)

        new_by_event: dict[uuid.UUID, set[str]] = {}
        rows_to_insert = []
        for google_id, atts in attendees_by_event.items():
            event_uuid = google_id_to_uuid.get(google_id)
            if not event_uuid:
                continue
            new_by_event[event_uuid] = set()
            for att in atts:
                email = att.get("email")
                if email:
                    new_by_event[event_uuid].add(email)
                    rows_to_insert.append({"calendar_event_id": event_uuid, **att})

        to_delete = []
        for event_uuid, existing_emails in existing_by_event.items():
            new_emails = new_by_event.get(event_uuid, set())
            for email in existing_emails - new_emails:
                to_delete.append((event_uuid, email))

        if to_delete:
            chunk_size = 100
            for i in range(0, len(to_delete), chunk_size):
                chunk = to_delete[i : i + chunk_size]
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
        """Batch fetch calendars for multiple members in a single query."""
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

    async def acquire_sync_lock(self, user_calendar_id: uuid.UUID) -> bool:
        lock_key = self._build_lock_key(user_calendar_id)
        result = await self.session.execute(text("SELECT pg_try_advisory_xact_lock(:lock_key)").bindparams(lock_key=lock_key))
        return bool(result.scalar())

    async def get_google_event_ids(
        self,
        user_calendar_id: uuid.UUID,
        start_dt: datetime | None = None,
        end_dt: datetime | None = None,
        batch_size: int = 10000,
    ) -> set[str]:
        base_stmt = select(CalendarEvent.google_event_id).where(CalendarEvent.user_calendar_id == user_calendar_id)
        if start_dt:
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            base_stmt = base_stmt.where(CalendarEvent.start_datetime >= start_dt)
        if end_dt:
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            base_stmt = base_stmt.where(CalendarEvent.start_datetime <= end_dt)

        result_set: set[str] = set()
        offset = 0

        while True:
            stmt = base_stmt.limit(batch_size).offset(offset)
            result = await self.session.execute(stmt)
            rows = result.all()
            if not rows:
                break
            result_set.update(row[0] for row in rows if row[0])
            if len(rows) < batch_size:
                break
            offset += batch_size

        return result_set

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
