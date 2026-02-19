from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from http import HTTPStatus

import httpx
from google.oauth2.credentials import Credentials

from src.modules.calendar.client import GoogleCalendarClient
from src.modules.calendar.models import UserCalendar
from src.modules.calendar.services.token_service import GoogleTokenService, TokenInvalidError

logger = logging.getLogger(__name__)

# Status codes that should trigger a retry with backoff
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class GoogleCalendarGateway:
    """Gateway for Google Calendar API with automatic retry logic for 403, 429, and 5xx errors."""

    MAX_RETRIES = 2
    BASE_BACKOFF_SECONDS = 1.0

    def __init__(self, google_client: GoogleCalendarClient, token_service: GoogleTokenService) -> None:
        self.google_client = google_client
        self.token_service = token_service

    @staticmethod
    def _is_retryable(status_code: int) -> bool:
        """Check if the status code should trigger a retry with backoff."""
        return status_code in RETRYABLE_STATUS_CODES

    async def list_events_with_retry(
        self,
        credentials: Credentials,
        user_calendar: UserCalendar,
        *,
        sync_token: str | None,
        full_sync: bool,
        time_min: datetime | None = None,
        time_max: datetime | None = None,
    ) -> tuple[list[dict], str | None, Credentials]:
        """List events with automatic retry on 403, 429, and 5xx errors."""
        current_creds = credentials

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                events, next_sync_token = await self.google_client.list_events(
                    access_token=current_creds.token,
                    calendar_email=user_calendar.calendar_email,
                    sync_token=sync_token,
                    full_sync=full_sync,
                    time_min=time_min,
                    time_max=time_max,
                )
                return events, next_sync_token, current_creds
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code

                # Handle retryable errors (429, 5xx) with exponential backoff
                if self._is_retryable(status_code):
                    if attempt < self.MAX_RETRIES:
                        backoff = self.BASE_BACKOFF_SECONDS * (2**attempt)
                        logger.warning(f"list_events got {status_code}, retrying in {backoff}s (attempt {attempt + 1})")
                        await asyncio.sleep(backoff)
                        continue
                    raise

                # Handle 403 with token refresh
                if status_code == HTTPStatus.FORBIDDEN:
                    new_creds = await self.token_service.refresh_access_token(user_calendar)
                    if not new_creds:
                        await self.token_service.invalidate_access(user_calendar, "token_invalid:403")
                        raise TokenInvalidError from exc
                    current_creds = new_creds
                    continue

                raise

        # Should not reach here, but just in case
        raise RuntimeError("Exhausted retries in list_events_with_retry")

    async def get_event_with_retry(
        self,
        credentials: Credentials,
        user_calendar: UserCalendar,
        event_id: str,
    ) -> tuple[dict | None, Credentials]:
        """Get a single event with automatic retry on 403, 429, and 5xx errors."""
        current_creds = credentials

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                event_data = await self.google_client.get_event(
                    access_token=current_creds.token,
                    calendar_email=user_calendar.calendar_email,
                    event_id=event_id,
                )
                return event_data, current_creds
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code

                # Handle retryable errors (429, 5xx) with exponential backoff
                if self._is_retryable(status_code):
                    if attempt < self.MAX_RETRIES:
                        backoff = self.BASE_BACKOFF_SECONDS * (2**attempt)
                        logger.warning(f"get_event got {status_code}, retrying in {backoff}s (attempt {attempt + 1})")
                        await asyncio.sleep(backoff)
                        continue
                    raise

                # Handle 403 with token refresh
                if status_code == HTTPStatus.FORBIDDEN:
                    new_creds = await self.token_service.refresh_access_token(user_calendar)
                    if not new_creds:
                        await self.token_service.invalidate_access(user_calendar, "token_invalid:403")
                        raise TokenInvalidError from exc
                    current_creds = new_creds
                    continue

                raise

        raise RuntimeError("Exhausted retries in get_event_with_retry")

    async def create_event_with_retry(
        self,
        credentials: Credentials,
        user_calendar: UserCalendar,
        body: dict,
    ) -> tuple[dict, Credentials]:
        """Create an event with automatic retry on 403, 429, and 5xx errors."""
        current_creds = credentials

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                event_data = await self.google_client.create_event(
                    access_token=current_creds.token,
                    calendar_email=user_calendar.calendar_email,
                    body=body,
                )
                return event_data, current_creds
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code

                if self._is_retryable(status_code):
                    if attempt < self.MAX_RETRIES:
                        backoff = self.BASE_BACKOFF_SECONDS * (2**attempt)
                        logger.warning(f"create_event got {status_code}, retrying in {backoff}s (attempt {attempt + 1})")
                        await asyncio.sleep(backoff)
                        continue
                    raise

                if status_code == HTTPStatus.FORBIDDEN:
                    new_creds = await self.token_service.refresh_access_token(user_calendar)
                    if not new_creds:
                        await self.token_service.invalidate_access(user_calendar, "token_invalid:403")
                        raise TokenInvalidError from exc
                    current_creds = new_creds
                    continue

                raise

        raise RuntimeError("Exhausted retries in create_event_with_retry")

    async def update_event_with_retry(
        self,
        credentials: Credentials,
        user_calendar: UserCalendar,
        event_id: str,
        body: dict,
    ) -> tuple[dict | None, Credentials]:
        """Update an event with automatic retry on 403, 429, and 5xx errors."""
        current_creds = credentials

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                event_data = await self.google_client.update_event(
                    access_token=current_creds.token,
                    calendar_email=user_calendar.calendar_email,
                    event_id=event_id,
                    body=body,
                )
                return event_data, current_creds
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code

                if self._is_retryable(status_code):
                    if attempt < self.MAX_RETRIES:
                        backoff = self.BASE_BACKOFF_SECONDS * (2**attempt)
                        logger.warning(f"update_event got {status_code}, retrying in {backoff}s (attempt {attempt + 1})")
                        await asyncio.sleep(backoff)
                        continue
                    raise

                if status_code == HTTPStatus.FORBIDDEN:
                    new_creds = await self.token_service.refresh_access_token(user_calendar)
                    if not new_creds:
                        await self.token_service.invalidate_access(user_calendar, "token_invalid:403")
                        raise TokenInvalidError from exc
                    current_creds = new_creds
                    continue

                raise

        raise RuntimeError("Exhausted retries in update_event_with_retry")

    async def safe_list_events(
        self,
        credentials: Credentials,
        user_calendar: UserCalendar,
        time_min: datetime | None,
        time_max: datetime | None,
    ) -> tuple[list[dict], str | None, Credentials] | None:
        """List events, returning None on token invalid instead of raising."""
        try:
            return await self.list_events_with_retry(
                credentials,
                user_calendar,
                sync_token=None,
                full_sync=True,
                time_min=time_min,
                time_max=time_max,
            )
        except TokenInvalidError:
            return None

    async def watch_events_with_retry(
        self,
        credentials: Credentials,
        user_calendar: UserCalendar,
        channel_id: str,
        webhook_url: str,
    ) -> tuple[str, str, str, Credentials]:
        """Set up push notification channel with automatic retry on 403, 429, and 5xx errors."""
        current_creds = credentials

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                c_id, r_id, exp_ts = await self.google_client.watch_events(
                    access_token=current_creds.token,
                    calendar_email=user_calendar.calendar_email,
                    channel_id=channel_id,
                    webhook_url=webhook_url,
                )
                return c_id, r_id, exp_ts, current_creds
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code

                # Handle retryable errors (429, 5xx) with exponential backoff
                if self._is_retryable(status_code):
                    if attempt < self.MAX_RETRIES:
                        backoff = self.BASE_BACKOFF_SECONDS * (2**attempt)
                        logger.warning(f"watch_events got {status_code}, retrying in {backoff}s (attempt {attempt + 1})")
                        await asyncio.sleep(backoff)
                        continue
                    raise

                # Handle 403 with token refresh
                if status_code == HTTPStatus.FORBIDDEN:
                    new_creds = await self.token_service.refresh_access_token(user_calendar)
                    if not new_creds:
                        await self.token_service.invalidate_access(user_calendar, "token_invalid:403")
                        raise TokenInvalidError from exc
                    current_creds = new_creds
                    continue

                raise

        raise RuntimeError("Exhausted retries in watch_events_with_retry")

    async def stop_channel_with_retry(
        self,
        credentials: Credentials,
        user_calendar: UserCalendar,
        channel_id: str,
        resource_id: str,
    ) -> Credentials:
        """Stop a push notification channel with automatic retry on 403, 429, and 5xx errors."""
        current_creds = credentials

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                await self.google_client.stop_channel(
                    access_token=current_creds.token,
                    channel_id=channel_id,
                    resource_id=resource_id,
                )
                return current_creds
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code

                # Handle retryable errors (429, 5xx) with exponential backoff
                if self._is_retryable(status_code):
                    if attempt < self.MAX_RETRIES:
                        backoff = self.BASE_BACKOFF_SECONDS * (2**attempt)
                        logger.warning(f"stop_channel got {status_code}, retrying in {backoff}s (attempt {attempt + 1})")
                        await asyncio.sleep(backoff)
                        continue
                    raise

                # Handle 403 with token refresh
                if status_code == HTTPStatus.FORBIDDEN:
                    new_creds = await self.token_service.refresh_access_token(user_calendar)
                    if not new_creds:
                        await self.token_service.invalidate_access(user_calendar, "token_invalid:403")
                        raise TokenInvalidError from exc
                    current_creds = new_creds
                    continue

                raise

        raise RuntimeError("Exhausted retries in stop_channel_with_retry")
