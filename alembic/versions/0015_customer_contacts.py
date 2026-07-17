"""customer_contacts table + customers.address column

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-17

Phase 21 (CUST-01..05): adds the profile schema — a `customer_contacts`
child table (D-01, one generic table with a `kind` discriminator for
phone/telegram/email/social) and `customers.address` (D-02, a singular
physical address, plain column not a contact row).

Both ops are native — no batch mode. A brand-new table needs
op.create_table; a nullable column needs op.add_column; both are natively
supported by SQLite, and render_as_batch=True in alembic/env.py only
affects autogenerate rendering of ops that genuinely need table rebuilds
(see 0005/0014 precedent).

Immutability rule (WR-06): this file must never import application
modules. The `kind` literals below are a FROZEN copy of
app.models.CONTACT_KINDS' keys.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_contacts",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("customer_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("value", sa.String(300), nullable=False),
        sa.Column("label", sa.String(100), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customer_contacts")),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_customer_contacts_customer_id_customers"),
        ),
        # Frozen snapshot of the CONTACT_KINDS keys (duplicated from
        # app.models.CONTACT_KINDS on purpose — migrations may duplicate
        # app constants, they must not reference them). Note the FULLY
        # EXPANDED name here (wrapped in op.f), unlike the model's short
        # "kind_valid" token which NAMING_CONVENTION expands at import time.
        sa.CheckConstraint(
            "kind IN ('phone', 'telegram', 'email', 'social')",
            name=op.f("ck_customer_contacts_kind_valid"),
        ),
    )
    op.create_index(
        op.f("ix_customer_contacts_customer_id"),
        "customer_contacts",
        ["customer_id"],
        unique=False,
    )
    op.add_column("customers", sa.Column("address", sa.String(300), nullable=True))


def downgrade() -> None:
    op.drop_column("customers", "address")
    op.drop_index(op.f("ix_customer_contacts_customer_id"), table_name="customer_contacts")
    op.drop_table("customer_contacts")
