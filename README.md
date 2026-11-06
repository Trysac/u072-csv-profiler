# csv-profiler

[![PyPI version](https://img.shields.io/pypi/v/trysac-csv-profiler)](https://pypi.org/project/trysac-csv-profiler/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-csv-profiler)](LICENSE)
[![CI](https://github.com/Trysac/u072-csv-profiler/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u072-csv-profiler/actions/workflows/ci.yml)

Profile a CSV or XLSX sheet: inferred types, nulls, duplicates, ranges, top values and warnings, as JSON or a script-free self-contained HTML page

## Problem

Before loading a spreadsheet someone sent, analysts need to know its types, nulls, duplicates and odd values, and they usually discover problems only after the import fails. Popular profilers pull in pandas, plotting libraries and dozens of dependencies. csv-profiler gives the same first look from a terminal or from Python with one small runtime dependency, openpyxl, used only for .xlsx files.

## Install

```sh
pip install trysac-csv-profiler
# or
uv add trysac-csv-profiler
```

Requires Python 3.10 or newer. The only runtime dependency is `openpyxl>=3.1,<4`, used for `.xlsx`.

## Usage

```python
from pathlib import Path
from csv_profiler import profile, read_table, render_json

Path("people.csv").write_text("id,name\n1,Ann\n2,Bob\n", encoding="utf-8")
table = read_table(Path("people.csv"))
report = profile(table)
print(render_json(report))
```

Command line (`python -m csv_profiler` always works; the `csv-profiler` script name depends on the installed package metadata):

```sh
python -m csv_profiler file.csv --format html -o out.html
python -m csv_profiler book.xlsx --sheet Data --format json
```

Options: `--sheet NAME`, `--format json|html`, `-o FILE`, `--max-rows N`, `--delimiter C` (use `tab` or `\t` for tabs). Exit code 0 means success and 2 means an input or usage error.

## Public API

- `read_table(path, *, sheet=None, delimiter=None, encoding='utf-8-sig', max_rows=1_000_000, max_bytes=104_857_600, max_columns=1000) -> Table`. `Table` has `columns: list[str]`, `rows: list[list[str | None]]` and `ragged_rows: int`. When `delimiter` is None the delimiter is sniffed among `,`, `;`, tab and `|`, falling back to comma.
- `profile(table) -> Profile` with `row_count`, `column_count`, `duplicate_row_count`, `columns: list[ColumnProfile]` and `warnings: list[ProfileWarning]`.
- `ColumnProfile` holds `name`, `inferred_type` (integer, float, boolean, date, datetime, string or empty), `null_count`, `null_ratio`, `distinct_count`, `min`, `max`, `mean`, `max_length`, `top_values` (up to five `(value, count)` pairs) and `non_conforming`.
- `ProfileWarning` holds `code`, `column` and `message`. Codes: `constant`, `high_null`, `mixed_types`, `probable_id`, `ragged_rows`.
- `render_json(profile) -> str` (sorted keys, indent 2) and `render_html(profile, *, title) -> str` (one page, inline CSS, every value escaped, no JavaScript, links or external resources).
- `ProfileError` has `code` and `message`. Codes: `empty`, `unsupported_format`, `too_large`, `encoding`, `unknown_sheet`, `cell_too_large`.
- `main(argv=None) -> int` is the command line entry point.

## Errors and limits

`ProfileError.code` is one of `empty`, `unsupported_format`, `too_large`, `encoding`, `unknown_sheet` or `cell_too_large`. Messages are truncated to 200 characters. `read_table` raises `ValueError` for invalid limits or delimiters and `OSError` when the file cannot be read.

Defaults: 1,000,000 rows, 104,857,600 bytes, 1000 columns, 131072 characters per CSV field, and at most 10,000 members in an XLSX archive. The decompressed size of an XLSX archive is checked against `max_bytes` before openpyxl opens it. Integers longer than 300 digits are treated as strings. Mean values are rounded to 6 decimals and top values are truncated to 100 characters. The CLI cannot change `max_bytes`.

## Why not ydata-profiling

ydata-profiling is the best-known Python profiler. It depends on pandas and matplotlib. csv-profiler is a standard-library-based reader plus a small openpyxl dependency, and it produces JSON or a static HTML page without plotting or dataframes.

## Security

See [docs/SECURITY.md](docs/SECURITY.md) for the threat model, what is defended and what is not.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
