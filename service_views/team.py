from fastapi import FastAPI, Request, HTTPException, Depends, APIRouter, Form

from sqlalchemy.orm import Session

from models import get_db, User, Team, TeamMember
from models.repositories.user_repository import UserRepository, TeamRepository, TeamMemberRepository
from utils.auth import get_user

router = APIRouter()


@router.get("/team/")
def team(user: User = Depends(get_user), db: Session = Depends(get_db)):
    team_repository = TeamRepository(db)
    # team = team_repository.find_by_create_user_id(user.id)
    # if team is None:
    #     return []
    # return team_repository.find_by_team_member(team.id)
    return team_repository.find_by_team_member("")


@router.get("/team/chart/")
def team_chart():
    return {"data": [
        {"Date": "Jun 19", "Recurring": 70, "One-time": 30},
        {"Date": "Jun 20", "Recurring": 80, "One-time": 20},
        {"Date": "Jun 21", "Recurring": 50, "One-time": 20},
        {"Date": "Jul 16", "Recurring": 40, "One-time": 60},
        {"Date": "Jul 18", "Recurring": 40, "One-time": 10},
        {"Date": "Jul 19", "Recurring": 40, "One-time": 30},
        {"Date": "Jul 24", "Recurring": 40, "One-time": 60}
    ]}
