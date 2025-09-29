import uuid

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship

from models import Base

class AgendaBeta(Base):
    __tablename__ = 'agenda_beta'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id = Column(UUID(as_uuid=True), ForeignKey('organization_members.id', ondelete='CASCADE'), nullable=False)
    event_id = Column(String(255), nullable=False)

    member = relationship('OrganizationMember', back_populates='agenda_items')
