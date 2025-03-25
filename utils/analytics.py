from sqlalchemy.orm import Session
from typing import List, Dict
from datetime import datetime, timedelta, date
from models.repositories.user_repository import UserRepository
from utils.services import refresh_google_access_token

def get_google_access_token(email: str, db: Session) -> str:
    user_repository = UserRepository(db)
    user = user_repository.find_by_email(email)
    access_token = refresh_google_access_token(user.google_refresh_token)
    return access_token


def get_events_for_day(events, date):
    events_for_day = []
    for event in events:
        event_start = datetime.fromisoformat(event['start']['dateTime'])
        event_end = datetime.fromisoformat(event['end']['dateTime'])
        if event_start.date() == date.date() or event_end.date() == date.date():
            events_for_day.append(event)
    return events_for_day


def group_events_by_date(events: List[Dict], start_date: datetime, end_date: datetime) -> Dict[date, List[Dict]]:
    events_by_date = {}
    current_date = start_date

    while current_date <= end_date:
        events_by_date[current_date.date()] = get_events_for_day(events, current_date)
        current_date += timedelta(days=1)

    return events_by_date


def count_event_attendees_one_to_one(events_on_day: List[Dict]) -> int:
    return sum(1 for event in events_on_day if len(event.get('attendees', [])) == 2)


def count_event_attendees_three_to_five(events_on_day: List[Dict]) -> int:
    return sum(1 for event in events_on_day if 2 <= len(event.get('attendees', [])) <= 5)


def count_event_attendees_more_than_five(events_on_day: List[Dict]) -> int:
    return sum(1 for event in events_on_day if len(event.get('attendees', [])) > 5)


def calculate_event_ratio(events_on_day: List[Dict]) -> float:
    total_duration = 0

    for event in events_on_day:
        start_time = datetime.fromisoformat(event['start']['dateTime'])
        end_time = datetime.fromisoformat(event['end']['dateTime'])
        total_duration += (end_time - start_time).total_seconds() / 3600  # Перетворюємо у години

    return round(total_duration / 8, 2)

def count_recurring_events(events_on_day: List[Dict]) -> int:
    return sum(1 for event in events_on_day if 'recurringEventId' in event)

def count_one_time_events(events_on_day: List[Dict]) -> int:
    return sum(1 for event in events_on_day if 'recurringEventId' not in event)
