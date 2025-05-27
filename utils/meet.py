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
            for event in response.json().get("items", []):
                if 'dateTime' in event.get('start', {}):
                    events.append(event)

    return events


def create_calendar_event(token: str, summary: str, start_time: datetime, end_time: datetime, calendar_id: str = "primary",
                          description: str = "", location: str = "") -> dict:
    url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    event_data = {
        "summary": summary,
        "description": description,
        "location": location,
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": "UTC"
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": "UTC"
        }
    }

    response = requests.post(url, headers=headers, json=event_data)

    if response.status_code == 200 or response.status_code == 201:
        return response.json()
    else:
        raise Exception(f"Failed to create event: {response.status_code} - {response.text}")
