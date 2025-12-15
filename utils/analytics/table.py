from collections import defaultdict
from datetime import datetime
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from sqlalchemy.orm import Session

from models.repositories.organization_team_repository import OrganizationTeamMemberRepository
from models.repositories.organization_team_repository import OrganizationTeamRepository
from utils import get_user_profile
from utils.analytics.calendar_stats import calculate_recurring_events_cost
from utils.analytics.calendar_stats import calculate_recurring_events_duration
from utils.analytics.calendar_stats import calculate_total_events_cost
from utils.analytics.calendar_stats import calculate_total_events_duration


def parse_recurrence_rule(recurrence: List[str]) -> Tuple[Optional[str], Optional[str]]:
    if not recurrence:
        return None, None

    for rule in recurrence:
        if rule.startswith("RRULE:"):
            rule_parts = rule[6:].split(";")
            freq = None
            day = None

            for part in rule_parts:
                if part.startswith("FREQ="):
                    freq = part[5:].lower()
                elif part.startswith("BYDAY="):
                    day = part[6:]

            return freq, day

    return None, None


def format_recurring_type(frequency: Optional[str], day_of_week: Optional[str]) -> str:
    if not frequency:
        return ""

    day_abbreviations = {"MO": "Mon", "TU": "Tue", "WE": "Wed", "TH": "Thu", "FR": "Fri", "SA": "Sat", "SU": "Sun"}

    if frequency == "weekly" and day_of_week and day_of_week in day_abbreviations:
        return f"Weekly on {day_abbreviations[day_of_week]}"
    elif frequency == "daily":
        return "Daily"
    elif frequency == "monthly":
        return "Monthly"
    elif frequency == "yearly":
        return "Yearly"
    else:
        return frequency.capitalize()


def get_event_duration(event: Dict) -> str:
    start_str = event.get("start", {}).get("dateTime", "")
    end_str = event.get("end", {}).get("dateTime", "")

    if not start_str or not end_str:
        return ""

    try:
        start_time = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(end_str.replace("Z", "+00:00"))

        duration_minutes = int((end_time - start_time).total_seconds() / 60)
        hours = duration_minutes // 60
        minutes = duration_minutes % 60

        if hours == 0 and minutes == 0:
            return ""
        elif hours == 0:
            return f"{minutes}m"
        elif minutes == 0:
            return f"{hours}h"
        else:
            return f"{hours}h {minutes}m"
    except (ValueError, TypeError):
        return ""


def calculate_cancellation_rate(events: List[Dict], members: List) -> float:
    total_instances = len(events)
    total_cancellations = 0
    member_emails = {member.email for member in members}

    for event in events:
        if event.get("status") == "cancelled":
            total_cancellations += 1
            continue

        for attendee in event.get("attendees", []):
            if attendee.get("email") in member_emails and attendee.get("responseStatus") == "declined":
                total_cancellations += 1
                break

    if total_instances == 0:
        return 0.0

    return round((total_cancellations / total_instances * 100), 2)


def get_recurrence_info_for_event(event: Dict, db, member_id: str | None = None) -> Tuple[Optional[str], Optional[str]]:
    recurring_id = event.get("recurringEventId")
    if not recurring_id:
        return None, None

    from models.repositories.organization_member_repository import OrganizationMemberCalendarRepository
    from models.repositories.organization_member_repository import OrganizationMemberRepository
    from utils.google_api import get_google_calendar_event_info

    emails = set()

    organizer = event.get("organizer", {})
    organizer_email = organizer.get("email")
    if organizer_email:
        emails.add(organizer_email.lower())

    attendees = event.get("attendees", [])
    for attendee in attendees:
        attendee_email = attendee.get("email")
        if attendee_email:
            emails.add(attendee_email.lower())

    if not emails:
        return None, None

    member_repository = OrganizationMemberRepository(db)
    member_calendar_repository = OrganizationMemberCalendarRepository(db)

    for email in emails:
        try:
            member = member_repository.find_by_email(email)
            if not member:
                continue

            calendars = member_calendar_repository.find_by_member_id(member.id)
            if not calendars:
                continue

            for calendar in calendars:
                try:
                    master_event = get_google_calendar_event_info(
                        access_token=calendar.access_token, event_id=recurring_id, calendar_id="primary"
                    )

                    if master_event and "recurrence" in master_event:
                        return parse_recurrence_rule(master_event.get("recurrence", []))
                except (Exception,):
                    continue
        except (Exception,):
            continue

    return None, None


def process_recurring_events(events: List[Dict], members, db: Session) -> List[Dict]:
    recurring_events_summary = []

    grouped_events = defaultdict(list)
    for event in events:
        recurring_id = event.get("recurringEventId")
        if recurring_id:
            grouped_events[recurring_id].append(event)

    for recurring_id, event_group in grouped_events.items():
        organizer_email = event_group[0].get("organizer", {}).get("email", "")
        organizer_profile = get_user_profile(organizer_email, db) if organizer_email else None

        first_event = event_group[0]

        member_id = first_event.get("member_id") or (members[0].member_id if hasattr(members[0], "member_id") else members[0].id)
        frequency, day_of_week = get_recurrence_info_for_event(first_event, db, member_id)

        if frequency is None and day_of_week is None:
            frequency, day_of_week = None, None

        recurring_events_summary.append(
            {
                "id": recurring_id,
                "meeting_name": first_event.get("summary"),
                "attendees": len(first_event.get("attendees", [])),
                "cancellation_rate": calculate_cancellation_rate(event_group, members),
                "total_time": calculate_recurring_events_duration(event_group),
                "total_cost": calculate_recurring_events_cost(event_group, members),
                "recurring_type": format_recurring_type(frequency, day_of_week),
                "duration": get_event_duration(first_event),
                "organizer": organizer_profile,
            }
        )

    return recurring_events_summary


def process_teams_collab(events: List[Dict], organization_id, main_team_id, db):
    org_team_repository = OrganizationTeamRepository(db)
    org_team_member_repository = OrganizationTeamMemberRepository(db)

    main_team_members = org_team_member_repository.find_by_team_id(main_team_id)
    main_team_emails = [member.email for member in main_team_members]

    result = []

    for team in org_team_repository.find_by_organization_id(organization_id):
        if team.id == main_team_id:
            continue

        team_members = org_team_member_repository.find_by_team_id(team.id)
        team_member_emails = [member.email for member in team_members]

        combined_members = team_members + main_team_members
        event_collab = []

        for event in events:
            attendees = event.get("attendees", [])
            attendee_emails = [attendee.get("email") for attendee in attendees if "email" in attendee]

            found = False
            for email in attendee_emails:
                if email in team_member_emails and email not in main_team_emails:
                    found = True
                    break

            if found:
                event_collab.append(event)

        info = {
            "id": team.id,
            "team_name": team.name,
            "manager_id": team.manager_id,
            "manager_name": team.manager_name,
            "manager_email": team.manager_email,
            "manager_photo_url": team.manager_photo,
            "collab_time": calculate_total_events_duration(event_collab),
            "collab_cost": calculate_total_events_cost(event_collab, combined_members),
        }
        result.append(info)

    return result
