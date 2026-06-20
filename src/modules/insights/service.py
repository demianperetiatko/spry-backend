from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.modules.analytics.personal.calculator import AnalyticsCalculator, count_weekdays
from src.modules.analytics.personal.dependency import AnalyticsContext
from src.modules.analytics.personal.repository import PersonalAnalyticsRepository
from src.modules.analytics.personal.services.data_loader import AnalyticsDataLoaderService
from src.modules.calendar.models import CalendarEvent, CalendarEventAttendee, OrganizationMemberCalendar
from src.modules.enums import (
    CalendarAttendeeResponseStatusEnum,
    CalendarEventStatusEnum,
    OrganizationCostTypeEnum,
    OrganizationCostVisibilityEnum,
    OrganizationMemberStatusEnum,
)
from src.modules.insights.schemas import (
    InsightDTO,
    InsightIconType,
    InsightPersonDTO,
    InsightRecommendationDTO,
    InsightStatus,
    InsightTab,
)
from src.modules.organization.model import Organization, OrganizationCurrency
from src.modules.organization_member.model import OrganizationMember
from src.modules.organization_team.model import OrganizationTeam, OrganizationTeamMember
from src.modules.user.model import User


# ── Пороги ────────────────────────────────────────────────────────────────────

# Personal — meeting time
MEETING_TIME_CRITICAL = Decimal("60")
MEETING_TIME_ATTENTION = Decimal("40")
MEETING_TIME_HEALTHY_MAX = Decimal("50")

# Personal — deep work
DEEP_WORK_CRITICAL = Decimal("20")
DEEP_WORK_ATTENTION = Decimal("35")

# Personal — agenda (% зустрічей організованих мною без description)
AGENDA_CRITICAL = Decimal("50")
AGENDA_ATTENTION = Decimal("25")

# Personal — великі зустрічі (6+)
LARGE_MEETING_CRITICAL = Decimal("20")
LARGE_MEETING_ATTENTION = Decimal("10")

# Personal — буфери
BUFFER_HEALTHY_MIN = Decimal("2")
BUFFER_HEALTHY_MAX = Decimal("12")

# Personal — pending responses
PENDING_RESPONSE_ATTENTION = 3

# Personal — нічний час (поза нормою)
AFTER_HOURS_START = 18
AFTER_HOURS_END = 9
AFTER_HOURS_ATTENTION_PCT = Decimal("10")

# Personal — trend (зміна між поточним і попереднім)
MEETING_TREND_ATTENTION = Decimal("8")

# Manager — порівняння з командою
MEMBER_VS_TEAM_RATIO_CRITICAL = Decimal("1.5")   # у 1.5 рази вище середнього
MEMBER_VS_TEAM_RATIO_ATTENTION = Decimal("1.25")

# Organizer rate
ORGANIZER_RATE_ATTENTION = Decimal("60")          # % зустрічей де він організатор

PERSON_COLORS = ["#4F7BF7", "#9B59B6", "#2ECC71", "#E67E22", "#E74C3C"]


def _initials(name: str) -> str:
    parts = name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper()


def _fmt(v: Decimal, decimals: int = 1) -> str:
    return f"{round(float(v), decimals)}"


# ── Головний сервіс ───────────────────────────────────────────────────────────

