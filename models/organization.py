import uuid
import enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, Boolean, Float, Enum
from sqlalchemy.orm import relationship

from models import Base


class OrganizationCostPeriodEnum(str, enum.Enum):
    YEAR = "YEAR"
    MONTH = "MONTH"
    HOUR = "HOUR"

class OrganizationCostVisibilityEnum(str, enum.Enum):
    OWNER = "OWNER"
    MANAGER = "MANAGER"
    ALL = "ALL"

class OrganizationCostTypeEnum(str, enum.Enum):
    PER_MEMBER = "PER_MEMBER"
    AVERAGE = "AVERAGE"


class Organization(Base):
    __tablename__ = 'organizations'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String)
    cost_is_active = Column(Boolean, default=False)

    currency = Column(String(3), default='USD')
    cost_period = Column(Enum(OrganizationCostPeriodEnum), nullable=True)
    cost_visibility = Column(Enum(OrganizationCostVisibilityEnum), nullable=True)
    cost_type = Column(Enum(OrganizationCostTypeEnum), nullable=True)
    average_cost = Column(Float, nullable=True)

    members = relationship("OrganizationMember", back_populates="organization", cascade="all, delete-orphan")
    teams = relationship("OrganizationTeam", back_populates="organization", cascade="all, delete-orphan")
