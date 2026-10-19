"""Validated order requests and API responses."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
DiscountPercent = Annotated[Decimal, Field(ge=0, le=20, max_digits=4, decimal_places=2)]
OrderStatus = Literal["draft", "placed", "paid", "cancelled"]


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrderItemInput(StrictRequest):
    variant_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=100)


class OrderCreate(StrictRequest):
    customer_id: Annotated[int | None, Field(gt=0)] = None
    items: Annotated[list[OrderItemInput], Field(min_length=1, max_length=50)]
    discount_percent: DiscountPercent = Decimal("0")
    discount_reason: Annotated[str | None, Field(min_length=3, max_length=255)] = None

    @field_validator("discount_reason", mode="before")
    @classmethod
    def clean_discount_reason(cls, value: str | None) -> str | None:
        return None if value is None else " ".join(value.strip().split())

    @model_validator(mode="after")
    def validate_order(self) -> "OrderCreate":
        variant_ids = [item.variant_id for item in self.items]
        if len(variant_ids) != len(set(variant_ids)):
            raise ValueError(
                "Each variant may appear only once; increase quantity instead"
            )
        if self.discount_percent > 0 and self.discount_reason is None:
            raise ValueError("discount_reason is required when a discount is applied")
        if self.discount_percent == 0 and self.discount_reason is not None:
            raise ValueError("discount_reason requires a positive discount_percent")
        return self


class OrderUpdate(StrictRequest):
    items: Annotated[list[OrderItemInput], Field(min_length=1, max_length=50)]
    discount_percent: DiscountPercent = Decimal("0")
    discount_reason: Annotated[str | None, Field(min_length=3, max_length=255)] = None

    @field_validator("discount_reason", mode="before")
    @classmethod
    def clean_discount_reason(cls, value: str | None) -> str | None:
        return None if value is None else " ".join(value.strip().split())

    @model_validator(mode="after")
    def validate_order(self) -> "OrderUpdate":
        variant_ids = [item.variant_id for item in self.items]
        if len(variant_ids) != len(set(variant_ids)):
            raise ValueError(
                "Each variant may appear only once; increase quantity instead"
            )
        if self.discount_percent > 0 and self.discount_reason is None:
            raise ValueError("discount_reason is required when a discount is applied")
        if self.discount_percent == 0 and self.discount_reason is not None:
            raise ValueError("discount_reason requires a positive discount_percent")
        return self


class OrderTransition(StrictRequest):
    target_status: Literal["placed", "cancelled"]
    reason: Annotated[str | None, Field(min_length=3, max_length=255)] = None

    @field_validator("reason", mode="before")
    @classmethod
    def clean_reason(cls, value: str | None) -> str | None:
        return None if value is None else " ".join(value.strip().split())

    @model_validator(mode="after")
    def require_cancel_reason(self) -> "OrderTransition":
        if self.target_status == "cancelled" and self.reason is None:
            raise ValueError("reason is required when cancelling an order")
        return self


class SimulatedPaymentCreate(StrictRequest):
    method: Literal["cash", "card_demo"]
    outcome: Literal["succeeded", "failed"] = "succeeded"


class OrderItemView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    variant_id: int
    product_name: str
    variant_name: str
    sku: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class OrderEventView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: int
    event_type: str
    from_status: str | None
    to_status: str
    note: str | None
    created_at: datetime


class PaymentView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    method: str
    status: str
    amount: Decimal
    provider_reference: str | None
    created_at: datetime


class OrderView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int | None
    employee_id: int | None
    status: OrderStatus
    subtotal_amount: Money
    discount_percent: Decimal
    discount_amount: Money
    total_amount: Money
    created_at: datetime
    items: list[OrderItemView]
    events: list[OrderEventView]
    payments: list[PaymentView]


class OrderPage(BaseModel):
    items: list[OrderView]
    total: int
    page: int
    page_size: int
    pages: int
