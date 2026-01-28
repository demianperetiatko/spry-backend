from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from src.modules.enums import OrganizationCostPeriodEnum


COST_DECIMAL_PLACES = Decimal("0.01")
COST_ROUNDING = ROUND_HALF_UP
HOURLY_PRECISION = Decimal("0.000001")  # keep enough precision for reverse conversions


def round_money(value: Decimal) -> Decimal:
    return value.quantize(COST_DECIMAL_PLACES, rounding=COST_ROUNDING)


def calculate_hourly_cost(cost: Decimal, period: OrganizationCostPeriodEnum) -> Decimal:
    if period == OrganizationCostPeriodEnum.YEAR:
        hourly = cost / Decimal(54 * 40)
    elif period == OrganizationCostPeriodEnum.MONTH:
        hourly = cost / Decimal(4 * 40)
    elif period == OrganizationCostPeriodEnum.HOUR:
        hourly = cost
    else:
        raise ValueError(f"Unknown period: {period}")

    return hourly.quantize(HOURLY_PRECISION, rounding=COST_ROUNDING)


def calculate_total_cost(hourly_cost: Decimal, period: OrganizationCostPeriodEnum) -> Decimal:
    if period == OrganizationCostPeriodEnum.YEAR:
        result = hourly_cost * Decimal(54 * 40)
    elif period == OrganizationCostPeriodEnum.MONTH:
        result = hourly_cost * Decimal(4 * 40)
    elif period == OrganizationCostPeriodEnum.HOUR:
        result = hourly_cost
    else:
        raise ValueError(f"Unknown period: {period}")

    return round_money(result)
