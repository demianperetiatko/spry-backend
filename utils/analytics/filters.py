def filter_meetings(events: list) -> list:
    meetings = []
    for event in events:
        attendees = event.get("attendees", [])
        start_str = event.get("start", {}).get("dateTime")
        end_str = event.get("end", {}).get("dateTime")
        if start_str and end_str and len(attendees) >= 2:
            meetings.append(event)
    return meetings
