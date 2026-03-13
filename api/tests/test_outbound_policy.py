from dataclasses import dataclass

import pytest
from app.security.outbound import (
    OutboundRequestBlockedError,
    is_url_allowlisted,
    validate_outbound_url,
)


@dataclass
class StubSettings:
    outbound_allowlist: list[str]


class SpyAuditService:
    def __init__(self) -> None:
        self.recorded: list[dict[str, object]] = []

    def record_event_best_effort(self, **kwargs):  # type: ignore[no-untyped-def]
        self.recorded.append(kwargs)
        return None


def test_allowlisted_internal_url_is_permitted() -> None:
    settings = StubSettings(outbound_allowlist=["identity.internal"])  # type: ignore[arg-type]
    assert is_url_allowlisted(
        "https://identity.internal/.well-known/openid-configuration",
        settings,
    )


def test_blocked_public_url_emits_outbound_audit_event() -> None:
    settings = StubSettings(outbound_allowlist=["identity.internal"])  # type: ignore[arg-type]
    spy = SpyAuditService()

    with pytest.raises(OutboundRequestBlockedError):
        validate_outbound_url(
            method="GET",
            url="https://api.openai.com/v1/models",
            purpose="unit_test",
            settings=settings,  # type: ignore[arg-type]
            audit_service=spy,  # type: ignore[arg-type]
        )

    assert len(spy.recorded) == 1
    captured = spy.recorded[0]
    assert captured["event_type"] == "OUTBOUND_CALL_BLOCKED"
    metadata = captured.get("metadata")
    assert isinstance(metadata, dict)
    assert metadata["host"] == "api.openai.com"
