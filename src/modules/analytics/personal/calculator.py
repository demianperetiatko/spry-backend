from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable, TYPE_CHECKING

from src.modules.analytics.common.calculator import (
    BUFFER_PER_SIDE_HOURS,
    MAX_TRANSITION_TIME_HOURS,
    SATURDAY_WEEKDAY,
    WORKDAY_DEFAULT_HOURS,
    calculate_change,
    duration_hours,
    sum_duration,
)
from src.modules.analytics.common.schemas import KPIResultDTO, MetricValue
from src.modules.analytics.personal.schemas import ProductivityItemDTO, ProductivityValueDTO
from src.modules.calendar.models import CalendarEvent

if TYPE_CHECKING:
    from collections.abc import Sequence


def count_weekdays(start: datetime, end: datetime) -> int:
    count = 0
    current = start.date()
    end_date = end.date()

    while current <= end_date:
        if current.weekday() < SATURDAY_WEEKDAY:
            count += 1
        current += timedelta(days=1)
    return count


def format_duration(duration_hours: Decimal) -> str:
    duration_minutes = int(Decimal(duration_hours) * 60)
    hours = duration_minutes // 60
    minutes = duration_minutes % 60
    if hours == 0 and minutes == 0:
        return ""
    elif hours == 0:
        return f"{minutes}m"
    elif minutes == 0:
        return f"{hours}h"
    else:
        return f"{hours}h {minutes}m"


MIN_EVENTS_FOR_TRANSITION = 2


