"""Inventory rules, stock calculations, and order consumption hooks."""

import hashlib
import json
from collections import defaultdict
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    Ingredient,
    InventoryTransaction,
    Order,
    ProductVariant,
    Recipe,
)
from app.inventory.repository import InventoryRepository
from app.inventory.schemas import (
    IngredientCreate,
    IngredientPage,
    IngredientUpdate,
    IngredientView,
    InventoryTransactionPage,
    ManualMovementCreate,
    RecipeUpsert,
)

MILLI = Decimal("0.001")


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code, detail={"code": code, "message": message}
    )


def fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def ingredient_view(ingredient: Ingredient, stock: Decimal) -> IngredientView:
    current = Decimal(stock).quantize(MILLI)
    return IngredientView(
        id=ingredient.id,
        sku=ingredient.sku,
        name=ingredient.name,
        unit=ingredient.unit,
        low_stock_threshold=ingredient.low_stock_threshold,
        current_stock=current,
        is_low_stock=current <= ingredient.low_stock_threshold,
        is_active=ingredient.is_active,
    )


class InventoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = InventoryRepository(db)

    def get_ingredient(self, ingredient_id: int) -> IngredientView:
        row = self.repository.ingredient_view_row(ingredient_id)
        if row is None:
            raise api_error(404, "ingredient_not_found", "Ingredient not found")
        return ingredient_view(row[0], row[1])

    def list_ingredients(
        self,
        *,
        search: str | None,
        active_only: bool,
        low_stock_only: bool,
        page: int,
        page_size: int,
    ) -> IngredientPage:
        rows, total = self.repository.list_ingredient_rows(
            search=search,
            active_only=active_only,
            low_stock_only=low_stock_only,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return IngredientPage(
            items=[ingredient_view(ingredient, stock) for ingredient, stock in rows],
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    def create_ingredient(self, payload: IngredientCreate) -> IngredientView:
        try:
            with self.db.begin():
                ingredient = Ingredient(**payload.model_dump())
                self.db.add(ingredient)
                self.db.flush()
                ingredient_id = ingredient.id
            return self.get_ingredient(ingredient_id)
        except IntegrityError as exc:
            raise api_error(
                409, "ingredient_conflict", "Ingredient SKU or name already exists"
            ) from exc

    def update_ingredient(
        self, ingredient_id: int, payload: IngredientUpdate
    ) -> IngredientView:
        try:
            with self.db.begin():
                ingredient = self.repository.get_ingredient(ingredient_id, lock=True)
                if ingredient is None:
                    raise api_error(404, "ingredient_not_found", "Ingredient not found")
                changes = payload.model_dump(exclude_unset=True)
                if (
                    "unit" in changes
                    and changes["unit"] != ingredient.unit
                    and self.repository.ingredient_has_history_or_recipe(ingredient_id)
                ):
                    raise api_error(
                        409,
                        "ingredient_unit_in_use",
                        "Unit cannot change after recipes or stock history exist",
                    )
                for field, value in changes.items():
                    setattr(ingredient, field, value)
                self.db.flush()
            return self.get_ingredient(ingredient_id)
        except IntegrityError as exc:
            raise api_error(
                409, "ingredient_conflict", "Ingredient SKU or name already exists"
            ) from exc

    def deactivate_ingredient(self, ingredient_id: int) -> None:
        with self.db.begin():
            ingredient = self.repository.get_ingredient(ingredient_id, lock=True)
            if ingredient is None:
                raise api_error(404, "ingredient_not_found", "Ingredient not found")
            ingredient.is_active = False

    def list_recipes(self, variant_id: int) -> list[Recipe]:
        if self.db.get(ProductVariant, variant_id) is None:
            raise api_error(404, "variant_not_found", "Product variant not found")
        return self.repository.list_recipes(variant_id)

    def upsert_recipe(
        self, variant_id: int, ingredient_id: int, payload: RecipeUpsert
    ) -> Recipe:
        with self.db.begin():
            if self.repository.lock_variant(variant_id) is None:
                raise api_error(404, "variant_not_found", "Product variant not found")
            ingredient = self.repository.get_ingredient(ingredient_id, lock=True)
            if ingredient is None:
                raise api_error(404, "ingredient_not_found", "Ingredient not found")
            if not ingredient.is_active:
                raise api_error(409, "ingredient_inactive", "Ingredient is inactive")
            recipe = self.repository.get_recipe(variant_id, ingredient_id, lock=True)
            if recipe is None:
                recipe = Recipe(
                    variant_id=variant_id,
                    ingredient_id=ingredient_id,
                    quantity_required=payload.quantity_required,
                )
                self.db.add(recipe)
            else:
                recipe.quantity_required = payload.quantity_required
            self.db.flush()
        return recipe

    def delete_recipe(self, variant_id: int, ingredient_id: int) -> None:
        with self.db.begin():
            if self.repository.lock_variant(variant_id) is None:
                raise api_error(404, "variant_not_found", "Product variant not found")
            recipe = self.repository.get_recipe(variant_id, ingredient_id, lock=True)
            if recipe is None:
                raise api_error(404, "recipe_not_found", "Recipe not found")
            self.db.delete(recipe)

    def record_manual_movement(
        self,
        payload: ManualMovementCreate,
        idempotency_key: str,
        actor_user_id: int,
    ) -> InventoryTransaction:
        request_hash = fingerprint(
            {
                "ingredient_id": payload.ingredient_id,
                "transaction_type": payload.transaction_type,
                "quantity_delta": str(payload.quantity_delta.quantize(MILLI)),
                "reason": payload.reason,
            }
        )
        try:
            with self.db.begin():
                existing = self.repository.get_transaction_by_key(idempotency_key)
                if existing is not None:
                    return self._validate_existing(existing, request_hash)
                ingredient = self.repository.get_ingredient(
                    payload.ingredient_id, lock=True
                )
                if ingredient is None:
                    raise api_error(404, "ingredient_not_found", "Ingredient not found")
                if not ingredient.is_active:
                    raise api_error(
                        409, "ingredient_inactive", "Ingredient is inactive"
                    )
                current = self.repository.ingredient_balance(ingredient.id)
                delta = payload.quantity_delta.quantize(MILLI)
                if current + delta < 0:
                    raise api_error(
                        409, "insufficient_stock", "Stock cannot become negative"
                    )
                existing = self.repository.get_transaction_by_key(idempotency_key)
                if existing is not None:
                    return self._validate_existing(existing, request_hash)
                transaction = InventoryTransaction(
                    ingredient_id=ingredient.id,
                    actor_user_id=actor_user_id,
                    idempotency_key=idempotency_key,
                    request_fingerprint=request_hash,
                    transaction_type=payload.transaction_type,
                    quantity_delta=delta,
                    reason=payload.reason,
                )
                self.db.add(transaction)
                self.db.flush()
            return transaction
        except IntegrityError as exc:
            with self.db.begin():
                existing = self.repository.get_transaction_by_key(idempotency_key)
                if existing is not None:
                    return self._validate_existing(existing, request_hash)
            raise api_error(
                409, "inventory_conflict", "Inventory update conflicted"
            ) from exc

    @staticmethod
    def _validate_existing(
        transaction: InventoryTransaction, request_hash: str
    ) -> InventoryTransaction:
        if transaction.request_fingerprint != request_hash:
            raise api_error(
                409,
                "idempotency_key_reused",
                "Idempotency-Key was already used for a different inventory request",
            )
        return transaction

    def list_transactions(
        self,
        *,
        ingredient_id: int | None,
        transaction_type: str | None,
        page: int,
        page_size: int,
    ) -> InventoryTransactionPage:
        items, total = self.repository.list_transactions(
            ingredient_id=ingredient_id,
            transaction_type=transaction_type,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return InventoryTransactionPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    def consume_for_order(self, order: Order, actor_user_id: int) -> None:
        quantities: dict[int, int] = defaultdict(int)
        for item in order.items:
            quantities[item.variant_id] += item.quantity
        variant_ids = sorted(quantities)
        self.repository.lock_variants(variant_ids)
        recipes = self.repository.recipes_for_variants(variant_ids)
        required_by_ingredient: dict[int, Decimal] = defaultdict(Decimal)
        for recipe in recipes:
            required_by_ingredient[recipe.ingredient_id] += (
                recipe.quantity_required * quantities[recipe.variant_id]
            )
        ingredients = self.repository.lock_ingredients(sorted(required_by_ingredient))
        ingredient_map = {ingredient.id: ingredient for ingredient in ingredients}
        for ingredient_id, required in required_by_ingredient.items():
            ingredient = ingredient_map[ingredient_id]
            if not ingredient.is_active:
                raise api_error(
                    409,
                    "ingredient_inactive",
                    f"Ingredient {ingredient.sku} is inactive",
                )
            if self.repository.ingredient_balance(ingredient_id) < required:
                raise api_error(
                    409,
                    "insufficient_stock",
                    f"Insufficient stock for ingredient {ingredient.sku}",
                )
        recipe_by_variant: dict[int, list[Recipe]] = defaultdict(list)
        for recipe in recipes:
            recipe_by_variant[recipe.variant_id].append(recipe)
        for item in order.items:
            for recipe in recipe_by_variant[item.variant_id]:
                quantity = (recipe.quantity_required * item.quantity).quantize(MILLI)
                key = (
                    f"order:{order.id}:item:{item.id}:ingredient:"
                    f"{recipe.ingredient_id}:sale"
                )
                self.db.add(
                    InventoryTransaction(
                        ingredient_id=recipe.ingredient_id,
                        order_item_id=item.id,
                        actor_user_id=actor_user_id,
                        idempotency_key=key,
                        request_fingerprint=fingerprint(
                            {
                                "order_item_id": item.id,
                                "ingredient_id": recipe.ingredient_id,
                                "quantity": str(quantity),
                            }
                        ),
                        transaction_type="sale",
                        quantity_delta=-quantity,
                        reason=f"Consumed by order {order.id}",
                    )
                )

    def return_for_cancelled_order(self, order: Order, actor_user_id: int) -> None:
        sales = self.repository.sales_for_order(order.id)
        self.repository.lock_ingredients(sorted({sale.ingredient_id for sale in sales}))
        for sale in sales:
            key = f"return:order:{order.id}:sale:{sale.id}"
            request_hash = fingerprint({"reversal_of_id": sale.id})
            existing = self.repository.get_transaction_by_key(key)
            if existing is not None:
                self._validate_existing(existing, request_hash)
                continue
            self.db.add(
                InventoryTransaction(
                    ingredient_id=sale.ingredient_id,
                    order_item_id=sale.order_item_id,
                    actor_user_id=actor_user_id,
                    reversal_of_id=sale.id,
                    idempotency_key=key,
                    request_fingerprint=request_hash,
                    transaction_type="return",
                    quantity_delta=-sale.quantity_delta,
                    reason=f"Returned after order {order.id} cancellation",
                )
            )
