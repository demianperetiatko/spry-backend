from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.analytics.common.calculator import (
    ONE_ON_ONE_ATTENDEES,
    SMALL_GROUP_MAX,
    SMALL_GROUP_MIN,
    WORKDAY_DEFAULT_HOURS,
    calculate_change,
    count_weekdays,
    duration_hours,
)
from src.modules.analytics.common.schemas import KPIMetricProductivityValue, MetricValue, UserProfileDTO
from src.modules.analytics.organization.dependency import OrganizationAnalyticsContext
from src.modules.analytics.organization.repository import OrganizationAnalyticsRepository
from src.modules.analytics.organization.schemas import (
    AnalyticsType,
    AttendeeTableRow,
    DistributionResponse,
    KPIMetric,
    KPIsResponse,
    ListType,
    MeetingChartItem,
    MeetingChartResponse,
    MemberProfileDTO,
    OrganizerTableRow,
    ParticipantMetric,
    ProductivityMetric,
    ProductivityResponse,
    SortByType,
    SortOrderType,
    TableResponse,
    TeamCollaborationRow,
)
from src.modules.analytics.organization.services.data_loader import OrganizationAnalyticsDataLoader
from src.modules.analytics.personal.calculator import AnalyticsCalculator
from src.modules.organization.repository import OrganizationCurrencyRepositorySQLAlchemy
from src.modules.organization_member.repository import OrganizationMemberRepository
from src.modules.organization_team.repository import OrganizationTeamRepositorySQLAlchemy
from src.modules.permissions.enums import OrganizationPermission
from src.modules.permissions.service import Permissions
from src.shared.rounded_decimal import RoundedDecimal


