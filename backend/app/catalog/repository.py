"""SQLAlchemy queries for the catalog module."""

from decimal import Decimal

from sqlalchemy import Select, exists, func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    Category,
    OrderItem,
    OrderItemTopping,
    Product,
    ProductTopping,
    ProductVariant,
    Recipe,
)

VIETNAMESE_SEARCH_SOURCE = (
    "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
)
VIETNAMESE_SEARCH_TARGET = (
    "aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd"
)


def normalize_search(value: str) -> str:
    replacements = str.maketrans(VIETNAMESE_SEARCH_SOURCE, VIETNAMESE_SEARCH_TARGET)
    return value.casefold().translate(replacements)


class CatalogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_category(self, category_id: int, *, lock: bool = False) -> Category | None:
        statement = select(Category).where(Category.id == category_id)
        if lock:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def list_categories(
        self,
        *,
        search: str | None,
        sort_by: str,
        sort_direction: str,
        offset: int,
        limit: int,
    ) -> tuple[list[Category], int]:
        filters = []
        if search:
            filters.append(Category.name.ilike(f"%{search}%"))
        total = self.db.scalar(select(func.count(Category.id)).where(*filters)) or 0
        order_column = Category.name if sort_by == "name" else Category.id
        order = order_column.desc() if sort_direction == "desc" else order_column.asc()
        rows = self.db.scalars(
            select(Category)
            .where(*filters)
            .order_by(order, Category.id)
            .offset(offset)
            .limit(limit)
        ).all()
        return list(rows), total

    def category_has_products(self, category_id: int) -> bool:
        return bool(
            self.db.scalar(select(exists().where(Product.category_id == category_id)))
        )

    def count_category_products(self, category_id: int) -> int:
        return (
            self.db.scalar(
                select(func.count(Product.id)).where(Product.category_id == category_id)
            )
            or 0
        )

    def list_replacement_categories(self, category_id: int) -> list[Category]:
        return list(
            self.db.scalars(
                select(Category)
                .where(Category.id != category_id)
                .order_by(Category.name, Category.id)
            ).all()
        )

    def lock_categories(self, category_ids: set[int]) -> dict[int, Category]:
        categories = self.db.scalars(
            select(Category)
            .where(Category.id.in_(category_ids))
            .order_by(Category.id)
            .with_for_update()
        ).all()
        return {category.id: category for category in categories}

    def reassign_products(
        self, source_category_id: int, replacement_category_id: int
    ) -> int:
        result = self.db.execute(
            update(Product)
            .where(Product.category_id == source_category_id)
            .values(category_id=replacement_category_id)
        )
        return result.rowcount or 0

    def add_category(self, category: Category) -> None:
        self.db.add(category)

    def delete_category(self, category: Category) -> None:
        self.db.delete(category)

    def product_statement(self) -> Select[tuple[Product]]:
        return select(Product).options(
            selectinload(Product.category),
            selectinload(Product.variants),
            selectinload(Product.toppings),
        )

    def get_product(self, product_id: int, *, lock: bool = False) -> Product | None:
        statement = self.product_statement().where(Product.id == product_id)
        if lock:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def list_products(
        self,
        *,
        search: str | None,
        category_id: int | None,
        is_active: bool | None,
        min_price: Decimal | None,
        max_price: Decimal | None,
        sort_by: str,
        sort_direction: str,
        offset: int,
        limit: int,
    ) -> tuple[list[Product], int]:
        filters = []
        if search:
            normalized_search = normalize_search(search)
            normalized_product_name = func.translate(
                func.lower(Product.name),
                VIETNAMESE_SEARCH_SOURCE,
                VIETNAMESE_SEARCH_TARGET,
            )
            variant_match = exists().where(
                ProductVariant.product_id == Product.id,
                or_(
                    ProductVariant.name.ilike(f"%{search}%"),
                    ProductVariant.sku.ilike(f"%{search}%"),
                ),
            )
            filters.append(
                or_(
                    normalized_product_name.contains(
                        normalized_search, autoescape=True
                    ),
                    variant_match,
                )
            )
        if category_id is not None:
            filters.append(Product.category_id == category_id)
        if is_active is not None:
            filters.append(Product.is_active.is_(is_active))
        if min_price is not None or max_price is not None:
            price_filters = [ProductVariant.product_id == Product.id]
            if min_price is not None:
                price_filters.append(ProductVariant.price >= min_price)
            if max_price is not None:
                price_filters.append(ProductVariant.price <= max_price)
            filters.append(exists().where(*price_filters))

        total = self.db.scalar(select(func.count(Product.id)).where(*filters)) or 0
        order_column = Product.name if sort_by == "name" else Product.id
        order = order_column.desc() if sort_direction == "desc" else order_column.asc()
        rows = self.db.scalars(
            self.product_statement()
            .where(*filters)
            .order_by(order, Product.id)
            .offset(offset)
            .limit(limit)
        ).all()
        return list(rows), total

    def add_product(self, product: Product) -> None:
        self.db.add(product)

    def get_variant(
        self, product_id: int, variant_id: int, *, lock: bool = False
    ) -> ProductVariant | None:
        statement = select(ProductVariant).where(
            ProductVariant.id == variant_id, ProductVariant.product_id == product_id
        )
        if lock:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def list_variants(self, product_id: int) -> list[ProductVariant]:
        return list(
            self.db.scalars(
                select(ProductVariant)
                .where(ProductVariant.product_id == product_id)
                .order_by(ProductVariant.id)
            ).all()
        )

    def add_variant(self, variant: ProductVariant) -> None:
        self.db.add(variant)

    def count_active_variants(self, product_id: int) -> int:
        return (
            self.db.scalar(
                select(func.count(ProductVariant.id)).where(
                    ProductVariant.product_id == product_id,
                    ProductVariant.is_active.is_(True),
                )
            )
            or 0
        )

    def variant_has_dependencies(self, variant_id: int) -> bool:
        return bool(
            self.db.scalar(
                select(
                    or_(
                        exists().where(OrderItem.variant_id == variant_id),
                        exists().where(Recipe.variant_id == variant_id),
                    )
                )
            )
        )

    def delete_variant(self, variant: ProductVariant) -> None:
        self.db.delete(variant)

    def remove_unused_automatic_variant(self, product_id: int) -> None:
        variant = self.db.scalar(
            select(ProductVariant).where(
                ProductVariant.product_id == product_id,
                ProductVariant.sku == f"AUTO-{product_id}",
                ~exists().where(OrderItem.variant_id == ProductVariant.id),
            )
        )
        if variant is not None:
            self.db.delete(variant)

    def get_topping(
        self, product_id: int, topping_id: int, *, lock: bool = False
    ) -> ProductTopping | None:
        statement = select(ProductTopping).where(
            ProductTopping.id == topping_id,
            ProductTopping.product_id == product_id,
        )
        if lock:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def list_toppings(self, product_id: int) -> list[ProductTopping]:
        return list(
            self.db.scalars(
                select(ProductTopping)
                .where(ProductTopping.product_id == product_id)
                .order_by(ProductTopping.id)
            ).all()
        )

    def topping_has_order_items(self, topping_id: int) -> bool:
        return bool(
            self.db.scalar(
                select(exists().where(OrderItemTopping.topping_id == topping_id))
            )
        )

    def delete_topping(self, topping: ProductTopping) -> None:
        self.db.delete(topping)
