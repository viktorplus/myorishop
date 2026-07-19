"""Phase 28 SC-3: the sync cursor can be stamped, the ledger stays immutable.

This module is the SQLite half of the trigger-relaxation proof. The
PostgreSQL half lives in `tests/test_pg_parity.py` (skipped unless
`DATABASE_URL` targets a `postgresql+psycopg://` server) and covers the same
behaviours plus the `json` payload cast that only PG needs.

What migration `0018` changed: `operations_no_update` and
`cash_movements_no_update` used to reject EVERY update. They now carry a
value-based `FOR EACH ROW WHEN` guard and fire only when an IMMUTABLE column
actually changes — so `UPDATE ... SET synced_at = ...` (the push cursor a
client must write to record that a row was synced) succeeds, while every
tamper attempt is still rejected. The DELETE triggers were not touched.

LOCKSTEP RULE: `app.db.APPEND_ONLY_TRIGGERS` is the live source of trigger
DDL for these fixtures (`tests/conftest.py` builds each test DB from
`Base.metadata.create_all` plus that constant, never via Alembic), while
migration `0018` is what runs in production. The two must always move
together — `test_trigger_column_list_matches_schema` and
`test_declared_constants_match_trigger_ddl` below are the tripwires that turn
a drift or a fail-open into a loud red test instead of a silent hole.

Every UPDATE/DELETE here is a raw `text()` statement executed through
`engine.begin()`, so it is the TRIGGER — not the ORM — doing the rejecting.
Rejections are matched on the message substring `append-only`, never on an
exception class (PG raises a driver-specific exception; keeping the same
assertion style across both halves).
"""

import pytest
from sqlalchemy import text

from app.db import APPEND_ONLY_TRIGGERS
from app.models import CashMovement, Operation

# --- The column enumeration the triggers claim to cover --------------------
# Must equal each model's columns MINUS the sync cursor `synced_at`.

IMMUTABLE_OPERATION_COLUMNS: frozenset[str] = frozenset(
    {
        "id",
        "type",
        "product_id",
        "qty_delta",
        "unit_cost_cents",
        "unit_price_cents",
        "payload",
        "sale_id",
        "batch_id",
        "author_id",
        "device_id",
        "seq",
        "created_at",
        "created_by",
    }
)

IMMUTABLE_CASH_COLUMNS: frozenset[str] = frozenset(
    {
        "id",
        "category",
        "amount_cents",
        "note",
        "sale_id",
        "author_id",
        "device_id",
        "seq",
        "created_at",
        "created_by",
    }
)

# --- Literal seed constants (no interpolated values — Security V5) ---------

OP_ID = "sc3-op-1"
CASH_ID = "sc3-cash-1"
PRODUCT_ID = "sc3-prod-1"
SEED_TS = "2026-07-19T00:00:00+00:00"
STAMP_TS = "2026-07-19T12:00:00+00:00"

_SEED_PRODUCT = (
    "INSERT INTO products (id, name, quantity, created_at, updated_at) "
    "VALUES ('sc3-prod-1', 'Тест', 0, '2026-07-19T00:00:00+00:00', "
    "'2026-07-19T00:00:00+00:00')"
)
_SEED_OPERATION = (
    "INSERT INTO operations (id, type, product_id, qty_delta, device_id, seq, "
    "created_at, created_by) VALUES ('sc3-op-1', 'receipt', 'sc3-prod-1', 5, "
    "'sc3-dev', 1, '2026-07-19T00:00:00+00:00', 'seed')"
)
_SEED_CASH = (
    "INSERT INTO cash_movements (id, category, amount_cents, device_id, seq, "
    "created_at, created_by) VALUES ('sc3-cash-1', 'sale', 1000, 'sc3-dev', 1, "
    "'2026-07-19T00:00:00+00:00', 'seed')"
)


@pytest.fixture()
def ledger(engine):
    """Seed one operations row and one cash_movements row, committed.

    Every NOT NULL column of each table is named explicitly (authoritative
    source: app/models.py); nullable columns are left unset so the tamper
    cases below have both NULL and non-NULL targets to change.
    """
    with engine.begin() as conn:
        conn.execute(text(_SEED_PRODUCT))
        conn.execute(text(_SEED_OPERATION))
        conn.execute(text(_SEED_CASH))
    return engine


def _stamped(engine, table: str, row_id: str) -> str | None:
    with engine.connect() as conn:
        return conn.execute(
            text(f"SELECT synced_at FROM {table} WHERE id = :id"),  # noqa: S608
            {"id": row_id},
        ).scalar()


# --- The stamp is ALLOWED --------------------------------------------------


def test_synced_at_stamp_allowed(ledger):
    """SYNC-01: stamping the sync cursor on an operations row succeeds."""
    with ledger.begin() as conn:
        conn.execute(
            text("UPDATE operations SET synced_at = :ts WHERE id = :id"),
            {"ts": STAMP_TS, "id": OP_ID},
        )
    assert _stamped(ledger, "operations", OP_ID) == STAMP_TS


def test_cash_synced_at_stamp_allowed(ledger):
    """SYNC-01: stamping the sync cursor on a cash_movements row succeeds."""
    with ledger.begin() as conn:
        conn.execute(
            text("UPDATE cash_movements SET synced_at = :ts WHERE id = :id"),
            {"ts": STAMP_TS, "id": CASH_ID},
        )
    assert _stamped(ledger, "cash_movements", CASH_ID) == STAMP_TS


