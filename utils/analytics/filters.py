from typing import List, Dict, Callable

def filter_meetings(events: list, email: str= "") -> list:
    meetings = []
    for event in events:
        if event.get("status") == "cancelled":
            continue

        attendees = event.get("attendees", [])
        start_str = event.get("start", {}).get("dateTime")
        end_str = event.get("end", {}).get("dateTime")
        hangout_link = event.get("hangoutLink")

        user_status = None
        for attendee in attendees:
            if attendee.get("email") == email:
                user_status = attendee.get("responseStatus")
                break

        if (
            start_str and end_str and hangout_link and
            len(attendees) >= 2 and
            user_status != "declined"
        ):
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
