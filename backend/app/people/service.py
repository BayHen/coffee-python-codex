"""Customer, employee, and loyalty business rules."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    AuthSession,
    Customer,
    Employee,
    LoyaltyTransaction,
    Order,
    User,
)
from app.people.repository import PeopleRepository
from app.people.schemas import (
    CustomerCreate,
    CustomerOrderPage,
    CustomerPage,
    CustomerUpdate,
    CustomerView,
    EmployeeCreate,
    EmployeePage,
    EmployeeUpdate,
    LoyaltyAdjustmentCreate,
    LoyaltyRefundCreate,
    LoyaltyTransactionPage,
)

LOYALTY_AMOUNT_PER_POINT = Decimal("10.00")


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code, detail={"code": code, "message": message}
    )


def fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def points_for_paid_amount(total_amount: Decimal) -> int:
    return int(total_amount // LOYALTY_AMOUNT_PER_POINT)


class PeopleService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = PeopleRepository(db)

    def _customer_view(
        self, customer: Customer, points: int | None = None
    ) -> CustomerView:
        return CustomerView(
            id=customer.id,
            full_name=customer.full_name,
            phone=customer.phone,
            email=customer.email,
            is_active=customer.is_active,
            loyalty_points=(
                self.repository.loyalty_balance(customer.id)
                if points is None
                else points
            ),
            created_at=customer.created_at,
        )

    def get_customer(self, customer_id: int) -> CustomerView:
        customer = self.repository.get_customer(customer_id)
        if customer is None:
            raise api_error(404, "customer_not_found", "Customer not found")
        return self._customer_view(customer)

    def list_customers(
        self,
        *,
        search: str | None,
        is_active: bool | None,
        page: int,
        page_size: int,
    ) -> CustomerPage:
        rows, total = self.repository.list_customers(
            search=search,
            is_active=is_active,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return CustomerPage(
            items=[self._customer_view(customer, points) for customer, points in rows],
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    def create_customer(self, payload: CustomerCreate) -> CustomerView:
        try:
            with self.db.begin():
                customer = Customer(**payload.model_dump(), is_active=True)
                self.db.add(customer)
                self.db.flush()
                customer_id = customer.id
            return self.get_customer(customer_id)
        except IntegrityError as exc:
            raise api_error(
                409,
                "customer_contact_exists",
                "Customer email or phone already exists",
            ) from exc

    def update_customer(
        self, customer_id: int, payload: CustomerUpdate, principal_role: str
    ) -> CustomerView:
        if "is_active" in payload.model_fields_set and principal_role == "Staff":
            raise api_error(
                403,
                "customer_status_forbidden",
                "Staff cannot change customer status",
            )
        try:
            with self.db.begin():
                customer = self.repository.get_customer(customer_id, lock=True)
                if customer is None:
                    raise api_error(404, "customer_not_found", "Customer not found")
                changes = payload.model_dump(exclude_unset=True)
                resulting_phone = changes.get("phone", customer.phone)
                resulting_email = changes.get("email", customer.email)
                if resulting_phone is None and resulting_email is None:
                    raise api_error(
                        422,
                        "customer_contact_required",
                        "Customer must keep a phone or email",
                    )
                for field, value in changes.items():
                    setattr(customer, field, value)
                self.db.flush()
            return self.get_customer(customer_id)
        except IntegrityError as exc:
            raise api_error(
                409,
                "customer_contact_exists",
                "Customer email or phone already exists",
            ) from exc

    def deactivate_customer(self, customer_id: int) -> None:
        with self.db.begin():
            customer = self.repository.get_customer(customer_id, lock=True)
            if customer is None:
                raise api_error(404, "customer_not_found", "Customer not found")
            customer.is_active = False

    def customer_orders(
        self, customer_id: int, page: int, page_size: int
    ) -> CustomerOrderPage:
        if self.repository.get_customer(customer_id) is None:
            raise api_error(404, "customer_not_found", "Customer not found")
        orders, total = self.repository.list_customer_orders(
            customer_id, offset=(page - 1) * page_size, limit=page_size
        )
        return CustomerOrderPage(
            items=orders,
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    def list_employees(
        self,
        *,
        search: str | None,
        is_active: bool | None,
        page: int,
        page_size: int,
    ) -> EmployeePage:
        employees, total = self.repository.list_employees(
            search=search,
            is_active=is_active,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return EmployeePage(
            items=employees,
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    def get_employee(self, employee_id: int) -> Employee:
        employee = self.repository.get_employee(employee_id)
        if employee is None:
            raise api_error(404, "employee_not_found", "Employee not found")
        return employee

    def _validate_user_link(
        self,
        user_id: int,
        principal_role: str,
        current_employee_id: int | None = None,
    ) -> User:
        user = self.repository.get_user(user_id, lock=True)
        if user is None:
            raise api_error(404, "user_not_found", "User account not found")
        linked = self.repository.employee_for_user(user_id)
        if linked is not None and linked.id != current_employee_id:
            raise api_error(409, "user_already_linked", "User already has an employee")
        if principal_role == "Manager" and user.role.name != "Staff":
            raise api_error(
                403, "employee_link_forbidden", "Manager can link Staff only"
            )
        return user

    @staticmethod
    def _validate_employee_scope(employee: Employee, principal_role: str) -> None:
        if (
            principal_role == "Manager"
            and employee.user is not None
            and employee.user.role.name != "Staff"
        ):
            raise api_error(
                403,
                "employee_management_forbidden",
                "Manager can manage Staff employees only",
            )

    def create_employee(self, payload: EmployeeCreate, principal_role: str) -> Employee:
        try:
            with self.db.begin():
                user = None
                if payload.user_id is not None:
                    user = self._validate_user_link(payload.user_id, principal_role)
                employee = Employee(**payload.model_dump())
                self.db.add(employee)
                if user is not None and not payload.is_active:
                    self._disable_user(user.id)
                self.db.flush()
            return employee
        except IntegrityError as exc:
            raise api_error(
                409,
                "employee_conflict",
                "Employee code or user account already exists",
            ) from exc

    def update_employee(
        self,
        employee_id: int,
        payload: EmployeeUpdate,
        principal_user_id: int,
        principal_role: str,
    ) -> Employee:
        try:
            with self.db.begin():
                employee = self.repository.get_employee(employee_id, lock=True)
                if employee is None:
                    raise api_error(404, "employee_not_found", "Employee not found")
                self._validate_employee_scope(employee, principal_role)
                changes = payload.model_dump(exclude_unset=True)
                target_user_id = changes.get("user_id")
                if "user_id" in changes and target_user_id is not None:
                    self._validate_user_link(
                        target_user_id, principal_role, current_employee_id=employee.id
                    )
                if (
                    changes.get("is_active") is False
                    and employee.user_id == principal_user_id
                ):
                    raise api_error(
                        400, "cannot_deactivate_self", "Cannot deactivate yourself"
                    )
                for field, value in changes.items():
                    setattr(employee, field, value)
                if not employee.is_active and employee.user_id is not None:
                    self._disable_user(employee.user_id)
                self.db.flush()
            return employee
        except IntegrityError as exc:
            raise api_error(
                409,
                "employee_conflict",
                "Employee code or user account already exists",
            ) from exc

    def deactivate_employee(
        self,
        employee_id: int,
        principal_user_id: int,
        principal_role: str,
    ) -> None:
        self.update_employee(
            employee_id,
            EmployeeUpdate(is_active=False),
            principal_user_id,
            principal_role,
        )

    def _disable_user(self, user_id: int) -> None:
        user = self.repository.get_user(user_id, lock=True)
        if user is None:
            return
        user.is_active = False
        self.db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )

    def list_loyalty(
        self, customer_id: int, page: int, page_size: int
    ) -> LoyaltyTransactionPage:
        if self.repository.get_customer(customer_id) is None:
            raise api_error(404, "customer_not_found", "Customer not found")
        items, total = self.repository.list_loyalty(
            customer_id, offset=(page - 1) * page_size, limit=page_size
        )
        return LoyaltyTransactionPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    def adjust_loyalty(
        self,
        customer_id: int,
        payload: LoyaltyAdjustmentCreate,
        idempotency_key: str,
        actor_user_id: int,
    ) -> LoyaltyTransaction:
        request_hash = fingerprint(
            {
                "customer_id": customer_id,
                "points_delta": payload.points_delta,
                "reason": payload.reason,
            }
        )
        try:
            with self.db.begin():
                existing = self.repository.get_loyalty_by_key(idempotency_key)
                if existing is not None:
                    return self._validate_existing_loyalty(existing, request_hash)
                customer = self.repository.get_customer(customer_id, lock=True)
                if customer is None:
                    raise api_error(404, "customer_not_found", "Customer not found")
                if (
                    self.repository.loyalty_balance(customer_id) + payload.points_delta
                    < 0
                ):
                    raise api_error(
                        409,
                        "insufficient_loyalty_points",
                        "Loyalty balance cannot become negative",
                    )
                transaction = LoyaltyTransaction(
                    customer_id=customer_id,
                    actor_user_id=actor_user_id,
                    idempotency_key=idempotency_key,
                    request_fingerprint=request_hash,
                    transaction_type="adjustment",
                    points_delta=payload.points_delta,
                    reason=payload.reason,
                )
                self.db.add(transaction)
                self.db.flush()
            return transaction
        except IntegrityError as exc:
            with self.db.begin():
                existing = self.repository.get_loyalty_by_key(idempotency_key)
                if existing is not None:
                    return self._validate_existing_loyalty(existing, request_hash)
            raise api_error(
                409, "loyalty_conflict", "Loyalty adjustment conflicted"
            ) from exc

    def refund_loyalty(
        self,
        order_id: int,
        payload: LoyaltyRefundCreate,
        idempotency_key: str,
        actor_user_id: int,
    ) -> LoyaltyTransaction:
        request_hash = fingerprint({"order_id": order_id, "reason": payload.reason})
        try:
            with self.db.begin():
                existing = self.repository.get_loyalty_by_key(idempotency_key)
                if existing is not None:
                    return self._validate_existing_loyalty(existing, request_hash)
                order = self.db.get(Order, order_id, with_for_update=True)
                if order is None:
                    raise api_error(404, "order_not_found", "Order not found")
                if order.status != "paid" or order.customer_id is None:
                    raise api_error(
                        409,
                        "loyalty_refund_not_allowed",
                        "A paid customer order is required",
                    )
                customer = self.repository.get_customer(order.customer_id, lock=True)
                if customer is None:
                    raise api_error(
                        409,
                        "order_customer_missing",
                        "Order customer is no longer available",
                    )
                earn = self.repository.loyalty_for_order(order.id, "earn")
                if earn is None:
                    raise api_error(
                        409,
                        "loyalty_earn_not_found",
                        "Order did not earn loyalty points",
                    )
                previous_refund = self.repository.loyalty_for_order(order.id, "refund")
                if previous_refund is not None:
                    raise api_error(
                        409,
                        "loyalty_already_refunded",
                        "Order loyalty points were already refunded",
                    )
                if self.repository.loyalty_balance(customer.id) < earn.points_delta:
                    raise api_error(
                        409,
                        "insufficient_loyalty_points",
                        "Current balance is lower than the earned points",
                    )
                transaction = LoyaltyTransaction(
                    customer_id=customer.id,
                    order_id=order.id,
                    actor_user_id=actor_user_id,
                    idempotency_key=idempotency_key,
                    request_fingerprint=request_hash,
                    transaction_type="refund",
                    points_delta=-earn.points_delta,
                    reason=payload.reason,
                )
                self.db.add(transaction)
                self.db.flush()
            return transaction
        except IntegrityError as exc:
            with self.db.begin():
                existing = self.repository.get_loyalty_by_key(idempotency_key)
                if existing is not None:
                    return self._validate_existing_loyalty(existing, request_hash)
            raise api_error(
                409, "loyalty_conflict", "Loyalty refund conflicted"
            ) from exc

    @staticmethod
    def _validate_existing_loyalty(
        transaction: LoyaltyTransaction, request_hash: str
    ) -> LoyaltyTransaction:
        if transaction.request_fingerprint != request_hash:
            raise api_error(
                409,
                "idempotency_key_reused",
                "Idempotency-Key was already used for a different loyalty request",
            )
        return transaction

    def award_for_paid_order(self, order: Order, actor_user_id: int) -> None:
        if order.customer_id is None:
            return
        customer = self.repository.get_customer(order.customer_id, lock=True)
        if customer is None:
            raise api_error(409, "customer_not_found", "Customer no longer exists")
        points = points_for_paid_amount(order.total_amount)
        if points <= 0:
            return
        if self.repository.loyalty_for_order(order.id, "earn") is not None:
            return
        key = f"loyalty:earn:order:{order.id}"
        self.db.add(
            LoyaltyTransaction(
                customer_id=order.customer_id,
                order_id=order.id,
                actor_user_id=actor_user_id,
                idempotency_key=key,
                request_fingerprint=fingerprint(
                    {"order_id": order.id, "points": points}
                ),
                transaction_type="earn",
                points_delta=points,
                reason=f"Earned from paid order {order.id}",
            )
        )
