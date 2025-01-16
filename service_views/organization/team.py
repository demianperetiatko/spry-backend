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


class TeamRequest(BaseModel):
    name: str
    member_ids: List[int]


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
        db: Session = Depends(get_db)
):
    org_repository = OrganizationRepository(db)
    team_repository = OrganizationTeamRepository(db)
    org = org_repository.find_by_user(user)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    team = OrganizationTeam(
        name=team_info.name,
        organization_id=org.id,
    )
    team_repository.create(team)
    for member_id in team_info.member_ids:
        team_repository.create(OrganizationTeamMember(team_id=team.id, member_id=member_id))
    return
