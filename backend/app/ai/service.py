"""Bounded, read-only tool orchestration for the management assistant."""

import json
import logging
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway, OpenAIResponsesGateway, ToolCall
from app.ai.schemas import (
    ChatResponse,
    LowStockArguments,
    ManagementAnswer,
    PeriodArguments,
    TopProductsArguments,
)
from app.auth.dependencies import Principal
from app.inventory.service import InventoryService
from app.reporting.service import DEFAULT_TIMEZONE, ReportingService, resolve_period

logger = logging.getLogger(__name__)
MAX_TOOL_ROUNDS = 3
MAX_TOOL_CALLS = 6
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW_SECONDS = 60


def ai_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


class UserRateLimiter:
    """Small per-process guard; use a shared limiter when the API is scaled out."""

    def __init__(self) -> None:
        self._requests: dict[int, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, user_id: int) -> None:
        now = time.monotonic()
        with self._lock:
            requests = self._requests[user_id]
            while requests and requests[0] <= now - RATE_LIMIT_WINDOW_SECONDS:
                requests.popleft()
            if len(requests) >= RATE_LIMIT_REQUESTS:
                raise ai_error(
                    429, "ai_rate_limit", "Too many AI requests; try again soon"
                )
            requests.append(now)


rate_limiter = UserRateLimiter()


class ReadOnlyToolExecutor:
    def __init__(self, db: Session, principal: Principal) -> None:
        self.db = db
        self.principal = principal

    def execute(self, call: ToolCall) -> str:
        if self.principal.role not in {"Admin", "Manager"}:
            raise ai_error(
                403, "tool_forbidden", "This tool requires management access"
            )
        handlers: dict[str, Callable[[str], str]] = {
            "get_revenue_summary": self._revenue_summary,
            "get_top_products": self._top_products,
            "get_low_stock_ingredients": self._low_stock,
        }
        handler = handlers.get(call.name)
        if handler is None:
            raise ai_error(
                400, "unknown_ai_tool", "The requested AI tool is not allowed"
            )
        return handler(call.arguments)

    @staticmethod
    def _arguments(raw: str) -> dict[str, Any]:
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ai_error(
                422, "invalid_tool_arguments", "Tool arguments are invalid"
            ) from exc
        if not isinstance(value, dict):
            raise ai_error(
                422, "invalid_tool_arguments", "Tool arguments must be an object"
            )
        return value

    def _revenue_summary(self, raw: str) -> str:
        try:
            arguments = PeriodArguments.model_validate(self._arguments(raw))
        except ValidationError as exc:
            raise ai_error(
                422, "invalid_tool_arguments", "Invalid report period"
            ) from exc
        period = resolve_period(
            arguments.date_from, arguments.date_to, DEFAULT_TIMEZONE
        )
        return ReportingService(self.db).summary(period).model_dump_json()

    def _top_products(self, raw: str) -> str:
        try:
            arguments = TopProductsArguments.model_validate(self._arguments(raw))
        except ValidationError as exc:
            raise ai_error(
                422, "invalid_tool_arguments", "Invalid top-product query"
            ) from exc
        period = resolve_period(
            arguments.date_from, arguments.date_to, DEFAULT_TIMEZONE
        )
        return (
            ReportingService(self.db)
            .top_products(period, arguments.limit)
            .model_dump_json()
        )

    def _low_stock(self, raw: str) -> str:
        try:
            arguments = LowStockArguments.model_validate(self._arguments(raw))
        except ValidationError as exc:
            raise ai_error(
                422, "invalid_tool_arguments", "Invalid stock query"
            ) from exc
        result = InventoryService(self.db).list_ingredients(
            search=None,
            active_only=True,
            low_stock_only=True,
            page=1,
            page_size=arguments.limit,
        )
        return result.model_dump_json()


class AIManagementService:
    def __init__(
        self,
        db: Session,
        principal: Principal,
        gateway: AIGateway | None = None,
    ) -> None:
        self.principal = principal
        self.gateway = gateway
        self.tools = ReadOnlyToolExecutor(db, principal)

    def chat(self, message: str) -> ChatResponse:
        request_id = str(uuid4())
        rate_limiter.check(self.principal.user_id)
        input_items: list[Any] = [{"role": "user", "content": message}]
        tools_used: list[str] = []
        total_calls = 0
        try:
            gateway = self.gateway or OpenAIResponsesGateway()
            for _round in range(MAX_TOOL_ROUNDS + 1):
                response = gateway.complete(input_items)
                logger.info(
                    "ai_response request_id=%s user_id=%s "
                    "input_tokens=%s output_tokens=%s",
                    request_id,
                    self.principal.user_id,
                    response.input_tokens,
                    response.output_tokens,
                )
                if not response.tool_calls:
                    try:
                        answer = ManagementAnswer.model_validate_json(
                            response.output_text
                        )
                    except ValidationError as exc:
                        raise ai_error(
                            502,
                            "invalid_ai_output",
                            "AI returned an invalid structured response",
                        ) from exc
                    # Use the backend call record instead of the model-provided field.
                    answer.tools_used = list(dict.fromkeys(tools_used))
                    return ChatResponse(**answer.model_dump(), request_id=request_id)
                total_calls += len(response.tool_calls)
                if total_calls > MAX_TOOL_CALLS:
                    raise ai_error(
                        502, "ai_tool_limit", "AI requested too many tool calls"
                    )
                input_items.extend(response.continuation_items)
                for call in response.tool_calls:
                    logger.info(
                        "ai_tool request_id=%s user_id=%s tool=%s",
                        request_id,
                        self.principal.user_id,
                        call.name,
                    )
                    result = self.tools.execute(call)
                    tools_used.append(call.name)
                    input_items.append(
                        {
                            "type": "function_call_output",
                            "call_id": call.call_id,
                            "output": result,
                        }
                    )
            raise ai_error(502, "ai_tool_limit", "AI exceeded the tool round limit")
        except HTTPException:
            raise
        except RuntimeError as exc:
            if str(exc) == "OPENAI_API_KEY is not configured":
                raise ai_error(503, "ai_not_configured", str(exc)) from exc
            raise
        except Exception as exc:
            self._raise_provider_error(exc)
            raise

    @staticmethod
    def _raise_provider_error(exc: Exception) -> None:
        from openai import APIError, APITimeoutError, RateLimitError

        if isinstance(exc, APITimeoutError):
            raise ai_error(504, "ai_timeout", "AI provider timed out") from exc
        if isinstance(exc, RateLimitError):
            raise ai_error(
                503, "ai_provider_rate_limit", "AI provider is busy"
            ) from exc
        if isinstance(exc, APIError):
            raise ai_error(
                502, "ai_provider_error", "AI provider request failed"
            ) from exc
        logger.exception("unexpected_ai_error")
        raise ai_error(502, "ai_provider_error", "AI provider request failed") from exc
