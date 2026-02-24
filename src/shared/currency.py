from __future__ import annotations

from typing import Any

import pycountry
from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema
from sqlalchemy import String, TypeDecorator

_all_currencies = {currency.alpha_3 for currency in pycountry.currencies}
_instances: dict[str, Currency] = {}


class Currency:
    __slots__ = ["_code"]

    def __new__(cls, code: str) -> Currency:
        if code not in _instances:
            _instances[code] = super().__new__(cls)
        return _instances[code]

    def __init__(self, code: str) -> None:
        if code not in _all_currencies:
            raise ValueError(f"Invalid currency code: {code}")
        self._code = code

    def __deepcopy__(self, memo: dict) -> Currency:
        return self

    def __str__(self) -> str:
        return self._code

    def __repr__(self) -> str:
        return f"Currency({self._code})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Currency):
            return False
        return self._code == other._code

    def __hash__(self) -> int:
        return hash(self._code)

    @property
    def code(self) -> str:
        return self._code

    @classmethod
    def all(cls) -> list[Currency]:
        return [Currency(code) for code in sorted(_all_currencies)]

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        def to_currency(value: Any) -> Currency:
            if isinstance(value, Currency):
                return value
            if isinstance(value, str):
                return cls(value)
            raise ValueError(f"Expected Currency or str, got {type(value)}")

        def to_str(value: Currency) -> str:
            return value.code

        from_str_schema = core_schema.no_info_after_validator_function(to_currency, core_schema.str_schema())
        from_currency_schema = core_schema.is_instance_schema(Currency)

        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.union_schema(
                [
                    from_currency_schema,
                    from_str_schema,
                ],
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(to_str),
        )


class CurrencyType(TypeDecorator[Currency]):
    impl = String(3)
    cache_ok = True

    def process_bind_param(self, value: Currency | str | None, dialect: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, Currency):
            return value.code
        return str(value)

    def process_result_value(self, value: str | None, dialect: Any) -> Currency | None:
        if value is None:
            return None
        return Currency(value)