class TeamAnalyticsCalculator:
    def __init__(
        self,
        current_events,
        prev_events,
        work_days: int,
        team_members_count: int,
        hourly_cost_map: dict[str, Decimal] | None = None,
        workday_hours: Decimal = Decimal("8"),
    ):
        self.events = current_events
        self.prev_events = prev_events
        self.work_days = work_days
        self.team_members_count = max(team_members_count, 1)
        self.hourly_cost_map = hourly_cost_map or {}
        self.workday_hours = workday_hours or WORKDAY_DEFAULT_HOURS

        self.total_duration = self._sum_duration(self.events)
        self.prev_total_duration = self._sum_duration(self.prev_events)

    @staticmethod
    def duration_hours(event) -> Decimal:
        return duration_hours(event)

    @classmethod
    def _sum_duration(cls, events) -> Decimal:
        return sum((cls.duration_hours(e) for e in events), start=Decimal("0"))

    @staticmethod
    def _calculate_change(new_value: Decimal, old_value: Decimal) -> Decimal:
        if old_value == Decimal("0"):
            if new_value > Decimal("0"):
                return Decimal("100")
            if new_value == Decimal("0"):
                return Decimal("0")
            return Decimal("-100")
        result = ((new_value - old_value) / old_value) * Decimal("100")
        return result.quantize(Decimal("0.1"))

    def _format_change(self, new_value: Decimal, old_value: Decimal) -> str:
        change = self._calculate_change(new_value, old_value)
        sign = "+" if change >= Decimal("0") else ""
        return f"{sign}{change}%"

    def _build_kpi(
        self,
        key: str,
        title: str,
        current_value: Decimal | int,
        previous_value: Decimal | int,
        type_value: str,
        lower_is_better: bool = True,
        round_value: bool = True,
    ) -> KPIMetric:
        current_decimal = Decimal(str(current_value)) if isinstance(current_value, int) else current_value
        previous_decimal = Decimal(str(previous_value)) if isinstance(previous_value, int) else previous_value
        change = calculate_change(current_decimal, previous_decimal)
        formatted_value = (
            current_decimal.quantize(Decimal("0.1")) if round_value and isinstance(current_value, Decimal) else current_value
        )
        is_positive = change <= Decimal("0") if lower_is_better else change >= Decimal("0")
        return KPIMetric(
            key=key,
            title=title,
            value=RoundedDecimal(formatted_value) if isinstance(formatted_value, Decimal) else formatted_value,
            change=self._format_change(current_decimal, previous_decimal),
            positive=is_positive,
            type_value=type_value,
        )

    def kpi_total_time(self) -> KPIMetric:
        return self._build_kpi(
            key="time_on_meetings",
            title="Time on meetings",
            current_value=self.total_duration,
            previous_value=self.prev_total_duration,
            type_value="time",
        )

    def kpi_avg_daily_time(self) -> KPIMetric:
        denominator = Decimal(str(self.work_days * self.team_members_count)) if self.work_days else Decimal("1")
        current = (self.total_duration / denominator) if denominator > 0 else Decimal("0")
        previous = (self.prev_total_duration / denominator) if denominator > 0 else Decimal("0")
        return self._build_kpi(
            key="avg_hours_per_person",
            title="Avg. hours per member",
            current_value=current,
            previous_value=previous,
            type_value="time",
        )

    def kpi_meetings_ratio(self) -> KPIMetric:
        total_work_hours = Decimal(str(self.work_days * self.team_members_count)) * self.workday_hours
        current = (self.total_duration * Decimal("100") / total_work_hours) if total_work_hours > 0 else Decimal("0")
        previous = (self.prev_total_duration * Decimal("100") / total_work_hours) if total_work_hours > 0 else Decimal("0")
        return self._build_kpi(
            key="meetings_time_ratio",
            title="Meetings time ratio",
            current_value=current,
            previous_value=previous,
            type_value="percent",
        )

    def _calc_cost(self, events) -> Decimal:
        if not self.hourly_cost_map:
            return Decimal("0")
        total = Decimal("0")
        for event in events:
            attendees = {att.email for att in event.attendees if att.email}
            duration = self.duration_hours(event)
            attendee_cost = sum(
                (self.hourly_cost_map.get(email, Decimal("0")) or Decimal("0") for email in attendees), start=Decimal("0")
            )
            total += duration * attendee_cost
        return total

    def kpi_total_cost(self) -> KPIMetric:
        current_cost = self._calc_cost(self.events)
        previous_cost = self._calc_cost(self.prev_events)
        return self._build_kpi(
            key="total_meetings_cost",
            title="Total meetings cost",
            current_value=current_cost,
            previous_value=previous_cost,
            type_value="currency",
        )

    def kpi_avg_daily_cost(self) -> KPIMetric:
        denominator = Decimal(str(self.work_days * self.team_members_count)) if self.work_days else Decimal("0")
        current = (self._calc_cost(self.events) / denominator) if denominator > 0 else Decimal("0")
        previous = (self._calc_cost(self.prev_events) / denominator) if denominator > 0 else Decimal("0")
        return self._build_kpi(
            key="avg_daily_meetings_cost",
            title="Avg. cost per member",
            current_value=current,
            previous_value=previous,
            type_value="currency",
        )

    def kpi_avg_member_cost(self) -> KPIMetric:
        denominator = Decimal(str(self.team_members_count)) if self.team_members_count else Decimal("0")
        current = (self._calc_cost(self.events) / denominator) if denominator > 0 else Decimal("0")
        previous = (self._calc_cost(self.prev_events) / denominator) if denominator > 0 else Decimal("0")
        return self._build_kpi(
            key="avg_daily_meetings_cost",
            title="Avg. cost per member",
            current_value=current,
            previous_value=previous,
            type_value="currency",
        )

    def kpi_meetings_count(self) -> KPIMetric:
        return self._build_kpi(
            key="meetings_count",
            title="Meetings count",
            current_value=len(self.events),
            previous_value=len(self.prev_events),
            type_value="count",
        )

    def kpi_without_description(self) -> KPIMetric:
        def count_without_desc(items) -> int:
            return sum(1 for e in items if not (e.description or "").strip())

        current = count_without_desc(self.events)
        previous = count_without_desc(self.prev_events)
        return self._build_kpi(
            key="meetings_wo_agenda",
            title="Meetings w/o agenda",
            current_value=current,
            previous_value=previous,
            type_value="count",
        )

    def _get_productivity_kpi(self, key: str, title: str, value_func, is_positive_growth: bool) -> ProductivityMetric:
        current_value = value_func(self.events)
        previous_value = value_func(self.prev_events)
        total_capacity = Decimal(str(self.work_days * self.team_members_count)) * self.workday_hours
        current_percent = (
            (current_value / total_capacity * Decimal("100")).quantize(Decimal("0.1")) if total_capacity > 0 else Decimal("0")
        )
        previous_percent = (
            (previous_value / total_capacity * Decimal("100")).quantize(Decimal("0.1")) if total_capacity > 0 else Decimal("0")
        )
        change = calculate_change(current_percent, previous_percent)
        is_positive = change > Decimal("0") if is_positive_growth else change <= Decimal("0")

        return ProductivityMetric(
            key=key,
            title=title,
            value=KPIMetricProductivityValue(percent=RoundedDecimal(current_percent), hours=RoundedDecimal(current_value)),
            change=self._format_change(current_percent, previous_percent),
            positive=is_positive,
            type_value="productivity",
        )

    def get_productivity_metrics(self) -> list[ProductivityMetric]:
        def calc_buffer(events):
            return AnalyticsCalculator._calc_buffer_time(events)

        def calc_transition(events):
            return AnalyticsCalculator._calc_transition_time(events)

        def calc_deep_work(events):
            capacity = Decimal(str(self.work_days * self.team_members_count)) * self.workday_hours
            duration = self._sum_duration(events)
            buffer = calc_buffer(events)
            transition = calc_transition(events)
            result = capacity - duration - buffer - transition
            return max(Decimal("0"), result)

        definitions = [
            ("meetings_time", "Time on meetings", self._sum_duration, False),
            ("deep_work", "Deep work", calc_deep_work, True),
            ("transition_time", "Transition time", calc_transition, False),
            ("buffers", "Buffers", calc_buffer, False),
        ]

        return [self._get_productivity_kpi(key, title, func, is_positive) for key, title, func, is_positive in definitions]


