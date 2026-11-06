"""Tests for the public API of csv_profiler."""

from __future__ import annotations

import csv
import json
import logging
import re
import zipfile
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from openpyxl import Workbook

import csv_profiler
from csv_profiler import (
    ColumnProfile,
    Profile,
    ProfileError,
    Table,
    profile,
    read_table,
    render_html,
    render_json,
)

ALLOWED_TAGS = {
    "!doctype",
    "html",
    "head",
    "meta",
    "title",
    "style",
    "body",
    "h1",
    "h2",
    "p",
    "ul",
    "li",
    "strong",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "code",
    "br",
}


def write_text(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_bytes(text.encode("utf-8"))
    return path


def error_code(path: Path, **kwargs: Any) -> str:
    with pytest.raises(ProfileError) as info:
        read_table(path, **kwargs)
    return info.value.code


def column_table(values: list[str | None]) -> Table:
    return Table(columns=["c"], rows=[[value] for value in values])


def profile_column(values: list[str | None]) -> ColumnProfile:
    return profile(column_table(values)).columns[0]


def warning_codes(result: Profile) -> set[str]:
    return {warning.code for warning in result.warnings}


# --- package ----------------------------------------------------------------


def test_version_and_null_handler() -> None:
    assert csv_profiler.__version__ == "0.1.0"
    handlers = logging.getLogger("csv_profiler").handlers
    assert any(isinstance(handler, logging.NullHandler) for handler in handlers)


def test_profile_error_has_code_and_bounded_message() -> None:
    error = ProfileError("empty", "x" * 500)
    assert error.code == "empty"
    assert len(str(error)) == 200
    assert error.message == str(error)
    assert isinstance(error, Exception)


# --- CSV reading ------------------------------------------------------------


@pytest.mark.parametrize("delimiter", [",", ";", "\t", "|"])
def test_read_table_detects_delimiters(tmp_path: Path, delimiter: str) -> None:
    rows = [
        ["id", "name", "city"],
        ["1", "ann", "rome"],
        ["2", "bob", "oslo"],
        ["3", "cy", "bern"],
    ]
    text = "\n".join(delimiter.join(row) for row in rows) + "\n"
    table = read_table(write_text(tmp_path, "t.csv", text))
    assert table.columns == ["id", "name", "city"]
    assert table.rows[2] == ["3", "cy", "bern"]
    assert table.ragged_rows == 0


@pytest.mark.parametrize("name", ["t.tsv", "t.txt", "T.CSV"])
def test_read_table_accepts_text_suffixes(tmp_path: Path, name: str) -> None:
    table = read_table(write_text(tmp_path, name, "a,b\n1,2\n3,4\n"))
    assert table.columns == ["a", "b"]


def test_read_table_strips_bom_so_first_header_is_id(tmp_path: Path) -> None:
    path = tmp_path / "bom.csv"
    path.write_bytes(b"\xef\xbb\xbfid,name\n1,a\n")
    assert read_table(path).columns == ["id", "name"]
    assert read_table(path, encoding="utf-8").columns == ["id", "name"]


def test_read_table_honours_explicit_delimiter(tmp_path: Path) -> None:
    path = write_text(tmp_path, "d.csv", "a,b;c\n1,2;3\n")
    table = read_table(path, delimiter=";")
    assert table.columns == ["a,b", "c"]
    assert table.rows == [["1,2", "3"]]


def test_read_table_pads_ragged_rows_and_warns(tmp_path: Path) -> None:
    path = write_text(tmp_path, "r.csv", "a,b,c\n1,2\n3,4,5\n6\n")
    table = read_table(path, delimiter=",")
    assert table.rows == [["1", "2", None], ["3", "4", "5"], ["6", None, None]]
    assert table.ragged_rows == 2
    found = [w for w in profile(table).warnings if w.code == "ragged_rows"]
    assert len(found) == 1
    assert found[0].column is None


def test_read_table_extends_header_for_wide_rows(tmp_path: Path) -> None:
    table = read_table(write_text(tmp_path, "w.csv", "a\n1,2\n"), delimiter=",")
    assert table.columns == ["a", "column_2"]
    assert table.rows == [["1", "2"]]
    assert table.ragged_rows == 1


def test_read_table_falls_back_to_comma_for_single_column(tmp_path: Path) -> None:
    table = read_table(write_text(tmp_path, "s.csv", "a\n1\n2\n"))
    assert table.columns == ["a"]
    assert table.rows == [["1"], ["2"]]


def test_read_table_handles_quotes_and_blank_lines(tmp_path: Path) -> None:
    text = 'a,b\n"x,1","line1\nline2"\n\n"he said ""hi""",z\n'
    table = read_table(write_text(tmp_path, "q.csv", text), delimiter=",")
    assert table.rows == [["x,1", "line1\nline2"], ['he said "hi"', "z"]]


def test_read_table_returns_no_rows_for_header_only_file(tmp_path: Path) -> None:
    table = read_table(write_text(tmp_path, "h.csv", "a,b\n"))
    assert table.rows == []
    assert profile(table).row_count == 0


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (",a,a", ["column_1", "a", "a_2"]),
        ("a,a,a_2,a", ["a", "a_2", "a_2_2", "a_3"]),
        ("x, ,y", ["x", "column_2", "y"]),
    ],
)
def test_read_table_renames_headers(tmp_path: Path, header: str, expected: list[str]) -> None:
    row = ",".join(["1"] * (header.count(",") + 1))
    path = write_text(tmp_path, "h.csv", header + "\n" + row + "\n")
    assert read_table(path, delimiter=",").columns == expected


