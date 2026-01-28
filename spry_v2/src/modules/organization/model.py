from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.session import Base
from src.modules.enums import (
    OrganizationCostPeriodEnum,
    OrganizationCostTypeEnum,
    OrganizationCostVisibilityEnum,
)
from src.shared.currency import Currency, CurrencyType

if TYPE_CHECKING:
    from src.modules.invitation.model import Invitation
    from src.modules.organization_member.model import OrganizationMember
    from src.modules.organization_team.model import OrganizationTeam


class OrganizationCurrency(Base):
    __tablename__ = "organizations_currency"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    currency_code: Mapped[Currency] = mapped_column(CurrencyType(), nullable=False, default=lambda: Currency("USD"))
    cost_avg: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    cost_is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cost_type: Mapped[OrganizationCostTypeEnum | None] = mapped_column(nullable=True)
    cost_period: Mapped[OrganizationCostPeriodEnum | None] = mapped_column(nullable=True)
    cost_visibility: Mapped[OrganizationCostVisibilityEnum | None] = mapped_column(nullable=True)

    organizations: Mapped[list["Organization"]] = relationship(
        "Organization",
        back_populates="currency",
    )


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    organizations_currency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations_currency.id"),
        nullable=False,
    )

    currency: Mapped["OrganizationCurrency"] = relationship(
        "OrganizationCurrency",
        back_populates="organizations",
    )
    members: Mapped[list["OrganizationMember"]] = relationship(
        "OrganizationMember",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    teams: Mapped[list["OrganizationTeam"]] = relationship(
        "OrganizationTeam",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    invitations: Mapped[list["Invitation"]] = relationship(
        "Invitation",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
