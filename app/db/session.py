"""Database session, engine configuration, and connectivity verification."""

import logging
from typing import Generator, Tuple
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Create SQLAlchemy engine with settings
# Note: In production and runtime, PostgreSQL is required.
# SQLite is permitted only in isolated testing environments where explicitly configured.
db_url = settings.get_database_url_str()

engine_kwargs = {
    "pool_pre_ping": True,
}

if "sqlite" in db_url.lower():
    # SQLite specific args for testing isolation
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update({
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "connect_args": {"connect_timeout": settings.db_timeout_seconds},
    })

engine = create_engine(db_url, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency for obtaining database sessions in API requests."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> Tuple[bool, str]:
    """
    Verify whether the database accepts connections and executes queries.
    Never exposes database passwords in the returned message.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, "connected"
    except Exception as e:
        logger.warning("Database connectivity check failed: %s", type(e).__name__)
        return False, f"unreachable: {type(e).__name__}"
