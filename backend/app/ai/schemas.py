"""Validated API, model output, and tool argument schemas."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChatRequest(StrictModel):
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must not be blank")
        return value


class ManagementAnswer(StrictModel):
    answer: str
    highlights: list[str]
    recommendations: list[str]
    tools_used: list[str]


class ChatResponse(ManagementAnswer):
    request_id: str


class PeriodArguments(StrictModel):
    date_from: date | None
    date_to: date | None


class TopProductsArguments(PeriodArguments):
    limit: int = Field(ge=1, le=20)


class LowStockArguments(StrictModel):
    limit: int = Field(ge=1, le=50)


ToolName = Literal[
    "get_revenue_summary",
    "get_top_products",
    "get_low_stock_ingredients",
]
