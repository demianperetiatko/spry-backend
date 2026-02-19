from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated

from pydantic import AfterValidator, PlainSerializer


def _round_1dp(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


RoundedDecimal = Annotated[
    Decimal,
    AfterValidator(_round_1dp),
    PlainSerializer(float, return_type=float, when_used="always"),
]
