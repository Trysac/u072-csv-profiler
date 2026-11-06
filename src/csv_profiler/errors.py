"""Typed errors raised by csv_profiler."""

from __future__ import annotations

from typing import Literal

ErrorCode = Literal[
    "empty",
    "unsupported_format",
    "too_large",
    "encoding",
    "unknown_sheet",
    "cell_too_large",
]

MAX_MESSAGE_CHARS = 200


def clip(value: str, limit: int = 60) -> str:
    """Return ``value`` cut to ``limit`` characters, marking a cut with three dots."""
    if len(value) <= limit:
        return value
    return value[:limit] + "..."


class ProfileError(Exception):
    """Base error of the library.

    Attributes:
        code: stable machine-readable identifier of the failure.
        message: human-readable text, never longer than 200 characters.
    """

    def __init__(self, code: ErrorCode, message: str) -> None:
        text = message[:MAX_MESSAGE_CHARS]
        super().__init__(text)
        self.code: ErrorCode = code
        self.message = text
