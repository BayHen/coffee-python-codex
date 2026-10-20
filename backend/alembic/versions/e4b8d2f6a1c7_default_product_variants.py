"""Ensure every product has an orderable default variant.

Revision ID: e4b8d2f6a1c7
Revises: c3e7f1a5b9d2
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e4b8d2f6a1c7"
down_revision: str | Sequence[str] | None = "c3e7f1a5b9d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO product_variants (product_id, sku, name, price, is_active)
        SELECT p.id, 'AUTO-' || p.id, 'Standard', 0, true
        FROM products AS p
        WHERE NOT EXISTS (
            SELECT 1 FROM product_variants AS pv WHERE pv.product_id = p.id
        )
        """
    )


def downgrade() -> None:
    raise RuntimeError(
        "Default variants may be referenced by orders; downgrade requires review"
    )
