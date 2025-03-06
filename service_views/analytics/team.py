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
def generate_meetings_time_by_type(start_date: datetime, end_date: datetime, view_type: str):
    data = []
    current_date = start_date

    while current_date <= end_date:
        if view_type == "daily":
            formatted_date = current_date.strftime("%b %-d")
            current_date += timedelta(days=1)
        elif view_type == "weekly":
            week_start = current_date
            week_end = min(current_date + timedelta(days=6), end_date)
            formatted_date = f"{week_start.strftime('%b %-d')} - {week_end.strftime('%b %-d')}"
            current_date += timedelta(weeks=1)
        elif view_type == "monthly":
            month_start = current_date.replace(day=1)
            # Determine the last day of the month
            next_month = current_date.replace(day=28) + timedelta(days=4)
            month_end = next_month - timedelta(days=next_month.day)
            formatted_date = f"{month_start.strftime('%b')} {month_start.year}"
            current_date = month_end + timedelta(days=1)

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
        type_view: str = Query(...),
        user: User = Depends(authenticated_user),
        db: Session = Depends(get_db)
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")

    return generate_meetings_time_by_type(start_date_dt, end_date_dt, type_view)


@router.get("/analytic/team/meeting/time")
def get_team_meeting_time(
        team_id: int = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        type_view: str = Query(...),
        user: User = Depends(authenticated_user),
        db: Session = Depends(get_db)
):
    pass


@router.get("/analytic/team/meeting/participants")
def get_team_meeting_participants(
        team_id: int = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        type_view: str = Query(...),
        user: User = Depends(authenticated_user),
        db: Session = Depends(get_db)
):
    pass
