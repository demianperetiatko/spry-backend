from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class MemberTeamDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    team_id: uuid.UUID = Field(description="Team ID")
    team_name: str = Field(description="Team name")
    manager_id: uuid.UUID | None = Field(default=None, description="Manager user ID")
    roles: list[str] = Field(default_factory=list, description="Member roles in this team (manager, member)")


class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="User ID")
    name: str | None = Field(default=None, description="User name")
    photo_url: str | None = Field(default=None, description="User photo URL")
    email: str = Field(description="User email")
    status: str = Field(description="Member status")
    cost: Decimal | None = Field(default=None, description="Total cost (if permission granted)")
    teams: list[MemberTeamDetailResponse] = Field(default_factory=list, description="Teams the member belongs to")


class PaginatedMembersResponse(BaseModel):
    count: int = Field(description="Total number of members")
    limit: int = Field(description="Limit per page")
    offset: int = Field(description="Offset")
    results: list[MemberResponse] = Field(description="List of members")


class AddMembersRequest(BaseModel):
    emails: list[EmailStr] = Field(description="List of email addresses to invite")


class UpdateTeamMemberRequest(BaseModel):
    team_id: uuid.UUID | None = Field(default=None, description="Team ID")
    is_manager: bool = Field(default=False, description="Is member a manager in this team")


class UpdateMemberRequest(BaseModel):
    cost: Decimal | None = Field(default=None, description="Total cost")
    teams: list[UpdateTeamMemberRequest] | None = Field(default=None, description="Teams to update")
