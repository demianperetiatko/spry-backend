from models import OrganizationCostPeriodEnum

def calculate_hourly_cost(cost: float, period) -> float:
    if period == OrganizationCostPeriodEnum.YEAR:
        return cost / (54 * 40)
    elif period == OrganizationCostPeriodEnum.MONTH:
        return cost / (4 * 40)
    elif period == OrganizationCostPeriodEnum.HOUR:
        return cost

def calculate_total_cost(hourly_cost: float, period) -> float:
    if period == OrganizationCostPeriodEnum.YEAR:
        return hourly_cost * (54 * 40)
    elif period == OrganizationCostPeriodEnum.MONTH:
        return hourly_cost * (4 * 40)
    elif period == OrganizationCostPeriodEnum.HOUR:
        return hourly_cost
