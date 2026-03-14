import re
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import uuid4

from fastapi import Request

REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


@dataclass(frozen=True)
class RequestCorrelation:
    request_id: str


_request_correlation_ctx: ContextVar[RequestCorrelation | None] = ContextVar(
    "request_correlation_ctx",
    default=None,
)


def resolve_request_id(header_value: str | None) -> str:
    if header_value and _REQUEST_ID_PATTERN.match(header_value.strip()):
        return header_value.strip()
    return str(uuid4())


def set_request_correlation(request_id: str):
    return _request_correlation_ctx.set(RequestCorrelation(request_id=request_id))


def reset_request_correlation(token) -> None:
    _request_correlation_ctx.reset(token)


def current_request_id() -> str | None:
    correlation = _request_correlation_ctx.get()
    if correlation is None:
        return None
    return correlation.request_id


def request_route_template(request: Request) -> str:
    route = request.scope.get("route")
    if route is None:
        return request.url.path
    path_format = getattr(route, "path_format", None)
    if isinstance(path_format, str) and path_format:
        return path_format
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        return path
    return request.url.path
