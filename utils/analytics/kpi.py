from utils.analytics.calendar_stats import calculate_avg_daily_meetings_hour
from utils.analytics.calendar_stats import calculate_buffer_time
from utils.analytics.calendar_stats import calculate_event_ratio
from utils.analytics.calendar_stats import calculate_person_deep_work_time
from utils.analytics.calendar_stats import calculate_team_deep_work_time
from utils.analytics.calendar_stats import calculate_total_events_cost
from utils.analytics.calendar_stats import calculate_total_events_duration
from utils.analytics.calendar_stats import calculate_transition_time
from utils.analytics.calendar_stats import count_cancelled_events
from utils.analytics.calendar_stats import count_events
from utils.analytics.calendar_stats import count_events_without_description
from utils.analytics.utils import calculate_chance

from .constants import WORKDAY_HOURS


def kpi_total_time(events: list, prev_events: list) -> dict:
    total_time = calculate_total_events_duration(events)
    prev_total_time = calculate_total_events_duration(prev_events)

    change = calculate_chance(total_time, prev_total_time)
    return {
        "value": total_time,
        "change": f"{'+' if change >= 0 else ''}{change}%",
        "positive": False if change > 0 else True,
        "type_value": "time",
    }


def kpi_avg_daily_meetings_time(events: list, prev_events: list, count_work_day: int, count_people: int = 1) -> dict:
    avg_daily_meetings_time = calculate_avg_daily_meetings_hour(events, count_work_day * count_people)
    prev_avg_daily_meetings_time = calculate_avg_daily_meetings_hour(prev_events, count_work_day * count_people)
    change = calculate_chance(avg_daily_meetings_time, prev_avg_daily_meetings_time)
    return {
        "value": avg_daily_meetings_time,
        "change": f"{'+' if change >= 0 else ''}{change}%",
        "positive": False if change > 0 else True,
        "type_value": "time",
    }


def kpi_cancelled_meetings(events: list, prev_events: list, email: str) -> dict:
    cancelled_meetings = count_cancelled_events(events, email)
    prev_cancelled_meetings = count_cancelled_events(prev_events, email)
    change = calculate_chance(cancelled_meetings, prev_cancelled_meetings)
    return {
        "value": cancelled_meetings,
        "change": f"{'+' if change > 0 else ''}{change}%",
        "positive": False if change > 0 else True,
        "type_value": "count",
    }


def kpi_count_meetings(events: list, prev_events: list) -> dict:
    count_meetings = count_events(events)
    prev_count_meetings = count_events(prev_events)
    change = calculate_chance(count_meetings, prev_count_meetings)
    return {
        "value": count_meetings,
        "change": f"{'+' if change >= 0 else ''}{change}%",
        "positive": False if change > 0 else True,
        "type_value": "count",
    }


def kpi_meetings_ratio(events: list, prev_events: list, count_work_day: int, count_people: int = 1) -> dict:
    meetings_ratio = calculate_event_ratio(events, count_work_day * count_people)
    prev_meetings_ratio = calculate_event_ratio(prev_events, count_work_day * count_people)
    change = calculate_chance(meetings_ratio, prev_meetings_ratio)
    return {
        "value": meetings_ratio,
        "change": f"{'+' if change >= 0 else ''}{change}%",
        "positive": False if change > 0 else True,
        "type_value": "percent",
    }


def kpi_total_cost(events: list, prev_events: list, members: list, currency) -> dict:
    if currency:
        if len(members) == 0:
            return {
                "value": None,
                "change": None,
                "positive": None,
                "type_value": "currency",
            }

        total_cost = calculate_total_events_cost(events, members)
        prev_total_cost = calculate_total_events_cost(prev_events, members)

        change = calculate_chance(total_cost, prev_total_cost)

        return {
            "value": total_cost,
            "change": f"{'+' if change >= 0 else ''}{change}%",
            "positive": False if change > 0 else True,
            "type_value": "currency",
        }
    else:
        return {
            "value": None,
            "change": None,
            "positive": None,
            "type_value": "currency",
        }


def kpi_avg_daily_meetings_cost(events: list, prev_events: list, members: list, count_work_day, currency) -> dict:
    if currency:
        if len(members) == 0 or count_work_day == 0:
            return {
                "value": None,
                "change": None,
                "positive": None,
                "type_value": "currency",
            }

        total_cost = calculate_total_events_cost(events, members) / (len(members) * count_work_day)
        prev_total_cost = calculate_total_events_cost(prev_events, members) / (len(members) * count_work_day)

        change = calculate_chance(total_cost, prev_total_cost)

        return {
            "value": total_cost,
            "change": f"{'+' if change >= 0 else ''}{change}%",
            "positive": False if change > 0 else True,
            "type_value": "currency",
        }
    else:
        return {
            "value": None,
            "change": None,
            "positive": None,
            "type_value": "currency",
        }


