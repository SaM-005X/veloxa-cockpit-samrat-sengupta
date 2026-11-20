"""Pytest session setup ensuring default local SQLite is hydrated from portable seed on fresh clones."""

from __future__ import annotations

import pytest

from db.database import DatabaseManager
from db.seed import ensure_populated


@pytest.fixture(scope="session", autouse=True)
def _ensure_default_db_hydrated() -> None:
    """Hydrate default veloxa.db from portable seed if running pytest directly on a fresh clone."""
    ensure_populated(DatabaseManager())
