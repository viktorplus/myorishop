"""SRV-01/SRV-02 PostgreSQL-parity proof harness (Phase 26, Wave 0).

RED in CI until Plans 02-03 land the dialect-branched trigger DDL and the
settings-driven `alembic/env.py` / `app/db.py` wiring. The whole module SKIPS
on SQLite (the local dev default) and RUNS only when `DATABASE_URL` targets a
`postgresql+psycopg://…` server — `settings.database_url` is the single source
of truth (Task 1). PG raises a driver-specific exception (not SQLite's
IntegrityError), so the append-only assertions match on the message SUBSTRING
`append-only` (`operations ledger is append-only` /
`cash ledger is append-only`).

Seed rule: every INSERT names all NOT NULL columns of its target table
(authoritative source: app/models.py) or the INSERT itself would fail on PG
before the append-only trigger can fire. Only literal constant seed values are
used — no external data is f-stringed into any SQL text (Security V5, T-26-03).

Seeds are idempotent (WR-03): append-only ledger inserts use `ON CONFLICT DO
NOTHING` (their rows can never be DELETEd once the triggers are live), and the
Cyrillic product rows are purged before re-insert. The harness can therefore be
re-run against a standing PostgreSQL server without duplicate-key failures.
"""

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from alembic import command
from app.config import settings
from app.models import Product
from app.services.catalog import search_products

# Single source of truth (Task 1): run only against a PostgreSQL target.
pytestmark = pytest.mark.skipif(
    not settings.database_url.startswith("postgresql"),
    reason="PG parity — set DATABASE_URL to a postgresql+psycopg:// URL",
)

# --- Literal seeds (constant strings only; never f-string external data) ---

# products parent row (NOT NULL: id, name, quantity, created_at, updated_at).
_SEED_PRODUCT_UPD = (
    "INSERT INTO products (id, name, quantity, created_at, updated_at) "
    "VALUES ('pg-op-upd-p', 'Тест', 0, '2026-07-18T00:00:00+00:00', "
    "'2026-07-18T00:00:00+00:00') ON CONFLICT DO NOTHING"
)
_SEED_PRODUCT_DEL = (
    "INSERT INTO products (id, name, quantity, created_at, updated_at) "
    "VALUES ('pg-op-del-p', 'Тест', 0, '2026-07-18T00:00:00+00:00', "
    "'2026-07-18T00:00:00+00:00') ON CONFLICT DO NOTHING"
)

# operations row (NOT NULL: id, type, product_id, qty_delta, device_id, seq,
# created_at, created_by; author_id is nullable — omitted).
_SEED_OP_UPD = (
    "INSERT INTO operations (id, type, product_id, qty_delta, device_id, seq, "
    "created_at, created_by) VALUES ('pg-op-upd', 'receipt', 'pg-op-upd-p', 1, "
    "'pg-dev', 1, '2026-07-18T00:00:00+00:00', 'seed') ON CONFLICT DO NOTHING"
)
_SEED_OP_DEL = (
    "INSERT INTO operations (id, type, product_id, qty_delta, device_id, seq, "
    "created_at, created_by) VALUES ('pg-op-del', 'receipt', 'pg-op-del-p', 1, "
    "'pg-dev', 2, '2026-07-18T00:00:00+00:00', 'seed') ON CONFLICT DO NOTHING"
)

# cash_movements row (NOT NULL: id, category, amount_cents, device_id, seq,
# created_at, created_by; author_id is nullable — omitted).
_SEED_CASH = (
    "INSERT INTO cash_movements (id, category, amount_cents, device_id, seq, "
    "created_at, created_by) VALUES ('pg-cash-1', 'sale', 1000, 'pg-dev', 1, "
    "'2026-07-18T00:00:00+00:00', 'seed') ON CONFLICT DO NOTHING"
)


