"""device_tokens table (per-device sync credential)

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-19

Phase 28 (SYNC-09): introduces the `device_tokens` table so a sync client can
prove which device it is without a browser session, and so an administrator can
kill a lost device's access instantly.

Only a SHA-256 hex digest of the token is persisted (`token_hash`); the
plaintext is returned by the mint service exactly once and never stored.
`token_prefix` is a NON-SECRET lookup key (the first 12 chars of the plaintext)
so verification is one indexed row read rather than a table scan.

`user_id` is a BARE column here — no DB-level FK — following the 0004 sale_id /
0008 batch_id / 0017 author_id precedent; the ORM ForeignKey gives Unit-of-Work
insert ordering and PostgreSQL portability.

There is deliberately no expiry column: revocation (`is_active = 0` +
`revoked_at`) is the control, and rows are never hard-deleted.

Portability: `sa.String` / `sa.Integer` only — no dialect imports, no server
defaults, no SQLite- or PostgreSQL-specific SQL.

Immutability rule (WR-06): this file must never import application modules —
stdlib + sqlalchemy + alembic.op only.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_tokens",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("device_id", sa.String(36), nullable=False),  # NOT unique
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("token_prefix", sa.String(12), nullable=False),  # non-secret
        sa.Column("token_hash", sa.String(64), nullable=False),  # sha256 hex
        sa.Column("user_id", sa.String(36), nullable=True),  # bare, ORM-only FK
        sa.Column("is_active", sa.Integer(), nullable=False),  # 1 active / 0 revoked
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("last_used_at", sa.String(32), nullable=True),
        sa.Column("revoked_at", sa.String(32), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_device_tokens")),
        sa.UniqueConstraint(
            "token_prefix", name=op.f("uq_device_tokens_token_prefix")
        ),
    )
    op.create_index(
        op.f("ix_device_tokens_token_prefix"), "device_tokens", ["token_prefix"]
    )
    op.create_index(op.f("ix_device_tokens_user_id"), "device_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_device_tokens_user_id"), table_name="device_tokens")
    op.drop_index(op.f("ix_device_tokens_token_prefix"), table_name="device_tokens")
    op.drop_table("device_tokens")
