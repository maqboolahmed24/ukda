import base64
import json
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlencode

from app.audit.models import AuditRequestContext
from app.audit.service import AuditService
from app.auth.models import (
    AuthMethod,
    AuthSource,
    PlatformRole,
    SessionPrincipal,
    SessionRecord,
    UserRecord,
)
from app.auth.store import AuthStore
from app.auth.tokens import issue_session_token, parse_session_token
from app.core.config import DevSeedIdentity, Settings, get_settings
from app.security.outbound import guarded_http_request
from app.telemetry.context import build_downstream_traceparent


class AuthConfigurationError(RuntimeError):
    """Auth configuration is incomplete or invalid."""


class InvalidSessionError(RuntimeError):
    """Session token is missing, malformed, expired, or revoked."""


class DevAuthDisabledError(RuntimeError):
    """Dev auth path is disabled in the current environment."""


class OidcExchangeError(RuntimeError):
    """OIDC exchange could not complete safely."""


@dataclass(frozen=True)
class OidcMetadata:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str


@dataclass(frozen=True)
class SessionIssue:
    user: UserRecord
    session: SessionRecord
    session_token: str


class AuthService:
    def __init__(
        self,
        *,
        settings: Settings,
        store: AuthStore | None = None,
    ) -> None:
        self._settings = settings
        self._store = store or AuthStore(settings)
        self._oidc_metadata: OidcMetadata | None = None

    @property
    def settings(self) -> Settings:
        return self._settings

    def _sanitize_roles(self, roles: list[str]) -> tuple[PlatformRole, ...]:
        accepted: list[PlatformRole] = []
        for role in roles:
            if role not in {"ADMIN", "AUDITOR"}:
                continue
            if role in accepted:
                continue
            accepted.append(role)  # type: ignore[arg-type]
        return tuple(accepted)

    def _issue_session_for_identity(
        self,
        *,
        oidc_sub: str,
        email: str,
        display_name: str,
        platform_roles: tuple[PlatformRole, ...],
        auth_method: AuthMethod,
    ) -> SessionIssue:
        user = self._store.upsert_user(
            oidc_sub=oidc_sub,
            email=email,
            display_name=display_name,
            platform_roles=platform_roles,
        )
        session = self._store.create_session(
            user_id=user.id,
            auth_method=auth_method,
            ttl_seconds=self._settings.auth_session_ttl_seconds,
        )
        token = issue_session_token(
            session_id=session.id,
            expires_at=session.expires_at,
            secret=self._settings.auth_session_secret,
        )
        return SessionIssue(user=user, session=session, session_token=token)

    def list_dev_seed_users(self) -> list[DevSeedIdentity]:
        return self._settings.auth_dev_seed_users

    def issue_session_for_dev_seed(self, seed_key: str) -> SessionIssue:
        if not self._settings.auth_dev_mode_enabled:
            raise DevAuthDisabledError("Dev auth is disabled.")

        seed_match = next(
            (seed for seed in self._settings.auth_dev_seed_users if seed.key == seed_key),
            None,
        )
        if seed_match is None:
            raise InvalidSessionError("Unknown dev seed identity.")

        return self._issue_session_for_identity(
            oidc_sub=seed_match.oidc_sub,
            email=seed_match.email,
            display_name=seed_match.display_name,
            platform_roles=tuple(seed_match.platform_roles),
            auth_method="dev",
        )

    def _ensure_oidc_enabled(self) -> None:
        if not self._settings.oidc_enabled:
            raise AuthConfigurationError("OIDC is not configured in this environment.")

    def _discover_oidc_metadata(
        self,
        *,
        request_context: AuditRequestContext | None = None,
        audit_service: AuditService | None = None,
    ) -> OidcMetadata:
        self._ensure_oidc_enabled()
        if self._oidc_metadata is not None:
            return self._oidc_metadata

        issuer_url = str(self._settings.oidc_issuer_url).rstrip("/")
        discovery_url = f"{issuer_url}/.well-known/openid-configuration"
        traceparent = build_downstream_traceparent()
        headers = {"traceparent": traceparent} if traceparent else None
        try:
            response = guarded_http_request(
                method="GET",
                url=discovery_url,
                purpose="oidc_discovery",
                settings=self._settings,
                request_context=request_context,
                audit_service=audit_service,
                headers=headers,
                timeout=3.0,
            )
            response.raise_for_status()
            payload = response.json()
        except (RuntimeError, ValueError) as error:
            raise OidcExchangeError("OIDC discovery document could not be loaded.") from error

        issuer = payload.get("issuer")
        authorization_endpoint = payload.get("authorization_endpoint")
        token_endpoint = payload.get("token_endpoint")
        if not all([issuer, authorization_endpoint, token_endpoint]):
            raise OidcExchangeError("OIDC discovery response is missing required fields.")

        self._oidc_metadata = OidcMetadata(
            issuer=issuer,
            authorization_endpoint=authorization_endpoint,
            token_endpoint=token_endpoint,
        )
        return self._oidc_metadata

    def build_oidc_authorization_url(
        self,
        *,
        state: str,
        nonce: str,
        code_challenge: str,
        request_context: AuditRequestContext | None = None,
        audit_service: AuditService | None = None,
    ) -> str:
        metadata = self._discover_oidc_metadata(
            request_context=request_context,
            audit_service=audit_service,
        )

        params = {
            "response_type": "code",
            "client_id": self._settings.oidc_client_id,
            "redirect_uri": self._settings.oidc_redirect_uri,
            "scope": " ".join(self._settings.oidc_scopes),
            "state": state,
            "nonce": nonce,
            "code_challenge_method": "S256",
            "code_challenge": code_challenge,
        }
        return f"{metadata.authorization_endpoint}?{urlencode(params)}"

    @staticmethod
    def _decode_jwt_payload(token: str) -> dict[str, object]:
        parts = token.split(".")
        if len(parts) != 3:
            raise OidcExchangeError("id_token is malformed.")
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        try:
            decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
            claims = json.loads(decoded.decode("utf-8"))
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
            raise OidcExchangeError("id_token claims could not be decoded.") from error
        if not isinstance(claims, dict):
            raise OidcExchangeError("id_token payload has unexpected shape.")
        return claims

    def exchange_oidc_code(
        self,
        *,
        code: str,
        code_verifier: str,
        nonce: str,
        request_context: AuditRequestContext | None = None,
        audit_service: AuditService | None = None,
    ) -> SessionIssue:
        metadata = self._discover_oidc_metadata(
            request_context=request_context,
            audit_service=audit_service,
        )

        traceparent = build_downstream_traceparent()
        headers = {"traceparent": traceparent} if traceparent else None
        try:
            response = guarded_http_request(
                method="POST",
                url=metadata.token_endpoint,
                purpose="oidc_token_exchange",
                settings=self._settings,
                request_context=request_context,
                audit_service=audit_service,
                headers=headers,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": str(self._settings.oidc_redirect_uri),
                    "client_id": str(self._settings.oidc_client_id),
                    "client_secret": str(self._settings.oidc_client_secret),
                    "code_verifier": code_verifier,
                },
                timeout=4.0,
            )
            response.raise_for_status()
            token_payload = response.json()
        except (RuntimeError, ValueError) as error:
            raise OidcExchangeError("OIDC token exchange failed.") from error

        id_token = token_payload.get("id_token")
        if not isinstance(id_token, str) or not id_token:
            raise OidcExchangeError("OIDC token response did not include id_token.")

        claims = self._decode_jwt_payload(id_token)
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            raise OidcExchangeError("OIDC id_token is missing a stable subject.")

        claim_nonce = claims.get("nonce")
        if nonce and claim_nonce and claim_nonce != nonce:
            raise OidcExchangeError("OIDC nonce validation failed.")

        email = claims.get("email")
        preferred_username = claims.get("preferred_username")
        display_name = claims.get("name")
        resolved_email = (
            str(email)
            if isinstance(email, str) and email.strip()
            else (
                str(preferred_username)
                if isinstance(preferred_username, str) and preferred_username.strip()
                else f"{subject}@unknown.ukde"
            )
        )
        resolved_display_name = (
            str(display_name)
            if isinstance(display_name, str) and display_name.strip()
            else resolved_email
        )
        claim_roles = claims.get("ukde_platform_roles")
        roles = self._sanitize_roles(claim_roles if isinstance(claim_roles, list) else [])

        return self._issue_session_for_identity(
            oidc_sub=subject,
            email=resolved_email,
            display_name=resolved_display_name,
            platform_roles=roles,
            auth_method="oidc",
        )

    def resolve_session(self, *, token: str, auth_source: AuthSource) -> SessionPrincipal:
        claims = parse_session_token(token, secret=self._settings.auth_session_secret)
        if claims is None:
            raise InvalidSessionError("Session token is invalid or expired.")

        principal = self._store.get_session_principal(
            session_id=claims.session_id,
            auth_source=auth_source,
        )
        if principal is None:
            raise InvalidSessionError("Session is not active.")
        return principal

    def revoke_session(self, *, session_id: str) -> None:
        self._store.revoke_session(session_id=session_id)


@lru_cache
def get_auth_service() -> AuthService:
    settings = get_settings()
    return AuthService(settings=settings)
