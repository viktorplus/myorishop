"""ledger business_date + reversal links, and the append-only guards for them

Revision ID: 0027
Revises: 0026
Create Date: 2026-09-04

Adds four nullable columns to the two append-only ledger tables and teaches
both `*_no_update` triggers to guard them:

  * `operations.business_date`            (DATE-03/DATE-08)
  * `operations.reverses_op_id`           (Phase 34, ships UNUSED)
  * `cash_movements.business_date`        (DATE-03/DATE-08)
  * `cash_movements.reverses_movement_id` (Phase 34, ships UNUSED)

LOCKSTEP RULE — five artifacts move in the SAME commit as this file:
this migration (both dialect branches AND both `downgrade()` halves),
`app.db.APPEND_ONLY_TRIGGERS` (the live source of trigger DDL for the test
fixtures, which build schema via `Base.metadata.create_all`, never Alembic),
`tests/test_append_only_cursor.py::IMMUTABLE_OPERATION_COLUMNS` and
`::IMMUTABLE_CASH_COLUMNS`, and the four model columns in `app/models.py`.
Migration 0026 exists solely because that lockstep was missed once, for
`cash_movements.currency`: the column was added by 0024 and stayed silently
mutable on an already-synced row until 0026 repaired the guard. A ledger
column that no trigger names fails OPEN, and says nothing.

Migrations 0018, 0024 and 0026 are NOT edited retroactively — an applied
migration is historical fact, and a correction ships as a NEW revision. That
rule applies to a known real defect too: `0024.downgrade()` drops its column
inside `op.batch_alter_table`, and Alembic's `SQLiteImpl` recreates the table
for every batch operation except `add_column` / `create_index` /
`drop_index`; SQLite drops a table's triggers with the table, so
`alembic downgrade 0023` silently leaves the cash ledger unguarded. That
defect is deliberately OUT OF SCOPE here — it is named so the next author
does not copy its shape, and it is pinned by
`tests/test_migrations.py::test_downgrade_upgrade_roundtrip_preserves_triggers`.
Nothing below ever uses `op.batch_alter_table`.

Column shape: all four columns are nullable and carry NO column-level value
of any kind — neither a Python-side one nor a DDL one. Two reasons, both
executed rather than assumed. (1) SQLAlchemy 2.0.51 removes a `None`-valued
key from the emitted INSERT and substitutes the column's Python-side value,
so any such value would silently convert a pre-0027 client's DELIBERATE NULL
into a date — destroying DATE-08's NULL sentinel, which the read-time
COALESCE bucketing depends on. (2) A DDL-level value that is a
`ClauseElement` flips Alembic's `requires_recreate_in_batch` to True, which
would take all four triggers down on the way UP. Neither reversal-link
column gets a native FK constraint: the ORM `ForeignKey` in `app/models.py`
supplies merge insert-ordering and PostgreSQL portability, while the bare
native column means a reversal whose target has not arrived yet renders as a
dangling link instead of rolling back an entire push (the shipped
`sale_id` / `batch_id` / `author_id` precedent).

Null-safety per dialect, same as 0018/0026: SQLite uses `IS NOT`;
PostgreSQL uses `IS DISTINCT FROM`.

PostgreSQL `json` trap (carried from 0018, not from 0026 — 0026 only touched
`cash_movements`, which has no JSON column): `operations.payload` is
`sa.JSON()`, mapping to PostgreSQL's `json`, which has NO equality operator.
An uncast `NEW.payload IS DISTINCT FROM OLD.payload` fails with
`operator does not exist: json = json`, so the PG guard compares
`NEW.payload::text IS DISTINCT FROM OLD.payload::text`. The PL/pgSQL
functions `operations_append_only()` and `cash_movements_append_only()`
created by 0001/0013 are REUSED unchanged and never re-created here.

FLEET DIVERGENCE (named and ACCEPTED, not solved — 33-ROLLOUT.md §3): the
business date is the operator's LOCAL calendar day, resolved against
whichever `display_tz` the machine writing the row runs. A client configured
with a `display_tz` different from the server's will therefore compute a
DIFFERENT business date for the same row near local midnight, and the two
sides will disagree about which bookkeeping period it belongs to. Today this
is theoretical: `DISPLAY_TZ` is unset on the server and falls back to
`Europe/Moscow`. It becomes live the moment any deployment sets `DISPLAY_TZ`
to something else — re-read 33-ROLLOUT.md §1 before any timezone change.

Immutability rule (WR-06): this file never imports application modules —
stdlib + sqlalchemy + alembic.op only. That is why the timezone below is a
file-local literal instead of a read of `app.config`; the shipped precedent
is `_DEFAULT_CURRENCY = "RUB"` in
`alembic/versions/0024_cash_movement_currency.py:30`. Every SQL statement in
this file is a literal string constant; the only per-row value is passed as
a BOUND PARAMETER, never interpolated.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None

# The effective `display_tz` of the deployment this revision was written for,
# MEASURED read-only on the server 2026-09-04 and recorded in
# `.planning/phases/33-back-dated-operations/33-ROLLOUT.md` §1 — not guessed
# from the application default. Baked in as a literal because a migration may
# never import app code (WR-06): an applied migration must keep producing the
# same result even after `app/` changes underneath it.
_DISPLAY_TZ = "Europe/Moscow"

# --- backfill statements (literal constants, bound per-row parameters) -----

_BACKFILL_SELECT: tuple[str, ...] = (
    "SELECT id, created_at FROM operations WHERE business_date IS NULL",
    "SELECT id, created_at FROM cash_movements WHERE business_date IS NULL",
)

_BACKFILL_UPDATE: tuple[str, ...] = (
    "UPDATE operations SET business_date = :bd WHERE id = :id",
    "UPDATE cash_movements SET business_date = :bd WHERE id = :id",
)

# --- v4 triggers: the four new columns joined to the WHEN enumerations -----
# Whitespace-normalised-identical to `app.db.APPEND_ONLY_TRIGGERS`, which
# `tests/test_migrations.py::test_alembic_head_triggers_match_app_db` diffs as
# a whole map (name -> DDL) against what `alembic upgrade head` really builds.

_SQLITE_DDL: tuple[str, ...] = (
    # SQLite grammar: DROP TRIGGER takes NO `ON <table>` clause.
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
      OR NEW.reverses_op_id   IS NOT OLD.reverses_op_id
      OR NEW.author_id        IS NOT OLD.author_id
      OR NEW.device_id        IS NOT OLD.device_id
      OR NEW.seq              IS NOT OLD.seq
      OR NEW.created_at       IS NOT OLD.created_at
      OR NEW.business_date    IS NOT OLD.business_date
      OR NEW.created_by       IS NOT OLD.created_by
    BEGIN SELECT RAISE(ABORT, 'operations ledger is append-only'); END
    """,
    "DROP TRIGGER IF EXISTS cash_movements_no_update",
    """
    CREATE TRIGGER cash_movements_no_update
    BEFORE UPDATE ON cash_movements
    FOR EACH ROW WHEN
         NEW.id                   IS NOT OLD.id
      OR NEW.category             IS NOT OLD.category
      OR NEW.amount_cents         IS NOT OLD.amount_cents
      OR NEW.currency             IS NOT OLD.currency
      OR NEW.note                 IS NOT OLD.note
      OR NEW.sale_id              IS NOT OLD.sale_id
      OR NEW.reverses_movement_id IS NOT OLD.reverses_movement_id
      OR NEW.author_id            IS NOT OLD.author_id
      OR NEW.device_id            IS NOT OLD.device_id
      OR NEW.seq                  IS NOT OLD.seq
      OR NEW.created_at           IS NOT OLD.created_at
      OR NEW.business_date        IS NOT OLD.business_date
      OR NEW.created_by           IS NOT OLD.created_by
    BEGIN SELECT RAISE(ABORT, 'cash ledger is append-only'); END
    """,
)

