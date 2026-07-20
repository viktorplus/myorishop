"""dictionary.rubric column (CAT-06)

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-20

Adds the coarse product rubric column to the dictionary helper table. Plain
nullable ADD COLUMN (native SQLite ALTER, and portable to PostgreSQL) plus a
plain index for rubric filtering — the append-only ledger triggers are never
touched. The column is backfilled at import time by
scripts/import_master_pricelist.py (app.services.rubrics), NOT here: this
migration must never reference application modules (immutability rule WR-06).
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("dictionary", sa.Column("rubric", sa.String(40), nullable=True))
    op.create_index(op.f("ix_dictionary_rubric"), "dictionary", ["rubric"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_dictionary_rubric"), table_name="dictionary")
    op.drop_column("dictionary", "rubric")
