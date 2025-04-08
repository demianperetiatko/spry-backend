from fastapi import Depends, APIRouter, HTTPException, Query

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from models import get_db, User, Organization

from models.repositories.organization_repository import OrganizationRepository, OrganizationMemberRepository, \
    OrganizationTeamRepository, OrganizationTeamMemberRepository

from utils.middleware import get_auth_user, get_organization
from utils.meet import get_calendar_events

from utils.analytics import get_google_access_token

from utils.analytics import count_event_attendees_one_to_one, count_event_attendees_three_to_five, \
    count_event_attendees_more_than_five, group_events_by_date

from utils.analytics.calendar_stats import calculate_recurring_event_time, calculate_one_time_event_time
from utils.analytics.calendar_stats import calculate_event_ratio

from utils.plots import Chart, Diagram
from utils.table import DataTable, SortOrderType

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


from enum import Enum


class AnalyticsType(str, Enum):
    time = "time"
    cost = "cost"


@router.get("/analytic/team/meeting")
def get_team_meetings(
        team_id: int = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        user: User = Depends(get_auth_user),
        type: AnalyticsType = Query(AnalyticsType.time),
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


@router.get("/analytic/team/meeting/distribution")
def get_team_meeting_distribution(
        team_id: int = Query(...),
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


class TableType(str, Enum):
    attendees = "attendees"
    organizers = "organizers"
    teams_collab = "teams_collab"
    recurring_meetings = "recurring_meetings"


@router.get("/analytic/team/meeting/table")
def get_team_meetings_table(
        team_id: int = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        type: TableType = Query(TableType.attendees),
        user: User = Depends(get_auth_user),
        org: Organization = Depends(get_organization),
        sort_by: str = Query(...),
        sort_order: SortOrderType = Query(SortOrderType.asc),
        db: Session = Depends(get_db)
):
    return {'data': []}
