from fastapi import Depends
from fastapi import HTTPException
from fastapi import Request
from sqlalchemy.orm import Session

from models import OrganizationMember
from models import get_db
from models.repositories.organization_repository import OrganizationMemberRepository
from models.repositories.organization_repository import OrganizationRepository
from utils.permissions import member_has_permissions


def get_auth_member(
    request: Request,
    db: Session = Depends(get_db),
):
    user_id = request.session.get("user_id")
    org_member_repository = OrganizationMemberRepository(db)
    member = org_member_repository.find_by_id(user_id)
    if not member:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return member


def get_auth_organization(
    request: Request,
    member: OrganizationMember = Depends(get_auth_member),
    db: Session = Depends(get_db),
):
    org_repository = OrganizationRepository(db)
    org = org_repository.find_by_id(member.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


def require_permission(required_permission: str):
    def permission_dependency(
        member: OrganizationMember = Depends(get_auth_member),
        db: Session = Depends(get_db),
    ):
        if not member_has_permissions(member, required_permission, db):
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to perform this action",
            )

    return Depends(permission_dependency)
