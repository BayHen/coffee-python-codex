"""Dependency-free smoke test for the disposable Docker demo environment."""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from decimal import Decimal
from typing import Any
from uuid import uuid4


def request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    body: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> tuple[int, Any]:
    base_url = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    payload = None if body is None else json.dumps(body).encode()
    call = urllib.request.Request(
        f"{base_url}{path}", data=payload, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(call, timeout=15) as response:
            data = response.read()
            return response.status, json.loads(data) if data else None
    except urllib.error.HTTPError as exc:
        data = exc.read()
        return exc.code, json.loads(data) if data else None


def require(status: int, expected: int, label: str) -> None:
    if status != expected:
        raise RuntimeError(f"{label} returned HTTP {status}, expected {expected}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true")
    args = parser.parse_args(argv)
    password = os.environ.get("DEMO_ADMIN_PASSWORD", "")
    if not password:
        print("DEMO_ADMIN_PASSWORD is required", file=sys.stderr)
        return 1
    try:
        status, health = request("GET", "/health")
        require(status, 200, "health")
        if health != {"status": "ok"}:
            raise RuntimeError("health response is invalid")
        status, tokens = request(
            "POST",
            "/auth/login",
            body={"email": "demo.admin@example.com", "password": password},
        )
        require(status, 200, "login")
        token = tokens["access_token"]
        status, products = request("GET", "/products?page_size=20", token=token)
        require(status, 200, "products")
        variants = [
            variant
            for product in products["items"]
            for variant in product["variants"]
            if variant["sku"] == "DEMO-LATTE-M"
        ]
        if len(variants) != 1:
            raise RuntimeError("demo product was not found")
        status, ingredients = request("GET", "/ingredients?page_size=100", token=token)
        require(status, 200, "ingredients")
        demo_stock = {
            item["sku"]: item["current_stock"]
            for item in ingredients["items"]
            if item["sku"].startswith("DEMO-")
        }
        if set(demo_stock) != {"DEMO-BEAN", "DEMO-MILK", "DEMO-CUP"}:
            raise RuntimeError("demo inventory was not found")
        if any(Decimal(quantity) <= 0 for quantity in demo_stock.values()):
            raise RuntimeError("demo opening inventory is invalid")

        status, ai_response = request(
            "POST",
            "/ai/chat",
            token=token,
            body={"message": "Summarize today's revenue."},
        )
        expected_ai_status = 200 if os.environ.get("EXPECT_AI_CONFIGURED") else 503
        require(status, expected_ai_status, "AI configuration policy")
        if expected_ai_status == 503 and (
            ai_response.get("detail", {}).get("code") != "ai_not_configured"
        ):
            raise RuntimeError("AI configuration error response is invalid")
        if not args.read_only:
            suffix = uuid4().hex
            order_key = f"smoke-order-{suffix}"
            order_body = {"items": [{"variant_id": variants[0]["id"], "quantity": 1}]}
            status, order = request(
                "POST",
                "/orders",
                token=token,
                idempotency_key=order_key,
                body=order_body,
            )
            require(status, 201, "create order")
            status, order_retry = request(
                "POST",
                "/orders",
                token=token,
                idempotency_key=order_key,
                body=order_body,
            )
            require(status, 201, "retry order")
            if order_retry["id"] != order["id"]:
                raise RuntimeError("order idempotency created a duplicate")
            status, _ = request(
                "POST",
                f"/orders/{order['id']}/transitions",
                token=token,
                body={"target_status": "placed"},
            )
            require(status, 200, "place order")
            payment_key = f"smoke-payment-{suffix}"
            payment_body = {"method": "cash", "outcome": "succeeded"}
            status, payment = request(
                "POST",
                f"/orders/{order['id']}/payments",
                token=token,
                idempotency_key=payment_key,
                body=payment_body,
            )
            require(status, 201, "payment")
            status, payment_retry = request(
                "POST",
                f"/orders/{order['id']}/payments",
                token=token,
                idempotency_key=payment_key,
                body=payment_body,
            )
            require(status, 201, "retry payment")
            if payment_retry["id"] != payment["id"]:
                raise RuntimeError("payment idempotency created a duplicate")
            status, report = request("GET", "/reports/revenue/summary", token=token)
            require(status, 200, "revenue report")
            if report["valid_order_count"] < 1:
                raise RuntimeError("paid order was not included in revenue")
        print("Docker demo smoke test passed")
        return 0
    except (KeyError, RuntimeError, TypeError, urllib.error.URLError) as exc:
        print(f"Smoke test failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