def test_read_table_reads_other_encodings(tmp_path: Path) -> None:
    path = tmp_path / "latin.csv"
    path.write_bytes(b"name\n\xe9\n")
    assert read_table(path, encoding="latin-1").rows == [["\u00e9"]]


# --- CSV errors and limits --------------------------------------------------


def test_read_table_rejects_empty_inputs(tmp_path: Path) -> None:
    zero = tmp_path / "zero.csv"
    zero.write_bytes(b"")
    assert error_code(zero) == "empty"
    assert error_code(write_text(tmp_path, "blank.csv", "\n  \n")) == "empty"
    only_bom = tmp_path / "bom.csv"
    only_bom.write_bytes(b"\xef\xbb\xbf")
    assert error_code(only_bom) == "empty"


@pytest.mark.parametrize("name", ["data.parquet", "old.xls", "noext", "a.json"])
def test_read_table_rejects_unsupported_formats(tmp_path: Path, name: str) -> None:
    path = tmp_path / name
    path.write_bytes(b"PAR1")
    assert error_code(path) == "unsupported_format"


def test_read_table_rejects_files_over_max_bytes(tmp_path: Path) -> None:
    max_bytes = 64
    path = tmp_path / "big.csv"
    path.write_bytes(b"a,b\n" + b"1" * (max_bytes + 1 - 4))
    assert path.stat().st_size == max_bytes + 1
    assert error_code(path, max_bytes=max_bytes) == "too_large"
    path.write_bytes(b"a,b\n" + b"1" * (max_bytes - 4))
    assert read_table(path, max_bytes=max_bytes).columns == ["a", "b"]


def test_read_table_rejects_fields_over_131072_characters(tmp_path: Path) -> None:
    too_big = write_text(tmp_path, "cell.csv", "a\n" + "x" * 131073 + "\n")
    assert error_code(too_big) == "cell_too_large"
    fits = write_text(tmp_path, "fits.csv", "a\n" + "x" * 131072 + "\n")
    assert len(read_table(fits).rows[0][0] or "") == 131072


def test_read_table_checks_cell_size_even_if_csv_limit_was_raised(tmp_path: Path) -> None:
    path = write_text(tmp_path, "cell.csv", "a\n" + "x" * 131073 + "\n")
    previous = csv.field_size_limit(10_000_000)
    try:
        assert error_code(path) == "cell_too_large"
    finally:
        csv.field_size_limit(previous)


