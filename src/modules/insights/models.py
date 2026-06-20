from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database.session import Base


class InsightSettings(Base):
    __tablename__ = "insight_settings"
    __table_args__ = (
        UniqueConstraint("organization_id", "tab", name="uq_insight_settings_org_tab"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    tab: Mapped[str] = mapped_column(String(32), nullable=False)
    generation_frequency: Mapped[str] = mapped_column(
        String(64), nullable=False, default="weekly_monday_8"
    )
    data_horizon: Mapped[str] = mapped_column(
        String(64), nullable=False, default="last_and_next_4_weeks"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
