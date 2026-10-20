"""AI orchestration tests use a fake gateway and never call OpenAI."""

import json
from collections import deque
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.ai.gateway import ModelResponse, OpenAIResponsesGateway, ToolCall
from app.ai.service import AIManagementService, ReadOnlyToolExecutor
from app.auth.dependencies import Principal


class FakeGateway:
    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = deque(responses)
        self.inputs: list[list[Any]] = []

    def complete(self, input_items: list[Any]) -> ModelResponse:
        self.inputs.append(list(input_items))
        return self.responses.popleft()


def principal(role: str = "Manager") -> Principal:
    return Principal(
        user_id=987654,
        session_id=uuid4(),
        email="manager@example.com",
        role=role,
    )


def test_chat_executes_only_allowlisted_tool_and_validates_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = FakeGateway(
        [
            ModelResponse(
                response_id="resp-tool",
                output_text="",
                tool_calls=[
                    ToolCall(
                        call_id="call-1",
                        name="get_revenue_summary",
                        arguments='{"date_from":null,"date_to":null}',
                    )
                ],
                continuation_items=[
                    {
                        "type": "function_call",
                        "call_id": "call-1",
                        "name": "get_revenue_summary",
                        "arguments": '{"date_from":null,"date_to":null}',
                    }
                ],
            ),
            ModelResponse(
                response_id="resp-final",
                output_text=json.dumps(
                    {
                        "answer": "Doanh thu là 145.00 VND.",
                        "highlights": ["2 đơn hợp lệ"],
                        "recommendations": [],
                        "tools_used": ["untrusted_model_value"],
                    }
                ),
                tool_calls=[],
                continuation_items=[],
            ),
        ]
    )
    monkeypatch.setattr(
        ReadOnlyToolExecutor,
        "execute",
        lambda _self, _call: '{"total_revenue":"145.00"}',
    )

    result = AIManagementService(None, principal(), gateway).chat(  # type: ignore[arg-type]
        "Doanh thu tháng này?"
    )

    assert result.answer == "Doanh thu là 145.00 VND."
    assert result.tools_used == ["get_revenue_summary"]
    assert gateway.inputs[1][-1] == {
        "type": "function_call_output",
        "call_id": "call-1",
        "output": '{"total_revenue":"145.00"}',
    }


def test_invalid_structured_output_is_rejected() -> None:
    gateway = FakeGateway(
        [
            ModelResponse(
                response_id="bad",
                output_text='{"answer":"missing required fields"}',
                tool_calls=[],
                continuation_items=[],
            )
        ]
    )
    with pytest.raises(HTTPException) as caught:
        AIManagementService(None, principal(), gateway).chat("Tóm tắt")  # type: ignore[arg-type]
    assert caught.value.status_code == 502
    assert caught.value.detail["code"] == "invalid_ai_output"


def test_unknown_tool_and_staff_tool_access_are_blocked() -> None:
    unknown = ToolCall("call-2", "run_sql", '{"sql":"DROP TABLE orders"}')
    with pytest.raises(HTTPException) as caught:
        ReadOnlyToolExecutor(None, principal()).execute(unknown)  # type: ignore[arg-type]
    assert caught.value.status_code == 400
    assert caught.value.detail["code"] == "unknown_ai_tool"

    allowed = ToolCall(
        "call-3",
        "get_revenue_summary",
        '{"date_from":null,"date_to":null}',
    )
    with pytest.raises(HTTPException) as forbidden:
        ReadOnlyToolExecutor(None, principal("Staff")).execute(allowed)  # type: ignore[arg-type]
    assert forbidden.value.status_code == 403


def test_openai_gateway_sends_strict_read_only_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-never-sent")
    captured: dict[str, Any] = {}

    class FakeResponses:
        def create(self, **kwargs: Any) -> Any:
            captured.update(kwargs)
            return SimpleNamespace(
                id="response-1",
                output=[],
                output_text=json.dumps(
                    {
                        "answer": "Không cần công cụ.",
                        "highlights": [],
                        "recommendations": [],
                        "tools_used": [],
                    }
                ),
                usage=SimpleNamespace(input_tokens=10, output_tokens=20),
            )

    gateway = OpenAIResponsesGateway()
    gateway.client = SimpleNamespace(responses=FakeResponses())  # type: ignore[assignment]
    result = gateway.complete([{"role": "user", "content": "Xin chào"}])

    assert result.response_id == "response-1"
    assert captured["store"] is False
    assert captured["text"]["format"]["strict"] is True
    assert {tool["name"] for tool in captured["tools"]} == {
        "get_revenue_summary",
        "get_top_products",
        "get_low_stock_ingredients",
    }
    assert all(tool["strict"] is True for tool in captured["tools"])
