from __future__ import annotations

import logging
from datetime import datetime
from http import HTTPStatus

import httpx

from src.core.exceptions import ServiceException

logger = logging.getLogger(__name__)


class StaleSyncTokenError(Exception):
    pass


class TooManyEventsError(Exception):
    """Raised when calendar has more events than the maximum limit."""

    pass


class GoogleCalendarClient:
    BASE_URL = "https://www.googleapis.com/calendar/v3"
    MAX_EVENTS_LIMIT = 50000  # Safety limit to prevent OOM

    async def list_events(
        self,
        *,
        access_token: str,
        calendar_email: str,
        sync_token: str | None,
        full_sync: bool,
        time_min: datetime | None = None,
        time_max: datetime | None = None,
    ) -> tuple[list[dict], str | None]:
        params: dict[str, str] = {
            "singleEvents": "true",
            "showDeleted": "true",
            "maxResults": "2500",
        }
        if not full_sync and sync_token:
            params["syncToken"] = sync_token
        else:
            if time_min is not None:
                params["timeMin"] = time_min.isoformat()
            if time_max is not None:
                params["timeMax"] = time_max.isoformat()

        headers = {"Authorization": f"Bearer {access_token}"}
        events: list[dict] = []
        next_sync_token: str | None = None

        async with httpx.AsyncClient(timeout=30.0) as client:
            page_token: str | None = None
            while True:
                paged_params = params.copy()
                if page_token:
                    paged_params["pageToken"] = page_token

                response = await client.get(
                    f"{self.BASE_URL}/calendars/{calendar_email}/events",
                    headers=headers,
                    params=paged_params,
                )
                if response.status_code == HTTPStatus.GONE:
                    raise StaleSyncTokenError("Stale sync token")
                response.raise_for_status()

                payload = response.json()
                events.extend(payload.get("items", []))
                next_sync_token = payload.get("nextSyncToken", next_sync_token)
                page_token = payload.get("nextPageToken")

                # Safety check to prevent OOM for calendars with excessive events
                if len(events) >= self.MAX_EVENTS_LIMIT:
                    logger.warning(
                        f"Calendar {calendar_email} exceeded max events limit ({self.MAX_EVENTS_LIMIT}), truncating results"
                    )
                    break

                if not page_token:
                    break

        return events, next_sync_token

    async def watch_events(
        self,
        *,
        access_token: str,
        calendar_email: str,
        channel_id: str,
        webhook_url: str,
    ) -> tuple[str, str, str]:
        headers = {"Authorization": f"Bearer {access_token}"}
        body = {
            "id": channel_id,
            "type": "web_hook",
            "address": webhook_url,
            "params": {"ttl": "604800"},
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/calendars/{calendar_email}/events/watch",
                headers=headers,
                json=body,
            )
            if response.status_code != HTTPStatus.OK:
                logger.error(f"Google Watch Error: {response.text}")
                raise ServiceException(
                    "Failed to create watch subscription",
                    code="google_watch_error",
                    status_code=response.status_code,
                )
            data = response.json()
            return data["id"], data["resourceId"], str(data.get("expiration", ""))

    async def get_event(
        self,
        *,
        access_token: str,
        calendar_email: str,
        event_id: str,
    ) -> dict | None:
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.BASE_URL}/calendars/{calendar_email}/events/{event_id}",
                headers=headers,
            )
            if response.status_code == HTTPStatus.NOT_FOUND:
                return None
            response.raise_for_status()
            return response.json()

    async def create_event(
        self,
        *,
        access_token: str,
        calendar_email: str,
        body: dict,
        send_updates: str = "none",
    ) -> dict:
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"sendUpdates": send_updates}

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/calendars/{calendar_email}/events",
                headers=headers,
                json=body,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def update_event(
        self,
        *,
        access_token: str,
        calendar_email: str,
        event_id: str,
        body: dict,
        send_updates: str = "none",
    ) -> dict | None:
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"sendUpdates": send_updates}

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.patch(
                f"{self.BASE_URL}/calendars/{calendar_email}/events/{event_id}",
                headers=headers,
                json=body,
                params=params,
            )
            if response.status_code == HTTPStatus.NOT_FOUND:
                return None
            response.raise_for_status()
            return response.json()

    async def stop_channel(self, *, access_token: str, channel_id: str, resource_id: str) -> None:
        headers = {"Authorization": f"Bearer {access_token}"}
        body = {"id": channel_id, "resourceId": resource_id}

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(f"{self.BASE_URL}/channels/stop", headers=headers, json=body)
            if response.status_code not in (HTTPStatus.OK, HTTPStatus.NO_CONTENT, HTTPStatus.NOT_FOUND):
                response.raise_for_status()