def kpi_avg_member_meetings_cost(events: list, prev_events: list, members: list, currency) -> dict:
    if currency:
        total_cost = calculate_total_events_cost(events, members) / (len(members))
        prev_total_cost = calculate_total_events_cost(prev_events, members) / (len(members))

        change = calculate_chance(total_cost, prev_total_cost)

        return {
            "value": total_cost,
            "change": f"{'+' if change >= 0 else ''}{change}%",
            "positive": False if change > 0 else True,
            "type_value": "currency",
        }
    else:
        return {
            "value": None,
            "change": None,
            "positive": None,
            "type_value": "currency",
        }


def kpi_without_description(events: list, prev_events: list) -> dict:
    total_without_description = count_events_without_description(events)
    prev_total_without_description = count_events_without_description(prev_events)

    change = calculate_chance(total_without_description, prev_total_without_description)

    return {
        "value": total_without_description,
        "change": f"{'+' if change >= 0 else ''}{change}%",
        "positive": False if change > 0 else True,
        "type_value": "count",
    }


def kpi_deep_work_time(events: list, prev_events: list, count_work_day) -> dict:
    total_work_time = calculate_person_deep_work_time(events, count_work_day)
    prev_total_work_time = calculate_person_deep_work_time(prev_events, count_work_day)

    change = calculate_chance(total_work_time, prev_total_work_time)
    return {
        "value": total_work_time,
        "change": f"{'+' if change >= 0 else ''}{change}%",
        "positive": True if change > 0 else False,
        "type_value": "time",
    }


def _calculate_percentage_kpi(
    current_value: float,
    previous_value: float,
    total_work_hours: float,
    is_positive_change: bool = False,
) -> dict:
    current_percent = round((current_value / total_work_hours) * 100, 1) if total_work_hours > 0 else 0
    previous_percent = round((previous_value / total_work_hours) * 100, 1) if total_work_hours > 0 else 0

    change = calculate_chance(current_percent, previous_percent)

    return {
        "value": {
            "percent": current_percent,
            "hours": round(current_value, 1),
        },
        "change": f"{'+' if change >= 0 else ''}{change}%",
        "positive": is_positive_change if change > 0 else not is_positive_change,
        "type_value": "productivity",
    }


def kpi_person_total_time_percent(events: list, prev_events: list, count_work_day: int) -> dict:
    current_time = calculate_total_events_duration(events)
    previous_time = calculate_total_events_duration(prev_events)
    total_work_hours = count_work_day * WORKDAY_HOURS

    return _calculate_percentage_kpi(current_time, previous_time, total_work_hours, is_positive_change=False)


def kpi_person_deep_work_time_percent(events: list, prev_events: list, count_work_day: int) -> dict:
    current_time = calculate_person_deep_work_time(events, count_work_day)
    previous_time = calculate_person_deep_work_time(prev_events, count_work_day)
    total_work_hours = count_work_day * WORKDAY_HOURS

    return _calculate_percentage_kpi(current_time, previous_time, total_work_hours, is_positive_change=True)


def kpi_person_buffers_time_percent(events: list, prev_events: list, count_work_day: int) -> dict:
    current_time = calculate_buffer_time(events)
    previous_time = calculate_buffer_time(prev_events)
    total_work_hours = count_work_day * WORKDAY_HOURS

    return _calculate_percentage_kpi(current_time, previous_time, total_work_hours, is_positive_change=False)


def kpi_person_transition_time_percent(events: list, prev_events: list, count_work_day: int) -> dict:
    current_time = calculate_transition_time(events)
    previous_time = calculate_transition_time(prev_events)
    total_work_hours = count_work_day * WORKDAY_HOURS

    return _calculate_percentage_kpi(current_time, previous_time, total_work_hours, is_positive_change=False)


def kpi_team_total_time_percent(events: list, prev_events: list, count_work_day: int, team_members_count: int) -> dict:
    current_time = calculate_total_events_duration(events)
    previous_time = calculate_total_events_duration(prev_events)
    total_work_hours = count_work_day * WORKDAY_HOURS * team_members_count

    return _calculate_percentage_kpi(current_time, previous_time, total_work_hours, is_positive_change=False)


def kpi_team_deep_work_time_percent(events: list, prev_events: list, count_work_day: int, team_members_count: int) -> dict:
    current_time = calculate_team_deep_work_time(events, count_work_day, team_members_count)
    previous_time = calculate_team_deep_work_time(prev_events, count_work_day, team_members_count)
    total_work_hours = count_work_day * WORKDAY_HOURS * team_members_count

    return _calculate_percentage_kpi(current_time, previous_time, total_work_hours, is_positive_change=True)


def kpi_team_buffers_time_percent(events: list, prev_events: list, count_work_day: int, team_members_count: int) -> dict:
    current_time = calculate_buffer_time(events)
    previous_time = calculate_buffer_time(prev_events)
    total_work_hours = count_work_day * WORKDAY_HOURS * team_members_count

    return _calculate_percentage_kpi(current_time, previous_time, total_work_hours, is_positive_change=False)


def kpi_team_transition_time_percent(events: list, prev_events: list, count_work_day: int, team_members_count: int) -> dict:
    current_time = calculate_transition_time(events)
    previous_time = calculate_transition_time(prev_events)
    total_work_hours = count_work_day * WORKDAY_HOURS * team_members_count

    return _calculate_percentage_kpi(current_time, previous_time, total_work_hours, is_positive_change=False)