_PG_DDL: tuple[str, ...] = (
    # PG grammar requires `DROP TRIGGER <name> ON <table>`.
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
         OR NEW.reverses_op_id   IS DISTINCT FROM OLD.reverses_op_id
         OR NEW.author_id        IS DISTINCT FROM OLD.author_id
         OR NEW.device_id        IS DISTINCT FROM OLD.device_id
         OR NEW.seq              IS DISTINCT FROM OLD.seq
         OR NEW.created_at       IS DISTINCT FROM OLD.created_at
         OR NEW.business_date    IS DISTINCT FROM OLD.business_date
         OR NEW.created_by       IS DISTINCT FROM OLD.created_by
       ) EXECUTE FUNCTION operations_append_only()""",
    "DROP TRIGGER IF EXISTS cash_movements_no_update ON cash_movements",
    """CREATE TRIGGER cash_movements_no_update BEFORE UPDATE ON cash_movements
       FOR EACH ROW WHEN (
            NEW.id                   IS DISTINCT FROM OLD.id
         OR NEW.category             IS DISTINCT FROM OLD.category
         OR NEW.amount_cents         IS DISTINCT FROM OLD.amount_cents
         OR NEW.currency             IS DISTINCT FROM OLD.currency
         OR NEW.note                 IS DISTINCT FROM OLD.note
         OR NEW.sale_id              IS DISTINCT FROM OLD.sale_id
         OR NEW.reverses_movement_id IS DISTINCT FROM OLD.reverses_movement_id
         OR NEW.author_id            IS DISTINCT FROM OLD.author_id
         OR NEW.device_id            IS DISTINCT FROM OLD.device_id
         OR NEW.seq                  IS DISTINCT FROM OLD.seq
         OR NEW.created_at           IS DISTINCT FROM OLD.created_at
         OR NEW.business_date        IS DISTINCT FROM OLD.business_date
         OR NEW.created_by           IS DISTINCT FROM OLD.created_by
       ) EXECUTE FUNCTION cash_movements_append_only()""",
)

# --- downgrade: restore the pre-0027 guards (0018 for operations, 0026 for
# --- cash_movements) BEFORE the columns they must stop naming are dropped.

_SQLITE_DOWNGRADE_DDL: tuple[str, ...] = (
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

_PG_DOWNGRADE_DDL: tuple[str, ...] = (
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


def _local_business_date(created_at: str) -> str:
    """`created_at` (UTC ISO-8601 text) -> the operator's LOCAL calendar day.

    NOT a 10-character prefix of `created_at`. A naive UTC cut and the
    timezone-correct value differ for any row written near local midnight, and
    that difference is exactly the DATE-07 byte-identity failure: at
    `Europe/Moscow`, `2026-08-31T21:30:00+00:00` has business date
    `2026-09-01`, while the naive prefix says `2026-08-31` — a sale silently
    moved into the wrong month. (The UTC prefix IS the right fallback at READ
    time for rows that legitimately stay NULL — that is `business_date_expr`,
    plan 33-06. The two rules must not be unified.)

    A malformed timestamp falls back to its leading 10 characters so no row is
    left NULL by a value this migration failed to parse.
    """
    try:
        moment = datetime.fromisoformat(created_at)
    except (TypeError, ValueError):
        return created_at[:10]
    if moment.tzinfo is None:
        # Documented invariant: created_at is UTC ISO text. A naive value is
        # read as UTC, never as the machine's local zone.
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(ZoneInfo(_DISPLAY_TZ)).date().isoformat()


def upgrade() -> None:
    # ORDER IS LOCKED (ROADMAP ordering constraint 3), and this is the single
    # most re-orderable thing in the file:
    #
    #   1. add_column   2. timezone-correct backfill   3. extend the triggers
    #
    # Reversed, the backfill UPDATE trips the guard it just installed and
    # `alembic upgrade head` ABORTS MID-UPGRADE on the live server. The reason
    # the correct order works is mechanical, not lucky: the guard is a
    # VALUE-based `FOR EACH ROW WHEN` over an EXPLICIT column enumeration (not
    # `UPDATE OF`, not "any UPDATE"), so an UPDATE of a column the trigger does
    # not yet name evaluates the WHEN to false and succeeds — for 100% of rows.
    # The identical UPDATE is ABORTed the moment step 3 teaches the trigger
    # that column's name. Shipped precedent: 0024 backfilled `currency` two
    # revisions before 0026 taught the trigger about it, and that order has
    # already run on the production server.
    #
    # Plain `op.add_column` only — NEVER `op.batch_alter_table`. `add_column`
    # is one of the three operations Alembic's SQLiteImpl does NOT turn into a
    # move-and-copy table rebuild; every other batch operation would take all
    # four append-only triggers down with the table (the 0024 defect named in
    # the module docstring).

    # 1. the four columns — nullable, valueless, no native FK constraint.
    op.add_column("operations", sa.Column("business_date", sa.String(length=10), nullable=True))
    op.add_column("operations", sa.Column("reverses_op_id", sa.String(length=36), nullable=True))
    op.add_column("cash_movements", sa.Column("business_date", sa.String(length=10), nullable=True))
    op.add_column(
        "cash_movements", sa.Column("reverses_movement_id", sa.String(length=36), nullable=True)
    )

    # 2. backfill every pre-existing row with its timezone-correct local day.
    #    `created_at` itself is never read back out, moved or reinterpreted
    #    (DATE-04) — it is the input to a NEW column, nothing more.
    connection = op.get_bind()
    for select_sql, update_sql in zip(_BACKFILL_SELECT, _BACKFILL_UPDATE, strict=True):
        rows = connection.execute(sa.text(select_sql)).all()
        params = [
            {"bd": _local_business_date(created_at), "id": row_id}
            for row_id, created_at in rows
            if created_at
        ]
        if params:
            connection.execute(sa.text(update_sql), params)

    # 3. only now may the triggers learn the four new names.
    if connection.dialect.name == "postgresql":
        for stmt in _PG_DDL:
            op.execute(stmt)
    else:  # sqlite
        for stmt in _SQLITE_DDL:
            op.execute(stmt)


def downgrade() -> None:
    # The MIRROR of upgrade(), and its order is equally non-optional:
    # restore the pre-0027 guards FIRST, then drop the columns. Executed the
    # other way round, SQLite refuses with
    # `OperationalError: error in trigger ... after drop column:
    #  no such column: NEW.business_date` and leaves the schema half-migrated;
    # PostgreSQL refuses the DROP COLUMN for the same dependency reason.
    # SQLite 3.35+ native DROP COLUMN preserves a table's triggers — but only
    # once no live trigger still names the column.
    #
    # Plain `op.drop_column` — NEVER `op.batch_alter_table`, which is what
    # makes `0024.downgrade()` destroy both cash_movements guards.
    if op.get_bind().dialect.name == "postgresql":
        for stmt in _PG_DOWNGRADE_DDL:
            op.execute(stmt)
    else:  # sqlite
        for stmt in _SQLITE_DOWNGRADE_DDL:
            op.execute(stmt)

    op.drop_column("cash_movements", "reverses_movement_id")
    op.drop_column("cash_movements", "business_date")
    op.drop_column("operations", "reverses_op_id")
    op.drop_column("operations", "business_date")
