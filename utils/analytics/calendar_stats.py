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


def count_events(events: List[Dict]) -> int:
    return len(events)


def count_events_with_2_attendees(events: List[Dict]) -> int:
    return sum(1 for event in events if len(event.get('attendees', [])) == 2)


def count_events_with_3_to_5_attendees(events: List[Dict]) -> int:
    return sum(1 for event in events if 2 <= len(event.get('attendees', [])) <= 5)


def count_events_with_more_than_5_attendees(events: List[Dict]) -> int:
    return sum(1 for event in events if len(event.get('attendees', [])) > 5)


def calculate_event_ratio(events: List[Dict], total_work_days: int = 1) -> float:
    total_duration = calculate_total_events_duration(events)
    return round(total_duration * 100 / (8 * total_work_days), 2)


def calculate_avg_daily_meetings_hour(events: list, total_work_days: int) -> float:
    total_duration = calculate_total_events_duration(events)
    return total_duration / total_work_days

def calculate_recurring_events_duration(events: List[Dict]) -> float:
    total_seconds = 0
    for event in events:
        if 'recurringEventId' in event:
            start_str = event.get("start", {}).get("dateTime")
            end_str = event.get("end", {}).get("dateTime")
            if start_str and end_str:
                start_time = datetime.fromisoformat(start_str)
                end_time = datetime.fromisoformat(end_str)
                total_seconds += (end_time - start_time).total_seconds()
    return total_seconds / 3600


def calculate_recurring_events_cost(events: List[Dict], prising) -> float:
    return 0


def calculate_single_events_duration(events: List[Dict]) -> float:
    total_seconds = 0
    for event in events:
        if 'recurringEventId' not in event:
            start_str = event.get("start", {}).get("dateTime")
            end_str = event.get("end", {}).get("dateTime")
            if start_str and end_str:
                start_time = datetime.fromisoformat(start_str)
                end_time = datetime.fromisoformat(end_str)
                total_seconds += (end_time - start_time).total_seconds()
    return total_seconds / 3600


def calculate_single_events_cost(events: List[Dict], prising) -> float:
    return 0


def calculate_total_events_duration(events: List[Dict]) -> float:
    total_seconds = 0
    for event in events:
        start_str = event.get("start", {}).get("dateTime")
        end_str = event.get("end", {}).get("dateTime")
        if start_str and end_str:
            start_time = datetime.fromisoformat(start_str)
            end_time = datetime.fromisoformat(end_str)
            total_seconds += (end_time - start_time).total_seconds()
    return total_seconds / 3600


def calculate_total_events_cost(events: List[Dict], prising) -> float:
    return 0


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
