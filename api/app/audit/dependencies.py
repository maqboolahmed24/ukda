from fastapi import Request

from app.audit.context import current_request_id, request_route_template
from app.audit.models import AuditRequestContext


def get_audit_request_context(request: Request) -> AuditRequestContext:
    request_id = getattr(request.state, "request_id", None) or current_request_id() or "unknown"
    client_host = request.client.host if request.client else None
    return AuditRequestContext(
        request_id=request_id,
        method=request.method,
        route_template=request_route_template(request),
        path=request.url.path,
        ip=client_host,
        user_agent=request.headers.get("user-agent"),
    )
