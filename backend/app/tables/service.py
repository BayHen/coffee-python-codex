"""Transactional table-session order workflow."""

import hashlib
import os
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import quote
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    CafeTable,
    Order,
    OrderEvent,
    OrderItem,
    OrderItemTopping,
    Payment,
    TableSession,
)
from app.inventory.service import InventoryService
from app.orders.service import api_error
from app.tables.repository import TableRepository
from app.tables.schemas import BillView, CheckoutCreate, TableCreate, TableUpdate

ZERO = Decimal("0.00")


class TableService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = TableRepository(db)

    @staticmethod
    def bill(session: TableSession) -> BillView:
        confirmed = sum(
            (
                order.total_amount
                for order in session.orders
                if order.status == "confirmed"
            ),
            ZERO,
        )
        draft = sum(
            (order.total_amount for order in session.orders if order.status == "draft"),
            ZERO,
        )
        return BillView(
            confirmed_subtotal=confirmed,
            draft_subtotal=draft,
            payable_total=confirmed,
        )

    @staticmethod
    def calculate_change(total: Decimal, cash_received: Decimal) -> Decimal:
        if cash_received < total:
            raise api_error(
                422,
                "insufficient_cash",
                "Cash received is less than the payable total",
            )
        return (cash_received - total).quantize(Decimal("0.01"))

    def table_view(self, table: CafeTable) -> dict[str, object]:
        active = next((item for item in table.sessions if item.status == "open"), None)
        total = (
            sum(
                (o.total_amount for o in active.orders if o.status == "confirmed"),
                ZERO,
            )
            if active
            else ZERO
        )
        return {
            "id": table.id,
            "table_number": table.table_number,
            "name": table.name,
            "is_active": table.is_active,
            "status": "occupied" if active else "available",
            "current_bill_total": total,
            "active_session_id": active.id if active else None,
        }

    def session_view(self, session: TableSession) -> dict[str, object]:
        return {
            "id": session.id,
            "table_id": session.table_id,
            "status": session.status,
            "opened_at": session.opened_at,
            "closed_at": session.closed_at,
            "opened_by": session.opened_by,
            "orders": session.orders,
            "bill": self.bill(session),
        }

    def list_tables(self) -> list[dict[str, object]]:
        return [self.table_view(table) for table in self.repo.list_tables()]

    def get_table(self, table_id: int) -> dict[str, object]:
        tables = [table for table in self.repo.list_tables() if table.id == table_id]
        if not tables:
            raise api_error(404, "table_not_found", "Table not found")
        return self.table_view(tables[0])

    def create_table(self, payload: TableCreate) -> dict[str, object]:
        try:
            with self.db.begin():
                table = CafeTable(**payload.model_dump())
                self.db.add(table)
                self.db.flush()
                table_id = table.id
        except IntegrityError as exc:
            raise api_error(
                409, "table_number_exists", "Table number already exists"
            ) from exc
        return self.get_table(table_id)

    def update_table(self, table_id: int, payload: TableUpdate) -> dict[str, object]:
        try:
            with self.db.begin():
                table = self.repo.table(table_id, lock=True)
                if table is None:
                    raise api_error(404, "table_not_found", "Table not found")
                active = self.repo.active_session_for_table(table_id)
                if payload.is_active is False and active is not None:
                    raise api_error(
                        409, "table_occupied", "An occupied table cannot be disabled"
                    )
                for key, value in payload.model_dump(exclude_unset=True).items():
                    setattr(table, key, value)
        except IntegrityError as exc:
            raise api_error(
                409, "table_number_exists", "Table number already exists"
            ) from exc
        return self.get_table(table_id)

    def open_session(self, table_id: int, actor_id: int) -> dict[str, object]:
        try:
            with self.db.begin():
                table = self.repo.table(table_id, lock=True)
                if table is None:
                    raise api_error(404, "table_not_found", "Table not found")
                if not table.is_active:
                    raise api_error(
                        409, "table_disabled", "Disabled table cannot be opened"
                    )
                if self.repo.active_session_for_table(table_id):
                    raise api_error(
                        409, "session_exists", "Table already has an open session"
                    )
                session = TableSession(
                    table_id=table_id, opened_by=actor_id, status="open"
                )
                self.db.add(session)
                self.db.flush()
                order = self._new_order(session.id, "initial", 1, actor_id)
                self.db.add(order)
                self.db.flush()
                session_id = session.id
        except IntegrityError as exc:
            raise api_error(
                409, "session_conflict", "An open session already exists"
            ) from exc
        return self.get_session(session_id)

    @staticmethod
    def _new_order(
        session_id: int, order_type: str, sequence: int, actor_id: int
    ) -> Order:
        key = f"session-order:{session_id}:{sequence}"
        return Order(
            session_id=session_id,
            order_type=order_type,
            sequence_number=sequence,
            created_by=actor_id,
            idempotency_key=key,
            request_fingerprint=hashlib.sha256(key.encode()).hexdigest(),
            status="draft",
            subtotal_amount=ZERO,
            discount_percent=ZERO,
            discount_amount=ZERO,
            total_amount=ZERO,
            events=[
                OrderEvent(
                    actor_user_id=actor_id,
                    event_type="created",
                    from_status=None,
                    to_status="draft",
                )
            ],
        )

    def active_session(self, table_id: int) -> dict[str, object]:
        session = self.repo.active_session_for_table(table_id)
        if session is None:
            raise api_error(
                404, "active_session_not_found", "Table has no open session"
            )
        return self.get_session(session.id)

    def get_session(self, session_id: int) -> dict[str, object]:
        session = self.repo.session(session_id)
        if session is None:
            raise api_error(404, "session_not_found", "Session not found")
        return self.session_view(session)

    def create_additional_order(
        self, session_id: int, actor_id: int
    ) -> dict[str, object]:
        try:
            with self.db.begin():
                session = self.repo.session(session_id, lock=True)
                if session is None:
                    raise api_error(404, "session_not_found", "Session not found")
                if session.status != "open":
                    raise api_error(409, "session_closed", "Session is not open")
                if not any(
                    o.order_type == "initial" and o.status == "confirmed"
                    for o in session.orders
                ):
                    raise api_error(
                        409, "initial_not_confirmed", "Confirm the initial order first"
                    )
                if any(
                    o.order_type == "additional" and o.status == "draft"
                    for o in session.orders
                ):
                    raise api_error(
                        409,
                        "additional_draft_exists",
                        "Finish the current additional draft",
                    )
                sequence = (
                    max((o.sequence_number or 0 for o in session.orders), default=0) + 1
                )
                order = self._new_order(session.id, "additional", sequence, actor_id)
                self.db.add(order)
                self.db.flush()
                order_id = order.id
        except IntegrityError as exc:
            raise api_error(
                409, "order_conflict", "Additional draft already exists"
            ) from exc
        return self.order_view(order_id)

    def order_view(self, order_id: int) -> Order:
        order = self.repo.order(order_id)
        if order is None:
            raise api_error(404, "order_not_found", "Session order not found")
        return order

    @staticmethod
    def _require_editable(order: Order, session: TableSession | None) -> None:
        if session is None or session.status != "open":
            raise api_error(409, "session_closed", "Session is not open")
        if order.status != "draft":
            raise api_error(
                409, "order_not_editable", "Only draft orders can be edited"
            )

    def add_item(
        self,
        order_id: int,
        product_id: int | None,
        variant_id: int | None,
        topping_ids: list[int],
        quantity: int,
        idempotency_key: str | None,
        actor_id: int,
    ) -> Order:
        with self.db.begin():
            order = self.repo.order(order_id, lock=True)
            if order is None:
                raise api_error(404, "order_not_found", "Session order not found")
            fingerprint = hashlib.sha256(
                (
                    f"{product_id}:{variant_id}:"
                    f"{','.join(str(item) for item in sorted(topping_ids))}:{quantity}"
                ).encode()
            ).hexdigest()
            if idempotency_key:
                existing_fingerprint = self.repo.item_request_fingerprint(
                    order_id, idempotency_key
                )
                if existing_fingerprint:
                    if existing_fingerprint != fingerprint:
                        raise api_error(
                            409,
                            "idempotency_key_reused",
                            "Key was used for another item configuration",
                        )
                    return order
            session = self.repo.session(order.session_id, lock=True)
            self._require_editable(order, session)
            variant = (
                self.repo.variant(variant_id)
                if variant_id is not None
                else self.repo.default_variant(product_id or 0)
            )
            if variant is None:
                raise api_error(
                    422,
                    "size_required",
                    "Select an available size for this product",
                )
            if product_id is not None and variant.product_id != product_id:
                raise api_error(
                    422,
                    "variant_product_mismatch",
                    "Selected size does not belong to this product",
                )
            if not variant.is_active or not variant.product.is_active:
                raise api_error(
                    409, "variant_unavailable", "Product variant is unavailable"
                )
            unique_topping_ids = sorted(set(topping_ids))
            if len(unique_topping_ids) != len(topping_ids):
                raise api_error(
                    422, "duplicate_topping", "Each topping may appear once"
                )
            toppings = self.repo.toppings(variant.product_id, unique_topping_ids)
            if len(toppings) != len(unique_topping_ids):
                raise api_error(
                    404, "topping_not_found", "One or more toppings are invalid"
                )
            if any(not topping.is_active for topping in toppings):
                raise api_error(409, "topping_unavailable", "A topping is unavailable")
            item = next(
                (
                    item
                    for item in order.items
                    if item.variant_id == variant.id
                    and sorted(
                        snapshot.topping_id for snapshot in item.topping_snapshots
                    )
                    == unique_topping_ids
                ),
                None,
            )
            if item:
                if item.quantity + quantity > 100:
                    raise api_error(
                        422, "quantity_invalid", "Quantity cannot exceed 100"
                    )
                item.quantity += quantity
                item.line_total = item.unit_price * item.quantity
            else:
                price = (
                    variant.product.base_price
                    + variant.price
                    + sum((topping.price for topping in toppings), ZERO)
                ).quantize(Decimal("0.01"))
                order.items.append(
                    OrderItem(
                        variant_id=variant.id,
                        product_name=variant.product.name,
                        variant_name=variant.name,
                        sku=variant.sku,
                        quantity=quantity,
                        unit_price=price,
                        line_total=price * quantity,
                        topping_snapshots=[
                            OrderItemTopping(
                                topping_id=topping.id,
                                name=topping.name,
                                price=topping.price,
                            )
                            for topping in toppings
                        ],
                    )
                )
            self._recalculate(order)
            if idempotency_key:
                order.events.append(
                    OrderEvent(
                        actor_user_id=actor_id,
                        event_type="item_added",
                        from_status="draft",
                        to_status="draft",
                        note=f"{idempotency_key}:{fingerprint}",
                    )
                )
        return self.order_view(order_id)

    def update_item(self, order_id: int, item_id: int, quantity: int) -> Order:
        with self.db.begin():
            order = self.repo.order(order_id, lock=True)
            if order is None:
                raise api_error(404, "order_not_found", "Session order not found")
            self._require_editable(
                order, self.repo.session(order.session_id, lock=True)
            )
            item = next((line for line in order.items if line.id == item_id), None)
            if item is None:
                raise api_error(404, "item_not_found", "Order item not found")
            item.quantity = quantity
            item.line_total = item.unit_price * quantity
            self._recalculate(order)
        return self.order_view(order_id)

    def delete_item(self, order_id: int, item_id: int) -> None:
        with self.db.begin():
            order = self.repo.order(order_id, lock=True)
            if order is None:
                raise api_error(404, "order_not_found", "Session order not found")
            self._require_editable(
                order, self.repo.session(order.session_id, lock=True)
            )
            item = next((line for line in order.items if line.id == item_id), None)
            if item is None:
                raise api_error(404, "item_not_found", "Order item not found")
            self.db.delete(item)
            order.items.remove(item)
            self._recalculate(order)

    @staticmethod
    def _recalculate(order: Order) -> None:
        total = sum((item.line_total for item in order.items), ZERO)
        order.subtotal_amount = total
        order.total_amount = total

    def confirm(self, order_id: int, actor_id: int) -> Order:
        with self.db.begin():
            order = self.repo.order(order_id, lock=True)
            if order is None:
                raise api_error(404, "order_not_found", "Session order not found")
            self._require_editable(
                order, self.repo.session(order.session_id, lock=True)
            )
            if not order.items:
                raise api_error(
                    409, "empty_order", "An empty order cannot be confirmed"
                )
            InventoryService(self.db).consume_for_order(order, actor_id)
            order.status = "confirmed"
            order.confirmed_by = actor_id
            order.confirmed_at = datetime.now(UTC)
            order.events.append(
                OrderEvent(
                    actor_user_id=actor_id,
                    event_type="confirmed",
                    from_status="draft",
                    to_status="confirmed",
                )
            )
        return self.order_view(order_id)

    def bank_transfer(self, session_id: int) -> dict[str, object]:
        session = self.repo.session(session_id)
        if session is None:
            raise api_error(404, "session_not_found", "Session not found")
        if session.status != "open":
            raise api_error(409, "session_closed", "Session is not open")
        bank_id = os.environ.get("PAYMENT_BANK_ID", "").strip()
        account = os.environ.get("PAYMENT_BANK_ACCOUNT", "").strip()
        holder = os.environ.get("PAYMENT_BANK_HOLDER", "").strip()
        bank_name = os.environ.get("PAYMENT_BANK_NAME", "").strip()
        reference = f"COFFEE S{session.id}"
        available = all((bank_id, account, holder, bank_name))
        total = self.bill(session).payable_total
        qr_url = None
        if available and total > ZERO:
            qr_url = (
                f"https://img.vietqr.io/image/{quote(bank_id)}-"
                f"{quote(account)}-compact2.png?amount={int(total)}"
                f"&addInfo={quote(reference)}&accountName={quote(holder)}"
            )
        return {
            "available": available,
            "bank_name": bank_name or None,
            "bank_id": bank_id or None,
            "account_number": account or None,
            "account_holder": holder or None,
            "payment_reference": reference,
            "qr_image_url": qr_url,
        }

    def checkout(
        self,
        session_id: int,
        payload: CheckoutCreate,
        key: str,
        actor_id: int,
    ) -> Payment:
        fingerprint = hashlib.sha256(
            f"{session_id}:{payload.model_dump_json()}".encode()
        ).hexdigest()
        try:
            with self.db.begin():
                existing = self.repo.payment_by_key(key)
                if existing:
                    if existing.request_fingerprint != fingerprint:
                        raise api_error(
                            409,
                            "idempotency_key_reused",
                            "Key was used for another checkout",
                        )
                    return existing
                session = self.repo.session(session_id, lock=True)
                if session is None:
                    raise api_error(404, "session_not_found", "Session not found")
                if session.status != "open":
                    raise api_error(409, "session_closed", "Session is not open")
                if any(o.status == "draft" and o.items for o in session.orders):
                    raise api_error(
                        409,
                        "draft_orders_exist",
                        "Resolve draft orders before checkout",
                    )
                total = self.bill(session).payable_total
                if total <= ZERO:
                    raise api_error(409, "nothing_to_pay", "No confirmed orders to pay")
                cash_received = payload.cash_received
                change_amount = (
                    self.calculate_change(total, cash_received)
                    if cash_received is not None
                    else None
                )
                if payload.method == "bank_transfer":
                    bank = self.bank_transfer(session_id)
                    if not bank["available"]:
                        raise api_error(
                            409,
                            "bank_transfer_unavailable",
                            "Bank transfer is not configured",
                        )
                paid_at = datetime.now(UTC)
                payment = Payment(
                    session_id=session.id,
                    idempotency_key=key,
                    request_fingerprint=fingerprint,
                    provider_reference=f"session_{uuid4().hex}",
                    method=payload.method,
                    status="succeeded",
                    amount=total,
                    receipt_number=f"RCP-{paid_at:%Y%m%d}-{uuid4().hex[:12].upper()}",
                    cashier_id=actor_id,
                    paid_at=paid_at,
                    cash_received=cash_received,
                    change_amount=change_amount,
                    transfer_reference=(
                        payload.transfer_reference or f"COFFEE S{session.id}"
                        if payload.method == "bank_transfer"
                        else None
                    ),
                )
                self.db.add(payment)
                session.status = "paid"
                session.closed_at = paid_at
                session.paid_at = paid_at
                self.db.flush()
                return payment
        except IntegrityError as exc:
            with self.db.begin():
                existing = self.repo.payment_by_key(key)
                if existing and existing.request_fingerprint == fingerprint:
                    return existing
            raise api_error(
                409, "payment_conflict", "Checkout was already recorded"
            ) from exc

    def receipt_view(self, payment: Payment) -> dict[str, object]:
        if payment.session_id is None or payment.receipt_number is None:
            raise api_error(404, "receipt_not_found", "Receipt not found")
        session = self.repo.session(payment.session_id)
        if session is None:
            raise api_error(404, "session_not_found", "Session not found")
        table = self.repo.table(session.table_id)
        if table is None:
            raise api_error(404, "table_not_found", "Table not found")
        return {
            "receipt_number": payment.receipt_number,
            "table_number": table.table_number,
            "session": self.session_view(session),
            "payment": payment,
        }

    def get_receipt(self, receipt_number: str) -> dict[str, object]:
        payment = self.repo.payment_by_receipt(receipt_number)
        if payment is None or payment.status != "succeeded":
            raise api_error(404, "receipt_not_found", "Receipt not found")
        return self.receipt_view(payment)

    def list_receipts(self, page: int, page_size: int) -> list[dict[str, object]]:
        return [
            self.receipt_view(payment)
            for payment in self.repo.session_payments(
                offset=(page - 1) * page_size, limit=page_size
            )
        ]
