# Architecture

## Purpose

`trysac-csv-profiler` (import name `csv_profiler`) reads a CSV, TSV, TXT or XLSX file into a table of strings and profiles each column: inferred type, nulls, duplicates, numeric ranges, top values and warnings. Results are rendered as JSON or as one self-contained HTML page.

## Shape

```text
caller / CLI (__main__.py)
        |
        v
reader.py   read_table: format detection, size limits, delimiter sniffing, XLSX guard
        |  Table(columns, rows, ragged_rows)
        v
profiling.py   profile: type inference, statistics, warnings, duplicate rows
        |  Profile
        v
render.py   render_json, render_html

errors.py   ProfileError, ErrorCode, clip (used by all modules)
__init__.py public re-exports listed in __all__
```

- **Public API**: the names listed in `__all__` of `src/csv_profiler/__init__.py`. Anything else is internal.
- **Errors**: input problems raise `ProfileError` with a stable `code`. Limit or delimiter misuse raises `ValueError`. File access problems raise `OSError`.
- **Side effects**: the library reads files only through `read_table`. It does not write files, use the network, or change global state. The CLI writes the report to stdout or to the file given with `-o`.
- **Logging**: a logger named `csv_profiler` gets a `NullHandler` and is never configured by the library.

## Module notes

- `reader.py` uses the `csv` module for CSV and `zipfile` plus `openpyxl` (imported with `importlib`) for XLSX. Every XLSX member is read in 64 KiB chunks against `max_bytes`.
- `profiling.py` infers types from regular expressions and `date` or `datetime` parsing. A type is chosen when at least 95 percent of non-null values conform.
- `render.py` escapes every value with `html.escape(quote=True)`.
