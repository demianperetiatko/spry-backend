from fastapi import Depends, APIRouter, HTTPException, Query

from sqlalchemy.orm import Session

from models import get_db, User, Organization

from models.repositories.organization_repository import OrganizationRepository, OrganizationMemberRepository, \
    OrganizationTeamRepository, OrganizationTeamMemberRepository


from utils.middleware import get_auth_user, get_organization
from utils.meet import get_calendar_events

from utils.analytics import get_google_access_token

from utils.analytics import group_events_by_date, calculate_event_ratio
from utils.analytics import count_event_attendees_one_to_one, count_event_attendees_three_to_five, \
    count_event_attendees_more_than_five
from utils.analytics import count_recurring_events, count_one_time_events

from datetime import datetime, timedelta

router = APIRouter()


@router.get("/analytic/team/meeting/kpi")
def get_team_kpi(
        team_id: int = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        user: User = Depends(get_auth_user),
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


@router.get("/analytic/team/meeting")
def get_team_meetings(
        team_id: int = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        user: User = Depends(get_auth_user),
        org: Organization = Depends(get_organization),
        db: Session = Depends(get_db)
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    events = []

    org_team_repository = OrganizationTeamRepository(db)
    org_team_member_repository = OrganizationTeamMemberRepository(db)

    org_team = org_team_repository.find_by_team_id(org.id, team_id)
    if not org_team:
        raise HTTPException(status_code=404, detail="Team not found")

    org_team_members = org_team_member_repository.find_by_team_id(org_team.id)
    for member in org_team_members:
        access_token = get_google_access_token(member.email, db)
        member_events = get_calendar_events(access_token, start_date_dt, end_date_dt)
        events += member_events

    events_by_date = group_events_by_date(list(set(events)), start_date_dt, end_date_dt)

    formatted_analytic = [
        {
            "date": date.strftime("%Y-%m-%d"),
            "recurring": count_recurring_events(events_on_day),
            "one-time": count_one_time_events(events_on_day),
            "external": 0,
            "avgTimePerMember": 0,
            "avgCostPerMember": 0

        }
        for date, events_on_day in events_by_date.items()
    ]

    return {'data': formatted_analytic}


@router.get("/analytic/team/meeting/participants")
def get_team_meeting_participants(
        team_id: int = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        user: User = Depends(get_auth_user),
        org: Organization = Depends(get_organization),
        db: Session = Depends(get_db)
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    events = []

    org_team_repository = OrganizationTeamRepository(db)
    org_team_member_repository = OrganizationTeamMemberRepository(db)

    org_team = org_team_repository.find_by_team_id(org.id, team_id)
    if not org_team:
        raise HTTPException(status_code=404, detail="Team not found")

    org_team_members = org_team_member_repository.find_by_team_id(org_team.id)
    for member in org_team_members:
        access_token = get_google_access_token(member.email, db)
        member_events = get_calendar_events(access_token, start_date_dt, end_date_dt)
        events += member_events

    events_by_date = group_events_by_date(list(set(events)), start_date_dt, end_date_dt)

    formatted_analytic = [
        {
            "date": date.strftime("%Y-%m-%d"),
            "1:1": count_event_attendees_one_to_one(events_on_day),
            "3-5": count_event_attendees_three_to_five(events_on_day),
            ">5": count_event_attendees_more_than_five(events_on_day),
        }
        for date, events_on_day in events_by_date.items()
    ]

    return {'data': formatted_analytic}


@router.get("/analytic/team/meeting/time")
def get_team_meeting_time(
        team_id: int = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        user: User = Depends(get_auth_user),
        org: Organization = Depends(get_organization),
        db: Session = Depends(get_db)
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    events = []

    org_team_repository = OrganizationTeamRepository(db)
    org_team_member_repository = OrganizationTeamMemberRepository(db)

    org_team = org_team_repository.find_by_team_id(org.id, team_id)
    if not org_team:
        raise HTTPException(status_code=404, detail="Team not found")

    org_team_members = org_team_member_repository.find_by_team_id(org_team.id)
    for member in org_team_members:
        access_token = get_google_access_token(member.email, db)
        member_events = get_calendar_events(access_token, start_date_dt, end_date_dt)
        events += member_events

    events_by_date = group_events_by_date(list(set(events)), start_date_dt, end_date_dt)

    formatted_analytic = [
        {
            "date": date.strftime("%Y-%m-%d"),
            "ratio": calculate_event_ratio(events_on_day),
        }
        for date, events_on_day in events_by_date.items()
    ]

    return {'data': formatted_analytic}