def test_read_table_enforces_row_and_column_limits(tmp_path: Path) -> None:
    rows = write_text(tmp_path, "rows.csv", "a\n1\n2\n3\n")
    assert error_code(rows, max_rows=2) == "too_large"
    assert len(read_table(rows, max_rows=3).rows) == 3
    wide = write_text(tmp_path, "wide.csv", "a,b,c\n1,2,3\n")
    assert error_code(wide, max_columns=2, delimiter=",") == "too_large"
    wide_row = write_text(tmp_path, "wide_row.csv", "a\n1,2,3\n")
    assert error_code(wide_row, max_columns=2, delimiter=",") == "too_large"


def test_read_table_reports_encoding_problems(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_bytes(b"a,b\n\xff\xfe,1\n")
    assert error_code(bad) == "encoding"
    good = write_text(tmp_path, "good.csv", "a\n1\n")
    assert error_code(good, encoding="no-such-codec") == "encoding"


def test_read_table_reports_malformed_csv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def broken(*args: Any, **kwargs: Any) -> Any:
        raise csv.Error("boom")

    monkeypatch.setattr(csv, "reader", broken)
    assert error_code(write_text(tmp_path, "m.csv", "a,b\n1,2\n")) == "encoding"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_rows": 0},
        {"max_bytes": 0},
        {"max_columns": 0},
        {"delimiter": "ab"},
        {"delimiter": ""},
        {"delimiter": '"'},
        {"delimiter": "\n"},
    ],
)
def test_read_table_validates_arguments(tmp_path: Path, kwargs: dict[str, Any]) -> None:
    path = write_text(tmp_path, "a.csv", "a\n1\n")
    with pytest.raises(ValueError):
        read_table(path, **kwargs)


