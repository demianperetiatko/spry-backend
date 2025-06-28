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
from utils.analytics.filters import filter_meetings

from utils.analytics.calendar_stats import calculate_recurring_events_duration, calculate_single_events_duration, \
    calculate_recurring_events_cost, calculate_single_events_cost, percent_inside_team_events, \
    percent_with_other_teams_events, percent_outside_organization_events
from utils.analytics.calendar_stats import calculate_event_ratio, calculate_total_events_duration, \
    count_user_organized_events

from utils.analytics.calendar_stats import percent_events_with_2_attendees, percent_events_with_3_to_5_attendees, \
    percent_events_with_more_than_5_attendees, calculate_total_events_cost
from utils.analytics.kpi import kpi_total_time, kpi_avg_daily_meetings_time, kpi_meetings_ratio, kpi_count_meetings, \
    kpi_total_cost, kpi_avg_daily_meetings_cost, kpi_without_description
from utils.analytics.utils import count_weekdays
from utils.analytics.calendar_stats import get_unique_events

from utils.analytics.table import process_recurring_events, process_teams_collab

from utils.plots import Chart, Diagram
from utils.table import DataTable, SortOrderType
from utils.analytics.calendar_stats import calculate_total_events_duration, calculate_buffer_time, \
    calculate_transition_time, calculate_deep_work_time

router = APIRouter()


def get_team_members(org_id, team_id, db: Session):
    if team_id is None:
        org_member_repository = OrganizationMemberRepository(db)
        return [member for member in org_member_repository.find_by_organization_id(org_id)
                if member.google_refresh_token and refresh_google_access_token(member.google_refresh_token)]
    else:
        org_team_repository = OrganizationTeamRepository(db)

        org_team = org_team_repository.find_by_team_id(org_id, team_id)
        if not org_team:
            raise HTTPException(status_code=404, detail="Team not found")

        org_team_member_repository = OrganizationTeamMemberRepository(db)

        return [member for member in org_team_member_repository.find_by_team_id(team_id)
                if member.google_refresh_token and refresh_google_access_token(member.google_refresh_token)]


def get_team_events(org_team_members, start_date, end_date):
    events = []
    for member in org_team_members:
        if member.google_refresh_token:
            access_token = refresh_google_access_token(member.google_refresh_token)
            member_events = filter_meetings(get_calendar_events(access_token, start_date, end_date))
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

    prev_start_date_dt = start_date_dt - delta
    prev_end_date_dt = end_date_dt - delta

    org_team_members = get_team_members(org.id, team_id, db)

    events = get_team_events(org_team_members, start_date_dt, end_date_dt)
    set_events = get_unique_events(events)

    prev_events = get_team_events(org_team_members, prev_start_date_dt, prev_end_date_dt)
    set_prev_events = get_unique_events(prev_events)

    count_work_day = count_weekdays(start_date_dt, end_date_dt)
    return {
        'data': [
            {"title": "Time on ,eetings", **kpi_total_time(events, prev_events)},
            {"title": "Meetings time ratio",
             **kpi_meetings_ratio(events, prev_events, count_work_day, len(org_team_members))},
            {"title": "Avg. time per member",
             **kpi_avg_daily_meetings_time(events, prev_events, count_work_day, len(org_team_members))},
            {"title": "Total meeting cost", **kpi_total_cost(set_events, set_prev_events, org_team_members)},
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
            ("one_to_one", "One-on-one", lambda i: {'value': percent_events_with_2_attendees(i)}),
            ("three_to_five", "3-5", lambda i: {'value': percent_events_with_3_to_5_attendees(i)}),
            ("more_than_five", "6+", lambda i: {'value': percent_events_with_more_than_5_attendees(i)}),
        ]
    )
    return {
        "data": response.as_dict()
    }


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
            ("inside_team", "Inside the team", lambda i: {'value': percent_inside_team_events(i, team_emails)}),
            ("cross_team", "With other teams",
             lambda i: {'value': percent_with_other_teams_events(i, team_emails, org_emails)}),
            ("external", "Outside the org.", lambda i: {'value': percent_outside_organization_events(i, org_emails)}),
        ]
    )
    return {
        "data": response.as_dict()
    }


class ListType(str, Enum):
    members = 'members'
    teams = 'teams'


class SortBy(str, Enum):
    meetings_time = 'meetings_time'
    deep_work = 'deep_work'


