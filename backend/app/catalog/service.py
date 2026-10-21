"""Catalog business rules and transaction boundaries."""

import unicodedata

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.catalog.repository import CatalogRepository
from app.catalog.schemas import (
    CategoryCreate,
    CategoryDeletionOptions,
    CategoryPage,
    CategoryReassignDelete,
    CategoryReassignDeleteResult,
    CategoryUpdate,
    ProductCreate,
    ProductPage,
    ProductUpdate,
    ToppingCreate,
    ToppingUpdate,
    VariantCreate,
    VariantUpdate,
    normalize_text,
)
from app.db.models import Category, Product, ProductTopping, ProductVariant


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
                    if payload.name is None:
                        raise api_error(
                            422, "category_name_required", "Category name is required"
                        )
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

    def get_category_deletion_options(
        self, category_id: int
    ) -> CategoryDeletionOptions:
        category = self.repository.get_category(category_id)
        if category is None:
            raise api_error(404, "category_not_found", "Category not found")
        replacements = self.repository.list_replacement_categories(category_id)
        preferred = [
            item
            for item in replacements
            if unicodedata.normalize("NFC", normalize_text(item.name)).casefold()
            == "trà"
        ]
        return CategoryDeletionOptions(
            category=category,
            linked_product_count=self.repository.count_category_products(category_id),
            replacement_categories=replacements,
            preferred_replacement_category_id=(
                preferred[0].id if len(preferred) == 1 else None
            ),
        )

    def reassign_and_delete_category(
        self, category_id: int, payload: CategoryReassignDelete
    ) -> CategoryReassignDeleteResult:
        replacement_category_id = payload.replacement_category_id
        if replacement_category_id == category_id:
            raise api_error(
                422,
                "replacement_category_must_differ",
                "Replacement category must differ from deleted category",
            )
        try:
            with self.db.begin():
                categories = self.repository.lock_categories(
                    {category_id, replacement_category_id}
                )
                category = categories.get(category_id)
                if category is None:
                    raise api_error(404, "category_not_found", "Category not found")
                if replacement_category_id not in categories:
                    raise api_error(
                        404,
                        "replacement_category_not_found",
                        "Replacement category not found",
                    )
                reassigned_count = self.repository.reassign_products(
                    category_id, replacement_category_id
                )
                self.db.flush()
                if self.repository.category_has_products(category_id):
                    raise api_error(
                        409,
                        "category_reassignment_incomplete",
                        "Not all products could be reassigned",
                    )
                self.repository.delete_category(category)
                self.db.flush()
        except IntegrityError as exc:
            raise api_error(
                409,
                "category_reassignment_conflict",
                "Products conflict with the replacement category",
            ) from exc
        return CategoryReassignDeleteResult(
            deleted_category_id=category_id,
            replacement_category_id=replacement_category_id,
            reassigned_product_count=reassigned_count,
        )

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
                self.repository.add_variant(
                    ProductVariant(
                        product_id=product_id,
                        sku=f"AUTO-{product_id}",
                        name="Standard",
                        price=0,
                        is_active=True,
                    )
                )
                self.db.flush()
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
                self.repository.remove_unused_automatic_variant(product_id)
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

    def list_toppings(self, product_id: int) -> list[ProductTopping]:
        self.get_product(product_id)
        return self.repository.list_toppings(product_id)

    def create_topping(self, product_id: int, payload: ToppingCreate) -> ProductTopping:
        try:
            with self.db.begin():
                if self.repository.get_product(product_id) is None:
                    raise api_error(404, "product_not_found", "Product not found")
                topping = ProductTopping(product_id=product_id, **payload.model_dump())
                self.db.add(topping)
                self.db.flush()
            return topping
        except IntegrityError as exc:
            raise api_error(
                409, "topping_conflict", "Topping name already exists"
            ) from exc

    def update_topping(
        self, product_id: int, topping_id: int, payload: ToppingUpdate
    ) -> ProductTopping:
        try:
            with self.db.begin():
                topping = self.repository.get_topping(product_id, topping_id, lock=True)
                if topping is None:
                    raise api_error(404, "topping_not_found", "Topping not found")
                for field, value in payload.model_dump(exclude_unset=True).items():
                    setattr(topping, field, value)
                self.db.flush()
            return topping
        except IntegrityError as exc:
            raise api_error(
                409, "topping_conflict", "Topping name already exists"
            ) from exc
