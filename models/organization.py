from sqlalchemy import Column, Integer, String, ForeignKey,Boolean, Float
from sqlalchemy.orm import relationship

from models import Base, User


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
    id = Column(Integer, primary_key=True)
    cost_is_active = Column(Boolean, default=False)
    currency = Column(String(3),default='USD')
    cost_period = Column(String(20), default=OrganizationCostPeriod.MONTH)
    cost_visibility = Column(String(20), default=OrganizationCostVisibility.OWNER)
    cost_type = Column(String(20), default=OrganizationCostType.AVERAGE)
    average_cost = Column(Float, nullable=True)
    create_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    create_user = relationship('User', backref='organizations_created')


class OrganizationMemberStatus:
    ACTIVE = "active"
    PENDING = "pending"


class OrganizationMember(Base):
    __tablename__ = 'organization_members'

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    email = Column(String(100), nullable=False, unique=True)
    rate = Column(String(255))
    type_rate = Column(String(255))
    status = Column(String(20), nullable=False, default=OrganizationMemberStatus.PENDING)
    organization = relationship('Organization', backref='members')


class OrganizationTeam(Base):
    __tablename__ = 'organization_teams'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)

    organization = relationship('Organization', backref='teams')

class OrganizationTeamMemberType:
    MEMBER = "member"
    MANAGER = "manager"

class OrganizationTeamMember(Base):
    __tablename__ = 'organization_team_members'

    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey('organization_teams.id'), nullable=False)
    member_id = Column(Integer, ForeignKey('organization_members.id'), nullable=False)
    type = Column(String(20), nullable=False, default=OrganizationTeamMemberType.MEMBER)

    team = relationship('OrganizationTeam', backref='team_members')
    member = relationship('OrganizationMember', backref='teams')

