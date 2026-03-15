import hmac
from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, Request, status

from app.audit.dependencies import get_audit_request_context
from app.audit.models import AuditRequestContext
from app.audit.service import AuditService, get_audit_service
from app.auth.models import AuthSource, PlatformRole, SessionPrincipal
from app.auth.service import InvalidSessionError, get_auth_service
from app.auth.store import AuthStoreUnavailableError
from app.core.config import Settings, get_settings
from app.telemetry.context import current_trace_id
from app.telemetry.service import TelemetryService, get_telemetry_service


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2:
        return None
    scheme, token = parts
    if scheme.lower() != "bearer":
        return None
    return token.strip() or None


def require_authenticated_user(
    request: Request,
    authorization: str | None = Header(default=None),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    telemetry_service: TelemetryService = Depends(get_telemetry_service),
    auth_service=Depends(get_auth_service),
) -> SessionPrincipal:
    bearer_token = _extract_bearer_token(authorization)
    cookie_token = request.cookies.get(auth_service.settings.auth_cookie_name)

    token: str | None = None
    auth_source: AuthSource = "bearer"
    if bearer_token:
        token = bearer_token
        auth_source = "bearer"
    elif cookie_token:
        token = cookie_token
        auth_source = "cookie"

    if not token:
        telemetry_service.record_auth_result(
            success=False,
            auth_source="none",
            reason="missing_session_token",
            request_id=request_context.request_id,
            trace_id=current_trace_id(),
        )
        audit_service.record_event_best_effort(
            event_type="AUTH_FAILED",
            actor_user_id=None,
            metadata={
                "reason": "missing_session_token",
                "auth_source": "none",
                "route": request_context.route_template,
                "status_code": status.HTTP_401_UNAUTHORIZED,
            },
            request_context=request_context,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required.",
        )

    try:
        principal = auth_service.resolve_session(token=token, auth_source=auth_source)
    except InvalidSessionError as error:
        telemetry_service.record_auth_result(
            success=False,
            auth_source=auth_source,
            reason="invalid_or_expired_session",
            request_id=request_context.request_id,
            trace_id=current_trace_id(),
        )
        audit_service.record_event_best_effort(
            event_type="AUTH_FAILED",
            actor_user_id=None,
            metadata={
                "reason": "invalid_or_expired_session",
                "auth_source": auth_source,
                "route": request_context.route_template,
                "status_code": status.HTTP_401_UNAUTHORIZED,
            },
            request_context=request_context,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        ) from error
    except AuthStoreUnavailableError as error:
        telemetry_service.record_auth_result(
            success=False,
            auth_source=auth_source,
            reason="auth_store_unavailable",
            request_id=request_context.request_id,
            trace_id=current_trace_id(),
        )
        audit_service.record_event_best_effort(
            event_type="AUTH_FAILED",
            actor_user_id=None,
            metadata={
                "reason": "auth_store_unavailable",
                "auth_source": auth_source,
                "route": request_context.route_template,
                "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
            },
            request_context=request_context,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication store is unavailable.",
        ) from error

    telemetry_service.record_auth_result(
        success=True,
        auth_source=auth_source,
        request_id=request_context.request_id,
        trace_id=current_trace_id(),
    )
    return principal


def require_platform_roles(
    *required_roles: PlatformRole,
) -> Callable[[SessionPrincipal], SessionPrincipal]:
    required = set(required_roles)

    def _guard(
        current_user: SessionPrincipal = Depends(require_authenticated_user),
        request_context: AuditRequestContext = Depends(get_audit_request_context),
        audit_service: AuditService = Depends(get_audit_service),
    ) -> SessionPrincipal:
        current_roles = set(current_user.platform_roles)
        if required.intersection(current_roles):
            return current_user
        audit_service.record_event_best_effort(
            event_type="ACCESS_DENIED",
            actor_user_id=current_user.user_id,
            metadata={
                "route": request_context.route_template,
                "required_roles": sorted(required),
                "status_code": status.HTTP_403_FORBIDDEN,
            },
            request_context=request_context,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The current session cannot access this route.",
        )

    return _guard


def require_internal_export_gateway_service_account(
    internal_token: str | None = Header(default=None, alias="X-UKDE-Internal-Token"),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    settings: Settings = Depends(get_settings),
) -> str:
    expected = settings.internal_export_gateway_token.strip()
    provided = (internal_token or "").strip()
    if expected and provided and hmac.compare_digest(provided, expected):
        return settings.internal_export_gateway_actor_user_id
    audit_service.record_event_best_effort(
        event_type="ACCESS_DENIED",
        actor_user_id=None,
        metadata={
            "route": request_context.route_template,
            "required_roles": ["INTERNAL_EXPORT_GATEWAY_SERVICE"],
            "status_code": status.HTTP_403_FORBIDDEN,
        },
        request_context=request_context,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Internal export-gateway authentication failed.",
    )


def require_csrf_for_cookie_auth(
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> None:
    if current_user.auth_source != "cookie":
        return
    if not csrf_header or csrf_header != current_user.csrf_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token validation failed.",
        )
