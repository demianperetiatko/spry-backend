import random
from datetime import datetime, timedelta

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


def generate_data(num_days):
    data = []
    start_date = datetime.now() - timedelta(days=int(num_days/2))

    for i in range(num_days):
        date = start_date + timedelta(days=i)
        formatted_date = date.strftime("%b %d")
        recurring = random.randint(30, 90)
        one_time = random.randint(10, 60)
        data.append({"Date": formatted_date, "Recurring": recurring, "One-time": one_time})

    return {"data": data}
@router.get("/team/chart/")
def team_chart():
    return generate_data(30)