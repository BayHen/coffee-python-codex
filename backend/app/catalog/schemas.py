"""Validated catalog request, response, and query models."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Name = Annotated[str, Field(min_length=1, max_length=150)]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


def normalize_text(value: str) -> str:
    return " ".join(value.strip().split())


class CategoryCreate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=100)]

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return normalize_text(value)


class CategoryUpdate(BaseModel):
    name: Annotated[str | None, Field(min_length=1, max_length=100)] = None

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return None if value is None else normalize_text(value)

    @model_validator(mode="after")
    def require_change(self) -> "CategoryUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        if self.name is None:
            raise ValueError("name cannot be null")
        return self


class CategoryView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class CategoryReassignDelete(BaseModel):
    replacement_category_id: int = Field(gt=0)


class CategoryDeletionOptions(BaseModel):
    category: CategoryView
    linked_product_count: int
    replacement_categories: list[CategoryView]
    preferred_replacement_category_id: int | None


class CategoryReassignDeleteResult(BaseModel):
    deleted_category_id: int
    replacement_category_id: int
    reassigned_product_count: int


class VariantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=100)]
    price: Money
    is_active: bool = True

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return normalize_text(value)


class VariantUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str | None, Field(min_length=1, max_length=100)] = None
    price: Money | None = None
    is_active: bool | None = None

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return None if value is None else normalize_text(value)

    @model_validator(mode="after")
    def require_change(self) -> "VariantUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Updated fields cannot be null")
        return self


class VariantView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    sku: str
    name: str
    price: Decimal
    is_active: bool


class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: int = Field(gt=0)
    name: Name
    base_price: Money = Decimal("0.00")
    is_active: bool = True

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return normalize_text(value)


class ProductUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: Annotated[int | None, Field(gt=0)] = None
    name: Name | None = None
    base_price: Money | None = None
    is_active: bool | None = None

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return None if value is None else normalize_text(value)

    @model_validator(mode="after")
    def require_change(self) -> "ProductUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Updated fields cannot be null")
        return self


class ProductView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    name: str
    base_price: Decimal
    is_active: bool
    category: CategoryView
    variants: list[VariantView]
    toppings: list["ToppingView"]


class ToppingCreate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=100)]
    price: Money
    is_active: bool = True

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return normalize_text(value)


class ToppingUpdate(BaseModel):
    name: Annotated[str | None, Field(min_length=1, max_length=100)] = None
    price: Money | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> "ToppingUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Updated fields cannot be null")
        return self


class ToppingView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    name: str
    price: Decimal
    is_active: bool


class CategoryPage(BaseModel):
    items: list[CategoryView]
    total: int
    page: int
    page_size: int
    pages: int


class ProductPage(BaseModel):
    items: list[ProductView]
    total: int
    page: int
    page_size: int
    pages: int


SortDirection = Literal["asc", "desc"]
CategorySort = Literal["id", "name"]
ProductSort = Literal["id", "name"]
