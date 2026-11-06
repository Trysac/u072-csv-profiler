# Stack

## Used

| Tool | Why |
|---|---|
| Python >= 3.10 | Minimum version declared for the package. |
| openpyxl 3.x (`>=3.1,<4`) | The only runtime dependency; reads `.xlsx` in read-only, data-only mode. Pure Python, so it can run under Pyodide. |
| Standard library (`csv`, `zipfile`, `zlib`, `re`, `heapq`, `dataclasses`, `json`, `html`) | Parsing, guards, statistics and rendering without extra packages. |

## Discarded

| Tool | Why not |
|---|---|
| pandas and ydata-profiling | Pull in pandas and matplotlib, which the project was created to avoid. |
| Parquet, JSON and `.xls` readers | Out of scope for this version. |
