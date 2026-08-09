"""warehouses.currency: per-warehouse currency (CUR-01)

Revision ID: 0023
Revises: 0022
Create Date: 2026-08-10

Each warehouse now carries the currency its amounts are expressed in. Money is
still stored as integer minor units — this column only names the unit, and the
app performs NO conversion, so amounts from different currencies are never
summed.

Backfill: every pre-existing warehouse (including the 'Склад по умолчанию' seed
row from 0007) becomes 'RUB', which is what all existing data has always been.
`server_default` is kept on the column so a row inserted by older code (or by a
client that has not upgraded yet) still lands on a valid currency rather than
NULL.

SQLite cannot ALTER a table to add a NOT NULL column without a default, hence
the server_default; `render_as_batch=True` in env.py handles the rest.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None

_DEFAULT_CURRENCY = "RUB"


def upgrade() -> None:
    with op.batch_alter_table("warehouses") as batch_op:
        batch_op.add_column(
            sa.Column(
                "currency",
                sa.String(length=3),
                nullable=False,
                server_default=_DEFAULT_CURRENCY,
            )
        )
    # Explicit backfill: server_default covers the ALTER itself, but state this
    # outright so the intent survives a future default change.
    op.execute(f"UPDATE warehouses SET currency = '{_DEFAULT_CURRENCY}' WHERE currency IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("warehouses") as batch_op:
        batch_op.drop_column("currency")
