from fastapi import Depends, APIRouter, HTTPException, Query

from sqlalchemy.orm import Session

from models import get_db, Organization, OrganizationMember

from models.repositories.organization_repository import OrganizationRepository, OrganizationMemberRepository, \
    OrganizationTeamRepository, OrganizationTeamMemberRepository

from utils.google_api import refresh_google_access_token

from utils.middleware import get_auth_member, get_auth_organization
from utils.google_api import get_calendar_events

from utils.analytics import group_events_by_date, analyze_event_participants

from utils.analytics.kpi import kpi_total_time, kpi_avg_daily_meetings_time, \
    kpi_cancelled_meetings, kpi_count_meetings, kpi_meetings_ratio

from utils.analytics.calendar_stats import calculate_recurring_events_duration, calculate_single_events_duration
from utils.analytics.calendar_stats import calculate_event_ratio
from utils.analytics.calendar_stats import count_events_with_2_attendees, count_events_with_3_to_5_attendees, \
    count_events_with_more_than_5_attendees
from utils.analytics.table import process_recurring_events

from utils.analytics.calendar_stats import count_inside_team_events, count_with_other_teams_events, \
    count_outside_organization_events
from utils.plots import Chart, Diagram
from utils.table import DataTable, SortOrderType

from utils import get_user_profile

router = APIRouter()

from datetime import datetime, timedelta
from utils.analytics.utils import count_weekdays


@router.get("/analytic/personal/meeting/kpi")
def get_personal_kpi(
        member_id: str = Query(...),
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

    org_member_repository = OrganizationMemberRepository(db)
    member = org_member_repository.find_by_member_id(org.id, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    access_token = refresh_google_access_token(member.google_refresh_token)

    events = get_calendar_events(access_token, start_date_dt, end_date_dt)
    prev_events = get_calendar_events(access_token, prev_start_date_dt, prev_end_date_dt)
    count_work_day = count_weekdays(start_date_dt, end_date_dt)

    return {
        'data': [
            {"title": "Total time on meetings", **kpi_total_time(events, prev_events)},
            {"title": "Avg. daily meetings time",
             **kpi_avg_daily_meetings_time(events, prev_events, count_work_day)},
            {"title": "Total meetings cost", },
            {"title": "Avg. daily meetings cost", },
            {"title": "Meetings count", **kpi_count_meetings(events, prev_events)},
            {"title": "Cancelled meetings", **kpi_cancelled_meetings(events, prev_events)},
        ]
    }


@router.get("/analytic/personal/meeting")
def get_personal_meetings(
        member_id: str = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        org: Organization = Depends(get_auth_organization),
        db: Session = Depends(get_db)
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    org_member_repository = OrganizationMemberRepository(db)
    member = org_member_repository.find_by_member_id(org.id, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    access_token = refresh_google_access_token(member.google_refresh_token)
    events = get_calendar_events(access_token, start_date_dt, end_date_dt)
    events_by_date = group_events_by_date(events, start_date_dt, end_date_dt)

    response = Chart(
        x_axis="date",
        items=events_by_date,
        metrics=[
            ("recurring", calculate_recurring_events_duration),
            ("one_time", calculate_single_events_duration),
            ("ratio", calculate_event_ratio),
        ]
    )

    return response.as_dict()


@router.get("/analytic/personal/meeting/participants")
def get_personal_meeting_participants(
        member_id: str = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        org: Organization = Depends(get_auth_organization),
        db: Session = Depends(get_db)
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    org_member_repository = OrganizationMemberRepository(db)
    member = org_member_repository.find_by_member_id(org.id, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    access_token = refresh_google_access_token(member.google_refresh_token)
    events = get_calendar_events(access_token, start_date_dt, end_date_dt)

    response = Diagram(
        items=events,
        metrics=[
            ("one_to_one", count_events_with_2_attendees),
            ("three_to_five", count_events_with_3_to_5_attendees),
            ("more_than_five", count_events_with_more_than_5_attendees),
        ]
    )
    return response.as_dict()


@router.get("/analytic/personal/meeting/distribution")
def get_personal_meeting_distribution(
        member_id: str = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        org: Organization = Depends(get_auth_organization),
        db: Session = Depends(get_db)
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    org_member_repository = OrganizationMemberRepository(db)
    org_team = OrganizationTeamRepository(db)
    org_team_member = OrganizationTeamMemberRepository(db)
    member = org_member_repository.find_by_member_id(org.id, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    access_token = refresh_google_access_token(member.google_refresh_token)
    events = get_calendar_events(access_token, start_date_dt, end_date_dt)

    team_emails = []
    for team in org_team.find_by_member_id(member.id):
        ms = org_team_member.find_by_team_id(team.team_id)
        for m in ms:
            team_emails.append(m.email)

    team_emails = list(set(team_emails))
    org_emails = [m.email for m in org_member_repository.find_by_organization_id(org.id)]

    response = Diagram(
        items=events,
        metrics=[
            ("inside_team", lambda i: count_inside_team_events(i, team_emails)),
            ("cross_team", lambda i: count_with_other_teams_events(i, team_emails, org_emails)),
            ("external", lambda i: count_outside_organization_events(i, org_emails)),
        ]
    )
    return response.as_dict()


@router.get("/analytic/organization/productivity")
def get_team_productivity(
        member_id: str = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),

        org: Organization = Depends(get_auth_organization),
        db: Session = Depends(get_db)
):
    return {
        "change_percentage": 12,
        "productivity": [
            {
                "title": "meetings_time",
                "value": 28,
                "change": 8,
                "positive": False,
            },
            {
                "title": "deep_work",
                "value": 42,
                "change": 15,
                "positive": True,
            },
            {
                "title": "transition_time",
                "value": 22,
                "change": 3,
                "positive": False,
            },
            {
                "title": "buffers",
                "value": 8,
                "change": 2,
                "positive": True,
            },
        ],
    }


from enum import Enum


class TableType(str, Enum):
    collaboration = "collaboration"
    recurring_meetings = "recurring_meetings"


@router.get("/analytic/personal/meeting/table")
def get_personal_table(
        member_id: str = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        sort_by: str = Query(...),
        sort_order: SortOrderType = Query(SortOrderType.asc),
        type: TableType = Query(TableType.collaboration),
        org: Organization = Depends(get_auth_organization),
        db: Session = Depends(get_db)
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    sort_by = sort_by.split('.')[-1] if isinstance(sort_by, str) else sort_order

    org_member_repository = OrganizationMemberRepository(db)
    member = org_member_repository.find_by_member_id(org.id, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    access_token = refresh_google_access_token(member.google_refresh_token)

    events = get_calendar_events(access_token, start_date_dt, end_date_dt)
    if type == TableType.collaboration:
        result = analyze_event_participants(events, member.email)
        columns = [
            ('member_profile', 'email', lambda event: get_user_profile(event['email'], db)),
            ('collab_time', 'collab_time')
        ]
    else:
        result = process_recurring_events(events, [member])
        columns = [
            ("id", "id"),
            ("meeting_profile", "meeting",
             lambda i: {"name": i.get('meeting_name'), "duration": "", "recurring_type": "", }),
            ("cancellation_rate", "cancellation_rate"),
            ("total_time", "total_time"),
            ("total_cost", "total_cost"),
        ]
    return DataTable(result, columns).fetch_dicts(sort_by, sort_order)
