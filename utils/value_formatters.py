def float_to_hours_str(value: float) -> str:
    return f"{round(value, 1)}h"


def float_to_percent_str(value: float) -> str:
    return f"{round(value)}%"


def float_to_money_str(value: float, currency: str = "USD") -> str:
    symbol_to_code = {
        "USD": "$",
        "EUR": "€",
    }
    currency_code = symbol_to_code.get(currency, currency)
    rounded = round(value)
    formatted = f"{rounded:,}".replace(",", " ")
    return f"{formatted} {currency_code}"


def float_to_quantity_str(value: float) -> str:
    return f"{value}"
