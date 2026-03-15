from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from threading import RLock

from app.audit.service import AuditService
from app.core.config import Settings, get_settings
from app.security.outbound import (
    OutboundRequestBlockedError,
    is_url_allowlisted,
    validate_outbound_url,
)


@dataclass(frozen=True)
class SecurityStatusSnapshot:
    generated_at: datetime
    environment: str
    deny_by_default_egress: bool
    outbound_allowlist: list[str]
    last_successful_egress_deny_test_at: str | None
    egress_test_detail: str
    csp_mode: str
    last_backup_at: str | None
    reduced_motion_preference_state: str
    reduced_transparency_preference_state: str
    export_gateway_state: str


class SecurityStatusService:
    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings
        self._lock = RLock()
        self._last_successful_egress_deny_test_at: str | None = None
        self._egress_test_detail = "Not yet executed."

    def run_startup_egress_deny_test(self, *, audit_service: AuditService | None = None) -> None:
        with self._lock:
            if audit_service is None:
                if is_url_allowlisted("https://example.com", self._settings):
                    self._egress_test_detail = (
                        "Deny-by-default self-test failed: representative public endpoint was "
                        "allowlisted."
                    )
                    return
                self._last_successful_egress_deny_test_at = datetime.now(UTC).isoformat()
                self._egress_test_detail = (
                    "Deny-by-default policy blocked a representative public endpoint."
                )
                return

            try:
                validate_outbound_url(
                    method="GET",
                    url="https://example.com",
                    purpose="startup_egress_deny_self_test",
                    settings=self._settings,
                    actor_user_id=None,
                    request_context=None,
                    audit_service=audit_service,
                )
            except OutboundRequestBlockedError:
                self._last_successful_egress_deny_test_at = datetime.now(UTC).isoformat()
                self._egress_test_detail = (
                    "Deny-by-default policy blocked a representative public endpoint."
                )
                return

            self._egress_test_detail = (
                "Deny-by-default self-test failed: representative public endpoint was allowed."
            )

    def snapshot(self) -> SecurityStatusSnapshot:
        with self._lock:
            return SecurityStatusSnapshot(
                generated_at=datetime.now(UTC),
                environment=self._settings.environment,
                deny_by_default_egress=True,
                outbound_allowlist=self._settings.outbound_allowlist,
                last_successful_egress_deny_test_at=self._last_successful_egress_deny_test_at,
                egress_test_detail=self._egress_test_detail,
                csp_mode=self._settings.security_csp_mode,
                last_backup_at=self._settings.security_last_backup_at,
                reduced_motion_preference_state="UNAVAILABLE_SERVER_SIDE",
                reduced_transparency_preference_state="UNAVAILABLE_SERVER_SIDE",
                export_gateway_state="ENFORCED_GATEWAY_ONLY",
            )


@lru_cache
def get_security_status_service() -> SecurityStatusService:
    settings = get_settings()
    return SecurityStatusService(settings=settings)
