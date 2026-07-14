"""dictionary.name_lc shadow column

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-14

Adds a nullable name_lc column to `dictionary` for Cyrillic-safe filtering
(Phase 14, LIST-02), backfills existing rows in PYTHON (SQLite lower() is
ASCII-only and would silently corrupt Cyrillic names — mirrors migration
0002's frozen products.name_lc precedent), and creates a non-unique index.

Plain op.add_column (native SQLite ALTER) — no batch mode needed for a
nullable ADD COLUMN, ledger untouched.

Immutability rule (WR-06): this file references no application modules.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("dictionary", sa.Column("name_lc", sa.String(200), nullable=True))
    op.create_index(
        op.f("ix_dictionary_name_lc"), "dictionary", ["name_lc"], unique=False
    )

    # Backfill in PYTHON — SQL lower() cannot fold Cyrillic (frozen, stdlib
    # str.lower only, mirrors migration 0002).
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, name FROM dictionary")).fetchall()
    for row_id, name in rows:
        bind.execute(
            sa.text("UPDATE dictionary SET name_lc = :lc WHERE id = :id"),
            {"lc": (name or "").lower(), "id": row_id},
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_dictionary_name_lc"), table_name="dictionary")
    # SQLite >= 3.35 supports native DROP COLUMN (local runtime is 3.50.4).
    op.drop_column("dictionary", "name_lc")
