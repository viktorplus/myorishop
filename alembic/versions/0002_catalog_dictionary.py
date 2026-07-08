"""catalog columns + dictionary table

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-08

Adds the CAT-01 product columns (category, cost_cents, sale_cents,
catalog_cents, name_lc), backfills name_lc in PYTHON (SQLite lower() is
ASCII-only and cannot fold Cyrillic — RESEARCH Finding 1), creates the
dictionary reference table (PD-1: UUID surrogate PK + UNIQUE(code)) and
the search indexes ix_products_code / ix_products_name_lc.

This migration uses only plain op.add_column (native SQLite ALTER) — NO
batch mode, and it NEVER touches the ledger table, so the append-only
triggers from migration 0001 are untouched.

Immutability rule (WR-06): this file must never reference application
modules. All values below are FROZEN copies — replaying the migration
chain on a fresh DB must produce the same history forever.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) products: plain ADD COLUMN (nullable) — native SQLite ALTER,
    #    no batch, triggers untouched.
    op.add_column("products", sa.Column("category", sa.String(100), nullable=True))
    op.add_column("products", sa.Column("cost_cents", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("sale_cents", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("catalog_cents", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("name_lc", sa.String(200), nullable=True))

    # 2) backfill name_lc in PYTHON — SQL lower() cannot fold Cyrillic
    #    (frozen, stdlib str.lower only).
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, name FROM products")).fetchall()
    for row_id, name in rows:
        bind.execute(
            sa.text("UPDATE products SET name_lc = :lc WHERE id = :id"),
            {"lc": (name or "").lower(), "id": row_id},
        )

    # 3) dictionary table (PD-1: UUID PK + unique code)
    op.create_table(
        "dictionary",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dictionary")),
        sa.UniqueConstraint("code", name=op.f("uq_dictionary_code")),
    )

    # 4) search indexes (locked discretion: code + name_lc)
    op.create_index(op.f("ix_products_code"), "products", ["code"], unique=False)
    op.create_index(op.f("ix_products_name_lc"), "products", ["name_lc"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_products_name_lc"), table_name="products")
    op.drop_index(op.f("ix_products_code"), table_name="products")
    op.drop_table("dictionary")
    # SQLite >= 3.35 supports native DROP COLUMN (local runtime is 3.50.4).
    op.drop_column("products", "name_lc")
    op.drop_column("products", "catalog_cents")
    op.drop_column("products", "sale_cents")
    op.drop_column("products", "cost_cents")
    op.drop_column("products", "category")
