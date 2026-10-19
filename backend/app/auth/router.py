"""Login, refresh, logout, and small role-protected account endpoints."""

import hmac
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    Principal,
    current_principal,
    require_roles,
    unauthorized,
)
from app.auth.schemas import (
    CreateUserRequest,
    LoginRequest,
    RefreshRequest,
    TokenPair,
    UserStatusUpdate,
    UserView,
)
from app.auth.security import (
    ACCESS_TOKEN_MINUTES,
    REFRESH_TOKEN_DAYS,
    create_access_token,
    create_refresh_token,
    dummy_password_hash,
    hash_password,
    parse_refresh_token,
    verify_password,
)
from app.db.models import AuthSession, Role, User
from app.db.session import get_session

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair)
def login(
    payload: LoginRequest,
    response: Response,
    db: Annotated[Session, Depends(get_session)],
) -> TokenPair:
    response.headers["Cache-Control"] = "no-store"
    with db.begin():
        user = db.scalar(
            select(User).where(func.lower(User.email) == str(payload.email))
        )
        password = payload.password.get_secret_value()
        if user is None:
            verify_password(password, dummy_password_hash())
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is inactive")
        if user.employee is not None and not user.employee.is_active:
            raise HTTPException(status_code=403, detail="Employee is inactive")

        session_id = uuid4()
        raw_refresh, hashed_refresh = create_refresh_token(session_id)
        db.add(
            AuthSession(
                id=session_id,
                user_id=user.id,
                refresh_token_hash=hashed_refresh,
                expires_at=datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_DAYS),
            )
        )
        access = create_access_token(user.id, session_id)

    return TokenPair(
        access_token=access,
        refresh_token=raw_refresh,
        expires_in=ACCESS_TOKEN_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenPair)
def refresh(
    payload: RefreshRequest,
    response: Response,
    db: Annotated[Session, Depends(get_session)],
) -> TokenPair:
    response.headers["Cache-Control"] = "no-store"
    parsed = parse_refresh_token(payload.refresh_token)
    if parsed is None:
        raise unauthorized("Invalid refresh token")
    session_id, presented_hash = parsed

    with db.begin():
        auth_session = db.get(AuthSession, session_id, with_for_update=True)
        if (
            auth_session is None
            or auth_session.revoked_at is not None
            or auth_session.expires_at <= datetime.now(UTC)
            or not hmac.compare_digest(auth_session.refresh_token_hash, presented_hash)
        ):
            raise unauthorized("Invalid or expired refresh token")
        user = db.get(User, auth_session.user_id)
        if user is None:
            raise unauthorized("Invalid or expired refresh token")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is inactive")
        if user.employee is not None and not user.employee.is_active:
            raise HTTPException(status_code=403, detail="Employee is inactive")

        raw_refresh, auth_session.refresh_token_hash = create_refresh_token(session_id)
        access = create_access_token(user.id, session_id)

    return TokenPair(
        access_token=access,
        refresh_token=raw_refresh,
        expires_in=ACCESS_TOKEN_MINUTES * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    principal: Annotated[Principal, Depends(current_principal)],
    db: Annotated[Session, Depends(get_session)],
) -> None:
    with db.begin():
        auth_session = db.get(AuthSession, principal.session_id, with_for_update=True)
        if auth_session is None or auth_session.revoked_at is not None:
            raise unauthorized()
        auth_session.revoked_at = datetime.now(UTC)


@router.get("/me", response_model=UserView)
def me(principal: Annotated[Principal, Depends(current_principal)]) -> UserView:
    return UserView(
        id=principal.user_id,
        email=principal.email,
        role=principal.role,
        is_active=True,
    )


@router.get("/roles", response_model=list[str])
def list_roles(
    _principal: Annotated[Principal, Depends(require_roles("Admin", "Manager"))],
    db: Annotated[Session, Depends(get_session)],
) -> list[str]:
    return list(db.scalars(select(Role.name).order_by(Role.name)))


@router.get("/users", response_model=list[UserView])
def list_users(
    _principal: Annotated[Principal, Depends(require_roles("Admin"))],
    db: Annotated[Session, Depends(get_session)],
) -> list[UserView]:
    users = db.scalars(select(User).order_by(User.id)).all()
    return [
        UserView(
            id=user.id,
            email=user.email,
            role=user.role.name,
            is_active=user.is_active,
        )
        for user in users
    ]


@router.post("/users", response_model=UserView, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: CreateUserRequest,
    _principal: Annotated[Principal, Depends(require_roles("Admin"))],
    db: Annotated[Session, Depends(get_session)],
) -> UserView:
    try:
        with db.begin():
            role = db.scalar(select(Role).where(Role.name == payload.role))
            if role is None:
                raise HTTPException(status_code=409, detail="Role is not initialized")
            user = User(
                role_id=role.id,
                email=str(payload.email),
                password_hash=hash_password(payload.password.get_secret_value()),
                is_active=True,
            )
            db.add(user)
            db.flush()
            result = UserView(
                id=user.id, email=user.email, role=role.name, is_active=True
            )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409, detail="Email is already registered"
        ) from exc
    return result


@router.patch("/users/{user_id}/status", response_model=UserView)
def set_user_status(
    user_id: int,
    payload: UserStatusUpdate,
    principal: Annotated[Principal, Depends(require_roles("Admin"))],
    db: Annotated[Session, Depends(get_session)],
) -> UserView:
    with db.begin():
        user = db.get(User, user_id, with_for_update=True)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        if user.id == principal.user_id and not payload.is_active:
            raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
        user.is_active = payload.is_active
        if not payload.is_active:
            db.execute(
                update(AuthSession)
                .where(
                    AuthSession.user_id == user_id,
                    AuthSession.revoked_at.is_(None),
                )
                .values(revoked_at=datetime.now(UTC))
            )
        return UserView(
            id=user.id,
            email=user.email,
            role=user.role.name,
            is_active=user.is_active,
        )
