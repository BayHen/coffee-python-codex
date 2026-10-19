"""SQLAlchemy queries for customers, employees, orders, and loyalty."""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    Customer,
    Employee,
    LoyaltyTransaction,
    Order,
    User,
)


class PeopleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def loyalty_balance(self, customer_id: int) -> int:
        return int(
            self.db.scalar(
                select(
                    func.coalesce(func.sum(LoyaltyTransaction.points_delta), 0)
                ).where(LoyaltyTransaction.customer_id == customer_id)
            )
            or 0
        )

    def get_customer(self, customer_id: int, *, lock: bool = False) -> Customer | None:
        statement = select(Customer).where(Customer.id == customer_id)
        if lock:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def list_customers(
        self,
        *,
        search: str | None,
        is_active: bool | None,
        offset: int,
        limit: int,
    ) -> tuple[list[tuple[Customer, int]], int]:
        filters = []
        if search:
            filters.append(
                or_(
                    Customer.full_name.ilike(f"%{search}%"),
                    Customer.phone.ilike(f"%{search}%"),
                    Customer.email.ilike(f"%{search}%"),
                )
            )
        if is_active is not None:
            filters.append(Customer.is_active.is_(is_active))
        total = self.db.scalar(select(func.count(Customer.id)).where(*filters)) or 0
        points = func.coalesce(func.sum(LoyaltyTransaction.points_delta), 0)
        rows = self.db.execute(
            select(Customer, points)
            .outerjoin(
                LoyaltyTransaction, LoyaltyTransaction.customer_id == Customer.id
            )
            .where(*filters)
            .group_by(Customer.id)
            .order_by(Customer.full_name, Customer.id)
            .offset(offset)
            .limit(limit)
        ).all()
        return [(row[0], int(row[1])) for row in rows], total

    def list_customer_orders(
        self, customer_id: int, *, offset: int, limit: int
    ) -> tuple[list[Order], int]:
        total = (
            self.db.scalar(
                select(func.count(Order.id)).where(Order.customer_id == customer_id)
            )
            or 0
        )
        orders = self.db.scalars(
            select(Order)
            .where(Order.customer_id == customer_id)
            .order_by(Order.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return list(orders), total

    def get_employee(self, employee_id: int, *, lock: bool = False) -> Employee | None:
        statement = select(Employee).where(Employee.id == employee_id)
        if lock:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def list_employees(
        self,
        *,
        search: str | None,
        is_active: bool | None,
        offset: int,
        limit: int,
    ) -> tuple[list[Employee], int]:
        filters = []
        if search:
            filters.append(
                or_(
                    Employee.full_name.ilike(f"%{search}%"),
                    Employee.employee_code.ilike(f"%{search}%"),
                )
            )
        if is_active is not None:
            filters.append(Employee.is_active.is_(is_active))
        total = self.db.scalar(select(func.count(Employee.id)).where(*filters)) or 0
        employees = self.db.scalars(
            select(Employee)
            .where(*filters)
            .order_by(Employee.full_name, Employee.id)
            .offset(offset)
            .limit(limit)
        ).all()
        return list(employees), total

    def get_user(self, user_id: int, *, lock: bool = False) -> User | None:
        statement = select(User).where(User.id == user_id)
        if lock:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def employee_for_user(self, user_id: int) -> Employee | None:
        return self.db.scalar(select(Employee).where(Employee.user_id == user_id))

    def get_loyalty_by_key(self, key: str) -> LoyaltyTransaction | None:
        return self.db.scalar(
            select(LoyaltyTransaction).where(LoyaltyTransaction.idempotency_key == key)
        )

    def loyalty_for_order(
        self, order_id: int, transaction_type: str
    ) -> LoyaltyTransaction | None:
        return self.db.scalar(
            select(LoyaltyTransaction).where(
                LoyaltyTransaction.order_id == order_id,
                LoyaltyTransaction.transaction_type == transaction_type,
            )
        )

    def list_loyalty(
        self, customer_id: int, *, offset: int, limit: int
    ) -> tuple[list[LoyaltyTransaction], int]:
        total = (
            self.db.scalar(
                select(func.count(LoyaltyTransaction.id)).where(
                    LoyaltyTransaction.customer_id == customer_id
                )
            )
            or 0
        )
        rows = self.db.scalars(
            select(LoyaltyTransaction)
            .where(LoyaltyTransaction.customer_id == customer_id)
            .order_by(LoyaltyTransaction.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return list(rows), total
