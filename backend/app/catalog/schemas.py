"""Validated catalog request, response, and query models."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Name = Annotated[str, Field(min_length=1, max_length=150)]
Sku = Annotated[
    str, Field(min_length=1, max_length=64, pattern=r"^[A-Z0-9][A-Z0-9._-]*$")
]
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


class VariantCreate(BaseModel):
    sku: Sku
    name: Annotated[str, Field(min_length=1, max_length=100)]
    price: Money
    is_active: bool = True

    @field_validator("sku", mode="before")
    @classmethod
    def normalize_sku(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return normalize_text(value)


class VariantUpdate(BaseModel):
    sku: Sku | None = None
    name: Annotated[str | None, Field(min_length=1, max_length=100)] = None
    price: Money | None = None
    is_active: bool | None = None

    @field_validator("sku", mode="before")
    @classmethod
    def normalize_sku(cls, value: str | None) -> str | None:
        return None if value is None else value.strip().upper()

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
    category_id: int = Field(gt=0)
    name: Name
    is_active: bool = True

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return normalize_text(value)


class ProductUpdate(BaseModel):
    category_id: Annotated[int | None, Field(gt=0)] = None
    name: Name | None = None
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
    is_active: bool
    category: CategoryView
    variants: list[VariantView]


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