def test_stamp_same_value_is_a_no_op(ledger):
    """Re-stamping synced_at to the value it already holds is permitted.

    The guard is VALUE-based, so a self-assignment changes nothing and does
    not fire. The PG harness relies on this to stay re-runnable against a
    standing server (its ledger rows can never be deleted).
    """
    for _ in range(2):
        with ledger.begin() as conn:
            conn.execute(
                text("UPDATE operations SET synced_at = :ts WHERE id = :id"),
                {"ts": STAMP_TS, "id": OP_ID},
            )
    assert _stamped(ledger, "operations", OP_ID) == STAMP_TS


# --- Tampering is REJECTED -------------------------------------------------


@pytest.mark.parametrize(
    ("table", "column", "value", "row_id"),
    [
        ("operations", "qty_delta", 99, OP_ID),
        ("operations", "created_by", "attacker", OP_ID),
        ("operations", "author_id", "someone-else", OP_ID),
        ("operations", "type", "writeoff", OP_ID),
        ("operations", "created_at", "1999-01-01T00:00:00+00:00", OP_ID),
        ("cash_movements", "amount_cents", 999999, CASH_ID),
        ("cash_movements", "category", "manual", CASH_ID),
        ("cash_movements", "created_by", "attacker", CASH_ID),
    ],
)
def test_immutable_columns_rejected(ledger, table, column, value, row_id):
    """SRV-02: changing ANY immutable column is still rejected."""
    with pytest.raises(Exception, match="append-only"):
        with ledger.begin() as conn:
            conn.execute(
                text(f"UPDATE {table} SET {column} = :v WHERE id = :id"),  # noqa: S608
                {"v": value, "id": row_id},
            )


def test_mixed_update_rejected(ledger):
    """A single statement setting synced_at AND an immutable column is rejected.

    This is the case an `UPDATE OF synced_at` guard would have failed to
    catch — and the reason the value-based `WHEN` was chosen. The cursor
    stamp must not become a smuggling channel for ledger edits.
    """
    with pytest.raises(Exception, match="append-only"):
        with ledger.begin() as conn:
            conn.execute(
                text(
                    "UPDATE operations SET synced_at = :ts, qty_delta = 99 "
                    "WHERE id = :id"
                ),
                {"ts": STAMP_TS, "id": OP_ID},
            )
    # …and nothing leaked through: the row is untouched.
    assert _stamped(ledger, "operations", OP_ID) is None


def test_mixed_cash_update_rejected(ledger):
    """The cash-ledger equivalent of the mixed-statement smuggling attempt."""
    with pytest.raises(Exception, match="append-only"):
        with ledger.begin() as conn:
            conn.execute(
                text(
                    "UPDATE cash_movements SET synced_at = :ts, amount_cents = 1 "
                    "WHERE id = :id"
                ),
                {"ts": STAMP_TS, "id": CASH_ID},
            )
    assert _stamped(ledger, "cash_movements", CASH_ID) is None


def test_delete_still_rejected(ledger):
    """The relaxation touched only the UPDATE triggers — DELETE stays blocked."""
    for sql in (
        "DELETE FROM operations WHERE id = :id",
        "DELETE FROM cash_movements WHERE id = :id",
    ):
        row_id = OP_ID if "operations" in sql else CASH_ID
        with pytest.raises(Exception, match="append-only"):
            with ledger.begin() as conn:
                conn.execute(text(sql), {"id": row_id})


# --- Fail-open tripwires ---------------------------------------------------

_DRIFT_HINT = (
    "Ledger schema drifted from the append-only trigger guard. A column not "
    "named in the trigger's WHEN clause can be changed FREELY — the ledger "
    "silently fails open. Update BOTH migration 0018 "
    "(alembic/versions/0018_sync_cursor_trigger_relaxation.py) AND "
    "app/db.py::APPEND_ONLY_TRIGGERS, plus the constant in this module, in "
    "the same commit."
)


def test_trigger_column_list_matches_schema():
    """A new ledger column must fail loudly instead of escaping the trigger.

    The guard enumerates columns by name, so a column added to the model
    without a matching trigger update would be mutable — a silent fail-open.
    This asserts the enumeration is exactly "every column except the sync
    cursor", which is the invariant the triggers encode.
    """
    op_columns = {c.key for c in Operation.__mapper__.columns} - {"synced_at"}
    assert op_columns == IMMUTABLE_OPERATION_COLUMNS, _DRIFT_HINT

    cash_columns = {c.key for c in CashMovement.__mapper__.columns} - {"synced_at"}
    assert cash_columns == IMMUTABLE_CASH_COLUMNS, _DRIFT_HINT


def test_declared_constants_match_trigger_ddl():
    """The constants above cannot drift from the DDL they claim to mirror.

    Guards the other direction from the schema check: the constants could be
    correct against the models yet describe a trigger that never names those
    columns.
    """
    ddl = {
        "operations": next(
            t for t in APPEND_ONLY_TRIGGERS if "CREATE TRIGGER operations_no_update" in t
        ),
        "cash_movements": next(
            t
            for t in APPEND_ONLY_TRIGGERS
            if "CREATE TRIGGER cash_movements_no_update" in t
        ),
    }

    for column in IMMUTABLE_OPERATION_COLUMNS:
        assert f"NEW.{column} " in ddl["operations"], (
            f"operations_no_update does not guard {column!r}. {_DRIFT_HINT}"
        )
    for column in IMMUTABLE_CASH_COLUMNS:
        assert f"NEW.{column} " in ddl["cash_movements"], (
            f"cash_movements_no_update does not guard {column!r}. {_DRIFT_HINT}"
        )

    # The cursor itself must NOT be guarded, or the stamp would be rejected.
    assert "NEW.synced_at" not in ddl["operations"]
    assert "NEW.synced_at" not in ddl["cash_movements"]
