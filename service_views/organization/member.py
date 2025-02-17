from typing import List, Optional
from fastapi import Depends, APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from sqlalchemy.orm import Session

from models import get_db, User, Organization, OrganizationMember, OrganizationMemberStatus
from models.repositories.organization_repository import OrganizationRepository, OrganizationMemberRepository, \
    OrganizationTeamMemberRepository

from models import OrganizationTeam, OrganizationTeamMember, OrganizationTeamMemberType
from models.repositories.organization_repository import OrganizationTeamRepository, OrganizationMemberRepository

from utils.services import authenticated_user
from utils.organization import send_invitation

router = APIRouter()


@router.get("/member/")
def get_member(user: User = Depends(authenticated_user), db: Session = Depends(get_db)):
    org_repository = OrganizationRepository(db)
    organization_member_repository = OrganizationMemberRepository(db)
    org = org_repository.find_by_user(user)
    members = organization_member_repository.find_by_organization_id(org.id)
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
    org = organization_repository.find_by_user(user)
    if not org:
        org = Organization(create_user_id=user.id)
        organization_repository.create(org)
    for email in member_info.emails:
        member = OrganizationMember(
            organization_id=org.id,
            email=email,
            status=OrganizationMemberStatus.PENDING,
        )
        send_invitation(email)
        organization_member_repository.create(member)

class UpdateTeamMember(BaseModel):
    team_id: Optional[int] = None
    team_name: Optional[str] = None
    is_manager: Optional[bool] = False

class UpdateMember(BaseModel):
    cost: Optional[float]
    teams:List[UpdateTeamMember]

@router.put("/member/{member_id}/")
def update_member(
        member_id: int,
        update_member: UpdateMember,
        user: User = Depends(authenticated_user),
        db: Session = Depends(get_db)
):
    org_repository = OrganizationRepository(db)
    org_member_repository = OrganizationMemberRepository(db)
    org_team_repository = OrganizationTeamRepository(db)
    org_team_member_repository = OrganizationTeamMemberRepository(db)
    org = org_repository.find_by_user(user)
    member = org_member_repository.find_by_id(member_id)
    if not org or member.organization_id != org.id:
        raise HTTPException(status_code=404, detail="Organization not found")
    member.cost = str(update_member.cost)
    org_team_member_repository.update(member)

    db.query(OrganizationTeamMember).filter(OrganizationTeamMember.member_id == member.id).filter(
        OrganizationTeamMember.type == OrganizationTeamMemberType.MEMBER).delete()

    for update_data in update_member.teams:
        if update_data.is_manager == False:
            team = org_team_repository.find_by_team_id(org.id, update_data.team_id)
            new_team_member = OrganizationTeamMember(
                team_id=team.id,
                member_id=member.id,
                type=OrganizationTeamMemberType.MANAGER if update_data.is_manager else OrganizationTeamMemberType.MEMBER
            )
            org_team_member_repository.create(new_team_member)


@router.delete("/member/{member_id}/")
def delete_member_from_organization(
        member_id: int,
        user: User = Depends(authenticated_user),
        db: Session = Depends(get_db)
):
    organization_repository = OrganizationRepository(db)
    organization_member_repository = OrganizationMemberRepository(db)
    org = organization_repository.find_by_user(user)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    member = organization_member_repository.find_by_member_id(org.id, member_id)
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
    org = organization_repository.find_by_user(user)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    member = organization_member_repository.find_by_member_id(org.id, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    send_invitation(member.email)
