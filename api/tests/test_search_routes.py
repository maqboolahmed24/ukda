from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.audit.service import get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.indexes.models import SearchDocumentRecord
from app.indexes.service import (
    IndexAccessDeniedError,
    IndexConflictError,
    IndexNotFoundError,
    ProjectSearchResult,
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


class FakeSearchService:
    def __init__(self, audit_service: SpyAuditService) -> None:
        now = datetime.now(UTC)
        self._audit_service = audit_service
        self.active_search_index_id: str | None = "search-active"
        self.rows = [
            SearchDocumentRecord(
                id="hit-token",
                search_index_id="search-active",
                document_id="doc-1",
                run_id="run-1",
                page_id="page-1",
                line_id="line-1",
                token_id="token-1",
                source_kind="LINE",
                source_ref_id="line-1",
                page_number=1,
                match_span_json=None,
                token_geometry_json={"x": 1, "y": 2, "w": 3, "h": 4},
                search_text="alpha token",
                search_metadata_json={"confidence": 0.98},
                created_at=now - timedelta(minutes=2),
            ),
            SearchDocumentRecord(
                id="hit-rescue",
                search_index_id="search-active",
                document_id="doc-1",
                run_id="run-1",
                page_id="page-2",
                line_id=None,
                token_id=None,
                source_kind="RESCUE_CANDIDATE",
                source_ref_id="resc-2-9",
                page_number=2,
                match_span_json={"start": 3, "end": 11},
                token_geometry_json=None,
                search_text="alpha rescue",
                search_metadata_json={"confidence": 0.71},
                created_at=now - timedelta(minutes=1),
            ),
            SearchDocumentRecord(
                id="hit-old",
                search_index_id="search-old",
                document_id="doc-9",
                run_id="run-9",
                page_id="page-9",
                line_id="line-9",
                token_id="token-9",
                source_kind="LINE",
                source_ref_id="line-9",
                page_number=9,
                match_span_json=None,
                token_geometry_json={"x": 9, "y": 9, "w": 9, "h": 9},
                search_text="alpha old generation",
                search_metadata_json={},
                created_at=now,
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

    def search_project(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        query_text: str,
        document_id: str | None,
        run_id: str | None,
        page_number: int | None,
        cursor: int,
        limit: int,
    ) -> ProjectSearchResult:
        if project_id != "project-1":
            raise IndexNotFoundError("Project not found.")
        if not self._can_read(current_user):
            raise IndexAccessDeniedError(
                "Current role cannot view project-scoped index metadata routes."
            )
        if self.active_search_index_id is None:
            raise IndexConflictError("No active search index is available for this project.")

        q = query_text.strip().lower()
        candidates = [
            row
            for row in self.rows
            if row.search_index_id == self.active_search_index_id
            and q in row.search_text.lower()
            and (document_id is None or row.document_id == document_id)
            and (run_id is None or row.run_id == run_id)
            and (page_number is None or row.page_number == page_number)
        ]
        ordered = sorted(
            candidates,
            key=lambda row: (row.page_number, row.document_id, row.run_id, row.id),
        )
        window = ordered[cursor : cursor + limit + 1]
        page_items = window[:limit]
        next_cursor = cursor + limit if len(window) > limit else None
        return ProjectSearchResult(
            search_index_id=self.active_search_index_id,
            items=page_items,
            next_cursor=next_cursor,
        )

    def open_search_result(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        search_document_id: str,
        route: str,
    ) -> SearchDocumentRecord:
        if project_id != "project-1":
            raise IndexNotFoundError("Project not found.")
        if not self._can_read(current_user):
            raise IndexAccessDeniedError(
                "Current role cannot view project-scoped index metadata routes."
            )
        if self.active_search_index_id is None:
            raise IndexConflictError("No active search index is available for this project.")
        row = next(
            (
                item
                for item in self.rows
                if item.search_index_id == self.active_search_index_id
                and item.id == search_document_id
            ),
            None,
        )
        if row is None:
            raise IndexNotFoundError("Search result was not found in the active search index.")
        self._audit_service.record_event_best_effort(
            event_type="SEARCH_RESULT_OPENED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            metadata={"route": route, "search_index_id": self.active_search_index_id},
        )
        return row


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


def _install_fakes(current_user: SessionPrincipal) -> tuple[FakeSearchService, SpyAuditService]:
    spy_audit = SpyAuditService()
    fake_service = FakeSearchService(audit_service=spy_audit)
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


def test_search_route_returns_active_generation_hits_only() -> None:
    _service, _audit = _install_fakes(_principal(user_id="user-researcher"))

    response = client.get("/projects/project-1/search?q=alpha")

    assert response.status_code == 200
    payload = response.json()
    assert payload["searchIndexId"] == "search-active"
    assert {item["searchDocumentId"] for item in payload["items"]} == {
        "hit-token",
        "hit-rescue",
    }


def test_search_route_rejects_when_no_active_search_index_exists() -> None:
    service, _audit = _install_fakes(_principal(user_id="user-researcher"))
    service.active_search_index_id = None

    response = client.get("/projects/project-1/search?q=alpha")

    assert response.status_code == 409
    assert "No active search index" in response.json()["detail"]


def test_search_route_blocks_auditor_access() -> None:
    _service, spy_audit = _install_fakes(
        _principal(user_id="user-auditor", platform_roles=("AUDITOR",))
    )

    response = client.get("/projects/project-1/search?q=alpha")

    assert response.status_code == 403
    assert "Current role cannot view" in response.json()["detail"]
    assert "ACCESS_DENIED" in _event_types(spy_audit)


def test_search_route_uses_deterministic_first_page_without_cursor() -> None:
    _service, _audit = _install_fakes(_principal(user_id="user-researcher"))

    without_cursor = client.get("/projects/project-1/search?q=alpha&limit=1")
    with_zero_cursor = client.get("/projects/project-1/search?q=alpha&limit=1&cursor=0")

    assert without_cursor.status_code == 200
    assert with_zero_cursor.status_code == 200
    assert without_cursor.json()["items"][0]["searchDocumentId"] == "hit-token"
    assert with_zero_cursor.json()["items"][0]["searchDocumentId"] == "hit-token"
    assert without_cursor.json()["nextCursor"] == 1


def test_search_route_preserves_token_rescue_and_fallback_fields() -> None:
    _service, _audit = _install_fakes(_principal(user_id="user-researcher"))

    response = client.get("/projects/project-1/search?q=alpha")

    assert response.status_code == 200
    hits = {item["searchDocumentId"]: item for item in response.json()["items"]}

    token_hit = hits["hit-token"]
    assert token_hit["tokenId"] == "token-1"
    assert token_hit["tokenGeometryJson"] == {"x": 1, "y": 2, "w": 3, "h": 4}
    assert token_hit["sourceKind"] == "LINE"

    rescue_hit = hits["hit-rescue"]
    assert rescue_hit["tokenId"] is None
    assert rescue_hit["matchSpanJson"] == {"start": 3, "end": 11}
    assert rescue_hit["sourceKind"] == "RESCUE_CANDIDATE"
    assert rescue_hit["sourceRefId"] == "resc-2-9"


def test_open_search_result_route_returns_workspace_path_and_emits_event() -> None:
    _service, spy_audit = _install_fakes(_principal(user_id="user-researcher"))

    response = client.post("/projects/project-1/search/hit-token/open")

    assert response.status_code == 200
    payload = response.json()
    assert payload["searchDocumentId"] == "hit-token"
    assert (
        payload["workspacePath"]
        == "/projects/project-1/documents/doc-1/transcription/workspace"
        "?lineId=line-1&page=1&runId=run-1&sourceKind=LINE&sourceRefId=line-1&tokenId=token-1"
    )
    assert "SEARCH_RESULT_OPENED" in _event_types(spy_audit)
