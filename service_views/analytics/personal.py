from fastapi import Depends, APIRouter, HTTPException, Query

from sqlalchemy.orm import Session

from models import get_db, User, Organization

from models.repositories.user_repository import UserRepository

from models.repositories.organization_repository import OrganizationRepository, OrganizationMemberRepository, \
    OrganizationTeamRepository, OrganizationTeamMemberRepository
from utils.services import refresh_google_access_token
from utils.middleware import get_auth_user, get_organization
from utils.meet import get_calendar_events
from datetime import datetime, timedelta

from utils.analytics import get_google_access_token

from utils.analytics import group_events_by_date, calculate_event_ratio
from utils.analytics import count_event_attendees_one_to_one, count_event_attendees_three_to_five, \
    count_event_attendees_more_than_five
from utils.analytics import count_recurring_events, count_one_time_events

router = APIRouter()


@router.get("/analytic/personal/meeting/kpi")
def get_personal_kpi(
        member_id: int = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        user: User = Depends(get_auth_user),
        org: Organization = Depends(get_organization),
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


@router.get("/analytic/personal/meeting")
def get_personal_meetings(
        member_id: int = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        user: User = Depends(get_auth_user),
        org: Organization = Depends(get_organization),
        db: Session = Depends(get_db)
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    org_member_repository = OrganizationMemberRepository(db)
    member = org_member_repository.find_by_member_id(org.id, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    access_token = get_google_access_token(user.email, db)

    events = get_calendar_events(access_token, start_date_dt, end_date_dt)

    events_by_date = group_events_by_date(events, start_date_dt, end_date_dt)

    formatted_analytic = [
        {
            "date": date.strftime("%Y-%m-%d"),
            "recurring": count_recurring_events(events_on_day),
            "one-time": count_one_time_events(events_on_day),
        }
        for date, events_on_day in events_by_date.items()
    ]
    return {'data': formatted_analytic}


@router.get("/analytic/personal/meeting/participants")
def get_personal_meeting_participants(
        member_id: int = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        user: User = Depends(get_auth_user),
        org: Organization = Depends(get_organization),
        db: Session = Depends(get_db)
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    org_member_repository = OrganizationMemberRepository(db)
    member = org_member_repository.find_by_member_id(org.id, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    access_token = get_google_access_token(user.email, db)

    events = get_calendar_events(access_token, start_date_dt, end_date_dt)

    events_by_date = group_events_by_date(events, start_date_dt, end_date_dt)

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


@router.get("/analytic/personal/meeting/time")
def get_personal_meeting_time(
        member_id: int = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        user: User = Depends(get_auth_user),
        org: Organization = Depends(get_organization),
        db: Session = Depends(get_db)
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    org_member_repository = OrganizationMemberRepository(db)
    member = org_member_repository.find_by_member_id(org.id, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    access_token = get_google_access_token(user.email, db)

    events = get_calendar_events(access_token, start_date_dt, end_date_dt)

    events_by_date = group_events_by_date(events, start_date_dt, end_date_dt)

    formatted_analytic = [
        {
            "date": date.strftime("%Y-%m-%d"),
            "ratio": calculate_event_ratio(events_on_day)
        }
        for date, events_on_day in events_by_date.items()
    ]

    return {'data': formatted_analytic}
