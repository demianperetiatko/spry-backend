from typing import Optional
from fastapi import Depends, APIRouter, HTTPException
from pydantic import BaseModel, field_validator, model_validator

from sqlalchemy.orm import Session

from models import get_db, User, OrganizationCostPeriod, OrganizationCostVisibility, OrganizationCostType
from models.repositories.organization_repository import OrganizationRepository

from utils.services import authenticated_user

router = APIRouter(prefix='/settings', tags=['settings'])

class UpdateCostSettings(BaseModel):
    cost_is_active: Optional[bool] = False
    currency: Optional[str] = None
    cost_period: Optional[str] = None
    cost_visibility: Optional[str] = None
    cost_type: Optional[str] = None
    average_cost: Optional[float] = None

    @field_validator("currency")
    def validate_currency(cls, value, info):
        if info.data.get('cost_is_active') and value is None:
            raise ValueError("Currency must not be None when cost_is_active is True.")
        if info.data.get('cost_is_active') is False and value is not None:
            raise ValueError("Currency must be None when cost_is_active is False.")
        return value

    @field_validator("cost_period")
    def validate_cost_period(cls, value, info):
        if info.data.get('cost_is_active') and value not in OrganizationCostPeriod.ALLOWED_PERIODS:
            raise ValueError(
                f"Invalid value for cost_period. Allowed values are: {', '.join(OrganizationCostPeriod.ALLOWED_PERIODS)}"
            )
        if info.data.get('cost_is_active') is False and value is not None:
            raise ValueError("cost_period must be None when cost_is_active is False.")
        return value

    @field_validator("cost_visibility")
    def validate_cost_visibility(cls, value, info):
        if info.data.get('cost_is_active') and value not in OrganizationCostVisibility.ALLOWED_PERIODS:
            raise ValueError(
                f"Invalid value for cost_visibility. Allowed values are: {', '.join(OrganizationCostVisibility.ALLOWED_PERIODS)}"
            )
        if info.data.get('cost_is_active') is False and value is not None:
            raise ValueError("cost_visibility must be None when cost_is_active is False.")
        return value

    @field_validator("cost_type")
    def validate_cost_type(cls, value, info):
        if info.data.get('cost_is_active') and value not in OrganizationCostType.ALLOWED_PERIODS:
            raise ValueError(
                f"Invalid value for cost_type. Allowed values are: {', '.join(OrganizationCostType.ALLOWED_PERIODS)}"
            )
        if info.data.get('cost_is_active') is False and value is not None:
            raise ValueError("cost_type must be None when cost_is_active is False.")
        return value

    @field_validator("average_cost")
    def validate_average_cost(cls, value, info):
        if info.data.get("cost_type") == OrganizationCostType.AVERAGE and value is None:
            raise ValueError("average_cost must not be None when cost_type is 'average'")
        return value

@router.get('/cost')
def get_settings_cost(user: User = Depends(authenticated_user), db: Session = Depends(get_db)):
    org_repository = OrganizationRepository(db)
    org = org_repository.find_by_user(user)
    return {
        'cost_is_active': org.cost_is_active or False,
        'currency': org.currency,
        'cost_period': org.cost_period,
        'cost_visibility': org.cost_visibility,
        'cost_type': org.cost_type,
        'average_cost': org.average_cost,
    }

@router.put('/cost')
def update_settings_cost(
    settings: UpdateCostSettings,
    user: User = Depends(authenticated_user),
    db: Session = Depends(get_db),
):
    org_repository = OrganizationRepository(db)
    org = org_repository.find_by_user(user)
    print(settings)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    org.cost_is_active = settings.cost_is_active
    org.currency = settings.currency
    org.cost_period = settings.cost_period
    org.cost_visibility = settings.cost_visibility
    org.cost_type = settings.cost_type
    org.average_cost = settings.average_cost
    org_repository.update(org)
    print(org.id)
    print(org.cost_is_active)
    return