from typing import List
from fastapi import Depends, APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from sqlalchemy.orm import Session

from models import get_db, User, Organization, OrganizationMember
from models.repositories.organization_repository import OrganizationRepository, OrganizationMemberRepository
from utils.services import authenticated_user
from utils.organization import send_invitation

router = APIRouter()


@router.get("/member/")
def get_member(user: User = Depends(authenticated_user), db: Session = Depends(get_db)):
    org_repository = OrganizationRepository(db)
    organization_member_repository = OrganizationMemberRepository(db)
    org = org_repository.find_organization(user)
    members = organization_member_repository.find_members(org.id)
    return {
        'data': members,
        'total_count': len(members)
    }

class MemberRequest(BaseModel):
    emails: List[EmailStr]

@router.post("/member/")
def add_members_to_organization(
        member_info: MemberRequest,
        user: User = Depends(authenticated_user),
        db: Session = Depends(get_db)
):
    organization_repository = OrganizationRepository(db)
    organization_member_repository = OrganizationMemberRepository(db)
    org = organization_repository.find_organization(user)
    if not org:
        org = Organization(create_user_id=user.id)
        organization_repository.create(org)
    for email in member_info.emails:
        member = OrganizationMember(
            organization_id=org.id,
            email=email,
            added_by_id=user.id
        )
        send_invitation(email)
        organization_member_repository.create(member)

class UpdateMemberRequest(BaseModel):
    email: EmailStr

@router.put("/member/{member_id}/")
def update_member(
        member_id: int,
        member_info: UpdateMemberRequest,
        user: User = Depends(authenticated_user),
        db: Session = Depends(get_db)
):
    pass

@router.delete("/member/{member_id}/")
def delete_member_from_organization(
        member_id: int,
        user: User = Depends(authenticated_user),
        db: Session = Depends(get_db)
):
    organization_repository = OrganizationRepository(db)
    organization_member_repository = OrganizationMemberRepository(db)
    org = organization_repository.find_organization(user)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    member = organization_member_repository.find_member(org.id, member_id)
    if not member or member.organization_id != org.id:
        raise HTTPException(status_code=404, detail="Member not found")
    organization_member_repository.delete(member)

@router.post("/member/{member_id}/resend-invitation")
def resend_invitation(
        member_id: int,
        user: User = Depends(authenticated_user),
        db: Session = Depends(get_db)
):
    organization_repository = OrganizationRepository(db)
    organization_member_repository = OrganizationMemberRepository(db)
    org = organization_repository.find_organization(user)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    member = organization_member_repository.find_member(org.id, member_id)
    if not member or member.organization_id != org.id:
        raise HTTPException(status_code=404, detail="Member not found")
    send_invitation(member.email)
