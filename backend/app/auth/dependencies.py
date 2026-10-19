"""FastAPI dependencies for signed sessions and role checks."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.db.models import AuthSession, User
from app.db.session import get_session

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    user_id: int
    session_id: UUID
    email: str
    role: str


def unauthorized(detail: str = "Invalid or missing access token") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_session)],
) -> Principal:
    if credentials is None:
        raise unauthorized()
    try:
        claims = decode_access_token(credentials.credentials)
    except ExpiredSignatureError as exc:
        raise unauthorized("Access token expired") from exc
    except InvalidTokenError as exc:
        raise unauthorized() from exc

    try:
        if claims.get("type") != "access":
            raise ValueError("Unexpected token type")
        user_id = int(str(claims["sub"]))
        if user_id <= 0:
            raise ValueError("Invalid subject")
        session_id = UUID(str(claims["sid"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise unauthorized() from exc

    with db.begin():
        auth_session = db.get(AuthSession, session_id)
        if (
            auth_session is None
            or auth_session.user_id != user_id
            or auth_session.revoked_at is not None
            or auth_session.expires_at <= datetime.now(UTC)
        ):
            raise unauthorized()
        user = db.get(User, user_id)
        if user is None:
            raise unauthorized()
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is inactive")
        if user.employee is not None and not user.employee.is_active:
            raise HTTPException(status_code=403, detail="Employee is inactive")
        return Principal(
            user_id=user.id,
            session_id=session_id,
            email=user.email,
            role=user.role.name,
        )


def require_roles(*allowed_roles: str) -> Callable[..., Principal]:
    def check_role(
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> Principal:
        if principal.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return principal

    return check_role
