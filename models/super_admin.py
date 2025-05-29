import uuid
from sqlalchemy import Column, String, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID

from models import Base


class SuperAdmin(Base):
    __tablename__ = 'super_admins'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    email = Column(String(100), nullable=False, unique=True)
