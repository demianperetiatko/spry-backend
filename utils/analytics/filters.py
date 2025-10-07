from typing import Callable
from typing import Dict
from typing import List


def filter_meetings(events: list) -> list:
    meetings = []
    for event in events:
        attendees = event.get("attendees", [])
        start_str = event.get("start", {}).get("dateTime")
        end_str = event.get("end", {}).get("dateTime")
        hangout_link = event.get("hangoutLink")

        if start_str and end_str and hangout_link and len(attendees) >= 2:
            meetings.append(event)
    return meetings


def filter_active(events, email: str = ""):
    res = []
    for event in events:
        if event.get("status") == "cancelled":
            continue

        attendees = event.get("attendees", [])

        user_status = None
        for attendee in attendees:
            if attendee.get("email") == email:
                user_status = attendee.get("responseStatus")
                break
        if user_status != "declined":
            res.append(event)
    return res


def filter_by_title(events: list, title) -> list:
    res = []
    for event in events:
        start_str = event.get("start", {}).get("dateTime")
        end_str = event.get("end", {}).get("dateTime")
        summary = event.get("summary")
        if start_str and end_str and summary == title:
            res.append(event)
    return res


def filter_events_by_attendee_count(events: List[Dict], condition: Callable[[int], bool]) -> List[Dict]:
    return [event for event in events if condition(len(event.get("attendees", [])))]
