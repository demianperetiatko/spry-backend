import uuid
import enum
from sqlalchemy import Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, ForeignKey, Text, Enum, DateTime
from sqlalchemy.orm import relationship

from models import Base


class OrganizationMemberStatusEnum(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PENDING = "PENDING"

class OrganizationMemberRoleEnum(str, enum.Enum):
    OWNER = "OWNER"
    MEMBER = "MEMBER"


class OrganizationMember(Base):
    __tablename__ = 'organization_members'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)
    name = Column(String(100))
    email = Column(String(100), nullable=False, unique=True)
    photo_url = Column(Text)
    hourly_cost = Column(String(255))

    google_access_token = Column(Text)
    google_access_token_expiry = Column(DateTime)
    google_refresh_token = Column(Text)

    status = Column(Enum(OrganizationMemberStatusEnum), nullable=False, default=OrganizationMemberStatusEnum.PENDING)
    role = Column(Enum(OrganizationMemberRoleEnum), default=OrganizationMemberRoleEnum.MEMBER)

    organization = relationship("Organization", back_populates="members")
    calendars = relationship("OrganizationMemberCalendar", back_populates="member", cascade='all, delete-orphan')
    teams = relationship("OrganizationTeamMember", back_populates="member", cascade='all, delete-orphan')


class CalendarTypeEnum(str, enum.Enum):
    GOOGLE = "GOOGLE"
    GOOGLE_SERVICES = "GOOGLE_SERVICES"


class OrganizationMemberCalendar(Base):
    __tablename__ = 'organization_member_calendars'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id = Column(UUID(as_uuid=True), ForeignKey('organization_members.id'), nullable=False)

    type = Column(Enum(CalendarTypeEnum), nullable=False, default=CalendarTypeEnum.GOOGLE)

    access_token = Column(Text, nullable=False)
    access_token_expiry = Column(DateTime)
    refresh_token = Column(Text, nullable=False)

    member = relationship('OrganizationMember', back_populates='calendars')
