from typing import List
from fastapi import Depends, APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from sqlalchemy.orm import Session

from models import get_db, User, Organization, OrganizationMember
from models.repositories.organization_repository import OrganizationRepository, OrganizationMemberRepository
from utils.services import authenticated_user
from utils.send_message import send_email

router = APIRouter()


@router.get("/member/")
def get_member(user: User = Depends(authenticated_user), db: Session = Depends(get_db)):
    org_repository = OrganizationRepository(db)
    organization_member_repository = OrganizationMemberRepository(db)
    org = org_repository.find_organization(user.id)
    members = organization_member_repository.find_member(org.id)
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
    org = organization_repository.find_organization(user.id)
    if not org:
        org = Organization(create_user_id=user.id)
        organization_repository.create(org)
    for email in member_info.emails:
        member = OrganizationMember(
            organization_id=org.id,
            email=email,
            added_by_id=user.id
        )
        send_email(to_email=email,
                   subject="Welcome to SPTY!",
                   html_content="""
                       <h1>Welcome to SPTY!</h1>
                       <p>You have been invited to join SPTY.</p>
                       <p>
                           Please click the link below to log in and get started:
                           <br>
                           <a href="https://app.spryplan.com/login" target="_blank">Log In</a>
                       </p>
                       <p>If you have any questions, feel free to contact us.</p>
                   """)
        organization_member_repository.create(member)
