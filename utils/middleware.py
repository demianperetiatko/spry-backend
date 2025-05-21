import requests
from fastapi import Request, HTTPException, Depends, Header

from sqlalchemy.orm import Session

from models import get_db, User, Organization, OrganizationMember, OrganizationMemberStatus
from models.repositories.user_repository import UserRepository
from models.repositories.organization_repository import OrganizationRepository, OrganizationMemberRepository
from utils.services import refresh_google_access_token


def get_auth_user(
        request: Request,
        db: Session = Depends(get_db),
):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_repository = UserRepository(db)
    user = user_repository.find_by_id(int(user_id))
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    access_token = refresh_google_access_token(user.google_refresh_token)
    if not access_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user


def get_organization(
        request: Request, user: User = Depends(get_auth_user), db: Session = Depends(get_db)
):
    org_repository = OrganizationRepository(db)
    org = org_repository.find_by_user(user)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org
