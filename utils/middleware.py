import requests
from fastapi import Request, HTTPException, Depends, Header

from sqlalchemy.orm import Session

from models import get_db, Organization, OrganizationMember, OrganizationMemberStatus
from models.repositories.organization_repository import OrganizationRepository, OrganizationMemberRepository
from utils.google_api import refresh_google_access_token


def get_auth_member(
        request: Request,
        db: Session = Depends(get_db),
):
    user_id = request.session.get("user_id")
    org_member_repository = OrganizationMemberRepository(db)
    member = org_member_repository.find_by_id(user_id)
    if not member:
        raise HTTPException(status_code=401, detail="Unauthorized")
    access_token = refresh_google_access_token(member.google_refresh_token)
    if not access_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return member


def get_auth_organization(
        request: Request, member: OrganizationMember = Depends(get_auth_member), db: Session = Depends(get_db)
):
    org_repository = OrganizationRepository(db)
    org = org_repository.find_by_id(member.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org
