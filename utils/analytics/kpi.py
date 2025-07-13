from datetime import datetime

from utils.analytics.utils import calculate_chance
from utils.analytics.calendar_stats import calculate_total_events_duration, count_cancelled_events, count_events, \
    calculate_event_ratio, calculate_avg_daily_meetings_hour, calculate_total_events_cost, \
    count_events_without_description, \
    calculate_deep_work_time

from utils.value_formatters import float_to_hours_str, float_to_percent_str, float_to_money_str, float_to_quantity_str


def kpi_total_time(events: list, prev_events: list) -> dict:
    total_time = calculate_total_events_duration(events)
    prev_total_time = calculate_total_events_duration(prev_events)

    change = calculate_chance(total_time, prev_total_time)

    return {
        "value": float_to_hours_str(total_time),
        "change": f"{'+' if change >= 0 else ''}{change}%",
        "positive": False if change > 0 else True,
    }


def kpi_avg_daily_meetings_time(events: list, prev_events: list, count_work_day: int, count_people: int = 1) -> dict:
    avg_daily_meetings_time = calculate_avg_daily_meetings_hour(events, count_work_day * count_people)
    prev_avg_daily_meetings_time = calculate_avg_daily_meetings_hour(prev_events, count_work_day * count_people)
    change = calculate_chance(avg_daily_meetings_time, prev_avg_daily_meetings_time)
    return {
        "value": float_to_hours_str(avg_daily_meetings_time),
        "change": f"{'+' if change >= 0 else ''}{change}%",
        "positive": False if change > 0 else True,
    }


def kpi_cancelled_meetings(events: list, prev_events: list, email: str) -> dict:
    cancelled_meetings = count_cancelled_events(events, email)
    prev_cancelled_meetings = count_cancelled_events(prev_events, email)
    change = calculate_chance(cancelled_meetings, prev_cancelled_meetings)
    return {
        "value": float_to_quantity_str(cancelled_meetings),
        "change": f"{'+' if change > 0 else ''}{change}%",
        "positive": False if change > 0 else True,
    }


def kpi_count_meetings(events: list, prev_events: list) -> dict:
    count_meetings = count_events(events)
    prev_count_meetings = count_events(prev_events)
    change = calculate_chance(count_meetings, prev_count_meetings)
    return {
        "value": float_to_quantity_str(count_meetings),
        "change": f"{'+' if change >= 0 else ''}{change}%",
        "positive": False if change > 0 else True,
    }


def kpi_meetings_ratio(events: list, prev_events: list, count_work_day: int, count_people: int = 1) -> dict:
    meetings_ratio = calculate_event_ratio(events, count_work_day * count_people)
    prev_meetings_ratio = calculate_event_ratio(prev_events, count_work_day * count_people)
    change = calculate_chance(meetings_ratio, prev_meetings_ratio)
    return {
        "value": float_to_percent_str(meetings_ratio),
        "change": f"{'+' if change >= 0 else ''}{change}%",
        "positive": False if change > 0 else True,
    }


def get_currency_symbol(currency: str) -> str:
    return {
        "USD": "$",
        "EUR": "€"
    }.get(currency.upper(), "")


def kpi_total_cost(events: list, prev_events: list, members: list, currency) -> dict:
    if currency:
        total_cost = calculate_total_events_cost(events, members)
        prev_total_cost = calculate_total_events_cost(prev_events, members)

        change = calculate_chance(total_cost, prev_total_cost)

        return {
            "value": float_to_money_str(total_cost, currency),
            "change": f"{'+' if change >= 0 else ''}{change}%",
            "positive": False if change > 0 else True
        }
    else:
        return {
            "value": None,
            "change": None,
            "positive": None
        }


def kpi_avg_daily_meetings_cost(events: list, prev_events: list, members: list, currency) -> dict:
    if currency:
        total_cost = calculate_total_events_cost(events, members) / len(members)
        prev_total_cost = calculate_total_events_cost(prev_events, members) / len(members)

        change = calculate_chance(total_cost, prev_total_cost)

        return {
            "value": float_to_money_str(total_cost, currency),
            "change": f"{'+' if change >= 0 else ''}{change}%",
            "positive": False if change > 0 else True
        }
    else:
        return {
            "value": None,
            "change": None,
            "positive": None
        }


def kpi_without_description(events: list, prev_events: list) -> dict:
    total_without_description = count_events_without_description(events)
    prev_total_without_description = count_events_without_description(prev_events)

    change = calculate_chance(total_without_description, prev_total_without_description)

    return {
        "value": float_to_quantity_str(total_without_description),
        "change": f"{'+' if change >= 0 else ''}{change}%",
        "positive": False if change > 0 else True
    }


def kpi_deep_work_time(events: list, prev_events: list, count_work_day) -> dict:
    total_work_time = calculate_deep_work_time(events, count_work_day)
    prev_total_work_time = calculate_deep_work_time(prev_events, count_work_day)

    change = calculate_chance(total_work_time, prev_total_work_time)
    return {
        "value": float_to_hours_str(total_work_time),
        "change": f"{'+' if change >= 0 else ''}{change}%",
        "positive": True if change > 0 else False
    }
