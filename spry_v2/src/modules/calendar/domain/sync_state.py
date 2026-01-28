from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass
class SyncContext:
    """Context for a calendar sync operation."""

    user_calendar_id: UUID
    sync_token: str | None
    timezone: str
    time_min: datetime | None = None
    time_max: datetime | None = None
    force_full: bool = False


@dataclass
class SyncResult:
    """Result of a calendar sync operation."""

    events_deleted: int = 0
    events_upserted: int = 0
    master_events_upserted: int = 0
    sync_token: str | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "events_deleted": self.events_deleted,
            "events_upserted": self.events_upserted,
            "master_events_upserted": self.master_events_upserted,
            "sync_token": self.sync_token,
            "errors": self.errors,
        }
