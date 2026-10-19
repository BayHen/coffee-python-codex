"""PostgreSQL concurrency check for simulated payment serialization."""

import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.db.models import (
    Category,
    Order,
    OrderEvent,
    OrderItem,
    Payment,
    Product,
    ProductVariant,
    Role,
    User,
)
from app.db.session import create_db_engine
from app.orders.schemas import SimulatedPaymentCreate
from app.orders.service import OrderService


def test_concurrent_successful_payments_are_serialized() -> None:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a migrated PostgreSQL test DB")
    if not (make_url(url).database or "").endswith("_test"):
        pytest.fail("TEST_DATABASE_URL database name must end with _test")

    suffix = uuid4().hex
    engine = create_db_engine(url)
    ids: dict[str, int] = {}
    try:
        with Session(engine) as db, db.begin():
            role = Role(name=f"Concurrency-{suffix}")
            db.add(role)
            db.flush()
            user = User(
                role_id=role.id,
                email=f"concurrency-{suffix}@example.com",
                password_hash=hash_password(uuid4().hex),
            )
            category = Category(name=f"Concurrency {suffix}")
            db.add_all([user, category])
            db.flush()
            product = Product(category_id=category.id, name=f"Coffee {suffix}")
            db.add(product)
            db.flush()
            variant = ProductVariant(
                product_id=product.id,
                sku=f"CONCURRENT-{suffix}",
                name="Regular",
                price=Decimal("5.00"),
            )
            db.add(variant)
            db.flush()
            order = Order(
                idempotency_key=f"order-{suffix}",
                request_fingerprint=suffix,
                status="placed",
                subtotal_amount=Decimal("5.00"),
                discount_percent=Decimal("0.00"),
                discount_amount=Decimal("0.00"),
                total_amount=Decimal("5.00"),
                items=[
                    OrderItem(
                        variant_id=variant.id,
                        product_name=product.name,
                        variant_name=variant.name,
                        sku=variant.sku,
                        quantity=1,
                        unit_price=Decimal("5.00"),
                        line_total=Decimal("5.00"),
                    )
                ],
            )
            db.add(order)
            db.flush()
            ids.update(
                role=role.id,
                user=user.id,
                category=category.id,
                product=product.id,
                variant=variant.id,
                order=order.id,
            )

        barrier = Barrier(2)

        def pay(attempt: int) -> tuple[str, int]:
            barrier.wait(timeout=10)
            with Session(engine, expire_on_commit=False) as db:
                try:
                    payment = OrderService(db).simulate_payment(
                        ids["order"],
                        SimulatedPaymentCreate(method="cash", outcome="succeeded"),
                        f"payment-{suffix}-{attempt}",
                        ids["user"],
                    )
                    return "succeeded", payment.id
                except HTTPException as exc:
                    return "rejected", exc.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(pay, (1, 2)))

        assert sorted(result[0] for result in results) == ["rejected", "succeeded"]
        assert next(value for outcome, value in results if outcome == "rejected") == 409
        with Session(engine) as db:
            successful = db.scalar(
                select(func.count(Payment.id)).where(
                    Payment.order_id == ids["order"], Payment.status == "succeeded"
                )
            )
            assert successful == 1
    finally:
        if ids:
            with Session(engine) as db, db.begin():
                db.execute(
                    delete(OrderEvent).where(OrderEvent.order_id == ids["order"])
                )
                db.execute(delete(Payment).where(Payment.order_id == ids["order"]))
                db.execute(delete(OrderItem).where(OrderItem.order_id == ids["order"]))
                db.execute(delete(Order).where(Order.id == ids["order"]))
                db.execute(
                    delete(ProductVariant).where(ProductVariant.id == ids["variant"])
                )
                db.execute(delete(Product).where(Product.id == ids["product"]))
                db.execute(delete(Category).where(Category.id == ids["category"]))
                db.execute(delete(User).where(User.id == ids["user"]))
                db.execute(delete(Role).where(Role.id == ids["role"]))
        engine.dispose()
