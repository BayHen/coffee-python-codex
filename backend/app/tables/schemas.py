"""Request and response contracts for table service."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TableCreate(StrictRequest):
    table_number: Annotated[str, Field(min_length=1, max_length=20)]
    name: Annotated[str, Field(min_length=1, max_length=100)]

    @field_validator("table_number", "name")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return " ".join(value.strip().split())


class TableUpdate(StrictRequest):
    table_number: Annotated[str | None, Field(min_length=1, max_length=20)] = None
    name: Annotated[str | None, Field(min_length=1, max_length=100)] = None
    is_active: bool | None = None

    @field_validator("table_number", "name")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return None if value is None else " ".join(value.strip().split())


class OrderCreate(StrictRequest):
    order_type: Literal["additional"]


class ItemCreate(StrictRequest):
    variant_id: int = Field(gt=0)
    topping_ids: list[int] = Field(default_factory=list, max_length=20)
    quantity: int = Field(gt=0, le=100)


class ItemUpdate(StrictRequest):
    quantity: int = Field(gt=0, le=100)


class CheckoutCreate(StrictRequest):
    method: Literal["cash", "bank_transfer"]
    cash_received: Money | None = None
    transfer_confirmed: bool = False
    transfer_reference: Annotated[str | None, Field(max_length=128)] = None

    @model_validator(mode="after")
    def validate_method_fields(self) -> "CheckoutCreate":
        if self.method == "cash" and self.cash_received is None:
            raise ValueError("cash_received is required for cash payments")
        if self.method == "bank_transfer" and not self.transfer_confirmed:
            raise ValueError("transfer_confirmed is required after verifying receipt")
        return self


class ItemView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    variant_id: int
    product_name: str
    variant_name: str
    sku: str
    quantity: int
    unit_price: Money
    line_total: Money
    topping_snapshots: list["ItemToppingView"]


class ItemToppingView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    price: Money


class SessionOrderView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    session_id: int
    order_type: Literal["initial", "additional"]
    sequence_number: int
    status: Literal["draft", "confirmed", "cancelled"]
    subtotal_amount: Money
    total_amount: Money
    confirmed_by: int | None
    confirmed_at: datetime | None
    created_at: datetime
    items: list[ItemView]


class BillView(BaseModel):
    confirmed_subtotal: Money
    draft_subtotal: Money
    payable_total: Money


class SessionView(BaseModel):
    id: int
    table_id: int
    status: Literal["open", "paid", "cancelled"]
    opened_at: datetime
    closed_at: datetime | None
    opened_by: int
    orders: list[SessionOrderView]
    bill: BillView


class TableView(BaseModel):
    id: int
    table_number: str
    name: str
    is_active: bool
    status: Literal["available", "occupied"]
    current_bill_total: Money
    active_session_id: int | None


class PaymentView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    session_id: int
    method: str
    status: str
    amount: Money
    provider_reference: str | None
    receipt_number: str
    cashier_id: int
    paid_at: datetime
    cash_received: Money | None
    change_amount: Money | None
    transfer_reference: str | None
    created_at: datetime


class BankTransferView(BaseModel):
    available: bool
    bank_name: str | None
    bank_id: str | None
    account_number: str | None
    account_holder: str | None
    payment_reference: str
    qr_image_url: str | None


class ReceiptView(BaseModel):
    receipt_number: str
    table_number: str
    session: SessionView
    payment: PaymentView
