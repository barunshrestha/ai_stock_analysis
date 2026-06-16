"""Shared dependencies (database manager singleton)."""

from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import HTTPException

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _db_or_none():
    try:
        from database import DatabaseManager

        return DatabaseManager()
    except Exception as exc:
        logger.warning("Database unavailable: %s", exc)
        return None


def get_db():
    """FastAPI dependency: the shared DatabaseManager, or 503 if unavailable."""
    db = _db_or_none()
    if db is None:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable. Check DATABASE_URL in .env.",
        )
    return db
