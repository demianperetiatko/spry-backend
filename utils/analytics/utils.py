from datetime import datetime, timedelta

def count_weekdays(start, end):
    count = 0
    current = start
    while current <= end:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return count


def calculate_chance(new, old):
    if old == 0:
        if new == 0:
            return 0
        elif new > 0:
            return 100
        else:
            return -100
    return round(((new - old) / old) * 100)