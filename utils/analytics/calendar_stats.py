from typing import List, Dict
from datetime import datetime, timedelta, date


def get_unique_events(events: List[Dict]) -> List[Dict]:
    seen_ids = set()
    unique_events = []
    for event in events:
        event_id = event.get("id")
        if event_id and event_id not in seen_ids:
            seen_ids.add(event_id)
            unique_events.append(event)
    return unique_events


def event_duration(event: Dict) -> float:
    total_seconds = 0
    start_str = event.get("start", {}).get("dateTime")
    end_str = event.get("end", {}).get("dateTime")
    if start_str and end_str:
        start_time = datetime.fromisoformat(start_str)
        end_time = datetime.fromisoformat(end_str)
        total_seconds += (end_time - start_time).total_seconds()
    return total_seconds / 3600


def event_cost(event: Dict, members) -> float:
    ed = event_duration(event)
    total = 0.0
    attendees = event.get("attendees", [])
    attendee_emails = {a.get("email") for a in attendees if "email" in a}
    for member in members:
        email = member.email
        cost_str = member.cost
        if email in attendee_emails:
            total += float(cost_str) if cost_str else 0.0
    return total * ed


def count_events(events: List[Dict]) -> int:
    return len(events)


def count_events_with_2_attendees(events: List[Dict]) -> int:
    return int(sum(1 for event in events if len(event.get('attendees', [])) == 2))


def count_events_with_3_to_5_attendees(events: List[Dict]) -> int:
    return int(sum(1 for event in events if 2 <= len(event.get('attendees', [])) <= 5))


def count_events_with_more_than_5_attendees(events: List[Dict]) -> int:
    return int(sum(1 for event in events if len(event.get('attendees', [])) > 5))


def calculate_event_ratio(events: List[Dict], total_work_days: int = 1) -> float:
    total_duration = calculate_total_events_duration(events)
    return round(total_duration * 100 / (8 * total_work_days), 2)


def calculate_avg_daily_meetings_hour(events: list, total_work_days: int) -> float:
    total_duration = calculate_total_events_duration(events)
    return total_duration / total_work_days


def calculate_recurring_events_duration(events: List[Dict]) -> float:
    return float(sum(event_duration(event) for event in events if 'recurringEventId' in event))


def calculate_recurring_events_cost(events: List[Dict], members) -> float:
    return float(sum(event_cost(event, members) for event in events if 'recurringEventId' in event))


def calculate_single_events_duration(events: List[Dict]) -> float:
    return float(sum(event_duration(event) for event in events if 'recurringEventId' not in event))


def calculate_single_events_cost(events: List[Dict], members) -> float:
    return float(sum(event_cost(event, members) for event in events if 'recurringEventId' not in event))


def calculate_total_events_duration(events: List[Dict]) -> float:
    return float(sum(event_duration(event) for event in events))


def calculate_total_events_cost(events: List[Dict], members) -> float:
    return float(sum(event_cost(event, members) for event in events))


def count_user_organized_events(events: List[Dict], email: str) -> int:
    organized_events = [
        event for event in events
        if event.get("organizer", {}).get("email") == email
           or event.get("creator", {}).get("self") == True
    ]
    return len(organized_events)


def count_cancelled_events(events: list) -> float:
    total_cancelled_meetings = 0
    for event in events:
        if event.get("status") == "cancelled":
            total_cancelled_meetings += 1
    return total_cancelled_meetings

def count_inside_team_events(events: List[Dict], team_emails: List[str]) -> int:
    count = 0
    for event in events:
        attendees = event.get("attendees", [])
        attendee_emails = {att.get("email") for att in attendees if "email" in att}
        if attendee_emails and attendee_emails.issubset(team_emails):
            count += 1
    return count


def count_with_other_teams_events(events: List[Dict], team_emails: List[str], org_emails: List[str]) -> int:
    count = 0
    for event in events:
        attendees = event.get("attendees", [])
        attendee_emails = {att.get("email") for att in attendees if "email" in att}
        if attendee_emails and attendee_emails.issubset(org_emails) and not attendee_emails.issubset(team_emails):
            count += 1
    return count


def count_outside_organization_events(events: List[Dict], org_emails: List[str]) -> int:
    count = 0
    for event in events:
        attendees = event.get("attendees", [])
        attendee_emails = {att.get("email") for att in attendees if "email" in att}
        if attendee_emails and not attendee_emails.issubset(org_emails):
            count += 1
    return count

def count_events_without_description(events: List[Dict]) -> int:
    return sum(1 for event in events if not event.get('description'))

def calculate_deep_work_time_events(events: List[Dict]) -> int:
    total = 0
    for event in events:
        if 'summary' in event and 'deep work time' in event['summary'].lower():
            total += event_duration(event)
    return total

