"""drop products.catalog_cents (PROD-05)

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-16

Phase 18 (PROD-05, D-01): the two-price model keeps only ДЦ (cost_cents)
and ПЦ (sale_cents); min_sale_cents stays as a guardrail threshold, NOT a
displayed price. catalog_cents is a write-once stale copy of the Oriflame
list price — the live reference is served from catalog_prices — so its
values are DISCARDED, not migrated (D-01: 0 rows have sale_cents IS NULL
AND catalog_cents IS NOT NULL, so no backfill is possible or needed).

NATIVE op.drop_column, NOT Alembic's batch (move-and-copy) mode (D-03, and
the house rule frozen in 0001:11-14 / 0008:11-17): a move-and-copy rebuild
of `products`
would recreate the partial unique index uq_products_code_active (0003,
sqlite_where="deleted_at IS NULL"). SQLite >= 3.35 supports native DROP
COLUMN (local runtime 3.50.4); catalog_cents is in no index/trigger/view.
Same statement already proven in 0002's downgrade (0002:75).

IRREVERSIBLE (D-01): downgrade re-adds the column as NULL-filled. The 6
discarded values are NOT recoverable from this migration. Pre-drop safety
net is app/services/backup.py's VACUUM INTO startup snapshot; historical
receipt payload.catalog_cents (8 ops) is untouched and stays readable.

Immutability rule (WR-06): this file must never import app modules.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("products", "catalog_cents")


def downgrade() -> None:
    # D-01: values were discarded on upgrade — the column returns EMPTY,
    # never fabricated from sale_cents (that would be D-02's rejected
    # re-pricing).
    op.add_column(
        "products", sa.Column("catalog_cents", sa.Integer(), nullable=True)
    )
