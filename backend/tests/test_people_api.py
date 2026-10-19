"""Customer, employee, and loyalty integration tests for PostgreSQL."""

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
def people_setup(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
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
                suffix = uuid4().hex[:10]
                password = secrets.token_urlsafe(20)
                with (
                    Session(
                        bind=connection, join_transaction_mode="create_savepoint"
                    ) as db,
                    db.begin(),
                ):
                    users = {}
                    emails = {}
                    for role_name in ("Admin", "Manager", "Staff"):
                        role = Role(name=role_name)
                        db.add(role)
                        db.flush()
                        email = f"people-{role_name.lower()}-{suffix}@example.com"
                        user = User(
                            role_id=role.id,
                            email=email,
                            password_hash=hash_password(password),
                        )
                        db.add(user)
                        db.flush()
                        users[role_name] = user.id
                        emails[role_name] = email
                    category = Category(name=f"People Coffee {suffix}")
                    db.add(category)
                    db.flush()
                    product = Product(category_id=category.id, name=f"Mocha {suffix}")
                    db.add(product)
                    db.flush()
                    variant = ProductVariant(
                        product_id=product.id,
                        sku=f"PEOPLE-MOCHA-{suffix}",
                        name="Regular",
                        price=Decimal("25.00"),
                    )
                    db.add(variant)
                    db.flush()
                    variant_id = variant.id

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
                    for role_name, email in emails.items():
                        response = client.post(
                            "/auth/login", json={"email": email, "password": password}
                        )
                        assert response.status_code == 200, response.text
                        tokens[role_name] = {
                            "Authorization": f"Bearer {response.json()['access_token']}"
                        }
                    yield {
                        "client": client,
                        "tokens": tokens,
                        "users": users,
                        "emails": emails,
                        "password": password,
                        "variant_id": variant_id,
                    }
            finally:
                app.dependency_overrides.pop(get_session, None)
                outer.rollback()
    finally:
        engine.dispose()


def with_key(headers: dict[str, str], prefix: str) -> dict[str, str]:
    return dict(headers, **{"Idempotency-Key": f"{prefix}-{uuid4().hex}"})


def test_customer_history_loyalty_award_adjustment_and_refund(
    people_setup: dict[str, Any],
) -> None:
    client: TestClient = people_setup["client"]
    admin = people_setup["tokens"]["Admin"]
    manager = people_setup["tokens"]["Manager"]
    staff = people_setup["tokens"]["Staff"]

    employee = client.post(
        "/employees",
        headers=admin,
        json={
            "employee_code": "staff-pos-01",
            "full_name": "POS Staff",
            "user_id": people_setup["users"]["Staff"],
        },
    )
    assert employee.status_code == 201, employee.text
    employee_id = employee.json()["id"]
    assert "password_hash" not in employee.json()
    assert "email" not in employee.json()

    customer = client.post(
        "/customers",
        headers=staff,
        json={
            "full_name": "Nguyễn An",
            "phone": "+84 912 345 678",
            "email": "AN@example.com",
        },
    )
    assert customer.status_code == 201, customer.text
    customer_id = customer.json()["id"]
    assert customer.json()["loyalty_points"] == 0

    listing = client.get(
        "/customers", headers=staff, params={"search": "nguyễn", "page_size": 1}
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    order = client.post(
        "/orders",
        headers=with_key(staff, "people-order"),
        json={
            "customer_id": customer_id,
            "items": [{"variant_id": people_setup["variant_id"], "quantity": 1}],
        },
    )
    assert order.status_code == 201, order.text
    assert order.json()["employee_id"] == employee_id
    order_id = order.json()["id"]
    assert (
        client.post(
            f"/orders/{order_id}/transitions",
            headers=staff,
            json={"target_status": "placed"},
        ).status_code
        == 200
    )
    payment_headers = with_key(staff, "people-payment")
    payment = client.post(
        f"/orders/{order_id}/payments",
        headers=payment_headers,
        json={"method": "cash", "outcome": "succeeded"},
    )
    assert payment.status_code == 201, payment.text
    payment_retry = client.post(
        f"/orders/{order_id}/payments",
        headers=payment_headers,
        json={"method": "cash", "outcome": "succeeded"},
    )
    assert payment_retry.status_code == 201
    assert payment_retry.json()["id"] == payment.json()["id"]

    after_payment = client.get(f"/customers/{customer_id}", headers=staff)
    assert after_payment.json()["loyalty_points"] == 2
    history = client.get(f"/customers/{customer_id}/orders", headers=staff)
    assert history.json()["items"][0]["id"] == order_id
    assert history.json()["items"][0]["status"] == "paid"
    assert "items" not in history.json()["items"][0]

    forbidden_status = client.patch(
        f"/customers/{customer_id}", headers=staff, json={"is_active": False}
    )
    assert forbidden_status.status_code == 403

    adjustment_headers = with_key(manager, "loyalty-adjust")
    adjustment = client.post(
        f"/customers/{customer_id}/loyalty-adjustments",
        headers=adjustment_headers,
        json={"points_delta": 3, "reason": "Service recovery"},
    )
    assert adjustment.status_code == 201, adjustment.text
    adjustment_retry = client.post(
        f"/customers/{customer_id}/loyalty-adjustments",
        headers=adjustment_headers,
        json={"points_delta": 3, "reason": "Service recovery"},
    )
    assert adjustment_retry.json()["id"] == adjustment.json()["id"]
    assert (
        client.get(f"/customers/{customer_id}", headers=staff).json()["loyalty_points"]
        == 5
    )

    negative = client.post(
        f"/customers/{customer_id}/loyalty-adjustments",
        headers=with_key(manager, "loyalty-negative"),
        json={"points_delta": -6, "reason": "Invalid overdraw"},
    )
    assert negative.status_code == 409

    refund_headers = with_key(manager, "loyalty-refund")
    refund = client.post(
        f"/orders/{order_id}/loyalty-refund",
        headers=refund_headers,
        json={"reason": "Payment refunded outside POS"},
    )
    assert refund.status_code == 201, refund.text
    refund_retry = client.post(
        f"/orders/{order_id}/loyalty-refund",
        headers=refund_headers,
        json={"reason": "Payment refunded outside POS"},
    )
    assert refund_retry.json()["id"] == refund.json()["id"]
    assert (
        client.get(f"/customers/{customer_id}", headers=staff).json()["loyalty_points"]
        == 3
    )

    ledger = client.get(f"/customers/{customer_id}/loyalty", headers=manager)
    assert [item["transaction_type"] for item in reversed(ledger.json()["items"])] == [
        "earn",
        "adjustment",
        "refund",
    ]

    assert client.delete(f"/customers/{customer_id}", headers=staff).status_code == 403
    assert (
        client.delete(f"/customers/{customer_id}", headers=manager).status_code == 204
    )
    assert (
        client.get(f"/customers/{customer_id}/orders", headers=manager).json()["total"]
        == 1
    )
    inactive_order = client.post(
        "/orders",
        headers=with_key(staff, "inactive-customer"),
        json={
            "customer_id": customer_id,
            "items": [{"variant_id": people_setup["variant_id"], "quantity": 1}],
        },
    )
    assert inactive_order.status_code == 404


def test_employee_permissions_and_deactivation_revoke_access(
    people_setup: dict[str, Any],
) -> None:
    client: TestClient = people_setup["client"]
    admin = people_setup["tokens"]["Admin"]
    manager = people_setup["tokens"]["Manager"]
    staff = people_setup["tokens"]["Staff"]

    assert (
        client.post(
            "/employees",
            headers=staff,
            json={"employee_code": "NOPE", "full_name": "Denied"},
        ).status_code
        == 403
    )
    forbidden_link = client.post(
        "/employees",
        headers=manager,
        json={
            "employee_code": "MGR-LINK",
            "full_name": "Manager Account",
            "user_id": people_setup["users"]["Manager"],
        },
    )
    assert forbidden_link.status_code == 403

    created = client.post(
        "/employees",
        headers=admin,
        json={
            "employee_code": "STAFF-02",
            "full_name": "Second Staff",
            "user_id": people_setup["users"]["Staff"],
        },
    )
    assert created.status_code == 201, created.text
    employee_id = created.json()["id"]
    found = client.get(
        "/employees", headers=manager, params={"search": "staff-02", "page_size": 1}
    )
    assert found.status_code == 200
    assert found.json()["total"] == 1

    disabled = client.delete(f"/employees/{employee_id}", headers=manager)
    assert disabled.status_code == 204, disabled.text
    assert client.get("/auth/me", headers=staff).status_code == 401
    login = client.post(
        "/auth/login",
        json={
            "email": people_setup["emails"]["Staff"],
            "password": people_setup["password"],
        },
    )
    assert login.status_code == 403
    saved = client.get(f"/employees/{employee_id}", headers=manager)
    assert saved.json()["is_active"] is False
