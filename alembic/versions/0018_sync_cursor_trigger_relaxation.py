"""sync cursor: relax the append-only UPDATE triggers to column-scoped guards

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-19

Phase 28 (SRV-02 / SYNC-01), ROADMAP Success Criterion 3: the two ledger
`*_no_update` triggers created by 0001 (`operations_no_update`) and 0013
(`cash_movements_no_update`) block EVERY update, including the harmless
`UPDATE ... SET synced_at = ...` that a client must issue to record that a
row was pushed. This migration drops and re-creates just those two triggers
with a value-based `FOR EACH ROW WHEN` guard that fires only when an
IMMUTABLE column actually changes.

This AMENDS how the SRV-02 guarantee is enforced; it does not weaken it:

  * every immutable column stays immutable (the guard enumerates all of
    them — 14 on operations, 10 on cash_movements);
  * a statement that sets `synced_at` AND an immutable column in one go is
    still rejected (the guard is value-based, not `UPDATE OF`-based, so it
    cannot be evaded by naming extra columns);
  * the two DELETE triggers created by 0001/0013 are NOT referenced here at
    all — deletion stays unconditionally blocked.

Value-based `WHEN` rather than `UPDATE OF`: `UPDATE OF col` fires on the
MENTION of a column in the SET clause, so it would reject the harmless
no-op `SET synced_at = ..., qty_delta = qty_delta` and — worse — its
semantics express "was named", not "was changed". The `WHEN` below
expresses the actual invariant.

Null-safety per dialect: SQLite uses `IS NOT` (universally supported;
`IS DISTINCT FROM` only landed in SQLite 3.39). PostgreSQL uses
`IS DISTINCT FROM`.

PostgreSQL `json` trap: `operations.payload` is `sa.JSON()`, which maps to
PostgreSQL's `json` type, and `json` has NO equality operator — an
uncast `NEW.payload IS DISTINCT FROM OLD.payload` fails with
`operator does not exist: json = json`. The PG guard therefore compares
`NEW.payload::text IS DISTINCT FROM OLD.payload::text`. SQLite stores JSON
as TEXT and needs no cast; `cash_movements` has no JSON column.

The PL/pgSQL functions `operations_append_only()` and
`cash_movements_append_only()` created by 0001/0013 are REUSED unchanged and
are never dropped here — only the two triggers are replaced.

LOCKSTEP RULE: `app.db.APPEND_ONLY_TRIGGERS` is the live source of trigger
DDL for the test fixtures (tests/conftest.py builds every test DB from that
constant plus `Base.metadata.create_all`, never via Alembic). Its SQLite
DDL was updated in the same commit as this file and must always move with
it — if they drift, the whole suite tests the old triggers while production
runs the new ones.

Immutability rule (WR-06): this file must never import application modules —
stdlib + sqlalchemy + alembic.op only. All DDL below is held in module-level
tuples of LITERAL string constants; no value is ever interpolated into SQL.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

# --- v2 (relaxed) triggers -------------------------------------------------

_SQLITE_DDL: tuple[str, ...] = (
    # SQLite grammar: DROP TRIGGER takes NO `ON <table>` clause (CR-01).
    "DROP TRIGGER IF EXISTS operations_no_update",
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
    "DROP TRIGGER IF EXISTS cash_movements_no_update",
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
)

_PG_DDL: tuple[str, ...] = (
    # PG grammar requires `DROP TRIGGER <name> ON <table>` (CR-01).
    "DROP TRIGGER IF EXISTS operations_no_update ON operations",
    """CREATE TRIGGER operations_no_update BEFORE UPDATE ON operations
       FOR EACH ROW WHEN (
            NEW.id               IS DISTINCT FROM OLD.id
         OR NEW.type             IS DISTINCT FROM OLD.type
         OR NEW.product_id       IS DISTINCT FROM OLD.product_id
         OR NEW.qty_delta        IS DISTINCT FROM OLD.qty_delta
         OR NEW.unit_cost_cents  IS DISTINCT FROM OLD.unit_cost_cents
         OR NEW.unit_price_cents IS DISTINCT FROM OLD.unit_price_cents
         OR NEW.payload::text    IS DISTINCT FROM OLD.payload::text
         OR NEW.sale_id          IS DISTINCT FROM OLD.sale_id
         OR NEW.batch_id         IS DISTINCT FROM OLD.batch_id
         OR NEW.author_id        IS DISTINCT FROM OLD.author_id
         OR NEW.device_id        IS DISTINCT FROM OLD.device_id
         OR NEW.seq              IS DISTINCT FROM OLD.seq
         OR NEW.created_at       IS DISTINCT FROM OLD.created_at
         OR NEW.created_by       IS DISTINCT FROM OLD.created_by
       ) EXECUTE FUNCTION operations_append_only()""",
    "DROP TRIGGER IF EXISTS cash_movements_no_update ON cash_movements",
    """CREATE TRIGGER cash_movements_no_update BEFORE UPDATE ON cash_movements
       FOR EACH ROW WHEN (
            NEW.id           IS DISTINCT FROM OLD.id
         OR NEW.category     IS DISTINCT FROM OLD.category
         OR NEW.amount_cents IS DISTINCT FROM OLD.amount_cents
         OR NEW.note         IS DISTINCT FROM OLD.note
         OR NEW.sale_id      IS DISTINCT FROM OLD.sale_id
         OR NEW.author_id    IS DISTINCT FROM OLD.author_id
         OR NEW.device_id    IS DISTINCT FROM OLD.device_id
         OR NEW.seq          IS DISTINCT FROM OLD.seq
         OR NEW.created_at   IS DISTINCT FROM OLD.created_at
         OR NEW.created_by   IS DISTINCT FROM OLD.created_by
       ) EXECUTE FUNCTION cash_movements_append_only()""",
)

# --- v1 (unconditional) triggers, restored on downgrade --------------------
# Byte-for-behaviour identical to the forms frozen in 0001 and 0013.

_SQLITE_DOWNGRADE_DDL: tuple[str, ...] = (
    "DROP TRIGGER IF EXISTS operations_no_update",
    """
    CREATE TRIGGER operations_no_update
    BEFORE UPDATE ON operations
    BEGIN SELECT RAISE(ABORT, 'operations ledger is append-only'); END
    """,
    "DROP TRIGGER IF EXISTS cash_movements_no_update",
    """
    CREATE TRIGGER cash_movements_no_update
    BEFORE UPDATE ON cash_movements
    BEGIN SELECT RAISE(ABORT, 'cash ledger is append-only'); END
    """,
)

_PG_DOWNGRADE_DDL: tuple[str, ...] = (
    "DROP TRIGGER IF EXISTS operations_no_update ON operations",
    """CREATE TRIGGER operations_no_update BEFORE UPDATE ON operations
       FOR EACH ROW EXECUTE FUNCTION operations_append_only()""",
    "DROP TRIGGER IF EXISTS cash_movements_no_update ON cash_movements",
    """CREATE TRIGGER cash_movements_no_update BEFORE UPDATE ON cash_movements
       FOR EACH ROW EXECUTE FUNCTION cash_movements_append_only()""",
)


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for stmt in _PG_DDL:
            op.execute(stmt)
    else:  # sqlite
        for stmt in _SQLITE_DDL:
            op.execute(stmt)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for stmt in _PG_DOWNGRADE_DDL:
            op.execute(stmt)
    else:  # sqlite
        for stmt in _SQLITE_DOWNGRADE_DDL:
            op.execute(stmt)