class InsightsService:
    def __init__(
        self,
        data_loader: AnalyticsDataLoaderService,
        repo: PersonalAnalyticsRepository,
    ) -> None:
        self.data_loader = data_loader
        self.repo = repo

    # ── Точка входу ──────────────────────────────────────────────────────────

    async def generate_personal_insights(
        self,
        ctx: AnalyticsContext,
        is_self: bool = True,
        member_name: str | None = None,
    ) -> list[InsightDTO]:
        """
        Генерує Personal інсайти.
        is_self=True  → режим 1 (ти дивишся на себе)
        is_self=False → режим 2 (менеджер дивиться на члена команди)
        """
        unique_events, unique_prev, _, _ = await self.data_loader.get_comparative_events(ctx, include_all=False)

        (start, end), _ = ctx.params.parse_periods()
        work_days = count_weekdays(start, end)

        calc = AnalyticsCalculator(unique_events, unique_prev, work_days, workday_hours=ctx.workday_hours)
        productivity = calc.get_productivity_metrics()

        metrics: dict[str, tuple[Decimal, Decimal]] = {}
        for item in productivity:
            if item.value:
                metrics[item.key] = (item.value.percent, item.value.hours)

        name = member_name or ""

        if is_self:
            return await self._insights_self(ctx, unique_events, unique_prev, metrics, work_days, start, end)
        else:
            return await self._insights_manager_view(ctx, unique_events, unique_prev, metrics, work_days, name)

    # ── Режим 1: ти дивишся на себе ──────────────────────────────────────────

    async def _insights_self(
        self,
        ctx: AnalyticsContext,
        events,
        prev_events,
        metrics: dict,
        work_days: int,
        start: datetime,
        end: datetime,
    ) -> list[InsightDTO]:
        insights: list[InsightDTO] = []
        total = len(events)

        mt_pct, mt_hrs = metrics.get("meetings_time", (Decimal("0"), Decimal("0")))
        dw_pct, dw_hrs = metrics.get("deep_work", (Decimal("0"), Decimal("0")))
        buf_pct, buf_hrs = metrics.get("buffers", (Decimal("0"), Decimal("0")))

        # ── p-c1: Agenda ──────────────────────────────────────────────────────
        my_organized = [e for e in events if (e.organizer_email or "").lower() == ctx.email.lower()]
        if my_organized:
            no_agenda = [e for e in my_organized if not (e.description or "").strip()]
            no_agenda_pct = Decimal(str(round(len(no_agenda) / len(my_organized) * 100, 1)))

            if no_agenda_pct >= AGENDA_CRITICAL:
                insights.append(InsightDTO(
                    id="p-c1",
                    tab=InsightTab.personal,
                    status=InsightStatus.negative,
                    icon_type=InsightIconType.calendar,
                    title="Half your meetings have no agenda",
                    data_signal=f"{no_agenda_pct}% of meetings you organize have no agenda set.",
                    recommendation=InsightRecommendationDTO(
                        action="Add a one-line agenda to every meeting you book this week",
                        outcome="sharper discussions and easier no-show decisions for attendees",
                    ),
                ))
            elif no_agenda_pct >= AGENDA_ATTENTION:
                insights.append(InsightDTO(
                    id="p-c1",
                    tab=InsightTab.personal,
                    status=InsightStatus.attention,
                    icon_type=InsightIconType.calendar,
                    title="Many meetings you organize are missing an agenda",
                    data_signal=f"{no_agenda_pct}% of meetings you organize have no agenda set.",
                    recommendation=InsightRecommendationDTO(
                        action="Start adding a brief agenda to your own meetings",
                        outcome="more productive discussions",
                    ),
                ))
            else:
                # p-p2: порівняти з попереднім période для тренду
                has_agenda_pct = Decimal("100") - no_agenda_pct
                prev_organized = [e for e in prev_events if (e.organizer_email or "").lower() == ctx.email.lower()]
                trend_str = ""
                if prev_organized:
                    prev_no_agenda = [e for e in prev_organized if not (e.description or "").strip()]
                    prev_no_agenda_pct = Decimal(str(round(len(prev_no_agenda) / len(prev_organized) * 100, 1)))
                    prev_has_pct = Decimal("100") - prev_no_agenda_pct
                    if has_agenda_pct > prev_has_pct + Decimal("5"):
                        trend_str = f" Agenda usage rose from {_fmt(prev_has_pct)}% to {_fmt(has_agenda_pct)}%."
                insights.append(InsightDTO(
                    id="p-p2",
                    tab=InsightTab.personal,
                    status=InsightStatus.positive,
                    icon_type=InsightIconType.trending_up if trend_str else InsightIconType.check,
                    title="Your agenda habit is paying off",
                    data_signal=f"{_fmt(has_agenda_pct)}% of meetings you organize have an agenda set.{trend_str}",
                    recommendation=InsightRecommendationDTO(
                        action="Keep it up",
                        outcome="this is becoming a strong habit",
                    ),
                ))

        # ── p-c2: Великі зустрічі ─────────────────────────────────────────────
        if total > 0:
            large = [e for e in events if len([a for a in e.attendees if not a.resource]) > 5]
            if large:
                large_hrs = sum((AnalyticsCalculator.duration_hours(e) for e in large), Decimal("0"))
                total_hrs = sum((AnalyticsCalculator.duration_hours(e) for e in events), Decimal("0"))
                large_pct = Decimal(str(round(float(large_hrs / total_hrs * 100) if total_hrs else 0, 1)))
                avg_att = Decimal(str(round(
                    sum(len([a for a in e.attendees if not a.resource]) for e in events) / total, 1
                )))

                if large_pct >= LARGE_MEETING_CRITICAL:
                    insights.append(InsightDTO(
                        id="p-c2",
                        tab=InsightTab.personal,
                        status=InsightStatus.negative,
                        icon_type=InsightIconType.meeting_size,
                        title="Most of your meeting time goes to large groups with low return",
                        data_signal=f"6+ person meetings take up {large_pct}% of your meeting hours. You average {avg_att} attendees per meeting.",
                        recommendation=InsightRecommendationDTO(
                            action="Split your largest recurring meeting into a smaller core group plus an async update",
                            outcome="same alignment with far less interruption for others",
                        ),
                    ))
                elif large_pct >= LARGE_MEETING_ATTENTION:
                    insights.append(InsightDTO(
                        id="p-c2",
                        tab=InsightTab.personal,
                        status=InsightStatus.attention,
                        icon_type=InsightIconType.meeting_size,
                        title="Large meetings are taking a notable share of time",
                        data_signal=f"6+ person meetings take up {large_pct}% of your meeting hours.",
                        recommendation=InsightRecommendationDTO(
                            action="Check if all attendees in your largest meetings truly need to be there",
                            outcome="smaller, faster meetings",
                        ),
                    ))

        # ── p-a1: Deep work ───────────────────────────────────────────────────
        if dw_pct < DEEP_WORK_CRITICAL:
            insights.append(InsightDTO(
                id="p-a1",
                tab=InsightTab.personal,
                status=InsightStatus.negative,
                icon_type=InsightIconType.focus,
                title="Deep work share is critically low",
                data_signal=f"Only {_fmt(dw_pct)}% ({_fmt(dw_hrs)}h) of your time is uninterrupted deep work.",
                recommendation=InsightRecommendationDTO(
                    action="Block 2–3 recurring focus sessions this week",
                    outcome="more uninterrupted progress on your own priorities",
                ),
            ))
        elif dw_pct < DEEP_WORK_ATTENTION:
            insights.append(InsightDTO(
                id="p-a1",
                tab=InsightTab.personal,
                status=InsightStatus.attention,
                icon_type=InsightIconType.focus,
                title="Deep work share is below average",
                data_signal=f"Only {_fmt(dw_pct)}% ({_fmt(dw_hrs)}h) of your time is uninterrupted deep work.",
                recommendation=InsightRecommendationDTO(
                    action="Try blocking one focus session per day",
                    outcome="better concentration and faster task completion",
                ),
            ))
        else:
            insights.append(InsightDTO(
                id="p-p3",
                tab=InsightTab.personal,
                status=InsightStatus.positive,
                icon_type=InsightIconType.focus,
                title="Deep work time is healthy",
                data_signal=f"{_fmt(dw_pct)}% ({_fmt(dw_hrs)}h) of your time is uninterrupted deep work.",
                recommendation=InsightRecommendationDTO(
                    action="Keep protecting your focus blocks",
                    outcome="sustained high-quality output",
                ),
            ))

        # ── p-a2: Meeting time trend ──────────────────────────────────────────
        prev_total = sum((AnalyticsCalculator.duration_hours(e) for e in prev_events), Decimal("0"))
        total_hrs_cur = sum((AnalyticsCalculator.duration_hours(e) for e in events), Decimal("0"))
        total_capacity = Decimal(str(work_days)) * (ctx.workday_hours or Decimal("8"))

        if mt_pct >= MEETING_TIME_CRITICAL:
            trend_pct = Decimal("0")
            if prev_total > Decimal("0"):
                trend_pct = ((total_hrs_cur - prev_total) / prev_total * 100).quantize(Decimal("0.1"))
            trend_str = f"up {abs(trend_pct)}%" if trend_pct > 0 else f"down {abs(trend_pct)}%"
            insights.append(InsightDTO(
                id="p-a2",
                tab=InsightTab.personal,
                status=InsightStatus.negative,
                icon_type=InsightIconType.trending_up,
                title="Meeting time keeps climbing",
                data_signal=f"{_fmt(mt_pct)}% ({_fmt(mt_hrs)}h) of your work time goes to meetings — well above the healthy 40% limit. Trend: {trend_str} vs previous period.",
                recommendation=InsightRecommendationDTO(
                    action="Audit your recurring meetings and decline or delegate two that don't need you live",
                    outcome="fewer hours lost to coordination",
                ),
            ))
        elif mt_pct >= MEETING_TIME_ATTENTION:
            insights.append(InsightDTO(
                id="p-a2",
                tab=InsightTab.personal,
                status=InsightStatus.attention,
                icon_type=InsightIconType.trending_up,
                title="Meeting load is getting heavy",
                data_signal=f"{_fmt(mt_pct)}% ({_fmt(mt_hrs)}h) of your work time goes to meetings.",
                recommendation=InsightRecommendationDTO(
                    action="Review your calendar for meetings you could skip or shorten",
                    outcome="more time for focused work",
                ),
            ))
        elif mt_pct <= MEETING_TIME_HEALTHY_MAX:
            insights.append(InsightDTO(
                id="p-p4",
                tab=InsightTab.personal,
                status=InsightStatus.positive,
                icon_type=InsightIconType.check,
                title="Your meeting load is balanced",
                data_signal=f"Time on meetings sits at {_fmt(mt_pct)}%, right within the healthy range.",
                recommendation=InsightRecommendationDTO(
                    action="No action needed",
                    outcome="keep current pace",
                ),
            ))

        # ── p-a3: Стагнуючі recurring серії ──────────────────────────────────
        # ВИДАЛЕНО: міряло e.updated_at (оновлюється при кожному синку календаря),
        # але стверджувало користувачу що "agenda/description не мінявся 90+ днів".
        # Це різні речі — недостовірний сигнал. Повернути після того, як sync-пайплайн
        # почне трекати хеш вмісту події (summary+description+duration). Див. spawn_task.

        # ── p-a4: Pending responses ───────────────────────────────────────────
        now = datetime.now(timezone.utc)
        all_events_raw = await self.repo.get_events_for_period(
            ctx.calendar_ids,
            ctx.params.parse_start_datetime(),
            ctx.params.parse_end_datetime(),
            include_cancelled=False,
        )
        pending_past = [
            e for e in all_events_raw
            if e.end_datetime < now
            for a in e.attendees
            if a.email.lower() == ctx.email.lower()
            and a.response_status == CalendarAttendeeResponseStatusEnum.NEEDS_ACTION
        ]
        if len(pending_past) >= PENDING_RESPONSE_ATTENTION:
            insights.append(InsightDTO(
                id="p-a4",
                tab=InsightTab.personal,
                status=InsightStatus.attention,
                icon_type=InsightIconType.calendar,
                title="Pending responses are piling up",
                data_signal=f"{len(pending_past)} invites sit in 'needsAction' past their start time over the last 2 weeks.",
                recommendation=InsightRecommendationDTO(
                    action="Clear your inbox of pending invites — accept or decline within a day of receiving",
                    outcome="cleaner calendar and clearer commitments",
                ),
            ))

        # ── p-p1: Buffers ─────────────────────────────────────────────────────
        if BUFFER_HEALTHY_MIN <= buf_pct <= BUFFER_HEALTHY_MAX:
            insights.append(InsightDTO(
                id="p-p1",
                tab=InsightTab.personal,
                status=InsightStatus.positive,
                icon_type=InsightIconType.check,
                title="Buffers are well managed",
                data_signal=f"Buffer time sits at {_fmt(buf_pct)}% ({_fmt(buf_hrs)}h), in line with a healthy range.",
                recommendation=InsightRecommendationDTO(
                    action="Keep current scheduling habits",
                    outcome="low context-switching overhead and more usable time per day",
                ),
            ))

        return insights

    # ── Режим 2: менеджер дивиться на людину ─────────────────────────────────

    async def _insights_manager_view(
        self,
        ctx: AnalyticsContext,
        events,
        prev_events,
        metrics: dict,
        work_days: int,
        name: str,
    ) -> list[InsightDTO]:
        insights: list[InsightDTO] = []
        total = len(events)

        mt_pct, mt_hrs = metrics.get("meetings_time", (Decimal("0"), Decimal("0")))
        dw_pct, dw_hrs = metrics.get("deep_work", (Decimal("0"), Decimal("0")))

        # Середнє по команді
        team_avg = await self._get_team_avg_metrics(ctx)
        team_mt_avg = team_avg.get("meetings_time_pct", Decimal("40"))
        team_dw_avg = team_avg.get("deep_work_pct", Decimal("35"))

        # ── m-c1: Ratio inverted ──────────────────────────────────────────────
        if (
            mt_pct > team_mt_avg * MEMBER_VS_TEAM_RATIO_CRITICAL
            and dw_pct < team_dw_avg / MEMBER_VS_TEAM_RATIO_CRITICAL
        ):
            insights.append(InsightDTO(
                id="m-c1",
                tab=InsightTab.personal,
                status=InsightStatus.negative,
                icon_type=InsightIconType.balance,
                title=f"{name}'s meeting/deep-work ratio is inverted vs the team",
                data_signal=(
                    f"{name} spends {_fmt(mt_pct)}% of time in meetings vs only {_fmt(dw_pct)}% in deep work "
                    f"— the opposite of the team's {_fmt(team_mt_avg)}%/{_fmt(team_dw_avg)}% split."
                ),
                recommendation=InsightRecommendationDTO(
                    action=f"Rebalance {name}'s calendar toward the team's typical pattern over the next two weeks",
                    outcome="healthier focus time and reduced burnout risk",
                ),
            ))

        # ── m-a1: Climbing fast ───────────────────────────────────────────────
        prev_total = sum((AnalyticsCalculator.duration_hours(e) for e in prev_events), Decimal("0"))
        total_hrs = sum((AnalyticsCalculator.duration_hours(e) for e in events), Decimal("0"))
        trend = Decimal("0")
        if prev_total > Decimal("0"):
            trend = ((total_hrs - prev_total) / prev_total * 100).quantize(Decimal("0.1"))

        if mt_pct >= MEETING_TIME_ATTENTION and trend >= MEETING_TREND_ATTENTION:
            insights.append(InsightDTO(
                id="m-a1",
                tab=InsightTab.personal,
                status=InsightStatus.attention,
                icon_type=InsightIconType.trending_up,
                title=f"{name}'s meeting load is climbing fast",
                data_signal=(
                    f"{name}'s meeting time is {_fmt(mt_hrs)}h ({_fmt(mt_pct)}% of work hours), "
                    f"rising {_fmt(trend)}% vs previous period."
                ),
                recommendation=InsightRecommendationDTO(
                    action=f"Review which of {name}'s recurring meetings truly need them present",
                    outcome="more build time, faster delivery, fewer delays",
                ),
            ))

        # ── m-a2: Organizer rate ──────────────────────────────────────────────
        if total > 0:
            organized = [e for e in events if (e.organizer_email or "").lower() == ctx.email.lower()]
            organizer_rate = Decimal(str(round(len(organized) / total * 100, 1)))
            if organizer_rate >= ORGANIZER_RATE_ATTENTION:
                insights.append(InsightDTO(
                    id="m-a2",
                    tab=InsightTab.personal,
                    status=InsightStatus.attention,
                    icon_type=InsightIconType.calendar,
                    title=f"{name} is organizing more than the rest of the team",
                    data_signal=f"{name} organizes {_fmt(organizer_rate)}% of their meetings vs team average of {_fmt(team_avg.get('organizer_rate', Decimal('30')))}%.",
                    recommendation=InsightRecommendationDTO(
                        action=f"Check if some of this organizing load can shift to a co-owner",
                        outcome="more balanced ownership and less coordination overhead for one person",
                    ),
                ))

        # ── m-a3: After-hours ─────────────────────────────────────────────────
        if total > 0:
            after_hours = [
                e for e in events
                if e.start_datetime.hour >= AFTER_HOURS_START or e.start_datetime.hour < AFTER_HOURS_END
            ]
            ah_pct = Decimal(str(round(len(after_hours) / total * 100, 1)))
            if ah_pct >= AFTER_HOURS_ATTENTION_PCT:
                insights.append(InsightDTO(
                    id="m-a3",
                    tab=InsightTab.personal,
                    status=InsightStatus.attention,
                    icon_type=InsightIconType.calendar,
                    title=f"{name}'s meetings often run outside normal hours",
                    data_signal=f"{_fmt(ah_pct)}% of {name}'s meetings start before 9am or after 6pm this period.",
                    recommendation=InsightRecommendationDTO(
                        action=f"Worth a quick check-in on workload and scheduling boundaries",
                        outcome="better work-life balance and sustainable pace",
                    ),
                ))

        # ── m-p1: Healthy balance ─────────────────────────────────────────────
        if (
            MEETING_TIME_ATTENTION <= mt_pct <= MEETING_TIME_HEALTHY_MAX
            and dw_pct >= DEEP_WORK_ATTENTION
        ):
            insights.append(InsightDTO(
                id="m-p1",
                tab=InsightTab.personal,
                status=InsightStatus.positive,
                icon_type=InsightIconType.check,
                title=f"{name} has a healthy meeting/focus balance",
                data_signal=f"{name}'s split sits at {_fmt(mt_pct)}% meetings / {_fmt(dw_pct)}% deep work, in line with the team's healthy range.",
                recommendation=InsightRecommendationDTO(
                    action="No action needed",
                    outcome="good pattern to recognize in your next 1:1",
                ),
            ))

        # ── m-a4: 💰 High meeting cost ────────────────────────────────────────
        currency_stmt = (
            select(OrganizationCurrency)
            .join(Organization, Organization.organizations_currency_id == OrganizationCurrency.id)
            .where(Organization.id == ctx.org.id)
        )
        cur_result = await self.repo.session.execute(currency_stmt)
        currency = cur_result.scalar_one_or_none()
        cost_active = currency.cost_is_active if currency else False
        cost_visibility = currency.cost_visibility if currency else None
        avg_cost_org = (currency.cost_avg or Decimal("0")) if currency else Decimal("0")

        auth_role = getattr(ctx.auth_member, "role", None)
        can_see_cost = (
            cost_active
            and cost_visibility in (
                OrganizationCostVisibilityEnum.ALL,
                OrganizationCostVisibilityEnum.MANAGER,
                OrganizationCostVisibilityEnum.ADMIN,
            )
        )

        if can_see_cost and total_hrs > Decimal("0"):
            member_cost_per_hr = ctx.member.hourly_cost or avg_cost_org
            member_meeting_cost = (total_hrs * member_cost_per_hr).quantize(Decimal("0.01"))
            team_avg_cost = team_avg.get("meeting_cost", Decimal("0"))
            if team_avg_cost > Decimal("0") and member_meeting_cost > team_avg_cost * MEMBER_VS_TEAM_RATIO_ATTENTION:
                insights.append(InsightDTO(
                    id="m-a4",
                    tab=InsightTab.personal,
                    status=InsightStatus.attention,
                    icon_type=InsightIconType.cost,
                    title=f"{name}'s meeting time carries a high cost",
                    data_signal=(
                        f"{name}'s meeting hours represent ${member_meeting_cost:,.0f} this period, "
                        f"above the team average of ${team_avg_cost:,.0f}."
                    ),
                    recommendation=InsightRecommendationDTO(
                        action=f"Review whether {name}'s presence is required on the highest-cost recurring series",
                        outcome="better return on their time investment",
                    ),
                ))

        # ── m-p2: Strong agenda discipline ───────────────────────────────────
        if total > 0:
            member_organized = [e for e in events if (e.organizer_email or "").lower() == ctx.email.lower()]
            if member_organized:
                member_no_ag = [e for e in member_organized if not (e.description or "").strip()]
                member_agenda_pct = Decimal("100") - Decimal(str(round(len(member_no_ag) / len(member_organized) * 100, 1)))
                team_agenda_avg = team_avg.get("agenda_pct", Decimal("50"))
                if member_agenda_pct >= Decimal("70") and member_agenda_pct > team_agenda_avg + Decimal("15"):
                    insights.append(InsightDTO(
                        id="m-p2",
                        tab=InsightTab.personal,
                        status=InsightStatus.positive,
                        icon_type=InsightIconType.check,
                        title=f"{name}'s agenda discipline is strong",
                        data_signal=(
                            f"{name} sets an agenda on {_fmt(member_agenda_pct)}% of meetings they organize, "
                            f"above team average of {_fmt(team_agenda_avg)}%."
                        ),
                        recommendation=InsightRecommendationDTO(
                            action="Worth calling out as a positive example for the team",
                            outcome="encourages the same habit in others",
                        ),
                    ))

        # ── m-p3: Improving ──────────────────────────────────────────────────
        if prev_total > Decimal("0") and trend <= Decimal("-8"):
            prev_capacity = Decimal(str(work_days)) * (ctx.workday_hours or Decimal("8"))
            prev_pct = (prev_total / prev_capacity * 100).quantize(Decimal("0.1")) if prev_capacity else Decimal("0")
            insights.append(InsightDTO(
                id="m-p3",
                tab=InsightTab.personal,
                status=InsightStatus.positive,
                icon_type=InsightIconType.trending_down,
                title=f"{name}'s workload trend is improving",
                data_signal=f"{name}'s meeting share dropped from {_fmt(prev_pct)}% to {_fmt(mt_pct)}% over this period.",
                recommendation=InsightRecommendationDTO(
                    action=f"Good moment to acknowledge the change in your next 1:1",
                    outcome="reinforces positive calendar habits",
                ),
            ))

        return insights

    # ── Допоміжний: середнє по команді ───────────────────────────────────────

    async def _get_team_avg_metrics(self, ctx: AnalyticsContext) -> dict[str, Decimal]:
        """Рахує середні метрики по членах команди для порівняння."""
        team_emails = await self.repo.get_team_member_emails(ctx.member.id)
        if not team_emails or len(team_emails) <= 1:
            return {
                "meetings_time_pct": Decimal("40"),
                "deep_work_pct": Decimal("35"),
                "organizer_rate": Decimal("30"),
            }

        from src.modules.organization_member.model import OrganizationMember
        from src.modules.user.model import User

        stmt = (
            select(OrganizationMember, User.email)
            .join(User, OrganizationMember.user_id == User.id)
            .where(
                OrganizationMember.organization_id == ctx.org.id,
                OrganizationMember.status == OrganizationMemberStatusEnum.ACTIVE,
                User.email.in_(team_emails),
            )
        )
        result = await self.repo.session.execute(stmt)
        rows = result.all()

        (start, end), _ = ctx.params.parse_periods()
        work_days = count_weekdays(start, end)
        total_capacity = Decimal(str(work_days)) * (ctx.workday_hours or Decimal("8"))

        # Батч calendar-id lookup замість N окремих запитів
        cal_ids_by_member = await self.repo.get_calendar_ids_for_members(
            [member.id for member, _ in rows]
        )

        all_mt_pcts: list[Decimal] = []
        all_dw_pcts: list[Decimal] = []
        all_org_rates: list[Decimal] = []
        all_agenda_pcts: list[Decimal] = []
        all_meeting_costs: list[Decimal] = []

        for member, email in rows:
            if email.lower() == ctx.email.lower():
                continue

            cal_ids = cal_ids_by_member.get(member.id, [])
            if not cal_ids:
                continue

            member_events = await self.repo.get_meeting_events_for_period(cal_ids, start, end, email)
            unique = self.data_loader.get_unique_events(list(member_events))
            if not unique:
                continue

            mt_hrs = sum((AnalyticsCalculator.duration_hours(e) for e in unique), Decimal("0"))
            mt_pct = (mt_hrs / total_capacity * 100).quantize(Decimal("0.1")) if total_capacity else Decimal("0")
            all_mt_pcts.append(mt_pct)

            calc = AnalyticsCalculator(unique, [], work_days, workday_hours=ctx.workday_hours)
            prod = calc.get_productivity_metrics()
            for item in prod:
                if item.key == "deep_work" and item.value:
                    all_dw_pcts.append(item.value.percent)
                    break

            organized = [e for e in unique if (e.organizer_email or "").lower() == email.lower()]
            org_rate = Decimal(str(round(len(organized) / len(unique) * 100, 1)))
            all_org_rates.append(org_rate)

            if organized:
                no_ag = [e for e in organized if not (e.description or "").strip()]
                ag_pct = Decimal("100") - Decimal(str(round(len(no_ag) / len(organized) * 100, 1)))
                all_agenda_pcts.append(ag_pct)

            hourly = member.hourly_cost or Decimal("0")
            if hourly > Decimal("0"):
                all_meeting_costs.append(mt_hrs * hourly)

        def avg(lst: list[Decimal]) -> Decimal:
            return (sum(lst, Decimal("0")) / Decimal(str(len(lst)))).quantize(Decimal("0.1")) if lst else Decimal("0")

        return {
            "meetings_time_pct": avg(all_mt_pcts) or Decimal("40"),
            "deep_work_pct": avg(all_dw_pcts) or Decimal("35"),
            "organizer_rate": avg(all_org_rates) or Decimal("30"),
            "agenda_pct": avg(all_agenda_pcts) or Decimal("50"),
            "meeting_cost": avg(all_meeting_costs),
        }


