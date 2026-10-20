"""Response schemas for revenue analytics."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class RevenueSummary(BaseModel):
    date_from: date
    date_to: date
    timezone: str
    total_revenue: Decimal = Field(decimal_places=2)
    valid_order_count: int
    average_order_value: Decimal = Field(decimal_places=2)
    refunded_amount: Decimal = Field(decimal_places=2)
    refunded_payment_count: int
    cash_revenue: Decimal = Field(decimal_places=2)
    bank_transfer_revenue: Decimal = Field(decimal_places=2)
    paid_session_count: int
    revenue_by_method: dict[str, Decimal]


class DailyRevenuePoint(BaseModel):
    date: date
    revenue: Decimal = Field(decimal_places=2)
    order_count: int


class DailyRevenueReport(BaseModel):
    date_from: date
    date_to: date
    timezone: str
    items: list[DailyRevenuePoint]


class TopProduct(BaseModel):
    product_name: str
    variant_name: str
    sku: str
    quantity_sold: int
    gross_item_sales: Decimal = Field(decimal_places=2)


class TopProductsReport(BaseModel):
    date_from: date
    date_to: date
    timezone: str
    items: list[TopProduct]
