"""active_catalog table

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-17

Phase 23 (DASH-02, D-01/D-02): adds the `active_catalog` table — a manually
set active catalog number + close date, edited on the existing `/catalogs`
page. Singleton by service-layer convention (app/services/active_catalog.py
get-or-create), no unique constraint, no seed row — an empty table is the
"no active catalog configured" placeholder state.

Native op.create_table, no batch mode — a brand-new table is natively
supported by SQLite (see 0015_customer_contacts.py precedent).

Immutability rule (WR-06): this file must never import application modules.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "active_catalog",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("number", sa.String(20), nullable=True),
        sa.Column("close_date", sa.String(10), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_active_catalog")),
    )


def downgrade() -> None:
    op.drop_table("active_catalog")