# ── Допоміжні структури для агрегації ─────────────────────────────────────────

@dataclass
class MemberStats:
    member_id: uuid.UUID
    name: str
    email: str
    hourly_cost: Decimal
    events: list[CalendarEvent] = field(default_factory=list)
    prev_events: list[CalendarEvent] = field(default_factory=list)

    @property
    def total_hrs(self) -> Decimal:
        return sum((AnalyticsCalculator.duration_hours(e) for e in self.events), Decimal("0"))

    @property
    def prev_hrs(self) -> Decimal:
        return sum((AnalyticsCalculator.duration_hours(e) for e in self.prev_events), Decimal("0"))

    def mt_pct(self, capacity: Decimal) -> Decimal:
        return (self.total_hrs / capacity * 100).quantize(Decimal("0.1")) if capacity else Decimal("0")

    def trend_pct(self) -> Decimal:
        if self.prev_hrs <= Decimal("0"):
            return Decimal("0")
        return ((self.total_hrs - self.prev_hrs) / self.prev_hrs * 100).quantize(Decimal("0.1"))

    def meeting_cost(self) -> Decimal:
        return (self.total_hrs * self.hourly_cost).quantize(Decimal("0.01"))

    def agenda_pct(self) -> Decimal:
        organized = [e for e in self.events if (e.organizer_email or "").lower() == self.email.lower()]
        if not organized:
            return Decimal("0")
        no_agenda = [e for e in organized if not (e.description or "").strip()]
        return Decimal(str(round(len(no_agenda) / len(organized) * 100, 1)))

    def avg_attendees(self) -> Decimal:
        if not self.events:
            return Decimal("0")
        return Decimal(str(round(
            sum(len([a for a in e.attendees if not a.resource]) for e in self.events) / len(self.events), 1
        )))

    def recurring_rate(self) -> Decimal:
        if not self.events:
            return Decimal("0")
        recurring = [e for e in self.events if e.recurring_event_id]
        return Decimal(str(round(len(recurring) / len(self.events) * 100, 1)))

    def initials(self) -> str:
        parts = self.name.strip().split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return self.name[:2].upper() if self.name else "??"

    def to_person_dto(self, color: str) -> InsightPersonDTO:
        return InsightPersonDTO(
            name=self.name,
            initials=self.initials(),
            color=color,
            member_id=None,
        )


