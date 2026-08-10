"""batches.cost_cents: batch-level cost snapshot (CUR-02)

Revision ID: 0025
Revises: 0024
Create Date: 2026-08-10

A batch's cost is now snapshotted at receipt time, in ITS warehouse's
currency. Nullable — legacy/never-entered batches stay NULL and fall back to
Product.cost_cents at read time (no backfill: batch-level cost was never
tracked before this migration, so NULL is the correct value for every
existing row).
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("batches") as batch_op:
        batch_op.add_column(sa.Column("cost_cents", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("batches") as batch_op:
        batch_op.drop_column("cost_cents")
