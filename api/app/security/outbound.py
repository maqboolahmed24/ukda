from __future__ import annotations

from ipaddress import ip_address
from urllib.parse import urlparse

import httpx

from app.audit.context import current_request_id
from app.audit.models import AuditRequestContext
from app.audit.service import AuditService, get_audit_service
from app.core.config import Settings, get_settings

_ALLOWED_SCHEMES = {"http", "https"}
_DEFAULT_REQUEST_ID = "outbound-policy"


class OutboundRequestBlockedError(RuntimeError):
    """Outbound call target is not allowlisted for this environment."""

    def __init__(
        self,
        *,
        method: str,
        url: str,
        host: str,
        reason: str,
    ) -> None:
        super().__init__(f"Blocked outbound call to '{host}' ({method.upper()} {url}): {reason}")
        self.method = method.upper()
        self.url = url
        self.host = host
        self.reason = reason
        self.code = "OUTBOUND_DOMAIN_NOT_ALLOWLISTED"


def _is_internal_host(host: str) -> bool:
    candidate = host.strip().lower()
    if not candidate:
        return False
    if candidate in {"localhost"}:
        return True
    if candidate.endswith(".internal") or candidate.endswith(".local"):
        return True
    try:
        resolved = ip_address(candidate)
    except ValueError:
        return False
    return bool(resolved.is_private or resolved.is_loopback)


def _matches_allowlist(host: str, allowlist: list[str]) -> bool:
    candidate = host.strip().lower()
    if not candidate:
        return False
    for raw_entry in allowlist:
        entry = raw_entry.strip().lower()
        if not entry:
            continue
        if entry.startswith("*."):
            suffix = f".{entry[2:]}"
            if candidate.endswith(suffix):
                return True
            continue
        if entry.startswith("."):
            if candidate.endswith(entry):
                return True
            continue
        if candidate == entry:
            return True
    return False


def is_url_allowlisted(url: str, settings: Settings) -> bool:
    parsed = urlparse(url)
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        return False
    host = (parsed.hostname or "").strip().lower()
    if not host:
        return False
    if _is_internal_host(host):
        return True
    return _matches_allowlist(host, settings.outbound_allowlist)


def _record_blocked_attempt(
    *,
    method: str,
    url: str,
    host: str,
    purpose: str,
    actor_user_id: str | None,
    request_context: AuditRequestContext | None,
    audit_service: AuditService | None,
    reason: str,
) -> None:
    service = audit_service or get_audit_service()
    if request_context:
        resolved_request_id = request_context.request_id
    else:
        resolved_request_id = current_request_id() or _DEFAULT_REQUEST_ID
    service.record_event_best_effort(
        event_type="OUTBOUND_CALL_BLOCKED",
        actor_user_id=actor_user_id,
        metadata={
            "method": method.upper(),
            "url": url,
            "host": host,
            "purpose": purpose,
            "reason": reason,
        },
        request_context=request_context,
        request_id=resolved_request_id,
    )


def validate_outbound_url(
    *,
    method: str,
    url: str,
    purpose: str,
    settings: Settings | None = None,
    actor_user_id: str | None = None,
    request_context: AuditRequestContext | None = None,
    audit_service: AuditService | None = None,
) -> None:
    resolved_settings = settings or get_settings()
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").strip().lower()

    if scheme not in _ALLOWED_SCHEMES or not host:
        reason = "Outbound URL must use HTTP(S) and include a resolvable host."
        _record_blocked_attempt(
            method=method,
            url=url,
            host=host or "__missing__",
            purpose=purpose,
            actor_user_id=actor_user_id,
            request_context=request_context,
            audit_service=audit_service,
            reason=reason,
        )
        raise OutboundRequestBlockedError(
            method=method,
            url=url,
            host=host or "__missing__",
            reason=reason,
        )

    if is_url_allowlisted(url, resolved_settings):
        return

    reason = "Target host is not in the internal outbound allowlist."
    _record_blocked_attempt(
        method=method,
        url=url,
        host=host,
        purpose=purpose,
        actor_user_id=actor_user_id,
        request_context=request_context,
        audit_service=audit_service,
        reason=reason,
    )
    raise OutboundRequestBlockedError(
        method=method,
        url=url,
        host=host,
        reason=reason,
    )


def guarded_http_request(
    *,
    method: str,
    url: str,
    purpose: str,
    settings: Settings | None = None,
    actor_user_id: str | None = None,
    request_context: AuditRequestContext | None = None,
    audit_service: AuditService | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 5.0,
    data: dict[str, str] | None = None,
) -> httpx.Response:
    validate_outbound_url(
        method=method,
        url=url,
        purpose=purpose,
        settings=settings,
        actor_user_id=actor_user_id,
        request_context=request_context,
        audit_service=audit_service,
    )
    return httpx.request(
        method=method,
        url=url,
        headers=headers,
        timeout=timeout,
        data=data,
    )
