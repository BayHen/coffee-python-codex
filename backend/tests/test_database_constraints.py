"""PostgreSQL integration tests; each test rolls back its own data."""

import os
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import Connection, insert, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    Category,
    Ingredient,
    InventoryTransaction,
    Order,
    OrderItem,
    Payment,
    Product,
    ProductVariant,
)
from app.db.session import create_db_engine


@pytest.fixture
def connection() -> Connection:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a migrated, dedicated PostgreSQL test DB")
    if not (make_url(url).database or "").endswith("_test"):
        pytest.fail("TEST_DATABASE_URL database name must end with _test")

    engine = create_db_engine(url)
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                yield connection
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def create_order_item(connection: Connection) -> tuple[int, int, int]:
    suffix = uuid4().hex[:12]
    category_id = connection.execute(
        insert(Category).values(name=f"Coffee {suffix}").returning(Category.id)
    ).scalar_one()
    product_id = connection.execute(
        insert(Product)
        .values(category_id=category_id, name="Latte")
        .returning(Product.id)
    ).scalar_one()
    variant_id = connection.execute(
        insert(ProductVariant)
        .values(
            product_id=product_id,
            sku=f"LATTE-{suffix}",
            name="Medium",
            price=Decimal("4.50"),
        )
        .returning(ProductVariant.id)
    ).scalar_one()
    order_id = connection.execute(
        insert(Order).values(total_amount=Decimal("9.00")).returning(Order.id)
    ).scalar_one()
    item_id = connection.execute(
        insert(OrderItem)
        .values(
            order_id=order_id,
            variant_id=variant_id,
            quantity=2,
            unit_price=Decimal("4.50"),
        )
        .returning(OrderItem.id)
    ).scalar_one()
    return order_id, variant_id, item_id


def test_order_item_keeps_sale_price(connection: Connection) -> None:
    order_id, variant_id, item_id = create_order_item(connection)
    connection.execute(
        ProductVariant.__table__.update()
        .where(ProductVariant.id == variant_id)
        .values(price=Decimal("5.25"))
    )

    sale_price = connection.scalar(
        select(OrderItem.unit_price).where(OrderItem.id == item_id)
    )
    assert sale_price == Decimal("4.50")

    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                insert(OrderItem).values(
                    order_id=order_id,
                    variant_id=variant_id,
                    quantity=0,
                    unit_price=Decimal("4.50"),
                )
            )


def test_payment_retries_cannot_double_charge(connection: Connection) -> None:
    order_id, _, _ = create_order_item(connection)
    payment = {
        "order_id": order_id,
        "method": "cash",
        "status": "succeeded",
        "amount": Decimal("9.00"),
    }
    connection.execute(insert(Payment).values(**payment, idempotency_key="pay-one"))

    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                insert(Payment).values(**payment, idempotency_key="pay-one")
            )

    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                insert(Payment).values(**payment, idempotency_key="pay-two")
            )


def test_stock_sale_event_cannot_be_recorded_twice(connection: Connection) -> None:
    _, _, item_id = create_order_item(connection)
    ingredient_id = connection.execute(
        insert(Ingredient)
        .values(sku=f"MILK-{uuid4().hex[:12]}", name="Milk", unit="ml")
        .returning(Ingredient.id)
    ).scalar_one()
    sale = {
        "ingredient_id": ingredient_id,
        "order_item_id": item_id,
        "transaction_type": "sale",
        "quantity_delta": Decimal("-250.000"),
    }
    connection.execute(
        insert(InventoryTransaction).values(**sale, idempotency_key="stock-one")
    )

    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                insert(InventoryTransaction).values(**sale, idempotency_key="stock-one")
            )

    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                insert(InventoryTransaction).values(**sale, idempotency_key="stock-two")
            )

    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                insert(InventoryTransaction).values(
                    ingredient_id=ingredient_id,
                    idempotency_key="bad-purchase",
                    transaction_type="purchase",
                    quantity_delta=Decimal("-1.000"),
                )
            )
