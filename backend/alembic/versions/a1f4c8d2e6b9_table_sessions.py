"""Add cafe tables, service sessions, and session-level checkout.

Revision ID: a1f4c8d2e6b9
Revises: b9d1e3f5a7c2
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1f4c8d2e6b9"
down_revision: str | Sequence[str] | None = "b9d1e3f5a7c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cafe_tables",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("table_number", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("table_number"),
    )
    op.create_index(
        "uq_cafe_tables_number_lower",
        "cafe_tables",
        [sa.text("lower(table_number)")],
        unique=True,
    )
    op.create_table(
        "table_sessions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("table_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status", sa.String(20), server_default=sa.text("'open'"), nullable=False
        ),
        sa.Column(
            "opened_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("opened_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('open', 'paid', 'cancelled')", name="status_valid"
        ),
        sa.ForeignKeyConstraint(["opened_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["table_id"], ["cafe_tables.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_table_sessions_table_id", "table_sessions", ["table_id"])
    op.create_index("ix_table_sessions_opened_by", "table_sessions", ["opened_by"])
    op.create_index(
        "uq_table_sessions_open_table",
        "table_sessions",
        ["table_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )

    op.add_column("orders", sa.Column("session_id", sa.BigInteger()))
    op.add_column("orders", sa.Column("order_type", sa.String(20)))
    op.add_column("orders", sa.Column("sequence_number", sa.Integer()))
    op.add_column("orders", sa.Column("created_by", sa.BigInteger()))
    op.add_column("orders", sa.Column("confirmed_by", sa.BigInteger()))
    op.add_column("orders", sa.Column("confirmed_at", sa.DateTime(timezone=True)))
    op.create_foreign_key(
        "fk_orders_session", "orders", "table_sessions", ["session_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_orders_created_by", "orders", "users", ["created_by"], ["id"]
    )
    op.create_foreign_key(
        "fk_orders_confirmed_by", "orders", "users", ["confirmed_by"], ["id"]
    )
    op.create_index("ix_orders_session_id", "orders", ["session_id"])
    op.create_index("ix_orders_created_by", "orders", ["created_by"])
    op.create_index("ix_orders_confirmed_by", "orders", ["confirmed_by"])
    op.create_unique_constraint(
        "uq_orders_session_sequence_number", "orders", ["session_id", "sequence_number"]
    )
    op.create_check_constraint(
        "order_type_valid",
        "orders",
        "order_type IS NULL OR order_type IN ('initial', 'additional')",
    )
    op.create_index(
        "uq_orders_session_additional_draft",
        "orders",
        ["session_id"],
        unique=True,
        postgresql_where=sa.text("status = 'draft' AND order_type = 'additional'"),
    )
    op.drop_constraint("status_valid", "orders", type_="check")
    op.create_check_constraint(
        "status_valid",
        "orders",
        "status IN ('draft', 'confirmed', 'placed', 'paid', 'cancelled')",
    )
    op.drop_constraint("to_status_valid", "order_events", type_="check")
    op.drop_constraint("from_status_valid", "order_events", type_="check")
    op.create_check_constraint(
        "to_status_valid",
        "order_events",
        "to_status IN ('draft', 'confirmed', 'placed', 'paid', 'cancelled')",
    )
    op.create_check_constraint(
        "from_status_valid",
        "order_events",
        "from_status IS NULL OR from_status IN "
        "('draft', 'confirmed', 'placed', 'paid', 'cancelled')",
    )

    op.alter_column("payments", "order_id", nullable=True)
    op.add_column("payments", sa.Column("session_id", sa.BigInteger()))
    op.create_foreign_key(
        "fk_payments_session", "payments", "table_sessions", ["session_id"], ["id"]
    )
    op.create_index("ix_payments_session_id", "payments", ["session_id"])
    op.create_index(
        "uq_payments_succeeded_session",
        "payments",
        ["session_id"],
        unique=True,
        postgresql_where=sa.text("status = 'succeeded' AND session_id IS NOT NULL"),
    )


def downgrade() -> None:
    raise RuntimeError("Table session downgrade requires an explicit data migration")
