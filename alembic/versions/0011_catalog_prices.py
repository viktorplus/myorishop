"""catalog_prices table (CAT-05)

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-13

Adds the catalog_prices helper table: one row per (catalog year, catalog
number, product code), imported from the xlsx price lists by
scripts/import_prices.py. Stores the consumer price (ПЦ), consultant price
(ОП) and bonus points (ББ) as integer cents / int. Helper data only (D-24):
never touches stock or the append-only ledger.

Plain op.create_table (native SQLite) — no batch mode, ledger untouched.

Immutability rule (WR-06): this file references no application modules.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalog_prices",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("consumer_cents", sa.Integer(), nullable=True),
        sa.Column("consultant_cents", sa.Integer(), nullable=True),
        sa.Column("points", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catalog_prices")),
        sa.UniqueConstraint(
            "year", "number", "code", name="uq_catalog_prices_year_number_code"
        ),
    )
    op.create_index(
        op.f("ix_catalog_prices_code"), "catalog_prices", ["code"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_catalog_prices_code"), table_name="catalog_prices")
    op.drop_table("catalog_prices")
