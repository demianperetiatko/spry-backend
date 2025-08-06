from fastapi import Depends, APIRouter, HTTPException, Query

from sqlalchemy.orm import Session

from models import get_db, Organization, OrganizationMember

from models.repositories.organization_repository import OrganizationRepository, \
    OrganizationTeamRepository, OrganizationTeamMemberRepository

from models.repositories.organization_member_repository import OrganizationMemberRepository

from utils.middleware import get_auth_member, get_auth_organization, require_permission

from utils.analytics import group_events_by_date, analyze_event_participants
from utils.analytics.filters import filter_meetings, filter_active
from utils.analytics.kpi import kpi_total_time, kpi_avg_daily_meetings_time, \
    kpi_cancelled_meetings, kpi_count_meetings, kpi_total_cost, kpi_avg_daily_meetings_cost

from utils.analytics.calendar_stats import calculate_recurring_events_duration, calculate_single_events_duration
from utils.analytics.calendar_stats import calculate_event_ratio
from utils.analytics.calendar_stats import percent_events_with_2_attendees, percent_events_with_3_to_5_attendees, \
    percent_events_with_more_than_5_attendees
from utils.analytics.table import process_recurring_events

from utils.analytics.calendar_stats import percent_inside_team_events, percent_with_other_teams_events, \
    percent_outside_organization_events
from utils.plots import Chart, Diagram
from utils.table import DataTable, SortOrderType

from utils import get_user_profile

router = APIRouter()

from datetime import datetime, timedelta
from utils.analytics.utils import count_weekdays
from utils.analytics.calendar_stats import get_unique_events

from utils.analytics.calendar_stats import calculate_total_events_duration, calculate_buffer_time, \
    calculate_transition_time, calculate_deep_work_time
from utils.analytics.utils import calculate_chance
from utils.analytics.constants import WORKDAY_HOURS

from utils.permissions import member_has_permissions

from utils.analytics.utils import get_member_calendar_events


def get_all_meetings(member: OrganizationMember, start_date_dt, end_date_dt, db):
    try:
        calendar_events = get_member_calendar_events(member.id, start_date_dt, end_date_dt, db)
        meetings = filter_meetings(calendar_events)
        return meetings
    except Exception as e:
        return []


def get_personal_meetings(member: OrganizationMember, start_date_dt, end_date_dt, db):
    try:
        calendar_events = get_member_calendar_events(member.id, start_date_dt, end_date_dt, db)
        meetings = filter_meetings(calendar_events)
        meetings = filter_active(meetings, member.email)
        return meetings
    except Exception as e:
        return []


