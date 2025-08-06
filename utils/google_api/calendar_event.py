import requests
from datetime import datetime


def create_google_calendar_event(access_token: str, summary: str, start_time: datetime, end_time: datetime,
                                 calendar_id: str = "primary", time_zone: str = "UTC",
                                 description: str = "", location: str = "") -> dict:
    url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
    headers = {
        "Authorization": f"Bearer {access_token}",
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


def update_google_calendar_event(
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


def get_calendars_list(access_token: str) -> dict:
    calendars_url = "https://www.googleapis.com/calendar/v3/users/me/calendarList"
    headers = {"Authorization": f"Bearer {access_token}"}

    calendar_list_response = requests.get(calendars_url, headers=headers)
    calendar_list = calendar_list_response.json().get("items", [])
    return calendar_list


def get_google_calendar_events(access_token: str, start_time: datetime, end_time: datetime, calendar_id: str = "primary") -> list:
    url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "timeMin": start_time.isoformat() + "Z",
        "timeMax": end_time.isoformat() + "Z",
        "singleEvents": True,
        "orderBy": "startTime",
        "maxResults": 2500
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        return response.json().get("items", [])
    else:
        return []

def get_google_calendar_event_info(access_token: str, event_id: str, calendar_id: str = "primary") -> dict | None:
    url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        return None


def get_google_calendar_timezone(access_token: str, calendar_id: str = "primary") -> str:
    url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("timeZone", "UTC")
    else:
        raise Exception(f"Failed to get calendar timezone: {response.status_code} - {response.text}")
