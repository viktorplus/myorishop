"""customers + sales tables, operations.sale_id

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-09

Adds the SAL-01..05/CST-01/02 schema: a `customers` table (D-07), a `sales`
header table (D-03), and a nullable `sale_id` FK column on `operations`
that links a `sale` op back to its header.

CRITICAL — Alembic batch caveat (see 0001's warning): a batch
(move-and-copy) migration on `operations` DROPS its append-only triggers.
The `sale_id` column below is therefore added with a NATIVE op.add_column
— NEVER batch_alter_table("operations").

RESEARCH A1 fallback applied: Alembic's SQLite dialect raises
NotImplementedError when add_column carries an inline FK constraint
("No support for ALTER of constraints in SQLite dialect" — confirmed by
running `alembic upgrade head` against this migration). The column is
therefore added as a BARE column with NO DB-level FK constraint; the ORM
ForeignKey stays on Operation.sale_id in app/models.py for Unit-of-Work
insert ordering (Sale header before sale ops) and PostgreSQL portability.
Trigger preservation outranks the physical FK (RESEARCH Code Example 3
verification note).

Immutability rule (WR-06): this file must never import app modules. All
values below are FROZEN copies — replaying the migration chain on a fresh
DB must produce the same history forever.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("surname", sa.String(200), nullable=True),
        sa.Column("consultant_number", sa.String(50), nullable=True),
        sa.Column("search_lc", sa.String(400), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customers")),
    )
    op.create_index(op.f("ix_customers_search_lc"), "customers", ["search_lc"])

    op.create_table(
        "sales",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("customer_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column("device_id", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sales")),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_sales_customer_id_customers"),
        ),
    )
    op.create_index(op.f("ix_sales_customer_id"), "sales", ["customer_id"])

    # NATIVE add-column (NO batch — preserves the operations_no_update /
    # operations_no_delete triggers from migration 0001). BARE column, no
    # DB-level FK (A1 fallback — see module docstring): Alembic's SQLite
    # dialect cannot ALTER in a constraint outside batch mode. The ORM
    # ForeignKey on Operation.sale_id (app/models.py) still gives
    # Unit-of-Work insert ordering and PostgreSQL portability.
    op.add_column(
        "operations",
        sa.Column("sale_id", sa.String(36), nullable=True),
    )
    op.create_index(op.f("ix_operations_sale_id"), "operations", ["sale_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_operations_sale_id"), table_name="operations")
    op.drop_column("operations", "sale_id")
    op.drop_index(op.f("ix_sales_customer_id"), table_name="sales")
    op.drop_table("sales")
    op.drop_index(op.f("ix_customers_search_lc"), table_name="customers")
    op.drop_table("customers")
