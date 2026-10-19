"""REST API for order workflow and simulated payments."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, require_roles
from app.db.session import get_session
from app.orders.schemas import (
    OrderCreate,
    OrderPage,
    OrderStatus,
    OrderTransition,
    OrderUpdate,
    OrderView,
    PaymentView,
    SimulatedPaymentCreate,
)
from app.orders.service import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])
Operator = Annotated[Principal, Depends(require_roles("Admin", "Manager", "Staff"))]
Db = Annotated[Session, Depends(get_session)]
IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    ),
]


@router.get("", response_model=OrderPage)
def list_orders(
    _principal: Operator,
    db: Db,
    order_status: Annotated[OrderStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> OrderPage:
    return OrderService(db).list_orders(order_status, page, page_size)


@router.post("", response_model=OrderView, status_code=201)
def create_order(
    payload: OrderCreate,
    idempotency_key: IdempotencyKey,
    principal: Operator,
    db: Db,
) -> OrderView:
    return OrderService(db).create_order(payload, idempotency_key, principal.user_id)


@router.get("/{order_id}", response_model=OrderView)
def get_order(order_id: int, _principal: Operator, db: Db) -> OrderView:
    return OrderService(db).get_order(order_id)


@router.put("/{order_id}", response_model=OrderView)
def update_order(
    order_id: int, payload: OrderUpdate, principal: Operator, db: Db
) -> OrderView:
    return OrderService(db).update_order(order_id, payload, principal.user_id)


@router.post("/{order_id}/transitions", response_model=OrderView)
def transition_order(
    order_id: int,
    payload: OrderTransition,
    principal: Operator,
    db: Db,
) -> OrderView:
    if payload.target_status == "cancelled" and principal.role == "Staff":
        raise HTTPException(status_code=403, detail="Insufficient role")
    return OrderService(db).transition_order(order_id, payload, principal.user_id)


@router.post("/{order_id}/payments", response_model=PaymentView, status_code=201)
def simulate_payment(
    order_id: int,
    payload: SimulatedPaymentCreate,
    idempotency_key: IdempotencyKey,
    principal: Operator,
    db: Db,
) -> PaymentView:
    return OrderService(db).simulate_payment(
        order_id, payload, idempotency_key, principal.user_id
    )
