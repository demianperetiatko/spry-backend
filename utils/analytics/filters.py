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

def filter_deet_work_events(events: list) -> list:
    res = []
    for event in events:
        start_str = event.get("start", {}).get("dateTime")
        end_str = event.get("end", {}).get("dateTime")
        summary = event.get("summary")
        if start_str and end_str and "Deep Work Time" == summary:
            res.append(event)
    return res


def filter_events_by_attendee_count(events: List[Dict], condition: Callable[[int], bool]) -> List[Dict]:
    return [event for event in events if condition(len(event.get('attendees', [])))]
