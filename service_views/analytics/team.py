from fastapi import Depends, APIRouter, HTTPException, Query

from sqlalchemy.orm import Session

from models import get_db, User

from utils.services import authenticated_user

router = APIRouter()


@router.get("/analytic/team/meeting/kpi")
def get_team_kpi(
        team_id: int = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        user: User = Depends(authenticated_user),
        db: Session = Depends(get_db)
):
    return {
        'data': [
            {"name": "total_time", "title": "Total Time", "value": "4,034 h", "change": "+12%"},
            {"name": "avg_time_per_member", "title": "Avg Time Per Member", "value": "40 h", "change": "+12%"},
            {"name": "total_cost", "title": "Total Cost", "value": "$1,234", "change": "+12%"},
            {"name": "avg_cost_per_member", "title": "Avg Cost Per Member", "value": "$2,400", "change": "+12%"},
            {"name": "meetings_count", "title": "Meetings Count", "value": "123", "change": "+12%"},
            {"name": "meetings_ratio", "title": "Meetings Ratio", "value": "55%", "change": "+12%"},
            {"name": "meetings_with_agenda", "title": "Meetings with Agenda", "value": "55%", "change": "+12%"},
        ]
    }


import random
from datetime import datetime, timedelta


def generate_meetings_time_by_type(start_date: datetime, end_date: datetime):
    data = []
    current_date = start_date

    while current_date <= end_date:
        formatted_date = current_date.strftime("%Y-%m-%d")
        current_date += timedelta(days=1)

        recurring = random.randint(30, 90)
        one_time = random.randint(10, 60)
        external = random.randint(5, 30)
        avg_time_per_member = random.randint(20, 60)
        avg_cost_per_member = random.randint(10, 50)

        data.append({
            "date": formatted_date,
            "recurring": recurring,
            "one-time": one_time,
            "external": external,
            "avgTimePerMember": avg_time_per_member,
            "avgCostPerMember": avg_cost_per_member,
        })

    return {"data": data}


@router.get("/analytic/team/meeting")
def get_team_meetings(
        team_id: int = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        user: User = Depends(authenticated_user),
        db: Session = Depends(get_db)
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")
    return generate_meetings_time_by_type(start_date_dt, end_date_dt)


def generate_meetings_time_ratio(start_date: datetime, end_date: datetime):
    data = []
    current_date = start_date

    while current_date <= end_date:
        formatted_date = current_date.strftime("%Y-%m-%d")
        current_date += timedelta(days=1)

        ratio = random.randint(5, 15)

        data.append({
            "date": formatted_date,
            "ratio": ratio,
        })

    return {"data": data}


# Data for generating participants by meeting size
def generate_meetings_by_participants(start_date: datetime, end_date: datetime):
    data = []
    current_date = start_date

    while current_date <= end_date:
        formatted_date = current_date.strftime("%Y-%m-%d")
        current_date += timedelta(days=1)

        participants = {
            '1-1': random.randint(0, 3),
            '2-5': random.randint(1, 5),
            '6+': random.randint(0, 2),
        }

        data.append({
            "date": formatted_date,
            **participants
        })

    return {"data": data}


@router.get("/analytic/team/meeting/time")
def get_team_meeting_time(
        team_id: int = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        user: User = Depends(authenticated_user),
        db: Session = Depends(get_db)
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")
    return generate_meetings_time_ratio(start_date_dt, end_date_dt)


# Endpoint to get the team meeting participants
@router.get("/analytic/team/meeting/participants")
def get_team_meeting_participants(
        team_id: int = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        user: User = Depends(authenticated_user),
        db: Session = Depends(get_db)
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")
    return generate_meetings_by_participants(start_date_dt, end_date_dt)
