from datetime import datetime
from typing import Optional

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from sqlalchemy.orm import Session

from models import Organization
from models import OrganizationMember
from models import get_db
from models.repositories.organization_member_repository import OrganizationMemberRepository
from models.repositories.organization_team_repository import OrganizationTeamMemberRepository
from models.repositories.organization_team_repository import OrganizationTeamRepository
from utils.analytics import group_events_by_date
from utils.analytics.calendar_stats import calculate_avg_attendees
from utils.analytics.calendar_stats import calculate_buffer_time
from utils.analytics.calendar_stats import calculate_event_ratio
from utils.analytics.calendar_stats import calculate_events_without_description_duration
from utils.analytics.calendar_stats import calculate_person_deep_work_time
from utils.analytics.calendar_stats import calculate_recurring_events_cost
from utils.analytics.calendar_stats import calculate_recurring_events_duration
from utils.analytics.calendar_stats import calculate_single_events_cost
from utils.analytics.calendar_stats import calculate_single_events_duration
from utils.analytics.calendar_stats import calculate_total_events_cost
from utils.analytics.calendar_stats import calculate_total_events_duration
from utils.analytics.calendar_stats import calculate_transition_time
from utils.analytics.calendar_stats import get_unique_events
from utils.analytics.calendar_stats import get_user_organized_events
from utils.analytics.calendar_stats import percent_events_with_2_attendees
from utils.analytics.calendar_stats import percent_events_with_3_to_5_attendees
from utils.analytics.calendar_stats import percent_events_with_more_than_5_attendees
from utils.analytics.calendar_stats import percent_inside_team_events
from utils.analytics.calendar_stats import percent_outside_organization_events
from utils.analytics.calendar_stats import percent_with_other_teams_events
from utils.analytics.filters import filter_active
from utils.analytics.filters import filter_meetings
from utils.analytics.kpi import kpi_avg_daily_meetings_time
from utils.analytics.kpi import kpi_avg_member_meetings_cost
from utils.analytics.kpi import kpi_count_meetings
from utils.analytics.kpi import kpi_meetings_ratio
from utils.analytics.kpi import kpi_team_buffers_time_percent
from utils.analytics.kpi import kpi_team_deep_work_time_percent
from utils.analytics.kpi import kpi_team_total_time_percent
from utils.analytics.kpi import kpi_team_transition_time_percent
from utils.analytics.kpi import kpi_total_cost
from utils.analytics.kpi import kpi_total_time
from utils.analytics.kpi import kpi_without_description
from utils.analytics.table import process_recurring_events
from utils.analytics.table import process_teams_collab
from utils.analytics.utils import count_weekdays
from utils.analytics.utils import get_member_calendar_events
from utils.analytics.utils import get_periods
from utils.middleware import get_auth_member
from utils.middleware import get_auth_organization
from utils.middleware import require_permission
from utils.permissions import member_has_permissions
from utils.plots import Chart
from utils.plots import Diagram
from utils.table import DataTable
from utils.table import SortOrderType

router = APIRouter()


def get_team_members(org_id, team_id, db: Session):  # todo: fix
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


def flatten_team_events(team_events):
    all_events = []
    for member_data in team_events:
        events = member_data.get("events", [])
        all_events.extend(events)
    return all_events


def get_team_events(org_team_members, start_date, end_date, db, can_filter_filter_active=True):
    res = []
    for member in org_team_members:
        try:
            calendar_events = get_member_calendar_events(member.member_id, start_date, end_date, db)
            events = filter_meetings(calendar_events)
            if can_filter_filter_active:
                events = filter_active(events, member.email)
            res.append(
                {
                    "member_id": member.member_id,
                    "member_email": member.email,
                    "events": events,
                }
            )
        except Exception:
            continue
    return res


