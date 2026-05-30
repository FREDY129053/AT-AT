from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from email.utils import parseaddr
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from jsonpath_ng.ext import parse as jsonpath_parse  # type: ignore
from schemathesis.core.transport import Response

from api_agent.schemas import (
    ArrayCheck,
    Check,
    DateRangeCheck,
    DependencyCheck,
    ExclusiveFieldsCheck,
    ExistsCheck,
    ExternalStepCheck,
    FieldCompareCheck,
    LogicalCheck,
    NumberCheck,
    ObjectCheck,
    OneRequiredCheck,
    StatusCodeCheck,
    StringCheck,
    TypeCheck,
    ValueEqualsCheck,
)


# ============================================================
# Exceptions
# ============================================================
@dataclass(slots=True)
class CheckValidationError(Exception):
    message: str
    kind: str | None = None
    path: str | None = None
    actual: Any = None
    expected: Any = None

    def __str__(self) -> str:
        parts: list[str] = [self.message]

        meta: list[str] = []

        if self.kind is not None:
            meta.append(f"kind={self.kind}")

        if self.path is not None:
            meta.append(f"path={self.path}")

        if self.expected is not None:
            meta.append(f"expected={self.expected!r}")

        if self.actual is not None:
            meta.append(f"actual={self.actual!r}")

        if meta:
            parts.append(f"({' | '.join(meta)})")

        return " ".join(parts)


class JsonPathResolutionError(CheckValidationError):
    pass


# ============================================================
# Internal sentinels
# ============================================================
class _Missing:
    __slots__ = ()

    def __repr__(self) -> str:
        return "<MISSING>"


MISSING = _Missing()


# ============================================================
# JSON type helpers
# ============================================================
def _json_type(value: Any) -> str:
    if value is None:
        return "null"

    if isinstance(value, bool):
        return "boolean"

    if isinstance(value, int):
        return "integer"

    if isinstance(value, float):
        return "number"

    if isinstance(value, str):
        return "string"

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return "array"

    if isinstance(value, Mapping):
        return "object"

    return type(value).__name__


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)


def _to_decimal(value: int | float | Decimal) -> Decimal:
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"Невозможно преобразовать {value!r} в Decimal.") from exc


# ============================================================
# JSONPath
# ============================================================
_JSONPATH_CACHE: dict[str, Any] = {}


def _compile_jsonpath(path: str):
    cached = _JSONPATH_CACHE.get(path)

    if cached is not None:
        return cached

    try:
        compiled = jsonpath_parse(path)
    except Exception as exc:
        raise ValueError(f"Некорректный JSONPath: {path!r}") from exc

    _JSONPATH_CACHE[path] = compiled
    return compiled


def _resolve_path(
    response: Any,
    path: str,
    *,
    kind: str | None = None,
    allow_missing: bool = False,
) -> Any:
    """
    Поведение:
    - если матчей нет -> MISSING / exception
    - если матч один -> value
    - если матчей несколько -> list
    """
    compiled = _compile_jsonpath(path)

    try:
        matches = compiled.find(response)
    except Exception as exc:
        raise JsonPathResolutionError(
            f"Ошибка обработки JSONPath {path!r}",
            kind=kind,
            path=path,
        ) from exc

    if not matches:
        if allow_missing:
            return MISSING

        raise JsonPathResolutionError(
            f"Путь {path!r} не найден.",
            kind=kind,
            path=path,
        )

    values = [m.value for m in matches]

    if len(values) == 1:
        return values[0]

    return values


def _path_exists(payload: Any, path: str) -> bool:
    return (
        _resolve_path(
            payload,
            path,
            allow_missing=True,
        )
        is not MISSING
    )


# ============================================================
# String formats
# ============================================================


def _validate_string_format(value: str, fmt: str) -> bool:
    if fmt == "email":
        _, addr = parseaddr(value)
        return "@" in addr

    if fmt == "uri":
        parsed = urlparse(value)
        return bool(parsed.scheme and parsed.netloc)

    if fmt == "uuid":
        try:
            UUID(value)
            return True
        except Exception:
            return False

    if fmt == "date":
        try:
            date.fromisoformat(value)
            return True
        except Exception:
            return False

    if fmt == "time":
        try:
            time.fromisoformat(value)
            return True
        except Exception:
            return False

    if fmt == "date-time":
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return True
        except Exception:
            return False

    raise ValueError(f"Неизвестный string format: {fmt!r}")


