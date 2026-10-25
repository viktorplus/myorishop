"""user_warehouses table (operator warehouse access)

Revision ID: 0029
Revises: 0028
Create Date: 2026-10-26

Quick task 261026-wha. An operator works only with the warehouses an
administrator assigned to them; this table holds those (user_id, warehouse_id)
pairs. Administrators are never restricted and get no rows.

SEED: every existing operator (active or not) is assigned every active
warehouse, so nobody loses access on upgrade; the administrator then removes
what is not theirs. A user created after this migration starts with none.

Portability: `sa.String` only and an ANSI `INSERT ... SELECT ... CROSS JOIN`,
no dialect-specific SQL. Immutability rule (WR-06): stdlib + sqlalchemy +
alembic.op only, never application modules.

Downgrade drops the table and with it every assignment made after upgrade.
"""

import sqlalchemy as sa

from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_warehouses",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id"), nullable=False
        ),
        sa.PrimaryKeyConstraint("user_id", "warehouse_id", name=op.f("pk_user_warehouses")),
    )
    op.execute(
        "INSERT INTO user_warehouses (user_id, warehouse_id) "
        "SELECT u.id, w.id FROM users u CROSS JOIN warehouses w "
        "WHERE u.role = 'operator' AND w.deleted_at IS NULL"
    )


def downgrade() -> None:
    op.drop_table("user_warehouses")