def _event_cost(event: CalendarEvent, member_costs: dict[str, Decimal], avg_cost: Decimal) -> Decimal:
    hrs = AnalyticsCalculator.duration_hours(event)
    total = Decimal("0")
    for att in event.attendees:
        if not att.resource:
            total += hrs * member_costs.get(att.email.lower(), avg_cost)
    return total.quantize(Decimal("0.01"))


# ── Teams insights service ────────────────────────────────────────────────────

class TeamInsightsService:
    def __init__(self, repo: PersonalAnalyticsRepository, data_loader: AnalyticsDataLoaderService) -> None:
        self.repo = repo
        self.data_loader = data_loader

    async def generate(
        self,
        team_id: uuid.UUID,
        org: Organization,
        auth_member: OrganizationMember,
        start: datetime,
        end: datetime,
        prev_start: datetime,
        prev_end: datetime,
        workday_hours: Decimal,
    ) -> list[InsightDTO]:
        work_days = count_weekdays(start, end)
        capacity = Decimal(str(work_days)) * workday_hours

        # Завантажити членів команди
        team_stmt = (
            select(OrganizationTeamMember)
            .options(selectinload(OrganizationTeamMember.member).selectinload(OrganizationMember.user))
            .where(OrganizationTeamMember.team_id == team_id)
        )
        result = await self.repo.session.execute(team_stmt)
        team_members_rows = result.scalars().all()

        # Отримати cost config через organizations_currency_id
        currency_stmt = (
            select(OrganizationCurrency)
            .join(Organization, Organization.organizations_currency_id == OrganizationCurrency.id)
            .where(Organization.id == org.id)
        )
        cur_result = await self.repo.session.execute(currency_stmt)
        currency = cur_result.scalar_one_or_none()
        avg_cost = (currency.cost_avg or Decimal("0")) if currency else Decimal("0")
        cost_active = currency.cost_is_active if currency else False

        # Батч calendar-id lookup замість N окремих запитів
        cal_ids_by_member = await self.repo.get_calendar_ids_for_members(
            [tm.member.id for tm in team_members_rows if tm.member]
        )

        # Зібрати stats для кожного члена
        stats: list[MemberStats] = []
        for tm in team_members_rows:
            member = tm.member
            if not member or not member.user:
                continue
            email = member.user.email
            cal_ids = cal_ids_by_member.get(member.id, [])
            if not cal_ids:
                continue

            events = self.data_loader.get_unique_events(
                list(await self.repo.get_meeting_events_for_period(cal_ids, start, end, email))
            )
            prev_events = self.data_loader.get_unique_events(
                list(await self.repo.get_meeting_events_for_period(cal_ids, prev_start, prev_end, email))
            )
            hourly = member.hourly_cost or avg_cost

            stats.append(MemberStats(
                member_id=member.id,
                name=member.user.name or email,
                email=email,
                hourly_cost=hourly,
                events=events,
                prev_events=prev_events,
            ))

        if not stats:
            return []

        # Email → cost map
        member_costs = {s.email.lower(): s.hourly_cost for s in stats}
        all_emails = {s.email.lower() for s in stats}

        insights: list[InsightDTO] = []

        # Всі зустрічі команди (unique by event id)
        all_event_ids: dict[str, CalendarEvent] = {}
        for s in stats:
            for e in s.events:
                all_event_ids[str(e.id)] = e

        all_team_events = list(all_event_ids.values())

        # ── t-c1: 💰 Найдорожча recurring зустріч ─────────────────────────────
        if cost_active:
            recurring_costs: dict[str, tuple[Decimal, str]] = {}
            for e in all_team_events:
                if e.recurring_event_id:
                    cost = _event_cost(e, member_costs, avg_cost)
                    prev_cost, name = recurring_costs.get(e.recurring_event_id, (Decimal("0"), e.summary or "Meeting"))
                    recurring_costs[e.recurring_event_id] = (prev_cost + cost, name)

            if recurring_costs:
                top_series_id = max(recurring_costs, key=lambda k: recurring_costs[k][0])
                top_cost, top_name = recurring_costs[top_series_id]
                # Знайдемо зустріч щоб отримати тривалість та кількість учасників
                top_events = [e for e in all_team_events if e.recurring_event_id == top_series_id]
                if top_events:
                    sample = top_events[0]
                    dur_min = int(AnalyticsCalculator.duration_hours(sample) * 60)
                    att_count = len([a for a in sample.attendees if not a.resource])
                    insights.append(InsightDTO(
                        id="t-c1",
                        tab=InsightTab.teams,
                        status=InsightStatus.negative,
                        icon_type=InsightIconType.cost,
                        title="Top recurring meeting is expensive relative to its cadence",
                        data_signal=(
                            f'"{top_name}" runs {dur_min} min with {att_count} attendees, '
                            f"costing ${top_cost:,.0f} this period."
                        ),
                        recommendation=InsightRecommendationDTO(
                            action="Trial a shorter format or split into async prep + sync decisions",
                            outcome="the same output at lower time and cost",
                        ),
                    ))

        # ── t-c2: Member з найгіршим ratio ────────────────────────────────────
        if capacity > Decimal("0"):
            team_mt_avg = (
                sum(s.mt_pct(capacity) for s in stats) / Decimal(str(len(stats)))
            ).quantize(Decimal("0.1"))
            team_dw_values: list[Decimal] = []
            for s in stats:
                if s.events:
                    calc = AnalyticsCalculator(s.events, [], work_days, workday_hours=workday_hours)
                    for item in calc.get_productivity_metrics():
                        if item.key == "deep_work" and item.value:
                            team_dw_values.append(item.value.percent)
                            break
            team_dw_avg = (
                sum(team_dw_values) / Decimal(str(len(team_dw_values)))
            ).quantize(Decimal("0.1")) if team_dw_values else Decimal("35")

            worst: MemberStats | None = None
            worst_score = Decimal("0")
            for s in stats:
                mt = s.mt_pct(capacity)
                ratio = mt / team_mt_avg if team_mt_avg else Decimal("0")
                if ratio >= MEMBER_VS_TEAM_RATIO_CRITICAL and ratio > worst_score:
                    worst = s
                    worst_score = ratio

            if worst:
                wmt = worst.mt_pct(capacity)
                wdw = Decimal("0")
                if worst.events:
                    calc = AnalyticsCalculator(worst.events, [], work_days, workday_hours=workday_hours)
                    for item in calc.get_productivity_metrics():
                        if item.key == "deep_work" and item.value:
                            wdw = item.value.percent
                            break
                insights.append(InsightDTO(
                    id="t-c2",
                    tab=InsightTab.teams,
                    status=InsightStatus.negative,
                    icon_type=InsightIconType.balance,
                    title=f"{worst.name}'s meeting/deep-work ratio is inverted vs the team",
                    data_signal=(
                        f"{worst.name} spends {_fmt(wmt)}% of time in meetings vs only {_fmt(wdw)}% in deep work "
                        f"— the opposite of the team's {_fmt(team_mt_avg)}%/{_fmt(team_dw_avg)}% split."
                    ),
                    recommendation=InsightRecommendationDTO(
                        action=f"Rebalance {worst.name}'s calendar toward the team's typical pattern over the next two weeks",
                        outcome="healthier focus time and reduced burnout risk",
                    ),
                    persons=[worst.to_person_dto(PERSON_COLORS[0])],
                ))

        # ── t-a1: Cross-team collab ────────────────────────────────────────────
        cross_hrs = Decimal("0")
        cross_cost = Decimal("0")
        for e in all_team_events:
            non_team = [a for a in e.attendees if not a.resource and a.email.lower() not in all_emails]
            if non_team:
                hrs = AnalyticsCalculator.duration_hours(e)
                cross_hrs += hrs
                if cost_active:
                    cross_cost += _event_cost(e, member_costs, avg_cost)

        if cross_hrs >= Decimal("10"):
            cost_str = f" / ${cross_cost:,.0f}" if cost_active and cross_cost > 0 else ""
            insights.append(InsightDTO(
                id="t-a1",
                tab=InsightTab.teams,
                status=InsightStatus.attention,
                icon_type=InsightIconType.collab,
                title="Cross-team collaboration time is concentrated on your team",
                data_signal=f"Your team shows {_fmt(cross_hrs)}h{cost_str} in cross-team collab this period.",
                recommendation=InsightRecommendationDTO(
                    action="Check whether this collab time maps to planned project work or ad-hoc pulls",
                    outcome="clearer boundaries between project time and support time",
                ),
            ))

        # ── t-a2: Member with fastest growing meeting load ─────────────────────
        if capacity > Decimal("0"):
            fastest: MemberStats | None = None
            fastest_trend = Decimal("0")
            for s in stats:
                mt = s.mt_pct(capacity)
                tr = s.trend_pct()
                if mt >= MEETING_TIME_ATTENTION and tr >= MEETING_TREND_ATTENTION and tr > fastest_trend:
                    fastest = s
                    fastest_trend = tr

            if fastest:
                insights.append(InsightDTO(
                    id="t-a2",
                    tab=InsightTab.teams,
                    status=InsightStatus.attention,
                    icon_type=InsightIconType.trending_up,
                    title=f"{fastest.name}'s meeting load is climbing fast",
                    data_signal=(
                        f"{fastest.name}'s meeting time is {_fmt(fastest.total_hrs)}h "
                        f"({_fmt(fastest.mt_pct(capacity))}% of work hours), "
                        f"rising {_fmt(fastest_trend)}% vs previous period."
                    ),
                    recommendation=InsightRecommendationDTO(
                        action=f"Review which of {fastest.name}'s recurring meetings truly need them present",
                        outcome="more build time, faster delivery, fewer delays",
                    ),
                    persons=[fastest.to_person_dto(PERSON_COLORS[0])],
                ))

        # ── t-a3: Agenda variance across team ─────────────────────────────────
        agenda_pcts = [(s.name, s.agenda_pct()) for s in stats if s.events]
        if len(agenda_pcts) >= 2:
            min_name, min_pct = min(agenda_pcts, key=lambda x: x[1])
            max_name, max_pct = max(agenda_pcts, key=lambda x: x[1])
            spread = max_pct - min_pct
            if spread >= Decimal("30"):
                has_agenda_min_pct = Decimal("100") - min_pct
                has_agenda_max_pct = Decimal("100") - max_pct
                insights.append(InsightDTO(
                    id="t-a3",
                    tab=InsightTab.teams,
                    status=InsightStatus.attention,
                    icon_type=InsightIconType.calendar,
                    title="Agenda usage varies a lot across the team",
                    data_signal=(
                        f"Agenda usage ranges from {_fmt(has_agenda_max_pct)}% ({max_name}) "
                        f"to {_fmt(has_agenda_min_pct)}% ({min_name}) between team members."
                    ),
                    recommendation=InsightRecommendationDTO(
                        action="Share agenda-setting practices from the highest-scoring members at your next team sync",
                        outcome="more consistent meeting quality across the team",
                    ),
                ))

        # ── t-p1: Team deep work recovering ───────────────────────────────────
        team_dw_prev: list[Decimal] = []
        for s in stats:
            if s.prev_events:
                calc = AnalyticsCalculator(s.prev_events, [], work_days, workday_hours=workday_hours)
                for item in calc.get_productivity_metrics():
                    if item.key == "deep_work" and item.value:
                        team_dw_prev.append(item.value.percent)
                        break

        if team_dw_values and team_dw_prev:
            dw_cur_avg = sum(team_dw_values) / Decimal(str(len(team_dw_values)))
            dw_prev_avg = sum(team_dw_prev) / Decimal(str(len(team_dw_prev)))
            if dw_cur_avg > dw_prev_avg + Decimal("5"):
                dw_hrs_avg = Decimal("0")
                for s in stats:
                    if s.events:
                        calc = AnalyticsCalculator(s.events, [], work_days, workday_hours=workday_hours)
                        for item in calc.get_productivity_metrics():
                            if item.key == "deep_work" and item.value:
                                dw_hrs_avg += item.value.hours
                                break
                dw_hrs_avg = (dw_hrs_avg / Decimal(str(len(stats)))).quantize(Decimal("0.1"))
                insights.append(InsightDTO(
                    id="t-p1",
                    tab=InsightTab.teams,
                    status=InsightStatus.positive,
                    icon_type=InsightIconType.trending_up,
                    title="Deep work is recovering across the team",
                    data_signal=(
                        f"Team deep work rose {_fmt(dw_prev_avg)}% → {_fmt(dw_cur_avg)}% "
                        f"({_fmt(dw_hrs_avg)}h average per person)."
                    ),
                    recommendation=InsightRecommendationDTO(
                        action="Share what's working in your team's calendar setup with other team leads",
                        outcome="the same gains across the org",
                    ),
                ))

        # ── t-p3: Team meeting size staying lean ──────────────────────────────
        if all_team_events:
            avg_att = Decimal(str(round(
                sum(len([a for a in e.attendees if not a.resource]) for e in all_team_events) / len(all_team_events), 1
            )))
            if avg_att <= Decimal("5"):
                insights.append(InsightDTO(
                    id="t-p3",
                    tab=InsightTab.teams,
                    status=InsightStatus.positive,
                    icon_type=InsightIconType.check,
                    title="Team meeting size is staying lean",
                    data_signal=f"Average attendees per team meeting is {_fmt(avg_att)}, below the typical 6-person threshold.",
                    recommendation=InsightRecommendationDTO(
                        action="Maintain current invite habits",
                        outcome="focused discussions and less coordination overhead",
                    ),
                ))

        # ── t-p4: Agenda adoption climbing ────────────────────────────────────
        if agenda_pcts and team_dw_prev:
            prev_agenda_pcts: list[Decimal] = []
            for s in stats:
                if s.prev_events:
                    organized_prev = [e for e in s.prev_events if (e.organizer_email or "").lower() == s.email.lower()]
                    if organized_prev:
                        no_agenda_prev = [e for e in organized_prev if not (e.description or "").strip()]
                        prev_agenda_pcts.append(Decimal("100") - Decimal(str(round(len(no_agenda_prev) / len(organized_prev) * 100, 1))))
            cur_agenda_avg = (
                sum(Decimal("100") - p for _, p in agenda_pcts) / Decimal(str(len(agenda_pcts)))
            ).quantize(Decimal("0.1"))
            if prev_agenda_pcts:
                prev_agenda_avg = (sum(prev_agenda_pcts) / Decimal(str(len(prev_agenda_pcts)))).quantize(Decimal("0.1"))
                if cur_agenda_avg > prev_agenda_avg + Decimal("5"):
                    insights.append(InsightDTO(
                        id="t-p4",
                        tab=InsightTab.teams,
                        status=InsightStatus.positive,
                        icon_type=InsightIconType.trending_up,
                        title="Agenda adoption is climbing on your team",
                        data_signal=f"Team-wide agenda usage rose from {_fmt(prev_agenda_avg)}% to {_fmt(cur_agenda_avg)}% this period.",
                        recommendation=InsightRecommendationDTO(
                            action="Recognize this progress at your next retro",
                            outcome="reinforces good meeting habits across the team",
                        ),
                    ))

        # ── t-p2: Cancellation discipline ─────────────────────────────────────
        # Перевіряємо recurring серії: якщо <= 10% cancellations — хороший знак
        cancelled_rates: list[Decimal] = []
        for s in stats:
            all_events_for_recur = [e for e in s.events if e.recurring_event_id]
            if not all_events_for_recur:
                continue
            cancelled = [e for e in all_events_for_recur if e.status == CalendarEventStatusEnum.CANCELLED]
            rate = Decimal(str(round(len(cancelled) / len(all_events_for_recur) * 100, 1)))
            cancelled_rates.append(rate)

        if cancelled_rates:
            avg_cancel = (sum(cancelled_rates) / Decimal(str(len(cancelled_rates)))).quantize(Decimal("0.1"))
            if avg_cancel <= Decimal("10"):
                insights.append(InsightDTO(
                    id="t-p2",
                    tab=InsightTab.teams,
                    status=InsightStatus.positive,
                    icon_type=InsightIconType.check,
                    title="Cancellation discipline is solid on key syncs",
                    data_signal=f"Only {_fmt(avg_cancel)}% of recurring series meetings were cancelled this period.",
                    recommendation=InsightRecommendationDTO(
                        action="Keep recurring series on schedule unless truly unnecessary",
                        outcome="stable cadence builds team trust and reduces uncertainty",
                    ),
                ))

        return insights


