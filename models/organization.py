from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship

from models import Base, User


class Organization(Base):
    __tablename__ = 'organizations'
    id = Column(Integer, primary_key=True)
    create_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    create_user = relationship('User', backref='organizations_created')


class OrganizationMember(Base):
    __tablename__ = 'organization_members'

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'))
    email = Column(String(100), nullable=False, unique=True)
    rate = Column(String(255))
    type_rate = Column(String(255))
    added_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    organization = relationship('Organization', backref='members')
    added_by = relationship('User', backref='organization_members_added')