class AnalyticsCalculator:
    def __init__(
        self,
        current_events: Sequence[CalendarEvent],
        prev_events: Sequence[CalendarEvent],
        work_days: int,
        hourly_cost: Decimal | None = None,
        workday_hours: Decimal = WORKDAY_DEFAULT_HOURS,
    ):
        self.events = current_events
        self.prev_events = prev_events
        self.work_days = work_days
        self.hourly_cost = hourly_cost
        self.workday_hours = workday_hours or WORKDAY_DEFAULT_HOURS

        self.total_duration = sum_duration(self.events)
        self.prev_total_duration = sum_duration(self.prev_events)

    @staticmethod
    def duration_hours(event: CalendarEvent) -> Decimal:
        return duration_hours(event)

    @classmethod
    def _sum_duration(cls, events: Sequence[CalendarEvent]) -> Decimal:
        return sum_duration(events)

    @staticmethod
    def _calculate_change(new_value: Decimal, old_value: Decimal) -> Decimal:
        return calculate_change(new_value, old_value)

    def _format_change(self, new_value: Decimal, old_value: Decimal) -> str:
        change = self._calculate_change(new_value, old_value)
        sign = "+" if change >= Decimal("0") else ""
        return f"{sign}{change}%"

    def _build_kpi_dto(
        self,
        current_value: Decimal | int,
        previous_value: Decimal | int,
        type_value: str,
        lower_is_better: bool = True,
        round_value: bool = True,
    ) -> KPIResultDTO:
        current_decimal = Decimal(str(current_value)) if isinstance(current_value, int) else current_value
        previous_decimal = Decimal(str(previous_value)) if isinstance(previous_value, int) else previous_value
        change = self._calculate_change(current_decimal, previous_decimal)
        formatted_value = (
            current_decimal.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            if round_value and isinstance(current_value, Decimal)
            else current_value
        )
        is_positive = change <= Decimal("0") if lower_is_better else change >= Decimal("0")
        return KPIResultDTO(
            value=formatted_value,
            change=self._format_change(current_decimal, previous_decimal),
            positive=is_positive,
            type_value=type_value,
        )

    def kpi_total_time(self) -> KPIResultDTO:
        return self._build_kpi_dto(
            current_value=self.total_duration,
            previous_value=self.prev_total_duration,
            type_value="time",
            lower_is_better=True,
        )

    def kpi_avg_daily_time(self) -> KPIResultDTO:
        current = (
            (self.total_duration / Decimal(str(self.work_days))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            if self.work_days
            else Decimal("0")
        )
        previous = (
            (self.prev_total_duration / Decimal(str(self.work_days))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            if self.work_days
            else Decimal("0")
        )
        return self._build_kpi_dto(
            current_value=current,
            previous_value=previous,
            type_value="time",
            lower_is_better=True,
            round_value=False,
        )

    def kpi_meetings_count(self) -> KPIResultDTO:
        return self._build_kpi_dto(
            current_value=len(self.events),
            previous_value=len(self.prev_events),
            type_value="count",
            lower_is_better=True,
            round_value=False,
        )

    def kpi_cancelled(
        self, all_current: Sequence[CalendarEvent], all_previous: Sequence[CalendarEvent], email: str
    ) -> KPIResultDTO:
        def count_cancelled(events: Sequence[CalendarEvent]) -> int:
            return sum(
                1
                for event in events
                if event.status.value == "cancelled"
                or any(att.email == email and att.response_status.value == "declined" for att in event.attendees)
            )

        current_count = count_cancelled(all_current)
        previous_count = count_cancelled(all_previous)
        return self._build_kpi_dto(
            current_value=current_count,
            previous_value=previous_count,
            type_value="count",
            lower_is_better=True,
            round_value=False,
        )

    def kpi_total_cost(self) -> KPIResultDTO:
        if self.hourly_cost is None:
            return KPIResultDTO(value=None, change=None, positive=None, type_value="currency")
        current_cost = self.total_duration * self.hourly_cost
        previous_cost = self.prev_total_duration * self.hourly_cost
        return self._build_kpi_dto(
            current_value=current_cost,
            previous_value=previous_cost,
            type_value="currency",
            lower_is_better=True,
        )

    def kpi_avg_daily_cost(self) -> KPIResultDTO:
        if self.hourly_cost is None or self.work_days == 0:
            return KPIResultDTO(value=None, change=None, positive=None, type_value="currency")
        current_cost = (self.total_duration * self.hourly_cost) / Decimal(str(self.work_days))
        previous_cost = (self.prev_total_duration * self.hourly_cost) / Decimal(str(self.work_days))
        return self._build_kpi_dto(
            current_value=current_cost,
            previous_value=previous_cost,
            type_value="currency",
            lower_is_better=True,
        )

    @staticmethod
    def _calc_buffer_time(events: Sequence[CalendarEvent]) -> Decimal:
        if not events:
            return Decimal("0")

        times = sorted(
            [(event.start_datetime, event.end_datetime) for event in events if event.start_datetime and event.end_datetime],
            key=lambda x: x[0],
        )
        if not times:
            return Decimal("0")

        blocks = []
        extra_gap = Decimal("0")
        current_start, current_end = times[0]

        for start_time, end_time in times[1:]:
            gap = Decimal(str((start_time - current_end).total_seconds())) / Decimal("3600")
            if gap < Decimal("2") * BUFFER_PER_SIDE_HOURS:
                if gap > Decimal("0"):
                    extra_gap += gap
                current_end = max(current_end, end_time)
            else:
                blocks.append((current_start, current_end))
                current_start, current_end = start_time, end_time
        blocks.append((current_start, current_end))

        return (BUFFER_PER_SIDE_HOURS * Decimal("2") * Decimal(str(len(blocks)))) + extra_gap

    @staticmethod
    def _calc_transition_time(events: Sequence[CalendarEvent]) -> Decimal:
        if len(events) < MIN_EVENTS_FOR_TRANSITION:
            return Decimal("0")

        times = sorted(
            [(event.start_datetime, event.end_datetime) for event in events if event.start_datetime and event.end_datetime],
            key=lambda x: x[0],
        )

        total_gap = Decimal("0")
        for i in range(1, len(times)):
            gap = Decimal(str((times[i][0] - times[i - 1][1]).total_seconds())) / Decimal("3600")
            if (BUFFER_PER_SIDE_HOURS * Decimal("2")) <= gap < MAX_TRANSITION_TIME_HOURS:
                total_gap += gap
        return total_gap

    def _get_productivity_kpi(
        self, value_func: Callable[[Sequence[CalendarEvent]], Decimal], is_positive_growth: bool
    ) -> dict[str, ProductivityValueDTO | str | bool]:
        current_value = value_func(self.events)
        previous_value = value_func(self.prev_events)
        total_capacity = Decimal(str(self.work_days)) * self.workday_hours
        current_percent = (
            ((current_value / total_capacity) * Decimal("100")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            if total_capacity > Decimal("0")
            else Decimal("0")
        )
        previous_percent = (
            ((previous_value / total_capacity) * Decimal("100")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            if total_capacity > Decimal("0")
            else Decimal("0")
        )
        change = self._calculate_change(current_percent, previous_percent)
        is_positive = change > Decimal("0") if is_positive_growth else change <= Decimal("0")
        return {
            "value": ProductivityValueDTO(
                percent=current_percent, hours=current_value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            ),
            "change": self._format_change(current_percent, previous_percent),
            "positive": is_positive,
            "type_value": "productivity",
        }

    def get_productivity_metrics(self) -> list[ProductivityItemDTO]:
        def calc_deep_work(events: Sequence[CalendarEvent]) -> Decimal:
            duration = self._sum_duration(events)
            buffer = self._calc_buffer_time(events)
            transition = self._calc_transition_time(events)
            result = (Decimal(str(self.work_days)) * self.workday_hours) - duration - buffer - transition
            return max(Decimal("0"), result)

        definitions = [
            ("meetings_time", "Time on meetings", self._sum_duration, False),
            ("deep_work", "Deep work", calc_deep_work, True),
            ("transition_time", "Transition time", self._calc_transition_time, False),
            ("buffers", "Buffers", self._calc_buffer_time, False),
        ]

        return [
            ProductivityItemDTO(
                key=key,
                title=title,
                value=kpi["value"],
                change=kpi["change"],
                positive=kpi["positive"],
                type_value=kpi["type_value"],
            )
            for key, title, value_func, is_positive in definitions
            for kpi in [self._get_productivity_kpi(value_func, is_positive)]
        ]

    @staticmethod
    def calculate_distribution(events: Sequence[CalendarEvent], filter_func) -> MetricValue:
        filtered = [event for event in events if filter_func(event)]
        total = len(events)
        hours = sum((AnalyticsCalculator.duration_hours(event) for event in filtered), start=Decimal("0"))
        percent = (
            ((Decimal(str(len(filtered))) / Decimal(str(total))) * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if total > 0
            else Decimal("0")
        )
        return MetricValue(percent=percent, hours=hours.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
