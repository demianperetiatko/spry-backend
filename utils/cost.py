from models import OrganizationCostPeriod

def calculate_hourly_cost(cost: float, period) -> float:
    if period == OrganizationCostPeriod.YEAR:
        return cost / (54 * 40)
    elif period == OrganizationCostPeriod.MONTH:
        return cost / (4 * 40)
    elif period == OrganizationCostPeriod.HOUR:
        return cost

def calculate_total_cost(hourly_cost: float, period) -> float:
    if period == OrganizationCostPeriod.YEAR:
        return hourly_cost * (54 * 40)
    elif period == OrganizationCostPeriod.MONTH:
        return hourly_cost * (4 * 40)
    elif period == OrganizationCostPeriod.HOUR:
        return hourly_cost
