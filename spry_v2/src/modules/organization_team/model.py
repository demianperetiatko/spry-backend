from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.session import Base
from src.modules.enums import OrganizationTeamMemberTypeEnum

if TYPE_CHECKING:
    from src.modules.organization.model import Organization
    from src.modules.organization_member.model import OrganizationMember


class OrganizationTeam(Base):
    __tablename__ = "organization_teams"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="teams", lazy="selectin")
    team_members: Mapped[list["OrganizationTeamMember"]] = relationship(
        "OrganizationTeamMember",
        back_populates="team",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class OrganizationTeamMember(Base):
    __tablename__ = "organization_team_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization_teams.id"),
        nullable=False,
    )
    organization_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization_members.id"),
        nullable=False,
    )
    type: Mapped[OrganizationTeamMemberTypeEnum] = mapped_column(
        nullable=False,
        default=OrganizationTeamMemberTypeEnum.MEMBER,
    )

    team: Mapped["OrganizationTeam"] = relationship(
        "OrganizationTeam",
        back_populates="team_members",
        lazy="selectin",
    )
    member: Mapped["OrganizationMember"] = relationship(
        "OrganizationMember",
        back_populates="team_members",
        lazy="selectin",
    )
