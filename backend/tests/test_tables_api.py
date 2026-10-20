"""Dine-in table workflow integration test against migrated PostgreSQL."""

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
def table_setup(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
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
                    for role_name in ("Manager", "Staff"):
                        role = Role(name=f"{role_name}-{suffix}")
                        db.add(role)
                        db.flush()
                        # Login/RBAC requires canonical role names.
                        canonical = (
                            db.query(Role).filter(Role.name == role_name).one_or_none()
                        )
                        if canonical is None:
                            role.name = role_name
                            canonical = role
                        user = User(
                            role_id=canonical.id,
                            email=f"table-{role_name.lower()}-{suffix}@example.com",
                            password_hash=hash_password(password),
                        )
                        db.add(user)
                        users[role_name] = user.email
                    category = Category(name=f"Table Coffee {suffix}")
                    db.add(category)
                    db.flush()
                    product = Product(category_id=category.id, name=f"Latte {suffix}")
                    db.add(product)
                    db.flush()
                    variant = ProductVariant(
                        product_id=product.id,
                        sku=f"TABLE-{suffix}",
                        name="Regular",
                        price=Decimal("35000.00"),
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
                    for role_name, email in users.items():
                        response = client.post(
                            "/auth/login", json={"email": email, "password": password}
                        )
                        assert response.status_code == 200, response.text
                        tokens[role_name] = {
                            "Authorization": f"Bearer {response.json()['access_token']}"
                        }
                    yield {"client": client, "tokens": tokens, "variant_id": variant_id}
            finally:
                app.dependency_overrides.pop(get_session, None)
                outer.rollback()
    finally:
        engine.dispose()


def test_initial_additional_bill_checkout_and_rbac(table_setup: dict[str, Any]) -> None:
    client: TestClient = table_setup["client"]
    manager = table_setup["tokens"]["Manager"]
    staff = table_setup["tokens"]["Staff"]

    denied = client.post(
        "/tables", headers=staff, json={"table_number": "05", "name": "Window"}
    )
    assert denied.status_code == 403
    created = client.post(
        "/tables", headers=manager, json={"table_number": "05", "name": "Window"}
    )
    assert created.status_code == 201, created.text
    table_id = created.json()["id"]
    duplicate = client.post(
        "/tables", headers=manager, json={"table_number": "05", "name": "Other"}
    )
    assert duplicate.status_code == 409

    opened = client.post(f"/tables/{table_id}/sessions", headers=staff)
    assert opened.status_code == 201, opened.text
    session = opened.json()
    order = session["orders"][0]
    assert client.post(f"/tables/{table_id}/sessions", headers=staff).status_code == 409
    empty_confirm = client.post(f"/orders/{order['id']}/confirm", headers=staff)
    assert empty_confirm.status_code == 409

    added = client.post(
        f"/orders/{order['id']}/items",
        headers=staff,
        json={"variant_id": table_setup["variant_id"], "quantity": 2},
    )
    assert added.status_code == 201, added.text
    item = added.json()["items"][0]
    assert added.json()["total_amount"] == "70000.00"
    updated = client.patch(
        f"/orders/{order['id']}/items/{item['id']}", headers=staff, json={"quantity": 1}
    )
    assert updated.json()["total_amount"] == "35000.00"
    confirmed = client.post(f"/orders/{order['id']}/confirm", headers=staff)
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"
    assert (
        client.patch(
            f"/orders/{order['id']}/items/{item['id']}",
            headers=staff,
            json={"quantity": 2},
        ).status_code
        == 409
    )

    additional = client.post(
        f"/sessions/{session['id']}/orders",
        headers=staff,
        json={"order_type": "additional"},
    )
    assert additional.status_code == 201
    assert additional.json()["sequence_number"] == 2
    assert (
        client.post(
            f"/sessions/{session['id']}/orders",
            headers=staff,
            json={"order_type": "additional"},
        ).status_code
        == 409
    )
    draft_id = additional.json()["id"]
    client.post(
        f"/orders/{draft_id}/items",
        headers=staff,
        json={"variant_id": table_setup["variant_id"], "quantity": 1},
    )
    bill = client.get(f"/sessions/{session['id']}/bill", headers=staff).json()
    assert bill == {
        "confirmed_subtotal": "35000.00",
        "draft_subtotal": "35000.00",
        "payable_total": "35000.00",
    }
    assert (
        client.post(
            f"/sessions/{session['id']}/checkout",
            headers={**staff, "Idempotency-Key": f"checkout-{uuid4().hex}"},
            json={"method": "cash", "cash_received": "70000.00"},
        ).status_code
        == 409
    )
    client.post(f"/orders/{draft_id}/confirm", headers=staff)
    key = f"checkout-{uuid4().hex}"
    payment = client.post(
        f"/sessions/{session['id']}/checkout",
        headers={**staff, "Idempotency-Key": key},
        json={"method": "cash", "cash_received": "100000.00"},
    )
    assert payment.status_code == 201, payment.text
    assert payment.json()["amount"] == "70000.00"
    assert payment.json()["change_amount"] == "30000.00"
    assert payment.json()["receipt_number"].startswith("RCP-")
    retry = client.post(
        f"/sessions/{session['id']}/checkout",
        headers={**staff, "Idempotency-Key": key},
        json={"method": "cash", "cash_received": "100000.00"},
    )
    assert retry.status_code == 201
    assert retry.json()["id"] == payment.json()["id"]
    table_rows = client.get("/tables", headers=staff).json()
    assert (
        next(row for row in table_rows if row["id"] == table_id)["status"]
        == "available"
    )
    history = client.get(f"/sessions/{session['id']}", headers=staff).json()
    assert history["status"] == "paid"
    assert len(history["orders"]) == 2
    assert (
        client.post(
            f"/sessions/{session['id']}/orders",
            headers=staff,
            json={"order_type": "additional"},
        ).status_code
        == 409
    )