class OrganizationMetricsService:
    def __init__(
        self,
        data_loader: OrganizationAnalyticsDataLoader,
        analytics_repo: OrganizationAnalyticsRepository,
        member_repo: OrganizationMemberRepository,
        permissions_service: type[Permissions],
        session: AsyncSession,
    ) -> None:
        self.data_loader = data_loader
        self.analytics_repo = analytics_repo
        self.member_repo = member_repo
        self.permissions_service = permissions_service
        self.session = session

    async def _get_finance_access(self, ctx: OrganizationAnalyticsContext) -> bool:
        if not ctx.org.organizations_currency_id:
            return False
        currency_repo = OrganizationCurrencyRepositorySQLAlchemy(self.session)
        currency = await currency_repo.find_by_id(ctx.org.organizations_currency_id)
        return await self.permissions_service.member_has_permission(
            member=ctx.auth_member,
            permission=OrganizationPermission.FINANCE_VIEW,
            currency=currency,
            member_repo=self.member_repo,
        )

    async def _hourly_cost_map(self, ctx: OrganizationAnalyticsContext) -> dict[str, Decimal] | None:
        has_finance_access = await self._get_finance_access(ctx)
        if not has_finance_access:
            return None
        mapping: dict[str, Decimal] = {}
        for member in ctx.members:
            email = getattr(member.user, "email", None)
            if email and member.hourly_cost:
                mapping[email] = Decimal(str(member.hourly_cost))
        return mapping

    async def get_kpis(self, ctx: OrganizationAnalyticsContext) -> KPIsResponse:
        # Calculate person-hours for each member separately to preserve parallel meetings
        (start, end), (prev_start, prev_end) = ctx.params.parse_periods()
        count_work_day = count_weekdays(start, ctx.params.parse_end_datetime())
        team_size = len(ctx.members)
        member_ctx = await self.data_loader.get_member_contexts(ctx)

        def _duration(events):
            return sum((duration_hours(e) for e in events), start=Decimal("0"))

        def _count_without_desc(events):
            return sum(1 for e in events if not (e.description or "").strip())

        total_duration = Decimal("0")
        prev_total_duration = Decimal("0")
        meetings_count = 0
        prev_meetings_count = 0
        without_desc = 0
        prev_without_desc = 0

        for mc in member_ctx:
            current_events = await self.analytics_repo.get_meeting_events_for_period(mc.calendar_ids, start, end, mc.email)
            current_events = self.data_loader.get_unique_events(current_events)
            prev_events = await self.analytics_repo.get_meeting_events_for_period(mc.calendar_ids, prev_start, prev_end, mc.email)
            prev_events = self.data_loader.get_unique_events(prev_events)

            total_duration += _duration(current_events)
            prev_total_duration += _duration(prev_events)
            meetings_count += len(current_events)
            prev_meetings_count += len(prev_events)
            without_desc += _count_without_desc(current_events)
            prev_without_desc += _count_without_desc(prev_events)

        def _build_kpi(
            key: str,
            title: str,
            current: Decimal | int,
            previous: Decimal | int,
            type_value: str,
            lower_is_better: bool = True,
        ) -> KPIMetric:
            current_dec = Decimal(str(current)) if isinstance(current, int) else current
            previous_dec = Decimal(str(previous)) if isinstance(previous, int) else previous
            change = calculate_change(current_dec, previous_dec)
            is_positive = change <= Decimal("0") if lower_is_better else change >= Decimal("0")
            formatted = current_dec.quantize(Decimal("0.1")) if isinstance(current_dec, Decimal) else current
            return KPIMetric(
                key=key,
                title=title,
                value=RoundedDecimal(formatted) if isinstance(formatted, Decimal) else formatted,
                change=f"{'+' if change >= 0 else ''}{change}%",
                positive=is_positive,
                type_value=type_value,
            )

        denom_hours = (
            Decimal(str(count_work_day * max(team_size, 1))) * ctx.workday_hours
            if count_work_day and ctx.workday_hours
            else Decimal("0")
        )
        kpis: list[KPIMetric] = [
            _build_kpi("time_on_meetings", "Time on meetings", total_duration, prev_total_duration, "time", lower_is_better=True),
            _build_kpi(
                "meetings_time_ratio",
                "Meetings time ratio",
                (total_duration * Decimal("100") / denom_hours) if denom_hours > 0 else Decimal("0"),
                (prev_total_duration * Decimal("100") / denom_hours) if denom_hours > 0 else Decimal("0"),
                "percent",
                lower_is_better=True,
            ),
            _build_kpi(
                "avg_hours_per_member",
                "Avg. hours per member",
                (total_duration / Decimal(str(count_work_day * max(team_size, 1))))
                if count_work_day and team_size
                else Decimal("0"),
                (prev_total_duration / Decimal(str(count_work_day * max(team_size, 1))))
                if count_work_day and team_size
                else Decimal("0"),
                "time",
                lower_is_better=True,
            ),
            _build_kpi("meetings_count", "Meetings count", meetings_count, prev_meetings_count, "count", lower_is_better=True),
            _build_kpi(
                "meetings_wo_agenda",
                "Meetings w/o agenda",
                without_desc,
                prev_without_desc,
                "count",
                lower_is_better=True,
            ),
        ]

        # Cost: use unique events (correct logic via attendees)
        hourly_cost_map = await self._hourly_cost_map(ctx)
        if hourly_cost_map is not None:
            unique_events, unique_prev, _, _ = await self.data_loader.get_comparative_events(ctx, include_all=True)
            cost_calc = TeamAnalyticsCalculator(
                unique_events, unique_prev, count_work_day, team_size, hourly_cost_map or {}, ctx.workday_hours
            )
            kpis.extend([cost_calc.kpi_total_cost(), cost_calc.kpi_avg_member_cost()])

        return KPIsResponse(data=kpis)

    async def get_meeting_chart(self, ctx: OrganizationAnalyticsContext, analytics_type: AnalyticsType) -> MeetingChartResponse:
        events = await self.data_loader.get_events_for_chart(ctx)
        start_dt = ctx.params.parse_start_datetime()
        end_dt = ctx.params.parse_end_datetime()
        events_by_date = self.data_loader.group_events_by_date(events, start_dt, end_dt)
        team_size = max(len(ctx.members), 1)
        hourly_cost_map = await self._hourly_cost_map(ctx) or {}

        data = []
        for day, day_events in events_by_date.items():
            total_duration = sum((AnalyticsCalculator.duration_hours(e) for e in day_events), start=Decimal("0"))
            recurring_duration = sum(
                (AnalyticsCalculator.duration_hours(e) for e in day_events if e.recurring_event_id), start=Decimal("0")
            )
            one_time_duration = total_duration - recurring_duration

            if analytics_type == AnalyticsType.TIME:
                ratio = (
                    (total_duration * Decimal("100")) / (ctx.workday_hours * Decimal(str(team_size)))
                    if team_size > 0 and ctx.workday_hours
                    else Decimal("0")
                )
                data.append(
                    MeetingChartItem(
                        date=day.strftime("%Y-%m-%d"),
                        recurring=recurring_duration,
                        one_time=one_time_duration,
                        ratio=ratio,
                    )
                )
            else:

                def _cost(evts):
                    total = Decimal("0")
                    for e in evts:
                        attendees = {att.email for att in e.attendees if att.email}
                        duration = AnalyticsCalculator.duration_hours(e)
                        attendee_cost = sum((hourly_cost_map.get(email, Decimal("0")) for email in attendees), start=Decimal("0"))
                        total += duration * attendee_cost
                    return total

                data.append(
                    MeetingChartItem(
                        date=day.strftime("%Y-%m-%d"),
                        recurring=_cost([e for e in day_events if e.recurring_event_id]),
                        one_time=_cost([e for e in day_events if not e.recurring_event_id]),
                        ratio=None,
                    )
                )

        return MeetingChartResponse(data=data)

    async def get_meeting_participants(self, ctx: OrganizationAnalyticsContext) -> list[ParticipantMetric]:
        events = await self.data_loader.get_analyzable_events(ctx)

        definitions = [
            ("one_to_one", "One-on-one", lambda e: len(e.attendees) == ONE_ON_ONE_ATTENDEES),
            ("three_to_five", "3-5", lambda e: SMALL_GROUP_MIN <= len(e.attendees) <= SMALL_GROUP_MAX),
            ("more_than_five", "6+", lambda e: len(e.attendees) > SMALL_GROUP_MAX),
        ]

        data: list[ParticipantMetric] = []
        total = len(events)
        for key, title, func in definitions:
            filtered = [e for e in events if func(e)]
            hours = sum((duration_hours(e) for e in filtered), start=Decimal("0"))
            percent = (
                (Decimal(str(len(filtered))) / Decimal(str(total)) * Decimal("100")).quantize(Decimal("0.01"))
                if total
                else Decimal("0")
            )
            data.append(
                ParticipantMetric(
                    key=key,
                    title=title,
                    value=MetricValue(percent=RoundedDecimal(percent), hours=RoundedDecimal(hours.quantize(Decimal("0.1")))),
                )
            )
        return data

    async def get_meeting_distribution(self, ctx: OrganizationAnalyticsContext) -> DistributionResponse:
        events = await self.data_loader.get_analyzable_events(ctx)
        team_emails = {getattr(m.user, "email", "") for m in ctx.members if getattr(m.user, "email", None)}
        org_emails = await self.analytics_repo.get_organization_member_emails(ctx.org.id)
        org_emails.update(team_emails)

        definitions = [
            (
                "inside_team",
                "Inside the team",
                lambda e: (emails := self.data_loader.get_attendee_emails(e)) and emails.issubset(team_emails),
            ),
            (
                "cross_team",
                "With other teams",
                lambda e: (emails := self.data_loader.get_attendee_emails(e))
                and emails.issubset(org_emails)
                and not emails.issubset(team_emails),
            ),
            (
                "external",
                "Outside the org.",
                lambda e: (emails := self.data_loader.get_attendee_emails(e)) and not emails.issubset(org_emails),
            ),
        ]

        data = []
        total = len(events)
        for key, title, func in definitions:
            filtered = [event for event in events if func(event)]
            hours = sum((duration_hours(e) for e in filtered), start=Decimal("0"))
            percent = (
                (Decimal(str(len(filtered))) / Decimal(str(total)) * Decimal("100")).quantize(Decimal("0.01"))
                if total
                else Decimal("0")
            )
            data.append(
                ParticipantMetric(
                    key=key,
                    title=title,
                    value=MetricValue(percent=RoundedDecimal(percent), hours=RoundedDecimal(hours.quantize(Decimal("0.1")))),
                )
            )

        return DistributionResponse(data=data)

    async def get_productivity(
        self,
        ctx: OrganizationAnalyticsContext,
        list_type: ListType,
        sort_by: SortByType,
        sort_order: SortOrderType,
    ) -> ProductivityResponse:
        (start_dt, end_dt), (prev_start_dt, prev_end_dt) = ctx.params.parse_periods()
        count_work_day = count_weekdays(start_dt, end_dt)
        reverse = sort_order == SortOrderType.DESC

        member_ctx = await self.data_loader.get_member_contexts(ctx)
        all_events = []
        prev_all_events = []
        data: list[dict[str, Any]] = []
        hourly_cost_map = await self._hourly_cost_map(ctx) or {}
        member_map = {m.id: m for m in ctx.members}

        def _duration(events):
            return sum((duration_hours(e) for e in events), start=Decimal("0"))

        def _buffer(events):
            return AnalyticsCalculator._calc_buffer_time(events)

        def _transition(events):
            return AnalyticsCalculator._calc_transition_time(events)

        def _deep_work(events, team_members_count: int = 1):
            capacity = Decimal(str(count_work_day * team_members_count)) * ctx.workday_hours
            duration = _duration(events)
            buffer = _buffer(events)
            transition = _transition(events)
            return capacity - duration - buffer - transition

        for mc in member_ctx:
            try:
                events = await self.analytics_repo.get_meeting_events_for_period(mc.calendar_ids, start_dt, end_dt, mc.email)
                events = self.data_loader.get_unique_events(events)
                prev_events = await self.analytics_repo.get_meeting_events_for_period(
                    mc.calendar_ids, prev_start_dt, prev_end_dt, mc.email
                )
                prev_events = self.data_loader.get_unique_events(prev_events)

                all_events.extend(events)
                prev_all_events.extend(prev_events)

                source_member = member_map.get(mc.member_id)
                name = getattr(source_member.user, "name", None) if source_member and source_member.user else None
                photo_url = getattr(source_member.user, "photo_url", None) if source_member and source_member.user else None

                data.append(
                    {
                        "id": str(mc.member_id),
                        "name": name,
                        "email": mc.email,
                        "member_photo_url": photo_url,
                        "meetings_time": float(_duration(events)),
                        "prev_meetings_time": float(_duration(prev_events)),
                        "deep_work": float(_deep_work(events)),
                        "prev_deep_work": float(_deep_work(prev_events)),
                        "transition_time": float(_transition(events)),
                        "prev_transition_time": float(_transition(prev_events)),
                        "buffers": float(_buffer(events)),
                        "prev_buffers": float(_buffer(prev_events)),
                    }
                )
            except Exception:
                continue

        all_events = self.data_loader.get_unique_events(all_events)
        prev_all_events = self.data_loader.get_unique_events(prev_all_events)

        calc = TeamAnalyticsCalculator(
            all_events, prev_all_events, count_work_day, len(ctx.members), hourly_cost_map, ctx.workday_hours
        )
        productivity_metrics = calc.get_productivity_metrics()

        def calculate_metric_with_hours_and_percent(value: float, team_members_count: int = 1) -> dict[str, float]:
            if count_work_day == 0:
                return {"percent": 0, "hours": round(value, 1)}
            percent = round((value / (count_work_day * float(ctx.workday_hours) * team_members_count)) * 100, 1)
            return {"percent": percent, "hours": round(value, 1)}

        if list_type == ListType.TEAMS:
            team_repo = OrganizationTeamRepositorySQLAlchemy(self.session)
            teams = [ctx.team] if ctx.team else await team_repo.get_teams_by_organization_id(ctx.org.id)
            rows = []
            for team in teams:
                if not team:
                    continue
                member_ids = {tm.member.id for tm in team.team_members if tm.member}
                team_members_data = [m for m in data if m["id"] in {str(mid) for mid in member_ids}]
                team_members_count = max(len(member_ids), 1)
                rows.append(
                    {
                        "id": str(team.id),
                        "name": team.name,
                        "team_members_count": team_members_count,
                        "meetings_time": sum(m["meetings_time"] for m in team_members_data),
                        "deep_work": sum(m["deep_work"] for m in team_members_data),
                        "transition_time": sum(m["transition_time"] for m in team_members_data),
                        "buffers": sum(m["buffers"] for m in team_members_data),
                    }
                )

            sort_key = sort_by.value if sort_by else SortByType.MEETINGS_TIME.value
            rows = sorted(rows, key=lambda i: i.get(sort_key) or 0, reverse=reverse)
            res_data = []
            for row in rows:
                res_data.append(
                    {
                        "id": row.get("id"),
                        "name": row.get("name"),
                        "meetings_time": calculate_metric_with_hours_and_percent(
                            row.get("meetings_time", 0.0), row.get("team_members_count", 1)
                        ),
                        "deep_work": calculate_metric_with_hours_and_percent(
                            row.get("deep_work", 0.0), row.get("team_members_count", 1)
                        ),
                        "transition_time": calculate_metric_with_hours_and_percent(
                            row.get("transition_time", 0.0), row.get("team_members_count", 1)
                        ),
                        "buffers": calculate_metric_with_hours_and_percent(
                            row.get("buffers", 0.0), row.get("team_members_count", 1)
                        ),
                    }
                )
        else:
            sort_key = sort_by.value if sort_by else SortByType.MEETINGS_TIME.value
            rows = sorted(data, key=lambda i: i.get(sort_key) or 0, reverse=reverse)
            res_data = []
            for row in rows:
                res_data.append(
                    {
                        "id": row.get("id"),
                        "member_profile": {
                            "id": row.get("id", " "),
                            "name": row.get("name", " "),
                            "email": row.get("email"),
                            "photo_url": row.get("member_photo_url"),
                        },
                        "meetings_time": calculate_metric_with_hours_and_percent(row.get("meetings_time", 0.0)),
                        "deep_work": calculate_metric_with_hours_and_percent(row.get("deep_work", 0.0)),
                        "transition_time": calculate_metric_with_hours_and_percent(row.get("transition_time", 0.0)),
                        "buffers": calculate_metric_with_hours_and_percent(row.get("buffers", 0.0)),
                    }
                )

        return ProductivityResponse(productivity=productivity_metrics, data=res_data)

    async def _member_table_sort(self, data: list[Any], sort_by: SortByType | None, reverse: bool) -> list[Any]:
        if not sort_by:
            return data
        key_name = sort_by.value if hasattr(sort_by, "value") else str(sort_by)

        def _get(item, path: str):
            try:
                if "." in path:
                    obj = item
                    for part in path.split("."):
                        obj = getattr(obj, part, None)
                    return obj
                return getattr(item, path, None)
            except Exception:
                return None

        return sorted(data, key=lambda x: _get(x, key_name) or 0, reverse=reverse)

    async def get_attendees_table(
        self,
        ctx: OrganizationAnalyticsContext,
        start_dt,
        end_dt,
        sort_by: SortByType | None,
        reverse: bool,
    ) -> TableResponse:
        member_ctx = await self.data_loader.get_member_contexts(ctx)
        count_work_day = count_weekdays(start_dt, end_dt)

        hourly_cost_map = await self._hourly_cost_map(ctx)
        finance_access = hourly_cost_map is not None
        hourly_cost_map = hourly_cost_map or {}
        rows: list[AttendeeTableRow] = []
        member_map = {m.id: m for m in ctx.members}
        for mc in member_ctx:
            events = await self.analytics_repo.get_meeting_events_for_period(mc.calendar_ids, start_dt, end_dt, mc.email)
            events = self.data_loader.get_unique_events(events)
            total_duration = sum((AnalyticsCalculator.duration_hours(e) for e in events), start=Decimal("0"))

            ratio = (
                (total_duration * Decimal("100")) / (ctx.workday_hours * Decimal(str(count_work_day)))
                if count_work_day > 0 and ctx.workday_hours
                else Decimal("0")
            )
            # cost for this member only
            cost = total_duration * hourly_cost_map.get(mc.email, Decimal("0")) if finance_access else None

            source_member = member_map.get(mc.member_id)
            member_profile = None
            if source_member and source_member.user:
                member_profile = MemberProfileDTO(
                    id=mc.member_id,
                    name=source_member.user.name,
                    email=mc.email,
                    photo_url=source_member.user.photo_url,
                )
            rows.append(
                AttendeeTableRow(
                    id=str(mc.member_id),
                    member_profile=member_profile,
                    time=RoundedDecimal(total_duration),
                    ratio=RoundedDecimal(ratio.quantize(Decimal("0.1"))),
                    cost=RoundedDecimal(cost) if finance_access else None,
                )
            )

        rows = await self._member_table_sort(rows, sort_by, reverse)
        return TableResponse(total_count=len(rows), data=[row.model_dump() for row in rows])

    async def get_organizers_table(
        self,
        ctx: OrganizationAnalyticsContext,
        start_dt,
        end_dt,
        sort_by: SortByType | None,
        reverse: bool,
    ) -> TableResponse:
        member_ctx = await self.data_loader.get_member_contexts(ctx)
        rows: list[OrganizerTableRow] = []
        member_map = {m.id: m for m in ctx.members}

        for mc in member_ctx:
            events = await self.analytics_repo.get_meeting_events_for_period(mc.calendar_ids, start_dt, end_dt, mc.email)
            events = self.data_loader.get_unique_events(events)
            organized = [e for e in events if (e.organizer_email == mc.email or e.is_self_created)]
            if not organized:
                continue

            meetings_time = sum((AnalyticsCalculator.duration_hours(e) for e in organized), start=Decimal("0"))
            recurring_time = sum(
                (AnalyticsCalculator.duration_hours(e) for e in organized if e.recurring_event_id), start=Decimal("0")
            )
            recurring_percent = (
                (recurring_time / meetings_time * Decimal("100")).quantize(Decimal("0.01")) if meetings_time > 0 else Decimal("0")
            )
            avg_attendees = (Decimal(str(sum(len(e.attendees) for e in organized))) / Decimal(str(len(organized)))).quantize(
                Decimal("0.01")
            )
            meetings_wo_agenda_time = sum(
                (AnalyticsCalculator.duration_hours(e) for e in organized if not (e.description or "").strip()),
                start=Decimal("0"),
            )
            meetings_wo_agenda_percent = (
                (meetings_wo_agenda_time / meetings_time * Decimal("100")).quantize(Decimal("0.01"))
                if meetings_time > 0
                else Decimal("0")
            )

            source_member = member_map.get(mc.member_id)
            member_profile = None
            if source_member and source_member.user:
                member_profile = MemberProfileDTO(
                    id=mc.member_id,
                    name=source_member.user.name,
                    email=mc.email,
                    photo_url=source_member.user.photo_url,
                )
            rows.append(
                OrganizerTableRow(
                    id=str(mc.member_id),
                    member_profile=member_profile,
                    count=len(organized),
                    meetings_time=RoundedDecimal(meetings_time),
                    recurring_meetings_percent=RoundedDecimal(recurring_percent),
                    avg_attendees=RoundedDecimal(avg_attendees),
                    meetings_wo_agenda_percent=RoundedDecimal(meetings_wo_agenda_percent),
                )
            )

        rows = await self._member_table_sort(rows, sort_by, reverse)
        return TableResponse(total_count=len(rows), data=[row.model_dump() for row in rows])

    async def get_teams_collab_table(
        self,
        ctx: OrganizationAnalyticsContext,
        start_dt,
        end_dt,
        sort_by: SortByType | None,
        reverse: bool,
    ) -> TableResponse:
        events = await self.data_loader.get_analyzable_events(ctx)
        events = self.data_loader.get_unique_events(events)

        team_repository = OrganizationTeamRepositorySQLAlchemy(self.session)
        teams = await team_repository.get_teams_by_organization_id(ctx.org.id)
        team_email_map: dict[str, set[str]] = {}
        manager_map: dict[str, UserProfileDTO] = {}
        for team in teams:
            emails = set()
            manager_profile = None
            for tm in team.team_members:
                if tm.member and tm.member.user and tm.member.user.email:
                    emails.add(tm.member.user.email)
                if tm.type.value == "manager" and tm.member and tm.member.user:
                    manager_profile = UserProfileDTO(
                        id=tm.member.user_id,
                        name=tm.member.user.name,
                        email=tm.member.user.email,
                        photo_url=tm.member.user.photo_url,
                    )
            team_email_map[str(team.id)] = emails
            if manager_profile:
                manager_map[str(team.id)] = manager_profile

        target_team_emails = {getattr(m.user, "email", None) for m in ctx.members if getattr(m.user, "email", None)}

        collab: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        collab_cost: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        hourly_cost_map = await self._hourly_cost_map(ctx)
        finance_access = hourly_cost_map is not None
        hourly_cost_map = hourly_cost_map or {}
        for event in events:
            attendees = {att.email for att in event.attendees if att.email}
            if not (attendees & target_team_emails):
                continue
            duration = AnalyticsCalculator.duration_hours(event)
            for team_id, emails in team_email_map.items():
                if ctx.team and str(ctx.team.id) == team_id:
                    continue
                if attendees & emails:
                    collab[team_id] += duration
                    if finance_access:
                        attendee_cost = sum(
                            (hourly_cost_map.get(email, Decimal("0")) for email in attendees if email in emails),
                            start=Decimal("0"),
                        )
                        collab_cost[team_id] += duration * attendee_cost

        rows: list[TeamCollaborationRow] = []
        for team_id, time_value in collab.items():
            rows.append(
                TeamCollaborationRow(
                    id=team_id,
                    team_name=next((t.name for t in teams if str(t.id) == team_id), ""),
                    team_manager_profile=manager_map.get(team_id),
                    collab_time=RoundedDecimal(time_value),
                    collab_cost=RoundedDecimal(collab_cost.get(team_id, Decimal("0"))) if finance_access else None,
                )
            )

        rows = await self._member_table_sort(rows, sort_by, reverse)
        return TableResponse(total_count=len(rows), data=[row.model_dump() for row in rows])
