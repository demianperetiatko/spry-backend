from typing import Optional
from fastapi import Depends, APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from sqlalchemy.orm import Session

from models import get_db, User
from models.repositories.organization_repository import OrganizationRepository

from utils.services import authenticated_user

router = APIRouter(prefix='/settings', tags=['settings'])

class UpdateCostSettings(BaseModel):
    cost_is_active: Optional[bool] = False
    currency: Optional[str] = None
    cost_period: Optional[str] = None
    cost_visibility: Optional[str] = None

@router.get('/cost')
def get_settings_cost(user: User = Depends(authenticated_user), db: Session = Depends(get_db)):
    org_repository = OrganizationRepository(db)
    org = org_repository.find_by_user(user)
    return {
        'cost_is_active': org.cost_is_active or False,
        'currency': org.currency,
        'cost_period': org.cost_period,
        'cost_visibility': org.cost_visibility,
    }

@router.put('/cost')
def update_settings_cost(
    settings: UpdateCostSettings,
    user: User = Depends(authenticated_user),
    db: Session = Depends(get_db),
):
    org_repository = OrganizationRepository(db)
    org = org_repository.find_by_user(user)

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    org.cost_is_active = settings.cost_is_active
    org.currency = settings.currency
    org.cost_period = settings.cost_period
    org.cost_visibility = settings.cost_visibility
    org_repository.update(org)
    return