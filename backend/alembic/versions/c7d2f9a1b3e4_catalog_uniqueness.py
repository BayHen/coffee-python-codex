"""Enforce case-insensitive catalog uniqueness.

Revision ID: c7d2f9a1b3e4
Revises: b4c1a8e2f0d7
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c7d2f9a1b3e4"
down_revision: str | Sequence[str] | None = "b4c1a8e2f0d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_categories_name_lower",
        "categories",
        [sa.text("lower(name)")],
        unique=True,
    )
    op.create_index(
        "uq_products_category_name_lower",
        "products",
        ["category_id", sa.text("lower(name)")],
        unique=True,
    )
    op.create_index(
        "uq_product_variants_sku_lower",
        "product_variants",
        [sa.text("lower(sku)")],
        unique=True,
    )
    op.create_index(
        "uq_product_variants_product_name_lower",
        "product_variants",
        ["product_id", sa.text("lower(name)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_product_variants_product_name_lower", table_name="product_variants"
    )
    op.drop_index("uq_product_variants_sku_lower", table_name="product_variants")
    op.drop_index("uq_products_category_name_lower", table_name="products")
    op.drop_index("uq_categories_name_lower", table_name="categories")
