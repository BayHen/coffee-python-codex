"""Add product pricing options and auditable session receipts.

Revision ID: c3e7f1a5b9d2
Revises: a1f4c8d2e6b9
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3e7f1a5b9d2"
down_revision: str | Sequence[str] | None = "a1f4c8d2e6b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "base_price",
            sa.Numeric(12, 2),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.execute(
        "UPDATE products AS p SET base_price = COALESCE("
        "(SELECT MIN(pv.price) FROM product_variants pv WHERE pv.product_id = p.id), 0)"
    )
    op.execute(
        "UPDATE product_variants AS pv SET price = pv.price - p.base_price "
        "FROM products AS p WHERE pv.product_id = p.id"
    )
    op.create_check_constraint("base_price_nonnegative", "products", "base_price >= 0")

    op.create_table(
        "product_toppings",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.CheckConstraint("price >= 0", name="price_nonnegative"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "name"),
    )
    op.create_index(
        "ix_product_toppings_product_id", "product_toppings", ["product_id"]
    )
    op.create_table(
        "order_item_toppings",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("order_item_id", sa.BigInteger(), nullable=False),
        sa.Column("topping_id", sa.BigInteger()),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.CheckConstraint("price >= 0", name="price_nonnegative"),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"]),
        sa.ForeignKeyConstraint(["topping_id"], ["product_toppings.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_order_item_toppings_order_item_id",
        "order_item_toppings",
        ["order_item_id"],
    )

    op.add_column("table_sessions", sa.Column("paid_at", sa.DateTime(timezone=True)))
    op.add_column("payments", sa.Column("receipt_number", sa.String(40)))
    op.add_column("payments", sa.Column("cashier_id", sa.BigInteger()))
    op.add_column("payments", sa.Column("paid_at", sa.DateTime(timezone=True)))
    op.add_column("payments", sa.Column("cash_received", sa.Numeric(12, 2)))
    op.add_column("payments", sa.Column("change_amount", sa.Numeric(12, 2)))
    op.add_column("payments", sa.Column("transfer_reference", sa.String(128)))
    op.create_unique_constraint(
        "uq_payments_receipt_number", "payments", ["receipt_number"]
    )
    op.create_foreign_key(
        "fk_payments_cashier", "payments", "users", ["cashier_id"], ["id"]
    )
    op.create_index("ix_payments_cashier_id", "payments", ["cashier_id"])
    op.create_index("ix_payments_paid_at", "payments", ["paid_at"])
    op.create_check_constraint(
        "cash_values_valid",
        "payments",
        "cash_received IS NULL OR "
        "(cash_received >= amount AND change_amount = cash_received - amount)",
    )


def downgrade() -> None:
    raise RuntimeError("Task 13 V3 downgrade requires an explicit data migration")
