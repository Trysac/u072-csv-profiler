"""Read CSV and XLSX files into a :class:`Table` with strict size limits."""

from __future__ import annotations

import csv
import importlib
import io
import logging
import math
import zipfile
import zlib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from .errors import ProfileError, clip

logger = logging.getLogger(__name__)

DEFAULT_MAX_ROWS = 1_000_000
DEFAULT_MAX_BYTES = 104_857_600
DEFAULT_MAX_COLUMNS = 1000
MAX_CELL_CHARS = 131_072
MAX_ZIP_MEMBERS = 10_000
SNIFF_SAMPLE_CHARS = 65_536

_CHUNK_BYTES = 65_536
_SNIFF_DELIMITERS = ",;\t|"
_FORBIDDEN_DELIMITERS = '\r\n"'
_CSV_SUFFIXES = frozenset({".csv", ".tsv", ".txt"})
_XLSX_SUFFIXES = frozenset({".xlsx"})
_EOCD_SIGNATURE = b"PK\x05\x06"
_EOCD_SIZE = 22
_MAX_ZIP_COMMENT = 65_535
_ARCHIVE_ERRORS = (
    zipfile.BadZipFile,
    zlib.error,
    RuntimeError,
    NotImplementedError,
    EOFError,
)
_CELL_MESSAGE = "a cell exceeds the 131072 character limit"
_BAD_XLSX = "the file is not a readable XLSX workbook"
_BAD_ZIP = "the file is not a valid ZIP archive"
_TOO_MANY_MEMBERS = "the archive has too many members"


@dataclass(frozen=True)
class Table:
    """A parsed table: unique column names, padded string rows and the ragged row count."""

    columns: list[str]
    rows: list[list[str | None]]
    ragged_rows: int = 0


def read_table(
    path: Path,
    *,
    sheet: str | None = None,
    delimiter: str | None = None,
    encoding: str = "utf-8-sig",
    max_rows: int = DEFAULT_MAX_ROWS,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_columns: int = DEFAULT_MAX_COLUMNS,
) -> Table:
    """Read a ``.csv``, ``.tsv``, ``.txt`` or ``.xlsx`` file into a :class:`Table`.

    Args:
        path: file to read; its suffix selects the format.
        sheet: worksheet name for XLSX (first sheet when ``None``); ignored for CSV.
        delimiter: single CSV delimiter; sniffed among ``, ; tab |`` when ``None``.
        encoding: text encoding of CSV files.
        max_rows: maximum number of data rows.
        max_bytes: maximum file size, and maximum decompressed size of an XLSX archive.
        max_columns: maximum number of columns.

    Raises:
        ProfileError: ``empty``, ``unsupported_format``, ``too_large``, ``encoding``,
            ``unknown_sheet`` or ``cell_too_large``.
        ValueError: a limit or the delimiter is not valid.
        OSError: the file cannot be read.
    """
    _require_positive("max_rows", max_rows)
    _require_positive("max_bytes", max_bytes)
    _require_positive("max_columns", max_columns)
    _check_delimiter(delimiter)
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix not in _CSV_SUFFIXES and suffix not in _XLSX_SUFFIXES:
        raise ProfileError("unsupported_format", f"unsupported file type: {clip(suffix)}")
    size = source.stat().st_size
    if size == 0:
        raise ProfileError("empty", "the file is empty")
    if size > max_bytes:
        raise ProfileError("too_large", f"the file exceeds {max_bytes} bytes")
    if suffix in _XLSX_SUFFIXES:
        table = _read_xlsx(source, sheet, max_rows, max_bytes, max_columns)
    else:
        table = _read_csv(source, delimiter, encoding, max_rows, max_bytes, max_columns)
    logger.debug("read table: %d columns, %d rows", len(table.columns), len(table.rows))
    return table


def _require_positive(name: str, value: int) -> None:
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")


def _check_delimiter(delimiter: str | None) -> None:
    if delimiter is None:
        return
    if len(delimiter) != 1 or delimiter in _FORBIDDEN_DELIMITERS:
        raise ValueError("delimiter must be one character, not a quote or newline")


def _read_csv(
    path: Path,
    delimiter: str | None,
    encoding: str,
    max_rows: int,
    max_bytes: int,
    max_columns: int,
) -> Table:
    with path.open("rb") as handle:
        data = handle.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ProfileError("too_large", f"the file exceeds {max_bytes} bytes")
    text = _decode(data, encoding)
    if not text.strip():
        raise ProfileError("empty", "the file has no content")
    separator = delimiter or _sniff_delimiter(text)
    try:
        rows = csv.reader(io.StringIO(text, newline=""), delimiter=separator)
        return _assemble(_checked_rows(rows), max_rows, max_columns, True)
    except csv.Error as exc:
        if "field larger than field limit" in str(exc):
            raise ProfileError("cell_too_large", _CELL_MESSAGE) from None
        raise ProfileError("encoding", "the CSV content is malformed") from None


def _decode(data: bytes, encoding: str) -> str:
    try:
        text = data.decode(encoding)
    except UnicodeDecodeError:
        raise ProfileError("encoding", f"the file is not valid {clip(encoding, 30)}") from None
    except LookupError:
        raise ProfileError("encoding", "unknown text encoding") from None
    return text[1:] if text.startswith("\ufeff") else text


