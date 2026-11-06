"""Render a :class:`Profile` as JSON or as one self-contained, script-free HTML page."""

from __future__ import annotations

import html
import json
from dataclasses import asdict

from .profiling import ColumnProfile, Profile, ProfileWarning

_CSS_RULES = [
    "body{font-family:sans-serif;margin:2rem;color:#222;background:#fff}",
    "table{border-collapse:collapse;width:100%}",
    "th,td{border:1px solid #ccc;padding:4px 8px;text-align:left;vertical-align:top}",
    "th{background:#f0f0f0}",
    "code{font-family:monospace}",
    ".warn{color:#8a4b00}",
]

_HEADERS = (
    "Column",
    "Type",
    "Nulls",
    "Null %",
    "Distinct",
    "Min",
    "Max",
    "Mean",
    "Max length",
    "Non-conforming",
    "Top values",
)


def render_json(profile: Profile) -> str:
    """Return ``profile`` as JSON with sorted keys and an indent of two spaces."""
    return json.dumps(asdict(profile), sort_keys=True, indent=2, allow_nan=False)


def render_html(profile: Profile, *, title: str) -> str:
    """Return a single HTML page with inline CSS and every value escaped.

    The page has no JavaScript, no links and no external resources.
    """
    css = "".join(_CSS_RULES)
    heading = "".join(f"<th>{label}</th>" for label in _HEADERS)
    rows = "\n".join(_column_row(column) for column in profile.columns)
    summary = (
        f"<p>{profile.row_count} rows, {profile.column_count} columns, "
        f"{profile.duplicate_row_count} duplicate rows</p>"
    )
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>{_esc(title)}</title>",
        f"<style>{css}</style>",
        "</head>",
        "<body>",
        f"<h1>{_esc(title)}</h1>",
        summary,
        "<h2>Warnings</h2>",
        _warnings_html(profile.warnings),
        "<h2>Columns</h2>",
        "<table>",
        f"<thead><tr>{heading}</tr></thead>",
        f"<tbody>\n{rows}\n</tbody>",
        "</table>",
        "</body>",
        "</html>",
    ]
    return "\n".join(parts) + "\n"


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _cell(value: object) -> str:
    return "-" if value is None else _esc(value)


def _warnings_html(warnings: list[ProfileWarning]) -> str:
    if not warnings:
        return "<p>No warnings.</p>"
    items = []
    for warning in warnings:
        scope = "" if warning.column is None else f" [{_esc(warning.column)}]"
        label = f"<strong>{_esc(warning.code)}</strong>{scope}"
        items.append(f'<li class="warn">{label}: {_esc(warning.message)}</li>')
    return "<ul>\n" + "\n".join(items) + "\n</ul>"


def _column_row(column: ColumnProfile) -> str:
    entries = [f"<code>{_esc(value)}</code> ({count})" for value, count in column.top_values]
    cells = [
        _esc(column.name),
        _esc(column.inferred_type),
        _cell(column.null_count),
        f"{column.null_ratio * 100:.1f}%",
        _cell(column.distinct_count),
        _cell(column.min),
        _cell(column.max),
        _cell(column.mean),
        _cell(column.max_length),
        _cell(column.non_conforming),
        "<br>".join(entries),
    ]
    return "<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>"
