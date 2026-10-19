"""Order workflow integration tests against a migrated PostgreSQL test database."""

import os
import secrets
from collections.abc import Iterator
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.db.models import Category, Product, ProductVariant, Role, User
from app.db.session import create_db_engine, get_session
from app.main import app


@pytest.fixture
def order_setup(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a migrated PostgreSQL test DB")
    if not (make_url(url).database or "").endswith("_test"):
        pytest.fail("TEST_DATABASE_URL database name must end with _test")

    monkeypatch.setenv("JWT_SECRET_KEY", secrets.token_urlsafe(48))
    engine = create_db_engine(url)
    try:
        with engine.connect() as connection:
            outer = connection.begin()
            try:
                password = secrets.token_urlsafe(20)
                suffix = uuid4().hex[:10]
                with (
                    Session(
                        bind=connection, join_transaction_mode="create_savepoint"
                    ) as db,
                    db.begin(),
                ):
                    for role_name in ("Admin", "Manager", "Staff"):
                        role = Role(name=role_name)
                        db.add(role)
                        db.flush()
                        db.add(
                            User(
                                role_id=role.id,
                                email=f"order-{role_name.lower()}-{suffix}@example.com",
                                password_hash=hash_password(password),
                            )
                        )
                    category = Category(name=f"Order Coffee {suffix}")
                    db.add(category)
                    db.flush()
                    product = Product(category_id=category.id, name=f"Latte {suffix}")
                    db.add(product)
                    db.flush()
                    small = ProductVariant(
                        product_id=product.id,
                        sku=f"ORDER-S-{suffix}",
                        name="Small",
                        price=Decimal("4.55"),
                    )
                    topping = ProductVariant(
                        product_id=product.id,
                        sku=f"ORDER-T-{suffix}",
                        name="Topping",
                        price=Decimal("2.35"),
                    )
                    db.add_all([small, topping])
                    db.flush()
                    product_id = product.id
                    variant_ids = [small.id, topping.id]

                def test_session() -> Iterator[Session]:
                    with Session(
                        bind=connection,
                        join_transaction_mode="create_savepoint",
                        expire_on_commit=False,
                    ) as db:
                        yield db

                app.dependency_overrides[get_session] = test_session
                with TestClient(app) as client:
                    tokens = {}
                    for role_name in ("Admin", "Manager", "Staff"):
                        response = client.post(
                            "/auth/login",
                            json={
                                "email": (
                                    f"order-{role_name.lower()}-{suffix}@example.com"
                                ),
                                "password": password,
                            },
                        )
                        assert response.status_code == 200, response.text
                        tokens[role_name] = {
                            "Authorization": f"Bearer {response.json()['access_token']}"
                        }
                    yield {
                        "client": client,
                        "tokens": tokens,
                        "product_id": product_id,
                        "variant_ids": variant_ids,
                    }
            finally:
                app.dependency_overrides.pop(get_session, None)
                outer.rollback()
    finally:
        engine.dispose()


def create_order(
    setup: dict[str, Any], key: str, headers: dict[str, str] | None = None
) -> dict[str, Any]:
    request_headers = dict(headers or setup["tokens"]["Staff"])
    request_headers["Idempotency-Key"] = key
    first, second = setup["variant_ids"]
    response = setup["client"].post(
        "/orders",
        headers=request_headers,
        json={
            "items": [
                {"variant_id": first, "quantity": 2},
                {"variant_id": second, "quantity": 1},
            ],
            "discount_percent": "10.00",
            "discount_reason": "Opening promotion",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_order_totals_snapshots_workflow_and_payment_idempotency(
    order_setup: dict[str, Any],
) -> None:
    client: TestClient = order_setup["client"]
    staff = order_setup["tokens"]["Staff"]
    manager = order_setup["tokens"]["Manager"]
    key = f"order-{uuid4().hex}"
    order = create_order(order_setup, key)

    assert order["status"] == "draft"
    assert order["subtotal_amount"] == "11.45"
    assert order["discount_amount"] == "1.15"
    assert order["total_amount"] == "10.30"
    assert order["items"][0]["product_name"].startswith("Latte")
    assert order["items"][0]["unit_price"] == "4.55"

    variant_id = order_setup["variant_ids"][0]
    changed_price = client.patch(
        f"/products/{order_setup['product_id']}/variants/{variant_id}",
        headers=manager,
        json={"price": "99.00"},
    )
    assert changed_price.status_code == 200, changed_price.text
    saved_snapshot = client.get(f"/orders/{order['id']}", headers=staff)
    assert saved_snapshot.json()["items"][0]["unit_price"] == "4.55"

    retry_headers = dict(staff, **{"Idempotency-Key": key})
    retry = client.post(
        "/orders",
        headers=retry_headers,
        json={
            "items": [
                {"variant_id": order_setup["variant_ids"][1], "quantity": 1},
                {"variant_id": order_setup["variant_ids"][0], "quantity": 2},
            ],
            "discount_percent": "10.00",
            "discount_reason": "Opening promotion",
        },
    )
    assert retry.status_code == 201
    assert retry.json()["id"] == order["id"]

    reused = client.post(
        "/orders",
        headers=retry_headers,
        json={"items": [{"variant_id": order_setup["variant_ids"][0], "quantity": 1}]},
    )
    assert reused.status_code == 409
    assert reused.json()["detail"]["code"] == "idempotency_key_reused"

    place = client.post(
        f"/orders/{order['id']}/transitions",
        headers=staff,
        json={"target_status": "placed"},
    )
    assert place.status_code == 200, place.text
    assert place.json()["status"] == "placed"

    payment_key = f"payment-{uuid4().hex}"
    payment_headers = dict(staff, **{"Idempotency-Key": payment_key})
    payment = client.post(
        f"/orders/{order['id']}/payments",
        headers=payment_headers,
        json={"method": "card_demo", "outcome": "succeeded"},
    )
    assert payment.status_code == 201, payment.text
    assert payment.json()["amount"] == "10.30"
    assert payment.json()["status"] == "succeeded"

    payment_retry = client.post(
        f"/orders/{order['id']}/payments",
        headers=payment_headers,
        json={"method": "card_demo", "outcome": "succeeded"},
    )
    assert payment_retry.status_code == 201
    assert payment_retry.json()["id"] == payment.json()["id"]

    duplicate_payment_headers = dict(
        staff, **{"Idempotency-Key": f"payment-{uuid4().hex}"}
    )
    duplicate_payment = client.post(
        f"/orders/{order['id']}/payments",
        headers=duplicate_payment_headers,
        json={"method": "cash", "outcome": "succeeded"},
    )
    assert duplicate_payment.status_code == 409

    final = client.get(f"/orders/{order['id']}", headers=manager)
    assert final.status_code == 200
    assert final.json()["status"] == "paid"
    assert [event["event_type"] for event in final.json()["events"]] == [
        "created",
        "status_changed",
        "payment_succeeded",
    ]


def test_order_errors_editing_failed_payment_and_cancel_permissions(
    order_setup: dict[str, Any],
) -> None:
    client: TestClient = order_setup["client"]
    staff = order_setup["tokens"]["Staff"]
    manager = order_setup["tokens"]["Manager"]
    order = create_order(order_setup, f"order-{uuid4().hex}")

    updated = client.put(
        f"/orders/{order['id']}",
        headers=staff,
        json={
            "items": [{"variant_id": order_setup["variant_ids"][0], "quantity": 3}],
            "discount_percent": "0",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["subtotal_amount"] == "13.65"

    denied_cancel = client.post(
        f"/orders/{order['id']}/transitions",
        headers=staff,
        json={"target_status": "cancelled", "reason": "Customer changed mind"},
    )
    assert denied_cancel.status_code == 403

    placed = client.post(
        f"/orders/{order['id']}/transitions",
        headers=staff,
        json={"target_status": "placed"},
    )
    assert placed.status_code == 200
    cannot_edit = client.put(
        f"/orders/{order['id']}",
        headers=staff,
        json={"items": [{"variant_id": order_setup["variant_ids"][0], "quantity": 1}]},
    )
    assert cannot_edit.status_code == 409

    failed_headers = dict(staff, **{"Idempotency-Key": f"payment-{uuid4().hex}"})
    failed = client.post(
        f"/orders/{order['id']}/payments",
        headers=failed_headers,
        json={"method": "card_demo", "outcome": "failed"},
    )
    assert failed.status_code == 201
    assert failed.json()["status"] == "failed"
    assert (
        client.get(f"/orders/{order['id']}", headers=staff).json()["status"] == "placed"
    )

    cancelled = client.post(
        f"/orders/{order['id']}/transitions",
        headers=manager,
        json={"target_status": "cancelled", "reason": "Customer changed mind"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    invalid = client.post(
        f"/orders/{order['id']}/transitions",
        headers=manager,
        json={"target_status": "placed"},
    )
    assert invalid.status_code == 409
