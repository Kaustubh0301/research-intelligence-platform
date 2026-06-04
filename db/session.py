"""
Database engine and session factory.
Reads DATABASE_URL from the environment (or .env file).
"""

import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. "
        "Add it to .env or export it before running.\n"
        "Example: postgresql://user:password@localhost:5432/research_platform"
    )

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,   # drops stale connections before use
    echo=False,           # set True to log all SQL for debugging
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@contextmanager
def get_session() -> Session:
    """Context manager that commits on success and rolls back on exception."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ping() -> bool:
    """Return True if the database is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        print(f"Database ping failed: {exc}")
        return False
