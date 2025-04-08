from fastapi import Depends, APIRouter, HTTPException, Query

from sqlalchemy.orm import Session

from models import get_db, User, Organization

from models.repositories.organization_repository import OrganizationRepository, OrganizationMemberRepository, \
    OrganizationTeamRepository, OrganizationTeamMemberRepository

from utils.middleware import get_auth_user, get_organization
from utils.meet import get_calendar_events


from utils.analytics import get_google_access_token

from utils.analytics import group_events_by_date, analyze_event_participants


from utils.analytics.kpi import calculate_kpi_total_time, calculate_kpi_avg_daily_meetings_time, \
    calculate_kpi_cancelled_meetings, calculate_kpi_count_meetings, calculate_kpi_meetings_ratio


from utils.analytics.calendar_stats import calculate_recurring_event_time, calculate_one_time_event_time
from utils.analytics.calendar_stats import calculate_event_ratio
from utils.analytics.calendar_stats import count_event_attendees_one_to_one, count_event_attendees_three_to_five, \
    count_event_attendees_more_than_five


from utils.plots import Chart, Diagram
from utils.table import DataTable, SortOrderType

from utils import get_user_profile

router = APIRouter()

from datetime import datetime, timedelta


def count_weekdays(start, end):
    count = 0
    current = start
    while current <= end:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return count


@router.get("/analytic/personal/meeting/kpi")
def get_personal_kpi(
        member_id: int = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        user: User = Depends(get_auth_user),
        org: Organization = Depends(get_organization),
        db: Session = Depends(get_db)
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    delta = end_date_dt - start_date_dt

    prev_start_date_dt = start_date_dt - delta - timedelta(days=1)
    prev_end_date_dt = end_date_dt - delta - timedelta(days=1)

    org_member_repository = OrganizationMemberRepository(db)
    member = org_member_repository.find_by_member_id(org.id, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    access_token = get_google_access_token(member.email, db)

    events = get_calendar_events(access_token, start_date_dt, end_date_dt)
    prev_events = get_calendar_events(access_token, prev_start_date_dt, prev_end_date_dt)
    count_work_day = count_weekdays(start_date_dt, end_date_dt)
    return {
        'data': [
            calculate_kpi_total_time(events, prev_events),
            calculate_kpi_avg_daily_meetings_time(events, prev_events, count_work_day),
            calculate_kpi_count_meetings(events, prev_events),
            calculate_kpi_meetings_ratio(events, prev_events, count_work_day),
            calculate_kpi_cancelled_meetings(events, prev_events),
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

    access_token = get_google_access_token(member.email, db)
    events = get_calendar_events(access_token, start_date_dt, end_date_dt)
    events_by_date = group_events_by_date(events, start_date_dt, end_date_dt)

    response = Chart(
        items=events_by_date,
        x_axis="date",
        y_axis_config=[
            {"side": "left", "unit": "h"},
            {"side": "right", "unit": "%"},
        ],
        headers=[
            {"name": "Recurring", "chart_type": "bar", "key": "recurring", "y_axis": "left"},
            {"name": "One-time", "chart_type": "bar", "key": "one_time", "y_axis": "left"},
            {"name": "Meetings time ratio", "chart_type": "line", "key": "ratio", "y_axis": "right"},
        ],
        metrics=[
            ("recurring", calculate_recurring_event_time),
            ("one_time", calculate_one_time_event_time),
            ("ratio", calculate_event_ratio),
        ]
    )

    return response.as_dict()


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

    access_token = get_google_access_token(member.email, db)
    events = get_calendar_events(access_token, start_date_dt, end_date_dt)

    response = Diagram(
        items=events,
        headers=[
            {"name": "1-1", "key": "one_to_one"},
            {"name": "3-5", "key": "three_to_five"},
            {"name": "6+", "key": "more_than_five"},
        ],
        metrics=[
            ("one_to_one", count_event_attendees_one_to_one),
            ("three_to_five", count_event_attendees_three_to_five),
            ("more_than_five", count_event_attendees_more_than_five),
        ]
    )
    return response.as_dict()


@router.get("/analytic/personal/meeting/distribution")
def get_personal_meeting_distribution(
        member_id: int = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        user: User = Depends(get_auth_user),
        org: Organization = Depends(get_organization),
        db: Session = Depends(get_db)
):
    import random

    def fun_random(events):
        return random.randint(0, 10)

    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    org_member_repository = OrganizationMemberRepository(db)
    member = org_member_repository.find_by_member_id(org.id, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    access_token = get_google_access_token(member.email, db)
    events = get_calendar_events(access_token, start_date_dt, end_date_dt)

    response = Diagram(
        items=events,
        headers=[
            {"name": "Inside the team", "key": "inside_team"},
            {"name": "With other teams", "key": "cross_team"},
            {"name": "Outside the organization", "key": "external"},
        ],
        metrics=[
            ("inside_team", fun_random),
            ("cross_team", fun_random),
            ("external", fun_random),
        ]
    )
    return response.as_dict()


@router.get("/analytic/personal/meeting/collaboration")
def get_personal_table_collaboration(
        member_id: int = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        sort_by: str = Query(...),
        sort_order: SortOrderType = Query(SortOrderType.asc),
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

    access_token = get_google_access_token(member.email, db)

    events = get_calendar_events(access_token, start_date_dt, end_date_dt)

    result = analyze_event_participants(events, member.email)
    columns = [
        ('member_profile', 'email', lambda event: get_user_profile(event['email'], db)),
        ('collab_time', 'collab_time')
    ]
    return DataTable(result, columns).fetch_dicts(sort_by, sort_order)
