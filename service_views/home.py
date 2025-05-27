from fastapi import Depends, APIRouter, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from models import get_db, User
from models.repositories.user_repository import UserRepository
from pydantic import BaseModel, validator
from datetime import datetime, timedelta
from utils.middleware import get_auth_user
from utils.meet import get_calendar_events, create_calendar_event

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
        {"title": "Deep work time", **kpi_deep_work_time(events, prev_events)},
    ]


def find_week_free_slots(start_date: datetime, end_date: datetime, busy_slots,
                         work_start="10:00", work_end="19:00",
                         min_duration=timedelta(hours=2)):
    free_slots = []

    busy_by_day = {}
    for s, e in busy_slots:
        start_dt = datetime.fromisoformat(s)
        end_dt = datetime.fromisoformat(e)
        day = start_dt.date()
        busy_by_day.setdefault(day, []).append((start_dt, end_dt))

    current_date = start_date
    while current_date.date() <= end_date.date():
        day = current_date.date()
        work_start_dt = datetime.combine(day, datetime.strptime(work_start, "%H:%M").time())
        work_end_dt = datetime.combine(day, datetime.strptime(work_end, "%H:%M").time())
        busy = sorted(busy_by_day.get(day, []))

        current = work_start_dt
        for b_start, b_end in busy:
            if b_start > current and b_start - current >= min_duration:
                free_slots.append((current, b_start))
            current = max(current, b_end)

        if work_end_dt - current >= min_duration:
            free_slots.append((current, work_end_dt))

        current_date += timedelta(days=1)

    result = []
    for (s, e) in free_slots:
        result.append({
            "startTime": s.strftime("%H:%M:%S"),
            "endTime": e.strftime("%H:%M:%S"),
            "date": s.strftime("%Y-%m-%d"),
            "duration": round((e - s).total_seconds() / 3600, 2)
        })
    return result


@router.get("/home/deep-work/time-slot")
def get_deep_work_slot(
        user: User = Depends(get_auth_user),
        db: Session = Depends(get_db)
):
    today = datetime.today()

    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    start_date = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = end_of_week.replace(hour=23, minute=59, second=59, microsecond=999999)

    access_token = get_google_access_token(user.email, db)
    events = get_calendar_events(access_token, start_date, end_date)
    busy_times = []
    for event in events:
        start_str = event.get("start", {}).get("dateTime", "").split("+")[0]
        end_str = event.get("end", {}).get("dateTime", "").split("+")[0]
        if start_str and end_str:
            busy_times.append((start_str, end_str))
    free_slots = find_week_free_slots(start_date, end_date, busy_times)
    return {
        "slots": free_slots,
    }



class TimeSlot(BaseModel):
    start_time: datetime
    end_time: datetime

    @validator('start_time', 'end_time', pre=True)
    def parse_datetime(cls, value):
        if isinstance(value, datetime):
            return value
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")



@router.post("/home/deep-work/time-slot")
def post_deep_work_slot(
        timeslot: TimeSlot,
        user: User = Depends(get_auth_user),
        db: Session = Depends(get_db)
):
    access_token = get_google_access_token(user.email, db)

    summary = "Deep Work Time"
    event = create_calendar_event(
        token=access_token,
        summary=summary,
        start_time=timeslot.start_time,
        end_time=timeslot.end_time,
    )
    return event

