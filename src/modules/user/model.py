from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.session import Base
from src.modules.enums import CalendarTypeEnum, UserStatusEnum

if TYPE_CHECKING:
    from src.modules.calendar.models import UserCalendar
    from src.modules.feedback.model import Feedback
    from src.modules.invitation.model import Invitation
    from src.modules.organization_member.model import OrganizationMember


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    email: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[UserStatusEnum] = mapped_column(
        nullable=False,
        default=UserStatusEnum.PENDING,
    )

    access_info: Mapped["UserAccessInfo"] = relationship("UserAccessInfo", back_populates="user")
    organization_members: Mapped[list["OrganizationMember"]] = relationship(
        "OrganizationMember",
        back_populates="user",
        cascade="all",
    )
    invitations: Mapped[list["Invitation"]] = relationship(
        "Invitation",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    feedbacks: Mapped[list["Feedback"]] = relationship(
        "Feedback",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserAccessInfo(Base):
    __tablename__ = "users_access_info"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        unique=True,
    )
    calendar_email: Mapped[str | None] = mapped_column(String(128), nullable=True)
    type: Mapped[CalendarTypeEnum] = mapped_column(
        nullable=False,
        default=CalendarTypeEnum.GOOGLE,
    )
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    access_token_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="access_info")
    calendars: Mapped[list["UserCalendar"]] = relationship(
        "UserCalendar",
        back_populates="user_access_info",
        cascade="all, delete-orphan",
    )
