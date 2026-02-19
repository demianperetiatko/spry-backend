from __future__ import annotations

import uuid
from dataclasses import dataclass

from src.core.events import Event


@dataclass
class InvitationAcceptedEvent(Event):
    user_id: uuid.UUID
    member_id: uuid.UUID
    user_email: str
