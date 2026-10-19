"""Add order snapshots, totals, workflow events, and idempotency.

Revision ID: e5a8c2d4f6b7
Revises: c7d2f9a1b3e4
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e5a8c2d4f6b7"
down_revision: str | Sequence[str] | None = "c7d2f9a1b3e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("idempotency_key", sa.String(128)))
    op.add_column("orders", sa.Column("request_fingerprint", sa.String(64)))
    op.add_column("orders", sa.Column("subtotal_amount", sa.Numeric(12, 2)))
    op.add_column(
        "orders",
        sa.Column(
            "discount_percent",
            sa.Numeric(5, 2),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "discount_amount",
            sa.Numeric(12, 2),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.execute(
        "UPDATE orders SET "
        "idempotency_key = 'legacy-order-' || id, "
        "request_fingerprint = 'legacy-' || id, "
        "subtotal_amount = total_amount"
    )
    op.alter_column("orders", "idempotency_key", nullable=False)
    op.alter_column("orders", "request_fingerprint", nullable=False)
    op.alter_column("orders", "subtotal_amount", nullable=False)
    op.create_unique_constraint(
        "uq_orders_idempotency_key", "orders", ["idempotency_key"]
    )

    op.add_column("order_items", sa.Column("product_name", sa.String(150)))
    op.add_column("order_items", sa.Column("variant_name", sa.String(100)))
    op.add_column("order_items", sa.Column("sku", sa.String(64)))
    op.add_column("order_items", sa.Column("line_total", sa.Numeric(12, 2)))
    op.execute(
        "UPDATE order_items AS oi SET "
        "product_name = p.name, variant_name = pv.name, sku = pv.sku, "
        "line_total = oi.unit_price * oi.quantity "
        "FROM product_variants AS pv "
        "JOIN products AS p ON p.id = pv.product_id "
        "WHERE oi.variant_id = pv.id"
    )
    for column in ("product_name", "variant_name", "sku", "line_total"):
        op.alter_column("order_items", column, nullable=False)

    op.drop_constraint("status_valid", "orders", type_="check")
    op.drop_constraint("total_nonnegative", "orders", type_="check")
    op.create_check_constraint(
        "status_valid",
        "orders",
        "status IN ('draft', 'placed', 'paid', 'cancelled')",
    )
    op.create_check_constraint("subtotal_nonnegative", "orders", "subtotal_amount >= 0")
    op.create_check_constraint(
        "discount_percent_valid",
        "orders",
        "discount_percent >= 0 AND discount_percent <= 20",
    )
    op.create_check_constraint("discount_nonnegative", "orders", "discount_amount >= 0")
    op.create_check_constraint("total_nonnegative", "orders", "total_amount >= 0")
    op.create_check_constraint(
        "total_components_valid",
        "orders",
        "subtotal_amount - discount_amount = total_amount",
    )
    op.create_check_constraint(
        "line_total_nonnegative", "order_items", "line_total >= 0"
    )
    op.create_check_constraint(
        "line_total_valid", "order_items", "unit_price * quantity = line_total"
    )

    op.add_column("payments", sa.Column("request_fingerprint", sa.String(64)))
    op.execute("UPDATE payments SET request_fingerprint = 'legacy-payment-' || id")
    op.alter_column("payments", "request_fingerprint", nullable=False)

    op.create_table(
        "order_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("from_status", sa.String(20)),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("note", sa.String(255)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "to_status IN ('draft', 'placed', 'paid', 'cancelled')",
            name="to_status_valid",
        ),
        sa.CheckConstraint(
            "from_status IS NULL OR "
            "from_status IN ('draft', 'placed', 'paid', 'cancelled')",
            name="from_status_valid",
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_events_order_id", "order_events", ["order_id"])
    op.create_index("ix_order_events_actor_user_id", "order_events", ["actor_user_id"])


def downgrade() -> None:
    raise RuntimeError("Order management downgrade requires an explicit data migration")
