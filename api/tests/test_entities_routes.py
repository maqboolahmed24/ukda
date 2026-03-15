from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.audit.service import get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.indexes.models import ControlledEntityRecord
from app.indexes.service import (
    EntityOccurrenceLink,
    IndexAccessDeniedError,
    IndexConflictError,
    IndexNotFoundError,
    ProjectEntityDetailResult,
    ProjectEntityListResult,
    ProjectEntityOccurrencesResult,
    get_index_service,
)
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


class SpyAuditService:
    def __init__(self) -> None:
        self.recorded: list[dict[str, object]] = []

    def record_event_best_effort(self, **kwargs):  # type: ignore[no-untyped-def]
        self.recorded.append(kwargs)
        return None


class FakeEntityService:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.active_entity_index_id: str | None = "entity-active"
        self.entities: list[ControlledEntityRecord] = [
            ControlledEntityRecord(
                id="entity-1",
                project_id="project-1",
                entity_index_id="entity-active",
                entity_type="PERSON",
                display_value="John Adams",
                canonical_value="john adams",
                confidence_summary_json={"band": "HIGH", "average": 0.95},
                occurrence_count=2,
                created_at=now - timedelta(minutes=2),
            ),
            ControlledEntityRecord(
                id="entity-2",
                project_id="project-1",
                entity_index_id="entity-active",
                entity_type="PLACE",
                display_value="York",
                canonical_value="york",
                confidence_summary_json={"band": "MEDIUM", "average": 0.72},
                occurrence_count=1,
                created_at=now - timedelta(minutes=1),
            ),
            ControlledEntityRecord(
                id="entity-old",
                project_id="project-1",
                entity_index_id="entity-old",
                entity_type="PERSON",
                display_value="Legacy Person",
                canonical_value="legacy person",
                confidence_summary_json={"band": "LOW", "average": 0.41},
                occurrence_count=1,
                created_at=now - timedelta(minutes=5),
            ),
        ]
        self.occurrences: list[EntityOccurrenceLink] = [
            EntityOccurrenceLink(
                id="occ-1",
                entity_index_id="entity-active",
                entity_id="entity-1",
                document_id="doc-1",
                run_id="run-1",
                page_id="page-1",
                page_number=1,
                line_id="line-1",
                token_id="token-1",
                source_kind="LINE",
                source_ref_id="line-1",
                confidence=0.98,
                occurrence_span_json={"start": 0, "end": 10},
                occurrence_span_basis_kind="LINE_TEXT",
                occurrence_span_basis_ref="line-1",
                token_geometry_json={"x": 1, "y": 2, "w": 3, "h": 4},
            ),
            EntityOccurrenceLink(
                id="occ-2",
                entity_index_id="entity-active",
                entity_id="entity-1",
                document_id="doc-1",
                run_id="run-1",
                page_id="page-2",
                page_number=2,
                line_id=None,
                token_id=None,
                source_kind="PAGE_WINDOW",
                source_ref_id="window-2-3",
                confidence=0.91,
                occurrence_span_json={"start": 8, "end": 19},
                occurrence_span_basis_kind="PAGE_WINDOW_TEXT",
                occurrence_span_basis_ref="window-2-3",
                token_geometry_json=None,
            ),
            EntityOccurrenceLink(
                id="occ-old",
                entity_index_id="entity-old",
                entity_id="entity-old",
                document_id="doc-old",
                run_id="run-old",
                page_id="page-old",
                page_number=9,
                line_id="line-old",
                token_id=None,
                source_kind="LINE",
                source_ref_id="line-old",
                confidence=0.3,
                occurrence_span_json={"start": 0, "end": 5},
                occurrence_span_basis_kind="LINE_TEXT",
                occurrence_span_basis_ref="line-old",
                token_geometry_json=None,
            ),
        ]

    @staticmethod
    def _is_admin(current_user: SessionPrincipal) -> bool:
        return "ADMIN" in set(current_user.platform_roles)

    @classmethod
    def _can_read(cls, current_user: SessionPrincipal) -> bool:
        if cls._is_admin(current_user):
            return True
        if "AUDITOR" in set(current_user.platform_roles):
            return False
        return current_user.user_id in {"user-lead", "user-researcher", "user-reviewer"}

    def _assert_read(self, current_user: SessionPrincipal, project_id: str) -> None:
        if project_id != "project-1":
            raise IndexNotFoundError("Project not found.")
        if not self._can_read(current_user):
            raise IndexAccessDeniedError(
                "Current role cannot view project-scoped index metadata routes."
            )
        if self.active_entity_index_id is None:
            raise IndexConflictError("No active entity index is available for this project.")

    def list_project_entities(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        query_text: str | None,
        entity_type: str | None,
        cursor: int,
        limit: int,
    ) -> ProjectEntityListResult:
        self._assert_read(current_user, project_id)
        assert self.active_entity_index_id is not None
        q = (query_text or "").strip().lower()
        normalized_type = (entity_type or "").strip().upper()
        candidates = [
            row
            for row in self.entities
            if row.entity_index_id == self.active_entity_index_id
            and (not q or q in row.display_value.lower() or q in row.canonical_value.lower())
            and (not normalized_type or row.entity_type == normalized_type)
        ]
        ordered = sorted(candidates, key=lambda row: (row.entity_type, row.canonical_value, row.id))
        window = ordered[cursor : cursor + limit + 1]
        page_items = window[:limit]
        next_cursor = cursor + limit if len(window) > limit else None
        return ProjectEntityListResult(
            entity_index_id=self.active_entity_index_id,
            items=page_items,
            next_cursor=next_cursor,
        )

    def get_project_entity_detail(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        entity_id: str,
    ) -> ProjectEntityDetailResult:
        self._assert_read(current_user, project_id)
        assert self.active_entity_index_id is not None
        entity = next(
            (
                row
                for row in self.entities
                if row.entity_index_id == self.active_entity_index_id and row.id == entity_id
            ),
            None,
        )
        if entity is None:
            raise IndexNotFoundError("Entity was not found in the active entity index.")
        return ProjectEntityDetailResult(
            entity_index_id=self.active_entity_index_id,
            entity=entity,
        )

    def list_project_entity_occurrences(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        entity_id: str,
        cursor: int,
        limit: int,
    ) -> ProjectEntityOccurrencesResult:
        detail = self.get_project_entity_detail(
            current_user=current_user,
            project_id=project_id,
            entity_id=entity_id,
        )
        candidates = [
            row
            for row in self.occurrences
            if row.entity_index_id == detail.entity_index_id and row.entity_id == detail.entity.id
        ]
        ordered = sorted(
            candidates,
            key=lambda row: (row.page_number, row.document_id, row.run_id, row.id),
        )
        window = ordered[cursor : cursor + limit + 1]
        page_items = window[:limit]
        next_cursor = cursor + limit if len(window) > limit else None
        return ProjectEntityOccurrencesResult(
            entity_index_id=detail.entity_index_id,
            entity=detail.entity,
            items=page_items,
            next_cursor=next_cursor,
        )


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:
    yield
    app.dependency_overrides.clear()