def test_read_table_propagates_missing_files(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_table(tmp_path / "nope.csv")


# --- XLSX -------------------------------------------------------------------


class FakeSheet:
    def __init__(self, title: str, rows: list[tuple[Any, ...]]) -> None:
        self.title = title
        self.rows = rows

    def iter_rows(self, values_only: bool = True) -> Any:
        return iter(self.rows)


class BrokenSheet(FakeSheet):
    def iter_rows(self, values_only: bool = True) -> Any:
        raise RuntimeError("boom")


class FakeBook:
    def __init__(self, sheets: list[FakeSheet]) -> None:
        self.worksheets = sheets
        self.closed = False

    def close(self) -> None:
        self.closed = True


def make_workbook(tmp_path: Path) -> Path:
    book = Workbook()
    sheet = book.active
    sheet.title = "Data"
    sheet.append(["id", "when", "stamp", "amount", "ok"])
    sheet.append([1, date(2024, 1, 15), datetime(2024, 1, 15, 10, 30), 3.0, True])
    sheet.append([2, date(2024, 2, 1), datetime(2024, 2, 1, 12, 0), 2.5, False])
    book.create_sheet("Other").append(["z"])
    path = tmp_path / "book.xlsx"
    book.save(path)
    return path


def install_fake(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, book: Any) -> Path:
    path = tmp_path / "fake.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("a.txt", "x")
    monkeypatch.setattr(csv_profiler.reader, "_load_workbook", lambda _path: book)
    return path


def test_xlsx_named_sheet_is_profiled_with_iso_dates(tmp_path: Path) -> None:
    path = make_workbook(tmp_path)
    table = read_table(path, sheet="Data")
    assert table.columns == ["id", "when", "stamp", "amount", "ok"]
    assert table.rows[0] == ["1", "2024-01-15", "2024-01-15T10:30:00", "3", "true"]
    assert table.rows[1] == ["2", "2024-02-01", "2024-02-01T12:00:00", "2.5", "false"]
    types = {column.name: column.inferred_type for column in profile(table).columns}
    assert types == {
        "id": "integer",
        "when": "date",
        "stamp": "datetime",
        "amount": "float",
        "ok": "boolean",
    }


def test_xlsx_defaults_to_first_sheet_and_selects_others(tmp_path: Path) -> None:
    path = make_workbook(tmp_path)
    assert read_table(path).columns[0] == "id"
    assert read_table(path, sheet="Other").columns == ["z"]


def test_xlsx_unknown_sheet_raises(tmp_path: Path) -> None:
    assert error_code(make_workbook(tmp_path), sheet="Missing") == "unknown_sheet"


def test_xlsx_archive_expanding_past_max_bytes_is_rejected_before_openpyxl(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def must_not_run(_path: str) -> Any:
        raise AssertionError("openpyxl must not open a bomb")

    monkeypatch.setattr(csv_profiler.reader, "_load_workbook", must_not_run)
    path = tmp_path / "bomb.xlsx"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/big.bin", b"\0" * 2_000_000)
    assert path.stat().st_size < 100_000
    assert error_code(path, max_bytes=100_000) == "too_large"


def test_xlsx_with_too_many_members_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "many.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        for index in range(10_001):
            archive.writestr(f"m{index}.txt", b"")
    assert error_code(path) == "too_large"
    monkeypatch.setattr(csv_profiler.reader, "_declared_member_count", lambda _path: None)
    assert error_code(path) == "too_large"


def test_xlsx_rejects_non_archives_and_non_workbooks(tmp_path: Path) -> None:
    text = tmp_path / "text.xlsx"
    text.write_bytes(b"not a zip archive")
    assert error_code(text) == "unsupported_format"
    plain = tmp_path / "plain.xlsx"
    with zipfile.ZipFile(plain, "w") as archive:
        archive.writestr("a.txt", "x")
    assert error_code(plain) == "unsupported_format"
    empty = tmp_path / "empty.xlsx"
    empty.write_bytes(b"")
    assert error_code(empty) == "empty"


def test_xlsx_requires_openpyxl(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "a.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("a.txt", "x")

    def missing(_name: str) -> Any:
        raise ImportError("no openpyxl")

    with monkeypatch.context() as patch:
        patch.setattr(csv_profiler.reader.importlib, "import_module", missing)
        assert error_code(path) == "unsupported_format"


def test_xlsx_cell_values_become_strings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rows = [
        ("kind", "value"),
        ("bool", True),
        ("date", date(2024, 1, 15)),
        ("midnight", datetime(2024, 1, 15, 0, 0)),
        ("aware", datetime(2024, 1, 15, 0, 0, tzinfo=timezone.utc)),
        ("stamp", datetime(2024, 1, 15, 10, 30, 5, 250000)),
        ("time", time(10, 30)),
        ("integral", 3.0),
        ("float", 2.5),
        ("big", 1e20),
        ("inf", float("inf")),
        ("decimal", Decimal("1.50")),
        ("delta", timedelta(seconds=5)),
        ("text", "  hi "),
        ("gap", None),
        (None, None),
        ("trail", "x", None, None),
    ]
    book = FakeBook([FakeSheet("S", rows)])
    table = read_table(install_fake(monkeypatch, tmp_path, book))
    values = {row[0]: row[1] for row in table.rows}
    assert table.columns == ["kind", "value"]
    assert values == {
        "bool": "true",
        "date": "2024-01-15",
        "midnight": "2024-01-15",
        "aware": "2024-01-15T00:00:00+00:00",
        "stamp": "2024-01-15T10:30:05.250000",
        "time": "10:30:00",
        "integral": "3",
        "float": "2.5",
        "big": "100000000000000000000",
        "inf": "inf",
        "decimal": "1.50",
        "delta": "0:00:05",
        "text": "  hi ",
        "gap": None,
        "trail": "x",
    }
    assert table.ragged_rows == 0
    assert book.closed


def test_xlsx_errors_from_the_reader_are_typed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    broken = FakeBook([BrokenSheet("S", [])])
    path = install_fake(monkeypatch, tmp_path, broken)
    assert error_code(path) == "unsupported_format"
    assert broken.closed

    no_sheets = FakeBook([])
    install_fake(monkeypatch, tmp_path, no_sheets)
    assert error_code(path) == "empty"

    blank = FakeBook([FakeSheet("S", [(None, None)])])
    install_fake(monkeypatch, tmp_path, blank)
    assert error_code(path) == "empty"

    big_cell = FakeBook([FakeSheet("S", [("a",), ("x" * 131073,)])])
    install_fake(monkeypatch, tmp_path, big_cell)
    assert error_code(path) == "cell_too_large"

    def fail(_path: str) -> Any:
        raise KeyError("x")

    monkeypatch.setattr(csv_profiler.reader, "_load_workbook", fail)
    assert error_code(path) == "unsupported_format"


def test_xlsx_enforces_row_and_column_limits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    book = FakeBook([FakeSheet("S", [("a", "b", "c"), (1, 2, 3), (4, 5, 6), (7, 8, 9)])])
    path = install_fake(monkeypatch, tmp_path, book)
    assert error_code(path, max_rows=2) == "too_large"
    assert error_code(path, max_columns=2) == "too_large"
    assert len(read_table(path, max_rows=3).rows) == 3


# --- profiling --------------------------------------------------------------


def test_21_integers_and_one_x_are_mixed_types() -> None:
    values: list[str | None] = [str(number) for number in range(1, 22)]
    values.append("x")
    result = profile(column_table(values))
    column = result.columns[0]
    assert column.inferred_type == "integer"
    assert column.non_conforming == 1
    assert "mixed_types" in warning_codes(result)


def test_conformance_threshold_is_95_percent() -> None:
    at_threshold = profile_column([str(n) for n in range(1, 20)] + ["x"])
    assert (at_threshold.inferred_type, at_threshold.non_conforming) == ("integer", 1)
    below = profile_column([str(n) for n in range(1, 19)] + ["x", "x"])
    assert (below.inferred_type, below.non_conforming) == ("string", 0)


def test_leading_zero_values_stay_strings() -> None:
    assert profile_column(["007"]).inferred_type == "string"
    assert profile_column(["007", "008", "010"]).inferred_type == "string"


def test_null_tokens_are_not_values() -> None:
    column = profile_column(["NA", "n/a", "null", "None", "", " ", "NaN", None, "1"])
    assert column.null_count == 8
    assert column.inferred_type == "integer"
    assert column.null_ratio == round(8 / 9, 6)
    assert column.distinct_count == 1


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("42", "integer"),
        ("-7", "integer"),
        ("+0", "integer"),
        ("0", "integer"),
        ("1", "integer"),
        ("007", "string"),
        ("-007", "string"),
        ("00", "string"),
        ("1e5", "float"),
        ("1.5", "float"),
        ("1.", "float"),
        (".5", "float"),
        ("-1.5E+3", "float"),
        ("1e999", "string"),
        ("1.5e999", "string"),
        ("inf", "string"),
        ("Infinity", "string"),
        ("1,5", "string"),
        ("1.5.2", "string"),
        ("\u0661\u0662", "string"),
        ("12abc", "string"),
        ("1e5x", "string"),
        ("1_000", "string"),
        ("YES", "boolean"),
        ("yes", "boolean"),
        ("No", "boolean"),
        ("TRUE", "boolean"),
        ("false", "boolean"),
        ("2024-01-01", "date"),
        ("2024-02-30", "string"),
        ("0000-01-01", "string"),
        ("2024-1-1", "string"),
        ("2024-01-01T10:00:00Z", "datetime"),
        ("2024-01-01 10:00", "datetime"),
        ("2024-01-01T10:00:00.5+05:30", "datetime"),
        ("2024-01-01T10:00:00.123456", "datetime"),
        ("2024-01-01x10:00", "string"),
        ("2024-01-01T25:00", "string"),
        ("2024-01-01T10:00:00+25:00", "string"),
        ("2024-01-01T10:00:00.1234567", "string"),
    ],
)
def test_single_value_type_inference(value: str, expected: str) -> None:
    assert profile_column([value]).inferred_type == expected


def test_values_are_trimmed_before_classification() -> None:
    column = profile_column([" 12 ", "13"])
    assert column.inferred_type == "integer"
    assert column.max_length == 2


def test_huge_integers_do_not_crash() -> None:
    assert profile_column(["9" * 300]).inferred_type == "integer"
    assert profile_column(["9" * 301]).inferred_type == "string"
    assert profile_column(["9" * 131072]).inferred_type == "string"


def test_mixed_dates_and_datetimes_infer_datetime() -> None:
    column = profile_column(["2024-01-01", "2024-01-02T10:00:00"])
    assert column.inferred_type == "datetime"
    assert column.non_conforming == 0


def test_numeric_columns_report_min_max_and_mean() -> None:
    column = profile_column(["1", "2", "3", "4"])
    assert (column.min, column.max, column.mean) == (1, 4, 2.5)
    assert column.max_length == 1
    floats = profile_column(["1", "2.5", "3"])
    assert floats.inferred_type == "float"
    assert (floats.min, floats.max, floats.mean) == (1.0, 3.0, 2.166667)
    assert isinstance(floats.min, float)


def test_float_mean_that_overflows_is_none() -> None:
    column = profile_column(["1e308", "1e308"])
    assert column.inferred_type == "float"
    assert column.max == 1e308
    assert column.mean is None


def test_date_columns_report_range_without_mean() -> None:
    column = profile_column(["2024-03-01", "2024-01-15", "2024-03-01"])
    assert (column.inferred_type, column.min, column.max) == ("date", "2024-01-15", "2024-03-01")
    assert column.mean is None


def test_string_columns_have_no_numeric_stats() -> None:
    column = profile_column(["b", "a"])
    assert (column.min, column.max, column.mean) == (None, None, None)


def test_top_values_hold_five_entries_ordered_by_count_then_value() -> None:
    values = ["5"] * 3 + ["10"] * 3 + ["2"] * 2 + ["7", "1", "3", "4"]
    column = profile_column(values)
    assert column.top_values == [("10", 3), ("5", 3), ("2", 2), ("1", 1), ("3", 1)]
    assert column.distinct_count == 7


def test_top_values_are_truncated_to_100_characters() -> None:
    column = profile_column(["y" * 150, "y" * 150, "z"])
    assert column.top_values[0] == ("y" * 100, 2)
    assert column.max_length == 150


def test_duplicate_rows_are_counted() -> None:
    two = Table(columns=["a", "b"], rows=[["1", "x"], ["1", "x"]])
    assert profile(two).duplicate_row_count == 1
    three = Table(columns=["a"], rows=[["1"], ["1"], ["1"], ["2"]])
    assert profile(three).duplicate_row_count == 2
    distinct = Table(columns=["a"], rows=[["1"], [None]])
    assert profile(distinct).duplicate_row_count == 0


def test_empty_and_all_null_columns() -> None:
    none_at_all = profile(column_table([]))
    assert none_at_all.row_count == 0
    assert none_at_all.columns[0].inferred_type == "empty"
    assert none_at_all.columns[0].null_ratio == 0.0
    assert none_at_all.columns[0].max_length is None
    nulls = profile(column_table([None, "NA", ""]))
    assert nulls.columns[0].inferred_type == "empty"
    assert "high_null" in warning_codes(nulls)


def test_short_rows_are_read_as_null() -> None:
    result = profile(Table(columns=["a", "b"], rows=[["1"], ["2", "x"]]))
    assert result.columns[1].null_count == 1
    assert result.column_count == 2


def test_constant_warning() -> None:
    result = profile(column_table(["a", "a", "a"]))
    found = [w for w in result.warnings if w.code == "constant"]
    assert [w.column for w in found] == ["c"]
    assert "constant" not in warning_codes(profile(column_table(["a"])))
    assert "constant" not in warning_codes(profile(column_table(["a", None])))
    assert "constant" not in warning_codes(profile(column_table(["a", "b"])))


def test_high_null_warning_needs_more_than_half() -> None:
    assert "high_null" in warning_codes(profile(column_table([None, None, None, "a", "b"])))
    assert "high_null" not in warning_codes(profile(column_table([None, None, "a", "b"])))


def test_probable_id_rules() -> None:
    ten = [str(n) for n in range(10)]
    assert "probable_id" in warning_codes(profile(column_table(ten)))
    letters = [f"id{n}" for n in range(10)]
    assert "probable_id" in warning_codes(profile(column_table(letters)))
    assert "probable_id" not in warning_codes(profile(column_table(ten[:9])))
    assert "probable_id" not in warning_codes(profile(column_table([*ten[:9], "8"])))
    floats = [f"{n}.5" for n in range(10)]
    assert "probable_id" not in warning_codes(profile(column_table(floats)))
    assert "probable_id" not in warning_codes(profile(column_table([None] * 10)))


def test_all_warning_codes_appear() -> None:
    rows: list[list[str | None]] = []
    for index in range(20):
        rows.append(
            [
                str(index),
                "x",
                None if index < 12 else f"v{index}",
                "x" if index == 19 else str(index),
            ]
        )
    table = Table(columns=["id", "k", "n", "m"], rows=rows, ragged_rows=1)
    result = profile(table)
    assert warning_codes(result) == {
        "constant",
        "high_null",
        "mixed_types",
        "probable_id",
        "ragged_rows",
    }
    assert result.warnings[0].code == "ragged_rows"


# --- rendering --------------------------------------------------------------


def test_render_json_matches_golden() -> None:
    table = Table(columns=["n"], rows=[["1"], ["2"], ["3"]])
    lines = [
        "{",
        '  "column_count": 1,',
        '  "columns": [',
        "    {",
        '      "distinct_count": 3,',
        '      "inferred_type": "integer",',
        '      "max": 3,',
        '      "max_length": 1,',
        '      "mean": 2.0,',
        '      "min": 1,',
        '      "name": "n",',
        '      "non_conforming": 0,',
        '      "null_count": 0,',
        '      "null_ratio": 0.0,',
        '      "top_values": [',
        "        [",
        '          "1",',
        "          1",
        "        ],",
        "        [",
        '          "2",',
        "          1",
        "        ],",
        "        [",
        '          "3",',
        "          1",
        "        ]",
        "      ]",
        "    }",
        "  ],",
        '  "duplicate_row_count": 0,',
        '  "row_count": 3,',
        '  "warnings": []',
        "}",
    ]
    assert render_json(profile(table)) == "\n".join(lines)


def test_render_json_is_valid_and_serialises_nulls_and_warnings() -> None:
    result = profile(Table(columns=["k"], rows=[["x"], ["x"]]))
    data = json.loads(render_json(result))
    assert data["columns"][0]["mean"] is None
    assert data["columns"][0]["top_values"] == [["x", 2]]
    assert data["warnings"][0] == {
        "code": "constant",
        "column": "k",
        "message": "column k holds a single distinct value",
    }
    assert render_json(result) == render_json(result)


def test_render_html_escapes_cells_and_has_no_active_content() -> None:
    table = Table(columns=["c"], rows=[["<script>alert(1)</script>"]])
    page = render_html(profile(table), title="Report")
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    for forbidden in ("<script", "src=", "href=", "http"):
        assert forbidden not in page
    assert page.startswith("<!DOCTYPE html>")
    assert "<style>" in page
    assert "url(" not in page
    assert "@import" not in page


def test_render_html_only_emits_known_tags_for_hostile_input() -> None:
    hostile = '"><img onerror=alert(1)>'
    table = Table(columns=[hostile, hostile + "2"], rows=[[hostile, "x"], [hostile, "x"]])
    page = render_html(profile(table), title="<i>" + hostile)
    tags = {tag.lstrip("/").lower() for tag in re.findall(r"<(/?[a-zA-Z!][a-zA-Z0-9]*)", page)}
    assert tags <= ALLOWED_TAGS
    assert "<img" not in page
    assert "&quot;&gt;&lt;img onerror=alert(1)&gt;" in page
    assert "<i>" not in page


def test_render_html_lists_warnings_and_columns() -> None:
    table = Table(columns=["k"], rows=[["x"], ["x"]], ragged_rows=1)
    page = render_html(profile(table), title="t")
    assert "constant" in page
    assert "ragged_rows" in page
    assert "2 rows, 1 columns, 1 duplicate rows" in page
    clean = render_html(profile(Table(columns=["k"], rows=[["x"], ["y"]])), title="t")
    assert "No warnings." in clean
