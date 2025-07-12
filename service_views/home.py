from fastapi import Depends, APIRouter, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator, model_validator
from typing import List
from models import get_db
from models import OrganizationMember
from utils.google_api import refresh_google_access_token

from datetime import datetime, timedelta
from utils.middleware import get_auth_member
from utils.google_api import get_calendar_events, get_calendar_event_info
from utils.analytics.filters import filter_meetings, filter_by_title
from utils.send_message import send_agenda_request

from utils.analytics.calendar_stats import count_events, calculate_total_events_duration
from utils.analytics.kpi import kpi_total_time, kpi_avg_daily_meetings_time, \
    kpi_cancelled_meetings, kpi_count_meetings, kpi_meetings_ratio, kpi_deep_work_time

from models.agenda import AgendaBeta
from models.repositories.agenda_repository import AgendaBetaRepository

from utils.google_api import create_calendar_event, update_calendar_event

from utils import get_user_profile

router = APIRouter()


@router.get("/home/kpi")
def get_user_kpi(
        auth_member: OrganizationMember = Depends(get_auth_member),
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

    access_token = refresh_google_access_token(auth_member.google_refresh_token)
    events = filter_meetings(filter_meetings(get_calendar_events(access_token, start_date, end_date)))
    prev_events = filter_meetings(filter_meetings(get_calendar_events(access_token, prev_start_date, prev_end_date)))

    return {
        'data': [
            {"title": "Time on meetings", **kpi_total_time(events, prev_events)},
            {"title": "Meetings count", **kpi_count_meetings(events, prev_events)},
            {"title": "Deep work time", **kpi_deep_work_time(events, prev_events, 7)},
        ]
    }


def find_week_free_slots(start_date: datetime, end_date: datetime, busy_slots,
                         work_start="10:00", work_end="18:00",
                         min_duration=timedelta(hours=2)):
    free_slots = []

    busy_by_day = {}
    for s, e in busy_slots:
        start_dt = datetime.fromisoformat(s)
        end_dt = datetime.fromisoformat(e)
        day = start_dt.date()
        busy_by_day.setdefault(day, []).append((start_dt, end_dt))

    now = datetime.now()
    current_date = start_date
    while current_date.date() <= end_date.date():
        if current_date.weekday() >= 5:
            current_date += timedelta(days=1)
            continue

        day = current_date.date()
        work_start_time = datetime.strptime(work_start, "%H:%M").time()
        work_end_time = datetime.strptime(work_end, "%H:%M").time()

        work_start_dt = datetime.combine(day, work_start_time)
        work_end_dt = datetime.combine(day, work_end_time)

        if day == now.date():
            work_start_dt = max(work_start_dt, now)
            if work_start_dt >= work_end_dt:
                current_date += timedelta(days=1)
                continue

        busy = [
            (max(start, work_start_dt), min(end, work_end_dt))
            for start, end in busy_by_day.get(day, [])
            if start < work_end_dt and end > work_start_dt
        ]
        busy.sort()

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
        auth_member: OrganizationMember = Depends(get_auth_member),
        db: Session = Depends(get_db)
):
    today = datetime.today()
    start_date = today
    end_date = (today + timedelta(days=14)).replace(hour=23, minute=59, second=59, microsecond=999999)

    access_token = refresh_google_access_token(auth_member.google_refresh_token)
    events = get_calendar_events(access_token, start_date, end_date)
    busy_times = []
    for event in filter_meetings(events) + filter_by_title(events, "Deep Work Time"):
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

    @model_validator(mode='after')
    def check_time_order(self):
        if self.start_time >= self.end_time:
            raise ValueError("`start_time` must be earlier than `end_time`.")
        return self


@router.post("/home/deep-work/time-slot")
def post_deep_work_slots(
        timeslots: List[TimeSlot],
        auth_member: OrganizationMember = Depends(get_auth_member),
        db: Session = Depends(get_db)
):
    access_token = refresh_google_access_token(auth_member.google_refresh_token)

    summary = "Deep Work Time"
    events = []
    for timeslot in timeslots:
        event = create_calendar_event(
            token=access_token,
            summary=summary,
            start_time=timeslot.start_time,
            end_time=timeslot.end_time,
        )
        events.append(event)

    return events


@router.get("/home/agenda-beta")
def get_agenda_beta(
        auth_member: OrganizationMember = Depends(get_auth_member),
        db: Session = Depends(get_db)
):
    agenda_repository = AgendaBetaRepository(db)

    today = datetime.today()
    start_date = today
    end_date = (today + timedelta(days=14)).replace(hour=23, minute=59, second=59, microsecond=999999)

    access_token = refresh_google_access_token(auth_member.google_refresh_token)
    events = filter_meetings(get_calendar_events(access_token, start_date, end_date))
    meetings = []
    for event in events:
        if 'description' in event:
            continue

        start_time = event["start"]["dateTime"]
        end_time = event["end"]["dateTime"]
        organizer_email = event.get("organizer", {}).get("email", "")
        date = start_time.split("T")[0]
        agenda = agenda_repository.find_by_event_id(event["id"], auth_member.id)
        meeting = {
            "id": event["id"],
            "name": event.get("summary", "No Title"),
            "start_time": start_time,
            "end_time": end_time,
            "date": date,
            "members": [get_user_profile(a["email"], db) for a in event.get("attendees", []) if "email" in a],
            "organizer": get_user_profile(organizer_email, db),
            "is_organizer": auth_member.email == organizer_email,
            "invitation_sent": True if agenda else False
        }
        meetings.append(meeting)
    return {
        "meetings": meetings,
        "count_all_events": len(events),
    }


@router.post("/home/agenda-beta/{event_id}/notify")
def notify_agenda_completed(
        event_id: str,
        auth_member: OrganizationMember = Depends(get_auth_member),
        db: Session = Depends(get_db)
):
    access_token = refresh_google_access_token(auth_member.google_refresh_token)
    event = get_calendar_event_info(access_token, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    organizer_email = event.get("organizer", {}).get("email")
    if not organizer_email:
        raise HTTPException(status_code=400, detail="Organizer email not found")
    agenda_repository = AgendaBetaRepository(db)
    agenda = agenda_repository.find_by_event_id(event_id, auth_member.id)
    if not agenda:
        new_agenda = AgendaBeta(
            event_id=event_id,
            member_id=auth_member.id
        )
        agenda_repository.create(new_agenda)
        send_agenda_request(organizer_email, event.get('htmlLink'))


class AgendaDescriptionRequest(BaseModel):
    description: str


@router.post("/home/agenda-beta/{event_id}/add")
def add_agenda_description(
        event_id: str,
        data: AgendaDescriptionRequest,
        auth_member: OrganizationMember = Depends(get_auth_member),
        db: Session = Depends(get_db)
):
    access_token = refresh_google_access_token(auth_member.google_refresh_token)

    updated_event = update_calendar_event(
        access_token=access_token,
        calendar_id="primary",
        event_id=event_id,
        description=data.description
    )
