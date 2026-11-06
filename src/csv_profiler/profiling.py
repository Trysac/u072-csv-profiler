"""Column profiling: type inference, nulls, duplicates, ranges, top values and warnings."""

from __future__ import annotations

import heapq
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

from .errors import clip
from .reader import Table

InferredType = Literal["integer", "float", "boolean", "date", "datetime", "string", "empty"]

TOP_VALUES = 5
MAX_TOP_VALUE_CHARS = 100
MAX_INTEGER_DIGITS = 300
CONFORMING_PERCENT = 95
PROBABLE_ID_MIN_ROWS = 10

_NULL_TOKENS = frozenset({"na", "n/a", "null", "none", "nan"})
_BOOLEANS = frozenset({"true", "false", "yes", "no"})
_ID_TYPES = frozenset({"integer", "string"})
_INT_RE = re.compile(r"[+-]?(?:0|[1-9][0-9]*)")
_FLOAT_RE = re.compile(r"[+-]?(?:[0-9]+[.][0-9]*|[.][0-9]+)(?:[eE][+-]?[0-9]+)?")
_EXP_RE = re.compile(r"[+-]?[0-9]+[eE][+-]?[0-9]+")
_DATE_PATTERN = r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
_CLOCK_PATTERN = r"[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:[.][0-9]{1,6})?)?"
_ZONE_PATTERN = r"(?:Z|[+-][0-9]{2}:[0-9]{2})?"
_DATE_RE = re.compile(_DATE_PATTERN)
_DATETIME_RE = re.compile(_DATE_PATTERN + _CLOCK_PATTERN + _ZONE_PATTERN)
_FRACTION_RE = re.compile(r"[.]([0-9]{1,6})")


@dataclass(frozen=True)
class ProfileWarning:
    """A finding about a column (or the whole table when ``column`` is ``None``)."""

    code: str
    column: str | None
    message: str


@dataclass(frozen=True)
class ColumnProfile:
    """Statistics of one column. Numbers and dates are reported only for conforming values."""

    name: str
    inferred_type: InferredType
    null_count: int
    null_ratio: float
    distinct_count: int
    min: int | float | str | None
    max: int | float | str | None
    mean: float | None
    max_length: int | None
    top_values: list[tuple[str, int]]
    non_conforming: int


@dataclass(frozen=True)
class Profile:
    """The profile of a whole table."""

    row_count: int
    column_count: int
    duplicate_row_count: int
    columns: list[ColumnProfile]
    warnings: list[ProfileWarning]


@dataclass
class _Tally:
    integers: list[tuple[int, int]] = field(default_factory=list)
    floats: list[tuple[float, int]] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
    integer_count: int = 0
    float_count: int = 0
    boolean_count: int = 0
    date_count: int = 0
    datetime_count: int = 0


def profile(table: Table) -> Profile:
    """Profile every column of ``table``.

    The table is expected to come from :func:`csv_profiler.read_table`, which already bounds
    its size. Rows shorter than the header are read as if padded with nulls.
    """
    row_count = len(table.rows)
    columns: list[ColumnProfile] = []
    for index, name in enumerate(table.columns):
        cells = [row[index] if index < len(row) else None for row in table.rows]
        columns.append(_profile_column(name, cells))
    warnings: list[ProfileWarning] = []
    if table.ragged_rows > 0:
        text = f"{table.ragged_rows} row(s) had a different number of fields than the header"
        warnings.append(ProfileWarning("ragged_rows", None, text))
    for column in columns:
        warnings.extend(_column_warnings(column, row_count))
    return Profile(
        row_count=row_count,
        column_count=len(table.columns),
        duplicate_row_count=_count_duplicates(table.rows),
        columns=columns,
        warnings=warnings,
    )


def _is_null(text: str) -> bool:
    return text == "" or text.lower() in _NULL_TOKENS


def _parse_int(text: str) -> int | None:
    if _INT_RE.fullmatch(text) is None:
        return None
    if len(text.lstrip("+-")) > MAX_INTEGER_DIGITS:
        return None
    return int(text)


def _parse_float(text: str) -> float | None:
    if _FLOAT_RE.fullmatch(text) is None and _EXP_RE.fullmatch(text) is None:
        return None
    number = float(text)
    return number if math.isfinite(number) else None


def _is_date(text: str) -> bool:
    if _DATE_RE.fullmatch(text) is None:
        return False
    try:
        date.fromisoformat(text)
    except ValueError:
        return False
    return True


def _pad_fraction(match: re.Match[str]) -> str:
    return "." + match.group(1).ljust(6, "0")


def _is_datetime(text: str) -> bool:
    if _DATETIME_RE.fullmatch(text) is None:
        return False
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    normalized = _FRACTION_RE.sub(_pad_fraction, normalized, count=1)
    try:
        datetime.fromisoformat(normalized)
    except ValueError:
        return False
    return True


