from __future__ import annotations

from enum import Enum
from pydantic import BaseModel


class InsightStatus(str, Enum):
    positive = "positive"
    attention = "attention"
    negative = "negative"


class InsightTab(str, Enum):
    personal = "personal"
    teams = "teams"
    organization = "organization"


class InsightIconType(str, Enum):
    trending_up = "trending-up"
    trending_down = "trending-down"
    cost = "cost"
    focus = "focus"
    calendar = "calendar"
    meeting_size = "meeting-size"
    balance = "balance"
    collab = "collab"
    person = "person"
    check = "check"


class InsightPersonDTO(BaseModel):
    name: str
    initials: str
    color: str
    member_id: int | None = None
    photo_url: str | None = None


class InsightRecommendationDTO(BaseModel):
    action: str
    outcome: str


class InsightDTO(BaseModel):
    id: str
    tab: InsightTab
    status: InsightStatus
    icon_type: InsightIconType
    title: str
    data_signal: str
    recommendation: InsightRecommendationDTO
    persons: list[InsightPersonDTO] = []


class InsightsResponse(BaseModel):
    data: list[InsightDTO]


# ── Settings enums ────────────────────────────────────────────────────────────

class GenerationFrequency(str, Enum):
    weekly_monday_8 = "weekly_monday_8"
    mon_wed_8 = "mon_wed_8"
    daily_8 = "daily_8"


class DataHorizon(str, Enum):
    last_and_next_4_weeks = "last_and_next_4_weeks"
    last_and_next_2_weeks = "last_and_next_2_weeks"
    current_month = "current_month"
    current_week = "current_week"
    last_3m = "last_3m"
    last_6m = "last_6m"
    next_3m = "next_3m"
    next_6m = "next_6m"


FREQUENCY_LABELS: dict[GenerationFrequency, str] = {
    GenerationFrequency.weekly_monday_8: "Every Mon at 8:00",
    GenerationFrequency.mon_wed_8: "Every Mon & Wed at 8:00",
    GenerationFrequency.daily_8: "Every day at 8:00",
}

HORIZON_LABELS: dict[DataHorizon, str] = {
    DataHorizon.last_and_next_4_weeks: "Last and next 4 weeks",
    DataHorizon.last_and_next_2_weeks: "Last and next 2 weeks",
    DataHorizon.current_month: "Current month",
    DataHorizon.current_week: "Current week",
    DataHorizon.last_3m: "Last 3m",
    DataHorizon.last_6m: "Last 6m",
    DataHorizon.next_3m: "Next 3m",
    DataHorizon.next_6m: "Next 6m",
}

# Default settings per tab
_DEFAULT = (GenerationFrequency.weekly_monday_8, DataHorizon.last_and_next_4_weeks)
DEFAULT_SETTINGS: dict[str, tuple[GenerationFrequency, DataHorizon]] = {
    "personal": _DEFAULT,
    "teams": _DEFAULT,
    "organization": _DEFAULT,
}


# ── Settings DTOs ─────────────────────────────────────────────────────────────

class InsightTabSettings(BaseModel):
    tab: str
    generation_frequency: GenerationFrequency
    data_horizon: DataHorizon
    frequency_label: str
    horizon_label: str


class InsightSettingsResponse(BaseModel):
    data: list[InsightTabSettings]


class UpdateInsightTabSettings(BaseModel):
    generation_frequency: GenerationFrequency | None = None
    data_horizon: DataHorizon | None = None
