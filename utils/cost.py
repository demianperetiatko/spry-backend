from models import OrganizationCostPeriodEnum

def calculate_hourly_cost(cost: float, period) -> float:
    if period == OrganizationCostPeriodEnum.year:
        return cost / (54 * 40)
    elif period == OrganizationCostPeriodEnum.month:
        return cost / (4 * 40)
    elif period == OrganizationCostPeriodEnum.hour:
        return cost

def calculate_total_cost(hourly_cost: float, period) -> float:
    if period == OrganizationCostPeriodEnum.year:
        return hourly_cost * (54 * 40)
    elif period == OrganizationCostPeriodEnum.month:
        return hourly_cost * (4 * 40)
    elif period == OrganizationCostPeriodEnum.hour:
        return hourly_cost
