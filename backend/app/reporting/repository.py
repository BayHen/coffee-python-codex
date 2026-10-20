"""Index-friendly PostgreSQL aggregation queries for reports."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Date, cast, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Order, OrderItem, Payment


class ReportingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _valid_payment_filters(
        start_utc: datetime, end_utc: datetime
    ) -> tuple[object, ...]:
        return (
            Payment.status == "succeeded",
            Payment.created_at >= start_utc,
            Payment.created_at < end_utc,
        )

    def revenue_summary(
        self, start_utc: datetime, end_utc: datetime
    ) -> tuple[Decimal, int, Decimal, Decimal, int]:
        row = self.db.execute(
            select(
                func.coalesce(func.sum(Payment.amount), Decimal("0.00")),
                func.count(Payment.id),
                func.coalesce(
                    func.sum(Payment.amount).filter(Payment.method == "cash"),
                    Decimal("0.00"),
                ),
                func.coalesce(
                    func.sum(Payment.amount).filter(Payment.method == "bank_transfer"),
                    Decimal("0.00"),
                ),
                func.count(Payment.id).filter(Payment.session_id.is_not(None)),
            ).where(*self._valid_payment_filters(start_utc, end_utc))
        ).one()
        return (
            Decimal(row[0]),
            int(row[1]),
            Decimal(row[2]),
            Decimal(row[3]),
            int(row[4]),
        )

    def refunded_summary(
        self, start_utc: datetime, end_utc: datetime
    ) -> tuple[Decimal, int]:
        row = self.db.execute(
            select(
                func.coalesce(func.sum(Payment.amount), Decimal("0.00")),
                func.count(Payment.id),
            ).where(
                Payment.status == "refunded",
                Payment.created_at >= start_utc,
                Payment.created_at < end_utc,
            )
        ).one()
        return Decimal(row[0]), int(row[1])

    def daily_revenue(
        self, start_utc: datetime, end_utc: datetime, timezone_name: str
    ) -> list[tuple[object, Decimal, int]]:
        local_date = cast(func.timezone(timezone_name, Payment.created_at), Date)
        rows = self.db.execute(
            select(
                local_date.label("local_date"),
                func.sum(Payment.amount).label("revenue"),
                func.count(Payment.id).label("order_count"),
            )
            .where(*self._valid_payment_filters(start_utc, end_utc))
            .group_by(local_date)
            .order_by(local_date)
        ).all()
        return [
            (row.local_date, Decimal(row.revenue), int(row.order_count)) for row in rows
        ]

    def top_products(
        self, start_utc: datetime, end_utc: datetime, limit: int
    ) -> list[tuple[str, str, str, int, Decimal]]:
        rows = self.db.execute(
            select(
                OrderItem.product_name,
                OrderItem.variant_name,
                OrderItem.sku,
                func.sum(OrderItem.quantity).label("quantity_sold"),
                func.sum(OrderItem.line_total).label("gross_item_sales"),
            )
            .join(Order, Order.id == OrderItem.order_id)
            .join(
                Payment,
                or_(
                    Payment.order_id == Order.id,
                    Payment.session_id == Order.session_id,
                ),
            )
            .where(
                *self._valid_payment_filters(start_utc, end_utc),
                Order.status != "cancelled",
            )
            .group_by(
                OrderItem.product_name,
                OrderItem.variant_name,
                OrderItem.sku,
            )
            .order_by(
                func.sum(OrderItem.quantity).desc(),
                func.sum(OrderItem.line_total).desc(),
                OrderItem.product_name,
                OrderItem.variant_name,
            )
            .limit(limit)
        ).all()
        return [
            (
                row.product_name,
                row.variant_name,
                row.sku,
                int(row.quantity_sold),
                Decimal(row.gross_item_sales),
            )
            for row in rows
        ]
