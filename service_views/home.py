from fastapi import Depends, APIRouter, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from models import get_db, User
from models.repositories.user_repository import UserRepository

from datetime import datetime, timedelta
from utils.middleware import get_auth_user
from utils.meet import get_calendar_events

from utils.analytics import get_google_access_token

from utils.analytics.calendar_stats import count_events, calculate_total_events_duration
from utils.analytics.kpi import kpi_total_time, kpi_avg_daily_meetings_time, \
    kpi_cancelled_meetings, kpi_count_meetings, kpi_meetings_ratio, kpi_deep_work_time

router = APIRouter()


@router.get("/home/kpi")
def get_user_kpi(
    user: User = Depends(get_auth_user),
    db: Session = Depends(get_db)
):
    today = datetime.today()

    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    start_date = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = end_of_week.replace(hour=23, minute=59, second=59, microsecond=999999)

    prev_start_of_week = start_of_week - timedelta(days=7)
    prev_end_of_week = end_of_week - timedelta(days=7)

    prev_start_date = prev_start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    prev_end_date = prev_end_of_week.replace(hour=23, minute=59, second=59, microsecond=999999)

    access_token = get_google_access_token(user.email, db)
    events = get_calendar_events(access_token, start_date, end_date)
    prev_events = get_calendar_events(access_token, prev_start_date, prev_end_date)

    return [
        {"title": "Time on meetings", **kpi_total_time(events, prev_events)},
        {"title": "Meetings count", **kpi_count_meetings(events, prev_events)},
        {"title": "Deep work time",  **kpi_deep_work_time(events, prev_events)},
    ]
