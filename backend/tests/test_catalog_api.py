"""Catalog API integration tests against a migrated PostgreSQL test database."""

import os
import secrets
from collections.abc import Iterator
from datetime import date
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.db.models import Role, User
from app.db.session import create_db_engine, get_session
from app.main import app


@pytest.fixture
def catalog_setup(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
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
                                email=f"catalog-{role_name.lower()}@example.com",
                                password_hash=hash_password(password),
                            )
                        )

                def test_session() -> Iterator[Session]:
                    with Session(
                        bind=connection,
                        join_transaction_mode="create_savepoint",
                        expire_on_commit=False,
                    ) as db:
                        yield db

                app.dependency_overrides[get_session] = test_session
                with TestClient(app) as client:
                    yield {"client": client, "password": password}
            finally:
                app.dependency_overrides.pop(get_session, None)
                outer.rollback()
    finally:
        engine.dispose()


def auth_headers(client: TestClient, role: str, password: str) -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={
            "email": f"catalog-{role.lower()}@example.com",
            "password": password,
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_catalog_crud_filtering_and_soft_delete(catalog_setup: dict[str, Any]) -> None:
    client: TestClient = catalog_setup["client"]
    headers = auth_headers(client, "Manager", catalog_setup["password"])

    category_response = client.post(
        "/categories", headers=headers, json={"name": "  Coffee  "}
    )
    assert category_response.status_code == 201, category_response.text
    category = category_response.json()
    category_update = client.patch(
        f"/categories/{category['id']}",
        headers=headers,
        json={"name": "Coffee drinks"},
    )
    assert category_update.status_code == 200
    assert category_update.json()["name"] == "Coffee drinks"

    product_response = client.post(
        "/products",
        headers=headers,
        json={"category_id": category["id"], "name": "Latte"},
    )
    assert product_response.status_code == 201, product_response.text
    product = product_response.json()

    manual_sku_create = client.post(
        f"/products/{product['id']}/variants",
        headers=headers,
        json={"sku": "MANUAL-SKU", "name": "Manual", "price": "1000.00"},
    )
    assert manual_sku_create.status_code == 422

    product_sku_update = client.patch(
        f"/products/{product['id']}",
        headers=headers,
        json={"sku": "PRODUCT-SKU"},
    )
    assert product_sku_update.status_code == 422

    variants = []
    for name, price in (
        ("Size S", "35000.00"),
        ("Size M", "45000.00"),
        ("Size L", "55000.00"),
    ):
        response = client.post(
            f"/products/{product['id']}/variants",
            headers=headers,
            json={"name": name, "price": price},
        )
        assert response.status_code == 201, response.text
        assert response.json()["sku"].startswith("VAR-")
        assert response.json()["price"] == price
        variants.append(response.json())

    product_update = client.patch(
        f"/products/{product['id']}", headers=headers, json={"name": "Caffè Latte"}
    )
    assert product_update.status_code == 200
    assert product_update.json()["name"] == "Caffè Latte"
    medium = variants[1]
    medium_sku = medium["sku"]
    variant_update = client.patch(
        f"/products/{product['id']}/variants/{medium['id']}",
        headers=headers,
        json={"price": "47000.00"},
    )
    assert variant_update.status_code == 200
    assert variant_update.json()["price"] == "47000.00"
    assert variant_update.json()["sku"] == medium_sku

    rejected_sku_update = client.patch(
        f"/products/{product['id']}/variants/{medium['id']}",
        headers=headers,
        json={"sku": "MANUAL-SKU"},
    )
    assert rejected_sku_update.status_code == 422

    listing = client.get(
        "/products",
        headers=headers,
        params={
            "search": medium_sku,
            "category_id": category["id"],
            "min_price": "40000.00",
            "max_price": "50000.00",
            "sort_by": "name",
            "page": 1,
            "page_size": 1,
        },
    )
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["name"] == "Caffè Latte"

    assert (
        client.delete(
            f"/products/{product['id']}/variants/{medium['id']}", headers=headers
        ).status_code
        == 204
    )

    assert (
        client.delete(f"/products/{product['id']}", headers=headers).status_code == 204
    )
    saved = client.get(f"/products/{product['id']}", headers=headers)
    assert saved.status_code == 200
    assert saved.json()["is_active"] is False
    assert len(saved.json()["variants"]) == 3

    category_delete = client.delete(f"/categories/{category['id']}", headers=headers)
    assert category_delete.status_code == 409
    assert category_delete.json()["detail"]["code"] == "category_in_use"

    empty = client.post("/categories", headers=headers, json={"name": "Empty"}).json()
    assert (
        client.delete(f"/categories/{empty['id']}", headers=headers).status_code == 204
    )


def test_catalog_validation_conflicts_and_rbac(catalog_setup: dict[str, Any]) -> None:
    client: TestClient = catalog_setup["client"]
    manager = auth_headers(client, "Manager", catalog_setup["password"])
    staff = auth_headers(client, "Staff", catalog_setup["password"])

    created = client.post("/categories", headers=manager, json={"name": "Tea"})
    assert created.status_code == 201
    duplicate = client.post("/categories", headers=manager, json={"name": "tea"})
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "category_name_exists"

    injection = client.get(
        "/categories",
        headers=staff,
        params={"search": "' OR 1=1 --"},
    )
    assert injection.status_code == 200
    assert injection.json()["total"] == 0

    assert client.get("/categories", headers=staff).status_code == 200
    assert (
        client.post("/categories", headers=staff, json={"name": "Juice"}).status_code
        == 403
    )
    assert client.get("/products").status_code == 401

    bad_price = client.post(
        "/products/1/variants",
        headers=manager,
        json={"name": "Bad", "price": "1.001"},
    )
    assert bad_price.status_code == 422
    bad_range = client.get(
        "/products",
        headers=staff,
        params={"min_price": "10.00", "max_price": "5.00"},
    )
    assert bad_range.status_code == 422
    assert bad_range.json()["detail"]["code"] == "invalid_price_range"


def test_category_reassignment_preserves_products_and_options(
    catalog_setup: dict[str, Any],
) -> None:
    client: TestClient = catalog_setup["client"]
    manager = auth_headers(client, "Manager", catalog_setup["password"])
    staff = auth_headers(client, "Staff", catalog_setup["password"])

    cafe = client.post("/categories", headers=manager, json={"name": "Cafe"}).json()
    tea = client.post("/categories", headers=manager, json={"name": "Trà"}).json()
    other = client.post("/categories", headers=manager, json={"name": "Nước ép"}).json()
    product = client.post(
        "/products",
        headers=manager,
        json={
            "category_id": cafe["id"],
            "name": "Cafe muối",
            "base_price": "32000.00",
        },
    ).json()
    accentless_search = client.get(
        "/products",
        headers=manager,
        params={"search": "CAFE MUOI", "page_size": 1},
    )
    assert accentless_search.status_code == 200
    assert accentless_search.json()["total"] == 1
    assert accentless_search.json()["items"][0]["id"] == product["id"]
    variant = client.post(
        f"/products/{product['id']}/variants",
        headers=manager,
        json={"name": "M", "price": "5000.00"},
    ).json()
    topping = client.post(
        f"/products/{product['id']}/toppings",
        headers=manager,
        json={"name": "Kem mặn", "price": "7000.00"},
    ).json()
    order_headers = dict(manager, **{"Idempotency-Key": f"order-{uuid4().hex}"})
    order_response = client.post(
        "/orders",
        headers=order_headers,
        json={"items": [{"variant_id": variant["id"], "quantity": 1}]},
    )
    assert order_response.status_code == 201, order_response.text
    order = order_response.json()
    placed = client.post(
        f"/orders/{order['id']}/transitions",
        headers=manager,
        json={"target_status": "placed"},
    )
    assert placed.status_code == 200, placed.text
    payment_headers = dict(manager, **{"Idempotency-Key": f"payment-{uuid4().hex}"})
    payment = client.post(
        f"/orders/{order['id']}/payments",
        headers=payment_headers,
        json={"method": "cash", "outcome": "succeeded"},
    )
    assert payment.status_code == 201, payment.text
    order_before = client.get(f"/orders/{order['id']}", headers=manager).json()
    today = date.today().isoformat()
    revenue_before = client.get(
        "/reports/revenue/summary",
        headers=manager,
        params={"date_from": today, "date_to": today},
    ).json()

    direct_delete = client.delete(f"/categories/{cafe['id']}", headers=manager)
    assert direct_delete.status_code == 409

    options = client.get(f"/categories/{cafe['id']}/deletion-options", headers=manager)
    assert options.status_code == 200, options.text
    assert options.json()["linked_product_count"] == 1
    assert options.json()["preferred_replacement_category_id"] == tea["id"]
    assert {item["id"] for item in options.json()["replacement_categories"]} == {
        tea["id"],
        other["id"],
    }

    assert (
        client.post(
            f"/categories/{cafe['id']}/reassign-and-delete",
            headers=staff,
            json={"replacement_category_id": tea["id"]},
        ).status_code
        == 403
    )
    same_category = client.post(
        f"/categories/{cafe['id']}/reassign-and-delete",
        headers=manager,
        json={"replacement_category_id": cafe["id"]},
    )
    assert same_category.status_code == 422
    missing_category = client.post(
        f"/categories/{cafe['id']}/reassign-and-delete",
        headers=manager,
        json={"replacement_category_id": 999999999},
    )
    assert missing_category.status_code == 404

    reassigned = client.post(
        f"/categories/{cafe['id']}/reassign-and-delete",
        headers=manager,
        json={"replacement_category_id": other["id"]},
    )
    assert reassigned.status_code == 200, reassigned.text
    assert reassigned.json() == {
        "deleted_category_id": cafe["id"],
        "replacement_category_id": other["id"],
        "reassigned_product_count": 1,
    }
    assert client.get(f"/categories/{cafe['id']}", headers=manager).status_code == 404
    saved_product = client.get(f"/products/{product['id']}", headers=manager).json()
    assert saved_product["id"] == product["id"]
    assert saved_product["category_id"] == other["id"]
    assert saved_product["base_price"] == "32000.00"
    assert {item["id"] for item in saved_product["variants"]} == {variant["id"]}
    assert {item["id"] for item in saved_product["toppings"]} == {topping["id"]}
    order_after = client.get(f"/orders/{order['id']}", headers=manager).json()
    revenue_after = client.get(
        "/reports/revenue/summary",
        headers=manager,
        params={"date_from": today, "date_to": today},
    ).json()
    assert order_after == order_before
    assert order_after["payments"] == [payment.json()]
    assert revenue_after == revenue_before


def test_category_reassignment_conflict_rolls_back(
    catalog_setup: dict[str, Any],
) -> None:
    client: TestClient = catalog_setup["client"]
    manager = auth_headers(client, "Manager", catalog_setup["password"])
    source = client.post("/categories", headers=manager, json={"name": "Source"}).json()
    replacement = client.post(
        "/categories", headers=manager, json={"name": "Replacement"}
    ).json()
    source_product = client.post(
        "/products",
        headers=manager,
        json={"category_id": source["id"], "name": "Duplicate"},
    ).json()
    client.post(
        "/products",
        headers=manager,
        json={"category_id": replacement["id"], "name": "Duplicate"},
    )

    response = client.post(
        f"/categories/{source['id']}/reassign-and-delete",
        headers=manager,
        json={"replacement_category_id": replacement["id"]},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "category_reassignment_conflict"
    assert client.get(f"/categories/{source['id']}", headers=manager).status_code == 200
    saved_product = client.get(
        f"/products/{source_product['id']}", headers=manager
    ).json()
    assert saved_product["category_id"] == source["id"]


def test_deleting_tea_does_not_preselect_itself(
    catalog_setup: dict[str, Any],
) -> None:
    client: TestClient = catalog_setup["client"]
    manager = auth_headers(client, "Manager", catalog_setup["password"])
    tea = client.post("/categories", headers=manager, json={"name": "Trà"}).json()
    options = client.get(f"/categories/{tea['id']}/deletion-options", headers=manager)
    assert options.status_code == 200
    assert options.json()["preferred_replacement_category_id"] is None
    assert all(
        item["id"] != tea["id"] for item in options.json()["replacement_categories"]
    )


def test_missing_tea_requires_manual_valid_replacement(
    catalog_setup: dict[str, Any],
) -> None:
    client: TestClient = catalog_setup["client"]
    manager = auth_headers(client, "Manager", catalog_setup["password"])
    source = client.post(
        "/categories", headers=manager, json={"name": "Đồ uống nóng"}
    ).json()
    product = client.post(
        "/products",
        headers=manager,
        json={"category_id": source["id"], "name": "Ca cao"},
    ).json()

    no_replacement = client.get(
        f"/categories/{source['id']}/deletion-options", headers=manager
    ).json()
    assert no_replacement["replacement_categories"] == []
    assert no_replacement["preferred_replacement_category_id"] is None
    assert (
        client.delete(f"/categories/{source['id']}", headers=manager).status_code == 409
    )

    other = client.post(
        "/categories", headers=manager, json={"name": "Trà xanh"}
    ).json()
    manual_options = client.get(
        f"/categories/{source['id']}/deletion-options", headers=manager
    ).json()
    assert manual_options["preferred_replacement_category_id"] is None
    assert manual_options["replacement_categories"] == [other]

    response = client.post(
        f"/categories/{source['id']}/reassign-and-delete",
        headers=manager,
        json={"replacement_category_id": other["id"]},
    )
    assert response.status_code == 200, response.text
    moved_product = client.get(f"/products/{product['id']}", headers=manager).json()
    assert moved_product["category_id"] == other["id"]
