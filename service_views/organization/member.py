from typing import List
from typing import Optional

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from pydantic import BaseModel
from pydantic import EmailStr
from sqlalchemy.orm import Session

from models import Organization
from models import OrganizationMember
from models import OrganizationMemberRoleEnum
from models import OrganizationMemberStatusEnum
from models import OrganizationTeamMember
from models import OrganizationTeamMemberTypeEnum
from models import get_db
from models.repositories.organization_member_repository import OrganizationMemberRepository
from models.repositories.organization_team_repository import OrganizationTeamMemberRepository
from models.repositories.organization_team_repository import OrganizationTeamRepository
from utils.cost import calculate_hourly_cost
from utils.cost import calculate_total_cost
from utils.middleware import get_auth_member
from utils.middleware import get_auth_organization
from utils.middleware import require_permission
from utils.permissions import member_has_permissions
from utils.send_message import send_user_invitation
from utils.table import DBTable

router = APIRouter()


@router.get("/member/")
def get_member(
    auth_member: OrganizationMember = Depends(get_auth_member),
    auth_organization: Organization = Depends(get_auth_organization),
    db: Session = Depends(get_db),
    _: None = require_permission("members:view"),
):
    org_team_repository = OrganizationTeamRepository(db)
    org_member_repository = OrganizationMemberRepository(db)

    columns = [
        ("id", "id"),
        ("name", "name"),
        ("photo_url", "photo_url"),
        ("email", "email"),
        ("status", "status", lambda i: i.status.lower()),
        ("teams", "teams", lambda i: org_team_repository.find_by_member_id(i.id)),
        (
            "role",
            "role",
            lambda i: [
                role
                for role in [
                    "admin" if i.role == OrganizationMemberRoleEnum.admin else None,
                    "manager" if org_member_repository.is_manager_of_organization(i.id) else None,
                ]
                if role is not None
            ],
        ),
    ]
    if member_has_permissions(auth_member, "finance:view", db):
        columns.append(
            (
                "cost",
                "cost",
                lambda i: calculate_total_cost(float(i.hourly_cost), auth_organization.cost_period) if i.hourly_cost else None,
            )
        )

    query_members = org_member_repository.query_find_by_organization_id(auth_member.organization_id)
    return DBTable(query_members, columns).fetch_dicts()


class MemberRequest(BaseModel):
    emails: List[EmailStr]


@router.post("/member/")
def add_members_to_organization(
    member_info: MemberRequest,
    auth_member: OrganizationMember = Depends(get_auth_member),
    auth_org: Organization = Depends(get_auth_organization),
    db: Session = Depends(get_db),
    _: None = require_permission("members:create"),
):
    org_member_repository = OrganizationMemberRepository(db)

    existing_emails = []

    for email in member_info.emails:
        existing_member = org_member_repository.find_by_email(email=email)
        if existing_member:
            existing_emails.append(email)

    if existing_emails:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Some members already exist either in your organization or in another organization.",
                "existing_emails": existing_emails,
            },
        )

    for email in member_info.emails:
        member = OrganizationMember(
            organization_id=auth_member.organization_id,
            email=email,
            status=OrganizationMemberStatusEnum.pending,
        )
        send_user_invitation(email, administrator_name=auth_member.name, organisation_name=auth_org.name)
        org_member_repository.create(member)


class UpdateTeamMember(BaseModel):
    team_id: Optional[str] = None
    team_name: Optional[str] = None
    is_manager: Optional[bool] = False


class UpdateMember(BaseModel):
    cost: Optional[float]
    teams: Optional[List[UpdateTeamMember]]


def can_member_edit_member(editor: OrganizationMember, target: OrganizationMember, db: Session) -> bool:
    org_team_member_repository = OrganizationTeamMemberRepository(db)
    if editor.role == OrganizationMemberRoleEnum.admin:
        return True
    if org_team_member_repository.is_editor_manager_in_target_teams(editor.id, target.id):
        return True
    return False


@router.put("/member/{member_id}/")
def update_member(
    member_id: str,
    update_member: UpdateMember,
    auth_member: OrganizationMember = Depends(get_auth_member),
    auth_organization: Organization = Depends(get_auth_organization),
    db: Session = Depends(get_db),
    _: None = require_permission("members:edit"),
):
    org_member_repository = OrganizationMemberRepository(db)
    org_team_repository = OrganizationTeamRepository(db)
    org_team_member_repository = OrganizationTeamMemberRepository(db)

    member = org_member_repository.find_by_id(member_id)

    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    if not can_member_edit_member(auth_member, member, db):
        raise HTTPException(status_code=403, detail="You do not have permission to perform this action")

    hourly_cost = None
    if update_member.cost:
        hourly_cost = calculate_hourly_cost(update_member.cost, auth_organization.cost_period)
    member.hourly_cost = str(hourly_cost) if hourly_cost else None
    org_team_member_repository.update(member)

    db.query(OrganizationTeamMember).filter(OrganizationTeamMember.member_id == member.id).filter(
        OrganizationTeamMember.type == OrganizationTeamMemberTypeEnum.member
    ).delete()
    db.commit()
    for update_data in update_member.teams:
        if update_data.is_manager == False:
            team = org_team_repository.find_by_team_id(auth_organization.id, update_data.team_id)
            new_team_member = OrganizationTeamMember(
                team_id=team.id,
                member_id=member.id,
                type=OrganizationTeamMemberTypeEnum.manager if update_data.is_manager else OrganizationTeamMemberTypeEnum.member,
            )
            org_team_member_repository.create(new_team_member)


@router.delete("/member/{member_id}/")
def delete_member_from_organization(
    member_id: str,
    auth_member: OrganizationMember = Depends(get_auth_member),
    auth_organization: Organization = Depends(get_auth_organization),
    db: Session = Depends(get_db),
    _: None = require_permission("members:delete"),
):
    organization_member_repository = OrganizationMemberRepository(db)

    member = organization_member_repository.find_by_id(member_id)

    if not member or member.organization_id != auth_organization.id:
        raise HTTPException(status_code=404, detail="Member not found")

    organization_member_repository.delete(member)


@router.post("/member/{member_id}/resend-invitation")
def resend_invitation(
    member_id: str,
    auth_member: OrganizationMember = Depends(get_auth_member),
    auth_organization: Organization = Depends(get_auth_organization),
    db: Session = Depends(get_db),
    _: None = require_permission("members:create"),
):
    organization_member_repository = OrganizationMemberRepository(db)
    member = organization_member_repository.find_by_member_id(auth_organization.id, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    send_user_invitation(
        member.email,
        administrator_name=auth_member.name,
        organisation_name=auth_organization.name,
    )
