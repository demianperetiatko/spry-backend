from typing import List, Optional
from fastapi import Depends, APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from sqlalchemy.orm import Session

from models import get_db, Organization, OrganizationMember, OrganizationMemberStatus
from models.repositories.organization_repository import OrganizationRepository, OrganizationMemberRepository, \
    OrganizationTeamMemberRepository

from models import OrganizationTeam, OrganizationTeamMember, OrganizationTeamMemberType
from models.repositories.organization_repository import OrganizationTeamRepository, OrganizationMemberRepository

from utils.middleware import get_auth_member, get_auth_organization
from utils.organization import send_invitation
from utils.table import DBTable

router = APIRouter()


@router.get("/member/")
def get_member(
        auth_member: OrganizationMember = Depends(get_auth_member),
        db: Session = Depends(get_db)
):
    org_team_repository = OrganizationTeamRepository(db)
    org_member_repository = OrganizationMemberRepository(db)

    columns = [
        ("id", "id"),
        ("name", "name"),
        ("photo_url", "photo_url"),
        ("email", "email"),
        ("cost", "cost", lambda i: float(i.cost) if i.cost else None),
        ("status", "status"),
        ("department", "department"),
        ("teams", "teams", lambda i: org_team_repository.find_by_member_id(i.id))
    ]

    query_members = org_member_repository.query_find_by_organization_id(auth_member.organization_id)
    return DBTable(query_members, columns).fetch_dicts()


class MemberRequest(BaseModel):
    emails: List[EmailStr]


@router.post("/member/")
def add_members_to_organization(
        member_info: MemberRequest,
        auth_member: OrganizationMember = Depends(get_auth_member),
        db: Session = Depends(get_db)
):
    org_member_repository = OrganizationMemberRepository(db)

    for email in member_info.emails:
        member = OrganizationMember(
            organization_id=auth_member.organization_id,
            email=email,
            status=OrganizationMemberStatus.PENDING,
        )
        send_invitation(email)
        org_member_repository.create(member)


class UpdateTeamMember(BaseModel):
    team_id: Optional[int] = None
    team_name: Optional[str] = None
    is_manager: Optional[bool] = False


class UpdateMember(BaseModel):
    cost: Optional[float]
    teams: Optional[List[UpdateTeamMember]]


@router.put("/member/{member_id}/")
def update_member(
        member_id: int,
        update_member: UpdateMember,
        auth_member: OrganizationMember = Depends(get_auth_member),
        auth_organization: Organization = Depends(get_auth_organization),
        db: Session = Depends(get_db)
):
    org_member_repository = OrganizationMemberRepository(db)
    org_team_repository = OrganizationTeamRepository(db)
    org_team_member_repository = OrganizationTeamMemberRepository(db)

    member = org_member_repository.find_by_id(member_id)
    member.cost = str(update_member.cost) if update_member.cost else None
    org_team_member_repository.update(member)

    db.query(OrganizationTeamMember).filter(OrganizationTeamMember.member_id == member.id).filter(
        OrganizationTeamMember.type == OrganizationTeamMemberType.MEMBER).delete()
    db.commit()
    for update_data in update_member.teams:
        if update_data.is_manager == False:
            team = org_team_repository.find_by_team_id(auth_organization.id, update_data.team_id)
            new_team_member = OrganizationTeamMember(
                team_id=team.id,
                member_id=member.id,
                type=OrganizationTeamMemberType.MANAGER if update_data.is_manager else OrganizationTeamMemberType.MEMBER
            )
            org_team_member_repository.create(new_team_member)


@router.delete("/member/{member_id}/")
def delete_member_from_organization(
        member_id: int,
        auth_member: OrganizationMember = Depends(get_auth_member),
        auth_organization: Organization = Depends(get_auth_organization),
        db: Session = Depends(get_db)
):
    organization_member_repository = OrganizationMemberRepository(db)

    member = organization_member_repository.find_by_member_id(auth_organization.id, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    organization_member_repository.delete(member)


@router.post("/member/{member_id}/resend-invitation")
def resend_invitation(
        member_id: int,
        auth_member: OrganizationMember = Depends(get_auth_member),
        auth_organization: Organization = Depends(get_auth_organization),
        db: Session = Depends(get_db)
):
    organization_member_repository = OrganizationMemberRepository(db)
    member = organization_member_repository.find_by_member_id(auth_organization.id, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    send_invitation(member.email)
