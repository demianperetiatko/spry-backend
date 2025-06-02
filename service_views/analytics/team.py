from fastapi import Depends, APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from models import get_db, Organization

from models.repositories.organization_repository import OrganizationRepository, OrganizationMemberRepository, \
    OrganizationTeamRepository, OrganizationTeamMemberRepository

from utils.middleware import get_auth_member, get_auth_organization
from utils.google_api import get_calendar_events
from utils.google_api import refresh_google_access_token


from utils.analytics import group_events_by_date

from utils.analytics.calendar_stats import calculate_recurring_events_duration, calculate_single_events_duration, \
    calculate_recurring_events_cost, calculate_single_events_cost, count_inside_team_events, \
    count_with_other_teams_events, count_outside_organization_events
from utils.analytics.calendar_stats import calculate_event_ratio, calculate_total_events_duration, \
    count_user_organized_events

from utils.analytics.calendar_stats import count_events_with_2_attendees, count_events_with_3_to_5_attendees, \
    count_events_with_more_than_5_attendees, calculate_total_events_cost
from utils.analytics.kpi import kpi_total_time, kpi_avg_daily_meetings_time, kpi_meetings_ratio, kpi_count_meetings, \
    kpi_total_cost, kpi_avg_daily_meetings_cost, kpi_without_description
from utils.analytics.utils import count_weekdays
from utils.analytics.calendar_stats import get_unique_events

from utils.analytics.table import process_recurring_events, process_teams_collab

from utils.plots import Chart, Diagram
from utils.table import DataTable, SortOrderType

router = APIRouter()


def get_team_members(org_id, team_id, db: Session):
    if team_id is None:
        org_member_repository = OrganizationMemberRepository(db)
        return org_member_repository.find_by_organization_id(org_id)
    else:
        org_team_repository = OrganizationTeamRepository(db)

        org_team = org_team_repository.find_by_team_id(org_id, team_id)
        if not org_team:
            raise HTTPException(status_code=404, detail="Team not found")

        org_team_member_repository = OrganizationTeamMemberRepository(db)
        return org_team_member_repository.find_by_team_id(team_id)


def get_team_events(org_team_members, start_date, end_date):
    events = []
    for member in org_team_members:
        access_token = refresh_google_access_token(member.google_refresh_token)
        member_events = get_calendar_events(access_token, start_date, end_date)
        events += member_events
    return events


