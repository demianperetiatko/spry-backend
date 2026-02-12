from __future__ import annotations

from datetime import datetime, timedelta, timezone

FULL_SYNC_DAYS = 180


def _get_end_of_year() -> datetime:
    """Get December 31st 23:59:59 UTC of the current year."""
    now = datetime.now(timezone.utc)
    return datetime(now.year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)


def get_full_sync_range() -> tuple[datetime, datetime]:
    """Get the default sync window for full synchronization."""
    now = datetime.now(timezone.utc)
    return now - timedelta(days=FULL_SYNC_DAYS), _get_end_of_year()


def compute_sync_window(earliest: datetime | None) -> tuple[datetime, datetime]:
    """
    Compute sync window: from first event (or now - 180 days) to end of current year.
    """
    now = datetime.now(timezone.utc)
    start = earliest or (now - timedelta(days=FULL_SYNC_DAYS))
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    return start, _get_end_of_year()