# --- Phase 28 SC-3 seeds: dedicated rows for the relaxed-trigger cases -----
# These rows are used by NO other case in this file. Ledger rows can never be
# DELETEd once the triggers are live, so each SC-3 case owns a fixed UUID and
# stamps a FIXED literal timestamp — a re-run against a standing PG server
# re-stamps the same value, which the value-based WHEN guard permits as a
# no-op, keeping the harness idempotent (WR-03).
_SEED_PRODUCT_SC3 = (
    "INSERT INTO products (id, name, quantity, created_at, updated_at) "
    "VALUES ('pg-sc3-p', 'Тест', 0, '2026-07-19T00:00:00+00:00', "
    "'2026-07-19T00:00:00+00:00') ON CONFLICT DO NOTHING"
)
_SEED_OP_SC3 = (
    "INSERT INTO operations (id, type, product_id, qty_delta, device_id, seq, "
    "created_at, created_by) VALUES ('pg-sc3-op', 'receipt', 'pg-sc3-p', 5, "
    "'pg-dev', 30, '2026-07-19T00:00:00+00:00', 'seed') ON CONFLICT DO NOTHING"
)
_SEED_CASH_SC3 = (
    "INSERT INTO cash_movements (id, category, amount_cents, device_id, seq, "
    "created_at, created_by) VALUES ('pg-sc3-cash', 'sale', 1000, 'pg-dev', 30, "
    "'2026-07-19T00:00:00+00:00', 'seed') ON CONFLICT DO NOTHING"
)
_SC3_STAMP = "2026-07-19T12:00:00+00:00"


def _engine():
    """Engine from the single-source-of-truth URL (postgresql+psycopg://…)."""
    return create_engine(settings.database_url)


def _upgrade_head():
    """Apply the whole migration chain to the PG target (env.py reads settings).

    Idempotent — `head` re-applied against an up-to-date DB is a no-op, so each
    test can call this to guarantee the schema exists without ordering coupling.
    """
    command.upgrade(Config("alembic.ini"), "head")


def test_full_history_applies():
    """SRV-01: the full Alembic history applies to empty PG and produces the
    products / operations / cash_movements tables."""
    _upgrade_head()
    engine = _engine()
    try:
        with engine.connect() as conn:
            for table in ("products", "operations", "cash_movements"):
                exists = conn.execute(
                    text("SELECT to_regclass(:t)"), {"t": table}
                ).scalar()
                assert exists is not None, f"missing table on PG: {table}"
    finally:
        engine.dispose()


def test_cyrillic_search_parity():
    """SRV-01: the Python-folded name_lc shadow-column search returns the same
    rows on PostgreSQL as on SQLite (lowercase-vs-lowercase LIKE is dialect
    independent)."""
    _upgrade_head()
    engine = _engine()
    factory = sessionmaker(bind=engine)
    try:
        with factory() as session:
            # Idempotent seed: products carry no append-only trigger, so purge
            # any rows left by a prior run before re-inserting (WR-03).
            session.execute(
                text("DELETE FROM products WHERE id IN ('pg-cyr-1', 'pg-cyr-2')")
            )
            session.add_all(
                [
                    Product(
                        id="pg-cyr-1",
                        code="CYR-001",
                        name="Крем для рук",
                        name_lc="крем для рук",
                        quantity=0,
                    ),
                    Product(
                        id="pg-cyr-2",
                        code="CYR-002",
                        name="Шампунь",
                        name_lc="шампунь",
                        quantity=0,
                    ),
                ]
            )
            session.commit()
            results = search_products(session, "крем")
            assert {p.id for p in results} == {"pg-cyr-1"}
    finally:
        engine.dispose()


def test_operations_update_rejected():
    """SRV-02: an UPDATE on operations is rejected by the append-only trigger."""
    _upgrade_head()
    engine = _engine()
    try:
        with engine.begin() as conn:
            conn.execute(text(_SEED_PRODUCT_UPD))
            conn.execute(text(_SEED_OP_UPD))
        with pytest.raises(Exception, match="append-only"):
            with engine.begin() as conn:
                conn.execute(
                    text("UPDATE operations SET qty_delta = 99 WHERE id = 'pg-op-upd'")
                )
    finally:
        engine.dispose()


def test_operations_delete_rejected():
    """SRV-02: a DELETE on operations is rejected by the append-only trigger."""
    _upgrade_head()
    engine = _engine()
    try:
        with engine.begin() as conn:
            conn.execute(text(_SEED_PRODUCT_DEL))
            conn.execute(text(_SEED_OP_DEL))
        with pytest.raises(Exception, match="append-only"):
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM operations WHERE id = 'pg-op-del'"))
    finally:
        engine.dispose()


def test_cash_movements_immutable():
    """SRV-02: both UPDATE and DELETE on cash_movements are rejected (the cash
    trigger message `cash ledger is append-only` also contains the substring)."""
    _upgrade_head()
    engine = _engine()
    try:
        with engine.begin() as conn:
            conn.execute(text(_SEED_CASH))
        for sql in (
            "UPDATE cash_movements SET amount_cents = 99 WHERE id = 'pg-cash-1'",
            "DELETE FROM cash_movements WHERE id = 'pg-cash-1'",
        ):
            with pytest.raises(Exception, match="append-only"):
                with engine.begin() as conn:
                    conn.execute(text(sql))
    finally:
        engine.dispose()


