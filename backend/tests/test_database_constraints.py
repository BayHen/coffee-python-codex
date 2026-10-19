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
    Customer,
    Ingredient,
    InventoryTransaction,
    LoyaltyTransaction,
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
        insert(Order)
        .values(
            idempotency_key=f"order-{suffix}",
            request_fingerprint=f"fingerprint-{suffix}",
            subtotal_amount=Decimal("9.00"),
            discount_percent=Decimal("0.00"),
            discount_amount=Decimal("0.00"),
            total_amount=Decimal("9.00"),
        )
        .returning(Order.id)
    ).scalar_one()
    item_id = connection.execute(
        insert(OrderItem)
        .values(
            order_id=order_id,
            variant_id=variant_id,
            product_name="Latte",
            variant_name="Medium",
            sku=f"LATTE-{suffix}",
            quantity=2,
            unit_price=Decimal("4.50"),
            line_total=Decimal("9.00"),
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
                    product_name="Latte",
                    variant_name="Medium",
                    sku=f"LATTE-{uuid4().hex[:12]}",
                    quantity=0,
                    unit_price=Decimal("4.50"),
                    line_total=Decimal("0.00"),
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
    connection.execute(
        insert(Payment).values(
            **payment,
            idempotency_key="pay-one",
            request_fingerprint="payment-one",
        )
    )

    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                insert(Payment).values(
                    **payment,
                    idempotency_key="pay-one",
                    request_fingerprint="payment-one",
                )
            )

    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                insert(Payment).values(
                    **payment,
                    idempotency_key="pay-two",
                    request_fingerprint="payment-two",
                )
            )


def test_loyalty_points_cannot_be_earned_or_refunded_twice(
    connection: Connection,
) -> None:
    order_id, _, _ = create_order_item(connection)
    suffix = uuid4().hex[:12]
    customer_id = connection.execute(
        insert(Customer)
        .values(full_name="Loyal Customer", email=f"loyal-{suffix}@example.com")
        .returning(Customer.id)
    ).scalar_one()
    connection.execute(
        Order.__table__.update()
        .where(Order.id == order_id)
        .values(customer_id=customer_id, status="paid")
    )
    earn = {
        "customer_id": customer_id,
        "order_id": order_id,
        "transaction_type": "earn",
        "points_delta": 1,
        "reason": "Paid order reward",
    }
    connection.execute(
        insert(LoyaltyTransaction).values(
            **earn,
            idempotency_key=f"earn-one-{suffix}",
            request_fingerprint=f"earn-one-{suffix}",
        )
    )
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                insert(LoyaltyTransaction).values(
                    **earn,
                    idempotency_key=f"earn-two-{suffix}",
                    request_fingerprint=f"earn-two-{suffix}",
                )
            )

    refund = earn | {
        "transaction_type": "refund",
        "points_delta": -1,
        "reason": "Refunded order reward",
    }
    connection.execute(
        insert(LoyaltyTransaction).values(
            **refund,
            idempotency_key=f"refund-one-{suffix}",
            request_fingerprint=f"refund-one-{suffix}",
        )
    )
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                insert(LoyaltyTransaction).values(
                    **refund,
                    idempotency_key=f"refund-two-{suffix}",
                    request_fingerprint=f"refund-two-{suffix}",
                )
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
        "request_fingerprint": "stock-sale",
        "reason": "Test order consumption",
    }
    sale_id = connection.execute(
        insert(InventoryTransaction)
        .values(**sale, idempotency_key="stock-one")
        .returning(InventoryTransaction.id)
    ).scalar_one()

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
                    request_fingerprint="bad-purchase",
                    transaction_type="purchase",
                    quantity_delta=Decimal("-1.000"),
                    reason="Invalid test purchase",
                )
            )

    stock_return = {
        "ingredient_id": ingredient_id,
        "order_item_id": item_id,
        "reversal_of_id": sale_id,
        "transaction_type": "return",
        "quantity_delta": Decimal("250.000"),
        "reason": "Test order cancellation",
    }
    connection.execute(
        insert(InventoryTransaction).values(
            **stock_return,
            idempotency_key="return-one",
            request_fingerprint="return-one",
        )
    )
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                insert(InventoryTransaction).values(
                    **stock_return,
                    idempotency_key="return-two",
                    request_fingerprint="return-two",
                )
            )
