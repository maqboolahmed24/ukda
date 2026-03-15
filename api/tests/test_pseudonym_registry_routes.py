from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.audit.service import get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.main import app
from app.pseudonyms.models import (
    PseudonymRegistryEntryEventRecord,
    PseudonymRegistryEntryRecord,
)
from app.pseudonyms.service import (
    PseudonymRegistryAccessDeniedError,
    PseudonymRegistryNotFoundError,
    get_pseudonym_registry_service,
)
from fastapi.testclient import TestClient

client = TestClient(app)


class SpyAuditService:
    def __init__(self) -> None:
        self.recorded: list[dict[str, object]] = []

    def record_event_best_effort(self, **kwargs):  # type: ignore[no-untyped-def]
        self.recorded.append(kwargs)
        return None


class FakePseudonymRegistryService:
    def __init__(self) -> None:
        now = datetime.now(UTC) - timedelta(hours=1)
        self.project_id = "project-1"
        self._entries: dict[str, PseudonymRegistryEntryRecord] = {}
        self._events: list[PseudonymRegistryEntryEventRecord] = []

        seed = PseudonymRegistryEntryRecord(
            id=f"entry-{uuid4()}",
            project_id=self.project_id,
            source_run_id="run-1",
            source_fingerprint_hmac_sha256="a" * 64,
            alias_value="PSN-AAAAAAAAAAAAAAAAAAAA",
            policy_id="policy-p1-v1",
            salt_version_ref="salt-v1",
            alias_strategy_version="v1",
            created_by="user-lead",
            created_at=now,
            last_used_run_id="run-1",
            updated_at=now,
            status="ACTIVE",
            retired_at=None,
            retired_by=None,
            supersedes_entry_id=None,
            superseded_by_entry_id=None,
        )
        self._entries[seed.id] = seed
        self._events.append(
            PseudonymRegistryEntryEventRecord(
                id=f"event-{uuid4()}",
                entry_id=seed.id,
                event_type="ENTRY_CREATED",
                run_id="run-1",
                actor_user_id="user-lead",
                created_at=seed.created_at,
            )
        )
        self._events.append(
            PseudonymRegistryEntryEventRecord(
                id=f"event-{uuid4()}",
                entry_id=seed.id,
                event_type="ENTRY_REUSED",
                run_id="run-2",
                actor_user_id="user-lead",
                created_at=seed.created_at + timedelta(minutes=3),
            )
        )

    def _role_for_user(self, current_user: SessionPrincipal) -> str:
        if "ADMIN" in set(current_user.platform_roles):
            return "ADMIN"
        if "AUDITOR" in set(current_user.platform_roles):
            return "AUDITOR"
        if current_user.user_id == "user-lead":
            return "PROJECT_LEAD"
        if current_user.user_id == "user-reviewer":
            return "REVIEWER"
        return "RESEARCHER"

    def _require_read(self, *, current_user: SessionPrincipal, project_id: str) -> None:
        if project_id != self.project_id:
            raise PseudonymRegistryNotFoundError("Project not found.")
        role = self._role_for_user(current_user)
        if role in {"PROJECT_LEAD", "ADMIN", "AUDITOR"}:
            return
        raise PseudonymRegistryAccessDeniedError(
            "Current role cannot view pseudonym registry routes in this project."
        )

    def list_entries(self, *, current_user: SessionPrincipal, project_id: str):
        self._require_read(current_user=current_user, project_id=project_id)
        rows = [entry for entry in self._entries.values() if entry.project_id == project_id]
        return sorted(rows, key=lambda entry: (entry.created_at, entry.id), reverse=True)

    def get_entry(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        entry_id: str,
    ):
        self._require_read(current_user=current_user, project_id=project_id)
        row = self._entries.get(entry_id)
        if row is None:
            raise PseudonymRegistryNotFoundError("Pseudonym registry entry not found.")
        return row

    def list_entry_events(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        entry_id: str,
    ):
        _ = self.get_entry(
            current_user=current_user,
            project_id=project_id,
            entry_id=entry_id,
        )
        return [event for event in self._events if event.entry_id == entry_id]


def _principal(*, user_id: str, platform_roles: tuple[str, ...] = ()) -> SessionPrincipal:
    now = datetime.now(UTC)
    return SessionPrincipal(
        session_id="session-1",
        auth_source="cookie",
        user_id=user_id,
        oidc_sub=f"oidc|{user_id}",
        email=f"{user_id}@example.test",
        display_name=user_id,
        platform_roles=platform_roles,  # type: ignore[arg-type]
        issued_at=now - timedelta(minutes=5),
        expires_at=now + timedelta(hours=1),
        csrf_token="csrf-token",
    )


@pytest.fixture(autouse=True)
def clear_overrides() -> None:
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_project_lead_can_read_registry_routes_and_audits_registry_events() -> None:
    fake_service = FakePseudonymRegistryService()
    spy_audit = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-lead")
    app.dependency_overrides[get_pseudonym_registry_service] = lambda: fake_service
    app.dependency_overrides[get_audit_service] = lambda: spy_audit

    list_response = client.get("/projects/project-1/pseudonym-registry")
    assert list_response.status_code == 200
    entry_id = list_response.json()["items"][0]["id"]

    detail_response = client.get(f"/projects/project-1/pseudonym-registry/{entry_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == entry_id

    events_response = client.get(f"/projects/project-1/pseudonym-registry/{entry_id}/events")
    assert events_response.status_code == 200
    assert len(events_response.json()["items"]) == 2

    recorded_types = [str(item.get("event_type")) for item in spy_audit.recorded]
    assert "PSEUDONYM_REGISTRY_VIEWED" in recorded_types
    assert "PSEUDONYM_REGISTRY_ENTRY_VIEWED" in recorded_types
    assert "PSEUDONYM_REGISTRY_EVENTS_VIEWED" in recorded_types


def test_auditor_can_read_registry_routes() -> None:
    fake_service = FakePseudonymRegistryService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="user-auditor",
        platform_roles=("AUDITOR",),
    )
    app.dependency_overrides[get_pseudonym_registry_service] = lambda: fake_service

    list_response = client.get("/projects/project-1/pseudonym-registry")
    assert list_response.status_code == 200
    entry_id = list_response.json()["items"][0]["id"]

    detail_response = client.get(f"/projects/project-1/pseudonym-registry/{entry_id}")
    assert detail_response.status_code == 200


def test_reviewer_cannot_read_registry_routes_and_access_denied_is_audited() -> None:
    fake_service = FakePseudonymRegistryService()
    spy_audit = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="user-reviewer"
    )
    app.dependency_overrides[get_pseudonym_registry_service] = lambda: fake_service
    app.dependency_overrides[get_audit_service] = lambda: spy_audit

    response = client.get("/projects/project-1/pseudonym-registry")
    assert response.status_code == 403

    denied_events = [
        item for item in spy_audit.recorded if str(item.get("event_type")) == "ACCESS_DENIED"
    ]
    assert len(denied_events) >= 1


def test_missing_entry_returns_not_found() -> None:
    fake_service = FakePseudonymRegistryService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-lead")
    app.dependency_overrides[get_pseudonym_registry_service] = lambda: fake_service

    response = client.get("/projects/project-1/pseudonym-registry/missing-entry")
    assert response.status_code == 404