@router.get("/analytic/organization/meeting/kpi")
def get_team_kpi(
    team_id: Optional[str] = Query(None),
    start_date: str = Query(...),
    end_date: str = Query(...),
    auth_member: OrganizationMember = Depends(get_auth_member),
    org: Organization = Depends(get_auth_organization),
    db: Session = Depends(get_db),
    _: None = require_permission("analytics-organization:view"),
):
    (start_date_dt, end_date_dt), (prev_start_date_dt, prev_end_date_dt) = get_periods(start_date, end_date)

    org_team_members = get_team_members(org.id, team_id, db)

    team_events = get_team_events(org_team_members, start_date_dt, end_date_dt, db)
    events = flatten_team_events(team_events)
    set_events = get_unique_events(events)

    prev_team_events = get_team_events(org_team_members, prev_start_date_dt, prev_end_date_dt, db)
    prev_events = flatten_team_events(prev_team_events)
    set_prev_events = get_unique_events(prev_events)

    count_work_day = count_weekdays(start_date_dt, end_date_dt)

    members_with_events_ids = {event["member_id"] for event in team_events}
    org_team_members = [m for m in org_team_members if m.member_id in members_with_events_ids]
    kpis = [
        {
            "key": "time_on_meetings",
            "title": "Time on meetings",
            **kpi_total_time(events, prev_events),
        },
        {
            "key": "meetings_time_ratio",
            "title": "Meetings time ratio",
            **kpi_meetings_ratio(events, prev_events, count_work_day, len(org_team_members)),
        },
        {
            "key": "avg_hours_per_person",
            "title": "Avg. hours per member",
            **kpi_avg_daily_meetings_time(events, prev_events, 1, len(org_team_members)),
        },  # quick fix
    ]
    if member_has_permissions(auth_member, "finance:view", db):
        currency = None
        if org.cost_is_active and org.currency:
            currency = org.currency
        kpis.extend(
            [
                {
                    "key": "total_meetings_cost",
                    "title": "Total meetings cost",
                    **kpi_total_cost(set_events, set_prev_events, org_team_members, currency),
                },
                {
                    "key": "avg_daily_meetings_cost",
                    "title": "Avg. cost per member",
                    **kpi_avg_member_meetings_cost(set_events, set_prev_events, org_team_members, currency),
                },
            ]
        )
    kpis.extend(
        [
            {
                "key": "meetings_count",
                "title": "Meetings count",
                **kpi_count_meetings(set_events, set_prev_events),
            },
            {
                "key": "meetings_wo_agenda",
                "title": "Meetings w/o agenda",
                **kpi_without_description(set_events, set_prev_events),
            },
        ]
    )

    return {"data": kpis}


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
    db: Session = Depends(get_db),
    _: None = require_permission("analytics-organization:view"),
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    org_team_members = get_team_members(org.id, team_id, db)
    team_events = get_team_events(org_team_members, start_date_dt, end_date_dt, db)
    events = flatten_team_events(team_events)
    set_events = get_unique_events(events)

    members_with_events_ids = {event["member_id"] for event in team_events}
    org_team_members = [m for m in org_team_members if m.member_id in members_with_events_ids]

    if type == AnalyticsType.time:
        response = Chart(
            x_axis="date",
            items=group_events_by_date(events, start_date_dt, end_date_dt),
            metrics=[
                ("recurring", calculate_recurring_events_duration),
                ("one_time", calculate_single_events_duration),
                (
                    "ratio",
                    lambda i: calculate_event_ratio(i, len(org_team_members) * 1),
                ),
            ],
        )
    else:
        response = Chart(
            x_axis="date",
            items=group_events_by_date(set_events, start_date_dt, end_date_dt),
            metrics=[
                (
                    "recurring",
                    lambda i: calculate_recurring_events_cost(i, org_team_members),
                ),
                (
                    "one_time",
                    lambda i: calculate_single_events_cost(i, org_team_members),
                ),
            ],
        )

    return response.as_dict()


