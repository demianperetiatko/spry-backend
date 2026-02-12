from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.modules.enums import CalendarEventStatusEnum

logger = logging.getLogger(__name__)


class GoogleEventMapper:
    """Maps Google Calendar events to internal event format."""

    @staticmethod
    def extract_dt(source: dict, default_tz: str) -> tuple[datetime | None, str | None, bool]:
        """Extract datetime from Google Calendar event start/end object."""
        if not source:
            return None, None, False

        tz_hint = source.get("timeZone") or default_tz
        is_all_day = "date" in source and "dateTime" not in source
        val = source.get("dateTime") or source.get("date")

        if not val:
            return None, tz_hint, is_all_day

        try:
            if is_all_day:
                # All-day events: store as UTC midnight to prevent incorrect display across timezones.
                # The is_all_day flag is used by frontend to display correctly.
                dt = datetime.fromisoformat(f"{val}T00:00:00").replace(tzinfo=timezone.utc)
            else:
                dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=ZoneInfo(tz_hint) if tz_hint else timezone.utc)
            return dt, tz_hint, is_all_day
        except (ValueError, TypeError):
            return None, tz_hint, is_all_day

    @staticmethod
    def map_event(
        event: dict, user_calendar_id: uuid.UUID, default_tz: str, synced_at: datetime
    ) -> tuple[dict | None, list[dict]]:
        """Map a Google Calendar event to internal format."""
        start_dt, start_tz, is_all_day = GoogleEventMapper.extract_dt(event.get("start", {}), default_tz)
        end_dt, end_tz, _ = GoogleEventMapper.extract_dt(event.get("end", {}), default_tz)

        if not start_dt or not end_dt:
            return None, []

        event_id = event.get("id")
        if not event_id:
            logger.warning(f"Event missing id, skipping: {event.get('summary', 'Unknown')}")
            return None, []

        recurring_event_id = event.get("recurringEventId")
        recurrence = event.get("recurrence")

        if recurring_event_id:
            logger.debug(
                f"map_event: Event {event_id} has recurringEventId={recurring_event_id}, "
                f"recurrence={recurrence}, has_recurrence_in_event={bool(recurrence)}"
            )

        raw_event = event
        if is_all_day:
            all_day_date = event.get("start", {}).get("date") or event.get("end", {}).get("date")
            if all_day_date:
                raw_event = dict(event)
                raw_event["_spry_all_day_date"] = all_day_date

        mapped = {
            "id": event_id,
            "google_event_id": event_id,
            "etag": event.get("etag"),
            "summary": event.get("summary"),
            "description": event.get("description"),
            "location": event.get("location"),
            "start_datetime": start_dt,
            "end_datetime": end_dt,
            "start_timezone": start_tz,
            "end_timezone": end_tz,
            "is_all_day": is_all_day,
            "status": event.get("status", CalendarEventStatusEnum.CONFIRMED.value),
            "html_link": event.get("htmlLink"),
            "hangout_link": event.get("hangoutLink"),
            "organizer_email": event.get("organizer", {}).get("email"),
            "creator_email": event.get("creator", {}).get("email"),
            "is_self_created": event.get("creator", {}).get("self", False),
            "recurring_event_id": event.get("recurringEventId"),
            "recurrence": event.get("recurrence"),
            "conference_data": event.get("conferenceData"),
            "raw_data": raw_event,
            "synced_at": synced_at,
            "user_calendar_id": user_calendar_id,
        }

        attendees = []
        for att in event.get("attendees", []):
            if email := att.get("email"):
                attendees.append(
                    {
                        "email": email,
                        "display_name": att.get("displayName"),
                        "response_status": att.get("responseStatus", "needsAction"),
                        "organizer": att.get("organizer", False),
                        "optional": att.get("optional", False),
                        "resource": att.get("resource", False),
                    }
                )

        return mapped, attendees

    @staticmethod
    def process_events_payload(
        events: list[dict], user_calendar_id: uuid.UUID, default_tz: str
    ) -> tuple[list[str], list[dict], dict[str, list[dict]]]:
        """Process a list of Google Calendar events into delete/upsert operations."""
        to_delete = []
        to_upsert = []
        attendees_map = {}
        synced_at = datetime.now(timezone.utc)

        for event in events:
            google_event_id = event.get("id")
            if not google_event_id:
                continue

            if event.get("status") == CalendarEventStatusEnum.CANCELLED.value:
                to_delete.append(google_event_id)
                continue

            mapped, attendees = GoogleEventMapper.map_event(event, user_calendar_id, default_tz, synced_at)
            if mapped:
                to_upsert.append(mapped)
                attendees_map[google_event_id] = attendees

        return to_delete, to_upsert, attendees_map
