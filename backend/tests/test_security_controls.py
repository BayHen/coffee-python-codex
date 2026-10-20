"""Focused tests for controls that do not require a database."""

import pytest
from fastapi import HTTPException

from app.auth.rate_limit import (
    LOGIN_WINDOW_SECONDS,
    MAX_LOGIN_FAILURES,
    LoginRateLimiter,
)


def test_login_rate_limit_is_scoped_hashed_and_expires() -> None:
    limiter = LoginRateLimiter()
    key = limiter.key("127.0.0.1", "Manager@Example.com")
    assert "manager@example.com" not in key
    assert key == limiter.key("127.0.0.1", "manager@example.com")

    for attempt in range(MAX_LOGIN_FAILURES):
        limiter.check(key, now=float(attempt))
        limiter.record_failure(key, now=float(attempt))
    with pytest.raises(HTTPException) as caught:
        limiter.check(key, now=float(MAX_LOGIN_FAILURES))
    assert caught.value.status_code == 429
    assert caught.value.headers == {"Retry-After": str(LOGIN_WINDOW_SECONDS)}

    limiter.check(key, now=LOGIN_WINDOW_SECONDS + MAX_LOGIN_FAILURES)


def test_successful_login_clears_failure_counter() -> None:
    limiter = LoginRateLimiter()
    key = limiter.key("127.0.0.1", "manager@example.com")
    for attempt in range(MAX_LOGIN_FAILURES):
        limiter.record_failure(key, now=float(attempt))
    limiter.clear(key)
    limiter.check(key, now=float(MAX_LOGIN_FAILURES))
