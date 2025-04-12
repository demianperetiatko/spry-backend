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

from utils.analytics.calendar_stats import calculate_recurring_events_duration, calculate_single_events_duration
from utils.analytics.calendar_stats import calculate_event_ratio, calculate_total_events_duration, count_user_organized_events

from utils.analytics.kpi import kpi_total_time

from utils.plots import Chart, Diagram
from utils.table import DataTable, SortOrderType

router = APIRouter()


def get_team_events(team_id, start_date, end_date, db: Session):
    events = []
    org_team_member_repository = OrganizationTeamMemberRepository(db)

    org_team_members = org_team_member_repository.find_by_team_id(team_id)
    for member in org_team_members:
        access_token = get_google_access_token(member.email, db)
        member_events = get_calendar_events(access_token, start_date, end_date)
        events += member_events

    return events


@router.get("/analytic/team/meeting/kpi")
def get_team_kpi(
        team_id: int = Query(...),
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

    org_team_repository = OrganizationTeamRepository(db)

    org_team = org_team_repository.find_by_team_id(org.id, team_id)
    if not org_team:
        raise HTTPException(status_code=404, detail="Team not found")

    events = get_team_events(org_team.id, start_date_dt, end_date_dt, db)
    prev_events = get_team_events(org_team.id, prev_start_date_dt, prev_end_date_dt, db)

    return {
        'data': [
            kpi_total_time(events, prev_events),
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
        metrics=[
            ("recurring", calculate_recurring_events_duration),
            ("one_time", calculate_single_events_duration),
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


from utils import get_user_profile


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
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    org_team_repository = OrganizationTeamRepository(db)
    org_team_member_repository = OrganizationTeamMemberRepository(db)

    org_team = org_team_repository.find_by_team_id(org.id, team_id)
    if not org_team:
        raise HTTPException(status_code=404, detail="Team not found")
    org_team_members = org_team_member_repository.query_find_by_team_id(org_team.id)

    if type == TableType.attendees:
        result = []
        for member in org_team_members:
            access_token = get_google_access_token(member.email, db)
            member_events = get_calendar_events(access_token, start_date_dt, end_date_dt)
            time = calculate_total_events_duration(member_events)
            info = {
                "id": member.id,
                "member_profile": get_user_profile(member.email, db),
                "time": time,
                "cost": time,
                "radio": calculate_event_ratio(member_events)
            }
            result.append(info)
        return {
            "total_count": len(result),
            "data": result,
        }
    elif type == TableType.organizers:
        result = []
        for member in org_team_members:
            access_token = get_google_access_token(member.email, db)
            member_events = get_calendar_events(access_token, start_date_dt, end_date_dt)
            info = {
                "id": member.id,
                "member_profile": get_user_profile(member.email, db),
                "count": count_user_organized_events(member_events, member.email),
            }
            result.append(info)
        return {
            "total_count": len(result),
            "data": result,
        }
    elif type == TableType.teams_collab:
        result = []
        return {
            "total_count": len(result),
            "data": result,
        }
    elif type == TableType.recurring_meetings:
        result = []
        return {
            "total_count": len(result),
            "data": result,
        }
