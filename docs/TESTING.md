# Testing

## Running

```sh
uv run pytest --cov=csv_profiler   # tests with coverage report
```

The test modules are not part of the source snapshot reviewed for this document, so this file does not list test file names. The behaviours that the tests must cover are the acceptance criteria in the project specification:

- `read_table`: delimiter detection for `,`, `;`, tab and `|`; UTF-8 BOM stripping so the first header is `id`; explicit `delimiter=';'`; ragged rows padded with None and counted in the `ragged_rows` warning.
- Type inference: integers with one non-conforming value give `mixed_types`; leading-zero values such as `007` stay string; the null tokens `NA`, `n/a`, `null`, `None` and empty; datetime with `Z`; boolean `YES`; float `1e5`.
- Strings for `1,5`, `1.5.2`, Arabic-Indic digits, `2024-02-30` and `2024-01-01x10:00`; duplicate rows; header renaming to `column_1`, `a`, `a_2`.
- Numeric min, max and mean; top values ordered by count descending then value ascending; `render_json` output compared to a golden.
- Warnings `constant`, `high_null`, `mixed_types`, `probable_id` and `ragged_rows`.
- XLSX: named sheet profiled, dates as ISO strings, `3.0` as `3`, `unknown_sheet`, and `too_large` raised before openpyxl opens an archive whose members expand beyond `max_bytes`.
- `render_html` escapes `<script>` and the output contains none of `<script`, `src=`, `href=` or `http`.
- Errors: `empty`, `unsupported_format`, `too_large` at `max_bytes + 1`, `cell_too_large` over 131072 characters; the CLI returns 2 for each and 0 on success.

## Policy

- Tests use the public API (`import csv_profiler`) and assert return values, exceptions and messages.
- Tests create CSV and XLSX files in `tmp_path`.
- Tests must not depend on the network, the wall clock or test order.
