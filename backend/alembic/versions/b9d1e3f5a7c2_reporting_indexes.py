"""Add payment aggregation index for revenue reports.

Revision ID: b9d1e3f5a7c2
Revises: a7c0e4f6b8d9
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b9d1e3f5a7c2"
down_revision: str | Sequence[str] | None = "a7c0e4f6b8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_payments_reporting_status_created_order",
        "payments",
        ["status", "created_at", "order_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_payments_reporting_status_created_order", table_name="payments")
