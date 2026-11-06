"""Behavior tests for the public API of csv_profiler."""

from __future__ import annotations

import pytest

import csv_profiler


def test_normalize_trims_and_lowercases() -> None:
    assert csv_profiler.normalize("  Hello World ") == "hello world"


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_normalize_rejects_blank_input(value: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        csv_profiler.normalize(value)


def test_version_is_semver() -> None:
    parts = csv_profiler.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
