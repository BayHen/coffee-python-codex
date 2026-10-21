"""Generate immutable product variant SKUs.

Revision ID: f2a6c8e0b4d1
Revises: e4b8d2f6a1c7
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f2a6c8e0b4d1"
down_revision: str | Sequence[str] | None = "e4b8d2f6a1c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE product_variant_sku_seq")
    op.execute(
        """
        SELECT setval(
            'product_variant_sku_seq',
            COALESCE(
                (
                    SELECT MAX(substring(sku FROM '^VAR-([0-9]+)$')::bigint)
                    FROM product_variants
                    WHERE sku ~ '^VAR-[0-9]+$'
                ),
                0
            ) + 1,
            false
        )
        """
    )
    op.execute(
        """
        ALTER TABLE product_variants
        ALTER COLUMN sku SET DEFAULT
            ('VAR-' || lpad(nextval('product_variant_sku_seq')::text, 6, '0'))
        """
    )
    op.execute(
        """
        CREATE FUNCTION prevent_product_variant_sku_update()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.sku IS DISTINCT FROM OLD.sku THEN
                RAISE EXCEPTION 'product variant SKU is immutable'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_product_variant_sku_immutable
        BEFORE UPDATE OF sku ON product_variants
        FOR EACH ROW
        EXECUTE FUNCTION prevent_product_variant_sku_update()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_product_variant_sku_immutable ON product_variants")
    op.execute("DROP FUNCTION prevent_product_variant_sku_update()")
    op.execute("ALTER TABLE product_variants ALTER COLUMN sku DROP DEFAULT")
    op.execute("DROP SEQUENCE product_variant_sku_seq")