# ============================================================
# Compare ops
# ============================================================
_COMPARE_OPS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
}


def _compare(left: Any, op: str, right: Any) -> bool:
    try:
        return _COMPARE_OPS[op](left, right)
    except Exception as exc:
        raise CheckValidationError(
            f"Невозможно сравнить значения оператором {op!r}.",
            actual=left,
            expected=right,
        ) from exc


# ============================================================
# Datetime parsing
# ============================================================
def _parse_datetime_like(
    value: str,
    *,
    payload: Any,
    now: datetime,
) -> datetime:
    """
    Поддерживает:
    - now
    - ISO datetime
    - ISO date
    - JSONPath
    """

    if value == "now":
        return now

    if value.startswith("$"):
        resolved = _resolve_path(payload, value)

        if not isinstance(resolved, str):
            raise CheckValidationError(
                "JSONPath для даты должен указывать на строку.",
                path=value,
                actual=resolved,
            )

        value = resolved

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        pass

    try:
        d = date.fromisoformat(value)
        return datetime.combine(d, time.min, tzinfo=timezone.utc)
    except Exception as exc:
        raise CheckValidationError(
            "Некорректная дата/время.",
            actual=value,
        ) from exc


# ============================================================
# Public API
# ============================================================
def validate_check(
    response: Response,
    check: "Check",
    *,
    external_step: Any = None,
    context: dict,
    now: datetime | None = None,
) -> None:
    """
    Public wrapper.

    now фиксируется один раз для всей цепочки.
    """

    if now is None:
        now = datetime.now(tz=timezone.utc)

    _validate_check(
        response=response,
        check=check,
        external_step=external_step,
        context=context,
        now=now,
    )


