from typing import List

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from pydantic import BaseModel
from pydantic import field_validator
from pydantic import model_validator
from sqlalchemy.orm import Session

from models import get_db
from models.organization import Organization
from models.organization_member import OrganizationMember
from models.organization_member import OrganizationMemberRoleEnum
from models.organization_team import OrganizationTeam
from models.organization_team import OrganizationTeamMember
from models.organization_team import OrganizationTeamMemberTypeEnum
from models.repositories.organization_team_repository import OrganizationTeamMemberRepository
from models.repositories.organization_team_repository import OrganizationTeamRepository
from utils.middleware import get_auth_member
from utils.middleware import get_auth_organization
from utils.middleware import require_permission
from utils.table import DBTable

router = APIRouter()


class TeamMemberRequest(BaseModel):
    member_id: str
    type: str

    @field_validator("type")
    def validate_currency(cls, value):
        ALLOWED_PERIODS = [
            OrganizationTeamMemberTypeEnum.member,
            OrganizationTeamMemberTypeEnum.manager,
        ]
        if value not in ALLOWED_PERIODS:
            raise ValueError(f"Invalid value for type. Allowed values are: {', '.join(ALLOWED_PERIODS)}")
        return value


class TeamRequest(BaseModel):
    name: str
    team_members: List[TeamMemberRequest]

    @model_validator(mode="before")
    def validate_manager(cls, values):
        team_members = values.get("team_members", [])
        manager_count = sum(1 for member in team_members if member.get("type") == OrganizationTeamMemberTypeEnum.manager)

        if manager_count != 1:
            raise ValueError(f"There must be exactly one member with type '{OrganizationTeamMemberTypeEnum.manager}'.")

        return values


@router.get("/team/")
def get_teams(
    auth_member: OrganizationMember = Depends(get_auth_member),
    auth_organization: Organization = Depends(get_auth_organization),
    db: Session = Depends(get_db),
    _: None = require_permission("teams:view"),
):
    org_team_repository = OrganizationTeamRepository(db)
    org_team_member_repository = OrganizationTeamMemberRepository(db)

    columns = [
        ("id", "id"),
        ("name", "name"),
        ("manager_id", "manager_id"),
        ("manager_email", "manager_email"),
        ("manager_name", "manager_name"),
        ("manager_photo", "manager_photo"),
        (
            "members",
            "members",
            lambda i: org_team_member_repository.find_by_team_id(i.id),
        ),
        (
            "members_count",
            "members_count",
            lambda i: org_team_member_repository.query_find_by_team_id(i.id).count(),
        ),
    ]
    query_teams = org_team_repository.query_find_by_organization_id(auth_organization.id)
    return DBTable(query_teams, columns).fetch_dicts()


@router.get("/team/{team_id}")
def get_team_by_id(
    team_id: str,
    auth_member: OrganizationMember = Depends(get_auth_member),
    auth_organization: Organization = Depends(get_auth_organization),
    db: Session = Depends(get_db),
    _: None = require_permission("teams:view"),
):
    team_repository = OrganizationTeamRepository(db)
    team_member_repository = OrganizationTeamMemberRepository(db)

    team = team_repository.find_by_team_id(auth_organization.id, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    team_members = team_member_repository.find_by_team_id(team.id)
    return {"team_id": team.id, "name": team.name, "team_members": team_members}


@router.post("/team/")
def create_team(
    team_info: TeamRequest,
    auth_member: OrganizationMember = Depends(get_auth_member),
    auth_organization: Organization = Depends(get_auth_organization),
    db: Session = Depends(get_db),
    _: None = require_permission("teams:create"),
):
    team_repository = OrganizationTeamRepository(db)

    team = OrganizationTeam(name=team_info.name, organization_id=auth_organization.id)
    team_repository.create(team)

    for member_info in team_info.team_members:
        team_member = OrganizationTeamMember(
            team_id=team.id,
            member_id=member_info.member_id,
            type=member_info.type,
        )
        team_repository.create(team_member)


def can_member_edit_team(team: OrganizationTeam, member: OrganizationMember, db: Session):
    if member.role == OrganizationMemberRoleEnum.admin:
        return True
    team_member_rep = OrganizationTeamMemberRepository(db)
    if team_member_rep.is_member_manager(team.id, member.id):
        return True
    return False


@router.put("/team/{team_id}")
def update_team(
    team_id: str,
    team_info: TeamRequest,
    auth_member: OrganizationMember = Depends(get_auth_member),
    auth_organization: Organization = Depends(get_auth_organization),
    db: Session = Depends(get_db),
    _: None = require_permission("teams:edit"),
):
    team_repository = OrganizationTeamRepository(db)
    team_member_repository = OrganizationTeamMemberRepository(db)

    team = team_repository.find_by_team_id(auth_organization.id, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    if not can_member_edit_team(team, auth_member, db):
        raise HTTPException(status_code=403, detail="You do not have permission to perform this action")

    team.name = team_info.name
    team_repository.update(team)

    team_member_repository.delete_all_team_member(team.id)

    for member_info in team_info.team_members:
        team_member = OrganizationTeamMember(
            team_id=team.id,
            member_id=member_info.member_id,
            type=member_info.type,
        )
        team_member_repository.create(team_member)

    return {"message": "Team updated successfully"}


@router.delete("/team/{team_id}")
def delete_team(
    team_id: str,
    auth_member: OrganizationMember = Depends(get_auth_member),
    auth_organization: Organization = Depends(get_auth_organization),
    db: Session = Depends(get_db),
    _: None = require_permission("teams:delete"),
):
    team_repository = OrganizationTeamRepository(db)
    team_member_repository = OrganizationTeamMemberRepository(db)

    team = team_repository.find_by_team_id(auth_organization.id, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    team_member_repository.delete_all_team_member(team.id)
    team_repository.delete(team)
