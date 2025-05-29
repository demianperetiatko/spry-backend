from sqlalchemy.orm import Session
from collections import defaultdict
from typing import List, Dict
from datetime import datetime, timedelta, date

from utils.services import refresh_google_access_token

from utils.analytics.calendar_stats import event_duration, event_cost




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


def analyze_event_participants(events: list, user_email: str) -> list:
    participant_durations = defaultdict(float)
    for event in events:
        duration_hours = event_duration(event)
        attendees = event.get("attendees", [])
        for person in attendees:
            email = person.get("email")
            if email and email.lower() != user_email.lower():
                participant_durations[email] += duration_hours

    result = [
        {"email": email, "collab_time": round(hours, 2)}
        for email, hours in participant_durations.items()
    ]
    return result