def _sniff_delimiter(text: str) -> str:
    sample = text[:SNIFF_SAMPLE_CHARS]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=_SNIFF_DELIMITERS)
    except csv.Error:
        return ","
    return dialect.delimiter if dialect.delimiter in _SNIFF_DELIMITERS else ","


def _checked_rows(rows: Iterable[list[str]]) -> Iterator[list[str | None]]:
    for row in rows:
        for cell in row:
            if len(cell) > MAX_CELL_CHARS:
                raise ProfileError("cell_too_large", _CELL_MESSAGE)
        cells: list[str | None] = list(row)
        yield cells


def _assemble(
    rows: Iterable[list[str | None]],
    max_rows: int,
    max_columns: int,
    count_ragged: bool,
) -> Table:
    header: list[str | None] | None = None
    body: list[list[str | None]] = []
    ragged = 0
    for row in rows:
        if not row:
            continue
        if len(row) > max_columns:
            raise ProfileError("too_large", f"more than {max_columns} columns")
        if header is None:
            header = row
            continue
        if len(body) >= max_rows:
            raise ProfileError("too_large", f"more than {max_rows} data rows")
        if count_ragged and len(row) != len(header):
            ragged += 1
        body.append(row)
    if header is None:
        raise ProfileError("empty", "the input has no header row")
    width = max([len(header), *(len(row) for row in body)])
    names = [(cell or "").strip() for cell in header]
    names.extend([""] * (width - len(names)))
    for row in body:
        row.extend([None] * (width - len(row)))
    return Table(columns=_unique_names(names), rows=body, ragged_rows=ragged)


def _unique_names(raw: list[str]) -> list[str]:
    used: set[str] = set()
    result: list[str] = []
    for position, name in enumerate(raw, start=1):
        base = name or f"column_{position}"
        candidate = base
        suffix = 2
        while candidate in used:
            candidate = f"{base}_{suffix}"
            suffix += 1
        used.add(candidate)
        result.append(candidate)
    return result


def _read_xlsx(
    path: Path,
    sheet: str | None,
    max_rows: int,
    max_bytes: int,
    max_columns: int,
) -> Table:
    _check_archive(path, max_bytes)
    try:
        workbook = _load_workbook(str(path))
    except ProfileError:
        raise
    except Exception as exc:
        raise ProfileError("unsupported_format", _BAD_XLSX) from exc
    try:
        target = _pick_sheet(list(workbook.worksheets), sheet)
        return _assemble(_xlsx_rows(target), max_rows, max_columns, False)
    except ProfileError:
        raise
    except Exception as exc:
        raise ProfileError("unsupported_format", _BAD_XLSX) from exc
    finally:
        workbook.close()


def _load_workbook(path: str) -> Any:
    try:
        module = importlib.import_module("openpyxl")
    except ImportError as exc:
        raise ProfileError("unsupported_format", "XLSX support requires openpyxl") from exc
    return module.load_workbook(path, read_only=True, data_only=True)


def _pick_sheet(worksheets: list[Any], name: str | None) -> Any:
    if not worksheets:
        raise ProfileError("empty", "the workbook has no worksheets")
    if name is None:
        return worksheets[0]
    for candidate in worksheets:
        if candidate.title == name:
            return candidate
    raise ProfileError("unknown_sheet", f"no sheet named {clip(name)}")


def _xlsx_rows(sheet: Any) -> Iterator[list[str | None]]:
    for values in sheet.iter_rows(values_only=True):
        end = len(values)
        while end > 0 and values[end - 1] is None:
            end -= 1
        cells = [_cell_text(value) for value in values[:end]]
        for cell in cells:
            if cell is not None and len(cell) > MAX_CELL_CHARS:
                raise ProfileError("cell_too_large", _CELL_MESSAGE)
        yield cells


def _cell_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        midnight = value.hour == value.minute == value.second == value.microsecond == 0
        if midnight and value.tzinfo is None:
            return value.date().isoformat()
        return value.isoformat()
    if isinstance(value, date | time):
        return value.isoformat()
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isfinite(value) and value.is_integer():
            return str(int(value))
        return repr(value)
    return str(value)


def _declared_member_count(path: Path) -> int | None:
    with path.open("rb") as handle:
        handle.seek(0, io.SEEK_END)
        size = handle.tell()
        handle.seek(max(0, size - _EOCD_SIZE - _MAX_ZIP_COMMENT))
        tail = handle.read()
    start = tail.rfind(_EOCD_SIGNATURE)
    if start < 0 or len(tail) < start + _EOCD_SIZE:
        return None
    return int.from_bytes(tail[start + 10 : start + 12], "little")


def _check_archive(path: Path, max_bytes: int) -> None:
    declared = _declared_member_count(path)
    if declared is not None and declared > MAX_ZIP_MEMBERS:
        raise ProfileError("too_large", _TOO_MANY_MEMBERS)
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > MAX_ZIP_MEMBERS:
                raise ProfileError("too_large", _TOO_MANY_MEMBERS)
            total = 0
            for info in members:
                total = _drain(archive, info, total, max_bytes)
    except _ARCHIVE_ERRORS as exc:
        raise ProfileError("unsupported_format", _BAD_ZIP) from exc


def _drain(archive: zipfile.ZipFile, info: zipfile.ZipInfo, total: int, max_bytes: int) -> int:
    with archive.open(info) as member:
        while True:
            chunk = member.read(_CHUNK_BYTES)
            if not chunk:
                return total
            total += len(chunk)
            if total > max_bytes:
                raise ProfileError("too_large", "the archive expands beyond the byte limit")
