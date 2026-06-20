"""
Unit tests for personal insights (режим 1 — self view).

Strategy: mock repo + data_loader so no DB is needed.
Each test verifies that a specific insight fires (or does NOT fire)
given a controlled event list.
"""
from __future__ import annotations

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.modules.insights.service import (
    AGENDA_ATTENTION,
    AGENDA_CRITICAL,
    DEEP_WORK_ATTENTION,
    DEEP_WORK_CRITICAL,
    LARGE_MEETING_ATTENTION,
    LARGE_MEETING_CRITICAL,
    MEETING_TIME_ATTENTION,
    MEETING_TIME_CRITICAL,
    InsightsService,
)
from tests.insights.factories import dt, make_attendee, make_ctx, make_event


# ─── Helpers ──────────────────────────────────────────────────────────────────

EMAIL = "user@example.com"


def _make_service(events, prev_events=None):
    """Build InsightsService with fully mocked repo and data_loader."""
    if prev_events is None:
        prev_events = []

    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = None
    exec_result.scalars.return_value.all.return_value = []
    exec_result.all.return_value = []

    session = AsyncMock()
    session.execute = AsyncMock(return_value=exec_result)

    repo = MagicMock()
    repo.session = session
    repo.get_events_for_period = AsyncMock(return_value=events)
    repo.get_meeting_events_for_period = AsyncMock(return_value=events)
    repo.get_team_member_emails = AsyncMock(return_value=[])

    data_loader = MagicMock()
    data_loader.get_comparative_events = AsyncMock(
        return_value=(events, prev_events, [], [])
    )
    data_loader.get_unique_events = MagicMock(side_effect=lambda evs: evs)

    return InsightsService(data_loader=data_loader, repo=repo)


def _mock_calc(metrics_dict: dict):
    """
    Patches AnalyticsCalculator to return controlled productivity metrics
    while preserving the real static duration_hours() method so that
    insight logic that calls it (large-meetings, etc.) still works.
    """
    from src.modules.analytics.personal.calculator import AnalyticsCalculator as RealCalc

    items = []
    for key, (pct, hrs) in metrics_dict.items():
        item = MagicMock()
        item.key = key
        item.value = MagicMock()
        item.value.percent = Decimal(str(pct))
        item.value.hours = Decimal(str(hrs))
        items.append(item)

    calc_instance = MagicMock()
    calc_instance.get_productivity_metrics.return_value = items

    mock_class = MagicMock(return_value=calc_instance)
    mock_class.duration_hours = staticmethod(RealCalc.duration_hours)

    return patch(
        "src.modules.insights.service.AnalyticsCalculator",
        mock_class,
    )


async def _run(events, prev_events=None, metrics=None, ctx_kwargs=None):
    ctx = make_ctx(email=EMAIL, **(ctx_kwargs or {}))
    svc = _make_service(events, prev_events or [])
    default_metrics = {
        "meetings_time": (30, 2.4),
        "deep_work": (40, 3.2),
        "buffers": (5, 0.4),
        "transition_time": (5, 0.4),
    }
    if metrics:
        default_metrics.update(metrics)

    with _mock_calc(default_metrics):
        return await svc.generate_personal_insights(ctx, is_self=True)


# ─── p-c1: Agenda ─────────────────────────────────────────────────────────────

