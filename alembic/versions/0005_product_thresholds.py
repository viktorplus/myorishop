"""per-product report thresholds

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-10

D-04/D-05: adds two nullable per-product threshold columns to `products` —
`low_stock_threshold` (RPT-02, "low stock") and `stale_days` (RPT-04, "days
without a sale = stale"). NULL means "use the global default"
(settings.low_stock_threshold / settings.stale_days) — NOT zero; an
operator-entered 0 is a genuinely explicit value and is stored as 0.

Immutability rule (WR-06): this file must never reference application
modules. All values below are FROZEN copies.

Native ADD COLUMN, no batch mode — this migration never touches
`operations`, so the append-only triggers are not a concern here, but the
native-ADD-COLUMN reasoning from 0002/0004 is restated for consistency:
never batch-alter a table whose migrations must stay replayable forever.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("low_stock_threshold", sa.Integer(), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("stale_days", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("products", "stale_days")
    op.drop_column("products", "low_stock_threshold")
