"""Inventory request, response, and pagination schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Unit = Literal["g", "ml", "piece"]
Quantity = Annotated[Decimal, Field(max_digits=14, decimal_places=3)]
NonNegativeQuantity = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=3)]
PositiveQuantity = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=3)]


def clean_text(value: str) -> str:
    return " ".join(value.strip().split())


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IngredientCreate(StrictRequest):
    sku: Annotated[
        str, Field(min_length=1, max_length=64, pattern=r"^[A-Z0-9][A-Z0-9._-]*$")
    ]
    name: Annotated[str, Field(min_length=1, max_length=150)]
    unit: Unit
    low_stock_threshold: NonNegativeQuantity = Decimal("0")

    @field_validator("sku", mode="before")
    @classmethod
    def normalize_sku(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return clean_text(value)


class IngredientUpdate(StrictRequest):
    sku: Annotated[
        str | None,
        Field(min_length=1, max_length=64, pattern=r"^[A-Z0-9][A-Z0-9._-]*$"),
    ] = None
    name: Annotated[str | None, Field(min_length=1, max_length=150)] = None
    unit: Unit | None = None
    low_stock_threshold: NonNegativeQuantity | None = None
    is_active: bool | None = None

    @field_validator("sku", mode="before")
    @classmethod
    def normalize_sku(cls, value: str | None) -> str | None:
        return None if value is None else value.strip().upper()

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return None if value is None else clean_text(value)

    @model_validator(mode="after")
    def require_non_null_change(self) -> "IngredientUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Updated fields cannot be null")
        return self


class IngredientView(BaseModel):
    id: int
    sku: str
    name: str
    unit: Unit
    low_stock_threshold: Decimal
    current_stock: Decimal
    is_low_stock: bool
    is_active: bool


class IngredientPage(BaseModel):
    items: list[IngredientView]
    total: int
    page: int
    page_size: int
    pages: int


class RecipeUpsert(StrictRequest):
    quantity_required: PositiveQuantity


class RecipeView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    variant_id: int
    ingredient_id: int
    quantity_required: Decimal


class ManualMovementCreate(StrictRequest):
    ingredient_id: int = Field(gt=0)
    transaction_type: Literal["purchase", "waste", "adjustment"]
    quantity_delta: Quantity
    reason: Annotated[str, Field(min_length=3, max_length=255)]

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return clean_text(value)

    @model_validator(mode="after")
    def validate_direction(self) -> "ManualMovementCreate":
        if self.quantity_delta == 0:
            raise ValueError("quantity_delta must not be zero")
        if self.transaction_type == "purchase" and self.quantity_delta < 0:
            raise ValueError("purchase quantity_delta must be positive")
        if self.transaction_type == "waste" and self.quantity_delta > 0:
            raise ValueError("waste quantity_delta must be negative")
        return self


class InventoryTransactionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ingredient_id: int
    order_item_id: int | None
    actor_user_id: int | None
    reversal_of_id: int | None
    transaction_type: str
    quantity_delta: Decimal
    reason: str
    created_at: datetime


class InventoryTransactionPage(BaseModel):
    items: list[InventoryTransactionView]
    total: int
    page: int
    page_size: int
    pages: int
