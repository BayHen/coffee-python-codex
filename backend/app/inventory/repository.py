"""SQLAlchemy data access for the inventory ledger."""

from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    Ingredient,
    InventoryTransaction,
    OrderItem,
    ProductVariant,
    Recipe,
)


class InventoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def stock_expression(self):
        return func.coalesce(func.sum(InventoryTransaction.quantity_delta), 0)

    def get_ingredient(
        self, ingredient_id: int, *, lock: bool = False
    ) -> Ingredient | None:
        statement = select(Ingredient).where(Ingredient.id == ingredient_id)
        if lock:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def lock_ingredients(self, ingredient_ids: list[int]) -> list[Ingredient]:
        return list(
            self.db.scalars(
                select(Ingredient)
                .where(Ingredient.id.in_(ingredient_ids))
                .order_by(Ingredient.id)
                .with_for_update()
            ).all()
        )

    def ingredient_balance(self, ingredient_id: int) -> Decimal:
        value = self.db.scalar(
            select(self.stock_expression()).where(
                InventoryTransaction.ingredient_id == ingredient_id
            )
        )
        return Decimal(value or 0).quantize(Decimal("0.001"))

    def ingredient_view_row(self, ingredient_id: int):
        stock = self.stock_expression().label("current_stock")
        return self.db.execute(
            select(Ingredient, stock)
            .outerjoin(
                InventoryTransaction,
                InventoryTransaction.ingredient_id == Ingredient.id,
            )
            .where(Ingredient.id == ingredient_id)
            .group_by(Ingredient.id)
        ).one_or_none()

    def list_ingredient_rows(
        self,
        *,
        search: str | None,
        active_only: bool,
        low_stock_only: bool,
        offset: int,
        limit: int,
    ) -> tuple[list[tuple[Ingredient, Decimal]], int]:
        balance = self.stock_expression()
        filters = []
        if search:
            filters.append(
                or_(
                    Ingredient.name.ilike(f"%{search}%"),
                    Ingredient.sku.ilike(f"%{search}%"),
                )
            )
        if active_only:
            filters.append(Ingredient.is_active.is_(True))

        grouped = (
            select(Ingredient.id.label("ingredient_id"), balance.label("stock"))
            .outerjoin(
                InventoryTransaction,
                InventoryTransaction.ingredient_id == Ingredient.id,
            )
            .where(*filters)
            .group_by(Ingredient.id)
        )
        if low_stock_only:
            grouped = grouped.having(balance <= Ingredient.low_stock_threshold)
        grouped = grouped.subquery()
        total = self.db.scalar(select(func.count()).select_from(grouped)) or 0
        rows = self.db.execute(
            select(Ingredient, grouped.c.stock)
            .join(grouped, grouped.c.ingredient_id == Ingredient.id)
            .order_by(Ingredient.name, Ingredient.id)
            .offset(offset)
            .limit(limit)
        ).all()
        return [(row[0], Decimal(row[1])) for row in rows], total

    def ingredient_has_history_or_recipe(self, ingredient_id: int) -> bool:
        has_transaction = self.db.scalar(
            select(InventoryTransaction.id)
            .where(InventoryTransaction.ingredient_id == ingredient_id)
            .limit(1)
        )
        has_recipe = self.db.scalar(
            select(Recipe.id).where(Recipe.ingredient_id == ingredient_id).limit(1)
        )
        return has_transaction is not None or has_recipe is not None

    def get_recipe(
        self, variant_id: int, ingredient_id: int, *, lock: bool = False
    ) -> Recipe | None:
        statement = select(Recipe).where(
            Recipe.variant_id == variant_id, Recipe.ingredient_id == ingredient_id
        )
        if lock:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def list_recipes(self, variant_id: int) -> list[Recipe]:
        return list(
            self.db.scalars(
                select(Recipe)
                .where(Recipe.variant_id == variant_id)
                .order_by(Recipe.ingredient_id)
            ).all()
        )

    def lock_variant(self, variant_id: int) -> ProductVariant | None:
        return self.db.scalar(
            select(ProductVariant)
            .where(ProductVariant.id == variant_id)
            .with_for_update()
        )

    def lock_variants(self, variant_ids: list[int]) -> None:
        self.db.scalars(
            select(ProductVariant)
            .where(ProductVariant.id.in_(variant_ids))
            .order_by(ProductVariant.id)
            .with_for_update()
        ).all()

    def recipes_for_variants(self, variant_ids: list[int]) -> list[Recipe]:
        return list(
            self.db.scalars(
                select(Recipe)
                .where(Recipe.variant_id.in_(variant_ids))
                .order_by(Recipe.variant_id, Recipe.ingredient_id)
            ).all()
        )

    def sales_for_order(self, order_id: int) -> list[InventoryTransaction]:
        return list(
            self.db.scalars(
                select(InventoryTransaction)
                .join(OrderItem, OrderItem.id == InventoryTransaction.order_item_id)
                .where(
                    OrderItem.order_id == order_id,
                    InventoryTransaction.transaction_type == "sale",
                )
                .order_by(InventoryTransaction.ingredient_id, InventoryTransaction.id)
            ).all()
        )

    def get_transaction_by_key(self, key: str) -> InventoryTransaction | None:
        return self.db.scalar(
            select(InventoryTransaction).where(
                InventoryTransaction.idempotency_key == key
            )
        )

    def list_transactions(
        self,
        *,
        ingredient_id: int | None,
        transaction_type: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[InventoryTransaction], int]:
        filters = []
        if ingredient_id is not None:
            filters.append(InventoryTransaction.ingredient_id == ingredient_id)
        if transaction_type is not None:
            filters.append(InventoryTransaction.transaction_type == transaction_type)
        total = (
            self.db.scalar(select(func.count(InventoryTransaction.id)).where(*filters))
            or 0
        )
        rows = self.db.scalars(
            select(InventoryTransaction)
            .where(*filters)
            .order_by(InventoryTransaction.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return list(rows), total