def _principal(
    *,
    user_id: str,
    platform_roles: tuple[str, ...] = (),
) -> SessionPrincipal:
    return SessionPrincipal(
        session_id=f"session-{user_id}",
        auth_source="dev",
        user_id=user_id,
        oidc_sub=f"oidc-{user_id}",
        email=f"{user_id}@test.local",
        display_name=user_id,
        platform_roles=platform_roles,  # type: ignore[arg-type]
        issued_at=datetime.now(UTC) - timedelta(minutes=2),
        expires_at=datetime.now(UTC) + timedelta(minutes=58),
        csrf_token="csrf-token",
    )


def _install_fakes(current_user: SessionPrincipal) -> tuple[FakeEntityService, SpyAuditService]:
    spy_audit = SpyAuditService()
    fake_service = FakeEntityService()
    app.dependency_overrides[require_authenticated_user] = lambda: current_user
    app.dependency_overrides[get_index_service] = lambda: fake_service
    app.dependency_overrides[get_audit_service] = lambda: spy_audit
    return fake_service, spy_audit


def _event_types(spy: SpyAuditService) -> set[str]:
    return {
        str(event_type)
        for event in spy.recorded
        if isinstance((event_type := event.get("event_type")), str)
    }


def test_entities_route_returns_active_generation_entities_only() -> None:
    _service, _audit = _install_fakes(_principal(user_id="user-researcher"))

    response = client.get("/projects/project-1/entities?q=adams")

    assert response.status_code == 200
    payload = response.json()
    assert payload["entityIndexId"] == "entity-active"
    assert [item["id"] for item in payload["items"]] == ["entity-1"]


def test_entities_route_rejects_when_no_active_entity_index_exists() -> None:
    service, _audit = _install_fakes(_principal(user_id="user-researcher"))
    service.active_entity_index_id = None

    response = client.get("/projects/project-1/entities?q=adams")

    assert response.status_code == 409
    assert "No active entity index" in response.json()["detail"]


def test_entities_route_blocks_auditor_access() -> None:
    _service, spy_audit = _install_fakes(
        _principal(user_id="user-auditor", platform_roles=("AUDITOR",))
    )

    response = client.get("/projects/project-1/entities?q=adams")

    assert response.status_code == 403
    assert "Current role cannot view" in response.json()["detail"]
    assert "ACCESS_DENIED" in _event_types(spy_audit)


def test_entity_detail_and_occurrences_stay_on_same_active_generation() -> None:
    _service, spy_audit = _install_fakes(_principal(user_id="user-reviewer"))

    detail_response = client.get("/projects/project-1/entities/entity-1")
    occurrences_response = client.get("/projects/project-1/entities/entity-1/occurrences")

    assert detail_response.status_code == 200
    assert occurrences_response.status_code == 200
    detail_payload = detail_response.json()
    occurrences_payload = occurrences_response.json()
    assert detail_payload["entityIndexId"] == "entity-active"
    assert occurrences_payload["entityIndexId"] == "entity-active"
    assert occurrences_payload["items"][0]["workspacePath"].startswith(
        "/projects/project-1/documents/doc-1/transcription/workspace?"
    )
    events = _event_types(spy_audit)
    assert "ENTITY_DETAIL_VIEWED" in events
    assert "ENTITY_OCCURRENCES_VIEWED" in events
