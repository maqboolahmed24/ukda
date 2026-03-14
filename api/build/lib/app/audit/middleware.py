import logging
from collections.abc import Awaitable, Callable
from time import perf_counter

from fastapi import Request, Response

from app.audit.context import (
    REQUEST_ID_HEADER,
    request_route_template,
    reset_request_correlation,
    resolve_request_id,
    set_request_correlation,
)
from app.telemetry.context import (
    TRACEPARENT_HEADER,
    reset_trace_context,
    resolve_trace_context,
    set_trace_context,
)
from app.telemetry.logging import emit_telemetry_log
from app.telemetry.service import get_telemetry_service


def _resolve_route_label(request: Request) -> str:
    route = request.scope.get("route")
    if route is None:
        return "/__unmatched__"
    return request_route_template(request)


def _resolve_project_id(request: Request) -> str | None:
    raw_project_id = request.path_params.get("project_id")
    if not isinstance(raw_project_id, str):
        return None
    candidate = raw_project_id.strip()
    if not candidate:
        return None
    return candidate[:128]


async def correlation_id_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    telemetry_service = get_telemetry_service()
    request_id = resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
    trace_context = resolve_trace_context(request.headers.get(TRACEPARENT_HEADER))
    request.state.request_id = request_id
    request.state.trace_id = trace_context.trace_id
    request.state.traceparent = trace_context.response_traceparent
    request_token = set_request_correlation(request_id)
    trace_token = set_trace_context(trace_context)
    started_at = perf_counter()

    try:
        response = await call_next(request)
    except Exception as error:
        duration_ms = (perf_counter() - started_at) * 1000
        route_template = _resolve_route_label(request)
        project_id = _resolve_project_id(request)
        telemetry_service.record_request(
            route_template=route_template,
            method=request.method,
            status_code=500,
            duration_ms=duration_ms,
            request_id=request_id,
            trace_id=trace_context.trace_id,
            project_id=project_id,
        )
        emit_telemetry_log(
            event="http_request_failed",
            message="API request failed before response completion.",
            payload={
                "request_id": request_id,
                "trace_id": trace_context.trace_id,
                "method": request.method,
                "route_template": route_template,
                "status_code": 500,
                "duration_ms": duration_ms,
                "project_id": project_id,
                "error_class": error.__class__.__name__,
            },
            level=logging.ERROR,
        )
        raise
    else:
        duration_ms = (perf_counter() - started_at) * 1000
        route_template = _resolve_route_label(request)
        project_id = _resolve_project_id(request)
        telemetry_service.record_request(
            route_template=route_template,
            method=request.method,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
            trace_id=trace_context.trace_id,
            project_id=project_id,
        )
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers[TRACEPARENT_HEADER] = trace_context.response_traceparent
        emit_telemetry_log(
            event="http_request",
            message="API request completed.",
            payload={
                "request_id": request_id,
                "trace_id": trace_context.trace_id,
                "method": request.method,
                "route_template": route_template,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "project_id": project_id,
            },
        )
        return response
    finally:
        reset_request_correlation(request_token)
        reset_trace_context(trace_token)
