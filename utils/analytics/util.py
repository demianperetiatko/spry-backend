def calculate_chance(new, old):
    if old == 0:
        if new == 0:
            return 0
        elif new > 0:
            return 100
        else:
            return -100
    return round(((new - old) / old) * 100, 2)