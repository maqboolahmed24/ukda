from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from app.auth.models import SessionPrincipal
from app.core.config import get_settings
from app.indexes.models import (
    ProjectIndexProjectionRecord,
    SearchDocumentPage,
    SearchDocumentRecord,
)
from app.indexes.service import (
    IndexAccessDeniedError,
    IndexConflictError,
    IndexService,
)
from app.projects.models import ProjectSummary


class SpyAuditService:
    def __init__(self) -> None:
        self.recorded: list[dict[str, object]] = []

    def record_event_best_effort(self, **kwargs):  # type: ignore[no-untyped-def]
        self.recorded.append(kwargs)
        return None


class FakeProjectStore:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.summary = ProjectSummary(
            id="project-1",
            name="Search tests",
            purpose="Prompt 89 controlled full-text search service validation.",
            status="ACTIVE",
            created_by="user-lead",
            created_at=now - timedelta(days=3),
            intended_access_tier="CONTROLLED",
            baseline_policy_snapshot_id="baseline-phase0-v1",
            current_user_role=None,
        )
        self.member_roles = {
            "user-lead": "PROJECT_LEAD",
            "user-researcher": "RESEARCHER",
            "user-reviewer": "REVIEWER",
        }

    def get_project_summary_for_user(
        self, *, project_id: str, user_id: str
    ) -> ProjectSummary | None:
        if project_id != self.summary.id:
            return None
        role = self.member_roles.get(user_id)
        if role is None:
            return None
        return replace(self.summary, current_user_role=role)  # type: ignore[arg-type]

    def get_project_summary(self, *, project_id: str) -> ProjectSummary | None:
        if project_id != self.summary.id:
            return None
        return replace(self.summary)


class FakeSearchStore:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.projection: ProjectIndexProjectionRecord | None = ProjectIndexProjectionRecord(
            project_id="project-1",
            active_search_index_id="search-active",
            active_entity_index_id=None,
            active_derivative_index_id=None,
            updated_at=now,
        )
        self.documents = [
            SearchDocumentRecord(
                id="hit-1",
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
                search_metadata_json={"confidence": 0.99},
                created_at=now - timedelta(minutes=2),
            ),
            SearchDocumentRecord(
                id="hit-2",
                search_index_id="search-active",
                document_id="doc-2",
                run_id="run-2",
                page_id="page-2",
                line_id=None,
                token_id=None,
                source_kind="PAGE_WINDOW",
                source_ref_id="window-2",
                page_number=2,
                match_span_json={"start": 4, "end": 10},
                token_geometry_json=None,
                search_text="alpha fallback",
                search_metadata_json={},
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
        self.query_audits: list[dict[str, object]] = []

    def get_projection(self, *, project_id: str) -> ProjectIndexProjectionRecord | None:
        if project_id != "project-1":
            return None
        return self.projection

    def list_search_documents_for_index(
        self,
        *,
        search_index_id: str,
        query_text: str,
        document_id: str | None,
        run_id: str | None,
        page_number: int | None,
        cursor: int,
        limit: int,
    ) -> SearchDocumentPage:
        q = query_text.strip().lower()
        candidates = [
            row
            for row in self.documents
            if row.search_index_id == search_index_id
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
        return SearchDocumentPage(items=page_items, next_cursor=next_cursor)

    def get_search_document_for_index(
        self,
        *,
        search_index_id: str,
        search_document_id: str,
    ) -> SearchDocumentRecord | None:
        return next(
            (
                row
                for row in self.documents
                if row.search_index_id == search_index_id and row.id == search_document_id
            ),
            None,
        )

    def store_search_query_text(self, *, project_id: str, query_text: str) -> str:
        key = f"query:{project_id}:{len(self.query_audits) + 1}"
        self.query_audits.append(
            {
                "project_id": project_id,
                "query_text": query_text,
                "query_text_key": key,
            }
        )
        return key

    def append_search_query_audit(
        self,
        *,
        project_id: str,
        actor_user_id: str,
        search_index_id: str,
        query_sha256: str,
        query_text_key: str,
        filters_json: dict[str, object],
        result_count: int,
    ) -> None:
        self.query_audits.append(
            {
                "project_id": project_id,
                "actor_user_id": actor_user_id,
                "search_index_id": search_index_id,
                "query_sha256": query_sha256,
                "query_text_key": query_text_key,
                "filters_json": filters_json,
                "result_count": result_count,
            }
        )


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


def _service() -> tuple[IndexService, FakeSearchStore, SpyAuditService]:
    store = FakeSearchStore()
    audit = SpyAuditService()
    service = IndexService(
        settings=get_settings(),
        store=store,  # type: ignore[arg-type]
        project_store=FakeProjectStore(),  # type: ignore[arg-type]
        audit_service=audit,  # type: ignore[arg-type]
    )
    return service, store, audit


def _event_types(spy: SpyAuditService) -> set[str]:
    return {
        str(event_type)
        for event in spy.recorded
        if isinstance((event_type := event.get("event_type")), str)
    }


def test_search_service_requires_active_search_index() -> None:
    service, store, _audit = _service()
    store.projection = replace(store.projection, active_search_index_id=None)  # type: ignore[arg-type]

    with pytest.raises(IndexConflictError):
        service.search_project(
            current_user=_principal(user_id="user-researcher"),
            project_id="project-1",
            query_text="alpha",
            document_id=None,
            run_id=None,
            page_number=None,
            cursor=0,
            limit=25,
        )


def test_search_service_scopes_results_to_active_generation() -> None:
    service, _store, _audit = _service()

    page = service.search_project(
        current_user=_principal(user_id="user-researcher"),
        project_id="project-1",
        query_text="alpha",
        document_id=None,
        run_id=None,
        page_number=None,
        cursor=0,
        limit=10,
    )

    assert page.search_index_id == "search-active"
    assert [item.id for item in page.items] == ["hit-1", "hit-2"]
    assert page.next_cursor is None


def test_open_search_result_records_audit_event() -> None:
    service, _store, audit = _service()

    hit = service.open_search_result(
        current_user=_principal(user_id="user-researcher"),
        project_id="project-1",
        search_document_id="hit-1",
        route="/projects/{project_id}/search/{search_document_id}/open",
    )

    assert hit.id == "hit-1"
    assert "SEARCH_RESULT_OPENED" in _event_types(audit)


def test_search_service_blocks_auditor_access() -> None:
    service, _store, _audit = _service()

    with pytest.raises(IndexAccessDeniedError):
        service.search_project(
            current_user=_principal(user_id="user-auditor", platform_roles=("AUDITOR",)),
            project_id="project-1",
            query_text="alpha",
            document_id=None,
            run_id=None,
            page_number=None,
            cursor=0,
            limit=25,
        )
