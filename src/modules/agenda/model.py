from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.session import Base

if TYPE_CHECKING:
    from src.modules.organization_member.model import OrganizationMember


class AgendaBeta(Base):
    __tablename__ = "agenda_beta"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization_members.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_id: Mapped[str] = mapped_column(String(255), nullable=False)

    member: Mapped["OrganizationMember"] = relationship("OrganizationMember", back_populates="agenda_items")
