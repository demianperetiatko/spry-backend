from __future__ import annotations

import uuid
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.modules.enums import OrganizationTeamMemberTypeEnum


class TeamSortByEnum(str, Enum):
    NAME = "name"
    MEMBERS_COUNT = "members_count"
    MANAGER_EMAIL = "manager_email"


class TeamMemberRequest(BaseModel):
    user_id: uuid.UUID = Field(description="User ID")
    role: OrganizationTeamMemberTypeEnum = Field(description="Team member role (member/manager)")

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: OrganizationTeamMemberTypeEnum) -> OrganizationTeamMemberTypeEnum:
        allowed_types = [OrganizationTeamMemberTypeEnum.MEMBER, OrganizationTeamMemberTypeEnum.MANAGER]
        if value not in allowed_types:
            raise ValueError(f"Invalid role. Allowed values are: {', '.join(t.value for t in allowed_types)}")
        return value


class _TeamBase(BaseModel):
    name: str = Field(description="Team name")
    team_members: list[TeamMemberRequest] = Field(description="List of team members")

    @model_validator(mode="after")
    def validate_manager(self) -> "_TeamBase":
        manager_count = sum(1 for m in self.team_members if m.role == OrganizationTeamMemberTypeEnum.MANAGER)
        if manager_count != 1:
            raise ValueError(f"There must be exactly one member with type '{OrganizationTeamMemberTypeEnum.MANAGER.value}'.")
        return self


class CreateTeamRequest(_TeamBase):
    pass


class UpdateTeamRequest(_TeamBase):
    pass


class TeamMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="User ID")
    user_id: uuid.UUID = Field(description="User ID")
    email: str = Field(description="User email")
    name: str | None = Field(default=None, description="User name")
    photo_url: str | None = Field(default=None, description="User photo URL")
    role: str = Field(description="Member role in team (manager, member)")


class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Team ID")
    name: str = Field(description="Team name")
    members: list[TeamMemberResponse] = Field(default_factory=list, description="Team members")
    members_count: int = Field(description="Number of team members")

    # Fields for v1 compatibility (extracted from members)
    manager_id: uuid.UUID | None = Field(default=None, description="Manager user ID")
    manager_email: str | None = Field(default=None, description="Manager email")
    manager_name: str | None = Field(default=None, description="Manager name")
    manager_photo: str | None = Field(default=None, description="Manager photo URL")

    @model_validator(mode="after")
    def extract_manager_info(self) -> "TeamResponse":
        manager = next(
            (m for m in self.members if m.role == "manager"),
            None,
        )
        if manager:
            self.manager_id = manager.user_id
            self.manager_email = manager.email
            self.manager_name = manager.name
            self.manager_photo = manager.photo_url
        return self


class TeamsListResponse(BaseModel):
    total_count: int = Field(description="Total number of teams")
    data: list[TeamResponse] = Field(description="List of teams")
