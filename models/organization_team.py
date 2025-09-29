import enum
import uuid

from sqlalchemy import Column
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from models import Base


class OrganizationTeamMemberTypeEnum(str, enum.Enum):
    member = "member"
    manager = "manager"


class OrganizationTeam(Base):
    __tablename__ = "organization_teams"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)

    organization = relationship("Organization", back_populates="teams")
    team_members = relationship("OrganizationTeamMember", back_populates="team", cascade="all, delete-orphan")


class OrganizationTeamMember(Base):
    __tablename__ = "organization_team_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id = Column(UUID(as_uuid=True), ForeignKey("organization_teams.id"), nullable=False)
    member_id = Column(UUID(as_uuid=True), ForeignKey("organization_members.id"), nullable=False)

    type = Column(
        Enum(OrganizationTeamMemberTypeEnum),
        nullable=False,
        default=OrganizationTeamMemberTypeEnum.member,
    )

    team = relationship("OrganizationTeam", back_populates="team_members")
    member = relationship("OrganizationMember", back_populates="teams")