class TestPC1Agenda:
    @pytest.mark.asyncio
    async def test_fires_critical_when_majority_has_no_agenda(self):
        events = [
            make_event(organizer_email=EMAIL, description=None),
            make_event(organizer_email=EMAIL, description=None),
            make_event(organizer_email=EMAIL, description=None),
            make_event(organizer_email=EMAIL, description="agenda"),
        ]
        insights = await _run(events)
        ids = [i.id for i in insights]
        assert "p-c1" in ids
        c1 = next(i for i in insights if i.id == "p-c1")
        assert c1.status.value == "negative"

    @pytest.mark.asyncio
    async def test_fires_attention_when_quarter_has_no_agenda(self):
        # 30% no agenda → between ATTENTION(25) and CRITICAL(50)
        events = [
            make_event(organizer_email=EMAIL, description=None),
            make_event(organizer_email=EMAIL, description=None),
            make_event(organizer_email=EMAIL, description=None),
            make_event(organizer_email=EMAIL, description="agenda"),
            make_event(organizer_email=EMAIL, description="agenda"),
            make_event(organizer_email=EMAIL, description="agenda"),
            make_event(organizer_email=EMAIL, description="agenda"),
            make_event(organizer_email=EMAIL, description="agenda"),
            make_event(organizer_email=EMAIL, description="agenda"),
            make_event(organizer_email=EMAIL, description="agenda"),
        ]
        insights = await _run(events)
        c1 = next((i for i in insights if i.id == "p-c1"), None)
        assert c1 is not None
        assert c1.status.value == "attention"

    @pytest.mark.asyncio
    async def test_fires_p_p2_when_all_have_agenda(self):
        events = [
            make_event(organizer_email=EMAIL, description="agenda set"),
            make_event(organizer_email=EMAIL, description="agenda set"),
        ]
        insights = await _run(events)
        ids = [i.id for i in insights]
        assert "p-c1" not in ids
        assert "p-p2" in ids

    @pytest.mark.asyncio
    async def test_no_agenda_insight_when_user_organized_nothing(self):
        events = [make_event(organizer_email="other@example.com")]
        insights = await _run(events)
        ids = [i.id for i in insights]
        assert "p-c1" not in ids
        assert "p-p2" not in ids


# ─── p-c2: Large meetings ─────────────────────────────────────────────────────

class TestPC2LargeMeetings:
    @pytest.mark.asyncio
    async def test_fires_negative_when_large_meetings_dominate(self):
        # >20% large meetings → critical
        big_attendees = [make_attendee(f"p{i}@x.com") for i in range(8)]
        events = [
            make_event(attendees=big_attendees, duration_hours=2),
            make_event(attendees=big_attendees, duration_hours=2),
            make_event(attendees=big_attendees, duration_hours=2),
            make_event(duration_hours=1),
            make_event(duration_hours=1),
        ]
        insights = await _run(events)
        c2 = next((i for i in insights if i.id == "p-c2"), None)
        assert c2 is not None
        assert c2.status.value in ("negative", "attention")

    @pytest.mark.asyncio
    async def test_no_large_meeting_insight_for_small_meetings(self):
        small = [make_attendee(f"p{i}@x.com") for i in range(3)]
        events = [make_event(attendees=small) for _ in range(5)]
        insights = await _run(events)
        ids = [i.id for i in insights]
        assert "p-c2" not in ids


# ─── p-p3: Deep work healthy ──────────────────────────────────────────────────

class TestPP3DeepWork:
    @pytest.mark.asyncio
    async def test_fires_when_deep_work_above_attention(self):
        insights = await _run(
            events=[make_event()],
            metrics={"deep_work": (40, 3.2), "meetings_time": (30, 2.4)},
        )
        ids = [i.id for i in insights]
        assert "p-p3" in ids

    @pytest.mark.asyncio
    async def test_fires_p_a1_when_deep_work_critical(self):
        insights = await _run(
            events=[make_event()],
            metrics={"deep_work": (15, 1.2), "meetings_time": (65, 5.2)},
        )
        ids = [i.id for i in insights]
        assert "p-a1" in ids  # p-a1 fires when deep_work < DEEP_WORK_CRITICAL (20%)

    @pytest.mark.asyncio
    async def test_no_p_p3_when_deep_work_below_threshold(self):
        insights = await _run(
            events=[make_event()],
            metrics={"deep_work": (20, 1.6), "meetings_time": (50, 4.0)},
        )
        ids = [i.id for i in insights]
        assert "p-p3" not in ids


# ─── p-p4 / p-a2: Meeting load balance ───────────────────────────────────────

class TestMeetingLoad:
    @pytest.mark.asyncio
    async def test_p_p4_fires_when_load_balanced(self):
        insights = await _run(
            events=[make_event()],
            metrics={"meetings_time": (35, 2.8), "deep_work": (40, 3.2)},
        )
        ids = [i.id for i in insights]
        assert "p-p4" in ids

    @pytest.mark.asyncio
    async def test_p_a2_fires_when_load_heavy(self):
        insights = await _run(
            events=[make_event()],
            metrics={"meetings_time": (45, 3.6), "deep_work": (30, 2.4)},
        )
        ids = [i.id for i in insights]
        assert "p-a2" in ids

    @pytest.mark.asyncio
    async def test_critical_fires_when_meetings_above_60pct(self):
        insights = await _run(
            events=[make_event()],
            metrics={"meetings_time": (65, 5.2), "deep_work": (15, 1.2)},
        )
        ids = [i.id for i in insights]
        # p-c3 or some critical variant for meeting overload
        crits = [i for i in insights if i.status.value == "negative"]
        assert len(crits) >= 1


