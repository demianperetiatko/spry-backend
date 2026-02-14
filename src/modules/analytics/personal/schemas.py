from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from src.modules.analytics.common.schemas import (  # re-export shared DTOs  # noqa: F401
    AnalyticsDateRangeParams,
    DistributionMetric,
    KPIMetric,
    KPIMetricProductivityValue,
    KPIResultDTO,
    MeetingChartItem,
    MeetingChartResponse,
    MeetingInfoDTO,
    MetricValue,
    ParticipantMetric,
    ProductivityMetric,
    RecurringMeetingTableRow,
    SortOrderType,
    TableResponse,
    TableResponseDTO,
    UserProfileDTO,
)
from src.shared.rounded_decimal import RoundedDecimal


class TableType(str, Enum):
    COLLABORATION = "collaboration"
    RECURRING_MEETINGS = "recurring_meetings"


class SortByType(str, Enum):
    COLLAB_TIME = "collab_time"
    EMAIL = "email"

    TOTAL_TIME = "total_time"
    TOTAL_COST = "total_cost"
    CANCELLATION_RATE = "cancellation_rate"
    MEETING_NAME = "meeting.name"


class PersonalAnalyticsParams(BaseModel):
    member_id: UUID
    start_date: str
    end_date: str

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


class ProductivityValueDTO(BaseModel):
    percent: RoundedDecimal
    hours: RoundedDecimal


class KPIMetricProductivityValue(BaseModel):
    percent: RoundedDecimal
    hours: RoundedDecimal


class KPIMetricProductivity(BaseModel):
    key: str
    title: str
    value: KPIMetricProductivityValue | None = None
    change: str | None = None
    positive: bool | None = None
    type_value: str = "productivity"

    model_config = ConfigDict(from_attributes=True)


class PersonalKPIsResponse(BaseModel):
    data: list[KPIMetric]

    model_config = ConfigDict(from_attributes=True)


class ParticipantsResponse(BaseModel):
    data: list[ParticipantMetric]

    model_config = ConfigDict(from_attributes=True)


class DistributionResponse(BaseModel):
    data: list[DistributionMetric]

    model_config = ConfigDict(from_attributes=True)


class ProductivityItemDTO(BaseModel):
    key: str
    title: str
    value: ProductivityValueDTO | None = None
    change: str | None = None
    positive: bool | None = None
    type_value: str = "productivity"


class ProductivityMetric(BaseModel):
    key: str
    title: str
    value: KPIMetricProductivityValue | None = None
    change: str | None = None
    positive: bool | None = None
    type_value: str = "productivity"

    model_config = ConfigDict(from_attributes=True)


class ProductivityResponse(BaseModel):
    productivity: list[ProductivityMetric]

    model_config = ConfigDict(from_attributes=True)


class CollaborationTableRow(BaseModel):
    email: str
    member_profile: UserProfileDTO | None = None
    collab_time: RoundedDecimal

    model_config = ConfigDict(from_attributes=True)
