import uuid

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Float, Text, DateTime
from sqlalchemy.orm import relationship

from models import Base


class OrganizationCostPeriod:
    YEAR = "year"
    MONTH = "month"
    HOUR = "hour"
    ALLOWED_PERIODS = {YEAR, MONTH, HOUR}


class OrganizationCostVisibility:
    OWNER = "owner"
    MANAGER = "manager"
    ALL = "all"
    ALLOWED_PERIODS = {OWNER, MANAGER, ALL}


class OrganizationCostType:
    PER_MEMBER = "per_member"
    AVERAGE = "average"
    ALLOWED_PERIODS = {PER_MEMBER, AVERAGE}


class Organization(Base):
    __tablename__ = 'organizations'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cost_is_active = Column(Boolean, default=False)
    currency = Column(String(3), default='USD')
    cost_period = Column(String(20), default=OrganizationCostPeriod.MONTH)
    cost_visibility = Column(String(20), default=OrganizationCostVisibility.OWNER)
    cost_type = Column(String(20), default=OrganizationCostType.AVERAGE)
    average_cost = Column(Float, nullable=True)


class OrganizationMemberStatus:
    ACTIVE = "active"
    PENDING = "pending"
    ALLOWED_PERIODS = {ACTIVE, PENDING}


class OrganizationMemberRole:
    OWNER = "owner"
    MEMBER = "member"
    ALLOWED_ROLES = {OWNER, MEMBER}


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

    status = Column(String(20), nullable=False, default=OrganizationMemberStatus.PENDING)
    role = Column(String(20), default=OrganizationMemberRole.MEMBER)
    organization = relationship('Organization', backref='members')


class OrganizationTeam(Base):
    __tablename__ = 'organization_teams'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)

    organization = relationship('Organization', backref='teams')


class OrganizationTeamMemberType:
    MEMBER = "member"
    MANAGER = "manager"
    ALLOWED_PERIODS = {MEMBER, MANAGER}


class OrganizationTeamMember(Base):
    __tablename__ = 'organization_team_members'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id = Column(UUID(as_uuid=True), ForeignKey('organization_teams.id'), nullable=False)
    member_id = Column(UUID(as_uuid=True), ForeignKey('organization_members.id'), nullable=False)
    type = Column(String(20), nullable=False, default=OrganizationTeamMemberType.MEMBER)

    team = relationship('OrganizationTeam', backref='team_members')
    member = relationship('OrganizationMember', backref='teams')

