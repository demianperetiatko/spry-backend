from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.session import Base
from src.modules.enums import InvitationStatusEnum, OrganizationMemberRoleEnum

if TYPE_CHECKING:
    from src.modules.organization.model import Organization
    from src.modules.user.model import User


class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    role: Mapped[OrganizationMemberRoleEnum] = mapped_column(
        nullable=False,
        default=OrganizationMemberRoleEnum.MEMBER,
    )
    status: Mapped[InvitationStatusEnum] = mapped_column(
        nullable=False,
        default=InvitationStatusEnum.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped["User"] = relationship("User", back_populates="invitations")
    organization: Mapped["Organization"] = relationship("Organization", back_populates="invitations")
