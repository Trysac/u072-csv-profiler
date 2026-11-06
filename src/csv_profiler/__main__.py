"""Command line interface: ``csv-profiler <file>``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .errors import ProfileError, clip
from .profiling import Profile, profile
from .reader import DEFAULT_MAX_ROWS, read_table
from .render import render_html, render_json

_TAB_ALIASES = frozenset({"\\t", "tab"})


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="csv-profiler",
        description="Profile a CSV or XLSX file and print JSON or HTML.",
    )
    parser.add_argument("file", help="path of the .csv, .tsv, .txt or .xlsx file")
    parser.add_argument("--sheet", help="worksheet name (XLSX only)")
    parser.add_argument("--format", choices=("json", "html"), default="json", dest="fmt")
    parser.add_argument("-o", "--output", help="write the report to this file")
    parser.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS, help="row limit")
    parser.add_argument("--delimiter", help="CSV delimiter; auto-detected when omitted")
    return parser


def _fail(message: str) -> int:
    sys.stderr.write(f"csv-profiler: error: {message}\n")
    return 2


def _render(report: Profile, fmt: str, name: str) -> str:
    if fmt == "html":
        return render_html(report, title=name)
    return render_json(report)


def main(argv: list[str] | None = None) -> int:
    """Run the command line tool and return the process exit code.

    Returns 0 on success and 2 for any input or usage error.
    """
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    delimiter = "\t" if args.delimiter in _TAB_ALIASES else args.delimiter
    source = Path(args.file)
    try:
        table = read_table(
            source,
            sheet=args.sheet,
            delimiter=delimiter,
            max_rows=args.max_rows,
        )
    except ProfileError as exc:
        return _fail(f"{exc.code}: {exc}")
    except (OSError, ValueError) as exc:
        return _fail(f"cannot read input: {clip(str(exc), 120)}")
    text = _render(profile(table), args.fmt, source.name)
    if args.output:
        try:
            Path(args.output).write_text(text + "\n", encoding="utf-8")
        except OSError as exc:
            return _fail(f"cannot write output: {clip(str(exc), 120)}")
    else:
        sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
