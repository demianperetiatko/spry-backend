from fastapi import FastAPI, Request, HTTPException, Depends, APIRouter, Form

from sqlalchemy.orm import Session

from models import get_db, User, Team, TeamMember
from models.repositories.user_repository import UserRepository, TeamRepository, TeamMemberRepository
from utils.auth import get_user


router = APIRouter()

@router.get("/team/")
def team(user: User = Depends(get_user), db: Session = Depends(get_db)):
    team_repository = TeamRepository(db)
    team = team_repository.find_by_create_user_id(user.id)
    if team is None:
        return []
    return team_repository.find_by_team_member(team.id)



@router.get("/team/chart/")
def team_chart():
    return {"data": [
        ['Date', 'Recurring', 'One-time'],
        ['Jun 19', 70, 30],
        ['Jun 20', 80, 20],
        ['Jun 21', 50, 20],
        ['Jul 16', 40, 60],
        ['Jul 18', 40, 10],
        ['Jul 19', 40, 30],
        ['Jul 24', 40, 60]
    ]}
