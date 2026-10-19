"""Order totals, workflow, transaction, and idempotency rules."""

import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Order, OrderEvent, OrderItem, Payment
from app.inventory.service import InventoryService
from app.orders.repository import OrderRepository
from app.orders.schemas import (
    OrderCreate,
    OrderItemInput,
    OrderPage,
    OrderTransition,
    OrderUpdate,
    SimulatedPaymentCreate,
)

CENT = Decimal("0.01")
ALLOWED_TRANSITIONS = {
    "draft": {"placed", "cancelled"},
    "placed": {"paid", "cancelled"},
    "paid": set(),
    "cancelled": set(),
}


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code, detail={"code": code, "message": message}
    )


def request_fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def order_fingerprint(payload: OrderCreate) -> str:
    return request_fingerprint(
        {
            "customer_id": payload.customer_id,
            "discount_percent": str(payload.discount_percent.quantize(CENT)),
            "discount_reason": payload.discount_reason,
            "items": sorted(
                (
                    {"variant_id": item.variant_id, "quantity": item.quantity}
                    for item in payload.items
                ),
                key=lambda item: item["variant_id"],
            ),
        }
    )


def payment_fingerprint(order_id: int, payload: SimulatedPaymentCreate) -> str:
    return request_fingerprint(
        {"order_id": order_id, "method": payload.method, "outcome": payload.outcome}
    )


