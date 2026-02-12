from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.modules.enums import InvitationStatusEnum, OrganizationMemberRoleEnum


class InvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Invitation ID")
    token: str = Field(description="Unique invitation token")
    user_id: uuid.UUID = Field(description="ID of the invited user")
    organization_id: uuid.UUID = Field(description="ID of the organization")
    role: OrganizationMemberRoleEnum = Field(description="Role for the invitation")
    status: InvitationStatusEnum = Field(description="Invitation status")
    created_at: datetime = Field(description="Creation timestamp")
    expires_at: datetime | None = Field(description="Expiration timestamp")
