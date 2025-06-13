from datetime import datetime

from utils.analytics.utils import calculate_chance
from utils.analytics.calendar_stats import calculate_total_events_duration, count_cancelled_events, count_events, \
    calculate_event_ratio, calculate_avg_daily_meetings_hour, calculate_total_events_cost, \
    count_events_without_description, \
    calculate_deep_work_time_events

from .constants import WORKDAY_HOURS


def kpi_total_time(events: list, prev_events: list) -> dict:
    total_time = calculate_total_events_duration(events)
    prev_total_time = calculate_total_events_duration(prev_events)

    change = calculate_chance(total_time, prev_total_time)

    return {
        "value": f"{round(total_time, 2)}h",
        "change": f"{'+' if change > 0 else ''}{change}%",
        "positive": False if change > 0 else True,
    }


def kpi_workday_events_total_time_percent(events: list, prev_events: list, count_work_days) -> dict:
    total_time = calculate_total_events_duration(events)
    prev_total_time = calculate_total_events_duration(prev_events)

    percent_of_day = round((total_time / (count_work_days * WORKDAY_HOURS)) * 100, 2)
    prev_percent_of_day = round((prev_total_time / (count_work_days * WORKDAY_HOURS)) * 100, 2)
    change = calculate_chance(percent_of_day, prev_percent_of_day)

    return {
        "value": percent_of_day,
        "change": f"{'+' if change > 0 else ''}{change}%",
        "positive": change >= 0
    }


def kpi_avg_daily_meetings_time(events: list, prev_events: list, count_work_day: int, count_people: int = 1) -> dict:
    avg_daily_meetings_time = calculate_avg_daily_meetings_hour(events, count_work_day * count_people)
    prev_avg_daily_meetings_time = calculate_avg_daily_meetings_hour(prev_events, count_work_day * count_people)
    change = calculate_chance(avg_daily_meetings_time, prev_avg_daily_meetings_time)
    return {
        "value": f"{round(avg_daily_meetings_time, 2)}h",
        "change": f"{'+' if change > 0 else ''}{change}%",
        "positive": False if change > 0 else True,
    }


def kpi_cancelled_meetings(events: list, prev_events: list) -> dict:
    cancelled_meetings = count_cancelled_events(events)
    prev_cancelled_meetings = count_cancelled_events(prev_events)
    change = calculate_chance(cancelled_meetings, prev_cancelled_meetings)
    return {
        "value": f"{cancelled_meetings}",
        "change": f"{'+' if change > 0 else ''}{change}",
        "positive": False if change > 0 else True,
    }


def kpi_count_meetings(events: list, prev_events: list) -> dict:
    count_meetings = count_events(events)
    prev_count_meetings = count_events(prev_events)
    change = calculate_chance(count_meetings, prev_count_meetings)
    return {
        "value": f"{count_meetings}",
        "change": f"{'+' if change > 0 else ''}{change}%",
        "positive": False if change > 0 else True,
    }


def kpi_meetings_ratio(events: list, prev_events: list, count_work_day: int, count_people: int = 1) -> dict:
    meetings_ratio = calculate_event_ratio(events, count_work_day * count_people)
    prev_meetings_ratio = calculate_event_ratio(prev_events, count_work_day * count_people)
    change = calculate_chance(meetings_ratio, prev_meetings_ratio)
    return {
        "value": f"{round(meetings_ratio, 2)}%",
        "change": f"{'+' if change > 0 else ''}{change}%",
        "positive": False if change > 0 else True,
    }


def kpi_total_cost(events: list, prev_events: list, members: list) -> dict:
    total_cost = calculate_total_events_cost(events, members)
    prev_total_cost = calculate_total_events_cost(prev_events, members)

    change = calculate_chance(total_cost, prev_total_cost)

    return {
        "value": f"{round(total_cost, 2)}",
        "change": f"{'+' if change > 0 else ''}{change}%",
        "positive": False if change > 0 else True
    }


def kpi_avg_daily_meetings_cost(events: list, prev_events: list, members: list) -> dict:
    total_cost = calculate_total_events_cost(events, members) / len(members)
    prev_total_cost = calculate_total_events_cost(prev_events, members) / len(members)

    change = calculate_chance(total_cost, prev_total_cost)

    return {
        "value": f"{round(total_cost, 2)}",
        "change": f"{'+' if change > 0 else ''}{change}%",
        "positive": False if change > 0 else True
    }


def kpi_without_description(events: list, prev_events: list) -> dict:
    total_without_description = count_events_without_description(events)
    prev_total_without_description = count_events_without_description(prev_events)

    change = calculate_chance(total_without_description, prev_total_without_description)

    return {
        "value": f"{round(total_without_description, 2)}",
        "change": f"{'+' if change > 0 else ''}{change}%",
        "positive": False if change > 0 else True
    }


def kpi_deep_work_time(events: list, prev_events: list) -> dict:
    total_work_time = calculate_deep_work_time_events(events)
    prev_total_work_time = calculate_deep_work_time_events(prev_events)

    change = calculate_chance(total_work_time, prev_total_work_time)
    return {
        "value": f"{round(total_work_time, 2)}",
        "change": f"{'+' if change > 0 else ''}{change}%",
        "positive": True if change > 0 else False
    }