# ============================================================
# Main validator
# ============================================================
def _validate_check(
    response: Response | Mapping,
    check: Check,
    *,
    external_step: Any = None,
    context: dict,
    now: datetime,
) -> None:
    payload = response.json() if isinstance(response, Response) else response

    match check:
        # ========================================================
        # ExistsCheck
        # ========================================================
        case ExistsCheck():
            if not _path_exists(payload, check.path):
                raise CheckValidationError(
                    f"Путь {check.path!r} отсутствует.",
                    kind=check.kind,
                    path=check.path,
                )

            return

        # ========================================================
        # ValueEqualsCheck
        # ========================================================
        case ValueEqualsCheck():
            actual = _resolve_path(payload, check.path, kind=check.kind)
            expected = check.expected

            if (
                check.case_insensitive
                and isinstance(actual, str)
                and isinstance(expected, str)
            ):
                ok = actual.casefold() == expected.casefold()
            else:
                ok = actual == expected

            if not ok:
                raise CheckValidationError(
                    "Значение не равно expected.",
                    kind=check.kind,
                    path=check.path,
                    actual=actual,
                    expected=expected,
                )

            return

        # ========================================================
        # TypeCheck
        # ========================================================
        case TypeCheck():
            actual = _resolve_path(payload, check.path, kind=check.kind)
            actual_type = _json_type(actual)

            if actual_type not in check.type:
                raise CheckValidationError(
                    "Тип значения не совпадает.",
                    kind=check.kind,
                    path=check.path,
                    actual=actual_type,
                    expected=check.type,
                )

            return

        # ========================================================
        # StringCheck
        # ========================================================
        case StringCheck():
            actual = _resolve_path(payload, check.path, kind=check.kind)

            if not isinstance(actual, str):
                raise CheckValidationError(
                    "Значение должно быть строкой.",
                    kind=check.kind,
                    path=check.path,
                    actual=type(actual).__name__,
                    expected="string",
                )

            if check.min_length is not None and len(actual) < check.min_length:
                raise CheckValidationError(
                    "Строка короче min_length.",
                    kind=check.kind,
                    path=check.path,
                    actual=len(actual),
                    expected=check.min_length,
                )

            if check.max_length is not None and len(actual) > check.max_length:
                raise CheckValidationError(
                    "Строка длиннее max_length.",
                    kind=check.kind,
                    path=check.path,
                    actual=len(actual),
                    expected=check.max_length,
                )

            if check.pattern is not None:
                if re.search(check.pattern, actual) is None:
                    raise CheckValidationError(
                        "Строка не соответствует pattern.",
                        kind=check.kind,
                        path=check.path,
                        actual=actual,
                        expected=check.pattern,
                    )

            if check.format is not None:
                if not _validate_string_format(actual, check.format):
                    raise CheckValidationError(
                        "Строка не соответствует формату.",
                        kind=check.kind,
                        path=check.path,
                        actual=actual,
                        expected=check.format,
                    )

            return

        # ========================================================
        # NumberCheck
        # ========================================================
        case NumberCheck():
            actual = _resolve_path(payload, check.path, kind=check.kind)

            if not _is_number(actual):
                raise CheckValidationError(
                    "Значение должно быть числом.",
                    kind=check.kind,
                    path=check.path,
                    actual=type(actual).__name__,
                    expected="number",
                )

            actual_dec = _to_decimal(actual)

            if check.minimum is not None:
                if actual_dec < _to_decimal(check.minimum):
                    raise CheckValidationError(
                        "Число меньше minimum.",
                        kind=check.kind,
                        path=check.path,
                        actual=actual,
                        expected=check.minimum,
                    )

            if check.maximum is not None:
                if actual_dec > _to_decimal(check.maximum):
                    raise CheckValidationError(
                        "Число больше maximum.",
                        kind=check.kind,
                        path=check.path,
                        actual=actual,
                        expected=check.maximum,
                    )

            if check.exclusive_minimum is not None:
                if actual_dec <= _to_decimal(check.exclusive_minimum):
                    raise CheckValidationError(
                        "Число должно быть строго больше exclusive_minimum.",
                        kind=check.kind,
                        path=check.path,
                        actual=actual,
                        expected=check.exclusive_minimum,
                    )

            if check.exclusive_maximum is not None:
                if actual_dec >= _to_decimal(check.exclusive_maximum):
                    raise CheckValidationError(
                        "Число должно быть строго меньше exclusive_maximum.",
                        kind=check.kind,
                        path=check.path,
                        actual=actual,
                        expected=check.exclusive_maximum,
                    )

            if check.multiple_of is not None:
                divisor = _to_decimal(check.multiple_of)

                if divisor == 0:
                    raise CheckValidationError(
                        "multiple_of не может быть 0.",
                        kind=check.kind,
                        path=check.path,
                    )

                remainder = actual_dec % divisor

                if remainder != 0:
                    raise CheckValidationError(
                        "Число не кратно multiple_of.",
                        kind=check.kind,
                        path=check.path,
                        actual=actual,
                        expected=check.multiple_of,
                    )

            if check.positive and actual_dec <= 0:
                raise CheckValidationError(
                    "Число должно быть > 0.",
                    kind=check.kind,
                    path=check.path,
                    actual=actual,
                )

            if check.negative and actual_dec >= 0:
                raise CheckValidationError(
                    "Число должно быть < 0.",
                    kind=check.kind,
                    path=check.path,
                    actual=actual,
                )

            if check.non_zero and actual_dec == 0:
                raise CheckValidationError(
                    "Число не должно быть 0.",
                    kind=check.kind,
                    path=check.path,
                    actual=actual,
                )

            return

        # ========================================================
        # ArrayCheck
        # ========================================================
        case ArrayCheck():
            actual = _resolve_path(payload, check.path, kind=check.kind)

            if not isinstance(actual, Sequence) or isinstance(
                actual, (str, bytes, bytearray)
            ):
                raise CheckValidationError(
                    "Значение должно быть массивом.",
                    kind=check.kind,
                    path=check.path,
                    actual=type(actual).__name__,
                    expected="array",
                )

            if check.min_items is not None and len(actual) < check.min_items:
                raise CheckValidationError(
                    "В массиве меньше min_items.",
                    kind=check.kind,
                    path=check.path,
                    actual=len(actual),
                    expected=check.min_items,
                )

            if check.max_items is not None and len(actual) > check.max_items:
                raise CheckValidationError(
                    "В массиве больше max_items.",
                    kind=check.kind,
                    path=check.path,
                    actual=len(actual),
                    expected=check.max_items,
                )

            if check.unique_items:
                seen = set()

                try:
                    for item in actual:
                        marker = repr(item)

                        if marker in seen:
                            raise CheckValidationError(
                                "Массив содержит неуникальные элементы.",
                                kind=check.kind,
                                path=check.path,
                            )

                        seen.add(marker)

                except TypeError:
                    raise CheckValidationError(
                        "Невозможно проверить unique_items для элементов массива.",
                        kind=check.kind,
                        path=check.path,
                    )

            if check.contains is not None:
                found = False

                errors: list[Exception] = []

                for item in actual:
                    try:
                        _validate_check(
                            item,
                            check.contains,
                            external_step=external_step,
                            context=context,
                            now=now,
                        )
                        found = True
                        break
                    except CheckValidationError as exc:
                        errors.append(exc)

                if not found:
                    raise CheckValidationError(
                        "Ни один элемент массива не удовлетворяет contains.",
                        kind=check.kind,
                        path=check.path,
                        actual=[str(e) for e in errors],
                    )

            return

        # ========================================================
        # ObjectCheck
        # ========================================================
        case ObjectCheck():
            actual = _resolve_path(payload, check.path, kind=check.kind)

            if not isinstance(actual, Mapping):
                raise CheckValidationError(
                    f"Значение по пути {check.path!r} должно быть объектом.",
                    kind=check.kind,
                    path=check.path,
                    actual=type(actual).__name__,
                    expected="object",
                )

            actual_keys = set(actual.keys())

            if (
                check.min_properties is not None
                and len(actual_keys) < check.min_properties
            ):
                raise CheckValidationError(
                    f"У объекта по пути {check.path!r} меньше min_properties.",
                    kind=check.kind,
                    path=check.path,
                    actual=len(actual_keys),
                    expected=check.min_properties,
                )

            if (
                check.max_properties is not None
                and len(actual_keys) > check.max_properties
            ):
                raise CheckValidationError(
                    f"У объекта по пути {check.path!r} больше max_properties.",
                    kind=check.kind,
                    path=check.path,
                    actual=len(actual_keys),
                    expected=check.max_properties,
                )

            if check.required is not None:
                missing = [key for key in check.required if key not in actual]

                if missing:
                    raise CheckValidationError(
                        f"У объекта по пути {check.path!r} отсутствуют обязательные поля.",
                        kind=check.kind,
                        path=check.path,
                        actual=missing,
                        expected=check.required,
                    )

            if check.properties is not None:
                if check.additional_properties is False:
                    extra = sorted(actual_keys - set(check.properties.keys()))

                    if extra:
                        raise CheckValidationError(
                            f"У объекта по пути {check.path!r} есть лишние поля.",
                            kind=check.kind,
                            path=check.path,
                            actual=extra,
                            expected=sorted(check.properties.keys()),
                        )

                for prop_name, prop_check in check.properties.items():
                    if prop_name not in actual:
                        continue

                    if prop_check is None:
                        continue

                    try:
                        _validate_check(
                            payload,
                            prop_check,
                            external_step=external_step,
                            context=context,
                            now=now,
                        )
                    except CheckValidationError as exc:
                        raise CheckValidationError(
                            f"Ошибка в поле {check.path}.{prop_name}: {exc}",
                            kind=exc.kind or check.kind,
                            path=f"{check.path}.{prop_name}",
                            actual=exc.actual,
                            expected=exc.expected,
                        ) from exc

            elif check.additional_properties is False:
                raise CheckValidationError(
                    "additional_properties=False нельзя использовать без properties.",
                    kind=check.kind,
                    path=check.path,
                )

            return

        # ========================================================
        # FieldCompareCheck
        # =======================================================
        case FieldCompareCheck():
            left = _resolve_path(payload, check.left_path, kind=check.kind)
            right = _resolve_path(payload, check.right_path, kind=check.kind)

            if not _compare(left, check.op, right):
                raise CheckValidationError(
                    "Сравнение полей не прошло.",
                    kind=check.kind,
                    path=f"{check.left_path} {check.op} {check.right_path}",
                    actual=left,
                    expected=right,
                )

            return

        # ========================================================
        # DependencyCheck
        # ========================================================
        case DependencyCheck():
            if _path_exists(payload, check.if_path):
                missing = [
                    path
                    for path in check.required_paths
                    if not _path_exists(payload, path)
                ]

                if missing:
                    raise CheckValidationError(
                        "Не выполнена зависимость полей.",
                        kind=check.kind,
                        path=check.if_path,
                        actual=missing,
                        expected=check.required_paths,
                    )

            return

        # ========================================================
        # ExclusiveFieldsCheck
        # ========================================================
        case ExclusiveFieldsCheck():
            existing = [path for path in check.fields if _path_exists(payload, path)]

            if len(existing) > 1:
                raise CheckValidationError(
                    "Поля взаимоисключающие.",
                    kind=check.kind,
                    actual=existing,
                    expected="не более одного поля",
                )

            return

        # ========================================================
        # OneRequiredCheck
        # ========================================================
        case OneRequiredCheck():
            existing = [path for path in check.fields if _path_exists(payload, path)]

            if len(existing) != 1:
                raise CheckValidationError(
                    "Должно присутствовать ровно одно поле.",
                    kind=check.kind,
                    actual=existing,
                    expected="ровно одно поле",
                )

            return

        # ========================================================
        # ExternalStepCheck
        # ========================================================
        case ExternalStepCheck():
            if external_step != check.arg:
                raise CheckValidationError(
                    "external_step не совпадает.",
                    kind=check.kind,
                    actual=external_step,
                    expected=check.arg,
                )

            return

        # ========================================================
        # StatusCodeCheck
        # ========================================================
        case StatusCodeCheck():
            status_code = getattr(response, "status_code", MISSING)

            if status_code is MISSING:
                raise CheckValidationError(
                    "В payload отсутствует status_code.",
                    kind=check.kind,
                )

            if not _compare(status_code, check.op, check.value):
                raise CheckValidationError(
                    "Status code check не прошёл.",
                    kind=check.kind,
                    actual=status_code,
                    expected=f"{check.op} {check.value}",
                )

            return

        # ========================================================
        # LogicalCheck
        # ========================================================
        case LogicalCheck():
            if check.kind == "all_of":
                for nested in check.checks or []:
                    _validate_check(
                        response,
                        nested,
                        external_step=external_step,
                        context=context,
                        now=now,
                    )

                return

            if check.kind == "any_of":
                errors: list[Exception] = []

                for nested in check.checks or []:
                    try:
                        _validate_check(
                            response,
                            nested,
                            external_step=external_step,
                            context=context,
                            now=now,
                        )
                        return
                    except CheckValidationError as exc:
                        errors.append(exc)

                raise CheckValidationError(
                    "Ни одна проверка any_of не прошла.",
                    kind=check.kind,
                    actual=[str(e) for e in errors],
                )

            if check.kind == "one_of":
                passed = 0

                for nested in check.checks or []:
                    try:
                        _validate_check(
                            response,
                            nested,
                            external_step=external_step,
                            context=context,
                            now=now,
                        )
                        passed += 1
                    except CheckValidationError:
                        pass

                if passed != 1:
                    raise CheckValidationError(
                        "Должна пройти ровно одна проверка.",
                        kind=check.kind,
                        actual=passed,
                        expected=1,
                    )

                return

            if check.kind == "not":
                try:
                    assert check.check is not None
                    _validate_check(
                        response,
                        check.check,
                        external_step=external_step,
                        context=context,
                        now=now,
                    )
                except (CheckValidationError, AssertionError):
                    return

                raise CheckValidationError(
                    "Проверка внутри not прошла успешно, что запрещено.",
                    kind=check.kind,
                )

        # ========================================================
        # DateRangeCheck
        # ========================================================
        case DateRangeCheck():
            actual = _resolve_path(payload, check.path, kind=check.kind)

            if not isinstance(actual, str):
                raise CheckValidationError(
                    "Дата должна быть строкой.",
                    kind=check.kind,
                    path=check.path,
                    actual=actual,
                )

            try:
                actual_dt = datetime.fromisoformat(actual.replace("Z", "+00:00"))
            except Exception as exc:
                raise CheckValidationError(
                    "Некорректный datetime.",
                    kind=check.kind,
                    path=check.path,
                    actual=actual,
                ) from exc

            if check.after is not None:
                after_dt = _parse_datetime_like(
                    check.after,
                    payload=payload,
                    now=now,
                )

                if check.inclusive_after:
                    ok = actual_dt >= after_dt
                else:
                    ok = actual_dt > after_dt

                if not ok:
                    raise CheckValidationError(
                        "Дата меньше допустимой lower bound.",
                        kind=check.kind,
                        path=check.path,
                        actual=actual,
                        expected=check.after,
                    )

            if check.before is not None:
                before_dt = _parse_datetime_like(
                    check.before,
                    payload=payload,
                    now=now,
                )

                if check.inclusive_before:
                    ok = actual_dt <= before_dt
                else:
                    ok = actual_dt < before_dt

                if not ok:
                    raise CheckValidationError(
                        "Дата больше допустимой upper bound.",
                        kind=check.kind,
                        path=check.path,
                        actual=actual,
                        expected=check.before,
                    )

            return

        # ========================================================
        # Unknown check
        # ========================================================
        case _:
            raise TypeError(f"Неизвестный тип check: {type(check)!r}")
