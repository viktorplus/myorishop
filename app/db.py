"""SQLite engine and session factory (D-12/D-14).

Sync driver only (no aiosqlite). Every pooled connection gets its PRAGMAs
via the connect-event listener — including the autocommit dance required
because sqlite3 silently ignores PRAGMA foreign_keys inside an open
transaction (Pitfall 2, per official SQLAlchemy SQLite dialect docs).
"""

from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Live source of the append-only trigger DDL (FND-01) for TEST FIXTURES.
# Migration 0001 carries its own FROZEN copy (WR-06: migrations must never
# import mutable app code). v1 blocks ALL updates (synced_at unused); the
# v2 sync milestone relaxes the UPDATE trigger with a WHEN clause in a NEW
# migration — never edit this constant's DDL semantics in place without
# also adding that migration.
APPEND_ONLY_TRIGGERS: tuple[str, str] = (
    """
    CREATE TRIGGER operations_no_update
    BEFORE UPDATE ON operations
    BEGIN SELECT RAISE(ABORT, 'operations ledger is append-only'); END
    """,
    """
    CREATE TRIGGER operations_no_delete
    BEFORE DELETE ON operations
    BEGIN SELECT RAISE(ABORT, 'operations ledger is append-only'); END
    """,
)


def build_engine(db_path: str) -> Engine:
    """Create a sync SQLite engine with per-connection PRAGMAs (D-14)."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}")

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        # sqlite3 ignores PRAGMA foreign_keys while autocommit=False.
        autocommit = dbapi_connection.autocommit
        dbapi_connection.autocommit = True
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()
        dbapi_connection.autocommit = autocommit

    return engine


engine = build_engine(settings.db_path)
SessionLocal = sessionmaker(bind=engine)


def get_session():
    """FastAPI dependency: yield a session, closed automatically."""
    with SessionLocal() as session:
        yield session
