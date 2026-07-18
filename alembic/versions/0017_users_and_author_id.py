"""users table + author_id attribution columns

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-18

Phase 25 (USER-01/ROLE-01/USER-05): introduces the `users` identity table and a
nullable `author_id` link on the three write-path tables (`operations`,
`cash_movements`, `sales`) so each row can be attributed to the operator who
authored it (D-USER-05).

CRITICAL — Alembic batch caveat (see 0008_batches.py / 0001's frozen warning):
a batch (move-and-copy) migration on `operations` or `cash_movements` DROPS
their append-only triggers (`operations_no_update`/`operations_no_delete`,
`cash_movements_no_update`/`cash_movements_no_delete`). `author_id` is therefore
added with a NATIVE op.add_column — NEVER an Alembic batch/move-and-copy rebuild.
Following the 0004 sale_id / 0008 batch_id precedent, each column is BARE (no
DB-level inline FK — Alembic's SQLite dialect raises NotImplementedError on
ALTER-in constraints); the ORM ForeignKey on the models gives Unit-of-Work
insert ordering and PostgreSQL portability.

No backfill: historical (pre-auth) rows keep author_id NULL. The
operations_no_update trigger would ABORT any UPDATE backfill anyway, and a
fabricated author would be a lie (RESEARCH Pitfall 2).

Immutability rule (WR-06): this file must never import application modules —
stdlib + sqlalchemy + alembic.op only.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("login", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),  # a ROLES key
        sa.Column("password_hash", sa.String(255), nullable=False),  # Argon2id PHC
        sa.Column("is_active", sa.Integer(), nullable=False),  # 1 active / 0 disabled
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("login", name=op.f("uq_users_login")),
    )

    # NATIVE add-column for each attribution link (NO batch — preserves the
    # operations/cash_movements append-only triggers from migration 0001/0013).
    # BARE columns, no DB-level FK (0004 sale_id / 0008 batch_id precedent).
    op.add_column(
        "operations",
        sa.Column("author_id", sa.String(36), nullable=True),
    )
    op.create_index(op.f("ix_operations_author_id"), "operations", ["author_id"])

    op.add_column(
        "cash_movements",
        sa.Column("author_id", sa.String(36), nullable=True),
    )
    op.create_index(
        op.f("ix_cash_movements_author_id"), "cash_movements", ["author_id"]
    )

    op.add_column(
        "sales",
        sa.Column("author_id", sa.String(36), nullable=True),
    )
    op.create_index(op.f("ix_sales_author_id"), "sales", ["author_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_sales_author_id"), table_name="sales")
    op.drop_column("sales", "author_id")  # native DROP COLUMN, index first

    op.drop_index(op.f("ix_cash_movements_author_id"), table_name="cash_movements")
    op.drop_column("cash_movements", "author_id")

    op.drop_index(op.f("ix_operations_author_id"), table_name="operations")
    op.drop_column("operations", "author_id")

    op.drop_table("users")
