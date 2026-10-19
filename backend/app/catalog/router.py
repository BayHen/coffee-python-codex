"""REST endpoints for categories, products, and product variants."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, require_roles
from app.catalog.schemas import (
    CategoryCreate,
    CategoryPage,
    CategorySort,
    CategoryUpdate,
    CategoryView,
    ProductCreate,
    ProductPage,
    ProductSort,
    ProductUpdate,
    ProductView,
    SortDirection,
    VariantCreate,
    VariantUpdate,
    VariantView,
)
from app.catalog.service import CatalogService
from app.db.session import get_session

router = APIRouter(tags=["catalog"])
Reader = Annotated[Principal, Depends(require_roles("Admin", "Manager", "Staff"))]
Writer = Annotated[Principal, Depends(require_roles("Admin", "Manager"))]
Db = Annotated[Session, Depends(get_session)]


@router.get("/categories", response_model=CategoryPage)
def list_categories(
    _principal: Reader,
    db: Db,
    search: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    sort_by: CategorySort = "name",
    sort_direction: SortDirection = "asc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CategoryPage:
    return CatalogService(db).list_categories(
        search=search,
        sort_by=sort_by,
        sort_direction=sort_direction,
        page=page,
        page_size=page_size,
    )


@router.post("/categories", response_model=CategoryView, status_code=201)
def create_category(
    payload: CategoryCreate, _principal: Writer, db: Db
) -> CategoryView:
    return CatalogService(db).create_category(payload)


@router.get("/categories/{category_id}", response_model=CategoryView)
def get_category(category_id: int, _principal: Reader, db: Db) -> CategoryView:
    return CatalogService(db).get_category(category_id)


@router.patch("/categories/{category_id}", response_model=CategoryView)
def update_category(
    category_id: int, payload: CategoryUpdate, _principal: Writer, db: Db
) -> CategoryView:
    return CatalogService(db).update_category(category_id, payload)


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: int, _principal: Writer, db: Db) -> Response:
    CatalogService(db).delete_category(category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/products", response_model=ProductPage)
def list_products(
    _principal: Reader,
    db: Db,
    search: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    category_id: Annotated[int | None, Query(gt=0)] = None,
    is_active: bool | None = None,
    min_price: Annotated[Decimal | None, Query(ge=0, decimal_places=2)] = None,
    max_price: Annotated[Decimal | None, Query(ge=0, decimal_places=2)] = None,
    sort_by: ProductSort = "name",
    sort_direction: SortDirection = "asc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ProductPage:
    return CatalogService(db).list_products(
        search=search,
        category_id=category_id,
        is_active=is_active,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by,
        sort_direction=sort_direction,
        page=page,
        page_size=page_size,
    )


@router.post("/products", response_model=ProductView, status_code=201)
def create_product(payload: ProductCreate, _principal: Writer, db: Db) -> ProductView:
    return CatalogService(db).create_product(payload)


@router.get("/products/{product_id}", response_model=ProductView)
def get_product(product_id: int, _principal: Reader, db: Db) -> ProductView:
    return CatalogService(db).get_product(product_id)


@router.patch("/products/{product_id}", response_model=ProductView)
def update_product(
    product_id: int, payload: ProductUpdate, _principal: Writer, db: Db
) -> ProductView:
    return CatalogService(db).update_product(product_id, payload)


@router.delete("/products/{product_id}", status_code=204)
def deactivate_product(product_id: int, _principal: Writer, db: Db) -> Response:
    CatalogService(db).deactivate_product(product_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/products/{product_id}/variants", response_model=list[VariantView])
def list_variants(product_id: int, _principal: Reader, db: Db) -> list[VariantView]:
    return CatalogService(db).list_variants(product_id)


@router.post(
    "/products/{product_id}/variants", response_model=VariantView, status_code=201
)
def create_variant(
    product_id: int, payload: VariantCreate, _principal: Writer, db: Db
) -> VariantView:
    return CatalogService(db).create_variant(product_id, payload)


@router.get("/products/{product_id}/variants/{variant_id}", response_model=VariantView)
def get_variant(
    product_id: int, variant_id: int, _principal: Reader, db: Db
) -> VariantView:
    return CatalogService(db).get_variant(product_id, variant_id)


@router.patch(
    "/products/{product_id}/variants/{variant_id}", response_model=VariantView
)
def update_variant(
    product_id: int,
    variant_id: int,
    payload: VariantUpdate,
    _principal: Writer,
    db: Db,
) -> VariantView:
    return CatalogService(db).update_variant(product_id, variant_id, payload)


@router.delete("/products/{product_id}/variants/{variant_id}", status_code=204)
def deactivate_variant(
    product_id: int, variant_id: int, _principal: Writer, db: Db
) -> Response:
    CatalogService(db).deactivate_variant(product_id, variant_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
