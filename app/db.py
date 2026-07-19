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
# Migrations 0001/0013 carry their own FROZEN v1 copies, and migration
# 0018_sync_cursor_trigger_relaxation.py carries the frozen v2 copy of the
# two *_no_update triggers below (WR-06: migrations must never import
# mutable app code).
#
# LOCKSTEP RULE — this constant and migration 0018 must ALWAYS move together.
# tests/conftest.py builds every test DB from Base.metadata.create_all plus
# this constant, never via Alembic; if the two drift, the whole suite tests
# the old triggers while production runs the new ones. Any future change to
# these triggers needs a NEW migration and a matching edit here in the SAME
# commit.
#
# v2 (Phase 28, SRV-02/SYNC-01): the *_no_update triggers are column-scoped —
# they fire only when an IMMUTABLE column actually changes, so the sync
# cursor `synced_at` can be stamped on a ledger row. Value-based `WHEN`
# rather than `UPDATE OF` on purpose: a statement setting synced_at AND an
# immutable column in one go is still rejected. The *_no_delete triggers are
# unchanged — DELETE stays unconditionally blocked.
APPEND_ONLY_TRIGGERS: tuple[str, ...] = (
    """
    CREATE TRIGGER operations_no_update
    BEFORE UPDATE ON operations
    FOR EACH ROW WHEN
         NEW.id               IS NOT OLD.id
      OR NEW.type             IS NOT OLD.type
      OR NEW.product_id       IS NOT OLD.product_id
      OR NEW.qty_delta        IS NOT OLD.qty_delta
      OR NEW.unit_cost_cents  IS NOT OLD.unit_cost_cents
      OR NEW.unit_price_cents IS NOT OLD.unit_price_cents
      OR NEW.payload          IS NOT OLD.payload
      OR NEW.sale_id          IS NOT OLD.sale_id
      OR NEW.batch_id         IS NOT OLD.batch_id
      OR NEW.author_id        IS NOT OLD.author_id
      OR NEW.device_id        IS NOT OLD.device_id
      OR NEW.seq              IS NOT OLD.seq
      OR NEW.created_at       IS NOT OLD.created_at
      OR NEW.created_by       IS NOT OLD.created_by
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
    FOR EACH ROW WHEN
         NEW.id           IS NOT OLD.id
      OR NEW.category     IS NOT OLD.category
      OR NEW.amount_cents IS NOT OLD.amount_cents
      OR NEW.note         IS NOT OLD.note
      OR NEW.sale_id      IS NOT OLD.sale_id
      OR NEW.author_id    IS NOT OLD.author_id
      OR NEW.device_id    IS NOT OLD.device_id
      OR NEW.seq          IS NOT OLD.seq
      OR NEW.created_at   IS NOT OLD.created_at
      OR NEW.created_by   IS NOT OLD.created_by
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
