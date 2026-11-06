# Profile with the standard library and openpyxl, with bounded readers

Status: accepted (generated, pending human review)

## Context

Analysts need a first look at a spreadsheet's types, nulls, duplicates and odd values before importing it. Popular profilers depend on pandas and plotting libraries, which is heavy for a terminal tool or a Pyodide page. Input files are untrusted, and XLSX archives can lie about their sizes.

## Decision

Use the csv module and a pure-Python openpyxl (read-only, data-only) as the only dependency, imported lazily. Read every input through explicit limits: byte size, rows, columns, a 131072-character cell check, at most 10,000 archive members, and a chunked decompression count against max_bytes before openpyxl opens an XLSX file. Infer types from each distinct value with strict ASCII regexes and a 95 percent conformance rule. Report problems as warnings, and fail with one ProfileError that carries a stable code. Render JSON and a script-free HTML page that escapes every value.

## Consequences

The tool is small and works in Pyodide. Reading is in memory, so files are capped by max_bytes and there is no streaming. Because the XLSX archive is decompressed once for the guard and once by openpyxl, large workbooks cost double the CPU. Locale formats, Parquet, JSON and .xls are out of scope. Strict regexes mean values such as 1,5 or Arabic-Indic digits stay strings.
