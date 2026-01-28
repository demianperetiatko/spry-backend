from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.session import Base
from src.modules.enums import (
    OrganizationMemberRoleEnum,
    OrganizationMemberStatusEnum,
)
from src.modules.organization_team.model import OrganizationTeamMember

if TYPE_CHECKING:
    from src.modules.agenda.model import AgendaBeta
    from src.modules.calendar.models import OrganizationMemberCalendar
    from src.modules.organization.model import Organization
    from src.modules.user.model import User


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    __table_args__ = (UniqueConstraint("user_id", "organization_id", name="uq_user_organization"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    hourly_cost: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    status: Mapped[OrganizationMemberStatusEnum] = mapped_column(
        nullable=False,
        default=OrganizationMemberStatusEnum.PENDING,
    )
    role: Mapped[OrganizationMemberRoleEnum] = mapped_column(
        default=OrganizationMemberRoleEnum.MEMBER,
    )

    user: Mapped["User"] = relationship("User", back_populates="organization_members", lazy="selectin")
    organization: Mapped["Organization"] = relationship("Organization", back_populates="members", lazy="selectin")
    team_members: Mapped[list["OrganizationTeamMember"]] = relationship(
        "OrganizationTeamMember",
        back_populates="member",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    calendars: Mapped[list["OrganizationMemberCalendar"]] = relationship(
        "OrganizationMemberCalendar",
        back_populates="member",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    agenda_items: Mapped[list["AgendaBeta"]] = relationship(
        "AgendaBeta",
        back_populates="member",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
