from __future__ import annotations

from dataclasses import dataclass
import uuid

from src.core.events import Event


@dataclass
class InvitationAcceptedEvent(Event):
    user_id: uuid.UUID
    member_id: uuid.UUID
    user_email: str
