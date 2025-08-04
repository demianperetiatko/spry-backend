from fastapi import Depends, APIRouter, HTTPException, Header
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from models import get_db, Organization, OrganizationMember
from models.repositories.organization_repository import OrganizationRepository,\
    OrganizationMemberRoleEnum, OrganizationMemberStatusEnum

from models.repositories.organization_member_repository import OrganizationMemberRepository
from utils.send_message import send_admin_invitation


router = APIRouter()

API_KEY = "mbZKfS_0ivwMf5XjisfhdQmWLUgll5wtOBEWgYjxDvI"


class OrganizationCreateRequest(BaseModel):
    email: EmailStr
    organization_name: str


@router.post("/admin/organization")
def admin_add_organization(
        request: OrganizationCreateRequest,
        db: Session = Depends(get_db),
        x_api_key: str = Header(..., alias="X-API-Key")
):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")

    org_repository = OrganizationRepository(db)
    org_member_repository = OrganizationMemberRepository(db)

    if org_member_repository.find_by_email(email=request.email):
        raise HTTPException(status_code=403, detail="Organization already exists")

    new_org = Organization(
        name=request.organization_name,
    )
    org_repository.create(new_org)
    new_member = OrganizationMember(
        email=request.email,
        role=OrganizationMemberRoleEnum.OWNER,
        status=OrganizationMemberStatusEnum.PENDING,
        organization=new_org
    )
    org_member_repository.create(new_member)
    send_admin_invitation(request.email)
    return {
        'status': 'success',
        'organization_id': new_org.id,
        'email': request.email
    }
