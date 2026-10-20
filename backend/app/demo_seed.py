"""Opt-in, idempotent demo data with reserved example identities."""

import hashlib
import os
import sys
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.db.models import (
    CafeTable,
    Category,
    Ingredient,
    InventoryTransaction,
    Product,
    ProductVariant,
    Role,
    User,
)
from app.db.session import get_session_factory

DEMO_EMAIL = "demo.admin@example.com"
ROLE_NAMES = ("Admin", "Manager", "Staff")


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def seed(db: Session, password: str) -> None:
    for name in ROLE_NAMES:
        db.execute(insert(Role).values(name=name).on_conflict_do_nothing())
    admin_role = db.scalar(select(Role).where(Role.name == "Admin"))
    if admin_role is None:
        raise RuntimeError("Admin role could not be initialized")
    user = db.scalar(select(User).where(func.lower(User.email) == DEMO_EMAIL))
    if user is None:
        user = User(
            role_id=admin_role.id,
            email=DEMO_EMAIL,
            password_hash=hash_password(password),
            is_active=True,
        )
        db.add(user)
        db.flush()

    for number in ("01", "02", "03", "04", "05", "06"):
        if (
            db.scalar(select(CafeTable.id).where(CafeTable.table_number == number))
            is None
        ):
            db.add(CafeTable(table_number=number, name=f"Demo Table {number}"))

    category = db.scalar(
        select(Category).where(func.lower(Category.name) == "demo coffee")
    )
    if category is None:
        category = Category(name="Demo Coffee")
        db.add(category)
        db.flush()

    product = db.scalar(
        select(Product).where(
            Product.category_id == category.id,
            func.lower(Product.name) == "demo latte",
        )
    )
    if product is None:
        product = Product(
            category_id=category.id,
            name="Demo Latte",
            base_price=Decimal("35000.00"),
        )
        db.add(product)
        db.flush()

    for sku, name, price in (
        ("DEMO-LATTE-S", "Size S", Decimal("0.00")),
        ("DEMO-LATTE-M", "Size M", Decimal("10000.00")),
        ("DEMO-LATTE-L", "Size L", Decimal("20000.00")),
    ):
        if (
            db.scalar(select(ProductVariant.id).where(ProductVariant.sku == sku))
            is None
        ):
            db.add(
                ProductVariant(
                    product_id=product.id,
                    sku=sku,
                    name=name,
                    price=price,
                )
            )

    for sku, name, unit, threshold, opening in (
        ("DEMO-BEAN", "Demo coffee beans", "g", "500.000", "5000.000"),
        ("DEMO-MILK", "Demo milk", "ml", "1000.000", "8000.000"),
        ("DEMO-CUP", "Demo paper cup", "piece", "20.000", "100.000"),
    ):
        ingredient = db.scalar(select(Ingredient).where(Ingredient.sku == sku))
        if ingredient is None:
            ingredient = Ingredient(
                sku=sku,
                name=name,
                unit=unit,
                low_stock_threshold=Decimal(threshold),
            )
            db.add(ingredient)
            db.flush()
        key = f"demo-opening:{sku}"
        if (
            db.scalar(
                select(InventoryTransaction.id).where(
                    InventoryTransaction.idempotency_key == key
                )
            )
            is None
        ):
            db.add(
                InventoryTransaction(
                    ingredient_id=ingredient.id,
                    actor_user_id=user.id,
                    idempotency_key=key,
                    request_fingerprint=fingerprint(key),
                    transaction_type="purchase",
                    quantity_delta=Decimal(opening),
                    reason="Safe demo opening stock",
                )
            )


def main() -> int:
    if os.environ.get("APP_ENV", "development").lower() == "production":
        print("Demo seed is disabled when APP_ENV=production", file=sys.stderr)
        return 1
    password = os.environ.get("DEMO_ADMIN_PASSWORD", "")
    if len(password) < 12 or len(password) > 1024 or not password.strip():
        print("DEMO_ADMIN_PASSWORD must contain 12-1024 characters", file=sys.stderr)
        return 1
    try:
        with get_session_factory()() as db, db.begin():
            seed(db, password)
    except (RuntimeError, SQLAlchemyError):
        print("Demo seed failed", file=sys.stderr)
        return 1
    print(f"Demo data ready. Admin email: {DEMO_EMAIL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
