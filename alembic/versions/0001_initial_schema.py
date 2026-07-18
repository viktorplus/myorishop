"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-08

Creates products and operations tables (UUID4 TEXT PKs, integer *_cents money,
UTC ISO-8601 TEXT timestamps), installs DB-level append-only triggers on
operations, and seeds one demo product for the walking skeleton.

IMPORTANT — Alembic batch caveat: batch (move-and-copy) migrations that
recreate the operations table DROP its triggers — any future batch migration
touching operations must re-create the append-only triggers (with the DDL
frozen in that NEW migration, not imported from app code).

Immutability rule (WR-06): this file must never import app modules. The
trigger DDL and seed timestamp below are FROZEN copies — replaying the
migration chain on a fresh DB must produce the same history forever.
app.db.APPEND_ONLY_TRIGGERS stays the live source for test fixtures only;
future trigger changes go into new migrations, never edited here.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

DEMO_PRODUCT_ID = "00000000-0000-4000-8000-000000000001"

# Frozen snapshot of the v1 append-only trigger DDL (duplicated from
# app.db.APPEND_ONLY_TRIGGERS on purpose — migrations may duplicate app
# constants, they must not reference them).
_APPEND_ONLY_TRIGGERS: tuple[str, str] = (
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

# PostgreSQL equivalent of the SQLite append-only triggers above (WR-06:
# ADDITIVE dialect branch only — the SQLite path stays byte-for-behavior
# identical). RAISE(ABORT, …) is SQLite trigger-body syntax and a syntax error
# on PostgreSQL, so PG needs a PL/pgSQL BEFORE UPDATE/DELETE trigger function.
# Trigger NAMES (operations_no_update / operations_no_delete) and the
# 'append-only' message substring are identical across dialects.
_PG_OPERATIONS_DDL: tuple[str, str, str] = (
    """CREATE OR REPLACE FUNCTION operations_append_only()
       RETURNS trigger LANGUAGE plpgsql AS $$
       BEGIN RAISE EXCEPTION 'operations ledger is append-only'; END; $$""",
    """CREATE TRIGGER operations_no_update BEFORE UPDATE ON operations
       FOR EACH ROW EXECUTE FUNCTION operations_append_only()""",
    """CREATE TRIGGER operations_no_delete BEFORE DELETE ON operations
       FOR EACH ROW EXECUTE FUNCTION operations_append_only()""",
)

# Frozen seed timestamp (UTC ISO-8601) — deterministic across installs.
_SEED_CREATED_AT = "2026-07-08T00:00:00+00:00"


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("code", sa.String(20), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.Column("deleted_at", sa.String(32), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
    )

    op.create_table(
        "operations",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("product_id", sa.String(36), nullable=False),
        sa.Column("qty_delta", sa.Integer(), nullable=False),
        sa.Column("unit_cost_cents", sa.Integer(), nullable=True),
        sa.Column("unit_price_cents", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("device_id", sa.String(36), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column("synced_at", sa.String(32), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_operations")),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_operations_product_id_products"),
        ),
        sa.UniqueConstraint("device_id", "seq", name=op.f("uq_operations_device_id")),
    )
    op.create_index(
        op.f("ix_operations_product_id"), "operations", ["product_id"], unique=False
    )

    # FND-01: append-only enforcement at the DATABASE level (frozen DDL copy).
    if op.get_bind().dialect.name == "postgresql":
        for stmt in _PG_OPERATIONS_DDL:
            op.execute(stmt)
    else:  # sqlite — output byte-for-behavior identical to today (WR-06)
        for stmt in _APPEND_ONLY_TRIGGERS:
            op.execute(stmt)

    # Walking-skeleton seed: one demo product to correct against.
    now = _SEED_CREATED_AT
    products = sa.table(
        "products",
        sa.column("id", sa.String),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("quantity", sa.Integer),
        sa.column("created_at", sa.String),
        sa.column("updated_at", sa.String),
    )
    op.bulk_insert(
        products,
        [
            {
                "id": DEMO_PRODUCT_ID,
                "code": "DEMO-001",
                "name": "Демо-товар",
                "quantity": 0,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS operations_no_update")
    op.execute("DROP TRIGGER IF EXISTS operations_no_delete")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS operations_append_only()")
    op.drop_index(op.f("ix_operations_product_id"), table_name="operations")
    op.drop_table("operations")
    op.drop_table("products")
