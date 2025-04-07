from typing import List, Dict
from datetime import datetime, timedelta, date


def count_event_attendees_one_to_one(events: List[Dict]) -> int:
    return sum(1 for event in events if len(event.get('attendees', [])) == 2)


def count_event_attendees_three_to_five(events: List[Dict]) -> int:
    return sum(1 for event in events if 2 <= len(event.get('attendees', [])) <= 5)


def count_event_attendees_more_than_five(events: List[Dict]) -> int:
    return sum(1 for event in events if len(event.get('attendees', [])) > 5)


def calculate_event_ratio(events: List[Dict]) -> float:
    total_duration = 0

    for event in events:
        if 'dateTime' in event.get('start', {}) and 'dateTime' in event.get('end', {}):
            start_time = datetime.fromisoformat(event['start']['dateTime'])
            end_time = datetime.fromisoformat(event['end']['dateTime'])
            total_duration += (end_time - start_time).total_seconds() / 3600

    return round(total_duration * 100 / 8, 2)


def calculate_recurring_event_time(events: List[Dict]) -> float:
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


def calculate_one_time_event_time(events: List[Dict]) -> float:
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
