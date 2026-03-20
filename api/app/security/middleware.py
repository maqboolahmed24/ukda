from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import RLock
from time import time

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.core.config import Settings


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    reset_epoch: int
    scope: str


@dataclass(frozen=True)
class RateLimitRule:
    scope: str
    window_seconds: int
    max_requests: int


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._lock = RLock()
        self._windows: dict[str, deque[float]] = {}

    def evaluate(self, *, key: str, rule: RateLimitRule) -> RateLimitDecision:
        now = time()
        window_start = now - rule.window_seconds
        composite_key = f"{rule.scope}:{key}"
        with self._lock:
            bucket = self._windows.setdefault(composite_key, deque())
            while bucket and bucket[0] <= window_start:
                bucket.popleft()

            if len(bucket) >= rule.max_requests:
                reset_epoch = int(bucket[0] + rule.window_seconds) if bucket else int(now)
                return RateLimitDecision(
                    allowed=False,
                    limit=rule.max_requests,
                    remaining=0,
                    reset_epoch=reset_epoch,
                    scope=rule.scope,
                )

            bucket.append(now)
            remaining = max(0, rule.max_requests - len(bucket))
            reset_epoch = int((bucket[0] if bucket else now) + rule.window_seconds)
            return RateLimitDecision(
                allowed=True,
                limit=rule.max_requests,
                remaining=remaining,
                reset_epoch=reset_epoch,
                scope=rule.scope,
            )


def _resolve_rate_limit_rule(path: str, settings: Settings) -> RateLimitRule | None:
    if path in {"/healthz", "/readyz"}:
        return None
    if path.startswith("/auth/"):
        return RateLimitRule(
            scope="auth",
            window_seconds=settings.auth_rate_limit_window_seconds,
            max_requests=settings.auth_rate_limit_max_requests,
        )
    return RateLimitRule(
        scope="protected",
        window_seconds=settings.protected_rate_limit_window_seconds,
        max_requests=settings.protected_rate_limit_max_requests,
    )


def _apply_security_headers(response: Response, settings: Settings) -> None:
    csp_header = (
        "Content-Security-Policy-Report-Only"
        if settings.security_csp_mode == "report-only"
        else "Content-Security-Policy"
    )
    response.headers[csp_header] = settings.security_csp_value
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = settings.security_referrer_policy
    response.headers["Permissions-Policy"] = settings.security_permissions_policy


def create_security_headers_middleware(settings: Settings):
    async def _middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        _apply_security_headers(response, settings)
        return response

    return _middleware


def create_rate_limit_middleware(settings: Settings):
    limiter = InMemoryRateLimiter()

    async def _middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        rule = _resolve_rate_limit_rule(request.url.path, settings)
        if rule is None:
            response = await call_next(request)
            return response

        client_host = request.client.host if request.client else "unknown"
        # Keep counters independent per concrete route so high-volume calls on one
        # endpoint do not starve unrelated protected endpoints for the same client.
        route_key = f"{request.method}:{request.url.path}"
        decision = limiter.evaluate(key=f"{client_host}:{route_key}", rule=rule)
        if not decision.allowed:
            response = JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded.",
                    "code": "RATE_LIMIT_EXCEEDED",
                    "scope": decision.scope,
                },
            )
            retry_after = max(0, decision.reset_epoch - int(time()))
            response.headers["Retry-After"] = str(retry_after)
        else:
            response = await call_next(request)

        response.headers["X-RateLimit-Limit"] = str(decision.limit)
        response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
        response.headers["X-RateLimit-Reset"] = str(decision.reset_epoch)
        _apply_security_headers(response, settings)
        return response

    return _middleware
