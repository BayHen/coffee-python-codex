"""Revenue report rules and PostgreSQL aggregation integration tests."""

import os
import secrets
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.db.models import (
    Category,
    Order,
    OrderItem,
    Payment,
    Product,
    ProductVariant,
    Role,
    User,
)
from app.db.session import create_db_engine, get_session
from app.main import app
from app.reporting.service import resolve_period


def test_report_period_uses_inclusive_local_dates_and_utc_boundaries() -> None:
    period = resolve_period(
        date(2026, 10, 19),
        date(2026, 10, 19),
        "Asia/Ho_Chi_Minh",
    )
    assert period.start_utc == datetime(2026, 10, 18, 17, tzinfo=UTC)
    assert period.end_utc == datetime(2026, 10, 19, 17, tzinfo=UTC)


@pytest.fixture
def reporting_setup(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
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
                    emails: dict[str, str] = {}
                    for role_name in ("Admin", "Manager", "Staff"):
                        role = Role(name=role_name)
                        db.add(role)
                        db.flush()
                        email = f"report-{role_name.lower()}-{suffix}@example.com"
                        db.add(
                            User(
                                role_id=role.id,
                                email=email,
                                password_hash=hash_password(password),
                            )
                        )
                        emails[role_name] = email

                    category = Category(name=f"Report drinks {suffix}")
                    db.add(category)
                    db.flush()
                    product = Product(category_id=category.id, name="Coffee")
                    db.add(product)
                    db.flush()
                    latte = ProductVariant(
                        product_id=product.id,
                        sku=f"LATTE-M-{suffix}",
                        name="M",
                        price=Decimal("30.00"),
                    )
                    tea = ProductVariant(
                        product_id=product.id,
                        sku=f"TEA-S-{suffix}",
                        name="S",
                        price=Decimal("40.00"),
                    )
                    db.add_all([latte, tea])
                    db.flush()

                    def seed_order(
                        number: int,
                        *,
                        status: str,
                        payment_status: str | None,
                        amount: str,
                        created_at: datetime,
                        items: list[tuple[ProductVariant, int, str]],
                    ) -> None:
                        total = Decimal(amount)
                        order = Order(
                            idempotency_key=f"report-order-{suffix}-{number}",
                            request_fingerprint=f"{number:064x}",
                            status=status,
                            subtotal_amount=total,
                            discount_percent=Decimal("0.00"),
                            discount_amount=Decimal("0.00"),
                            total_amount=total,
                            created_at=created_at,
                        )
                        db.add(order)
                        db.flush()
                        for variant, quantity, line_total in items:
                            line = Decimal(line_total)
                            db.add(
                                OrderItem(
                                    order_id=order.id,
                                    variant_id=variant.id,
                                    product_name=(
                                        "Latte" if variant.id == latte.id else "Tea"
                                    ),
                                    variant_name=variant.name,
                                    sku=variant.sku,
                                    quantity=quantity,
                                    unit_price=line / quantity,
                                    line_total=line,
                                )
                            )
                        if payment_status:
                            db.add(
                                Payment(
                                    order_id=order.id,
                                    idempotency_key=f"report-payment-{suffix}-{number}",
                                    request_fingerprint=f"{number + 100:064x}",
                                    provider_reference=f"SIM-{suffix}-{number}",
                                    method="cash",
                                    status=payment_status,
                                    amount=total,
                                    created_at=created_at,
                                )
                            )

                    # UTC instants map to 01 and 02 October in Asia/Ho_Chi_Minh.
                    seed_order(
                        1,
                        status="paid",
                        payment_status="succeeded",
                        amount="100.00",
                        created_at=datetime(2026, 9, 30, 18, tzinfo=UTC),
                        items=[(latte, 2, "60.00"), (tea, 1, "40.00")],
                    )
                    seed_order(
                        2,
                        status="paid",
                        payment_status="succeeded",
                        amount="45.00",
                        created_at=datetime(2026, 10, 1, 18, tzinfo=UTC),
                        items=[(latte, 1, "45.00")],
                    )
                    seed_order(
                        3,
                        status="placed",
                        payment_status="failed",
                        amount="500.00",
                        created_at=datetime(2026, 10, 1, 19, tzinfo=UTC),
                        items=[(tea, 1, "500.00")],
                    )
                    seed_order(
                        4,
                        status="paid",
                        payment_status="refunded",
                        amount="70.00",
                        created_at=datetime(2026, 10, 1, 20, tzinfo=UTC),
                        items=[(tea, 1, "70.00")],
                    )
                    seed_order(
                        5,
                        status="cancelled",
                        payment_status="succeeded",
                        amount="80.00",
                        created_at=datetime(2026, 10, 1, 21, tzinfo=UTC),
                        items=[(tea, 1, "80.00")],
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
                    yield {"client": client, "tokens": tokens}
            finally:
                app.dependency_overrides.pop(get_session, None)
                outer.rollback()
    finally:
        engine.dispose()


def test_reports_reconcile_revenue_days_and_top_products(
    reporting_setup: dict[str, Any],
) -> None:
    client: TestClient = reporting_setup["client"]
    params = {"date_from": "2026-10-01", "date_to": "2026-10-03"}
    headers = reporting_setup["tokens"]["Manager"]

    summary = client.get("/reports/revenue/summary", headers=headers, params=params)
    assert summary.status_code == 200, summary.text
    assert summary.json() == {
        "date_from": "2026-10-01",
        "date_to": "2026-10-03",
        "timezone": "Asia/Ho_Chi_Minh",
        "total_revenue": "145.00",
        "valid_order_count": 2,
        "average_order_value": "72.50",
        "refunded_amount": "70.00",
        "refunded_payment_count": 1,
        "cash_revenue": "145.00",
        "bank_transfer_revenue": "0.00",
        "paid_session_count": 0,
        "revenue_by_method": {"cash": "145.00", "bank_transfer": "0.00"},
    }

    daily = client.get("/reports/revenue/daily", headers=headers, params=params)
    assert [
        (row["date"], row["revenue"], row["order_count"])
        for row in daily.json()["items"]
    ] == [
        ("2026-10-01", "100.00", 1),
        ("2026-10-02", "45.00", 1),
        ("2026-10-03", "0.00", 0),
    ]

    products = client.get("/reports/top-products", headers=headers, params=params)
    assert [
        (row["product_name"], row["quantity_sold"], row["gross_item_sales"])
        for row in products.json()["items"]
    ] == [
        ("Latte", 3, "105.00"),
        ("Tea", 1, "40.00"),
    ]


def test_staff_cannot_access_revenue_reports(reporting_setup: dict[str, Any]) -> None:
    response = reporting_setup["client"].get(
        "/reports/revenue/summary",
        headers=reporting_setup["tokens"]["Staff"],
    )
    assert response.status_code == 403
