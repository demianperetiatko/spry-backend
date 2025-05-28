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

from .super_admin import SuperAdmin
from .organization import Organization, OrganizationCostPeriod, OrganizationCostVisibility, OrganizationCostType
from .organization import OrganizationMember, OrganizationMemberStatus, OrganizationMemberRole
from .organization import OrganizationTeam, OrganizationTeamMember, OrganizationTeamMemberType



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
