from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship

from models import Base


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(100), nullable=False, unique=True)
    google_access_token = Column(Text)
    google_refresh_token = Column(Text)


class Team(Base):
    __tablename__ = 'teams'
    id = Column(Integer, primary_key=True)
    create_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    create_user = relationship('User', backref='teams_created')


class TeamMember(Base):
    __tablename__ = 'team_members'

    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey('teams.id'))
    email = Column(String(100), nullable=False, unique=True)
    rate = Column(String(255))
    type_rate = Column(String(255))
    added_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    team = relationship('Team', backref='members')
    added_by = relationship('User', backref='team_members_added')
