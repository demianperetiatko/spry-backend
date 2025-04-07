from sqlalchemy.orm import Session
from collections import defaultdict
from typing import List, Dict
from datetime import datetime, timedelta, date
from models.repositories.user_repository import UserRepository
from utils.services import refresh_google_access_token

def get_google_access_token(email: str, db: Session) -> str:
    access_token = None
    user_repository = UserRepository(db)
    user = user_repository.find_by_email(email)
    if user and user.google_refresh_token:
        access_token = refresh_google_access_token(user.google_refresh_token)
    return access_token


def get_events_for_day(events, date):
    events_for_day = []
    for event in events:
        if 'dateTime' in event.get('start', {}) and 'dateTime' in event.get('end', {}):
            event_start = datetime.fromisoformat(event['start']['dateTime'])
            event_end = datetime.fromisoformat(event['end']['dateTime'])
            if event_start.date() == date.date() or event_end.date() == date.date():
                events_for_day.append(event)
        if 'date' in event.get('start', {}) and 'date' in event.get('end', {}):
            # TODO: calendar events that last all day
            continue
    return events_for_day


def group_events_by_date(events: List[Dict], start_date: datetime, end_date: datetime) -> Dict[date, List[Dict]]:
    events_by_date = {}
    current_date = start_date

    while current_date <= end_date:
        events_by_date[current_date.date()] = get_events_for_day(events, current_date)
        current_date += timedelta(days=1)

    return events_by_date


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

def count_recurring_events(events_on_day: List[Dict]) -> int:
    return sum(1 for event in events_on_day if 'recurringEventId' in event)

def count_one_time_events(events_on_day: List[Dict]) -> int:
    return sum(1 for event in events_on_day if 'recurringEventId' not in event)

def analyze_event_participants(events: list, user_email: str) -> list:
    participant_durations = defaultdict(float)

    for event in events:
        if event.get("status") == "cancelled":
            continue

        start = event.get("start", {}).get("dateTime")
        end = event.get("end", {}).get("dateTime")
        if not start or not end:
            continue

        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        except Exception:
            continue

        duration_hours = (end_dt - start_dt).total_seconds() / 3600

        attendees = event.get("attendees", [])
        for person in attendees:
            email = person.get("email")
            if email and email.lower() != user_email.lower():
                participant_durations[email] += duration_hours

    result = [
        {"email": email, "hours": round(hours, 2)}
        for email, hours in participant_durations.items()
    ]
    return result
