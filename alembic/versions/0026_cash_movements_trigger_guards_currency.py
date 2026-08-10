"""cash_movements_no_update: guard the new currency column (CUR-02)

Revision ID: 0026
Revises: 0025
Create Date: 2026-08-10

LOCKSTEP RULE fix: migration 0024 added `cash_movements.currency` but did not
update the `cash_movements_no_update` append-only trigger created by 0018 to
guard it — an oversight caught by
`tests/test_append_only_cursor.py::test_trigger_column_list_matches_schema`.
Without this, `currency` would be silently mutable on an already-synced cash
row (a fail-open in the append-only ledger invariant).

Migration 0018 itself is NOT edited retroactively (already-applied
migrations are historical fact) — this migration re-applies its exact
DROP/CREATE technique with `currency` added to the WHEN clause. The
`operations_no_update` trigger is untouched (Operation gained no new column
in this plan). `app.db.APPEND_ONLY_TRIGGERS` (the live source for test
fixtures, which build schema via `Base.metadata.create_all`, never Alembic)
and `tests/test_append_only_cursor.py::IMMUTABLE_CASH_COLUMNS` move together
with this file in the same commit (LOCKSTEP RULE, per 0018's docstring).

Null-safety per dialect, same as 0018: SQLite uses `IS NOT`; PostgreSQL uses
`IS DISTINCT FROM`. The PL/pgSQL function `cash_movements_append_only()`
created by 0013 is reused unchanged — only the trigger is replaced.

Immutability rule (WR-06): this file never imports application modules —
stdlib + sqlalchemy + alembic.op only. All DDL below is a literal string
constant; no value is ever interpolated into SQL.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None

_SQLITE_DDL: tuple[str, ...] = (
    "DROP TRIGGER IF EXISTS cash_movements_no_update",
    """
    CREATE TRIGGER cash_movements_no_update
    BEFORE UPDATE ON cash_movements
    FOR EACH ROW WHEN
         NEW.id           IS NOT OLD.id
      OR NEW.category     IS NOT OLD.category
      OR NEW.amount_cents IS NOT OLD.amount_cents
      OR NEW.currency     IS NOT OLD.currency
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
    "DROP TRIGGER IF EXISTS cash_movements_no_update ON cash_movements",
    """CREATE TRIGGER cash_movements_no_update BEFORE UPDATE ON cash_movements
       FOR EACH ROW WHEN (
            NEW.id           IS DISTINCT FROM OLD.id
         OR NEW.category     IS DISTINCT FROM OLD.category
         OR NEW.amount_cents IS DISTINCT FROM OLD.amount_cents
         OR NEW.currency     IS DISTINCT FROM OLD.currency
         OR NEW.note         IS DISTINCT FROM OLD.note
         OR NEW.sale_id      IS DISTINCT FROM OLD.sale_id
         OR NEW.author_id    IS DISTINCT FROM OLD.author_id
         OR NEW.device_id    IS DISTINCT FROM OLD.device_id
         OR NEW.seq          IS DISTINCT FROM OLD.seq
         OR NEW.created_at   IS DISTINCT FROM OLD.created_at
         OR NEW.created_by   IS DISTINCT FROM OLD.created_by
       ) EXECUTE FUNCTION cash_movements_append_only()""",
)

# --- downgrade: restore the 0018/0024-era guard (no currency column) -------

_SQLITE_DOWNGRADE_DDL: tuple[str, ...] = (
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

_PG_DOWNGRADE_DDL: tuple[str, ...] = (
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
