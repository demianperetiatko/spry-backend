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
