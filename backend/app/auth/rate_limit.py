"""Bound repeated login failures without storing email addresses in limiter keys."""

import hashlib
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException

MAX_LOGIN_FAILURES = 10
LOGIN_WINDOW_SECONDS = 300


class LoginRateLimiter:
    def __init__(self) -> None:
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    @staticmethod
    def key(client_host: str, email: str) -> str:
        value = f"{client_host}\0{email.strip().lower()}".encode()
        return hashlib.sha256(value).hexdigest()

    def check(self, key: str, *, now: float | None = None) -> None:
        current = time.monotonic() if now is None else now
        with self._lock:
            failures = self._failures[key]
            self._prune(failures, current)
            if len(failures) >= MAX_LOGIN_FAILURES:
                raise HTTPException(
                    status_code=429,
                    detail="Too many login attempts; try again later",
                    headers={"Retry-After": str(LOGIN_WINDOW_SECONDS)},
                )

    def record_failure(self, key: str, *, now: float | None = None) -> None:
        current = time.monotonic() if now is None else now
        with self._lock:
            failures = self._failures[key]
            self._prune(failures, current)
            failures.append(current)

    def clear(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    @staticmethod
    def _prune(failures: deque[float], current: float) -> None:
        boundary = current - LOGIN_WINDOW_SECONDS
        while failures and failures[0] <= boundary:
            failures.popleft()


login_rate_limiter = LoginRateLimiter()