@router.get("/analytic/organization/productivity")
def get_team_productivity(
        team_id: Optional[str] = Query(None),
        start_date: str = Query(...),
        end_date: str = Query(...),
        list_type: ListType = Query(ListType.members),
        sort_by: SortBy = Query(SortBy.meetings_time),
        sort_order: SortOrderType = Query(SortOrderType.asc),
        org: Organization = Depends(get_auth_organization),
        db: Session = Depends(get_db)
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    count_work_day = count_weekdays(start_date_dt, end_date_dt)

    delta = end_date_dt - start_date_dt

    prev_start_date_dt = start_date_dt - delta
    prev_end_date_dt = end_date_dt - delta

    org_team_members = get_team_members(org.id, team_id, db)
    data = []
    for member in org_team_members:
        if member.google_refresh_token:
            access_token = refresh_google_access_token(member.google_refresh_token)
            events = filter_meetings(get_calendar_events(access_token, start_date_dt, end_date_dt))
            prev_events = filter_meetings(get_calendar_events(access_token, prev_start_date_dt, prev_end_date_dt))
            info = {
                'id': member.id,
                'name': member.name,
                'email': member.email,
                "photo_url": member.photo_url,
                "meetings_time": calculate_total_events_duration(events),
                "prev_meetings_time": calculate_total_events_duration(prev_events),
                "deep_work": calculate_deep_work_time(events, count_work_day),
                "prev_deep_work": calculate_deep_work_time(prev_events, count_work_day),
                "transition_time": calculate_transition_time(events),
                "prev_transition_time": calculate_transition_time(prev_events),
                "buffers": calculate_buffer_time(events),
                "prev_buffers": calculate_buffer_time(prev_events),
            }
            data.append(info)

    def calculete(data, key):
        from utils.analytics.utils import calculate_chance
        from utils.analytics.constants import WORKDAY_HOURS
        kpi = sum([info[key] for info in data])
        prev_kpi = sum([info[f'prev_{key}'] for info in data])
        percent_of_day = round((kpi / (count_work_day * WORKDAY_HOURS)) * 100, 2)
        prev_percent_of_day = round((prev_kpi / (count_work_day * WORKDAY_HOURS)) * 100, 2)
        change = calculate_chance(percent_of_day, prev_percent_of_day)

        return {
            "value": percent_of_day,
            "change": f"{'+' if change >= 0 else ''}{change}%",
            "positive": change >= 0
        }

    productivity = Diagram(
        items=data,
        metrics=[
            ("meetings_time", "Meetings time", lambda i: calculete(i, "meetings_time")),
            ("deep_work", "Deep Work", lambda i: calculete(i, "deep_work")),
            ("transition_time", "Transition time", lambda i: calculete(i, "transition_time")),
            ("buffers", "Buffers", lambda i: calculete(i, "buffers")),
        ]
    )

    if list_type == ListType.teams:
        help_data = []
        org_team_repository = OrganizationTeamRepository(db)
        org_team_member_repository = OrganizationTeamMemberRepository(db)
        if team_id is None:
            teams = org_team_repository.find_by_organization_id(org.id)
        else:
            teams = [org_team_repository.find_by_id(team_id)]

        for team in teams:
            members = org_team_member_repository.find_by_team_id(team.id)
            team_member_ids = {member.member_id for member in members}
            team_members_data = [m for m in data if m['id'] in team_member_ids]
            help_data.append({
                "id": team.id,
                "name": team.name,
                "meetings_time": sum(m["meetings_time"] for m in team_members_data),
                "deep_work": sum(m["deep_work"] for m in team_members_data),
                "transition_time": sum(m["transition_time"] for m in team_members_data),
                "buffers": sum(m["buffers"] for m in team_members_data),
            })

        columns = [
            ("id", "id"),
            ("name", "name"),
            ('meetings_time', 'meetings_time'),
            ('deep_work', 'deep_work'),
            ('transition_time', 'transition_time'),
            ('buffers', 'buffers'),
        ]
        res_data = DataTable(help_data, columns).fetch_dicts(sort_by, sort_order).get('data', [])
    else:
        columns = [
            ("id", "id"),
            ("member_profile", "member_profile",
             lambda i: {"name": i.get("name", " "), "email": i.get("email"),
                        "photo_url": i.get("member_photo_url")}),
            ('meetings_time', 'meetings_time'),
            ('deep_work', 'deep_work'),
            ('transition_time', 'transition_time'),
            ('buffers', 'buffers'),
        ]
        res_data = DataTable(data, columns).fetch_dicts(sort_by, sort_order).get('data', [])
    return {
        "productivity": productivity.as_dict(),
        "data": res_data
    }


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
            member_events = filter_meetings(get_calendar_events(access_token, start_date_dt, end_date_dt))
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
             lambda i: {"name": i.get("name", " "), "email": i.get("email"),
                        "photo_url": i.get("member_photo_url")}),
            ("time", "time"),
            ("cost", "cost"),
            ("ratio", "ratio")
        ]
    elif type == TableType.organizers:
        result = []
        for member in org_team_members:
            access_token = refresh_google_access_token(member.google_refresh_token)
            member_events = filter_meetings(get_calendar_events(access_token, start_date_dt, end_date_dt))
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
