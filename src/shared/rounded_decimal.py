from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated, Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema


class _RoundedDecimalValidator:
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(cls._validate, handler(Decimal))

    @staticmethod
    def _validate(v: Decimal) -> Decimal:
        return v.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


RoundedDecimal = Annotated[Decimal, _RoundedDecimalValidator]
