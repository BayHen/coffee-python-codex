"""SQLAlchemy data access for orders and simulated payments."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    Customer,
    Employee,
    Order,
    Payment,
    Product,
    ProductVariant,
)


class OrderRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def eager_order_options() -> tuple[object, ...]:
        return (
            selectinload(Order.items),
            selectinload(Order.events),
            selectinload(Order.payments),
        )

    def get_order(self, order_id: int, *, lock: bool = False) -> Order | None:
        statement = (
            select(Order)
            .where(Order.id == order_id)
            .options(*self.eager_order_options())
        )
        if lock:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def get_order_by_key(self, key: str) -> Order | None:
        return self.db.scalar(
            select(Order)
            .where(Order.idempotency_key == key)
            .options(*self.eager_order_options())
        )

    def list_orders(
        self,
        *,
        status: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[Order], int]:
        filters = [Order.status == status] if status else []
        total = self.db.scalar(select(func.count(Order.id)).where(*filters)) or 0
        rows = self.db.scalars(
            select(Order)
            .where(*filters)
            .options(*self.eager_order_options())
            .order_by(Order.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return list(rows), total

    def lock_variants(self, variant_ids: list[int]) -> list[ProductVariant]:
        return list(
            self.db.scalars(
                select(ProductVariant)
                .join(ProductVariant.product)
                .where(ProductVariant.id.in_(variant_ids))
                .order_by(ProductVariant.id)
                .options(selectinload(ProductVariant.product))
                .with_for_update(of=(ProductVariant, Product))
            ).all()
        )

    def customer_exists(self, customer_id: int) -> bool:
        return bool(
            self.db.scalar(
                select(Customer.id).where(
                    Customer.id == customer_id, Customer.is_active.is_(True)
                )
            )
        )

    def employee_id_for_user(self, user_id: int) -> int | None:
        return self.db.scalar(select(Employee.id).where(Employee.user_id == user_id))

    def get_payment_by_key(self, key: str) -> Payment | None:
        return self.db.scalar(select(Payment).where(Payment.idempotency_key == key))
