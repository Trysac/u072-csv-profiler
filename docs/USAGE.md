# Usage

`csv_profiler` profiles a CSV, TSV, TXT or XLSX file without pandas. The only runtime dependency is
`openpyxl` (>=3.1,<4), used lazily for `.xlsx` files.

## Library

```python
from pathlib import Path

from csv_profiler import profile, read_table, render_html, render_json

table = read_table(Path("people.csv"))
report = profile(table)
print(render_json(report))
Path("people.html").write_text(render_html(report, title="people.csv"), encoding="utf-8")
```

`read_table(path, *, sheet=None, delimiter=None, encoding="utf-8-sig", max_rows=1_000_000,
max_bytes=104_857_600, max_columns=1000)` returns a `Table(columns, rows, ragged_rows)`.

## Command line

```text
csv-profiler <file> [--sheet NAME] [--format json|html] [-o FILE] [--max-rows N] [--delimiter C]
```

Exit code 0 means success, 2 means an input or usage error. The same tool runs with
`python -m csv_profiler`.

## Rules

- Nulls: empty after trimming, or `NA`, `N/A`, `null`, `None`, `NaN` in any case.
- Types: integer, float, boolean (`true`, `false`, `yes`, `no`), date, datetime, string, empty.
  Leading zeros keep a value a string. The inferred type is the narrowest one accepted by at least
  95 percent of the non-null values; the rest are reported as `non_conforming`.
- A float column also accepts integer-looking values, and a datetime column also accepts dates.
- Integers longer than 300 digits and floats that overflow to infinity are treated as strings.
- Rows wider than the header extend it with `column_N` names; short rows are padded with `None`.
  Both count as ragged rows.
- XLSX datetimes at exactly midnight without a time zone are written as plain dates.
- Warning codes: `constant`, `high_null`, `mixed_types`, `probable_id`, `ragged_rows`.

## Limits

Every limit raises `ProfileError` with a stable `code`: `empty`, `unsupported_format`, `too_large`,
`encoding`, `unknown_sheet` or `cell_too_large`. A CSV field longer than 131072 characters is
rejected without touching the global `csv.field_size_limit`. An XLSX archive may hold at most
10,000 members and is decompressed in 64 KiB chunks against `max_bytes` before openpyxl opens it.
