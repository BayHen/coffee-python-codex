"""Add revocable authentication sessions.

Revision ID: b4c1a8e2f0d7
Revises: d8398c7e85ca
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b4c1a8e2f0d7"
down_revision: str | Sequence[str] | None = "d8398c7e85ca"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("expires_at > created_at", name="auth_session_expiry_valid"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("refresh_token_hash"),
    )
    op.create_index(op.f("ix_auth_sessions_user_id"), "auth_sessions", ["user_id"])


def downgrade() -> None:
    """Require an explicit data removal plan for authentication history."""
    raise RuntimeError("Auth session downgrade would delete session data")