# --- Phase 28 SC-3: the relaxed (column-scoped) UPDATE triggers -------------
# The PostgreSQL half of the trigger-relaxation proof introduced by migration
# 0018. The SQLite half lives in tests/test_append_only_cursor.py.


def test_pg_synced_at_stamp_allowed():
    """SYNC-01: stamping the sync cursor on an operations row succeeds on PG.

    Migration 0018 relaxed operations_no_update to fire only when an IMMUTABLE
    column actually changes, so a client can record that it pushed a row.
    """
    _upgrade_head()
    engine = _engine()
    try:
        with engine.begin() as conn:
            conn.execute(text(_SEED_PRODUCT_SC3))
            conn.execute(text(_SEED_OP_SC3))
            conn.execute(
                text(
                    "UPDATE operations SET synced_at = '2026-07-19T12:00:00+00:00' "
                    "WHERE id = 'pg-sc3-op'"
                )
            )
        with engine.connect() as conn:
            stamped = conn.execute(
                text("SELECT synced_at FROM operations WHERE id = 'pg-sc3-op'")
            ).scalar()
        assert stamped == _SC3_STAMP
    finally:
        engine.dispose()


def test_pg_payload_tamper_rejected():
    """Pitfall 1 regression: the `payload` guard needs an explicit ::text cast.

    `operations.payload` is sa.JSON → PostgreSQL `json`, which has NO equality
    operator. Without `NEW.payload::text IS DISTINCT FROM OLD.payload::text` in
    the trigger's WHEN clause, this UPDATE fails with
    `operator does not exist: json = json` — which does NOT match `append-only`
    and so fails this test loudly. Passing proves the cast both compiles and
    actually discriminates.
    """
    _upgrade_head()
    engine = _engine()
    try:
        with engine.begin() as conn:
            conn.execute(text(_SEED_PRODUCT_SC3))
            conn.execute(text(_SEED_OP_SC3))
        with pytest.raises(Exception, match="append-only"):
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "UPDATE operations SET payload = '{\"tampered\": true}'::json "
                        "WHERE id = 'pg-sc3-op'"
                    )
                )
    finally:
        engine.dispose()


def test_pg_immutable_columns_still_rejected():
    """SRV-02 holds after the relaxation: immutable columns stay immutable.

    Includes the mixed-statement case — setting synced_at AND an immutable
    column in one UPDATE is rejected, so the cursor stamp cannot become a
    smuggling channel for ledger edits (this is what a value-based WHEN buys
    over `UPDATE OF`).
    """
    _upgrade_head()
    engine = _engine()
    try:
        with engine.begin() as conn:
            conn.execute(text(_SEED_PRODUCT_SC3))
            conn.execute(text(_SEED_OP_SC3))
        for sql in (
            "UPDATE operations SET qty_delta = 99 WHERE id = 'pg-sc3-op'",
            "UPDATE operations SET created_by = 'attacker' WHERE id = 'pg-sc3-op'",
            "UPDATE operations SET synced_at = '2026-07-19T12:00:00+00:00', "
            "qty_delta = 99 WHERE id = 'pg-sc3-op'",
            "DELETE FROM operations WHERE id = 'pg-sc3-op'",
        ):
            with pytest.raises(Exception, match="append-only"):
                with engine.begin() as conn:
                    conn.execute(text(sql))
    finally:
        engine.dispose()


def test_pg_cash_synced_at_stamp_allowed():
    """SYNC-01: the cash_movements equivalent — stamp allowed, tamper rejected."""
    _upgrade_head()
    engine = _engine()
    try:
        with engine.begin() as conn:
            conn.execute(text(_SEED_CASH_SC3))
            conn.execute(
                text(
                    "UPDATE cash_movements SET "
                    "synced_at = '2026-07-19T12:00:00+00:00' "
                    "WHERE id = 'pg-sc3-cash'"
                )
            )
        with engine.connect() as conn:
            stamped = conn.execute(
                text("SELECT synced_at FROM cash_movements WHERE id = 'pg-sc3-cash'")
            ).scalar()
        assert stamped == _SC3_STAMP

        with pytest.raises(Exception, match="append-only"):
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "UPDATE cash_movements SET amount_cents = 99 "
                        "WHERE id = 'pg-sc3-cash'"
                    )
                )
    finally:
        engine.dispose()
