"""dictionary.catalogs membership column

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-13

Adds a nullable JSON column `catalogs` to the reference dictionary. It holds
the list of catalog codes (e.g. ["01_26", "03_26"]) a product code appears in,
imported from catalogs/products.json. The dictionary stays a HELPER table
(D-24): this column never feeds stock or the ledger.

Plain op.add_column (native SQLite ALTER) — no batch mode, ledger untouched.

Immutability rule (WR-06): this file references no application modules.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("dictionary", sa.Column("catalogs", sa.JSON(), nullable=True))


def downgrade() -> None:
    # SQLite >= 3.35 supports native DROP COLUMN (local runtime is 3.50.4).
    op.drop_column("dictionary", "catalogs")
