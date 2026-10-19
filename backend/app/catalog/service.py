"""Catalog business rules and transaction boundaries."""

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.catalog.repository import CatalogRepository
from app.catalog.schemas import (
    CategoryCreate,
    CategoryPage,
    CategoryUpdate,
    ProductCreate,
    ProductPage,
    ProductUpdate,
    VariantCreate,
    VariantUpdate,
)
from app.db.models import Category, Product, ProductVariant


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code, detail={"code": code, "message": message}
    )


class CatalogService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = CatalogRepository(db)

    def list_categories(self, **filters: object) -> CategoryPage:
        page = int(filters.pop("page"))
        page_size = int(filters.pop("page_size"))
        items, total = self.repository.list_categories(
            **filters, offset=(page - 1) * page_size, limit=page_size
        )
        return CategoryPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    def get_category(self, category_id: int) -> Category:
        category = self.repository.get_category(category_id)
        if category is None:
            raise api_error(404, "category_not_found", "Category not found")
        return category

    def create_category(self, payload: CategoryCreate) -> Category:
        try:
            with self.db.begin():
                category = Category(name=payload.name)
                self.repository.add_category(category)
                self.db.flush()
        except IntegrityError as exc:
            raise api_error(
                409, "category_name_exists", "Category name already exists"
            ) from exc
        return category

    def update_category(self, category_id: int, payload: CategoryUpdate) -> Category:
        try:
            with self.db.begin():
                category = self.repository.get_category(category_id, lock=True)
                if category is None:
                    raise api_error(404, "category_not_found", "Category not found")
                if "name" in payload.model_fields_set:
                    assert payload.name is not None
                    category.name = payload.name
                self.db.flush()
        except IntegrityError as exc:
            raise api_error(
                409, "category_name_exists", "Category name already exists"
            ) from exc
        return category

    def delete_category(self, category_id: int) -> None:
        with self.db.begin():
            category = self.repository.get_category(category_id, lock=True)
            if category is None:
                raise api_error(404, "category_not_found", "Category not found")
            if self.repository.category_has_products(category_id):
                raise api_error(
                    409,
                    "category_in_use",
                    "Category with products cannot be deleted",
                )
            self.repository.delete_category(category)

    def list_products(self, **filters: object) -> ProductPage:
        page = int(filters.pop("page"))
        page_size = int(filters.pop("page_size"))
        min_price = filters.get("min_price")
        max_price = filters.get("max_price")
        if min_price is not None and max_price is not None and min_price > max_price:
            raise api_error(
                422, "invalid_price_range", "min_price must not exceed max_price"
            )
        items, total = self.repository.list_products(
            **filters, offset=(page - 1) * page_size, limit=page_size
        )
        return ProductPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    def get_product(self, product_id: int) -> Product:
        product = self.repository.get_product(product_id)
        if product is None:
            raise api_error(404, "product_not_found", "Product not found")
        return product

    def create_product(self, payload: ProductCreate) -> Product:
        try:
            with self.db.begin():
                if self.repository.get_category(payload.category_id) is None:
                    raise api_error(404, "category_not_found", "Category not found")
                product = Product(**payload.model_dump())
                self.repository.add_product(product)
                self.db.flush()
                product_id = product.id
            return self.get_product(product_id)
        except IntegrityError as exc:
            raise api_error(
                409,
                "product_name_exists",
                "Product name already exists in this category",
            ) from exc

    def update_product(self, product_id: int, payload: ProductUpdate) -> Product:
        try:
            with self.db.begin():
                product = self.repository.get_product(product_id, lock=True)
                if product is None:
                    raise api_error(404, "product_not_found", "Product not found")
                changes = payload.model_dump(exclude_unset=True)
                category_id = changes.get("category_id")
                if (
                    category_id is not None
                    and self.repository.get_category(category_id) is None
                ):
                    raise api_error(404, "category_not_found", "Category not found")
                for field, value in changes.items():
                    setattr(product, field, value)
                self.db.flush()
            return self.get_product(product_id)
        except IntegrityError as exc:
            raise api_error(
                409,
                "product_name_exists",
                "Product name already exists in this category",
            ) from exc

    def deactivate_product(self, product_id: int) -> None:
        with self.db.begin():
            product = self.repository.get_product(product_id, lock=True)
            if product is None:
                raise api_error(404, "product_not_found", "Product not found")
            product.is_active = False

    def list_variants(self, product_id: int) -> list[ProductVariant]:
        self.get_product(product_id)
        return self.repository.list_variants(product_id)

    def get_variant(self, product_id: int, variant_id: int) -> ProductVariant:
        variant = self.repository.get_variant(product_id, variant_id)
        if variant is None:
            raise api_error(404, "variant_not_found", "Product variant not found")
        return variant

    def create_variant(self, product_id: int, payload: VariantCreate) -> ProductVariant:
        try:
            with self.db.begin():
                if self.repository.get_product(product_id) is None:
                    raise api_error(404, "product_not_found", "Product not found")
                variant = ProductVariant(product_id=product_id, **payload.model_dump())
                self.repository.add_variant(variant)
                self.db.flush()
        except IntegrityError as exc:
            raise api_error(
                409, "variant_conflict", "SKU or variant name already exists"
            ) from exc
        return variant

    def update_variant(
        self, product_id: int, variant_id: int, payload: VariantUpdate
    ) -> ProductVariant:
        try:
            with self.db.begin():
                variant = self.repository.get_variant(product_id, variant_id, lock=True)
                if variant is None:
                    raise api_error(
                        404, "variant_not_found", "Product variant not found"
                    )
                for field, value in payload.model_dump(exclude_unset=True).items():
                    setattr(variant, field, value)
                self.db.flush()
        except IntegrityError as exc:
            raise api_error(
                409, "variant_conflict", "SKU or variant name already exists"
            ) from exc
        return variant

    def deactivate_variant(self, product_id: int, variant_id: int) -> None:
        with self.db.begin():
            variant = self.repository.get_variant(product_id, variant_id, lock=True)
            if variant is None:
                raise api_error(404, "variant_not_found", "Product variant not found")
            variant.is_active = False
