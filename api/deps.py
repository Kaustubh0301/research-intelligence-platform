"""
Shared FastAPI dependencies for the v1 API.
"""

from __future__ import annotations

from typing import Generator

from sqlalchemy.orm import Session

from db.session import get_session


def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session; commit on success, rollback on exception."""
    with get_session() as session:
        yield session
