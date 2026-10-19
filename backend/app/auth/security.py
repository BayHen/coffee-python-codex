"""Password hashing, signed access tokens, and opaque refresh tokens."""

import hashlib
import os
import re
import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from uuid import UUID, uuid4

import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

ACCESS_TOKEN_MINUTES = 15
REFRESH_TOKEN_DAYS = 7
JWT_ISSUER = "smart-coffee-api"
JWT_AUDIENCE = "smart-coffee-client"
JWT_ALGORITHM = "HS256"

password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        return password_hasher.verify(password, encoded_hash)
    except UnknownHashError:
        return False


@lru_cache
def dummy_password_hash() -> str:
    """Spend hashing work for unknown users without storing a fixed password."""
    return hash_password(secrets.token_urlsafe(32))


def jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET_KEY", "")
    if len(secret.encode("utf-8")) < 32:
        raise RuntimeError("JWT_SECRET_KEY must contain at least 32 random bytes")
    return secret


def create_access_token(user_id: int, session_id: UUID) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "type": "access",
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
        "jti": uuid4().hex,
    }
    return jwt.encode(payload, jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, object]:
    return jwt.decode(
        token,
        jwt_secret(),
        algorithms=[JWT_ALGORITHM],
        audience=JWT_AUDIENCE,
        issuer=JWT_ISSUER,
        options={
            "require": ["sub", "sid", "type", "iss", "aud", "iat", "nbf", "exp"],
        },
    )


def refresh_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def create_refresh_token(session_id: UUID) -> tuple[str, str]:
    raw_token = f"{session_id.hex}.{secrets.token_urlsafe(32)}"
    return raw_token, refresh_token_hash(raw_token)


def parse_refresh_token(token: str) -> tuple[UUID, str] | None:
    if not re.fullmatch(r"[0-9a-f]{32}\.[A-Za-z0-9_-]{43}", token):
        return None
    session_hex, _ = token.split(".", maxsplit=1)
    return UUID(hex=session_hex), refresh_token_hash(token)
