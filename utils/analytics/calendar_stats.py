from typing import List, Dict, Set
from datetime import datetime, timedelta, date
from .filters import filter_events_by_attendee_count

from .constants import BUFFER_PER_SIDE_HOURS, MAX_TRANSITION_TIME_HOURS,  WORKDAY_HOURS


def get_attendee_emails(event: Dict) -> Set[str]:
    return {att.get("email") for att in event.get("attendees", []) if "email" in att}


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


def percent_events_with_2_attendees(events: List[Dict]) -> float:
    if not events:
        return 0.0
    filtered = filter_events_by_attendee_count(events, lambda count: count == 2)
    return round(len(filtered) / len(events) * 100, 2)


def percent_events_with_3_to_5_attendees(events: List[Dict]) -> float:
    if not events:
        return 0.0
    filtered = filter_events_by_attendee_count(events, lambda count: 3 <= count <= 5)
    return round(len(filtered) / len(events) * 100, 2)


def percent_events_with_more_than_5_attendees(events: List[Dict]) -> float:
    if not events:
        return 0.0
    filtered = filter_events_by_attendee_count(events, lambda count: count > 5)
    return round(len(filtered) / len(events) * 100, 2)


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


def percent_inside_team_events(events: List[Dict], team_emails: List[str]) -> float:
    if not events:
        return 0.0
    team_set = set(team_emails)
    count = sum(
        1 for event in events
        if (emails := get_attendee_emails(event)) and emails.issubset(team_set)
    )
    return round(count / len(events) * 100, 2)


def percent_with_other_teams_events(events: List[Dict], team_emails: List[str], org_emails: List[str]) -> float:
    if not events:
        return 0.0
    team_set = set(team_emails)
    org_set = set(org_emails)
    count = sum(
        1 for event in events
        if (emails := get_attendee_emails(event)) and emails.issubset(org_set) and not emails.issubset(team_set)
    )
    return round(count / len(events) * 100, 2)


def percent_outside_organization_events(events: List[Dict], org_emails: List[str]) -> float:
    if not events:
        return 0.0
    org_set = set(org_emails)
    count = sum(
        1 for event in events
        if (emails := get_attendee_emails(event)) and not emails.issubset(org_set)
    )
    return round(count / len(events) * 100, 2)


def count_events_without_description(events: List[Dict]) -> int:
    return sum(1 for event in events if not event.get('description'))


def calculate_buffer_time(events: List[Dict]) -> float:
    event_times = []
    for event in events:
        start_str = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date")
        end_str = event.get("end", {}).get("dateTime") or event.get("end", {}).get("date")
        if not start_str or not end_str:
            continue

        start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        event_times.append((start, end))

    event_times.sort(key=lambda x: x[0])

    blocks = []
    extra_gap_time = 0.0
    if not event_times:
        return 0.0

    current_block_start, current_block_end = event_times[0]

    for start, end in event_times[1:]:
        gap_hours = (start - current_block_end).total_seconds() / 3600
        if gap_hours < 2 * BUFFER_PER_SIDE_HOURS:
            extra_gap_time += gap_hours
            if end > current_block_end:
                current_block_end = end
        else:
            blocks.append((current_block_start, current_block_end))
            current_block_start, current_block_end = start, end
    blocks.append((current_block_start, current_block_end))

    return BUFFER_PER_SIDE_HOURS * 2 * len(blocks) + extra_gap_time


def calculate_transition_time(events: List[Dict]) -> float:
    event_times = []
    for event in events:
        start_str = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date")
        end_str = event.get("end", {}).get("dateTime") or event.get("end", {}).get("date")
        if not start_str or not end_str:
            continue

        start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        event_times.append((start, end))

    event_times.sort(key=lambda x: x[0])

    if not event_times or len(event_times) < 2:
        return 0.0

    total_gap = 0.0
    for i in range(1, len(event_times)):
        prev_end = event_times[i - 1][1]
        curr_start = event_times[i][0]
        gap_hours = (curr_start - prev_end).total_seconds() / 3600

        if BUFFER_PER_SIDE_HOURS * 2 <= gap_hours < MAX_TRANSITION_TIME_HOURS:
            total_gap += gap_hours

    return total_gap


def calculate_deep_work_time(events: List[Dict], count_work_day) -> float:
    event_time = calculate_total_events_duration(events)
    buffer_time = calculate_buffer_time(events)
    transition_time = calculate_transition_time(events)
    return WORKDAY_HOURS * count_work_day - event_time - buffer_time - transition_time
