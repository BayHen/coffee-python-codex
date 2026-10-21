"""Queries for tables, sessions, and their order history."""

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased, contains_eager, selectinload

from app.db.models import (
    CafeTable,
    Order,
    OrderEvent,
    OrderItem,
    Payment,
    Product,
    ProductTopping,
    ProductVariant,
    TableSession,
)


class TableRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_tables(self) -> list[CafeTable]:
        return list(
            self.db.scalars(
                select(CafeTable)
                .options(
                    selectinload(CafeTable.sessions).selectinload(TableSession.orders)
                )
                .order_by(CafeTable.table_number)
            ).all()
        )

    def table(self, table_id: int, *, lock: bool = False) -> CafeTable | None:
        query = select(CafeTable).where(CafeTable.id == table_id)
        if lock:
            query = query.with_for_update()
        return self.db.scalar(query)

    def active_session_for_table(self, table_id: int) -> TableSession | None:
        return self.db.scalar(
            select(TableSession).where(
                TableSession.table_id == table_id, TableSession.status == "open"
            )
        )

    def session(self, session_id: int, *, lock: bool = False) -> TableSession | None:
        query = (
            select(TableSession)
            .where(TableSession.id == session_id)
            .options(
                selectinload(TableSession.orders)
                .selectinload(Order.items)
                .selectinload(OrderItem.topping_snapshots),
                selectinload(TableSession.payments),
            )
        )
        if lock:
            query = query.with_for_update()
        return self.db.scalar(query)

    def order(self, order_id: int, *, lock: bool = False) -> Order | None:
        query = (
            select(Order)
            .where(Order.id == order_id, Order.session_id.is_not(None))
            .options(
                selectinload(Order.items).selectinload(OrderItem.topping_snapshots)
            )
        )
        if lock:
            query = query.with_for_update()
        return self.db.scalar(query)

    def variant(self, variant_id: int) -> ProductVariant | None:
        return self.db.scalar(
            select(ProductVariant)
            .join(ProductVariant.product)
            .where(ProductVariant.id == variant_id)
            .options(contains_eager(ProductVariant.product))
            .with_for_update(of=(ProductVariant, Product))
        )

    def default_variant(self, product_id: int) -> ProductVariant | None:
        other_variant = aliased(ProductVariant)
        return self.db.scalar(
            select(ProductVariant)
            .join(ProductVariant.product)
            .where(
                ProductVariant.product_id == product_id,
                ProductVariant.sku == f"AUTO-{product_id}",
                ~select(other_variant.id)
                .where(
                    other_variant.product_id == product_id,
                    other_variant.id != ProductVariant.id,
                    other_variant.is_active.is_(True),
                )
                .exists(),
            )
            .options(contains_eager(ProductVariant.product))
            .with_for_update(of=(ProductVariant, Product))
        )

    def item_request_fingerprint(self, order_id: int, key: str) -> str | None:
        note = self.db.scalar(
            select(OrderEvent.note).where(
                OrderEvent.order_id == order_id,
                OrderEvent.event_type == "item_added",
                OrderEvent.note.startswith(f"{key}:", autoescape=True),
            )
        )
        return note.rsplit(":", 1)[-1] if note else None

    def toppings(self, product_id: int, topping_ids: list[int]) -> list[ProductTopping]:
        if not topping_ids:
            return []
        return list(
            self.db.scalars(
                select(ProductTopping)
                .where(
                    ProductTopping.product_id == product_id,
                    ProductTopping.id.in_(topping_ids),
                )
                .order_by(ProductTopping.id)
                .with_for_update()
            ).all()
        )

    def payment_by_key(self, key: str) -> Payment | None:
        return self.db.scalar(select(Payment).where(Payment.idempotency_key == key))

    def payment_by_receipt(self, receipt_number: str) -> Payment | None:
        return self.db.scalar(
            select(Payment).where(Payment.receipt_number == receipt_number)
        )

    def session_payments(self, *, offset: int, limit: int) -> list[Payment]:
        return list(
            self.db.scalars(
                select(Payment)
                .where(
                    Payment.session_id.is_not(None),
                    Payment.status == "succeeded",
                )
                .order_by(Payment.paid_at.desc(), Payment.id.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        )
