"""End-to-end authentication checks against a migrated PostgreSQL test DB."""

import os
import secrets
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.auth import bootstrap_admin
from app.auth.security import hash_password, refresh_token_hash, verify_password
from app.db.models import AuthSession, Role, User
from app.db.session import create_db_engine, get_session
from app.main import app


@pytest.fixture
def auth_setup(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
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
                    roles = {
                        name: Role(name=name) for name in ("Admin", "Manager", "Staff")
                    }
                    db.add_all(roles.values())
                    db.flush()
                    for name, role in roles.items():
                        db.add(
                            User(
                                role_id=role.id,
                                email=f"{name.lower()}@example.com",
                                password_hash=hash_password(password),
                                is_active=True,
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
                    yield {
                        "client": client,
                        "connection": connection,
                        "password": password,
                        "secret": os.environ["JWT_SECRET_KEY"],
                    }
            finally:
                app.dependency_overrides.pop(get_session, None)
                outer.rollback()
    finally:
        engine.dispose()


def login(client: TestClient, role: str, password: str) -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"email": f"{role.lower()}@example.com", "password": password},
    )
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_login_and_role_permissions(auth_setup: dict[str, Any]) -> None:
    client: TestClient = auth_setup["client"]
    password: str = auth_setup["password"]
    admin = login(client, "Admin", password)
    manager = login(client, "Manager", password)
    staff = login(client, "Staff", password)

    assert (
        client.get("/auth/me", headers=bearer(staff["access_token"])).json()["role"]
        == "Staff"
    )
    assert (
        client.get("/auth/roles", headers=bearer(admin["access_token"])).status_code
        == 200
    )
    assert (
        client.get("/auth/roles", headers=bearer(manager["access_token"])).status_code
        == 200
    )
    assert (
        client.get("/auth/users", headers=bearer(admin["access_token"])).status_code
        == 200
    )
    assert (
        client.get("/auth/users", headers=bearer(manager["access_token"])).status_code
        == 403
    )
    assert (
        client.get("/auth/roles", headers=bearer(staff["access_token"])).status_code
        == 403
    )
    assert client.get("/auth/me").status_code == 401

    new_password = secrets.token_urlsafe(20)
    create = client.post(
        "/auth/users",
        headers=bearer(admin["access_token"]),
        json={
            "email": "new.staff@example.com",
            "password": new_password,
            "role": "Staff",
        },
    )
    assert create.status_code == 201, create.text
    assert "password" not in create.json()
    assert login(client, "new.staff", new_password)["access_token"]
    duplicate = client.post(
        "/auth/users",
        headers=bearer(admin["access_token"]),
        json={
            "email": "new.staff@example.com",
            "password": new_password,
            "role": "Staff",
        },
    )
    assert duplicate.status_code == 409
    assert (
        client.post(
            "/auth/users",
            headers=bearer(manager["access_token"]),
            json={"email": "x@example.com", "password": new_password, "role": "Staff"},
        ).status_code
        == 403
    )


def test_refresh_rotation_logout_and_hash_only(auth_setup: dict[str, Any]) -> None:
    client: TestClient = auth_setup["client"]
    connection: Connection = auth_setup["connection"]
    tokens = login(client, "Staff", auth_setup["password"])
    session_hash = connection.scalar(select(AuthSession.refresh_token_hash))
    assert session_hash == refresh_token_hash(tokens["refresh_token"])
    assert tokens["refresh_token"] not in session_hash

    refreshed = client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 200, refreshed.text
    new_tokens = refreshed.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]
    assert (
        client.post(
            "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 401
    )
    assert (
        client.get("/auth/me", headers=bearer(new_tokens["access_token"])).status_code
        == 200
    )

    assert (
        client.post(
            "/auth/logout", headers=bearer(new_tokens["access_token"])
        ).status_code
        == 204
    )
    assert (
        client.get("/auth/me", headers=bearer(tokens["access_token"])).status_code
        == 401
    )
    assert (
        client.get("/auth/me", headers=bearer(new_tokens["access_token"])).status_code
        == 401
    )
    assert (
        client.post(
            "/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]}
        ).status_code
        == 401
    )


def test_bad_credentials_tokens_and_disabled_account(
    auth_setup: dict[str, Any],
) -> None:
    client: TestClient = auth_setup["client"]
    password: str = auth_setup["password"]
    assert (
        client.post(
            "/auth/login",
            json={"email": "staff@example.com", "password": secrets.token_urlsafe(16)},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/auth/login",
            json={"email": "missing@example.com", "password": password},
        ).status_code
        == 401
    )

    admin = login(client, "Admin", password)
    staff = login(client, "Staff", password)
    assert client.get("/auth/me", headers=bearer("not-a-jwt")).status_code == 401
    assert (
        client.post("/auth/refresh", json={"refresh_token": "not-a-token"}).status_code
        == 401
    )

    claims = jwt.decode(
        staff["access_token"],
        auth_setup["secret"],
        algorithms=["HS256"],
        audience="smart-coffee-client",
        issuer="smart-coffee-api",
    )
    claims["exp"] = datetime.now(UTC) - timedelta(seconds=1)
    expired = jwt.encode(claims, auth_setup["secret"], algorithm="HS256")
    assert client.get("/auth/me", headers=bearer(expired)).status_code == 401
    wrong_signature = jwt.encode(
        claims | {"exp": datetime.now(UTC) + timedelta(minutes=5)},
        secrets.token_urlsafe(48),
        algorithm="HS256",
    )
    assert client.get("/auth/me", headers=bearer(wrong_signature)).status_code == 401
    wrong_type = jwt.encode(
        claims | {"type": "refresh", "exp": datetime.now(UTC) + timedelta(minutes=5)},
        auth_setup["secret"],
        algorithm="HS256",
    )
    assert client.get("/auth/me", headers=bearer(wrong_type)).status_code == 401

    staff_user_id = auth_setup["connection"].scalar(
        select(User.id).where(User.email == "staff@example.com")
    )
    response = client.patch(
        f"/auth/users/{staff_user_id}/status",
        headers=bearer(admin["access_token"]),
        json={"is_active": False},
    )
    assert response.status_code == 200, response.text
    assert (
        client.post(
            "/auth/login", json={"email": "staff@example.com", "password": password}
        ).status_code
        == 403
    )
    assert (
        client.get("/auth/me", headers=bearer(staff["access_token"])).status_code == 401
    )
    assert (
        client.post(
            "/auth/refresh", json={"refresh_token": staff["refresh_token"]}
        ).status_code
        == 401
    )


def test_bootstrap_admin_is_interactive_and_one_time(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a migrated PostgreSQL test DB")
    if not (make_url(url).database or "").endswith("_test"):
        pytest.fail("TEST_DATABASE_URL database name must end with _test")

    password = secrets.token_urlsafe(20)
    engine = create_db_engine(url)
    try:
        with engine.connect() as connection:
            outer = connection.begin()
            try:
                factory = sessionmaker(
                    bind=connection, join_transaction_mode="create_savepoint"
                )
                monkeypatch.setattr(
                    bootstrap_admin, "get_session_factory", lambda: factory
                )
                monkeypatch.setattr(
                    bootstrap_admin.sys,
                    "stdin",
                    SimpleNamespace(isatty=lambda: True),
                )
                monkeypatch.setattr(
                    bootstrap_admin.getpass, "getpass", lambda _prompt: password
                )

                assert bootstrap_admin.main(["--email", "bootstrap@example.com"]) == 0
                assert bootstrap_admin.main(["--email", "other@example.com"]) == 1
                with Session(bind=connection) as db:
                    user = db.scalar(
                        select(User).where(User.email == "bootstrap@example.com")
                    )
                    assert user is not None
                    assert user.password_hash.startswith("$argon2id$")
                    assert user.password_hash != password
                    assert verify_password(password, user.password_hash)
                    assert len(db.scalars(select(Role)).all()) == 3
                output = capsys.readouterr()
                assert password not in output.out + output.err
            finally:
                outer.rollback()
    finally:
        engine.dispose()


def test_email_unique_ignores_case(auth_setup: dict[str, Any]) -> None:
    connection: Connection = auth_setup["connection"]
    role_id, password_hash = connection.execute(
        select(User.role_id, User.password_hash).where(
            User.email == "admin@example.com"
        )
    ).one()
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                insert(User).values(
                    role_id=role_id,
                    email="ADMIN@EXAMPLE.COM",
                    password_hash=password_hash,
                )
            )
