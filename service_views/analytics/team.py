from fastapi import Depends, APIRouter, HTTPException, Query

from sqlalchemy.orm import Session

from models import get_db, User

from models.repositories.user_repository import UserRepository
from models.repositories.organization_repository import OrganizationRepository, OrganizationMemberRepository, \
    OrganizationTeamRepository, OrganizationTeamMemberRepository

from utils.services import authenticated_user, refresh_google_access_token
from utils.meet import get_calendar_events

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


def get_events_for_day(events, date):
    events_for_day = []
    for event in events:
        event_start = datetime.fromisoformat(event['start']['dateTime'])
        event_end = datetime.fromisoformat(event['end']['dateTime'])
        if event_start.date() == date.date() or event_end.date() == date.date():
            events_for_day.append(event)
    return events_for_day


@router.get("/analytic/team/meeting")
def get_team_meetings(
        team_id: int = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        user: User = Depends(authenticated_user),
        db: Session = Depends(get_db)
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    user_repository = UserRepository(db)
    org_repository = OrganizationRepository(db)
    team_repository = OrganizationTeamRepository(db)
    team_member_repository = OrganizationTeamMemberRepository(db)
    org = org_repository.find_by_user(user)

    events = []
    count_team_member = 0
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    team = team_repository.find_by_team_id(org.id, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    team_members = team_member_repository.find_by_team_id(team.id)
    for t_member in team_members:
        user = user_repository.find_by_email(t_member.email)
        if not user or not user.google_refresh_token:
            print("analytic not correct")
        else:
            access_token = refresh_google_access_token(user.google_refresh_token)
            user_events = get_calendar_events(access_token, start_date_dt, end_date_dt)
            events += user_events
            count_team_member += 1

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
        external = 0
        total_time_per_member = 0
        member_count = 0

        for event in events_on_day:
            print(formatted_date)
            if 'recurringEventId' in event:
                recurring += 1
            else:
                one_time += 1

            if 'conferenceData' in event and event['conferenceData'].get('entryPoints'):
                external += 1

            start_time = datetime.fromisoformat(event['start']['dateTime'])
            end_time = datetime.fromisoformat(event['end']['dateTime'])
            event_duration = (end_time - start_time).total_seconds() / 60
            total_time_per_member += event_duration

        avg_time_per_member = total_time_per_member / count_team_member if count_team_member else 0
        avg_cost_per_member = 0

        formatted_analytic.append({
            "date": formatted_date,
            "recurring": recurring,
            "one-time": one_time,
            "external": external,
            "avgTimePerMember": avg_time_per_member,
            "avgCostPerMember": avg_cost_per_member
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
            '2:5': random.randint(1, 5),
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
