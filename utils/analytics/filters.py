from typing import List, Dict, Callable

def filter_meetings(events: list) -> list:
    meetings = []
    for event in events:
        attendees = event.get("attendees", [])
        start_str = event.get("start", {}).get("dateTime")
        end_str = event.get("end", {}).get("dateTime")
        hangout_link = event.get("hangoutLink")
        if start_str and end_str and len(attendees) >= 2 and hangout_link:
            meetings.append(event)
    return meetings

def filter_events_by_attendee_count(events: List[Dict], condition: Callable[[int], bool]) -> List[Dict]:
    return [event for event in events if condition(len(event.get('attendees', [])))]
