"""REST API for ingredients, recipes, stock, and immutable ledger entries."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, require_roles
from app.db.session import get_session
from app.inventory.schemas import (
    IngredientCreate,
    IngredientPage,
    IngredientUpdate,
    IngredientView,
    InventoryTransactionPage,
    InventoryTransactionView,
    ManualMovementCreate,
    RecipeUpsert,
    RecipeView,
)
from app.inventory.service import InventoryService

router = APIRouter(tags=["inventory"])
Reader = Annotated[Principal, Depends(require_roles("Admin", "Manager", "Staff"))]
Writer = Annotated[Principal, Depends(require_roles("Admin", "Manager"))]
Db = Annotated[Session, Depends(get_session)]
IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    ),
]


@router.get("/ingredients", response_model=IngredientPage)
def list_ingredients(
    _principal: Reader,
    db: Db,
    search: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    active_only: bool = True,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> IngredientPage:
    return InventoryService(db).list_ingredients(
        search=search,
        active_only=active_only,
        low_stock_only=False,
        page=page,
        page_size=page_size,
    )


@router.get("/ingredients/low-stock", response_model=IngredientPage)
def list_low_stock(
    _principal: Reader,
    db: Db,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> IngredientPage:
    return InventoryService(db).list_ingredients(
        search=None,
        active_only=True,
        low_stock_only=True,
        page=page,
        page_size=page_size,
    )


@router.post("/ingredients", response_model=IngredientView, status_code=201)
def create_ingredient(
    payload: IngredientCreate, _principal: Writer, db: Db
) -> IngredientView:
    return InventoryService(db).create_ingredient(payload)


@router.get("/ingredients/{ingredient_id}", response_model=IngredientView)
def get_ingredient(ingredient_id: int, _principal: Reader, db: Db) -> IngredientView:
    return InventoryService(db).get_ingredient(ingredient_id)


@router.patch("/ingredients/{ingredient_id}", response_model=IngredientView)
def update_ingredient(
    ingredient_id: int,
    payload: IngredientUpdate,
    _principal: Writer,
    db: Db,
) -> IngredientView:
    return InventoryService(db).update_ingredient(ingredient_id, payload)


@router.delete("/ingredients/{ingredient_id}", status_code=204)
def deactivate_ingredient(ingredient_id: int, _principal: Writer, db: Db) -> Response:
    InventoryService(db).deactivate_ingredient(ingredient_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/product-variants/{variant_id}/recipes", response_model=list[RecipeView])
def list_recipes(variant_id: int, _principal: Reader, db: Db) -> list[RecipeView]:
    return InventoryService(db).list_recipes(variant_id)


@router.put(
    "/product-variants/{variant_id}/recipes/{ingredient_id}",
    response_model=RecipeView,
)
def upsert_recipe(
    variant_id: int,
    ingredient_id: int,
    payload: RecipeUpsert,
    _principal: Writer,
    db: Db,
) -> RecipeView:
    return InventoryService(db).upsert_recipe(variant_id, ingredient_id, payload)


@router.delete(
    "/product-variants/{variant_id}/recipes/{ingredient_id}", status_code=204
)
def delete_recipe(
    variant_id: int, ingredient_id: int, _principal: Writer, db: Db
) -> Response:
    InventoryService(db).delete_recipe(variant_id, ingredient_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/inventory/transactions", response_model=InventoryTransactionPage)
def list_transactions(
    _principal: Reader,
    db: Db,
    ingredient_id: Annotated[int | None, Query(gt=0)] = None,
    transaction_type: Literal["purchase", "sale", "return", "adjustment", "waste"]
    | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> InventoryTransactionPage:
    return InventoryService(db).list_transactions(
        ingredient_id=ingredient_id,
        transaction_type=transaction_type,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/inventory/transactions",
    response_model=InventoryTransactionView,
    status_code=201,
)
def record_manual_movement(
    payload: ManualMovementCreate,
    idempotency_key: IdempotencyKey,
    principal: Writer,
    db: Db,
) -> InventoryTransactionView:
    return InventoryService(db).record_manual_movement(
        payload, idempotency_key, principal.user_id
    )
