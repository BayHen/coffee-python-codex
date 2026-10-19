"""Add customer status, case-insensitive staff keys, and loyalty ledger.

Revision ID: a7c0e4f6b8d9
Revises: f6b9d3e5a7c8
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a7c0e4f6b8d9"
down_revision: str | Sequence[str] | None = "f6b9d3e5a7c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.create_index(
        "uq_customers_email_lower",
        "customers",
        [sa.text("lower(email)")],
        unique=True,
    )
    op.create_index(
        "uq_employees_code_lower",
        "employees",
        [sa.text("lower(employee_code)")],
        unique=True,
    )
    op.create_table(
        "loyalty_transactions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger()),
        sa.Column("actor_user_id", sa.BigInteger()),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("points_delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("points_delta <> 0", name="points_delta_nonzero"),
        sa.CheckConstraint(
            "transaction_type IN ('earn', 'refund', 'adjustment')",
            name="type_valid",
        ),
        sa.CheckConstraint(
            "(transaction_type = 'earn' AND points_delta > 0) "
            "OR (transaction_type = 'refund' AND points_delta < 0) "
            "OR transaction_type = 'adjustment'",
            name="points_direction_valid",
        ),
        sa.CheckConstraint(
            "transaction_type = 'adjustment' OR order_id IS NOT NULL",
            name="order_required",
        ),
        sa.CheckConstraint("char_length(btrim(reason)) >= 3", name="reason_valid"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        "ix_loyalty_transactions_customer_id",
        "loyalty_transactions",
        ["customer_id"],
    )
    op.create_index(
        "ix_loyalty_transactions_order_id",
        "loyalty_transactions",
        ["order_id"],
    )
    op.create_index(
        "ix_loyalty_transactions_actor_user_id",
        "loyalty_transactions",
        ["actor_user_id"],
    )
    op.create_index(
        "uq_loyalty_earn_order",
        "loyalty_transactions",
        ["order_id"],
        unique=True,
        postgresql_where=sa.text("transaction_type = 'earn'"),
    )
    op.create_index(
        "uq_loyalty_refund_order",
        "loyalty_transactions",
        ["order_id"],
        unique=True,
        postgresql_where=sa.text("transaction_type = 'refund'"),
    )


def downgrade() -> None:
    raise RuntimeError("People and loyalty downgrade would remove audit history")
