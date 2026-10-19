"""REST API for customer, employee, and loyalty management."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, require_roles
from app.db.session import get_session
from app.people.schemas import (
    CustomerCreate,
    CustomerOrderPage,
    CustomerPage,
    CustomerUpdate,
    CustomerView,
    EmployeeCreate,
    EmployeePage,
    EmployeeUpdate,
    EmployeeView,
    LoyaltyAdjustmentCreate,
    LoyaltyRefundCreate,
    LoyaltyTransactionPage,
    LoyaltyTransactionView,
)
from app.people.service import PeopleService

router = APIRouter(tags=["people"])
Reader = Annotated[Principal, Depends(require_roles("Admin", "Manager", "Staff"))]
Manager = Annotated[Principal, Depends(require_roles("Admin", "Manager"))]
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


@router.get("/customers", response_model=CustomerPage)
def list_customers(
    _principal: Reader,
    db: Db,
    search: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    is_active: bool | None = True,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CustomerPage:
    return PeopleService(db).list_customers(
        search=search,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )


@router.post("/customers", response_model=CustomerView, status_code=201)
def create_customer(
    payload: CustomerCreate, _principal: Reader, db: Db
) -> CustomerView:
    return PeopleService(db).create_customer(payload)


@router.get("/customers/{customer_id}", response_model=CustomerView)
def get_customer(customer_id: int, _principal: Reader, db: Db) -> CustomerView:
    return PeopleService(db).get_customer(customer_id)


@router.patch("/customers/{customer_id}", response_model=CustomerView)
def update_customer(
    customer_id: int, payload: CustomerUpdate, principal: Reader, db: Db
) -> CustomerView:
    return PeopleService(db).update_customer(customer_id, payload, principal.role)


@router.delete("/customers/{customer_id}", status_code=204)
def deactivate_customer(customer_id: int, _principal: Manager, db: Db) -> Response:
    PeopleService(db).deactivate_customer(customer_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/customers/{customer_id}/orders", response_model=CustomerOrderPage)
def customer_orders(
    customer_id: int,
    _principal: Reader,
    db: Db,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CustomerOrderPage:
    return PeopleService(db).customer_orders(customer_id, page, page_size)


@router.get("/customers/{customer_id}/loyalty", response_model=LoyaltyTransactionPage)
def list_loyalty(
    customer_id: int,
    _principal: Reader,
    db: Db,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> LoyaltyTransactionPage:
    return PeopleService(db).list_loyalty(customer_id, page, page_size)


@router.post(
    "/customers/{customer_id}/loyalty-adjustments",
    response_model=LoyaltyTransactionView,
    status_code=201,
)
def adjust_loyalty(
    customer_id: int,
    payload: LoyaltyAdjustmentCreate,
    idempotency_key: IdempotencyKey,
    principal: Manager,
    db: Db,
) -> LoyaltyTransactionView:
    return PeopleService(db).adjust_loyalty(
        customer_id, payload, idempotency_key, principal.user_id
    )


@router.post(
    "/orders/{order_id}/loyalty-refund",
    response_model=LoyaltyTransactionView,
    status_code=201,
)
def refund_loyalty(
    order_id: int,
    payload: LoyaltyRefundCreate,
    idempotency_key: IdempotencyKey,
    principal: Manager,
    db: Db,
) -> LoyaltyTransactionView:
    return PeopleService(db).refund_loyalty(
        order_id, payload, idempotency_key, principal.user_id
    )


@router.get("/employees", response_model=EmployeePage)
def list_employees(
    _principal: Reader,
    db: Db,
    search: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    is_active: bool | None = True,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> EmployeePage:
    return PeopleService(db).list_employees(
        search=search,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )


@router.post("/employees", response_model=EmployeeView, status_code=201)
def create_employee(
    payload: EmployeeCreate, principal: Manager, db: Db
) -> EmployeeView:
    return PeopleService(db).create_employee(payload, principal.role)


@router.get("/employees/{employee_id}", response_model=EmployeeView)
def get_employee(employee_id: int, _principal: Reader, db: Db) -> EmployeeView:
    return PeopleService(db).get_employee(employee_id)


@router.patch("/employees/{employee_id}", response_model=EmployeeView)
def update_employee(
    employee_id: int,
    payload: EmployeeUpdate,
    principal: Manager,
    db: Db,
) -> EmployeeView:
    return PeopleService(db).update_employee(
        employee_id, payload, principal.user_id, principal.role
    )


@router.delete("/employees/{employee_id}", status_code=204)
def deactivate_employee(employee_id: int, principal: Manager, db: Db) -> Response:
    PeopleService(db).deactivate_employee(
        employee_id, principal.user_id, principal.role
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
