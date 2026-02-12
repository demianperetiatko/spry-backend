from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Header, status

from src.core.config import settings
from src.modules.auth.dependency import OrganizationContext, require_permission
from src.modules.organization.schemas import (
    CostSettingsResponse,
    OrganizationOnboardRequest,
    OrganizationOnboardResponse,
    UpdateCostSettingsRequest,
)
from src.modules.organization.service import OrganizationService, get_organization_service
from src.modules.permissions.enums import OrganizationPermission

router = APIRouter(prefix="/organizations", tags=["organizations"])


def verify_admin_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> None:
    if x_api_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")


@router.post(
    "/onboard",
    response_model=OrganizationOnboardResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_admin_api_key)],
)
async def onboard_organization(
    payload: OrganizationOnboardRequest,
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationOnboardResponse:
    new_org = await service.onboard_organization(payload)
    return OrganizationOnboardResponse(
        organization_id=str(new_org.id),
        admin_email=payload.admin_email,
    )


@router.get(
    "/{organization_id}/cost",
    response_model=CostSettingsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_cost_settings(
    ctx: Annotated[OrganizationContext, require_permission(OrganizationPermission.MEETINGS_COSTS_VIEW)],
    service: OrganizationService = Depends(get_organization_service),
) -> CostSettingsResponse:
    return await service.get_cost_settings(ctx.organization.id)


@router.put(
    "/{organization_id}/cost",
    response_model=CostSettingsResponse,
    status_code=status.HTTP_200_OK,
)
async def update_cost_settings(
    cost_settings: UpdateCostSettingsRequest,
    ctx: Annotated[OrganizationContext, require_permission(OrganizationPermission.MEETINGS_COSTS_VIEW)],
    service: OrganizationService = Depends(get_organization_service),
) -> CostSettingsResponse:
    return await service.update_cost_settings(ctx.organization.id, cost_settings)
