import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

load_dotenv()
Base = declarative_base()

engine = create_engine(os.getenv("SQLALCHEMY_DATABASE_URI"))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

from .agenda import AgendaBeta
from .organization import Organization
from .organization import OrganizationCostPeriodEnum
from .organization import OrganizationCostTypeEnum
from .organization import OrganizationCostVisibilityEnum
from .organization_member import OrganizationMember
from .organization_member import OrganizationMemberCalendar
from .organization_member import OrganizationMemberRoleEnum
from .organization_member import OrganizationMemberStatusEnum
from .organization_team import OrganizationTeam
from .organization_team import OrganizationTeamMember
from .organization_team import OrganizationTeamMemberTypeEnum


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
