"""Add inventory metadata, units, thresholds, and reversal links.

Revision ID: f6b9d3e5a7c8
Revises: e5a8c2d4f6b7
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f6b9d3e5a7c8"
down_revision: str | Sequence[str] | None = "e5a8c2d4f6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ingredients",
        sa.Column(
            "low_stock_threshold",
            sa.Numeric(14, 3),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "ingredients",
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "unit_valid", "ingredients", "unit IN ('g', 'ml', 'piece')"
    )
    op.create_check_constraint(
        "low_stock_threshold_nonnegative",
        "ingredients",
        "low_stock_threshold >= 0",
    )
    op.create_index(
        "uq_ingredients_sku_lower",
        "ingredients",
        [sa.text("lower(sku)")],
        unique=True,
    )
    op.create_index(
        "uq_ingredients_name_lower",
        "ingredients",
        [sa.text("lower(name)")],
        unique=True,
    )

    op.add_column("inventory_transactions", sa.Column("actor_user_id", sa.BigInteger()))
    op.add_column(
        "inventory_transactions", sa.Column("reversal_of_id", sa.BigInteger())
    )
    op.add_column(
        "inventory_transactions", sa.Column("request_fingerprint", sa.String(64))
    )
    op.add_column("inventory_transactions", sa.Column("reason", sa.String(255)))
    op.execute(
        "UPDATE inventory_transactions SET "
        "request_fingerprint = 'legacy-inventory-' || id, "
        "reason = 'Legacy inventory transaction'"
    )
    op.alter_column("inventory_transactions", "request_fingerprint", nullable=False)
    op.alter_column("inventory_transactions", "reason", nullable=False)
    op.create_foreign_key(
        "fk_inventory_transactions_actor_user_id",
        "inventory_transactions",
        "users",
        ["actor_user_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_inventory_transactions_reversal_of_id",
        "inventory_transactions",
        "inventory_transactions",
        ["reversal_of_id"],
        ["id"],
    )
    op.create_index(
        "ix_inventory_transactions_actor_user_id",
        "inventory_transactions",
        ["actor_user_id"],
    )
    op.create_unique_constraint(
        "uq_inventory_transactions_reversal_of_id",
        "inventory_transactions",
        ["reversal_of_id"],
    )

    op.drop_constraint("delta_direction_valid", "inventory_transactions", type_="check")
    op.drop_constraint("type_valid", "inventory_transactions", type_="check")
    op.drop_constraint("sale_has_order_item", "inventory_transactions", type_="check")
    op.create_check_constraint(
        "delta_direction_valid",
        "inventory_transactions",
        "(transaction_type IN ('sale', 'waste') AND quantity_delta < 0) "
        "OR (transaction_type IN ('purchase', 'return') AND quantity_delta > 0) "
        "OR transaction_type = 'adjustment'",
    )
    op.create_check_constraint(
        "type_valid",
        "inventory_transactions",
        "transaction_type IN ('purchase', 'sale', 'return', 'adjustment', 'waste')",
    )
    op.create_check_constraint(
        "order_movement_has_order_item",
        "inventory_transactions",
        "transaction_type NOT IN ('sale', 'return') OR order_item_id IS NOT NULL",
    )
    op.create_check_constraint(
        "reason_valid",
        "inventory_transactions",
        "char_length(btrim(reason)) >= 3",
    )


def downgrade() -> None:
    raise RuntimeError("Inventory downgrade requires an explicit ledger migration")
