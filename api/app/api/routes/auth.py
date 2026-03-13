from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.audit.dependencies import get_audit_request_context
from app.audit.models import AuditRequestContext
from app.audit.service import AuditService, get_audit_service
from app.audit.store import AuditStoreUnavailableError as AuditUnavailableError
from app.auth.dependencies import (
    require_authenticated_user,
    require_csrf_for_cookie_auth,
)
from app.auth.models import SessionPrincipal
from app.auth.service import (
    AuthConfigurationError,
    DevAuthDisabledError,
    InvalidSessionError,
    OidcExchangeError,
    get_auth_service,
)
from app.auth.store import AuthStoreUnavailableError
from app.telemetry.context import current_trace_id
from app.telemetry.service import TelemetryService, get_telemetry_service

public_router = APIRouter(prefix="/auth")
protected_router = APIRouter(prefix="/auth")


class ProviderSeed(BaseModel):
    key: str
    display_name: str = Field(serialization_alias="displayName")
    email: str
    platform_roles: list[str] = Field(serialization_alias="platformRoles")


class ProviderResponse(BaseModel):
    oidc_enabled: bool = Field(serialization_alias="oidcEnabled")
    dev_enabled: bool = Field(serialization_alias="devEnabled")
    dev_seeds: list[ProviderSeed] = Field(default_factory=list, serialization_alias="devSeeds")


class OidcAuthorizationUrlResponse(BaseModel):
    authorization_url: str = Field(serialization_alias="authorizationUrl")


class OidcAuthorizationUrlRequest(BaseModel):
    state: str = Field(min_length=12, max_length=256)
    nonce: str = Field(min_length=12, max_length=256)
    code_challenge: str = Field(min_length=43, max_length=128)


class OidcExchangeRequest(BaseModel):
    code: str = Field(min_length=8)
    code_verifier: str = Field(min_length=43, max_length=128)
    nonce: str = Field(min_length=12, max_length=256)


class DevLoginRequest(BaseModel):
    seed_key: str = Field(min_length=1)


class SessionUserResponse(BaseModel):
    id: str
    sub: str
    email: str
    display_name: str = Field(serialization_alias="displayName")
    platform_roles: list[str] = Field(serialization_alias="platformRoles")


class SessionBoundaryResponse(BaseModel):
    id: str
    expires_at: str = Field(serialization_alias="expiresAt")


class SessionResponse(BaseModel):
    user: SessionUserResponse
    session: SessionBoundaryResponse


class SessionIssueResponse(SessionResponse):
    session_token: str = Field(serialization_alias="sessionToken")
    csrf_token: str = Field(serialization_alias="csrfToken")


def _as_session_response(current_user: SessionPrincipal) -> SessionResponse:
    return SessionResponse(
        user=SessionUserResponse(
            id=current_user.user_id,
            sub=current_user.oidc_sub,
            email=current_user.email,
            display_name=current_user.display_name,
            platform_roles=list(current_user.platform_roles),
        ),
        session=SessionBoundaryResponse(
            id=current_user.session_id,
            expires_at=current_user.expires_at.isoformat(),
        ),
    )


@public_router.get("/providers", response_model=ProviderResponse)
def auth_providers(auth_service=Depends(get_auth_service)) -> ProviderResponse:
    seeds = []
    if auth_service.settings.auth_dev_mode_enabled:
        seeds = [
            ProviderSeed(
                key=seed.key,
                display_name=seed.display_name,
                email=seed.email,
                platform_roles=list(seed.platform_roles),
            )
            for seed in auth_service.list_dev_seed_users()
        ]
    return ProviderResponse(
        oidc_enabled=auth_service.settings.oidc_enabled,
        dev_enabled=auth_service.settings.auth_dev_mode_enabled,
        dev_seeds=seeds,
    )