# ── Organization insights service ─────────────────────────────────────────────

class OrgInsightsService:
    def __init__(self, repo: PersonalAnalyticsRepository, data_loader: AnalyticsDataLoaderService) -> None:
        self.repo = repo
        self.data_loader = data_loader

    async def generate(
        self,
        org: Organization,
        start: datetime,
        end: datetime,
        prev_start: datetime,
        prev_end: datetime,
        workday_hours: Decimal,
    ) -> list[InsightDTO]:
        work_days = count_weekdays(start, end)
        capacity = Decimal(str(work_days)) * workday_hours

        # Завантажити всіх активних членів org з email + cost
        members_stmt = (
            select(OrganizationMember)
            .options(selectinload(OrganizationMember.user))
            .where(
                OrganizationMember.organization_id == org.id,
                OrganizationMember.status == OrganizationMemberStatusEnum.ACTIVE,
            )
        )
        result = await self.repo.session.execute(members_stmt)
        members = result.scalars().all()

        currency_stmt = (
            select(OrganizationCurrency)
            .join(Organization, Organization.organizations_currency_id == OrganizationCurrency.id)
            .where(Organization.id == org.id)
        )
        cur_result = await self.repo.session.execute(currency_stmt)
        currency = cur_result.scalar_one_or_none()
        avg_cost = (currency.cost_avg or Decimal("0")) if currency else Decimal("0")
        cost_active = currency.cost_is_active if currency else False

        # Батч calendar-id lookup замість N окремих запитів
        cal_ids_by_member = await self.repo.get_calendar_ids_for_members(
            [member.id for member in members]
        )

        # Побудувати stats для кожного члена
        stats: list[MemberStats] = []
        for member in members:
            if not member.user:
                continue
            email = member.user.email
            cal_ids = cal_ids_by_member.get(member.id, [])
            if not cal_ids:
                continue
            events = self.data_loader.get_unique_events(
                list(await self.repo.get_meeting_events_for_period(cal_ids, start, end, email))
            )
            prev_events = self.data_loader.get_unique_events(
                list(await self.repo.get_meeting_events_for_period(cal_ids, prev_start, prev_end, email))
            )
            stats.append(MemberStats(
                member_id=member.id,
                name=member.user.name or email,
                email=email,
                hourly_cost=member.hourly_cost or avg_cost,
                events=events,
                prev_events=prev_events,
            ))

        if not stats:
            return []

        member_costs = {s.email.lower(): s.hourly_cost for s in stats}
        # Всі унікальні зустрічі org (дедуп за google_event_id)
        all_by_gid: dict[str, CalendarEvent] = {}
        for s in stats:
            for e in s.events:
                all_by_gid[e.google_event_id] = e
        all_prev_by_gid: dict[str, CalendarEvent] = {}
        for s in stats:
            for e in s.prev_events:
                all_prev_by_gid[e.google_event_id] = e

        all_events = list(all_by_gid.values())
        all_prev_events = list(all_prev_by_gid.values())

        total_hrs = sum((AnalyticsCalculator.duration_hours(e) for e in all_events), Decimal("0"))
        prev_hrs = sum((AnalyticsCalculator.duration_hours(e) for e in all_prev_events), Decimal("0"))
        total_cost = sum((_event_cost(e, member_costs, avg_cost) for e in all_events), Decimal("0"))
        prev_cost = sum((_event_cost(e, member_costs, avg_cost) for e in all_prev_events), Decimal("0"))

        insights: list[InsightDTO] = []

        # ── o-c1: 💰 Топ-2 recurring серії по cost ────────────────────────────
        if cost_active and total_cost > Decimal("0"):
            recurring_costs: dict[str, tuple[Decimal, str]] = {}
            for e in all_events:
                if e.recurring_event_id:
                    c = _event_cost(e, member_costs, avg_cost)
                    prev_c, nm = recurring_costs.get(e.recurring_event_id, (Decimal("0"), e.summary or "Meeting"))
                    recurring_costs[e.recurring_event_id] = (prev_c + c, nm)

            if len(recurring_costs) >= 2:
                top2 = sorted(recurring_costs.items(), key=lambda x: x[1][0], reverse=True)[:2]
                top2_cost = sum(v for _, (v, _) in top2)
                pct = (top2_cost / total_cost * 100).quantize(Decimal("0.1"))
                names = " and ".join(f'"{nm}"' for _, (_, nm) in top2)
                if pct >= Decimal("50"):
                    insights.append(InsightDTO(
                        id="o-c1",
                        tab=InsightTab.organization,
                        status=InsightStatus.negative,
                        icon_type=InsightIconType.cost,
                        title="Two recurring meetings drive most of total meeting cost",
                        data_signal=f"{names} together account for {_fmt(pct)}% of the ${total_cost:,.0f} total meeting cost.",
                        recommendation=InsightRecommendationDTO(
                            action="Redesign or shorten these two recurring meetings",
                            outcome="immediate, org-wide cost savings with minimal disruption",
                        ),
                    ))

        # ── o-c2: Member з найвищим avg attendees + recurring rate ─────────────
        if stats:
            most_overloaded: MemberStats | None = None
            most_score = Decimal("0")
            for s in stats:
                if not s.events:
                    continue
                score = s.avg_attendees() * s.recurring_rate() / Decimal("100")
                if score > most_score:
                    most_overloaded = s
                    most_score = score

            if most_overloaded and most_score >= Decimal("5"):
                insights.append(InsightDTO(
                    id="o-c2",
                    tab=InsightTab.organization,
                    status=InsightStatus.negative,
                    icon_type=InsightIconType.person,
                    title=f"{most_overloaded.name}'s meeting pattern signals a scaling risk",
                    data_signal=(
                        f"{most_overloaded.name} averages {_fmt(most_overloaded.avg_attendees())} attendees "
                        f"and a {_fmt(most_overloaded.recurring_rate())}% recurring rate — "
                        f"both the highest in the org."
                    ),
                    recommendation=InsightRecommendationDTO(
                        action=f"Audit {most_overloaded.name}'s recurring meetings for size and necessity",
                        outcome="a repeatable pattern other organizers can follow as headcount grows",
                    ),
                    persons=[most_overloaded.to_person_dto(PERSON_COLORS[0])],
                ))

        # ── o-a1: 💰 Cost rising faster than time ─────────────────────────────
        if cost_active and prev_hrs > Decimal("0") and prev_cost > Decimal("0"):
            time_trend = ((total_hrs - prev_hrs) / prev_hrs * 100).quantize(Decimal("0.1"))
            cost_trend = ((total_cost - prev_cost) / prev_cost * 100).quantize(Decimal("0.1"))
            if cost_trend > time_trend + Decimal("4") and cost_trend > Decimal("0"):
                insights.append(InsightDTO(
                    id="o-a1",
                    tab=InsightTab.organization,
                    status=InsightStatus.attention,
                    icon_type=InsightIconType.trending_up,
                    title="Total meeting cost is rising faster than meeting time",
                    data_signal=(
                        f"Total meeting cost is up {_fmt(cost_trend)}% to ${total_cost:,.0f} "
                        f"while total time is up {_fmt(time_trend)}%, suggesting higher-cost participants are attending more."
                    ),
                    recommendation=InsightRecommendationDTO(
                        action="Review which meetings include senior/high-cost roles that could be represented by one delegate",
                        outcome="lower coordination cost without losing decision quality",
                    ),
                ))

        # ── o-a2: Recurring dominance з volatile peaks ─────────────────────────
        if all_events:
            recurring_all = [e for e in all_events if e.recurring_event_id]
            recur_rate = Decimal(str(round(len(recurring_all) / len(all_events) * 100, 1)))
            if recur_rate >= Decimal("60"):
                # Порахуємо розкид по днях
                from collections import defaultdict
                daily_hrs: dict[str, Decimal] = defaultdict(Decimal)
                for e in all_events:
                    day_key = e.start_datetime.strftime("%Y-%m-%d")
                    daily_hrs[day_key] += AnalyticsCalculator.duration_hours(e)
                if daily_hrs:
                    daily_vals = list(daily_hrs.values())
                    peak = max(daily_vals)
                    low = min(daily_vals)
                    if peak - low >= Decimal("2"):
                        insights.append(InsightDTO(
                            id="o-a2",
                            tab=InsightTab.organization,
                            status=InsightStatus.attention,
                            icon_type=InsightIconType.trending_up,
                            title="Recurring meetings dominate the week with volatile peaks",
                            data_signal=(
                                f"Recurring meeting hours range from {_fmt(low)}h to {_fmt(peak)}h per day. "
                                f"{_fmt(recur_rate)}% of all meetings are recurring."
                            ),
                            recommendation=InsightRecommendationDTO(
                                action="Monitor weekly meeting spikes, not just averages",
                                outcome="earlier detection of workload pressure points",
                            ),
                        ))

        # ── o-a3: Large meetings ───────────────────────────────────────────────
        if all_events:
            large = [e for e in all_events if len([a for a in e.attendees if not a.resource]) > 5]
            large_hrs = sum((AnalyticsCalculator.duration_hours(e) for e in large), Decimal("0"))
            large_pct = (large_hrs / total_hrs * 100).quantize(Decimal("0.1")) if total_hrs else Decimal("0")
            if large_pct >= LARGE_MEETING_ATTENTION:
                insights.append(InsightDTO(
                    id="o-a3",
                    tab=InsightTab.organization,
                    status=InsightStatus.attention,
                    icon_type=InsightIconType.meeting_size,
                    title="Large meetings are taking a notable share of time",
                    data_signal=f"6+ person meetings take up {_fmt(large_pct)}% of total meeting hours.",
                    recommendation=InsightRecommendationDTO(
                        action="Check if all attendees in your largest meetings truly need to be there",
                        outcome="smaller, faster meetings across the org",
                    ),
                ))

        # ── o-a4: Agenda inconsistency ─────────────────────────────────────────
        agenda_by_member = [(s.name, Decimal("100") - s.agenda_pct()) for s in stats if s.events]
        if len(agenda_by_member) >= 3:
            all_agenda_pcts = [p for _, p in agenda_by_member]
            org_avg = (sum(all_agenda_pcts) / Decimal(str(len(all_agenda_pcts)))).quantize(Decimal("0.1"))
            spread = max(all_agenda_pcts) - min(all_agenda_pcts)
            if spread >= Decimal("30"):
                min_team = min(agenda_by_member, key=lambda x: x[1])
                max_team = max(agenda_by_member, key=lambda x: x[1])
                insights.append(InsightDTO(
                    id="o-a4",
                    tab=InsightTab.organization,
                    status=InsightStatus.attention,
                    icon_type=InsightIconType.calendar,
                    title="Agenda usage is inconsistent across the org",
                    data_signal=(
                        f"Org-wide agenda usage sits at {_fmt(org_avg)}%, "
                        f"ranging from {_fmt(min_team[1])}% ({min_team[0]}) to {_fmt(max_team[1])}% ({max_team[0]})."
                    ),
                    recommendation=InsightRecommendationDTO(
                        action="Identify members with the lowest agenda usage and share best practices from top performers",
                        outcome="more consistent meeting quality across the org",
                    ),
                ))

        # ── o-p1: Daily meeting time trending down ────────────────────────────
        if prev_hrs > Decimal("0"):
            time_trend_daily = ((total_hrs - prev_hrs) / prev_hrs * 100).quantize(Decimal("0.1"))
            total_days = max(len({e.start_datetime.strftime("%Y-%m-%d") for e in all_events}), 1)
            avg_daily = (total_hrs / Decimal(str(total_days))).quantize(Decimal("0.1"))
            if time_trend_daily <= Decimal("-4"):
                insights.append(InsightDTO(
                    id="o-p1",
                    tab=InsightTab.organization,
                    status=InsightStatus.positive,
                    icon_type=InsightIconType.trending_down,
                    title="Daily meeting time is trending down",
                    data_signal=f"Avg. daily meeting time decreased {_fmt(abs(time_trend_daily))}% to {_fmt(avg_daily)}h.",
                    recommendation=InsightRecommendationDTO(
                        action="Identify what changed this period and reinforce it",
                        outcome="continued reduction in daily meeting load",
                    ),
                ))

        # ── o-p2: Mostly inside-team collab ───────────────────────────────────
        # Побудуємо map email → team_id
        team_members_stmt = (
            select(OrganizationTeamMember, User.email)
            .join(OrganizationMember, OrganizationTeamMember.organization_member_id == OrganizationMember.id)
            .join(User, OrganizationMember.user_id == User.id)
            .where(OrganizationMember.organization_id == org.id)
        )
        tm_result = await self.repo.session.execute(team_members_stmt)
        email_to_team: dict[str, uuid.UUID] = {
            email.lower(): row.team_id
            for row, email in tm_result.all()
        }

        inside_hrs = Decimal("0")
        cross_hrs = Decimal("0")
        ext_hrs = Decimal("0")
        org_emails = {s.email.lower() for s in stats}

        for e in all_events:
            hrs = AnalyticsCalculator.duration_hours(e)
            organizer_email = (e.organizer_email or "").lower()
            organizer_team = email_to_team.get(organizer_email)
            attendee_emails = {a.email.lower() for a in e.attendees if not a.resource}
            team_attendees = attendee_emails & org_emails
            ext_attendees = attendee_emails - org_emails

            if ext_attendees:
                ext_hrs += hrs
            elif organizer_team and all(
                email_to_team.get(em) == organizer_team for em in team_attendees if em != organizer_email
            ):
                inside_hrs += hrs
            else:
                cross_hrs += hrs

        total_collab = inside_hrs + cross_hrs + ext_hrs
        if total_collab > Decimal("0"):
            inside_pct = (inside_hrs / total_collab * 100).quantize(Decimal("0.1"))
            if inside_pct >= Decimal("50"):
                insights.append(InsightDTO(
                    id="o-p2",
                    tab=InsightTab.organization,
                    status=InsightStatus.positive,
                    icon_type=InsightIconType.collab,
                    title="Most collaboration happens inside teams, not across them",
                    data_signal=(
                        f"{_fmt(inside_pct)}% of meeting hours are inside-team vs "
                        f"{_fmt((cross_hrs / total_collab * 100).quantize(Decimal('0.1')))}% cross-team and "
                        f"{_fmt((ext_hrs / total_collab * 100).quantize(Decimal('0.1')))}% external."
                    ),
                    recommendation=InsightRecommendationDTO(
                        action="Maintain this ratio as a healthy baseline",
                        outcome="efficient internal alignment without excessive cross-team overhead",
                    ),
                ))

        # ── o-p3: 💰 Cost efficiency improving ────────────────────────────────
        if cost_active and prev_hrs > Decimal("0") and prev_cost > Decimal("0") and total_hrs > Decimal("0"):
            cost_per_hr_cur = (total_cost / total_hrs).quantize(Decimal("0.01"))
            cost_per_hr_prev = (prev_cost / prev_hrs).quantize(Decimal("0.01"))
            if cost_per_hr_cur < cost_per_hr_prev * Decimal("0.95"):
                insights.append(InsightDTO(
                    id="o-p3",
                    tab=InsightTab.organization,
                    status=InsightStatus.positive,
                    icon_type=InsightIconType.trending_down,
                    title="Meeting cost efficiency is improving",
                    data_signal=f"Cost per meeting hour dropped from ${cost_per_hr_prev} to ${cost_per_hr_cur} this period.",
                    recommendation=InsightRecommendationDTO(
                        action="Identify and document what drove the improvement",
                        outcome="sustained cost efficiency as the org grows",
                    ),
                ))

        # ── o-p4: Org-wide agenda adoption climbing ────────────────────────────
        if agenda_by_member:
            org_cur = (sum(p for _, p in agenda_by_member) / Decimal(str(len(agenda_by_member)))).quantize(Decimal("0.1"))
            prev_agenda: list[Decimal] = []
            for s in stats:
                if s.prev_events:
                    org_prev_org = [e for e in s.prev_events if (e.organizer_email or "").lower() == s.email.lower()]
                    if org_prev_org:
                        no_ag = [e for e in org_prev_org if not (e.description or "").strip()]
                        prev_agenda.append(Decimal("100") - Decimal(str(round(len(no_ag) / len(org_prev_org) * 100, 1))))
            if prev_agenda:
                org_prev = (sum(prev_agenda) / Decimal(str(len(prev_agenda)))).quantize(Decimal("0.1"))
                if org_cur > org_prev + Decimal("5"):
                    insights.append(InsightDTO(
                        id="o-p4",
                        tab=InsightTab.organization,
                        status=InsightStatus.positive,
                        icon_type=InsightIconType.trending_up,
                        title="Org-wide agenda adoption is climbing",
                        data_signal=f"Org-wide agenda usage rose from {_fmt(org_prev)}% to {_fmt(org_cur)}% this period.",
                        recommendation=InsightRecommendationDTO(
                            action="Highlight teams leading this shift in an internal update",
                            outcome="reinforces good meeting culture org-wide",
                        ),
                    ))

        return insights
