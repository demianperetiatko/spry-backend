from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from src.modules.analytics.common.schemas import (  # noqa: F401  re-export shared DTOs
    AnalyticsDateRangeParams,
    DistributionMetric,
    KPIMetric,
    KPIMetricProductivityValue,
    MeetingChartItem,
    MeetingChartResponse,
    ParticipantMetric,
    ProductivityMetric,
    RecurringMeetingTableRow,
    SortOrderType,
    UserProfileDTO,
)
from src.shared.rounded_decimal import RoundedDecimal

T = TypeVar("T")


class AnalyticsType(str, Enum):
    TIME = "time"
    COST = "cost"


class TableType(str, Enum):
    ATTENDEES = "attendees"
    ORGANIZERS = "organizers"
    TEAMS_COLLAB = "teams_collab"
    RECURRING_MEETINGS = "recurring_meetings"


class ListType(str, Enum):
    MEMBERS = "members"
    TEAMS = "teams"


class SortByType(str, Enum):
    TIME = "time"
    COST = "cost"
    RATIO = "ratio"
    COUNT = "count"
    MEETINGS_TIME = "meetings_time"
    DEEP_WORK = "deep_work"
    TRANSITION_TIME = "transition_time"
    BUFFERS = "buffers"
    RECURRING_MEETINGS_PERCENT = "recurring_meetings_percent"
    AVG_ATTENDEES = "avg_attendees"
    MEETINGS_WO_AGENDA_PERCENT = "meetings_wo_agenda_percent"
    COLLAB_TIME = "collab_time"
    TEAM_NAME = "team_name"
    TOTAL_TIME = "total_time"
    CANCELLATION_RATE = "cancellation_rate"
    MEETING_NAME = "meeting.name"


class OrganizationAnalyticsParams(BaseModel):
    start_date: str
    end_date: str
    team_id: UUID | None = None

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, value: str) -> str:
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return value
        except ValueError:
            raise ValueError("Invalid date format. Expected YYYY-MM-DD")

    def parse_start_datetime(self) -> datetime:
        return datetime.strptime(self.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    def parse_end_datetime(self) -> datetime:
        return datetime.strptime(self.end_date, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc
        )

    def parse_periods(self) -> tuple[tuple[datetime, datetime], tuple[datetime, datetime]]:
        start_date = datetime.strptime(self.start_date, "%Y-%m-%d")
        end_date = datetime.strptime(self.end_date, "%Y-%m-%d")

        current_start = datetime.combine(start_date.date(), datetime.min.time()).replace(tzinfo=timezone.utc)
        current_end = datetime.combine(end_date.date(), datetime.max.time()).replace(tzinfo=timezone.utc)

        delta = current_end - current_start

        prev_end = current_start - timedelta(days=1)
        prev_start = prev_end - delta

        prev_start = datetime.combine(prev_start.date(), datetime.min.time()).replace(tzinfo=timezone.utc)
        prev_end = datetime.combine(prev_end.date(), datetime.max.time()).replace(tzinfo=timezone.utc)

        return (current_start, current_end), (prev_start, prev_end)


class KPIsResponse(BaseModel):
    data: list[KPIMetric]

    model_config = ConfigDict(from_attributes=True)


class ParticipantsResponse(BaseModel):
    data: list[ParticipantMetric]

    model_config = ConfigDict(from_attributes=True)


class DistributionResponse(BaseModel):
    data: list[DistributionMetric]

    model_config = ConfigDict(from_attributes=True)


class ProductivityResponse(BaseModel):
    productivity: list[ProductivityMetric]
    data: list[dict[str, Any]] | None = None

    model_config = ConfigDict(from_attributes=True)


class MemberProfileDTO(BaseModel):
    id: UUID | str
    name: str | None
    email: str
    photo_url: str | None

    model_config = ConfigDict(from_attributes=True)


class AttendeeTableRow(BaseModel):
    id: UUID | str
    member_profile: MemberProfileDTO | None = None
    time: RoundedDecimal
    ratio: RoundedDecimal | None = None
    cost: RoundedDecimal | None = None

    model_config = ConfigDict(from_attributes=True)


class OrganizerTableRow(BaseModel):
    id: UUID | str
    member_profile: MemberProfileDTO | None = None
    count: int
    meetings_time: RoundedDecimal
    recurring_meetings_percent: RoundedDecimal
    avg_attendees: RoundedDecimal
    meetings_wo_agenda_percent: RoundedDecimal

    model_config = ConfigDict(from_attributes=True)


class TeamManagerProfileDTO(BaseModel):
    id: UUID | str | None = None
    name: str | None = None
    email: str | None = None
    photo_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class TeamCollaborationRow(BaseModel):
    id: UUID | str
    team_name: str
    team_manager_profile: TeamManagerProfileDTO | None = None
    collab_time: RoundedDecimal
    collab_cost: RoundedDecimal | None = None

    model_config = ConfigDict(from_attributes=True)


class TableResponseDTO(BaseModel, Generic[T]):
    total_count: int
    data: list[T]


class TableResponse(BaseModel):
    total_count: int
    data: list[dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)
