"""sync_state table + unsynced partial indexes (online client sync)

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-20

Phase 29 (D-10 / D-11 / D-15): the client-side online-sync data foundation.

`sync_state` is a single-row (id always 1) bookkeeping table. Its three D-10
result columns (last_sync_at / last_status / last_result) persist the outcome of
the most recent sync attempt so the header status survives an app restart; its
two D-15 config columns (auto_enabled / auto_interval_seconds) hold the
runtime-mutable auto-sync toggle + interval. The sync TOKEN is never a column
here — it is an `.env`-only secret so a copied `myorishop.db` cannot leak the
device credential.

`ix_operations_unsynced` / `ix_cash_movements_unsynced` are NON-unique partial
indexes on `synced_at IS NULL` that keep the D-11 unsynced-count badge
`COUNT(*)` cheap as ledger history grows.

Portability (SRV-01): `sa.String` / `sa.Integer` only, no server defaults, and
the partial-index predicate is supplied via BOTH `sqlite_where` and
`postgresql_where` (the 0003 precedent) so the one shared history applies on
SQLite AND PostgreSQL. `render_as_batch` is auto-derived per dialect in
`alembic/env.py` — no per-migration handling.

Immutability rule (WR-06): this file must never import application modules —
stdlib + sqlalchemy + alembic.op only.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sync_state",
        sa.Column("id", sa.Integer(), nullable=False),  # singleton, always 1
        sa.Column("last_sync_at", sa.String(32), nullable=True),  # UTC ISO text
        sa.Column("last_status", sa.String(16), nullable=True),  # ok|partial|error
        sa.Column("last_result", sa.String(300), nullable=True),  # RU message (D-12)
        sa.Column("auto_enabled", sa.Integer(), nullable=False),  # 0 off / 1 on
        sa.Column("auto_interval_seconds", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_state")),
    )
    op.create_index(
        "ix_operations_unsynced",
        "operations",
        ["synced_at"],
        sqlite_where=sa.text("synced_at IS NULL"),
        postgresql_where=sa.text("synced_at IS NULL"),
    )
    op.create_index(
        "ix_cash_movements_unsynced",
        "cash_movements",
        ["synced_at"],
        sqlite_where=sa.text("synced_at IS NULL"),
        postgresql_where=sa.text("synced_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_cash_movements_unsynced", table_name="cash_movements")
    op.drop_index("ix_operations_unsynced", table_name="operations")
    op.drop_table("sync_state")
