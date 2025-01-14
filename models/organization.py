from sqlalchemy import Column, Integer, String, ForeignKey, Enum
from sqlalchemy.orm import relationship

from models import Base, User
import enum


class Organization(Base):
    __tablename__ = 'organizations'
    id = Column(Integer, primary_key=True)
    create_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    create_user = relationship('User', backref='organizations_created')


class OrganizationMemberStatus:
    ACTIVE = "active"
    PENDING = "pending"


class OrganizationMember(Base):
    __tablename__ = 'organization_members'

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'))
    email = Column(String(100), nullable=False, unique=True)
    rate = Column(String(255))
    type_rate = Column(String(255))
    added_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    status = Column(String(20), nullable=False, default=OrganizationMemberStatus.PENDING)

    organization = relationship('Organization', backref='members')
    added_by = relationship('User', backref='organization_members_added')
