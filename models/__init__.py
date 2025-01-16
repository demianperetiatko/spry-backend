import os
from contextlib import contextmanager

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()
Base = declarative_base()

engine = create_engine(os.getenv("SQLALCHEMY_DATABASE_URI"))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

from .user import User
from .organization import Organization
from .organization import OrganizationMember, OrganizationMemberStatus
from .organization import OrganizationTeam, OrganizationTeamMember

from .agenda import AgendaTemplate


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_context_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
