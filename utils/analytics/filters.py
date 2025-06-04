def filter_meetings(events: list) -> list:
    meetings = []
    for event in events:
        attendees = event.get("attendees", [])
        if len(attendees) > 2:
            meetings.append(event)
    return meetings