class OrderService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = OrderRepository(db)

    def list_orders(self, status: str | None, page: int, page_size: int) -> OrderPage:
        items, total = self.repository.list_orders(
            status=status, offset=(page - 1) * page_size, limit=page_size
        )
        return OrderPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    def get_order(self, order_id: int) -> Order:
        order = self.repository.get_order(order_id)
        if order is None:
            raise api_error(404, "order_not_found", "Order not found")
        return order

    def _validate_existing_order(self, order: Order, fingerprint: str) -> Order:
        if order.request_fingerprint != fingerprint:
            raise api_error(
                409,
                "idempotency_key_reused",
                "Idempotency-Key was already used for a different request",
            )
        return order

    def _priced_items(
        self, inputs: list[OrderItemInput]
    ) -> tuple[list[OrderItem], Decimal]:
        requested = {item.variant_id: item.quantity for item in inputs}
        variants = self.repository.lock_variants(sorted(requested))
        found = {variant.id for variant in variants}
        missing = set(requested) - found
        if missing:
            raise api_error(
                404, "variant_not_found", "One or more variants do not exist"
            )

        items = []
        subtotal = Decimal("0.00")
        for variant in variants:
            if not variant.is_active or not variant.product.is_active:
                raise api_error(
                    409,
                    "variant_unavailable",
                    f"Variant {variant.sku} is not available",
                )
            quantity = requested[variant.id]
            unit_price = variant.price.quantize(CENT)
            line_total = (unit_price * quantity).quantize(CENT)
            subtotal += line_total
            items.append(
                OrderItem(
                    variant_id=variant.id,
                    product_name=variant.product.name,
                    variant_name=variant.name,
                    sku=variant.sku,
                    quantity=quantity,
                    unit_price=unit_price,
                    line_total=line_total,
                )
            )
        if subtotal <= 0:
            raise api_error(
                422, "order_total_invalid", "Order subtotal must be positive"
            )
        return items, subtotal.quantize(CENT)

    @staticmethod
    def _totals(
        subtotal: Decimal, discount_percent: Decimal
    ) -> tuple[Decimal, Decimal]:
        discount = (subtotal * discount_percent / Decimal("100")).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        return discount, (subtotal - discount).quantize(CENT)

    def create_order(
        self, payload: OrderCreate, idempotency_key: str, actor_user_id: int
    ) -> Order:
        fingerprint = order_fingerprint(payload)
        try:
            with self.db.begin():
                existing = self.repository.get_order_by_key(idempotency_key)
                if existing is not None:
                    return self._validate_existing_order(existing, fingerprint)
                if (
                    payload.customer_id is not None
                    and not self.repository.customer_exists(payload.customer_id)
                ):
                    raise api_error(404, "customer_not_found", "Customer not found")
                items, subtotal = self._priced_items(payload.items)
                existing = self.repository.get_order_by_key(idempotency_key)
                if existing is not None:
                    return self._validate_existing_order(existing, fingerprint)
                discount, total = self._totals(subtotal, payload.discount_percent)
                order = Order(
                    customer_id=payload.customer_id,
                    employee_id=self.repository.employee_id_for_user(actor_user_id),
                    idempotency_key=idempotency_key,
                    request_fingerprint=fingerprint,
                    status="draft",
                    subtotal_amount=subtotal,
                    discount_percent=payload.discount_percent,
                    discount_amount=discount,
                    total_amount=total,
                    items=items,
                )
                order.events.append(
                    OrderEvent(
                        actor_user_id=actor_user_id,
                        event_type="created",
                        from_status=None,
                        to_status="draft",
                        note=payload.discount_reason,
                    )
                )
                self.db.add(order)
                self.db.flush()
                order_id = order.id
            return self.get_order(order_id)
        except IntegrityError as exc:
            with self.db.begin():
                existing = self.repository.get_order_by_key(idempotency_key)
                if existing is not None:
                    return self._validate_existing_order(existing, fingerprint)
            raise api_error(
                409, "order_conflict", "Order could not be created"
            ) from exc

    def update_order(
        self, order_id: int, payload: OrderUpdate, actor_user_id: int
    ) -> Order:
        with self.db.begin():
            order = self.repository.get_order(order_id, lock=True)
            if order is None:
                raise api_error(404, "order_not_found", "Order not found")
            if order.status != "draft":
                raise api_error(
                    409, "order_not_editable", "Only draft orders can be edited"
                )
            items, subtotal = self._priced_items(payload.items)
            discount, total = self._totals(subtotal, payload.discount_percent)
            for item in list(order.items):
                self.db.delete(item)
            order.items = items
            order.subtotal_amount = subtotal
            order.discount_percent = payload.discount_percent
            order.discount_amount = discount
            order.total_amount = total
            order.events.append(
                OrderEvent(
                    actor_user_id=actor_user_id,
                    event_type="updated",
                    from_status="draft",
                    to_status="draft",
                    note=payload.discount_reason,
                )
            )
            self.db.flush()
        return self.get_order(order_id)

    def transition_order(
        self, order_id: int, payload: OrderTransition, actor_user_id: int
    ) -> Order:
        with self.db.begin():
            order = self.repository.get_order(order_id, lock=True)
            if order is None:
                raise api_error(404, "order_not_found", "Order not found")
            if payload.target_status not in ALLOWED_TRANSITIONS[order.status]:
                raise api_error(
                    409,
                    "invalid_order_transition",
                    f"Cannot transition from {order.status} to {payload.target_status}",
                )
            previous = order.status
            inventory = InventoryService(self.db)
            if previous == "draft" and payload.target_status == "placed":
                inventory.consume_for_order(order, actor_user_id)
            elif previous == "placed" and payload.target_status == "cancelled":
                inventory.return_for_cancelled_order(order, actor_user_id)
            order.status = payload.target_status
            order.events.append(
                OrderEvent(
                    actor_user_id=actor_user_id,
                    event_type="status_changed",
                    from_status=previous,
                    to_status=payload.target_status,
                    note=payload.reason,
                )
            )
        return self.get_order(order_id)

    def simulate_payment(
        self,
        order_id: int,
        payload: SimulatedPaymentCreate,
        idempotency_key: str,
        actor_user_id: int,
    ) -> Payment:
        fingerprint = payment_fingerprint(order_id, payload)
        try:
            with self.db.begin():
                existing = self.repository.get_payment_by_key(idempotency_key)
                if existing is not None:
                    return self._validate_existing_payment(existing, fingerprint)
                order = self.repository.get_order(order_id, lock=True)
                if order is None:
                    raise api_error(404, "order_not_found", "Order not found")
                existing = self.repository.get_payment_by_key(idempotency_key)
                if existing is not None:
                    return self._validate_existing_payment(existing, fingerprint)
                if order.status != "placed":
                    raise api_error(
                        409,
                        "order_not_payable",
                        "Only placed orders can be paid",
                    )
                payment = Payment(
                    order_id=order.id,
                    idempotency_key=idempotency_key,
                    request_fingerprint=fingerprint,
                    provider_reference=f"sim_{uuid4().hex}",
                    method=payload.method,
                    status=payload.outcome,
                    amount=order.total_amount,
                )
                self.db.add(payment)
                if payload.outcome == "succeeded":
                    order.status = "paid"
                    event_type = "payment_succeeded"
                    to_status = "paid"
                else:
                    event_type = "payment_failed"
                    to_status = "placed"
                order.events.append(
                    OrderEvent(
                        actor_user_id=actor_user_id,
                        event_type=event_type,
                        from_status="placed",
                        to_status=to_status,
                        note=payload.method,
                    )
                )
                self.db.flush()
            return payment
        except IntegrityError as exc:
            with self.db.begin():
                existing = self.repository.get_payment_by_key(idempotency_key)
                if existing is not None:
                    return self._validate_existing_payment(existing, fingerprint)
            raise api_error(
                409, "payment_conflict", "A successful payment already exists"
            ) from exc

    @staticmethod
    def _validate_existing_payment(payment: Payment, fingerprint: str) -> Payment:
        if payment.request_fingerprint != fingerprint:
            raise api_error(
                409,
                "idempotency_key_reused",
                "Idempotency-Key was already used for a different payment request",
            )
        return payment
