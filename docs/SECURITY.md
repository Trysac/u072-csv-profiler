# Security notes

## Threat model

`trysac-csv-profiler` reads one local file per call and never writes files, opens sockets or evaluates input. The inputs are untrusted files, so the library enforces size limits and renders output safely.

### Defended

- **Oversized files**: `read_table` rejects files larger than `max_bytes` (default 104,857,600 bytes) with `too_large`, and rejects more than `max_rows` rows and more than `max_columns` columns.
- **XLSX zip bombs**: the archive must have at most 10,000 members. Each member is read through `ZipFile.open` in 64 KiB chunks with a running total against `max_bytes`, because central-directory sizes can be false. The check runs before openpyxl opens the workbook.
- **Oversized CSV fields**: the default field limit of 131072 characters is enforced by catching the csv error and raising `cell_too_large`. The library does not change the global `csv.field_size_limit`.
- **Invalid encodings**: undecodable CSV bytes raise `encoding` instead of being replaced silently.
- **HTML injection**: every value in `render_html` passes through `html.escape(quote=True)`. The page has no JavaScript, links or external resources.
- **Error text**: `ProfileError` messages are truncated to 200 characters.
- **Code execution**: input is never passed to `eval`, `exec` or a deserializer.

### Not defended

- **Memory and time within limits**: the whole table is held in memory and profiled in full. A file that stays within the limits can still use a large amount of memory or time. There are no timeouts.
- **Sniffing**: delimiter detection looks only at the first 64 KiB, so a misdetected delimiter yields wrong but well-formed output.
- **The CLI cannot set `max_bytes`**: the CLI uses the library default. Use the Python API to change it.
- **openpyxl parsing**: the library relies on openpyxl to parse XLSX XML after the size guard. Vulnerabilities in openpyxl or in its dependencies are not mitigated here.
- **Dependency supply chain**: the only runtime dependency is openpyxl. Its installation and the publishing channel are not verified by this document.
- **Sensitive content in output**: profiles and HTML reports include cell values such as top values and minimum or maximum values. Callers must not publish them if the input is confidential.

To report a vulnerability, see [SECURITY.md](../SECURITY.md).
