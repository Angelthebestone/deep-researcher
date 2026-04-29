"""
Centralized serialization utilities for the storage layer.

These functions were previously duplicated between
storage/service.py, storage/operations.py, and storage/documents.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def to_json(value: Any) -> Any:
    """Recursively convert a value to JSON-safe types."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: to_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_json(item) for item in value]
    return value


def coerce_datetime(value: object) -> datetime:
    """Coerce a value to a datetime, defaulting to now(UTC)."""
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.now(UTC)


def optional_error(value: object) -> str | None:
    """Return a stripped string if non-empty, otherwise None."""
    if isinstance(value, str) and value.strip():
        return value
    return None