@router.get("/analytic/organization/meeting/kpi")
def get_team_kpi(
        team_id: Optional[str] = Query(None),
        start_date: str = Query(...),
        end_date: str = Query(...),
        org: Organization = Depends(get_auth_organization),
        db: Session = Depends(get_db)
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    delta = end_date_dt - start_date_dt

    prev_start_date_dt = start_date_dt - delta - timedelta(days=1)
    prev_end_date_dt = end_date_dt - delta - timedelta(days=1)

    org_team_members = get_team_members(org.id, team_id, db)

    events = get_team_events(org_team_members, start_date_dt, end_date_dt)
    set_events = get_unique_events(events)

    prev_events = get_team_events(org_team_members, prev_start_date_dt, prev_end_date_dt)
    set_prev_events = get_unique_events(prev_events)

    count_work_day = count_weekdays(start_date_dt, end_date_dt)
    return {
        'data': [
            {"title": "Total Time", **kpi_total_time(events, prev_events)},
            {"title": "Avg. time per member",
             **kpi_avg_daily_meetings_time(events, prev_events, count_work_day, len(org_team_members))},
            {"title": "Meetings time ratio",
             **kpi_meetings_ratio(events, prev_events, count_work_day, len(org_team_members))},
            {"title": "Total Cost", **kpi_total_cost(set_events, set_prev_events, org_team_members)},
            {"title": "Avg. cost per member",
             **kpi_avg_daily_meetings_cost(set_events, set_prev_events, org_team_members)},
            {"title": "Meetings count", **kpi_count_meetings(set_events, set_prev_events)},
            {"title": "Meetings w/o Agenda", **kpi_without_description(set_events, set_prev_events)},
        ]
    }


from enum import Enum


class AnalyticsType(str, Enum):
    time = "time"
    cost = "cost"


@router.get("/analytic/organization/meeting")
async def get_team_meetings(
        team_id: Optional[str] = Query(None),
        start_date: str = Query(...),
        end_date: str = Query(...),
        type: AnalyticsType = Query(AnalyticsType.time),
        org: Organization = Depends(get_auth_organization),
        db: Session = Depends(get_db)
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    org_team_members = get_team_members(org.id, team_id, db)
    events = get_team_events(org_team_members, start_date_dt, end_date_dt)
    set_events = get_unique_events(events)

    if type == AnalyticsType.time:
        response = Chart(
            x_axis="date",
            items=group_events_by_date(events, start_date_dt, end_date_dt),
            metrics=[
                ("recurring", calculate_recurring_events_duration),
                ("one_time", calculate_single_events_duration),
                ("ratio", calculate_event_ratio),
            ]
        )
    else:
        response = Chart(
            x_axis="date",
            items=group_events_by_date(set_events, start_date_dt, end_date_dt),
            metrics=[
                ("recurring", lambda i: calculate_recurring_events_cost(i, org_team_members)),
                ("one_time", lambda i: calculate_single_events_cost(i, org_team_members)),
                ("ratio", calculate_event_ratio),
            ])

    return response.as_dict()


@router.get("/analytic/organization/meeting/participants")
def get_team_meeting_participants(
        team_id: Optional[str] = Query(None),
        start_date: str = Query(...),
        end_date: str = Query(...),
        org: Organization = Depends(get_auth_organization),
        db: Session = Depends(get_db)
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    org_team_members = get_team_members(org.id, team_id, db)
    events = get_team_events(org_team_members, start_date_dt, end_date_dt)

    response = Diagram(
        items=events,
        metrics=[
            ("one_to_one", count_events_with_2_attendees),
            ("three_to_five", count_events_with_3_to_5_attendees),
            ("more_than_five", count_events_with_more_than_5_attendees),
        ]
    )
    return response.as_dict()


@router.get("/analytic/organization/meeting/distribution")
def get_team_meeting_distribution(
        team_id: Optional[str] = Query(None),
        start_date: str = Query(...),
        end_date: str = Query(...),
        org: Organization = Depends(get_auth_organization),
        db: Session = Depends(get_db)
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    org_member_repository = OrganizationMemberRepository(db)

    org_members = org_member_repository.find_by_organization_id(org.id)
    org_team_members = get_team_members(org.id, team_id, db)

    events = get_team_events(org_team_members, start_date_dt, end_date_dt)
    set_events = get_unique_events(events)
    team_emails = [m.email for m in org_team_members]
    org_emails = [m.email for m in org_members]

    response = Diagram(
        items=set_events,
        metrics=[
            ("inside_team", lambda i: count_inside_team_events(i, team_emails)),
            ("cross_team", lambda i: count_with_other_teams_events(i, team_emails, org_emails)),
            ("external", lambda i: count_outside_organization_events(i, org_emails)),
        ]
    )
    return response.as_dict()


class TableType(str, Enum):
    attendees = "attendees"
    organizers = "organizers"
    teams_collab = "teams_collab"
    recurring_meetings = "recurring_meetings"


@router.get("/analytic/organization/meeting/table")
def get_team_meetings_table(
        team_id: Optional[str] = Query(None),
        start_date: str = Query(...),
        end_date: str = Query(...),
        type: TableType = Query(TableType.attendees),
        org: Organization = Depends(get_auth_organization),
        sort_by: Optional[str] = Query(None),
        sort_order: SortOrderType = Query(SortOrderType.asc),
        db: Session = Depends(get_db)
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    sort_by = sort_by.split('.')[-1] if isinstance(sort_by, str) else sort_order

    org_team_members = get_team_members(org.id, team_id, db)

    count_work_day = count_weekdays(start_date_dt, end_date_dt)

    if type == TableType.attendees:
        result = []
        for member in org_team_members:
            access_token = refresh_google_access_token(member.google_refresh_token)
            member_events = get_calendar_events(access_token, start_date_dt, end_date_dt)
            info = {
                "id": member.id,
                "name": member.name,
                "email": member.email,
                "member_photo_url": member.photo_url,
                "time": calculate_total_events_duration(member_events),
                "cost": calculate_total_events_cost(member_events, [member]),
                "ratio": calculate_event_ratio(member_events, count_work_day)
            }
            result.append(info)
        columns = [
            ("id", "id"),
            ("member_profile", "member_profile",
             lambda i: {"name": i.get("name"," "), "email": i.get("email"),
                        "photo_url": i.get("member_photo_url")}),
            ("time", "time"),
            ("cost", "cost"),
            ("ratio", "ratio")
        ]
    elif type == TableType.organizers:
        result = []
        for member in org_team_members:
            access_token = refresh_google_access_token(member.google_refresh_token)
            member_events = get_calendar_events(access_token, start_date_dt, end_date_dt)
            info = {
                "id": member.id,
                "name": member.name,
                "emai": member.email,
                "photo_url": member.photo_url,
                "count": count_user_organized_events(member_events, member.email),
            }
            result.append(info)

        columns = [
            ("id", "id"),
            ("member_profile", "member_profile",
             lambda i: {"name": i.get("name", ""), "email": i.get("emai"),
                        "photo_url": i.get("photo_url")}),
            ("count", "count")
        ]
    elif type == TableType.teams_collab:
        events = get_team_events(org_team_members, start_date_dt, end_date_dt)
        result = process_teams_collab(get_unique_events(events), org.id, team_id, db)

        columns = [
            ("id", "id"),
            ("team_name", "team_name"),
            ("team_manager_profile", "team_manager_profile",
             lambda i: {"name": i.get('manager_name', ""), "email": i.get('manager_email'),
                        "photo_url": i.get('manager_photo_url')}),
            ('collab_time', 'collab_time'),
            ('collab_cost', 'collab_cost'),
        ]
    else:
        events = get_team_events(org_team_members, start_date_dt, end_date_dt)
        result = process_recurring_events(events, org_team_members)
        columns = [
            ("id", "id"),
            ("meeting_profile", "meeting",
             lambda i: {"name": i.get('meeting_name'), "duration": "", "recurring_type": "", }),
            ("attendees", "attendees"),
            ("cancellation_rate", "cancellation_rate"),
            ("total_time", "total_time"),
            ("total_cost", "total_cost"),
        ]
    return DataTable(result, columns).fetch_dicts(sort_by, sort_order)
