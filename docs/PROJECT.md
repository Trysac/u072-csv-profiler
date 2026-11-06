# Project record

## Objective

Profile a CSV or XLSX sheet: inferred types, nulls, duplicates, ranges, top values and warnings, as JSON or a script-free self-contained HTML page. The goal is a first look at an unknown spreadsheet in seconds, from a terminal or from Python, with a single small runtime dependency.

## Scope

- In scope: `read_table`, `profile`, `render_json`, `render_html`, `ProfileError` and the command line interface, for `.csv`, `.tsv`, `.txt` and `.xlsx` files.
- In scope: the public API documented in [README.md](../README.md).
- Out of scope: Parquet, JSON, `.xls`, charts, correlations, streaming, and locale-specific number or date formats.
- Out of scope: anything that needs runtime dependencies beyond openpyxl, or I/O beyond reading the input file, without an accepted ADR.

## Timeline

| Date | Event |
|---|---|
| 2026 | Repository created from the factory utility template. |

## Effort metrics

Measured values only; a value that has not been measured stays "pending measurement".

| Metric | Value |
|---|---|
| Tokens (input / output) | 580152 / 139219 |
| Hours (human) | pending measurement |
| Cost (USD) | 1.1190 |

## Factory run u072 (measured from API usage)

| Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|
| generation | claude-sonnet-5-5 | yes | 2665 | 117766 | 0 | 4246 | 0.5919 |
| fix-1 | claude-sonnet-5-5 | no | 8 | 1379 | 20778 | 69055 | 0.0727 |
| fix-2 | claude-sonnet-5-5 | no | 8 | 1709 | 7332 | 55391 | 0.0410 |
| audit | claude-sonnet-5-5 | no | 14 | 5265 | 43459 | 159657 | 0.1773 |
| fix-3 | claude-sonnet-5-5 | no | 8 | 3590 | 26985 | 92089 | 0.1126 |
| fix-4 | claude-sonnet-5-5 | no | 8 | 1592 | 5143 | 58851 | 0.0347 |
| docs | claude-haiku-5-5 | no | 138152 | 7918 | 0 | 0 | 0.0889 |

Total: $1.1190. Prices: Anthropic list prices.
