from typing import List
from fastapi import Depends, APIRouter, HTTPException
from pydantic import BaseModel, field_validator, model_validator

from sqlalchemy.orm import Session

from models import get_db, User
from models.repositories.organization_repository import OrganizationRepository, OrganizationMemberRepository

from models import OrganizationTeam, OrganizationTeamMember, OrganizationTeamMemberType
from models.repositories.organization_repository import OrganizationTeamRepository, OrganizationTeamMemberRepository

from utils.services import authenticated_user

router = APIRouter()


class TeamMemberRequest(BaseModel):
    member_id: int
    type: str

    @field_validator("type")
    def validate_currency(cls, value):
        if value not in OrganizationTeamMemberType.ALLOWED_PERIODS:
            raise ValueError(
                f"Invalid value for type. Allowed values are: {', '.join(OrganizationTeamMemberType.ALLOWED_PERIODS)}"
            )
        return value


class TeamRequest(BaseModel):
    name: str
    team_members: List[TeamMemberRequest]

    @model_validator(mode='before')
    def validate_manager(cls, values):
        team_members = values.get('team_members', [])
        manager_count = sum(1 for member in team_members if member.get('type') == OrganizationTeamMemberType.MANAGER)

        if manager_count != 1:
            raise ValueError(f"There must be exactly one member with type '{OrganizationTeamMemberType.MANAGER}'.")

        return values


@router.get("/team/")
def get_teams(user: User = Depends(authenticated_user), db: Session = Depends(get_db)):
    org_repository = OrganizationRepository(db)
    team_repository = OrganizationTeamRepository(db)
    org = org_repository.find_by_user(user)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    teams = team_repository.find_by_organization_id(org.id)
    return {
        'data': teams,
        'total_count': len(teams)
    }


@router.get("/team/{team_id}")
def get_team_by_id(team_id: int, user: User = Depends(authenticated_user), db: Session = Depends(get_db)):
    org_repository = OrganizationRepository(db)
    team_repository = OrganizationTeamRepository(db)
    team_member_repository = OrganizationTeamMemberRepository(db)
    org = org_repository.find_by_user(user)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    team = team_repository.find_by_team_id(org.id, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    team_members = team_member_repository.find_by_team_id(team.id)
    return {"team_id": team.id, "name": team.name, "team_members": team_members}


@router.post("/team/")
def create_team(
        team_info: TeamRequest,
        user: User = Depends(authenticated_user),
        db: Session = Depends(get_db),
):
    org_repository = OrganizationRepository(db)
    team_repository = OrganizationTeamRepository(db)
    org = org_repository.find_by_user(user)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    team = OrganizationTeam(name=team_info.name, organization_id=org.id)
    team_repository.create(team)

    for member_info in team_info.team_members:
        team_member = OrganizationTeamMember(
            team_id=team.id,
            member_id=member_info.member_id,
            type=member_info.type,
        )
        team_repository.create(team_member)


@router.put("/team/{team_id}")
def update_team(
        team_id: int,
        team_info: TeamRequest,
        user: User = Depends(authenticated_user),
        db: Session = Depends(get_db),
):
    org_repository = OrganizationRepository(db)
    team_repository = OrganizationTeamRepository(db)
    team_member_repository = OrganizationTeamMemberRepository(db)

    org = org_repository.find_by_user(user)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    team = team_repository.find_by_team_id(org.id, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

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
def delete_team(team_id: int, user: User = Depends(authenticated_user), db: Session = Depends(get_db)):
    org_repository = OrganizationRepository(db)
    team_repository = OrganizationTeamRepository(db)
    team_member_repository = OrganizationTeamMemberRepository(db)
    org = org_repository.find_by_user(user)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    team = team_repository.find_by_team_id(org.id, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    team_member_repository.delete_all_team_member(team.id)
    team_repository.delete(team)
    return
