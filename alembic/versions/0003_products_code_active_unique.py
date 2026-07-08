"""partial unique index on active product codes

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-08

WR-04: product-code uniqueness among ACTIVE products was enforced only by
a SELECT-then-INSERT check in the catalog service — a double-submit could
create two active products with the same code. This partial unique index
is the DB backstop; deleted products may still share codes (D-19).
Portable: sqlite_where + postgresql_where cover both target databases.

Immutability rule (WR-06): this file must never reference application
modules. All values below are FROZEN copies.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_products_code_active",
        "products",
        ["code"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_products_code_active", table_name="products")