@router.get("/analytic/personal/meeting/kpi")
def get_personal_kpi(
        member_id: str = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        auth_member: OrganizationMember = Depends(get_auth_member),
        org: Organization = Depends(get_auth_organization),
        db: Session = Depends(get_db),
        _: None = require_permission('analytics-members:view')
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    delta = end_date_dt - start_date_dt

    prev_start_date_dt = start_date_dt - delta
    prev_end_date_dt = end_date_dt - delta

    org_member_repository = OrganizationMemberRepository(db)
    member = org_member_repository.find_by_member_id(org.id, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    events = get_personal_meetings(member, start_date_dt, end_date_dt, db)
    meetings = get_all_meetings(member, start_date_dt, end_date_dt, db)
    set_events = get_unique_events(events)

    prev_events = get_personal_meetings(member, prev_start_date_dt, prev_end_date_dt, db)
    prev_meetings = get_all_meetings(member, prev_start_date_dt, prev_end_date_dt, db)
    set_prev_events = get_unique_events(prev_events)

    count_work_day = count_weekdays(start_date_dt, end_date_dt)
    kpis = [
        {"key": "time_on_meetings", "title": "Time on meetings", **kpi_total_time(events, prev_events)},
        {"key": "avg_daily_meetings_time", "title": "Avg. daily meetings time",
         **kpi_avg_daily_meetings_time(events, prev_events, count_work_day)},
    ]
    if member_has_permissions(auth_member, 'finance:view', db):
        currency = None
        if org.cost_is_active and org.currency:
            currency = org.currency
        kpis.extend([
            {"key": "total_meetings_cost", "title": "Total meetings cost",
             **kpi_total_cost(set_events, set_prev_events, [member], currency)},
            {"key": "avg_daily_meetings_cost", "title": "Avg. daily meetings cost",
             **kpi_avg_daily_meetings_cost(set_events, set_prev_events, [member], currency)},
        ])
    kpis.extend([
        {"key": "meetings_count", "title": "Meetings count", **kpi_count_meetings(events, prev_events)},
        {"key": "cancelled_meetings", "title": "Cancelled meetings",
         **kpi_cancelled_meetings(meetings, prev_meetings, member.email)},
    ])
    return {
        'data': kpis
    }


@router.get("/analytic/personal/meeting")
def get_personal_meetings_chart(
        member_id: str = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        org: Organization = Depends(get_auth_organization),
        db: Session = Depends(get_db),
        _: None = require_permission('analytics-members:view')
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    org_member_repository = OrganizationMemberRepository(db)
    member = org_member_repository.find_by_member_id(org.id, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    events = get_personal_meetings(member, start_date_dt, end_date_dt, db)
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
        db: Session = Depends(get_db),
        _: None = require_permission('analytics-members:view')
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    org_member_repository = OrganizationMemberRepository(db)
    member = org_member_repository.find_by_member_id(org.id, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    events = get_personal_meetings(member, start_date_dt, end_date_dt, db)

    response = Diagram(
        items=events,
        metrics=[
            ("one_to_one", "One-on-one", lambda i: {'value': percent_events_with_2_attendees(i)}),
            ("three_to_five", "3-5", lambda i: {'value': percent_events_with_3_to_5_attendees(i)}),
            ("more_than_five", "6+", lambda i: {'value': percent_events_with_more_than_5_attendees(i)}),
        ]
    )
    return {
        "data": response.as_dict()
    }


@router.get("/analytic/personal/meeting/distribution")
def get_personal_meeting_distribution(
        member_id: str = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
        org: Organization = Depends(get_auth_organization),
        db: Session = Depends(get_db),
        _: None = require_permission('analytics-members:view')
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    org_member_repository = OrganizationMemberRepository(db)
    org_team = OrganizationTeamRepository(db)
    org_team_member = OrganizationTeamMemberRepository(db)
    member = org_member_repository.find_by_member_id(org.id, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    events = get_personal_meetings(member, start_date_dt, end_date_dt, db)

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
            ("inside_team", "Inside the team", lambda i: {'value': percent_inside_team_events(i, team_emails)}),
            ("cross_team", "With other teams",
             lambda i: {'value': percent_with_other_teams_events(i, team_emails, org_emails)}),
            ("external", "Outside the org.", lambda i: {'value': percent_outside_organization_events(i, org_emails)}),
        ]
    )
    return {
        "data": response.as_dict()
    }


@router.get("/analytic/personal/productivity")
def get_personal_productivity(
        member_id: str = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),

        org: Organization = Depends(get_auth_organization),
        db: Session = Depends(get_db),
        _: None = require_permission('analytics-members:view')
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    count_work_day = count_weekdays(start_date_dt, end_date_dt)
    delta = end_date_dt - start_date_dt

    prev_start_date_dt = start_date_dt - delta
    prev_end_date_dt = end_date_dt - delta

    org_member_repository = OrganizationMemberRepository(db)
    member = org_member_repository.find_by_member_id(org.id, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    events = get_personal_meetings(member, start_date_dt, end_date_dt, db)

    prev_events = get_personal_meetings(member, prev_start_date_dt, prev_end_date_dt, db)

    def get_meetings_time():
        total_time = calculate_total_events_duration(events)
        prev_total_time = calculate_total_events_duration(prev_events)

        percent_of_day = round((total_time / (count_work_day * WORKDAY_HOURS)) * 100)
        prev_percent_of_day = round((prev_total_time / (count_work_day * WORKDAY_HOURS)) * 100)
        change = calculate_chance(percent_of_day, prev_percent_of_day)

        return {
            "value": percent_of_day,
            "change": f"{'+' if change >= 0 else ''}{change}%",
            "positive": change >= 0
        }

    def get_buffers_time():
        total_time = calculate_buffer_time(events)
        prev_total_time = calculate_buffer_time(prev_events)

        percent_of_day = round((total_time / (count_work_day * WORKDAY_HOURS)) * 100)
        prev_percent_of_day = round((prev_total_time / (count_work_day * WORKDAY_HOURS)) * 100)
        change = calculate_chance(percent_of_day, prev_percent_of_day)

        return {
            "value": percent_of_day,
            "change": f"{'+' if change >= 0 else ''}{change}%",
            "positive": change >= 0
        }

    def get_deep_work_time():
        total_time = calculate_deep_work_time(events, count_work_day)
        prev_total_time = calculate_deep_work_time(prev_events, count_work_day)

        percent_of_day = round((total_time / (count_work_day * WORKDAY_HOURS)) * 100)
        prev_percent_of_day = round((prev_total_time / (count_work_day * WORKDAY_HOURS)) * 100)
        change = calculate_chance(percent_of_day, prev_percent_of_day)

        return {
            "value": percent_of_day,
            "change": f"{'+' if change >= 0 else ''}{change}%",
            "positive": change >= 0
        }

    def get_transition_time():
        total_time = calculate_transition_time(events)
        prev_total_time = calculate_transition_time(prev_events)

        percent_of_day = round((total_time / (count_work_day * WORKDAY_HOURS)) * 100)
        prev_percent_of_day = round((prev_total_time / (count_work_day * WORKDAY_HOURS)) * 100)
        change = calculate_chance(percent_of_day, prev_percent_of_day)

        return {
            "value": percent_of_day,
            "change": f"{'+' if change >= 0 else ''}{change}%",
            "positive": change >= 0
        }

    productivity = Diagram(
        items=[],
        metrics=[
            ("meetings_time", "Time on meetings", lambda i: get_meetings_time()),
            ("deep_work", " Deep work", lambda i: get_deep_work_time()),
            ("transition_time", "Transition time", lambda i: get_transition_time()),
            ("buffers", "Buffers", lambda i: get_buffers_time()),
        ]
    )

    return {
        "productivity": productivity.as_dict(),
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
        auth_member: OrganizationMember = Depends(get_auth_member),
        org: Organization = Depends(get_auth_organization),
        db: Session = Depends(get_db),
        _: None = require_permission('analytics-members:view')
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    sort_by = sort_by.split('.')[-1] if isinstance(sort_by, str) else sort_order

    org_member_repository = OrganizationMemberRepository(db)
    member = org_member_repository.find_by_member_id(org.id, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    if type == TableType.collaboration:
        events = get_personal_meetings(member, start_date_dt, end_date_dt, db)
        result = analyze_event_participants(events, member.email)
        columns = [
            ('member_profile', 'email', lambda event: get_user_profile(event['email'], db)),
            ('collab_time', 'collab_time')
        ]
    else:
        events = get_all_meetings(member, start_date_dt, end_date_dt, db)
        result = process_recurring_events(events, [member])
        columns = [
            ("id", "id"),
            ("meeting_profile", "meeting",
             lambda i: {"name": i.get('meeting_name'), "duration": "", "recurring_type": "", }),
            ("cancellation_rate", "cancellation_rate"),
            ("total_time", "total_time"),
        ]
        if member_has_permissions(auth_member, 'finance:view', db):
            columns.append(('total_cost', 'total_cost'))
    return DataTable(result, columns).fetch_dicts(sort_by, sort_order)
