from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.modules.analytics.common.schemas import KPIMetric
from src.shared.rounded_decimal import RoundedDecimal


class KPIResponse(BaseModel):
    data: list[KPIMetric]

    model_config = ConfigDict(from_attributes=True)


class TimeSlot(BaseModel):
    start_time: datetime = Field(description="Start datetime of the deep work slot")
    end_time: datetime = Field(description="End datetime of the deep work slot")

    @model_validator(mode="after")
    def validate_range(self) -> "TimeSlot":
        if self.start_time >= self.end_time:
            raise ValueError("`start_time` must be earlier than `end_time`.")
        return self


class TimeSlotDTO(BaseModel):
    startTime: str
    endTime: str
    date: str
    duration: RoundedDecimal


class DeepWorkSlotsResponse(BaseModel):
    slots: list[TimeSlotDTO]


class AgendaDescriptionRequest(BaseModel):
    description: str = Field(min_length=1, description="Agenda description text")


class UserProfile(BaseModel):
    id: UUID | None = None
    name: str | None = None
    email: str
    photo_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AgendaMeeting(BaseModel):
    id: str
    name: str
    start_time: str
    end_time: str
    date: str
    members: list[UserProfile]
    organizer: UserProfile | None = None
    is_organizer: bool
    invitation_sent: bool


class AgendaResponse(BaseModel):
    meetings: list[AgendaMeeting]
    count_all_events: int
