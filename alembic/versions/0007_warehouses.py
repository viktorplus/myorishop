"""warehouses (WH-01)

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-11

Creates the standalone `warehouses` table (D-01: no FK from products/
operations yet — Batch.warehouse_id is Phase 9's job) and seeds exactly
one default row so success criterion 2 is satisfied conceptually: nothing
is lost because nothing yet references warehouses to lose (D-02).

D-03: DEFAULT_WAREHOUSE_ID and the seed name below are the frozen,
documented identity Phase 9's legacy-batch migration is expected to point
at (re-declared there, never imported from this module).

Immutability rule (WR-06): this file must never reference application
modules. All values below are FROZEN copies.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

# D-03: frozen, documented identity Phase 9's legacy-batch migration can
# rely on without importing this module.
DEFAULT_WAREHOUSE_ID = "00000000-0000-4000-8000-000000000010"
_SEED_CREATED_AT = "2026-07-11T00:00:00+00:00"


def upgrade() -> None:
    op.create_table(
        "warehouses",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("address", sa.String(300), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.Column("deleted_at", sa.String(32), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_warehouses")),
    )

    warehouses = sa.table(
        "warehouses",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("address", sa.String),
        sa.column("created_at", sa.String),
        sa.column("updated_at", sa.String),
    )
    op.bulk_insert(
        warehouses,
        [
            {
                "id": DEFAULT_WAREHOUSE_ID,
                "name": "Склад по умолчанию",
                "address": None,
                "created_at": _SEED_CREATED_AT,
                "updated_at": _SEED_CREATED_AT,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("warehouses")
