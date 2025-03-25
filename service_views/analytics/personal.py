from fastapi import Depends, APIRouter, HTTPException, Query

from sqlalchemy.orm import Session

from models import get_db, User

from models.repositories.user_repository import UserRepository

from models.repositories.organization_repository import OrganizationRepository, OrganizationMemberRepository, \
    OrganizationTeamRepository, OrganizationTeamMemberRepository
from utils.services import authenticated_user, refresh_google_access_token
from utils.meet import get_calendar_events

router = APIRouter()


@router.get("/analytic/personal/meeting/kpi")
def get_personal_kpi(
        member_id: int = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        user: User = Depends(authenticated_user),
        db: Session = Depends(get_db)
):
    return {
        'data': [
            {"name": "total_time", "title": "Total time on meetings", "value": "124 h", "change": "+12%"},
            {"name": "avg_time_per_member", "title": "Avg. daily meetings time", "value": "2.4 h", "change": "+12%"},
            {"name": "total_cost", "title": "Meetings count", "value": "123", "change": "+12%"},
            {"name": "avg_cost_per_member", "title": "Meetings ratio", "value": "55%", "change": "+12%"},
            {"name": "meetings_count", "title": "Cancelled meetings", "value": "11", "change": "+12%"},
        ]
    }


import random
from datetime import datetime, timedelta


def get_events_for_day(events, date):
    events_for_day = []
    for event in events:
        event_start = datetime.fromisoformat(event['start']['dateTime'])
        event_end = datetime.fromisoformat(event['end']['dateTime'])
        if event_start.date() == date.date() or event_end.date() == date.date():
            events_for_day.append(event)
    return events_for_day


@router.get("/analytic/personal/meeting")
def get_personal_meetings(
        member_id: int = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        user: User = Depends(authenticated_user),
        db: Session = Depends(get_db)
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    user_repository = UserRepository(db)
    org_member_repository = OrganizationMemberRepository(db)
    member = org_member_repository.find_by_id(member_id)
    user = user_repository.find_by_email(member.email)
    access_token = refresh_google_access_token(user.google_refresh_token)
    events = get_calendar_events(access_token, start_date_dt, end_date_dt)

    current_date = start_date_dt
    events_by_date = {}

    while current_date <= end_date_dt:
        events_for_day = get_events_for_day(events, current_date)
        events_by_date[current_date.date()] = events_for_day
        current_date += timedelta(days=1)

    formatted_analytic = []
    for date, events_on_day in events_by_date.items():
        formatted_date = date.strftime("%Y-%m-%d")
        recurring = 0
        one_time = 0

        for event in events_on_day:
            if 'recurringEventId' in event:
                recurring += 1
            else:
                one_time += 1

        formatted_analytic.append({
            "date": formatted_date,
            "recurring": recurring,
            "one-time": one_time,
        })
    return {'data': formatted_analytic}


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
            '1:1': random.randint(0, 3),
            '3-5': random.randint(1, 5),
            '>5': random.randint(0, 2),
        }

        data.append({
            "date": formatted_date,
            **participants
        })

    return {"data": data}


@router.get("/analytic/personal/meeting/time")
def get_personal_meeting_time(
        member_id: int = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        user: User = Depends(authenticated_user),
        db: Session = Depends(get_db)
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")
    return generate_meetings_time_ratio(start_date_dt, end_date_dt)



@router.get("/analytic/personal/meeting/participants")
def get_personal_meeting_participants(
        member_id: int = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        user: User = Depends(authenticated_user),
        db: Session = Depends(get_db)
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")
    return generate_meetings_by_participants(start_date_dt, end_date_dt)
