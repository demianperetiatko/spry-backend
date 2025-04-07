from datetime import datetime

from utils.analytics.util import calculate_chance


def kpi_total_time(events: list) -> float:
    total_time = 0.0
    for event in events:
        if event.get("status") == "cancelled":
            continue
        start = event.get("start", {}).get("dateTime")
        end = event.get("end", {}).get("dateTime")
        if not start or not end:
            continue
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        total_time += (end_dt - start_dt).total_seconds() / 3600
    return total_time


def kpi_avg_daily_meetings_time(events: list, total_days: int) -> float:
    total_time = 0.0
    for event in events:
        if event.get("status") == "cancelled":
            continue
        start = event.get("start", {}).get("dateTime")
        end = event.get("end", {}).get("dateTime")
        if not start or not end:
            continue
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        total_time += (end_dt - start_dt).total_seconds() / 3600

    avg_daily_time = total_time / total_days
    return avg_daily_time


def kpi_cancelled_meetings(events: list) -> float:
    total_cancelled_meetings = 0
    for event in events:
        if event.get("status") == "cancelled":
            total_cancelled_meetings += 1
    return total_cancelled_meetings


def kpi_count_meetings(events: list) -> float:
    return len(events)


def kpi_meetings_ratio(events: list, total_days: int) -> float:
    total_time = 0.0
    for event in events:
        if event.get("status") == "cancelled":
            continue
        start = event.get("start", {}).get("dateTime")
        end = event.get("end", {}).get("dateTime")
        if not start or not end:
            continue
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        total_time += (end_dt - start_dt).total_seconds() / 3600

    avg_daily_time = total_time / (total_days * 8) * 100
    return avg_daily_time


def calculate_kpi_total_time(events: list, prev_events: list) -> dict:
    total_time = kpi_total_time(events)
    prev_total_time = kpi_total_time(prev_events)

    change = calculate_chance(total_time, prev_total_time)

    return {
        "name": "total_time",
        "title": "Total Time",
        "value": f"{round(total_time)}h",
        "change": f"{'+' if change > 0 else ''}{change}%",
        "positive": True
    }


def calculate_kpi_avg_daily_meetings_time(events: list, prev_events: list, count_work_day: int) -> dict:
    avg_daily_meetings_time = kpi_avg_daily_meetings_time(events, count_work_day)
    prev_avg_daily_meetings_time = kpi_avg_daily_meetings_time(prev_events, count_work_day)
    change = calculate_chance(avg_daily_meetings_time, prev_avg_daily_meetings_time)
    return {
        "name": "avg_daily_meetings_time",
        "title": "Avg. daily meetings time",
        "value": f"{round(avg_daily_meetings_time, 2)}h",
        "change": f"{'+' if change > 0 else ''}{change}%",
        "positive": True,
    }


def calculate_kpi_cancelled_meetings(events: list, prev_events: list) -> dict:
    cancelled_meetings = kpi_cancelled_meetings(events)
    prev_cancelled_meetings = kpi_cancelled_meetings(prev_events)
    change = calculate_chance(cancelled_meetings, prev_cancelled_meetings)
    return {
        "name": "meetings_count",
        "title": "Cancelled meetings",
        "value": f"{cancelled_meetings}",
        "change": f"{'+' if change > 0 else ''}{change}",
        "positive": True,
    }


def calculate_kpi_count_meetings(events: list, prev_events: list) -> dict:
    count_meetings = kpi_count_meetings(events)
    prev_count_meetings = kpi_count_meetings(prev_events)
    change = calculate_chance(count_meetings, prev_count_meetings)
    return {
        "name": "meetings_cost",
        "title": "Meetings count",
        "value": f"{count_meetings}",
        "change": f"{'+' if change > 0 else ''}{change}%",
        "positive": True,
    }


def calculate_kpi_meetings_ratio(events: list, prev_events: list, count_work_day: int) -> dict:
    meetings_ratio = kpi_meetings_ratio(events, count_work_day)
    prev_meetings_ratio = kpi_meetings_ratio(prev_events, count_work_day)
    change = calculate_chance(meetings_ratio, prev_meetings_ratio)
    return {
        "name": "meetings_ratio",
        "title": "Meetings ratio",
        "value": f"{round(meetings_ratio, 2)}%",
        "change": f"{'+' if change > 0 else ''}{change}%",
        "positive": True,
    }
