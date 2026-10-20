"""Demo data is safe, opt-in, and repeatable."""

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app import demo_seed
from app.auth.security import verify_password
from app.db.models import InventoryTransaction, ProductVariant, User
from app.db.session import create_db_engine


@pytest.fixture
def demo_db() -> Iterator[Session]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a migrated PostgreSQL test DB")
    if not (make_url(url).database or "").endswith("_test"):
        pytest.fail("TEST_DATABASE_URL database name must end with _test")
    engine = create_db_engine(url)
    try:
        with engine.connect() as connection:
            outer = connection.begin()
            try:
                with Session(
                    bind=connection,
                    join_transaction_mode="create_savepoint",
                    expire_on_commit=False,
                ) as db:
                    yield db
            finally:
                outer.rollback()
    finally:
        engine.dispose()


def test_demo_seed_is_idempotent_and_uses_fake_identity(demo_db: Session) -> None:
    password = "safe-demo-password"
    with demo_db.begin():
        demo_seed.seed(demo_db, password)
    with demo_db.begin():
        demo_seed.seed(demo_db, password)

    user = demo_db.scalar(select(User).where(User.email == demo_seed.DEMO_EMAIL))
    assert user is not None
    assert user.email.endswith("@example.com")
    assert verify_password(password, user.password_hash)
    assert (
        demo_db.scalar(
            select(func.count(ProductVariant.id)).where(
                ProductVariant.sku.like("DEMO-%")
            )
        )
        == 3
    )
    assert (
        demo_db.scalar(
            select(func.count(InventoryTransaction.id)).where(
                InventoryTransaction.idempotency_key.like("demo-opening:%")
            )
        )
        == 3
    )


def test_demo_seed_refuses_production(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_ADMIN_PASSWORD", "safe-demo-password")
    assert demo_seed.main() == 1
    assert "disabled" in capsys.readouterr().err
