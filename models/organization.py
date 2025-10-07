import enum
import uuid

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import Enum
from sqlalchemy import Float
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from models import Base


class OrganizationCostPeriodEnum(str, enum.Enum):
    year = "year"
    month = "month"
    hour = "hour"


class OrganizationCostVisibilityEnum(str, enum.Enum):
    admin = "admin"
    manager = "manager"
    all = "all"


class OrganizationCostTypeEnum(str, enum.Enum):
    per_member = "per_member"
    average = "average"


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String)
    cost_is_active = Column(Boolean, default=False)

    currency = Column(String(3), default="USD")
    cost_period = Column(Enum(OrganizationCostPeriodEnum), nullable=True)
    cost_visibility = Column(Enum(OrganizationCostVisibilityEnum), nullable=True)
    cost_type = Column(Enum(OrganizationCostTypeEnum), nullable=True)
    average_cost = Column(Float, nullable=True)

    members = relationship(
        "OrganizationMember",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    teams = relationship("OrganizationTeam", back_populates="organization", cascade="all, delete-orphan")
