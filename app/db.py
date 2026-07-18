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
APPEND_ONLY_TRIGGERS: tuple[str, ...] = (
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
    """
    CREATE TRIGGER cash_movements_no_update
    BEFORE UPDATE ON cash_movements
    BEGIN SELECT RAISE(ABORT, 'cash ledger is append-only'); END
    """,
    """
    CREATE TRIGGER cash_movements_no_delete
    BEFORE DELETE ON cash_movements
    BEGIN SELECT RAISE(ABORT, 'cash ledger is append-only'); END
    """,
)


def build_engine_from_url(url: str) -> Engine:
    """Create a sync engine from a full DB URL, gating SQLite-only side effects.

    SRV-01/SRV-02 (Phase 26): `settings.database_url` is the single source of
    truth (sqlite:///… by default, postgresql+psycopg://… when DATABASE_URL is
    set). The parent-dir mkdir and the PRAGMA connect-listener are SQLite-only
    (Pitfall 3: `PRAGMA …` is a syntax error on PostgreSQL, which enforces FKs
    by default and needs no WAL/busy_timeout), so they run only when the
    resolved dialect is sqlite.
    """
    engine = create_engine(url)
    if engine.dialect.name != "sqlite":
        return engine

    # SQLite file target: ensure the parent directory exists (fresh clone,
    # gitignored data/) before the first connection creates the db file.
    Path(engine.url.database).parent.mkdir(parents=True, exist_ok=True)

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


def build_engine(db_path: str) -> Engine:
    """Create a sync SQLite engine with per-connection PRAGMAs (D-14).

    Kept for the test suite (tests/conftest.py) — lowest blast radius. Delegates
    to build_engine_from_url() with the sqlite file URL so the SQLite path is
    byte-identical to before.
    """
    return build_engine_from_url(f"sqlite:///{db_path}")


engine = build_engine_from_url(settings.database_url)
SessionLocal = sessionmaker(bind=engine)


def get_session():
    """FastAPI dependency: yield a session, closed automatically."""
    with SessionLocal() as session:
        yield session
