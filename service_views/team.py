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


def generate_data(start_date: datetime, end_date: datetime, view_type: str):
    data = []
    current_date = start_date

    while current_date <= end_date:
        if view_type == "day":
            formatted_date = current_date.strftime("%b %d")  # формат yyyy-MM-dd
            current_date += timedelta(days=1)
        elif view_type == "week":
            week_start = current_date
            week_end = min(current_date + timedelta(days=6), end_date)
            formatted_date = f"{week_start.strftime('%b %d')} - {week_end.strftime('%b %d')}"
            current_date += timedelta(weeks=1)

        recurring = random.randint(30, 90)
        one_time = random.randint(10, 60)
        data.append({"Date": formatted_date, "Recurring": recurring, "One-time": one_time})

    return {"data": data}
@router.get("/team/chart/")
def team_chart(start_date: str, end_date: str, type: str):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")

    return generate_data(start_date_dt, end_date_dt, type)