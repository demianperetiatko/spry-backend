import requests
from datetime import datetime


def create_calendar_event(token: str, summary: str, start_time: datetime, end_time: datetime,
                          calendar_id: str = "primary", time_zone: str = "UTC",
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
            "timeZone": time_zone
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": time_zone
        }
    }

    response = requests.post(url, headers=headers, json=event_data)

    if response.status_code == 200 or response.status_code == 201:
        return response.json()
    else:
        raise Exception(f"Failed to create event: {response.status_code} - {response.text}")


def update_calendar_event(
        access_token: str,
        calendar_id: str,
        event_id: str,
        description: str
) -> dict:
    url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    body = {
        "description": description
    }

    response = requests.patch(url, headers=headers, json=body)

    return response.json()


def get_calendars_list(token: str) -> dict:
    calendars_url = "https://www.googleapis.com/calendar/v3/users/me/calendarList"
    headers = {"Authorization": f"Bearer {token}"}

    calendar_list_response = requests.get(calendars_url, headers=headers)
    calendar_list = calendar_list_response.json().get("items", [])
    return calendar_list


def get_calendar_events(token: str, start_date: datetime, end_date: datetime, calendar_id: str = "primary") -> list:
    url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "timeMin": start_date.isoformat() + "Z",
        "timeMax": end_date.isoformat() + "Z",
        "singleEvents": True,
        "orderBy": "startTime",
        "maxResults": 2500
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        return response.json().get("items", [])
    else:
        return []

def get_calendar_event_info(token: str, event_id: str, calendar_id: str = "primary") -> dict | None:
    url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}"
    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        return None
