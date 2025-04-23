from sqlalchemy.orm import Session
from collections import defaultdict
from typing import List, Dict
from datetime import datetime, timedelta, date
from models.repositories.user_repository import UserRepository
from utils.services import refresh_google_access_token

from utils.analytics.calendar_stats import calculate_recurring_events_cost, calculate_recurring_events_duration



def process_recurring_events(events: List[Dict], members) -> List[Dict]:
    from collections import defaultdict
    recurring_events_summary = []

    grouped_events = defaultdict(list)
    for event in events:
        recurring_id = event.get("recurringEventId")
        if recurring_id:
            grouped_events[recurring_id].append(event)

    for recurring_id, event_group in grouped_events.items():
        recurring_events_summary.append({
            "id": recurring_id,
            "meeting_name":  event_group[0].get('summary'),
            "attendees": len(event_group[0].get('attendees', [])),
            "cancellation_rate": None,
            "total_time": calculate_recurring_events_duration(event_group),
            "total_cost": calculate_recurring_events_cost(event_group, members),
        })

    return recurring_events_summary