def _tally(counter: Counter[str]) -> _Tally:
    tally = _Tally()
    for text, count in counter.items():
        integer = _parse_int(text)
        if integer is not None:
            tally.integers.append((integer, count))
            tally.integer_count += count
            continue
        number = _parse_float(text)
        if number is not None:
            tally.floats.append((number, count))
            tally.float_count += count
        elif text.lower() in _BOOLEANS:
            tally.boolean_count += count
        elif _is_date(text):
            tally.dates.append(text)
            tally.date_count += count
        elif _is_datetime(text):
            tally.datetime_count += count
    return tally


def _choose_type(tally: _Tally, non_null: int) -> tuple[InferredType, int]:
    if non_null == 0:
        return "empty", 0
    candidates: list[tuple[InferredType, int]] = [
        ("integer", tally.integer_count),
        ("float", tally.integer_count + tally.float_count),
        ("boolean", tally.boolean_count),
        ("date", tally.date_count),
        ("datetime", tally.datetime_count + tally.date_count),
    ]
    for inferred, accepted in candidates:
        if accepted * 100 >= CONFORMING_PERCENT * non_null:
            return inferred, accepted
    return "string", non_null


def _rounded(mean: float) -> float | None:
    return round(mean, 6) if math.isfinite(mean) else None


def _integer_stats(items: list[tuple[int, int]]) -> tuple[int, int, float | None]:
    low = min(value for value, _ in items)
    high = max(value for value, _ in items)
    count = sum(times for _, times in items)
    total = sum(value * times for value, times in items)
    return low, high, _rounded(total / count)


def _float_stats(items: list[tuple[float, int]]) -> tuple[float, float, float | None]:
    low = min(value for value, _ in items)
    high = max(value for value, _ in items)
    count = sum(times for _, times in items)
    try:
        total = math.fsum(value for value, times in items for _ in range(times))
    except OverflowError:
        return low, high, None
    return low, high, _rounded(total / count)


def _top_key(item: tuple[str, int]) -> tuple[int, str]:
    return (-item[1], item[0])


def _profile_column(name: str, cells: list[str | None]) -> ColumnProfile:
    counter: Counter[str] = Counter()
    null_count = 0
    for cell in cells:
        text = "" if cell is None else cell.strip()
        if _is_null(text):
            null_count += 1
        else:
            counter[text] += 1
    row_count = len(cells)
    non_null = row_count - null_count
    tally = _tally(counter)
    inferred, accepted = _choose_type(tally, non_null)
    minimum: int | float | str | None = None
    maximum: int | float | str | None = None
    mean: float | None = None
    if inferred == "integer":
        minimum, maximum, mean = _integer_stats(tally.integers)
    elif inferred == "float":
        converted = [(float(value), count) for value, count in tally.integers]
        minimum, maximum, mean = _float_stats([*converted, *tally.floats])
    elif inferred == "date":
        minimum, maximum = min(tally.dates), max(tally.dates)
    top = heapq.nsmallest(TOP_VALUES, counter.items(), key=_top_key)
    return ColumnProfile(
        name=name,
        inferred_type=inferred,
        null_count=null_count,
        null_ratio=round(null_count / row_count, 6) if row_count else 0.0,
        distinct_count=len(counter),
        min=minimum,
        max=maximum,
        mean=mean,
        max_length=max(len(text) for text in counter) if counter else None,
        top_values=[(value[:MAX_TOP_VALUE_CHARS], count) for value, count in top],
        non_conforming=non_null - accepted,
    )


def _column_warnings(column: ColumnProfile, row_count: int) -> list[ProfileWarning]:
    found: list[ProfileWarning] = []
    label = clip(column.name)
    non_null = row_count - column.null_count
    if column.distinct_count == 1 and non_null >= 2:
        message = f"column {label} holds a single distinct value"
        found.append(ProfileWarning("constant", column.name, message))
    if column.null_count * 2 > row_count:
        message = f"column {label} is {column.null_ratio * 100:.1f}% null"
        found.append(ProfileWarning("high_null", column.name, message))
    if column.non_conforming > 0:
        count = column.non_conforming
        message = f"column {label}: {count} value(s) do not fit type {column.inferred_type}"
        found.append(ProfileWarning("mixed_types", column.name, message))
    distinct_ids = column.distinct_count == non_null and non_null > 0
    if row_count >= PROBABLE_ID_MIN_ROWS and distinct_ids and column.inferred_type in _ID_TYPES:
        message = f"column {label} looks like an identifier: all values are distinct"
        found.append(ProfileWarning("probable_id", column.name, message))
    return found


def _count_duplicates(rows: list[list[str | None]]) -> int:
    seen: set[tuple[str | None, ...]] = set()
    duplicates = 0
    for row in rows:
        key = tuple(row)
        if key in seen:
            duplicates += 1
        else:
            seen.add(key)
    return duplicates
