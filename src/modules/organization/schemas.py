from __future__ import annotations

from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from src.modules.enums import (
    OrganizationCostPeriodEnum,
    OrganizationCostTypeEnum,
    OrganizationCostVisibilityEnum,
)
from src.shared.currency import Currency
from src.shared.rounded_decimal import RoundedDecimal


class OrganizationOnboardRequest(BaseModel):
    admin_email: EmailStr = Field(description="Email of the admin user to be invited")
    name: str = Field(
        description="Name of the organization",
        min_length=1,
        max_length=255,
    )


class OrganizationOnboardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str = Field(description="Operation status", default="success")
    organization_id: str = Field(description="ID of the created organization")
    admin_email: EmailStr = Field(description="Email to which the invitation was sent")


class CostSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cost_is_active: bool
    currency_code: Currency | None = None
    cost_period: OrganizationCostPeriodEnum | None = None
    cost_visibility: OrganizationCostVisibilityEnum | None = None
    cost_type: OrganizationCostTypeEnum | None = None
    cost_avg: RoundedDecimal | None = None


class UpdateCostSettingsRequest(BaseModel):
    cost_is_active: bool
    currency_code: Currency | None = None
    cost_period: OrganizationCostPeriodEnum | None = None
    cost_visibility: OrganizationCostVisibilityEnum | None = None
    cost_type: OrganizationCostTypeEnum | None = None
    cost_avg: Decimal | None = None

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        if not self.cost_is_active:
            self.currency_code = None
            self.cost_period = None
            self.cost_visibility = None
            self.cost_type = None
            self.cost_avg = None
            return self

        required_fields = {
            "currency_code": self.currency_code,
            "cost_period": self.cost_period,
            "cost_visibility": self.cost_visibility,
            "cost_type": self.cost_type,
        }

        missing = [name for name, value in required_fields.items() if value is None]
        if missing:
            raise ValueError(f"When cost tracking is active, fields must be set: {', '.join(missing)}")

        if self.cost_type == OrganizationCostTypeEnum.AVERAGE and self.cost_avg is None:
            raise ValueError("cost_avg is required when cost_type is 'AVERAGE'")

        return self
