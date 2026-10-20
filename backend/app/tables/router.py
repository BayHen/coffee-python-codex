"""HTTP API for tables, table sessions, and additional orders."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, require_roles
from app.db.session import get_session
from app.tables.schemas import (
    BankTransferView,
    CheckoutCreate,
    ItemCreate,
    ItemUpdate,
    OrderCreate,
    PaymentView,
    ReceiptView,
    SessionOrderView,
    SessionView,
    TableCreate,
    TableUpdate,
    TableView,
)
from app.tables.service import TableService

router = APIRouter(tags=["table service"])
Operator = Annotated[Principal, Depends(require_roles("Admin", "Manager", "Staff"))]
Manager = Annotated[Principal, Depends(require_roles("Admin", "Manager"))]
Db = Annotated[Session, Depends(get_session)]
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


@router.get("/tables", response_model=list[TableView])
def list_tables(_principal: Operator, db: Db) -> list[TableView]:
    return TableService(db).list_tables()


@router.post("/tables", response_model=TableView, status_code=201)
def create_table(payload: TableCreate, _principal: Manager, db: Db) -> TableView:
    return TableService(db).create_table(payload)


@router.get("/tables/{table_id}", response_model=TableView)
def get_table(table_id: int, _principal: Operator, db: Db) -> TableView:
    return TableService(db).get_table(table_id)


@router.patch("/tables/{table_id}", response_model=TableView)
def update_table(
    table_id: int, payload: TableUpdate, _principal: Manager, db: Db
) -> TableView:
    return TableService(db).update_table(table_id, payload)


@router.post("/tables/{table_id}/sessions", response_model=SessionView, status_code=201)
def open_session(table_id: int, principal: Operator, db: Db) -> SessionView:
    return TableService(db).open_session(table_id, principal.user_id)


@router.get("/tables/{table_id}/active-session", response_model=SessionView)
def active_session(table_id: int, _principal: Operator, db: Db) -> SessionView:
    return TableService(db).active_session(table_id)


@router.get("/sessions/{session_id}", response_model=SessionView)
def get_session(session_id: int, _principal: Operator, db: Db) -> SessionView:
    return TableService(db).get_session(session_id)


@router.get("/sessions/{session_id}/orders", response_model=list[SessionOrderView])
def session_orders(
    session_id: int, _principal: Operator, db: Db
) -> list[SessionOrderView]:
    return TableService(db).get_session(session_id)["orders"]


@router.get("/sessions/{session_id}/bill")
def session_bill(session_id: int, _principal: Operator, db: Db) -> object:
    return TableService(db).get_session(session_id)["bill"]


@router.post(
    "/sessions/{session_id}/orders", response_model=SessionOrderView, status_code=201
)
def additional_order(
    session_id: int, payload: OrderCreate, principal: Operator, db: Db
) -> SessionOrderView:
    return TableService(db).create_additional_order(session_id, principal.user_id)


@router.post(
    "/orders/{order_id}/items", response_model=SessionOrderView, status_code=201
)
def add_item(
    order_id: int, payload: ItemCreate, _principal: Operator, db: Db
) -> SessionOrderView:
    return TableService(db).add_item(
        order_id, payload.variant_id, payload.topping_ids, payload.quantity
    )


@router.patch("/orders/{order_id}/items/{item_id}", response_model=SessionOrderView)
def update_item(
    order_id: int, item_id: int, payload: ItemUpdate, _principal: Operator, db: Db
) -> SessionOrderView:
    return TableService(db).update_item(order_id, item_id, payload.quantity)


@router.delete("/orders/{order_id}/items/{item_id}", status_code=204)
def delete_item(order_id: int, item_id: int, _principal: Operator, db: Db) -> Response:
    TableService(db).delete_item(order_id, item_id)
    return Response(status_code=204)


@router.post("/orders/{order_id}/confirm", response_model=SessionOrderView)
def confirm_order(order_id: int, principal: Operator, db: Db) -> SessionOrderView:
    return TableService(db).confirm(order_id, principal.user_id)


@router.post(
    "/sessions/{session_id}/checkout", response_model=PaymentView, status_code=201
)
def checkout(
    session_id: int, payload: CheckoutCreate, key: Key, principal: Operator, db: Db
) -> PaymentView:
    return TableService(db).checkout(session_id, payload, key, principal.user_id)


@router.get("/sessions/{session_id}/bank-transfer", response_model=BankTransferView)
def bank_transfer(session_id: int, _principal: Operator, db: Db) -> BankTransferView:
    return TableService(db).bank_transfer(session_id)


@router.get("/receipts", response_model=list[ReceiptView])
def list_receipts(
    _principal: Operator,
    db: Db,
    page: int = 1,
    page_size: int = 50,
) -> list[ReceiptView]:
    return TableService(db).list_receipts(page, min(page_size, 100))


@router.get("/receipts/{receipt_number}", response_model=ReceiptView)
def get_receipt(receipt_number: str, _principal: Operator, db: Db) -> ReceiptView:
    return TableService(db).get_receipt(receipt_number)
