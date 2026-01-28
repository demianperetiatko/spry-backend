from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Callable, Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.analytics.personal.calculator import AnalyticsCalculator, count_weekdays
from src.modules.analytics.personal.schemas import (
    CollaborationTableRow,
    DistributionMetric,
    KPIMetric,
    KPIMetricProductivityValue,
    MeetingChartItem,
    MeetingChartResponse,
    ParticipantMetric,
    ProductivityMetric,
    TableResponse,
    UserProfileDTO,
)
from src.modules.analytics.personal.dependency import AnalyticsContext
from src.modules.calendar.models import CalendarEvent
from src.modules.analytics.personal.services.data_loader import AnalyticsDataLoaderService
from src.modules.organization.repository import OrganizationCurrencyRepositorySQLAlchemy
from src.modules.organization_member.repository import OrganizationMemberRepository
from src.modules.permissions.enums import OrganizationPermission
from src.modules.permissions.service import Permissions

if TYPE_CHECKING:
    pass


class PersonalMetricsService:
    def __init__(
        self,
        data_loader: AnalyticsDataLoaderService,
        member_repo: OrganizationMemberRepository,
        permissions_service: type[Permissions],
        session: AsyncSession,
    ) -> None:
        self.data_loader = data_loader
        self.member_repo = member_repo
        self.permissions_service = permissions_service
        self.session = session

    async def _get_finance_access(self, ctx: AnalyticsContext) -> bool:
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

    async def get_personal_kpis(self, ctx: AnalyticsContext) -> list[KPIMetric]:
        unique_events, unique_prev, all_events, all_prev_events = await self.data_loader.get_comparative_events(
            ctx, include_all=True
        )

        (start, end), _ = ctx.params.parse_periods()

        hourly_cost = None
        has_finance_access = await self._get_finance_access(ctx)
        if has_finance_access and ctx.member.hourly_cost:
            hourly_cost = ctx.member.hourly_cost

        work_days = count_weekdays(start, end)
        calc = AnalyticsCalculator(unique_events, unique_prev, work_days, hourly_cost, workday_hours=ctx.workday_hours)

        kpis = [
            self._build_kpi("time_on_meetings", "Time on meetings", calc.kpi_total_time()),
            self._build_kpi("avg_daily_meetings_time", "Avg. daily meetings time", calc.kpi_avg_daily_time()),
        ]

        if has_finance_access:
            kpis.extend(
                [
                    self._build_kpi("total_meetings_cost", "Total meetings cost", calc.kpi_total_cost()),
                    self._build_kpi("avg_daily_meetings_cost", "Avg. daily meetings cost", calc.kpi_avg_daily_cost()),
                ]
            )

        all_unique_events = self.data_loader.get_unique_events(all_events) if all_events else []
        all_unique_prev_events = self.data_loader.get_unique_events(all_prev_events) if all_prev_events else []

        kpis.extend(
            [
                self._build_kpi("meetings_count", "Meetings count", calc.kpi_meetings_count()),
                self._build_kpi(
                    "cancelled_meetings",
                    "Cancelled meetings",
                    calc.kpi_cancelled(all_unique_events, all_unique_prev_events, ctx.email),
                ),
            ]
        )

        return kpis

    @staticmethod
    def _build_kpi(key: str, title: str, kpi_result: Any) -> KPIMetric:
        return KPIMetric(
            key=key,
            title=title,
            value=kpi_result.value,
            change=kpi_result.change,
            positive=kpi_result.positive,
            type_value=kpi_result.type_value,
        )

    async def get_meeting_chart(self, ctx: AnalyticsContext) -> MeetingChartResponse:
        events = await self.data_loader.get_events_for_chart(ctx)
        start_dt = ctx.params.parse_start_datetime()
        end_dt = ctx.params.parse_end_datetime()
        events_by_date = self.data_loader.group_events_by_date(events, start_dt, end_dt)

        data = []
        for day, day_events in events_by_date.items():
            total_duration = sum((AnalyticsCalculator.duration_hours(e) for e in day_events), start=Decimal("0"))
            recurring_duration = sum(
                (AnalyticsCalculator.duration_hours(e) for e in day_events if e.recurring_event_id), start=Decimal("0")
            )
            one_time_duration = total_duration - recurring_duration

            data.append(
                MeetingChartItem(
                    date=day.strftime("%Y-%m-%d"),
                    recurring=recurring_duration,
                    one_time=one_time_duration,
                    ratio=(total_duration * Decimal("100")) / ctx.workday_hours if ctx.workday_hours else Decimal("0"),
                )
            )

        return MeetingChartResponse(data=data)

    async def get_meeting_participants(self, ctx: AnalyticsContext) -> list[ParticipantMetric]:
        unique_events = await self.data_loader.get_analyzable_events(ctx)

        definitions = [
            ("one_to_one", "One-on-one", lambda e: len(e.attendees) == 2),
            ("three_to_five", "3-5", lambda e: 3 <= len(e.attendees) <= 5),
            ("more_than_five", "6+", lambda e: len(e.attendees) > 5),
        ]

        return [
            ParticipantMetric(key=key, title=title, value=AnalyticsCalculator.calculate_distribution(unique_events, func))
            for key, title, func in definitions
        ]

    async def get_meeting_distribution(self, ctx: AnalyticsContext) -> list[DistributionMetric]:
        unique_events = await self.data_loader.get_analyzable_events(ctx)

        repo = self.data_loader.repo
        team_emails = await repo.get_team_member_emails(ctx.member.id)
        org_emails = await repo.get_organization_member_emails(ctx.org.id)

        org_emails.add(ctx.email)
        team_emails.add(ctx.email)

        definitions = self._build_distribution_filters(team_emails, org_emails)
        return [
            DistributionMetric(key=key, title=title, value=AnalyticsCalculator.calculate_distribution(unique_events, func))
            for key, title, func in definitions
        ]

    @staticmethod
    def _build_distribution_filters(
        team_emails: set[str], org_emails: set[str]
    ) -> list[tuple[str, str, Callable[[CalendarEvent], bool]]]:
        def _get_emails(e: CalendarEvent) -> set[str]:
            return AnalyticsDataLoaderService.get_attendee_emails(e)

        return [
            ("inside_team", "Inside the team", lambda e: bool((emails := _get_emails(e)) and emails.issubset(team_emails))),
            (
                "cross_team",
                "With other teams",
                lambda e: bool((emails := _get_emails(e)) and emails.issubset(org_emails) and not emails.issubset(team_emails)),
            ),
            ("external", "Outside the org.", lambda e: bool((emails := _get_emails(e)) and not emails.issubset(org_emails))),
        ]

    async def get_productivity(self, ctx: AnalyticsContext) -> list[ProductivityMetric]:
        unique_events, unique_prev, _, _ = await self.data_loader.get_comparative_events(ctx, include_all=False)

        (start, end), _ = ctx.params.parse_periods()
        work_days = count_weekdays(start, end)
        calc = AnalyticsCalculator(unique_events, unique_prev, work_days, workday_hours=ctx.workday_hours)

        productivity_items = calc.get_productivity_metrics()
        return [
            ProductivityMetric(
                key=item.key,
                title=item.title,
                value=KPIMetricProductivityValue(percent=item.value.percent, hours=item.value.hours) if item.value else None,
                change=item.change,
                positive=item.positive,
                type_value=item.type_value,
            )
            for item in productivity_items
        ]

    async def get_collaboration_table(
        self,
        ctx: AnalyticsContext,
        start_dt: datetime,
        end_dt: datetime,
        sort_by: str,
        reverse: bool,
    ) -> TableResponse:
        events = await self.data_loader.repo.get_meeting_events_for_period(ctx.calendar_ids, start_dt, end_dt, ctx.email)
        events = self.data_loader.get_unique_events(events)

        collab_map: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

        for event in events:
            attendees = self.data_loader.get_attendee_emails(event)
            if ctx.email not in attendees:
                continue

            duration = AnalyticsCalculator.duration_hours(event)
            for att_email in attendees:
                if att_email != ctx.email:
                    collab_map[att_email] += duration

        users = await self.data_loader.repo.get_users_by_emails(list(collab_map.keys()))
        user_map = {u.email: u for u in users}

        result_data = [
            CollaborationTableRow(
                email=participant_email,
                member_profile=UserProfileDTO.model_validate(user_map[participant_email])
                if participant_email in user_map
                else None,
                collab_time=time_value,
            )
            for participant_email, time_value in collab_map.items()
        ]

        result_data.sort(key=lambda x: self._get_sort_value(x, sort_by), reverse=reverse)
        return TableResponse(total_count=len(result_data), data=[row.model_dump() for row in result_data])

    @staticmethod
    def _get_sort_value(row: Any, full_path: str) -> Any:
        try:
            if "." in full_path:
                parts = full_path.split(".")
                obj = row
                for part in parts:
                    obj = getattr(obj, part, None)
                    if obj is None:
                        return 0
                return obj
            return getattr(row, full_path, 0)
        except (AttributeError, TypeError):
            return 0
