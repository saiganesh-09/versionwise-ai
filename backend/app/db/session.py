"""Database engine and session management.

The engine is created lazily so the app can start (and `/health` can respond)
even when the database is unavailable; `/health/ready` reports connectivity.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        if settings.database_url is None:
            raise RuntimeError("DATABASE_URL is not configured.")
        _engine = create_engine(
            str(settings.database_url),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped session."""
    if _SessionLocal is None:
        get_engine()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()


def check_database(timeout_seconds: float = 2.0) -> tuple[bool, str | None]:
    """Ping the database with SELECT 1. Returns (ok, error_detail)."""
    try:
        settings = get_settings()
        if settings.database_url is None:
            return False, "DATABASE_URL not configured"
        engine = create_engine(
            str(settings.database_url),
            connect_args={"connect_timeout": int(timeout_seconds)},
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        return False, type(exc).__name__
