"""Catalog API integration tests against a migrated PostgreSQL test database."""

import os
import secrets
from collections.abc import Iterator
from typing import Any

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

    variants = []
    for sku, name, price in (
        ("LATTE-S", "Size S", "35000.00"),
        ("LATTE-M", "Size M", "45000.00"),
        ("LATTE-L", "Size L", "55000.00"),
    ):
        response = client.post(
            f"/products/{product['id']}/variants",
            headers=headers,
            json={"sku": sku, "name": name, "price": price},
        )
        assert response.status_code == 201, response.text
        assert response.json()["price"] == price
        variants.append(response.json())

    product_update = client.patch(
        f"/products/{product['id']}", headers=headers, json={"name": "Caffè Latte"}
    )
    assert product_update.status_code == 200
    assert product_update.json()["name"] == "Caffè Latte"
    medium = variants[1]
    variant_update = client.patch(
        f"/products/{product['id']}/variants/{medium['id']}",
        headers=headers,
        json={"price": "47000.00"},
    )
    assert variant_update.status_code == 200
    assert variant_update.json()["price"] == "47000.00"

    listing = client.get(
        "/products",
        headers=headers,
        params={
            "search": "LATTE-M",
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

    assert client.get("/categories", headers=staff).status_code == 200
    assert (
        client.post("/categories", headers=staff, json={"name": "Juice"}).status_code
        == 403
    )
    assert client.get("/products").status_code == 401

    bad_price = client.post(
        "/products/1/variants",
        headers=manager,
        json={"sku": "BAD", "name": "Bad", "price": "1.001"},
    )
    assert bad_price.status_code == 422
    bad_range = client.get(
        "/products",
        headers=staff,
        params={"min_price": "10.00", "max_price": "5.00"},
    )
    assert bad_range.status_code == 422
    assert bad_range.json()["detail"]["code"] == "invalid_price_range"
