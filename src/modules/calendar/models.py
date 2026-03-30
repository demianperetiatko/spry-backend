from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.session import Base
from src.modules.enums import (
    CalendarAttendeeResponseStatusEnum,
    CalendarEventStatusEnum,
    CalendarSyncStatusEnum,
    CalendarTypeEnum,
)

if TYPE_CHECKING:
    from src.modules.organization_member.model import OrganizationMember
    from src.modules.user.model import UserAccessInfo


class UserCalendar(Base):
    __tablename__ = "user_calendars"
    __table_args__ = (UniqueConstraint("user_access_info_id", "calendar_email", name="uq_user_calendar_email"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_access_info_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users_access_info.id", ondelete="CASCADE"),
        nullable=False,
    )
    calendar_email: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[CalendarTypeEnum] = mapped_column(nullable=False, default=CalendarTypeEnum.GOOGLE)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user_access_info: Mapped["UserAccessInfo"] = relationship("UserAccessInfo", back_populates="calendars")
    events: Mapped[list["CalendarEvent"]] = relationship(
        "CalendarEvent",
        back_populates="user_calendar",
        cascade="all, delete-orphan",
    )
    organization_calendars: Mapped[list["OrganizationMemberCalendar"]] = relationship(
        "OrganizationMemberCalendar",
        back_populates="user_calendar",
    )
    cache_metadata: Mapped["CalendarCacheMetadata"] = relationship(
        "CalendarCacheMetadata",
        back_populates="user_calendar",
        cascade="all, delete-orphan",
        uselist=False,
    )


class OrganizationMemberCalendar(Base):
    __tablename__ = "organization_member_calendars"
    __table_args__ = (UniqueConstraint("organization_member_id", "user_calendar_id", name="uq_org_member_user_calendar"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization_members.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_calendar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_calendars.id", ondelete="CASCADE"),
        nullable=False,
    )

    member: Mapped["OrganizationMember"] = relationship("OrganizationMember", back_populates="calendars")
    user_calendar: Mapped["UserCalendar"] = relationship("UserCalendar", back_populates="organization_calendars")


class CalendarCacheMetadata(Base):
    __tablename__ = "calendar_cache_metadata"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_calendar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_calendars.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    timezone: Mapped[str] = mapped_column(String(255), nullable=False, default="UTC")
    last_sync_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    sync_status: Mapped[CalendarSyncStatusEnum] = mapped_column(
        nullable=False,
        default=CalendarSyncStatusEnum.SUCCESS,
    )
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_token: Mapped[str | None] = mapped_column(String, nullable=True)
    channel_id: Mapped[str | None] = mapped_column(String, nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String, nullable=True)
    channel_expiration: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user_calendar: Mapped["UserCalendar"] = relationship(
        "UserCalendar",
        back_populates="cache_metadata",
    )


class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    __table_args__ = (
        UniqueConstraint("google_event_id", "user_calendar_id", name="uq_event_calendar"),
        Index("idx_calendar_events_date_range", "user_calendar_id", "start_datetime", "end_datetime"),
        Index("idx_events_synced_at", "synced_at"),
        Index("idx_calendar_status", "user_calendar_id", "status"),
        Index("ix_calendar_events_start_datetime", "start_datetime"),
        Index("ix_calendar_events_end_datetime", "end_datetime"),
        Index("ix_calendar_events_recurring_event_id", "recurring_event_id"),
        Index("ix_calendar_events_google_event_id", "google_event_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    google_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    start_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    start_timezone: Mapped[str | None] = mapped_column(String(255), nullable=True)
    end_timezone: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[CalendarEventStatusEnum] = mapped_column(
        nullable=False,
        default=CalendarEventStatusEnum.CONFIRMED,
    )
    html_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    hangout_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    organizer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    creator_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_self_created: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recurring_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recurrence: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    conference_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    user_calendar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_calendars.id", ondelete="CASCADE"),
        nullable=False,
    )

    user_calendar: Mapped["UserCalendar"] = relationship("UserCalendar", back_populates="events")
    attendees: Mapped[list["CalendarEventAttendee"]] = relationship(
        "CalendarEventAttendee",
        back_populates="event",
        cascade="all, delete-orphan",
    )


class CalendarEventAttendee(Base):
    __tablename__ = "calendar_event_attendees"
    __table_args__ = (
        UniqueConstraint("calendar_event_id", "email", name="idx_event_attendee_unique"),
        Index("ix_calendar_event_attendees_calendar_event_id", "calendar_event_id"),
        Index("ix_calendar_event_attendees_email", "email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    calendar_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calendar_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    response_status: Mapped[CalendarAttendeeResponseStatusEnum] = mapped_column(
        nullable=False,
        default=CalendarAttendeeResponseStatusEnum.NEEDS_ACTION,
    )
    organizer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    optional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resource: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    event: Mapped["CalendarEvent"] = relationship("CalendarEvent", back_populates="attendees")
