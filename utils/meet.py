import requests
from datetime import datetime


def get_calendar_events(token: str, start_date: datetime, end_date: datetime) -> list:
    url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

    params = {
        "timeMin": start_date.isoformat() + "Z",
        "timeMax": end_date.isoformat() + "Z",
        "singleEvents": True,
        "orderBy": "startTime",
        "maxResults": 2500

    }
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(url, headers=headers, params=params)

    return response.json().get("items", [])


