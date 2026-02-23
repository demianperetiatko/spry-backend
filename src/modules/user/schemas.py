from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.modules.enums import OrganizationMemberRoleEnum, OrganizationMemberStatusEnum


class UserInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="User ID")
    photo_url: str | None = Field(default=None, description="Photo URL")
    email: str = Field(description="Email")
    name: str | None = Field(default=None, description="Name")


class OrganizationMemberInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    organization_id: UUID = Field(description="Organization ID")
    organization_name: str | None = Field(default=None, description="Organization name")
    role: OrganizationMemberRoleEnum = Field(description="Member role")
    status: OrganizationMemberStatusEnum = Field(description="Member status")
    member_id: UUID = Field(description="Organization member ID")
    type: str | None = Field(default=None, description="User type in this organization (admin/manager/member)")
    permissions: list[str] = Field(default_factory=list, description="User permissions in this organization")


class UserWithOrganizationsInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="User ID")
    photo_url: str | None = Field(default=None, description="Photo URL")
    email: str = Field(description="Email")
    name: str | None = Field(default=None, description="Name")
    organizations: list[OrganizationMemberInfo] = Field(default_factory=list, description="List of organizations")
