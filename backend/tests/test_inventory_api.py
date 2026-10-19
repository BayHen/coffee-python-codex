"""Inventory API and order consumption integration tests for PostgreSQL."""

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
def inventory_setup(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
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
                    emails = {}
                    for role_name in ("Admin", "Manager", "Staff"):
                        role = Role(name=role_name)
                        db.add(role)
                        db.flush()
                        email = f"inventory-{role_name.lower()}-{suffix}@example.com"
                        emails[role_name] = email
                        db.add(
                            User(
                                role_id=role.id,
                                email=email,
                                password_hash=hash_password(password),
                            )
                        )
                    category = Category(name=f"Inventory Coffee {suffix}")
                    db.add(category)
                    db.flush()
                    product = Product(category_id=category.id, name=f"Latte {suffix}")
                    db.add(product)
                    db.flush()
                    variant = ProductVariant(
                        product_id=product.id,
                        sku=f"INV-LATTE-{suffix}",
                        name="Regular",
                        price=Decimal("5.00"),
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
                            "/auth/login",
                            json={"email": email, "password": password},
                        )
                        assert response.status_code == 200, response.text
                        tokens[role_name] = {
                            "Authorization": f"Bearer {response.json()['access_token']}"
                        }
                    yield {
                        "client": client,
                        "tokens": tokens,
                        "variant_id": variant_id,
                    }
            finally:
                app.dependency_overrides.pop(get_session, None)
                outer.rollback()
    finally:
        engine.dispose()


def idempotent(headers: dict[str, str], prefix: str) -> dict[str, str]:
    return dict(headers, **{"Idempotency-Key": f"{prefix}-{uuid4().hex}"})


def test_inventory_crud_recipe_purchase_order_consumption_and_return(
    inventory_setup: dict[str, Any],
) -> None:
    client: TestClient = inventory_setup["client"]
    manager = inventory_setup["tokens"]["Manager"]
    staff = inventory_setup["tokens"]["Staff"]
    variant_id = inventory_setup["variant_id"]

    created = client.post(
        "/ingredients",
        headers=manager,
        json={
            "sku": "milk-test",
            "name": "Fresh Milk",
            "unit": "ml",
            "low_stock_threshold": "600.000",
        },
    )
    assert created.status_code == 201, created.text
    ingredient = created.json()
    assert ingredient["current_stock"] == "0.000"
    ingredient_id = ingredient["id"]

    recipe = client.put(
        f"/product-variants/{variant_id}/recipes/{ingredient_id}",
        headers=manager,
        json={"quantity_required": "250.000"},
    )
    assert recipe.status_code == 200, recipe.text

    purchase_headers = idempotent(manager, "purchase")
    purchase = client.post(
        "/inventory/transactions",
        headers=purchase_headers,
        json={
            "ingredient_id": ingredient_id,
            "transaction_type": "purchase",
            "quantity_delta": "1000.000",
            "reason": "Opening stock",
        },
    )
    assert purchase.status_code == 201, purchase.text
    retry = client.post(
        "/inventory/transactions",
        headers=purchase_headers,
        json={
            "ingredient_id": ingredient_id,
            "transaction_type": "purchase",
            "quantity_delta": "1000.0",
            "reason": "Opening stock",
        },
    )
    assert retry.status_code == 201
    assert retry.json()["id"] == purchase.json()["id"]

    order_headers = idempotent(staff, "order")
    order = client.post(
        "/orders",
        headers=order_headers,
        json={"items": [{"variant_id": variant_id, "quantity": 2}]},
    )
    assert order.status_code == 201, order.text
    order_id = order.json()["id"]
    assert (
        client.get(f"/ingredients/{ingredient_id}", headers=staff).json()[
            "current_stock"
        ]
        == "1000.000"
    )

    placed = client.post(
        f"/orders/{order_id}/transitions",
        headers=staff,
        json={"target_status": "placed"},
    )
    assert placed.status_code == 200, placed.text
    stock_after_sale = client.get(f"/ingredients/{ingredient_id}", headers=staff)
    assert stock_after_sale.json()["current_stock"] == "500.000"
    assert stock_after_sale.json()["is_low_stock"] is True

    duplicate_place = client.post(
        f"/orders/{order_id}/transitions",
        headers=staff,
        json={"target_status": "placed"},
    )
    assert duplicate_place.status_code == 409
    assert (
        client.get(f"/ingredients/{ingredient_id}", headers=staff).json()[
            "current_stock"
        ]
        == "500.000"
    )

    low_stock = client.get("/ingredients/low-stock", headers=staff)
    assert ingredient_id in {item["id"] for item in low_stock.json()["items"]}

    cancelled = client.post(
        f"/orders/{order_id}/transitions",
        headers=manager,
        json={"target_status": "cancelled", "reason": "Customer cancelled"},
    )
    assert cancelled.status_code == 200, cancelled.text
    restored = client.get(f"/ingredients/{ingredient_id}", headers=staff)
    assert restored.json()["current_stock"] == "1000.000"

    ledger = client.get(
        "/inventory/transactions",
        headers=manager,
        params={"ingredient_id": ingredient_id},
    )
    assert [item["transaction_type"] for item in reversed(ledger.json()["items"])] == [
        "purchase",
        "sale",
        "return",
    ]
    assert (
        client.delete(
            f"/product-variants/{variant_id}/recipes/{ingredient_id}",
            headers=manager,
        ).status_code
        == 204
    )
    assert (
        client.get(f"/product-variants/{variant_id}/recipes", headers=staff).json()
        == []
    )


def test_inventory_validation_permissions_and_negative_stock(
    inventory_setup: dict[str, Any],
) -> None:
    client: TestClient = inventory_setup["client"]
    manager = inventory_setup["tokens"]["Manager"]
    staff = inventory_setup["tokens"]["Staff"]
    ingredient = client.post(
        "/ingredients",
        headers=manager,
        json={"sku": "BEANS-TEST", "name": "Beans", "unit": "g"},
    ).json()

    denied = client.post(
        "/inventory/transactions",
        headers=idempotent(staff, "denied"),
        json={
            "ingredient_id": ingredient["id"],
            "transaction_type": "adjustment",
            "quantity_delta": "10.000",
            "reason": "Count correction",
        },
    )
    assert denied.status_code == 403

    negative = client.post(
        "/inventory/transactions",
        headers=idempotent(manager, "waste"),
        json={
            "ingredient_id": ingredient["id"],
            "transaction_type": "waste",
            "quantity_delta": "-1.000",
            "reason": "Damaged beans",
        },
    )
    assert negative.status_code == 409
    assert negative.json()["detail"]["code"] == "insufficient_stock"

    invalid_unit = client.patch(
        f"/ingredients/{ingredient['id']}", headers=manager, json={"unit": "kg"}
    )
    assert invalid_unit.status_code == 422

    updated = client.patch(
        f"/ingredients/{ingredient['id']}",
        headers=manager,
        json={"name": "Arabica Beans", "low_stock_threshold": "5.000"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Arabica Beans"
    assert (
        client.delete(f"/ingredients/{ingredient['id']}", headers=manager).status_code
        == 204
    )
    assert (
        client.get(f"/ingredients/{ingredient['id']}", headers=staff).json()[
            "is_active"
        ]
        is False
    )


def test_placing_order_with_insufficient_stock_rolls_back(
    inventory_setup: dict[str, Any],
) -> None:
    client: TestClient = inventory_setup["client"]
    manager = inventory_setup["tokens"]["Manager"]
    staff = inventory_setup["tokens"]["Staff"]
    variant_id = inventory_setup["variant_id"]
    ingredient = client.post(
        "/ingredients",
        headers=manager,
        json={"sku": "SYRUP-TEST", "name": "Syrup", "unit": "ml"},
    ).json()
    recipe = client.put(
        f"/product-variants/{variant_id}/recipes/{ingredient['id']}",
        headers=manager,
        json={"quantity_required": "10.000"},
    )
    assert recipe.status_code == 200
    order = client.post(
        "/orders",
        headers=idempotent(staff, "insufficient-order"),
        json={"items": [{"variant_id": variant_id, "quantity": 1}]},
    ).json()

    placed = client.post(
        f"/orders/{order['id']}/transitions",
        headers=staff,
        json={"target_status": "placed"},
    )
    assert placed.status_code == 409
    assert placed.json()["detail"]["code"] == "insufficient_stock"
    saved = client.get(f"/orders/{order['id']}", headers=staff)
    assert saved.json()["status"] == "draft"
    ledger = client.get(
        "/inventory/transactions",
        headers=manager,
        params={"ingredient_id": ingredient["id"]},
    )
    assert ledger.json()["total"] == 0
