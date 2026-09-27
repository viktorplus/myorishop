"""products: per-currency card prices (UAH and EUR sets)

Revision ID: 0028
Revises: 0027
Create Date: 2026-09-27

Quick task 260927-k1m. A product card carries its own price set per currency:
the existing unsuffixed `cost_cents` / `sale_cents` / `min_sale_cents` stay the
RUB set, and this migration adds the same three for UAH and EUR. An operation
reads and writes only the set of the currency of the warehouse it touches, so
a receipt into a UAH warehouse can no longer overwrite the RUB card.

All six columns are nullable Integer cents with NO default of any kind: a
missing price in a currency is NULL, and a Python/DDL default would replace an
explicit None on merge inserts. There is NO backfill — converted values are
form suggestions only and never reach stored money unless the operator saves.

Offline bundles are schema-version matched exactly, so bundles built before
0028 are rejected afterwards and must be re-downloaded.

DOWNGRADE IS DATA-LOSSY: it drops the six columns, destroying EVERY UAH and
EUR card price entered after the upgrade (the `price_change` history that
names those fields stays behind, orphaned). Take a backup first — copy the
SQLite .db file with the app closed, or `pg_dump` on PostgreSQL.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None

_COLUMNS = (
    "cost_uah_cents",
    "sale_uah_cents",
    "min_sale_uah_cents",
    "cost_eur_cents",
    "sale_eur_cents",
    "min_sale_eur_cents",
)


def upgrade() -> None:
    # Same shape as 0025: `add_column` inside batch mode does NOT recreate the
    # table on SQLite, so the partial index on products survives.
    with op.batch_alter_table("products") as batch_op:
        for name in _COLUMNS:
            batch_op.add_column(sa.Column(name, sa.Integer(), nullable=True))


def downgrade() -> None:
    # DATA-LOSSY (review WR-03): drops ALL UAH/EUR card prices — back up the
    # database (copy the .db / `pg_dump`) before running this.
    # Plain `op.drop_column` — NEVER `op.batch_alter_table` (see 0027's
    # downgrade note): a batch drop rebuilds `products`, which carries the
    # partial unique index `uq_products_code_active` (WHERE deleted_at IS NULL).
    for name in reversed(_COLUMNS):
        op.drop_column("products", name)
