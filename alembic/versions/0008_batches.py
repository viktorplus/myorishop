"""batches table, operations.batch_id, per-product legacy-batch seed

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-12

Phase 9 (LOT-01): introduces `batches` as the true stock-holding unit and a
nullable `operations.batch_id` link so the ledger can attribute each stock
change to a lot (D-10).

CRITICAL — Alembic batch caveat (see 0001's frozen warning): a batch
(move-and-copy) migration on `operations` DROPS its append-only triggers
(`operations_no_update` / `operations_no_delete`). `batch_id` is therefore
added with a NATIVE op.add_column — NEVER an Alembic batch/move-and-copy
rebuild of the operations table.
Following the 0004 sale_id precedent, the column is BARE (no DB-level inline
FK — Alembic's SQLite dialect raises NotImplementedError on ALTER-in
constraints); the ORM ForeignKey on Operation.batch_id gives Unit-of-Work
insert ordering and PostgreSQL portability.

Legacy data (D-13/D-14): seed exactly one legacy batch per product whose
ledger SUM(qty_delta) > 0. Quantity is read from the LEDGER in plain SQL,
NEVER from the products.quantity cache (which may be stale) — so success
criterion 5 balances against a rebuilt ledger. Zero-/negative-stock products
get no legacy batch. Field values are frozen literals.

Immutability rule (WR-06): this file must never import app modules. `uuid`
from the stdlib IS allowed (the ban is on app modules); uuid5 keyed on
product_id makes the seed replay-deterministic per product. All values below
are FROZEN copies.
"""

import uuid

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

# D-14 frozen literals (re-declared, never imported from 0007 or app modules).
DEFAULT_WAREHOUSE_ID = "00000000-0000-4000-8000-000000000010"  # 0007 D-03 contract
LEGACY_COMMENT = "Остаток до внедрения партий"
_SEED_CREATED_AT = "2026-07-11T00:00:00+00:00"
# Frozen namespace for deterministic per-product legacy-batch ids (uuid5).
_LEGACY_NS = uuid.UUID("00000000-0000-4000-8000-00000000000b")


def upgrade() -> None:
    op.create_table(
        "batches",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("product_id", sa.String(36), nullable=False),
        sa.Column("warehouse_id", sa.String(36), nullable=False),
        sa.Column("expiry", sa.String(10), nullable=True),  # ISO yyyy-mm-dd (LOT-03)
        sa.Column("price_cents", sa.Integer(), nullable=True),
        sa.Column("location", sa.String(100), nullable=True),  # WH-02
        sa.Column("comment", sa.String(200), nullable=True),  # LOT-04
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("is_legacy", sa.Integer(), nullable=False),  # 1 only for the seed
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_batches")),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_batches_product_id_products"),
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name=op.f("fk_batches_warehouse_id_warehouses"),
        ),
    )
    op.create_index(op.f("ix_batches_product_id"), "batches", ["product_id"])

    # NATIVE add-column (NO batch — preserves the operations_no_update /
    # operations_no_delete triggers from migration 0001). BARE column, no
    # DB-level FK (0004 sale_id precedent).
    op.add_column(
        "operations",
        sa.Column("batch_id", sa.String(36), nullable=True),
    )
    op.create_index(op.f("ix_operations_batch_id"), "operations", ["batch_id"])

    # D-13: one legacy batch per product with LEDGER stock > 0 (plain SQL,
    # NEVER the products.quantity cache — Pitfall 5).
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT product_id, SUM(qty_delta) AS qty FROM operations "
            "GROUP BY product_id HAVING SUM(qty_delta) > 0"
        )
    ).fetchall()
    for product_id, qty in rows:
        conn.execute(
            sa.text(
                "INSERT INTO batches (id, product_id, warehouse_id, expiry, "
                "price_cents, location, comment, quantity, is_legacy, "
                "created_at, updated_at) "
                "VALUES (:id, :pid, :wid, NULL, NULL, NULL, :comment, :qty, 1, "
                ":ts, :ts)"
            ),
            {
                "id": str(uuid.uuid5(_LEGACY_NS, product_id)),
                "pid": product_id,
                "wid": DEFAULT_WAREHOUSE_ID,
                "comment": LEGACY_COMMENT,
                "qty": qty,
                "ts": _SEED_CREATED_AT,
            },
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_operations_batch_id"), table_name="operations")
    op.drop_column("operations", "batch_id")  # native DROP COLUMN, index first
    op.drop_index(op.f("ix_batches_product_id"), table_name="batches")
    op.drop_table("batches")
