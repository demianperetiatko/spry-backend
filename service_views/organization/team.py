from typing import List
from fastapi import Depends, APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from sqlalchemy.orm import Session

from models import get_db, User
from models.repositories.organization_repository import OrganizationRepository, OrganizationMemberRepository

from models import OrganizationTeam, OrganizationTeamMember
from models.repositories.organization_repository import OrganizationTeamRepository, OrganizationMemberRepository

from utils.services import authenticated_user

router = APIRouter()


class TeamMemberRequest(BaseModel):
    member_id: int
    type: str


class TeamRequest(BaseModel):
    name: str
    team_members: List[TeamMemberRequest]


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
