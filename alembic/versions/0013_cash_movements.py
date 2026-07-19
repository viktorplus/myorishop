"""cash_movements table

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-14

Adds the FIN-01/02/06 cash ledger foundation: a `cash_movements` table
mirroring `operations`' sync-ready shape (UUID4 TEXT PK, signed integer
amount_cents, device_id/seq, created_at/created_by, nullable sale_id FK)
but dropping all stock-specific columns. Guarded by DB-level BEFORE
UPDATE/DELETE triggers (D-00a append-only guarantee), mirrored in
app.db.APPEND_ONLY_TRIGGERS for test fixtures.

Fresh CREATE TABLE (no batch mode needed — batch is only for ALTER, per
the 0001 precedent).

Immutability rule (WR-06): this file must never import app modules. The
trigger DDL below is a FROZEN copy — replaying the migration chain on a
fresh DB must produce the same history forever. app.db.APPEND_ONLY_TRIGGERS
stays the live source for test fixtures only; future trigger changes go
into new migrations, never edited here.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

# Frozen snapshot of the cash append-only trigger DDL (duplicated from
# app.db.APPEND_ONLY_TRIGGERS on purpose — migrations may duplicate app
# constants, they must not reference them).
_CASH_APPEND_ONLY_TRIGGERS: tuple[str, str] = (
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

# PostgreSQL equivalent of the SQLite append-only triggers above (WR-06:
# ADDITIVE dialect branch only — the SQLite path stays byte-for-behavior
# identical). RAISE(ABORT, …) is SQLite trigger-body syntax and a syntax error
# on PostgreSQL, so PG needs a PL/pgSQL BEFORE UPDATE/DELETE trigger function.
# Trigger NAMES (cash_movements_no_update / cash_movements_no_delete) and the
# 'append-only' message substring are identical across dialects. The message
# wording ('cash ledger is append-only') is preserved exactly as on SQLite.
_PG_CASH_APPEND_ONLY_DDL: tuple[str, str, str] = (
    """CREATE OR REPLACE FUNCTION cash_movements_append_only()
       RETURNS trigger LANGUAGE plpgsql AS $$
       BEGIN RAISE EXCEPTION 'cash ledger is append-only'; END; $$""",
    """CREATE TRIGGER cash_movements_no_update BEFORE UPDATE ON cash_movements
       FOR EACH ROW EXECUTE FUNCTION cash_movements_append_only()""",
    """CREATE TRIGGER cash_movements_no_delete BEFORE DELETE ON cash_movements
       FOR EACH ROW EXECUTE FUNCTION cash_movements_append_only()""",
)


def upgrade() -> None:
    op.create_table(
        "cash_movements",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(300), nullable=True),
        sa.Column("sale_id", sa.String(36), nullable=True),
        sa.Column("device_id", sa.String(36), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column("synced_at", sa.String(32), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cash_movements")),
        sa.ForeignKeyConstraint(
            ["sale_id"],
            ["sales.id"],
            name=op.f("fk_cash_movements_sale_id_sales"),
        ),
        sa.UniqueConstraint(
            "device_id", "seq", name=op.f("uq_cash_movements_device_id")
        ),
    )
    op.create_index(
        op.f("ix_cash_movements_sale_id"), "cash_movements", ["sale_id"], unique=False
    )

    # FND-01 / D-00a: append-only enforcement at the DATABASE level (frozen
    # DDL copy).
    if op.get_bind().dialect.name == "postgresql":
        for stmt in _PG_CASH_APPEND_ONLY_DDL:
            op.execute(stmt)
    else:  # sqlite — output byte-for-behavior identical to today (WR-06)
        for stmt in _CASH_APPEND_ONLY_TRIGGERS:
            op.execute(stmt)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        # PG grammar requires `DROP TRIGGER name ON table`; the SQLite-only
        # form (no ON clause) raises a syntax error on PG (CR-01).
        op.execute("DROP TRIGGER IF EXISTS cash_movements_no_update ON cash_movements")
        op.execute("DROP TRIGGER IF EXISTS cash_movements_no_delete ON cash_movements")
        op.execute("DROP FUNCTION IF EXISTS cash_movements_append_only()")
    else:
        op.execute("DROP TRIGGER IF EXISTS cash_movements_no_update")
        op.execute("DROP TRIGGER IF EXISTS cash_movements_no_delete")
    op.drop_index(op.f("ix_cash_movements_sale_id"), table_name="cash_movements")
    op.drop_table("cash_movements")
