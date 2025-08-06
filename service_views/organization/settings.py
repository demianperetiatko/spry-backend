from typing import Optional
from fastapi import Depends, APIRouter, HTTPException
from pydantic import BaseModel, field_validator, model_validator

from sqlalchemy.orm import Session

from models import get_db, Organization, OrganizationMember, OrganizationCostPeriodEnum, OrganizationCostVisibilityEnum, \
    OrganizationCostTypeEnum
from models.repositories.organization_repository import OrganizationRepository, OrganizationMemberRepository

from utils.middleware import get_auth_member, get_auth_organization, require_permission

from utils.cost import calculate_hourly_cost

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
        ALLOWED_PERIODS = [
            OrganizationCostPeriodEnum.year,
            OrganizationCostPeriodEnum.month,
            OrganizationCostPeriodEnum.hour,
        ]
        if info.data.get('cost_is_active') and value not in ALLOWED_PERIODS:
            raise ValueError(
                f"Invalid value for cost_period. Allowed values are: {', '.join(ALLOWED_PERIODS)}"
            )
        if info.data.get('cost_is_active') is False and value is not None:
            raise ValueError("cost_period must be None when cost_is_active is False.")
        return value

    @field_validator("cost_visibility")
    def validate_cost_visibility(cls, value, info):
        ALLOWED_PERIODS = [
            OrganizationCostVisibilityEnum.owner,
            OrganizationCostVisibilityEnum.manager,
            OrganizationCostVisibilityEnum.all
        ]
        if info.data.get('cost_is_active') and value not in ALLOWED_PERIODS:
            raise ValueError(
                f"Invalid value for cost_visibility. Allowed values are: {', '.join(ALLOWED_PERIODS)}"
            )
        if info.data.get('cost_is_active') is False and value is not None:
            raise ValueError("cost_visibility must be None when cost_is_active is False.")
        return value

    @field_validator("cost_type")
    def validate_cost_type(cls, value, info):
        ALLOWED_PERIODS = [
            OrganizationCostTypeEnum.per_member,
            OrganizationCostTypeEnum.average,
        ]
        if info.data.get('cost_is_active') and value not in ALLOWED_PERIODS:
            raise ValueError(
                f"Invalid value for cost_type. Allowed values are: {', '.join(ALLOWED_PERIODS)}"
            )
        if info.data.get('cost_is_active') is False and value is not None:
            raise ValueError("cost_type must be None when cost_is_active is False.")
        return value

    @field_validator("average_cost")
    def validate_average_cost(cls, value, info):
        if info.data.get("cost_type") == OrganizationCostTypeEnum.average and value is None:
            raise ValueError("average_cost must not be None when cost_type is 'average'")
        return value


@router.get('/cost')
def get_settings_cost(
        auth_member: OrganizationMember = Depends(get_auth_member),
        auth_organization: Organization = Depends(get_auth_organization),
        db: Session = Depends(get_db),
        # TODO: move currency to /auth
        # _: None = require_permission('meetings-costs:view')
):
    return {
        'cost_is_active': auth_organization.cost_is_active or False,
        'currency': auth_organization.currency,
        'cost_period': auth_organization.cost_period,
        'cost_visibility': auth_organization.cost_visibility,
        'cost_type': auth_organization.cost_type,
        'average_cost': auth_organization.average_cost,
    }


@router.put('/cost')
def update_settings_cost(
        settings: UpdateCostSettings,
        auth_member: OrganizationMember = Depends(get_auth_member),
        auth_organization: Organization = Depends(get_auth_organization),
        db: Session = Depends(get_db),
        _: None = require_permission('meetings-costs:view')
):
    org_repository = OrganizationRepository(db)
    org_member_repository = OrganizationMemberRepository(db)

    auth_organization.cost_is_active = settings.cost_is_active
    auth_organization.currency = settings.currency
    auth_organization.cost_period = settings.cost_period
    auth_organization.cost_visibility = settings.cost_visibility

    if settings.cost_type == OrganizationCostTypeEnum.average:
        hourly_cost = calculate_hourly_cost(settings.average_cost, auth_organization.cost_period)
        org_member_repository.update_member_cost(auth_organization.id, hourly_cost)
    elif auth_organization.cost_type != settings.cost_type:
        org_member_repository.update_member_cost(auth_organization.id, None)
    auth_organization.cost_type = settings.cost_type
    auth_organization.average_cost = settings.average_cost
    org_repository.update(auth_organization)
    return
