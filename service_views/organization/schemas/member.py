from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict


class MemberTeamDetailResponse(BaseModel):
    team_id: UUID
    team_name: str
    manager_id: UUID
    is_manager: bool

    model_config = ConfigDict(from_attributes=True)


class MemberResponse(BaseModel):
    id: UUID
    name: str | None = None
    photo_url: str | None = None
    email: str
    status: str
    roles: list[str]
    cost: float | None = None
    teams: list[MemberTeamDetailResponse] = []

    model_config = ConfigDict(from_attributes=True)


class PaginatedMembersResponse(BaseModel):
    count: int
    limit: int
    offset: int
    results: list[MemberResponse]
