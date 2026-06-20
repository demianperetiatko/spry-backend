from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from src.shared.rounded_decimal import RoundedDecimal

T = TypeVar("T")


class SortOrderType(str, Enum):
    ASC = "asc"
    DESC = "desc"


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _month_start_str() -> str:
    today = datetime.now(timezone.utc)
    return today.replace(day=1).strftime("%Y-%m-%d")


class AnalyticsDateRangeParams(BaseModel):
    start_date: str = ""
    end_date: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.start_date:
            object.__setattr__(self, "start_date", _month_start_str())
        if not self.end_date:
            object.__setattr__(self, "end_date", _today_str())

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def validate_date_format(cls, value: str) -> str:
        if not value:
            return value
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


class UserProfileDTO(BaseModel):
    id: UUID | str
    name: str | None
    email: str
    photo_url: str | None

    model_config = ConfigDict(from_attributes=True)


class KPIResultDTO(BaseModel):
    value: RoundedDecimal | int | None
    change: str | None
    positive: bool | None
    type_value: str


class KPIMetric(BaseModel):
    key: str
    title: str
    value: RoundedDecimal | None = None
    change: str | None = None
    positive: bool | None = None
    type_value: str

    model_config = ConfigDict(from_attributes=True)


class KPIMetricProductivityValue(BaseModel):
    percent: RoundedDecimal
    hours: RoundedDecimal


class MeetingChartItem(BaseModel):
    date: str
    recurring: RoundedDecimal | None = None
    one_time: RoundedDecimal | None = None
    ratio: RoundedDecimal | None = None

    model_config = ConfigDict(from_attributes=True)


class MeetingChartResponse(BaseModel):
    data: list[MeetingChartItem]

    model_config = ConfigDict(from_attributes=True)


class MetricValue(BaseModel):
    percent: RoundedDecimal
    hours: RoundedDecimal


class ParticipantMetric(BaseModel):
    key: str
    title: str
    value: MetricValue

    model_config = ConfigDict(from_attributes=True)


class DistributionMetric(BaseModel):
    key: str
    title: str
    value: MetricValue

    model_config = ConfigDict(from_attributes=True)


class ProductivityMetric(BaseModel):
    key: str
    title: str
    value: KPIMetricProductivityValue | None = None
    change: str | None = None
    positive: bool | None = None
    type_value: str = "productivity"

    model_config = ConfigDict(from_attributes=True)


class TableResponseDTO(BaseModel, Generic[T]):
    total_count: int
    data: list[T]


class TableResponse(BaseModel):
    total_count: int
    data: list[dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)


class MeetingInfoDTO(BaseModel):
    name: str
    duration: str
    recurring_type: str


class RecurringMeetingTableRow(BaseModel):
    id: str
    meeting_profile: MeetingInfoDTO
    attendees: int = 0
    cancellation_rate: RoundedDecimal
    total_time: RoundedDecimal
    total_cost: RoundedDecimal | None = None
    organizer: UserProfileDTO | None = None

    model_config = ConfigDict(from_attributes=True)