@public_router.post(
    "/oidc/authorization-url",
    response_model=OidcAuthorizationUrlResponse,
)
def oidc_authorization_url(
    payload: OidcAuthorizationUrlRequest,
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    auth_service=Depends(get_auth_service),
) -> OidcAuthorizationUrlResponse:
    try:
        url = auth_service.build_oidc_authorization_url(
            state=payload.state,
            nonce=payload.nonce,
            code_challenge=payload.code_challenge,
            request_context=request_context,
            audit_service=audit_service,
        )
    except (AuthConfigurationError, OidcExchangeError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    return OidcAuthorizationUrlResponse(authorization_url=url)


@public_router.post("/oidc/exchange", response_model=SessionIssueResponse)
def oidc_exchange(
    payload: OidcExchangeRequest,
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    telemetry_service: TelemetryService = Depends(get_telemetry_service),
    auth_service=Depends(get_auth_service),
) -> SessionIssueResponse:
    try:
        issued = auth_service.exchange_oidc_code(
            code=payload.code,
            code_verifier=payload.code_verifier,
            nonce=payload.nonce,
            request_context=request_context,
            audit_service=audit_service,
        )
    except (AuthConfigurationError, OidcExchangeError, AuthStoreUnavailableError) as error:
        telemetry_service.record_auth_result(
            success=False,
            auth_source="oidc",
            reason="oidc_exchange_failed",
            request_id=request_context.request_id,
            trace_id=current_trace_id(),
        )
        audit_service.record_event_best_effort(
            event_type="AUTH_FAILED",
            actor_user_id=None,
            metadata={
                "reason": "oidc_exchange_failed",
                "auth_source": "oidc",
                "route": request_context.route_template,
                "status_code": status.HTTP_400_BAD_REQUEST,
            },
            request_context=request_context,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    try:
        audit_service.record_event(
            event_type="USER_LOGIN",
            actor_user_id=issued.user.id,
            object_type="session",
            object_id=issued.session.id,
            metadata={
                "auth_method": "oidc",
                "auth_source": "oidc",
                "session_id": issued.session.id,
            },
            request_context=request_context,
        )
    except AuditUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audit store is unavailable.",
        ) from error

    telemetry_service.record_auth_result(
        success=True,
        auth_source="oidc",
        request_id=request_context.request_id,
        trace_id=current_trace_id(),
    )

    return SessionIssueResponse(
        user=SessionUserResponse(
            id=issued.user.id,
            sub=issued.user.oidc_sub,
            email=issued.user.email,
            display_name=issued.user.display_name,
            platform_roles=list(issued.user.platform_roles),
        ),
        session=SessionBoundaryResponse(
            id=issued.session.id,
            expires_at=issued.session.expires_at.isoformat(),
        ),
        session_token=issued.session_token,
        csrf_token=issued.session.csrf_token,
    )


@public_router.post("/dev/login", response_model=SessionIssueResponse)
def dev_login(
    payload: DevLoginRequest,
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    telemetry_service: TelemetryService = Depends(get_telemetry_service),
    auth_service=Depends(get_auth_service),
) -> SessionIssueResponse:
    try:
        issued = auth_service.issue_session_for_dev_seed(seed_key=payload.seed_key)
    except DevAuthDisabledError as error:
        telemetry_service.record_auth_result(
            success=False,
            auth_source="dev",
            reason="dev_auth_disabled",
            request_id=request_context.request_id,
            trace_id=current_trace_id(),
        )
        audit_service.record_event_best_effort(
            event_type="AUTH_FAILED",
            actor_user_id=None,
            metadata={
                "reason": "dev_auth_disabled",
                "auth_source": "dev",
                "route": request_context.route_template,
                "status_code": status.HTTP_403_FORBIDDEN,
            },
            request_context=request_context,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
    except (InvalidSessionError, AuthStoreUnavailableError) as error:
        telemetry_service.record_auth_result(
            success=False,
            auth_source="dev",
            reason="dev_login_failed",
            request_id=request_context.request_id,
            trace_id=current_trace_id(),
        )
        audit_service.record_event_best_effort(
            event_type="AUTH_FAILED",
            actor_user_id=None,
            metadata={
                "reason": "dev_login_failed",
                "auth_source": "dev",
                "route": request_context.route_template,
                "status_code": status.HTTP_400_BAD_REQUEST,
            },
            request_context=request_context,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    try:
        audit_service.record_event(
            event_type="USER_LOGIN",
            actor_user_id=issued.user.id,
            object_type="session",
            object_id=issued.session.id,
            metadata={
                "auth_method": "dev",
                "auth_source": "dev",
                "session_id": issued.session.id,
            },
            request_context=request_context,
        )
    except AuditUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audit store is unavailable.",
        ) from error

    telemetry_service.record_auth_result(
        success=True,
        auth_source="dev",
        request_id=request_context.request_id,
        trace_id=current_trace_id(),
    )

    return SessionIssueResponse(
        user=SessionUserResponse(
            id=issued.user.id,
            sub=issued.user.oidc_sub,
            email=issued.user.email,
            display_name=issued.user.display_name,
            platform_roles=list(issued.user.platform_roles),
        ),
        session=SessionBoundaryResponse(
            id=issued.session.id,
            expires_at=issued.session.expires_at.isoformat(),
        ),
        session_token=issued.session_token,
        csrf_token=issued.session.csrf_token,
    )


@protected_router.get(
    "/session",
    response_model=SessionResponse,
)
def current_session(
    current_user: SessionPrincipal = Depends(require_authenticated_user),
) -> SessionResponse:
    return _as_session_response(current_user)


@protected_router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_for_cookie_auth)],
)
def logout(
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    auth_service=Depends(get_auth_service),
) -> None:
    try:
        auth_service.revoke_session(session_id=current_user.session_id)
    except AuthStoreUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session invalidation failed.",
        ) from error

    try:
        audit_service.record_event(
            event_type="USER_LOGOUT",
            actor_user_id=current_user.user_id,
            object_type="session",
            object_id=current_user.session_id,
            metadata={
                "auth_source": current_user.auth_source,
                "session_id": current_user.session_id,
            },
            request_context=request_context,
        )
    except AuditUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audit store is unavailable.",
        ) from error
