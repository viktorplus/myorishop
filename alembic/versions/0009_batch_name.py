"""batches.name: auto-generated human-readable batch label

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-12

Phase 9 (LOT-01, UAT test 1 symptom 3): adds a nullable `batches.name` label
that register_receipt auto-generates as «{product name} — {creation date}» at
batch birth. A STORED column (not a read-time derived label) snapshots the name
at creation so it survives later product renames — consistent with this
project's snapshot/append-only philosophy. Nullable so existing/legacy
(pre-0009) rows stay valid; there is NO data backfill — only NEW batches get a
name, and the chooser falls back to the expiry/price description for nameless
rows.

CRITICAL — Alembic batch caveat (see 0001's frozen warning, restated in 0008):
this uses a NATIVE `op.add_column` on `batches`. It must NEVER be converted to
an Alembic batch / move-and-copy rebuild. The move-and-copy pattern is what
drops the append-only `operations_no_update` / `operations_no_delete` triggers —
and it is both dangerous and unnecessary here: `batches` carries no triggers,
and SQLite supports ADD COLUMN natively, so a native add-column is safe and
portable (no SQLite-specific SQL, no PostgreSQL-migration hazard).

Immutability rule (WR-06): this file imports no app modules.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NATIVE add-column (NO batch — `batches` has no triggers; this never
    # rebuilds a table). Nullable so pre-0009 rows remain valid; no backfill.
    op.add_column(
        "batches",
        sa.Column("name", sa.String(200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("batches", "name")
