"""Tests for the csv-profiler command line interface."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from openpyxl import Workbook

from csv_profiler.__main__ import main


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def make_csv(tmp_path: Path, text: str = "a,b\n1,x\n2,y\n") -> Path:
    path = tmp_path / "d.csv"
    path.write_bytes(text.encode("utf-8"))
    return path


def test_cli_prints_json_and_returns_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, err = run(capsys, str(make_csv(tmp_path)))
    assert code == 0
    assert err == ""
    assert json.loads(out)["row_count"] == 2


def test_cli_writes_html_to_a_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "out.html"
    code, out, err = run(capsys, str(make_csv(tmp_path)), "--format", "html", "-o", str(target))
    assert (code, out, err) == (0, "", "")
    page = target.read_text(encoding="utf-8")
    assert page.startswith("<!DOCTYPE html>")
    assert "<title>d.csv</title>" in page


def test_cli_honours_delimiter_options(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    semicolon = make_csv(tmp_path, "a;b\n1;2\n")
    code, out, _ = run(capsys, str(semicolon), "--delimiter", ";")
    assert code == 0
    assert json.loads(out)["column_count"] == 2
    tabbed = make_csv(tmp_path, "a\tb\n1\t2\n")
    for alias in ("\\t", "tab"):
        code, out, _ = run(capsys, str(tabbed), "--delimiter", alias)
        assert code == 0
        assert json.loads(out)["column_count"] == 2


@pytest.mark.parametrize(
    ("name", "content", "extra", "expected"),
    [
        ("empty.csv", b"", [], "empty"),
        ("data.parquet", b"PAR1", [], "unsupported_format"),
        ("rows.csv", b"a\n1\n2\n", ["--max-rows", "1"], "too_large"),
        ("cell.csv", b"a\n" + b"x" * 131073 + b"\n", [], "cell_too_large"),
        ("bad.csv", b"a,b\n\xff,1\n", [], "encoding"),
    ],
)
def test_cli_returns_two_for_input_errors(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    name: str,
    content: bytes,
    extra: list[str],
    expected: str,
) -> None:
    path = tmp_path / name
    path.write_bytes(content)
    code, out, err = run(capsys, str(path), *extra)
    assert code == 2
    assert out == ""
    assert expected in err


def test_cli_returns_two_for_unknown_sheet(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    book = Workbook()
    book.active.title = "Data"
    book.active.append(["a"])
    path = tmp_path / "b.xlsx"
    book.save(path)
    code, _, err = run(capsys, str(path), "--sheet", "Nope")
    assert code == 2
    assert "unknown_sheet" in err
    code, out, _ = run(capsys, str(path), "--sheet", "Data")
    assert code == 0
    assert json.loads(out)["column_count"] == 1


def test_cli_returns_two_for_missing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, err = run(capsys, str(tmp_path / "missing.csv"))
    assert (code, out) == (2, "")
    assert "cannot read input" in err


def test_cli_returns_two_for_invalid_options(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = str(make_csv(tmp_path))
    assert run(capsys, path, "--delimiter", "ab")[0] == 2
    assert run(capsys, path, "--max-rows", "0")[0] == 2
    assert run(capsys, path, "--max-rows", "many")[0] == 2
    assert run(capsys, path, "--format", "xml")[0] == 2


def test_cli_returns_two_without_arguments(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["csv-profiler"])
    assert main() == 2
    assert "usage" in capsys.readouterr().err.lower()


def test_cli_help_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "--help")
    assert code == 0
    assert "csv-profiler" in out


def test_cli_returns_two_when_output_cannot_be_written(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, _, err = run(capsys, str(make_csv(tmp_path)), "-o", str(tmp_path))
    assert code == 2
    assert "cannot write output" in err
