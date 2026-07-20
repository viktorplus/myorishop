"""remove the seed 'Демо-товар' placeholder product

Revision ID: 0022
Revises: 0021
Create Date: 2026-07-20

Production baseline starts with ZERO products (only the справочник). Migration
0001 seeded a single placeholder product 'DEMO-001' (qty 0); this removes it.
The 'Склад по умолчанию' seeded by 0007 is intentionally kept. DEMO-001 is
never referenced by any operation (it was never transacted), so the delete
touches no ledger rows and the append-only triggers stay untouched.

Immutability rule (WR-06): frozen id/timestamp copied from 0001, no app imports.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

_DEMO_PRODUCT_ID = "00000000-0000-4000-8000-000000000001"
_SEED_CREATED_AT = "2026-07-08T00:00:00+00:00"


def upgrade() -> None:
    op.execute("DELETE FROM products WHERE code = 'DEMO-001'")


def downgrade() -> None:
    op.execute(
        "INSERT INTO products (id, code, name, quantity, created_at, updated_at) "
        f"VALUES ('{_DEMO_PRODUCT_ID}', 'DEMO-001', 'Демо-товар', 0, "
        f"'{_SEED_CREATED_AT}', '{_SEED_CREATED_AT}')"
    )
