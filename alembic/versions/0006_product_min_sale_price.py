"""optional minimum sale price guardrail

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-10

D-06: adds one nullable Integer column `min_sale_cents` to `products` —
NULL means "no minimum price floor is set". Deliberately NO global-settings
fallback, unlike `low_stock_threshold`/`stale_days` (0005): PRICE-01's
sale-time guardrail either has a per-product floor to compare against, or
it does not warn at all. An operator-entered 0 is a genuinely explicit
value and is stored as 0, never coerced to NULL.

Immutability rule (WR-06): this file must never reference application
modules. All values below are FROZEN copies.

Native ADD COLUMN, no batch mode — this migration never touches
`operations`, so the append-only triggers are not a concern here, but the
native-ADD-COLUMN reasoning from 0002/0004/0005 is restated for
consistency: never batch-alter a table whose migrations must stay
replayable forever.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("min_sale_cents", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("products", "min_sale_cents")
