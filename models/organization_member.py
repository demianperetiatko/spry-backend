import uuid
import enum
from sqlalchemy import Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, ForeignKey, Text, Enum, DateTime
from sqlalchemy.orm import relationship

from models import Base


class OrganizationMemberStatusEnum(str, enum.Enum):
    active = "active"
    pending = "pending"

class OrganizationMemberRoleEnum(str, enum.Enum):
    owner = "owner"
    member = "member"


class OrganizationMember(Base):
    __tablename__ = 'organization_members'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)
    name = Column(String(100))
    email = Column(String(100), nullable=False, unique=True)
    photo_url = Column(Text)
    hourly_cost = Column(String(255))

    status = Column(Enum(OrganizationMemberStatusEnum), nullable=False, default=OrganizationMemberStatusEnum.pending)
    role = Column(Enum(OrganizationMemberRoleEnum), default=OrganizationMemberRoleEnum.member)

    organization = relationship("Organization", back_populates="members")
    calendars = relationship("OrganizationMemberCalendar", back_populates="member", cascade='all, delete-orphan')
    teams = relationship("OrganizationTeamMember", back_populates="member", cascade='all, delete-orphan')


class CalendarTypeEnum(str, enum.Enum):
    google = "google"
    google_services = "google_services"


class OrganizationMemberCalendar(Base):
    __tablename__ = 'organization_member_calendars'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id = Column(UUID(as_uuid=True), ForeignKey('organization_members.id'), nullable=False)

    type = Column(Enum(CalendarTypeEnum), nullable=False, default=CalendarTypeEnum.google)

    access_token = Column(Text, nullable=False)
    access_token_expiry = Column(DateTime)
    refresh_token = Column(Text, nullable=False)

    member = relationship('OrganizationMember', back_populates='calendars')
