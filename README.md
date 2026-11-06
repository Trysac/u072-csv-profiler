# csv-profiler

[![PyPI version](https://img.shields.io/pypi/v/trysac-csv-profiler)](https://pypi.org/project/trysac-csv-profiler/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-csv-profiler)](LICENSE)
[![CI](https://github.com/Trysac/u072-csv-profiler/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u072-csv-profiler/actions/workflows/ci.yml)

Profile a CSV or XLSX sheet: inferred types, nulls, duplicates, ranges, top values and warnings, as JSON or a script-free self-contained HTML page

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-csv-profiler
# or
uv add trysac-csv-profiler
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import csv_profiler

# normalize() trims surrounding whitespace and lower-cases the text.
print(csv_profiler.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    csv_profiler.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
