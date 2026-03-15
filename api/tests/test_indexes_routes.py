from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.audit.service import get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.indexes.models import (
    ActiveProjectIndexesView,
    IndexKind,
    IndexRecord,
    ProjectIndexProjectionRecord,
)
from app.indexes.service import (
    IndexAccessDeniedError,
    IndexCancelResult,
    IndexConflictError,
    IndexNotFoundError,
    IndexRebuildResult,
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


def _hash_payload(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class FakeIndexService:
    def __init__(self, audit_service: SpyAuditService | None = None) -> None:
        now = datetime.now(UTC)
        self._audit_service = audit_service
        self.rows: dict[IndexKind, dict[str, IndexRecord]] = {
            "SEARCH": {},
            "ENTITY": {},
            "DERIVATIVE": {},
        }
        self.projection = ProjectIndexProjectionRecord(
            project_id="project-1",
            active_search_index_id=None,
            active_entity_index_id=None,
            active_derivative_index_id=None,
            updated_at=now,
        )
        self._seed_row("SEARCH", "search-1", status="SUCCEEDED", version=1)
        self._seed_row("ENTITY", "entity-1", status="SUCCEEDED", version=1)
        self._seed_row("DERIVATIVE", "derivative-1", status="RUNNING", version=1)
        self.projection = replace(
            self.projection,
            active_search_index_id="search-1",
            active_entity_index_id="entity-1",
            updated_at=now,
        )

    @staticmethod
    def _is_admin(current_user: SessionPrincipal) -> bool:
        return "ADMIN" in set(current_user.platform_roles)

    @staticmethod
    def _role_for_user(current_user: SessionPrincipal) -> str:
        if FakeIndexService._is_admin(current_user):
            return "ADMIN"
        if current_user.user_id == "user-lead":
            return "PROJECT_LEAD"
        if current_user.user_id == "user-reviewer":
            return "REVIEWER"
        return "RESEARCHER"

    @staticmethod
    def _require_project(project_id: str) -> None:
        if project_id != "project-1":
            raise IndexNotFoundError("Project not found.")

    def _require_read(self, *, current_user: SessionPrincipal, project_id: str) -> None:
        self._require_project(project_id)
        role = self._role_for_user(current_user)
        if role in {"ADMIN", "PROJECT_LEAD", "RESEARCHER", "REVIEWER"}:
            return
        raise IndexAccessDeniedError(
            "Current role cannot view project-scoped index metadata routes."
        )

    def _require_mutate(self, *, current_user: SessionPrincipal, project_id: str) -> None:
        self._require_project(project_id)
        if self._is_admin(current_user):
            return
        raise IndexAccessDeniedError(
            "Index rebuild, cancel, and activate operations require ADMIN."
        )

    def _seed_row(
        self,
        kind: IndexKind,
        index_id: str,
        *,
        status: str,
        version: int,
    ) -> None:
        now = datetime.now(UTC) - timedelta(minutes=version)
        row = IndexRecord(
            id=index_id,
            project_id="project-1",
            kind=kind,
            version=version,
            source_snapshot_json={"seed": index_id},
            source_snapshot_sha256=_hash_payload({"seed": index_id}),
            build_parameters_json={"pipelineVersion": "10.0"},
            rebuild_dedupe_key=_hash_payload({"kind": kind, "seed": index_id}),
            status=status,  # type: ignore[arg-type]
            supersedes_index_id=None,
            superseded_by_index_id=None,
            failure_reason=None,
            created_by="user-admin",
            created_at=now,
            started_at=now if status != "QUEUED" else None,
            finished_at=now if status in {"SUCCEEDED", "FAILED", "CANCELED"} else None,
            cancel_requested_by=None,
            cancel_requested_at=None,
            canceled_by=None,
            canceled_at=None,
            activated_by="user-admin" if status == "SUCCEEDED" else None,
            activated_at=now if status == "SUCCEEDED" else None,
        )
        self.rows[kind][row.id] = row

    def get_active_indexes(
        self, *, current_user: SessionPrincipal, project_id: str
    ) -> ActiveProjectIndexesView:
        self._require_read(current_user=current_user, project_id=project_id)
        return ActiveProjectIndexesView(
            projection=self.projection,
            search_index=self.rows["SEARCH"].get(self.projection.active_search_index_id or ""),
            entity_index=self.rows["ENTITY"].get(self.projection.active_entity_index_id or ""),
            derivative_index=self.rows["DERIVATIVE"].get(
                self.projection.active_derivative_index_id or ""
            ),
        )

    def list_indexes(
        self, *, current_user: SessionPrincipal, project_id: str, kind: IndexKind
    ) -> list[IndexRecord]:
        self._require_read(current_user=current_user, project_id=project_id)
        return sorted(self.rows[kind].values(), key=lambda row: row.version, reverse=True)

    def get_index(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        kind: IndexKind,
        index_id: str,
    ) -> IndexRecord:
        self._require_read(current_user=current_user, project_id=project_id)
        row = self.rows[kind].get(index_id)
        if row is None:
            raise IndexNotFoundError("Index generation not found.")
        return row

    def rebuild_index(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        kind: IndexKind,
        source_snapshot_json: dict[str, object] | object,
        build_parameters_json: dict[str, object] | object | None = None,
        force: bool = False,
        supersedes_index_id: str | None = None,
    ) -> IndexRebuildResult:
        del supersedes_index_id
        self._require_mutate(current_user=current_user, project_id=project_id)
        source = source_snapshot_json if isinstance(source_snapshot_json, dict) else {}
        params = build_parameters_json if isinstance(build_parameters_json, dict) else {}
        dedupe_key = _hash_payload(
            {
                "project_id": project_id,
                "kind": kind,
                "source_snapshot_sha256": _hash_payload(source),
                "build_parameters": params,
            }
        )
        if not force:
            for row in self.rows[kind].values():
                if row.rebuild_dedupe_key == dedupe_key and row.status in {
                    "QUEUED",
                    "RUNNING",
                    "SUCCEEDED",
                }:
                    return IndexRebuildResult(
                        index=row,
                        created=False,
                        reason=f"EXISTING_{row.status}",
                    )

        next_version = max((row.version for row in self.rows[kind].values()), default=0) + 1
        now = datetime.now(UTC)
        row = IndexRecord(
            id=f"{kind.lower()}-{uuid4()}",
            project_id=project_id,
            kind=kind,
            version=next_version,
            source_snapshot_json=source,
            source_snapshot_sha256=_hash_payload(source),
            build_parameters_json=params,
            rebuild_dedupe_key=dedupe_key,
            status="QUEUED",
            supersedes_index_id=None,
            superseded_by_index_id=None,
            failure_reason=None,
            created_by=current_user.user_id,
            created_at=now,
            started_at=None,
            finished_at=None,
            cancel_requested_by=None,
            cancel_requested_at=None,
            canceled_by=None,
            canceled_at=None,
            activated_by=None,
            activated_at=None,
        )
        self.rows[kind][row.id] = row
        return IndexRebuildResult(index=row, created=True, reason="CREATED")

    def cancel_index(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        kind: IndexKind,
        index_id: str,
    ) -> IndexCancelResult:
        self._require_mutate(current_user=current_user, project_id=project_id)
        row = self.rows[kind].get(index_id)
        if row is None:
            raise IndexNotFoundError("Index generation not found.")
        if row.status == "QUEUED":
            updated = replace(
                row,
                status="CANCELED",
                canceled_by=current_user.user_id,
                canceled_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
            )
            self.rows[kind][row.id] = updated
            return IndexCancelResult(index=updated, terminal=True)
        if row.status == "RUNNING":
            updated = replace(
                row,
                cancel_requested_by=current_user.user_id,
                cancel_requested_at=datetime.now(UTC),
            )
            self.rows[kind][row.id] = updated
            return IndexCancelResult(index=updated, terminal=False)
        raise IndexConflictError("Cancel is allowed only for QUEUED or RUNNING indexes.")

    def activate_index(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        kind: IndexKind,
        index_id: str,
    ) -> tuple[IndexRecord, ProjectIndexProjectionRecord]:
        self._require_mutate(current_user=current_user, project_id=project_id)
        row = self.rows[kind].get(index_id)
        if row is None:
            raise IndexNotFoundError("Index generation not found.")
        if row.status != "SUCCEEDED":
            raise IndexConflictError("Only SUCCEEDED index generations can be activated.")
        updated_row = replace(
            row,
            activated_by=current_user.user_id,
            activated_at=datetime.now(UTC),
        )
        self.rows[kind][row.id] = updated_row
        if kind == "SEARCH":
            self.projection = replace(
                self.projection,
                active_search_index_id=row.id,
                updated_at=datetime.now(UTC),
            )
        elif kind == "ENTITY":
            self.projection = replace(
                self.projection,
                active_entity_index_id=row.id,
                updated_at=datetime.now(UTC),
            )
        else:
            self.projection = replace(
                self.projection,
                active_derivative_index_id=row.id,
                updated_at=datetime.now(UTC),
            )
        return updated_row, self.projection

    @staticmethod
    def _run_created_event(kind: IndexKind) -> str:
        if kind == "SEARCH":
            return "SEARCH_INDEX_RUN_CREATED"
        if kind == "ENTITY":
            return "ENTITY_INDEX_RUN_CREATED"
        return "DERIVATIVE_INDEX_RUN_CREATED"

    @staticmethod
    def _run_canceled_event(kind: IndexKind) -> str:
        if kind == "SEARCH":
            return "SEARCH_INDEX_RUN_CANCELED"
        if kind == "ENTITY":
            return "ENTITY_INDEX_RUN_CANCELED"
        return "DERIVATIVE_INDEX_RUN_CANCELED"

    def record_run_created_audit(self, **kwargs):  # type: ignore[no-untyped-def]
        if self._audit_service is None:
            return None
        kind = kwargs.get("kind")
        if not isinstance(kind, str):
            return None
        index = kwargs.get("index")
        object_id = index.id if isinstance(index, IndexRecord) else None
        self._audit_service.record_event_best_effort(
            event_type=self._run_created_event(kind),  # type: ignore[arg-type]
            actor_user_id=kwargs.get("actor_user_id"),
            project_id=kwargs.get("project_id"),
            object_type="index",
            object_id=object_id,
            metadata={"route": kwargs.get("route", "test")},
        )
        return None

    def record_run_canceled_audit(self, **kwargs):  # type: ignore[no-untyped-def]
        if self._audit_service is None:
            return None
        kind = kwargs.get("kind")
        if not isinstance(kind, str):
            return None
        index = kwargs.get("index")
        object_id = index.id if isinstance(index, IndexRecord) else None
        self._audit_service.record_event_best_effort(
            event_type=self._run_canceled_event(kind),  # type: ignore[arg-type]
            actor_user_id=kwargs.get("actor_user_id"),
            project_id=kwargs.get("project_id"),
            object_type="index",
            object_id=object_id,
            metadata={"route": kwargs.get("route", "test")},
        )
        return None


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


def _install_fakes(current_user: SessionPrincipal) -> tuple[FakeIndexService, SpyAuditService]:
    spy_audit = SpyAuditService()
    fake_service = FakeIndexService(audit_service=spy_audit)
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


def _collection_path(kind: IndexKind) -> str:
    if kind == "SEARCH":
        return "search-indexes"
    if kind == "ENTITY":
        return "entity-indexes"
    return "derivative-indexes"


def test_active_indexes_read_route_allows_researcher_and_emits_audit() -> None:
    _service, spy_audit = _install_fakes(_principal(user_id="user-researcher"))

    response = client.get("/projects/project-1/indexes/active")

    assert response.status_code == 200
    payload = response.json()
    assert payload["projectId"] == "project-1"
    assert payload["projection"]["activeSearchIndexId"] == "search-1"
    assert any(event["event_type"] == "INDEX_ACTIVE_VIEWED" for event in spy_audit.recorded)


def test_rebuild_route_rejects_non_admin_and_emits_access_denied_audit() -> None:
    _service, spy_audit = _install_fakes(_principal(user_id="user-researcher"))

    response = client.post(
        "/projects/project-1/search-indexes/rebuild",
        json={
            "sourceSnapshotJson": {"refs": ["run-1"]},
            "buildParametersJson": {"pipelineVersion": "10.0"},
        },
    )

    assert response.status_code == 403
    assert any(event["event_type"] == "ACCESS_DENIED" for event in spy_audit.recorded)


def test_search_rebuild_route_dedupes_equivalent_requests_without_force() -> None:
    _service, _spy_audit = _install_fakes(
        _principal(user_id="user-admin", platform_roles=("ADMIN",))
    )
    payload = {
        "sourceSnapshotJson": {"refs": ["run-1"]},
        "buildParametersJson": {"pipelineVersion": "10.0"},
    }

    first = client.post("/projects/project-1/search-indexes/rebuild", json=payload)
    second = client.post("/projects/project-1/search-indexes/rebuild", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["created"] is True
    assert second.json()["created"] is False
    assert first.json()["index"]["id"] == second.json()["index"]["id"]


def test_cancel_route_rejects_terminal_status_generations() -> None:
    fake_service, _spy_audit = _install_fakes(
        _principal(user_id="user-admin", platform_roles=("ADMIN",))
    )

    response = client.post("/projects/project-1/search-indexes/search-1/cancel")

    assert response.status_code == 409
    assert response.json()["detail"].startswith("Cancel is allowed only")
    # keep behavior deterministic for this route suite
    assert fake_service.rows["SEARCH"]["search-1"].status == "SUCCEEDED"


def test_activate_route_updates_projection_for_succeeded_generation() -> None:
    fake_service, _spy_audit = _install_fakes(
        _principal(user_id="user-admin", platform_roles=("ADMIN",))
    )
    fake_service._seed_row("SEARCH", "search-2", status="SUCCEEDED", version=2)

    response = client.post("/projects/project-1/search-indexes/search-2/activate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["index"]["id"] == "search-2"
    assert payload["projection"]["activeSearchIndexId"] == "search-2"


@pytest.mark.parametrize(
    ("kind", "index_id", "list_event", "detail_event", "status_event"),
    [
        (
            "SEARCH",
            "search-1",
            "SEARCH_INDEX_LIST_VIEWED",
            "SEARCH_INDEX_DETAIL_VIEWED",
            "SEARCH_INDEX_STATUS_VIEWED",
        ),
        (
            "ENTITY",
            "entity-1",
            "ENTITY_INDEX_LIST_VIEWED",
            "ENTITY_INDEX_DETAIL_VIEWED",
            "ENTITY_INDEX_STATUS_VIEWED",
        ),
        (
            "DERIVATIVE",
            "derivative-1",
            "DERIVATIVE_INDEX_LIST_VIEWED",
            "DERIVATIVE_INDEX_DETAIL_VIEWED",
            "DERIVATIVE_INDEX_STATUS_VIEWED",
        ),
    ],
)
def test_index_read_routes_emit_family_specific_audit_events(
    kind: IndexKind,
    index_id: str,
    list_event: str,
    detail_event: str,
    status_event: str,
) -> None:
    _service, spy_audit = _install_fakes(_principal(user_id="user-lead"))
    collection = _collection_path(kind)

    list_response = client.get(f"/projects/project-1/{collection}")
    detail_response = client.get(f"/projects/project-1/{collection}/{index_id}")
    status_response = client.get(f"/projects/project-1/{collection}/{index_id}/status")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert status_response.status_code == 200
    events = _event_types(spy_audit)
    assert list_event in events
    assert detail_event in events
    assert status_event in events


@pytest.mark.parametrize(
    ("kind", "run_created_event", "run_canceled_event"),
    [
        ("SEARCH", "SEARCH_INDEX_RUN_CREATED", "SEARCH_INDEX_RUN_CANCELED"),
        ("ENTITY", "ENTITY_INDEX_RUN_CREATED", "ENTITY_INDEX_RUN_CANCELED"),
        (
            "DERIVATIVE",
            "DERIVATIVE_INDEX_RUN_CREATED",
            "DERIVATIVE_INDEX_RUN_CANCELED",
        ),
    ],
)
def test_rebuild_and_cancel_routes_emit_family_run_audit_events(
    kind: IndexKind,
    run_created_event: str,
    run_canceled_event: str,
) -> None:
    _service, spy_audit = _install_fakes(
        _principal(user_id="user-admin", platform_roles=("ADMIN",))
    )
    collection = _collection_path(kind)
    payload = {
        "sourceSnapshotJson": {"refs": [f"{kind.lower()}-run"]},
        "buildParametersJson": {"pipelineVersion": "10.0"},
    }

    rebuild = client.post(f"/projects/project-1/{collection}/rebuild", json=payload)
    assert rebuild.status_code == 201
    assert rebuild.json()["created"] is True
    index_id = rebuild.json()["index"]["id"]

    cancel = client.post(f"/projects/project-1/{collection}/{index_id}/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["terminal"] is True

    events = _event_types(spy_audit)
    assert run_created_event in events
    assert run_canceled_event in events
