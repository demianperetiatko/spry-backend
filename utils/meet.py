import requests
from datetime import datetime


def get_calendar_events(token: str, start_date: datetime, end_date: datetime) -> list:
    calendars_url = "https://www.googleapis.com/calendar/v3/users/me/calendarList"
    headers = {"Authorization": f"Bearer {token}"}

    calendar_list_response = requests.get(calendars_url, headers=headers)
    calendar_list = calendar_list_response.json().get("items", [])

    events = []

    for calendar in calendar_list:
        calendar_id = calendar['id']
        url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"

        params = {
            "timeMin": start_date.isoformat() + "Z",
            "timeMax": end_date.isoformat() + "Z",
            "singleEvents": True,
            "orderBy": "startTime",
            "maxResults": 2500
        }

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            events.extend(response.json().get("items", []))

    return events


