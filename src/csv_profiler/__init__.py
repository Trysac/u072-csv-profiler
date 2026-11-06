"""Profile CSV and XLSX files: types, nulls, duplicates, ranges, top values and warnings."""

from __future__ import annotations

import logging

from .errors import ErrorCode, ProfileError
from .profiling import ColumnProfile, Profile, ProfileWarning, profile
from .reader import Table, read_table
from .render import render_html, render_json

__all__ = [
    "ColumnProfile",
    "ErrorCode",
    "Profile",
    "ProfileError",
    "ProfileWarning",
    "Table",
    "__version__",
    "profile",
    "read_table",
    "render_html",
    "render_json",
]

__version__ = "0.1.0"

logging.getLogger(__name__).addHandler(logging.NullHandler())
