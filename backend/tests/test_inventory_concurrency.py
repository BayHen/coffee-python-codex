"""PostgreSQL concurrency test proving stock cannot become negative."""

import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.db.models import Ingredient, InventoryTransaction, Role, User
from app.db.session import create_db_engine
from app.inventory.schemas import ManualMovementCreate
from app.inventory.service import InventoryService, fingerprint


def test_concurrent_outflows_cannot_overdraw_stock() -> None:
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
            role = Role(name=f"InventoryConcurrency-{suffix}")
            db.add(role)
            db.flush()
            user = User(
                role_id=role.id,
                email=f"inventory-concurrency-{suffix}@example.com",
                password_hash=hash_password(uuid4().hex),
            )
            ingredient = Ingredient(
                sku=f"CONCURRENT-{suffix}",
                name=f"Concurrent ingredient {suffix}",
                unit="g",
            )
            db.add_all([user, ingredient])
            db.flush()
            opening_delta = Decimal("1000.000")
            db.add(
                InventoryTransaction(
                    ingredient_id=ingredient.id,
                    actor_user_id=user.id,
                    idempotency_key=f"opening-{suffix}",
                    request_fingerprint=fingerprint(
                        {"ingredient_id": ingredient.id, "delta": str(opening_delta)}
                    ),
                    transaction_type="purchase",
                    quantity_delta=opening_delta,
                    reason="Concurrency test opening stock",
                )
            )
            ids.update(role=role.id, user=user.id, ingredient=ingredient.id)

        barrier = Barrier(2)

        def remove_stock(attempt: int) -> tuple[str, int]:
            barrier.wait(timeout=10)
            with Session(engine, expire_on_commit=False) as db:
                try:
                    transaction = InventoryService(db).record_manual_movement(
                        ManualMovementCreate(
                            ingredient_id=ids["ingredient"],
                            transaction_type="waste",
                            quantity_delta=Decimal("-700.000"),
                            reason=f"Concurrent waste attempt {attempt}",
                        ),
                        f"waste-{suffix}-{attempt}",
                        ids["user"],
                    )
                    return "succeeded", transaction.id
                except HTTPException as exc:
                    return "rejected", exc.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(remove_stock, (1, 2)))

        assert sorted(result[0] for result in results) == ["rejected", "succeeded"]
        assert next(value for outcome, value in results if outcome == "rejected") == 409
        with Session(engine) as db:
            assert InventoryService(db).get_ingredient(
                ids["ingredient"]
            ).current_stock == Decimal("300.000")
    finally:
        if ids:
            with Session(engine) as db, db.begin():
                db.execute(
                    delete(InventoryTransaction).where(
                        InventoryTransaction.ingredient_id == ids["ingredient"]
                    )
                )
                db.execute(delete(Ingredient).where(Ingredient.id == ids["ingredient"]))
                db.execute(delete(User).where(User.id == ids["user"]))
                db.execute(delete(Role).where(Role.id == ids["role"]))
        engine.dispose()