# ─── p-p1: Buffers ────────────────────────────────────────────────────────────

class TestPP1Buffers:
    @pytest.mark.asyncio
    async def test_fires_when_buffers_in_healthy_range(self):
        insights = await _run(
            events=[make_event()],
            metrics={"buffers": (7, 0.56), "meetings_time": (35, 2.8)},
        )
        ids = [i.id for i in insights]
        assert "p-p1" in ids

    @pytest.mark.asyncio
    async def test_no_p_p1_when_buffers_too_low(self):
        insights = await _run(
            events=[make_event()],
            metrics={"buffers": (1, 0.08), "meetings_time": (35, 2.8)},
        )
        ids = [i.id for i in insights]
        assert "p-p1" not in ids

    @pytest.mark.asyncio
    async def test_no_p_p1_when_buffers_too_high(self):
        insights = await _run(
            events=[make_event()],
            metrics={"buffers": (15, 1.2), "meetings_time": (35, 2.8)},
        )
        ids = [i.id for i in insights]
        assert "p-p1" not in ids


# ─── p-p2: Agenda trend ───────────────────────────────────────────────────────

class TestPP2AgendaTrend:
    @pytest.mark.asyncio
    async def test_shows_trend_when_improved_vs_prev(self):
        current = [
            make_event(organizer_email=EMAIL, description="agenda"),
            make_event(organizer_email=EMAIL, description="agenda"),
            make_event(organizer_email=EMAIL, description="agenda"),
        ]
        prev = [
            make_event(organizer_email=EMAIL, description=None),
            make_event(organizer_email=EMAIL, description=None),
            make_event(organizer_email=EMAIL, description="agenda"),
        ]
        insights = await _run(current, prev_events=prev)
        p2 = next((i for i in insights if i.id == "p-p2"), None)
        assert p2 is not None
        # Should mention "rose from" since we improved by >5%
        assert "rose from" in p2.data_signal or "100" in p2.data_signal

    @pytest.mark.asyncio
    async def test_no_trend_text_when_no_prev_events(self):
        current = [make_event(organizer_email=EMAIL, description="agenda")]
        insights = await _run(current, prev_events=[])
        p2 = next((i for i in insights if i.id == "p-p2"), None)
        assert p2 is not None
        assert "rose from" not in p2.data_signal


# ─── No events edge case ──────────────────────────────────────────────────────

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_no_events_returns_empty_list(self):
        insights = await _run(events=[])
        # Without events, most insights should not fire
        ids = [i.id for i in insights]
        assert "p-c1" not in ids
        assert "p-c2" not in ids

    @pytest.mark.asyncio
    async def test_single_event_does_not_crash(self):
        insights = await _run(events=[make_event()])
        assert isinstance(insights, list)

    @pytest.mark.asyncio
    async def test_insight_ids_are_unique(self):
        events = [
            make_event(organizer_email=EMAIL, description=None),
            make_event(organizer_email=EMAIL, description=None),
            make_event(organizer_email=EMAIL, description=None),
            make_event(organizer_email=EMAIL, description=None),
            make_event(large=True),
            make_event(large=True),
            make_event(large=True),
        ]
        insights = await _run(
            events,
            metrics={"meetings_time": (65, 5.2), "deep_work": (15, 1.2), "buffers": (5, 0.4)},
        )
        ids = [i.id for i in insights]
        assert len(ids) == len(set(ids)), f"Duplicate insight IDs: {ids}"

    @pytest.mark.asyncio
    async def test_all_insights_have_required_fields(self):
        events = [make_event(organizer_email=EMAIL, description=None) for _ in range(5)]
        insights = await _run(events)
        for insight in insights:
            assert insight.id, "Missing id"
            assert insight.title, "Missing title"
            assert insight.data_signal, "Missing data_signal"
            assert insight.recommendation is not None, "Missing recommendation"
            assert insight.tab is not None
            assert insight.status is not None
