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
    Failure,
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
    CheckSpec
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


def _make_error(
    failure: Failure,
    *,
    path: str | None = None,
    actual: Any = None,
    expected: Any = None,
) -> CheckValidationError:
    msg = failure.message
    if failure.type == "warning":
        msg = f"[warning] {msg}"

    return CheckValidationError(
        msg,
        kind=failure.kind,
        path=path,
        actual=actual,
        expected=expected,
    )
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
    check_and_failure: CheckSpec,
    *,
    external_step: Any = None,
    context: dict,
    now: datetime | None = None,
) -> list[CheckValidationError]:
    """
    Public wrapper.

    now фиксируется один раз для всей цепочки.
    """

    if now is None:
        now = datetime.now(tz=timezone.utc)

    return _validate_check(
        response=response,
        spec=check_and_failure,
        external_step=external_step,
        context=context,
        now=now,
    )


# ============================================================
# Main validator
# ============================================================
def _validate_check(
    spec: CheckSpec,
    response: Response | Mapping,
    *,
    external_step: Any = None,
    context: dict,
    now: datetime,
) -> list[CheckValidationError]:
    payload = response.json() if isinstance(response, Response) else response
    errors: list[CheckValidationError] = []

    def add(
        *,
        path: str | None = None,
        actual: Any = None,
        expected: Any = None,
    ) -> None:
        errors.append(
            _make_error(
                spec.failure,
                path=path,
                actual=actual,
                expected=expected,
            )
        )

    def walk(check: Check, current_payload: Any) -> None:
        match check:
            # ========================================================
            # ExistsCheck
            # ========================================================
            case ExistsCheck():
                if not _path_exists(current_payload, check.path):
                    add(path=check.path, expected="path exists")
                return

            # ========================================================
            # ValueEqualsCheck
            # ========================================================
            case ValueEqualsCheck():
                actual = _resolve_path(current_payload, check.path, kind=check.kind)
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
                    add(path=check.path, actual=actual, expected=expected)
                return

            # ========================================================
            # TypeCheck
            # ========================================================
            case TypeCheck():
                actual = _resolve_path(current_payload, check.path, kind=check.kind)
                actual_type = _json_type(actual)

                if actual_type not in check.type:
                    add(path=check.path, actual=actual_type, expected=check.type)
                return

            # ========================================================
            # StringCheck
            # ========================================================
            case StringCheck():
                actual = _resolve_path(current_payload, check.path, kind=check.kind)

                if not isinstance(actual, str):
                    add(
                        path=check.path,
                        actual=type(actual).__name__,
                        expected="string",
                    )
                    return

                if check.min_length is not None and len(actual) < check.min_length:
                    add(
                        path=check.path,
                        actual=len(actual),
                        expected=check.min_length,
                    )

                if check.max_length is not None and len(actual) > check.max_length:
                    add(
                        path=check.path,
                        actual=len(actual),
                        expected=check.max_length,
                    )

                if check.pattern is not None and re.search(check.pattern, actual) is None:
                    add(path=check.path, actual=actual, expected=check.pattern)

                if check.format is not None and not _validate_string_format(actual, check.format):
                    add(path=check.path, actual=actual, expected=check.format)

                return

            # ========================================================
            # NumberCheck
            # ========================================================
            case NumberCheck():
                actual = _resolve_path(current_payload, check.path, kind=check.kind)

                if not _is_number(actual):
                    add(
                        path=check.path,
                        actual=type(actual).__name__,
                        expected="number",
                    )
                    return

                actual_dec = _to_decimal(actual)

                if check.minimum is not None and actual_dec < _to_decimal(check.minimum):
                    add(path=check.path, actual=actual, expected=check.minimum)

                if check.maximum is not None and actual_dec > _to_decimal(check.maximum):
                    add(path=check.path, actual=actual, expected=check.maximum)

                if check.exclusive_minimum is not None and actual_dec <= _to_decimal(check.exclusive_minimum):
                    add(path=check.path, actual=actual, expected=check.exclusive_minimum)

                if check.exclusive_maximum is not None and actual_dec >= _to_decimal(check.exclusive_maximum):
                    add(path=check.path, actual=actual, expected=check.exclusive_maximum)

                if check.multiple_of is not None:
                    divisor = _to_decimal(check.multiple_of)
                    if divisor == 0:
                        add(path=check.path, actual=actual, expected="multiple_of != 0")
                    else:
                        if _to_decimal(actual) % divisor != 0:
                            add(path=check.path, actual=actual, expected=check.multiple_of)

                if check.positive and actual_dec <= 0:
                    add(path=check.path, actual=actual, expected="> 0")

                if check.negative and actual_dec >= 0:
                    add(path=check.path, actual=actual, expected="< 0")

                if check.non_zero and actual_dec == 0:
                    add(path=check.path, actual=actual, expected="!= 0")

                return

            # ========================================================
            # ArrayCheck
            # ========================================================
            case ArrayCheck():
                actual = _resolve_path(current_payload, check.path, kind=check.kind)

                if not isinstance(actual, Sequence) or isinstance(actual, (str, bytes, bytearray)):
                    add(
                        path=check.path,
                        actual=type(actual).__name__,
                        expected="array",
                    )
                    return

                if check.min_items is not None and len(actual) < check.min_items:
                    add(path=check.path, actual=len(actual), expected=check.min_items)

                if check.max_items is not None and len(actual) > check.max_items:
                    add(path=check.path, actual=len(actual), expected=check.max_items)

                if check.unique_items:
                    seen = set()
                    try:
                        for item in actual:
                            marker = repr(item)
                            if marker in seen:
                                add(path=check.path, expected="unique_items")
                                break
                            seen.add(marker)
                    except TypeError:
                        add(path=check.path, expected="unique_items check is not possible")

                if check.contains is not None:
                    found = False
                    branch_errors: list[CheckValidationError] = []

                    for item in actual:
                        before = len(errors)
                        walk(check.contains, item)
                        if len(errors) == before:
                            found = True
                            break
                        branch_errors.extend(errors[before:])
                        del errors[before:]

                    if not found:
                        # оставляем одну итоговую ошибку, но можно и branch_errors добавить,
                        # если нужно видеть причины по каждому элементу
                        add(path=check.path, actual=[str(e) for e in branch_errors], expected="contains")
                return

            # ========================================================
            # ObjectCheck
            # ========================================================
            case ObjectCheck():
                actual = _resolve_path(current_payload, check.path, kind=check.kind)

                if not isinstance(actual, Mapping):
                    add(
                        path=check.path,
                        actual=type(actual).__name__,
                        expected="object",
                    )
                    return

                actual_keys = set(actual.keys())

                if check.min_properties is not None and len(actual_keys) < check.min_properties:
                    add(path=check.path, actual=len(actual_keys), expected=check.min_properties)

                if check.max_properties is not None and len(actual_keys) > check.max_properties:
                    add(path=check.path, actual=len(actual_keys), expected=check.max_properties)

                if check.required is not None:
                    missing = [key for key in check.required if key not in actual]
                    if missing:
                        add(path=check.path, actual=missing, expected=check.required)

                if check.properties is not None:
                    if check.additional_properties is False:
                        extra = sorted(actual_keys - set(check.properties.keys()))
                        if extra:
                            add(path=check.path, actual=extra, expected=sorted(check.properties.keys()))

                    for prop_name, prop_check in check.properties.items():
                        if prop_check is None:
                            continue
                        if prop_name not in actual:
                            continue

                        # ВАЖНО:
                        # если твои prop_check.path абсолютные — оставляй current_payload = current_payload
                        # если относительные — замени на current_payload = actual[prop_name]
                        walk(prop_check, current_payload)

                elif check.additional_properties is False:
                    add(path=check.path, expected="properties must be set when additional_properties=False")

                return

            # ========================================================
            # FieldCompareCheck
            # =======================================================
            case FieldCompareCheck():
                left = _resolve_path(current_payload, check.left_path, kind=check.kind)
                right = _resolve_path(current_payload, check.right_path, kind=check.kind)

                if not _compare(left, check.op, right):
                    add(
                        path=f"{check.left_path} {check.op} {check.right_path}",
                        actual=left,
                        expected=right,
                    )
                return

            # ========================================================
            # DependencyCheck
            # ========================================================
            case DependencyCheck():
                if _path_exists(current_payload, check.if_path):
                    missing = [
                        path for path in check.required_paths
                        if not _path_exists(current_payload, path)
                    ]
                    if missing:
                        add(path=check.if_path, actual=missing, expected=check.required_paths)
                return

            # ========================================================
            # ExclusiveFieldsCheck
            # ========================================================
            case ExclusiveFieldsCheck():
                existing = [path for path in check.fields if _path_exists(current_payload, path)]
                if len(existing) > 1:
                    add(actual=existing, expected="no more than one field")
                return

            # ========================================================
            # OneRequiredCheck
            # ========================================================
            case OneRequiredCheck():
                existing = [path for path in check.fields if _path_exists(current_payload, path)]
                if len(existing) != 1:
                    add(actual=existing, expected="exactly one field")
                return

            # ========================================================
            # ExternalStepCheck
            # ========================================================
            case ExternalStepCheck():
                if external_step != check.arg:
                    add(actual=external_step, expected=check.arg)
                return

            # ========================================================
            # StatusCodeCheck
            # ========================================================
            case StatusCodeCheck():
                status_code = getattr(response, "status_code", MISSING)

                if status_code is MISSING:
                    add(expected="status_code")
                    return

                if not _compare(status_code, check.op, check.value):
                    add(actual=status_code, expected=f"{check.op} {check.value}")
                return

            # ========================================================
            # LogicalCheck
            # ========================================================
            case LogicalCheck():
                nested = check.checks or []

                if check.kind == "all_of":
                    for item in nested:
                        walk(item, current_payload)
                    return

                if check.kind == "any_of":
                    branch_failed_errors: list[CheckValidationError] = []
                    passed = False

                    for item in nested:
                        before = len(errors)
                        walk(item, current_payload)

                        if len(errors) == before:
                            passed = True
                            break

                        branch_failed_errors.extend(errors[before:])
                        del errors[before:]

                    if not passed:
                        # Можно оставить только одну итоговую ошибку.
                        # Но если тебе важно видеть все причины, добавь и branch_failed_errors.
                        errors.extend(branch_failed_errors)
                        add(expected="any_of")
                    return

                if check.kind == "one_of":
                    passed = 0
                    branch_failed_errors: list[CheckValidationError] = []

                    for item in nested:
                        before = len(errors)
                        walk(item, current_payload)

                        if len(errors) == before:
                            passed += 1
                        else:
                            branch_failed_errors.extend(errors[before:])
                            del errors[before:]

                    if passed != 1:
                        errors.extend(branch_failed_errors)
                        add(actual=passed, expected=1)
                    return

                if check.kind == "not":
                    if not nested:
                        add(expected="nested check for not")
                        return

                    before = len(errors)
                    walk(check.check, current_payload)  # type: ignore[arg-type]

                    if len(errors) == before:
                        # внутренняя проверка прошла, а это запрещено
                        add(expected="nested check must fail")
                    else:
                        # внутренняя проверка не прошла, это и нужно для not
                        del errors[before:]
                    return

                raise TypeError(f"Неизвестный kind logical check: {check.kind!r}")

            # ========================================================
            # DateRangeCheck
            # ========================================================
            case DateRangeCheck():
                actual = _resolve_path(current_payload, check.path, kind=check.kind)

                if not isinstance(actual, str):
                    add(path=check.path, actual=actual, expected="datetime string")
                    return

                try:
                    actual_dt = datetime.fromisoformat(actual.replace("Z", "+00:00"))
                except Exception:
                    add(path=check.path, actual=actual, expected="valid datetime")
                    return

                if check.after is not None:
                    after_dt = _parse_datetime_like(check.after, payload=current_payload, now=now)
                    ok = actual_dt >= after_dt if check.inclusive_after else actual_dt > after_dt
                    if not ok:
                        add(path=check.path, actual=actual, expected=check.after)

                if check.before is not None:
                    before_dt = _parse_datetime_like(check.before, payload=current_payload, now=now)
                    ok = actual_dt <= before_dt if check.inclusive_before else actual_dt < before_dt
                    if not ok:
                        add(path=check.path, actual=actual, expected=check.before)

                return

            # ========================================================
            # Unknown
            # ========================================================
            case _:
                raise TypeError(f"Неизвестный тип check: {type(check)!r}")

    walk(spec.check, payload)

    # при желании можно убрать дубликаты
    uniq: list[CheckValidationError] = []
    seen = set()
    for err in errors:
        marker = (
            getattr(err, "kind", None),
            getattr(err, "path", None),
            getattr(err, "message", None),
            repr(getattr(err, "actual", None)),
            repr(getattr(err, "expected", None)),
        )
        if marker in seen:
            continue
        seen.add(marker)
        uniq.append(err)

    return uniq