@router.get("/analytic/organization/meeting/participants")
def get_team_meeting_participants(
    team_id: Optional[str] = Query(None),
    start_date: str = Query(...),
    end_date: str = Query(...),
    org: Organization = Depends(get_auth_organization),
    db: Session = Depends(get_db),
    _: None = require_permission("analytics-organization:view"),
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    org_team_members = get_team_members(org.id, team_id, db)
    events = flatten_team_events(get_team_events(org_team_members, start_date_dt, end_date_dt, db))

    response = Diagram(
        items=events,
        metrics=[
            (
                "one_to_one",
                "One-on-one",
                lambda i: {"value": percent_events_with_2_attendees(i)},
            ),
            (
                "three_to_five",
                "3-5",
                lambda i: {"value": percent_events_with_3_to_5_attendees(i)},
            ),
            (
                "more_than_five",
                "6+",
                lambda i: {"value": percent_events_with_more_than_5_attendees(i)},
            ),
        ],
    )
    return {"data": response.as_dict()}


@router.get("/analytic/organization/meeting/distribution")
def get_team_meeting_distribution(
    team_id: Optional[str] = Query(None),
    start_date: str = Query(...),
    end_date: str = Query(...),
    org: Organization = Depends(get_auth_organization),
    db: Session = Depends(get_db),
    _: None = require_permission("analytics-organization:view"),
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    org_member_repository = OrganizationMemberRepository(db)

    org_members = org_member_repository.find_by_organization_id(org.id)
    org_team_members = get_team_members(org.id, team_id, db)
    team_events = get_team_events(org_team_members, start_date_dt, end_date_dt, db)
    events = flatten_team_events(team_events)
    set_events = get_unique_events(events)

    members_with_events_ids = {event["member_id"] for event in team_events}
    org_team_members = [m for m in org_team_members if m.member_id in members_with_events_ids]

    team_emails = [m.email for m in org_team_members]
    org_emails = [m.email for m in org_members]

    response = Diagram(
        items=set_events,
        metrics=[
            (
                "inside_team",
                "Inside the team",
                lambda i: {"value": percent_inside_team_events(i, team_emails)},
            ),
            (
                "cross_team",
                "With other teams",
                lambda i: {"value": percent_with_other_teams_events(i, team_emails, org_emails)},
            ),
            (
                "external",
                "Outside the org.",
                lambda i: {"value": percent_outside_organization_events(i, org_emails)},
            ),
        ],
    )
    return {"data": response.as_dict()}


def get_personal_meetings(member: OrganizationMember, start_date_dt, end_date_dt, db):
    if hasattr(
        member, "member_id"
    ):  # quick fix: member.id contains OrganizationTeamMember.id if team_id is not None (func get_team_members)
        member_id = member.member_id
    else:
        member_id = member.id
    calendar_events = get_member_calendar_events(member_id, start_date_dt, end_date_dt, db)
    meetings = filter_meetings(calendar_events)
    meetings = filter_active(meetings, member.email)
    return meetings


class ListType(str, Enum):
    members = "members"
    teams = "teams"


class SortBy(str, Enum):
    meetings_time = "meetings_time"
    deep_work = "deep_work"


@router.get("/analytic/organization/productivity")
def get_team_productivity(
    team_id: Optional[str] = Query(None),
    start_date: str = Query(...),
    end_date: str = Query(...),
    list_type: ListType = Query(ListType.members),
    sort_by: SortBy = Query(SortBy.meetings_time),
    sort_order: SortOrderType = Query(SortOrderType.asc),
    org: Organization = Depends(get_auth_organization),
    db: Session = Depends(get_db),
    _: None = require_permission("analytics-organization:view"),
):
    (start_date_dt, end_date_dt), (prev_start_date_dt, prev_end_date_dt) = get_periods(start_date, end_date)
    count_work_day = count_weekdays(start_date_dt, end_date_dt)

    org_team_members = get_team_members(org.id, team_id, db)
    all_events = []
    prev_all_events = []
    data = []
    for member in org_team_members:
        try:
            events = get_personal_meetings(member, start_date_dt, end_date_dt, db)
            all_events.extend(events)

            prev_events = get_personal_meetings(member, prev_start_date_dt, prev_end_date_dt, db)
            prev_all_events.extend(prev_events)

            info = {
                "id": member.id,
                "name": member.name,
                "email": member.email,
                "photo_url": member.photo_url,
                "meetings_time": calculate_total_events_duration(events),
                "prev_meetings_time": calculate_total_events_duration(prev_events),
                "deep_work": calculate_person_deep_work_time(events, count_work_day),
                "prev_deep_work": calculate_person_deep_work_time(prev_events, count_work_day),
                "transition_time": calculate_transition_time(events),
                "prev_transition_time": calculate_transition_time(prev_events),
                "buffers": calculate_buffer_time(events),
                "prev_buffers": calculate_buffer_time(prev_events),
            }
            data.append(info)
        except Exception:
            continue

    productivity = Diagram(
        items=[],
        metrics=[
            (
                "meetings_time",
                "Time on meetings",
                lambda i: kpi_team_total_time_percent(all_events, prev_all_events, count_work_day, len(org_team_members)),
            ),
            (
                "deep_work",
                " Deep work",
                lambda i: kpi_team_deep_work_time_percent(all_events, prev_all_events, count_work_day, len(org_team_members)),
            ),
            (
                "transition_time",
                "Transition time",
                lambda i: kpi_team_transition_time_percent(all_events, prev_all_events, count_work_day, len(org_team_members)),
            ),
            (
                "buffers",
                "Buffers",
                lambda i: kpi_team_buffers_time_percent(all_events, prev_all_events, count_work_day, len(org_team_members)),
            ),
        ],
    )

    def calculate_percent(data, key):
        from utils.analytics.constants import WORKDAY_HOURS

        kpi = data[key]
        if count_work_day == 0:
            return 0
        return round((kpi / (count_work_day * WORKDAY_HOURS)) * 100)

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
            team_members_data = [m for m in data if m["id"] in team_member_ids]
            help_data.append(
                {
                    "id": team.id,
                    "name": team.name,
                    "meetings_time": sum(m["meetings_time"] for m in team_members_data),
                    "deep_work": sum(m["deep_work"] for m in team_members_data),
                    "transition_time": sum(m["transition_time"] for m in team_members_data),
                    "buffers": sum(m["buffers"] for m in team_members_data),
                }
            )

        columns = [
            ("id", "id"),
            ("name", "name"),
            ("meeting_hours", "meeting_hours", lambda i: i.get("meetings_time", 0)),
            (
                "meetings_time",
                "meetings_time",
                lambda i: calculate_percent(i, "meetings_time"),
            ),
            ("deep_work", "deep_work", lambda i: calculate_percent(i, "deep_work")),
            (
                "transition_time",
                "transition_time",
                lambda i: calculate_percent(i, "transition_time"),
            ),
            ("buffers", "buffers", lambda i: calculate_percent(i, "buffers")),
        ]
        res_data = DataTable(help_data, columns).fetch_dicts(sort_by, sort_order).get("data", [])
    else:
        columns = [
            ("id", "id"),
            (
                "member_profile",
                "member_profile",
                lambda i: {
                    "name": i.get("name", " "),
                    "email": i.get("email"),
                    "photo_url": i.get("member_photo_url"),
                },
            ),
            ("meeting_hours", "meeting_hours", lambda i: i.get("meetings_time", 0)),
            (
                "meetings_time",
                "meetings_time",
                lambda i: calculate_percent(i, "meetings_time"),
            ),
            ("deep_work", "deep_work", lambda i: calculate_percent(i, "deep_work")),
            (
                "transition_time",
                "transition_time",
                lambda i: calculate_percent(i, "transition_time"),
            ),
            ("buffers", "buffers", lambda i: calculate_percent(i, "buffers")),
        ]
        res_data = DataTable(data, columns).fetch_dicts(sort_by, sort_order).get("data", [])
    return {"productivity": productivity.as_dict(), "data": res_data}


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
    auth_member: OrganizationMember = Depends(get_auth_member),
    org: Organization = Depends(get_auth_organization),
    sort_by: Optional[str] = Query(None),
    sort_order: SortOrderType = Query(SortOrderType.asc),
    db: Session = Depends(get_db),
):
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    sort_by = sort_by.split(".")[-1] if isinstance(sort_by, str) else sort_order

    org_team_members = get_team_members(org.id, team_id, db)

    count_work_day = count_weekdays(start_date_dt, end_date_dt)

    if type == TableType.attendees:
        result = []
        for member in org_team_members:
            try:
                member_events = get_personal_meetings(member, start_date_dt, end_date_dt, db)
                info = {
                    "id": member.id,
                    "name": member.name,
                    "email": member.email,
                    "member_photo_url": member.photo_url,
                    "time": calculate_total_events_duration(member_events),
                    "cost": calculate_total_events_cost(member_events, [member]),
                    "ratio": calculate_event_ratio(member_events, count_work_day),
                }
                result.append(info)
            except Exception:
                continue
        columns = [
            ("id", "id"),
            (
                "member_profile",
                "member_profile",
                lambda i: {
                    "name": i.get("name", " "),
                    "email": i.get("email"),
                    "photo_url": i.get("member_photo_url"),
                },
            ),
            ("time", "time"),
            ("ratio", "ratio"),
        ]
        if member_has_permissions(auth_member, "finance:view", db):
            columns.append(("cost", "cost"))

    elif type == TableType.organizers:
        result = []
        for member in org_team_members:
            try:
                member_events = get_personal_meetings(member, start_date_dt, end_date_dt, db)
                organized_events = get_user_organized_events(member_events, member.email)

                meetings_time = calculate_total_events_duration(organized_events)
                recurring_time = calculate_recurring_events_duration(organized_events)
                recurring_percent = round((recurring_time / meetings_time * 100), 2) if meetings_time > 0 else 0.0

                avg_attendees = calculate_avg_attendees(organized_events)

                meetings_wo_agenda_time = calculate_events_without_description_duration(organized_events)
                meetings_wo_agenda_percent = (
                    round((meetings_wo_agenda_time / meetings_time * 100), 2) if meetings_time > 0 else 0.0
                )

                info = {
                    "id": member.id,
                    "name": member.name,
                    "email": member.email,
                    "photo_url": member.photo_url,
                    "count": len(organized_events),
                    "meetings_time": round(meetings_time, 2),
                    "recurring_meetings_percent": recurring_percent,
                    "avg_attendees": avg_attendees,
                    "meetings_wo_agenda_percent": meetings_wo_agenda_percent,
                }
                result.append(info)
            except (Exception,):
                continue

        columns = [
            ("id", "id"),
            (
                "member_profile",
                "member_profile",
                lambda i: {
                    "name": i.get("name", ""),
                    "email": i.get("email"),
                    "photo_url": i.get("photo_url"),
                },
            ),
            ("count", "count"),
            ("meetings_time", "meetings_time"),
            ("recurring_meetings_percent", "recurring_meetings_percent"),
            ("avg_attendees", "avg_attendees"),
            ("meetings_wo_agenda_percent", "meetings_wo_agenda_percent"),
        ]
    elif type == TableType.teams_collab:
        events = flatten_team_events(get_team_events(org_team_members, start_date_dt, end_date_dt, db))
        result = process_teams_collab(get_unique_events(events), org.id, team_id, db)

        columns = [
            ("id", "id"),
            ("team_name", "team_name"),
            (
                "team_manager_profile",
                "team_manager_profile",
                lambda i: {
                    "name": i.get("manager_name", ""),
                    "email": i.get("manager_email"),
                    "photo_url": i.get("manager_photo_url"),
                },
            ),
            ("collab_time", "collab_time"),
        ]
        if member_has_permissions(auth_member, "finance:view", db):
            columns.append(("collab_cost", "collab_cost"))
    else:
        team_events = get_team_events(
            org_team_members,
            start_date_dt,
            end_date_dt,
            db,
            can_filter_filter_active=False,
        )
        events = flatten_team_events(team_events)
        members_with_events_ids = {event["member_id"] for event in team_events}
        org_team_members = [m for m in org_team_members if m.member_id in members_with_events_ids]
        result = process_recurring_events(events, org_team_members)
        columns = [
            ("id", "id"),
            (
                "meeting_profile",
                "meeting",
                lambda i: {
                    "name": i.get("meeting_name"),
                    "duration": "",
                    "recurring_type": "",
                },
            ),
            ("attendees", "attendees"),
            ("cancellation_rate", "cancellation_rate"),
            ("total_time", "total_time"),
        ]
        if member_has_permissions(auth_member, "finance:view", db):
            columns.append(("total_cost", "total_cost"))
    return DataTable(result, columns).fetch_dicts(sort_by, sort_order)
