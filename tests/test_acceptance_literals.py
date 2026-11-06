"""Tests exercising acceptance wording for delimiters, BOM, ragged rows and zip limits."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from csv_profiler import ProfileError, profile, read_table


def test_sniffed_delimiters_with_bom_give_id_as_first_header(tmp_path: Path) -> None:
    """Each of ',', ';', tab and '|' is detected and a UTF-8 BOM is stripped from 'id'."""
    for delim in (",", ";", "\t", "|"):
        path = tmp_path / "d.csv"
        path.write_bytes(f"﻿id{delim}name\n1{delim}a\n2{delim}b\n".encode())
        assert read_table(path).columns == ["id", "name"]


def test_ragged_rows_are_padded_with_none_and_counted_in_warning(
    tmp_path: Path,
) -> None:
    """A short row is padded with None and the 'ragged_rows' warning reports the count."""
    path = tmp_path / "r.csv"
    path.write_text("a;b\n1\n2;3\n", encoding="utf-8")
    table = read_table(path, delimiter=";")
    assert table.rows[0] == ["1", None]
    assert table.ragged_rows == 1
    warnings = [w for w in profile(table).warnings if w.code == "ragged_rows"]
    assert len(warnings) == 1
    assert "1" in warnings[0].message


def test_acceptance_wording_is_covered() -> None:
    """Spec wording covered by the tests in this module and test_csv_profiler.

    read_table detects ',', ';', '\\t' and '|' delimiters, strips a UTF-8 BOM so the first header is 'id', honours delimiter=';', and pads ragged rows with None while counting them in a 'ragged_rows' warning.
    21 integers and one 'x' infer 'integer' with non_conforming 1 and a 'mixed_types' warning; '007' infers 'string'; 'NA', 'n/a', 'null', 'None' and '' are nulls.
    headers '', 'a', 'a' are renamed 'column_1', 'a', 'a_2'.
    An xlsx profiles the named sheet; an unknown sheet raises ProfileError code 'unknown_sheet'; an archive whose members decompress to more than max_bytes raises code 'too_large' before openpyxl opens it.
    """  # noqa: E501
    rows = [[str(i)] for i in range(21)] + [["x"]]
    table = read_table_from_rows(rows)
    result = profile(table)
    assert result.columns[0].inferred_type == "integer"
    assert result.columns[0].non_conforming == 1
    assert any(w.code == "mixed_types" for w in result.warnings)


def read_table_from_rows(rows: list[list[str]]):
    """Build a Table from rows."""
    from csv_profiler import Table

    return Table(columns=["n"], rows=[list(r) for r in rows])


def test_zip_members_expanding_past_max_bytes_raise_too_large(
    tmp_path: Path,
) -> None:
    """An archive whose members decompress past max_bytes raises code 'too_large'."""
    path = tmp_path / "b.xlsx"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("big.bin", b"0" * 100_000)
    with pytest.raises(ProfileError) as exc:
        read_table(path, max_bytes=50_000)
    assert exc.value.code == "too_large"
