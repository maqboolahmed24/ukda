from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from app.auth.models import SessionPrincipal
from app.core.config import get_settings
from app.indexes.models import (
    ControlledEntityRecord,
    EntityOccurrenceRecord,
    IndexKind,
    IndexRecord,
    ProjectIndexProjectionRecord,
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
            name="Index service tests",
            purpose="Prompt 88 deterministic index service lifecycle validation.",
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


class FakeIndexStore:
    def __init__(self) -> None:
        self.indexes: dict[IndexKind, dict[str, IndexRecord]] = {
            "SEARCH": {},
            "ENTITY": {},
            "DERIVATIVE": {},
        }
        self.controlled_entities: dict[str, list[ControlledEntityRecord]] = {}
        self.entity_occurrences: dict[str, list[EntityOccurrenceRecord]] = {}
        self.projections: dict[str, ProjectIndexProjectionRecord] = {}

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def list_indexes(self, *, project_id: str, kind: IndexKind) -> list[IndexRecord]:
        rows = [row for row in self.indexes[kind].values() if row.project_id == project_id]
        return sorted(rows, key=lambda row: row.version, reverse=True)

    def get_index(
        self,
        *,
        project_id: str,
        kind: IndexKind,
        index_id: str,
    ) -> IndexRecord | None:
        row = self.indexes[kind].get(index_id)
        if row is None or row.project_id != project_id:
            return None
        return row

    def get_projection(self, *, project_id: str) -> ProjectIndexProjectionRecord | None:
        return self.projections.get(project_id)

    def find_equivalent_index(
        self,
        *,
        project_id: str,
        kind: IndexKind,
        rebuild_dedupe_key: str,
    ) -> IndexRecord | None:
        candidates = [
            row
            for row in self.indexes[kind].values()
            if row.project_id == project_id
            and row.rebuild_dedupe_key == rebuild_dedupe_key
            and row.status in {"QUEUED", "RUNNING", "SUCCEEDED"}
        ]
        if not candidates:
            return None
        return sorted(candidates, key=lambda row: row.version, reverse=True)[0]

    def create_index_generation(
        self,
        *,
        project_id: str,
        kind: IndexKind,
        index_id: str,
        source_snapshot_json: dict[str, object],
        source_snapshot_sha256: str,
        build_parameters_json: dict[str, object],
        rebuild_dedupe_key: str,
        created_by: str,
        supersedes_index_id: str | None,
    ) -> IndexRecord:
        next_version = (
            max((row.version for row in self.indexes[kind].values()), default=0) + 1
        )
        created_at = self._now()
        row = IndexRecord(
            id=index_id,
            project_id=project_id,
            kind=kind,
            version=next_version,
            source_snapshot_json=dict(source_snapshot_json),
            source_snapshot_sha256=source_snapshot_sha256,
            build_parameters_json=dict(build_parameters_json),
            rebuild_dedupe_key=rebuild_dedupe_key,
            status="QUEUED",
            supersedes_index_id=supersedes_index_id,
            superseded_by_index_id=None,
            failure_reason=None,
            created_by=created_by,
            created_at=created_at,
            started_at=None,
            finished_at=None,
            cancel_requested_by=None,
            cancel_requested_at=None,
            canceled_by=None,
            canceled_at=None,
            activated_by=None,
            activated_at=None,
        )
        self.indexes[kind][row.id] = row
        if supersedes_index_id and supersedes_index_id in self.indexes[kind]:
            superseded = self.indexes[kind][supersedes_index_id]
            if superseded.superseded_by_index_id is None:
                self.indexes[kind][supersedes_index_id] = replace(
                    superseded, superseded_by_index_id=row.id
                )
        return row

    def cancel_queued(
        self,
        *,
        project_id: str,
        kind: IndexKind,
        index_id: str,
        canceled_by: str,
        canceled_at: datetime | None = None,
    ) -> IndexRecord | None:
        row = self.get_index(project_id=project_id, kind=kind, index_id=index_id)
        if row is None or row.status != "QUEUED":
            return None
        now = canceled_at or self._now()
        updated = replace(
            row,
            status="CANCELED",
            canceled_by=canceled_by,
            canceled_at=now,
            finished_at=now,
        )
        self.indexes[kind][row.id] = updated
        return updated

    def request_running_cancel(
        self,
        *,
        project_id: str,
        kind: IndexKind,
        index_id: str,
        requested_by: str,
        requested_at: datetime | None = None,
    ) -> IndexRecord | None:
        row = self.get_index(project_id=project_id, kind=kind, index_id=index_id)
        if row is None or row.status != "RUNNING":
            return None
        now = requested_at or self._now()
        updated = replace(
            row,
            cancel_requested_by=row.cancel_requested_by or requested_by,
            cancel_requested_at=row.cancel_requested_at or now,
        )
        self.indexes[kind][row.id] = updated
        return updated

    def set_activation_metadata(
        self,
        *,
        project_id: str,
        kind: IndexKind,
        index_id: str,
        activated_by: str,
        activated_at: datetime | None = None,
    ) -> IndexRecord | None:
        row = self.get_index(project_id=project_id, kind=kind, index_id=index_id)
        if row is None:
            return None
        updated = replace(
            row,
            activated_by=activated_by,
            activated_at=activated_at or self._now(),
        )
        self.indexes[kind][row.id] = updated
        return updated

    def upsert_projection(
        self,
        *,
        project_id: str,
        active_search_index_id: str | None,
        active_entity_index_id: str | None,
        active_derivative_index_id: str | None,
        updated_at: datetime | None = None,
    ) -> ProjectIndexProjectionRecord:
        projection = ProjectIndexProjectionRecord(
            project_id=project_id,
            active_search_index_id=active_search_index_id,
            active_entity_index_id=active_entity_index_id,
            active_derivative_index_id=active_derivative_index_id,
            updated_at=updated_at or self._now(),
        )
        self.projections[project_id] = projection
        return projection

    def mark_running(
        self,
        *,
        project_id: str,
        kind: IndexKind,
        index_id: str,
        started_at: datetime | None = None,
    ) -> IndexRecord | None:
        row = self.get_index(project_id=project_id, kind=kind, index_id=index_id)
        if row is None or row.status != "QUEUED":
            return None
        updated = replace(
            row,
            status="RUNNING",
            started_at=row.started_at or started_at or self._now(),
            failure_reason=None,
        )
        self.indexes[kind][row.id] = updated
        return updated

    def mark_succeeded(
        self,
        *,
        project_id: str,
        kind: IndexKind,
        index_id: str,
        finished_at: datetime | None = None,
    ) -> IndexRecord | None:
        row = self.get_index(project_id=project_id, kind=kind, index_id=index_id)
        if row is None or row.status != "RUNNING":
            return None
        updated = replace(
            row,
            status="SUCCEEDED",
            finished_at=finished_at or self._now(),
            failure_reason=None,
        )
        self.indexes[kind][row.id] = updated
        return updated

    def mark_failed(
        self,
        *,
        project_id: str,
        kind: IndexKind,
        index_id: str,
        failure_reason: str,
        finished_at: datetime | None = None,
    ) -> IndexRecord | None:
        row = self.get_index(project_id=project_id, kind=kind, index_id=index_id)
        if row is None or row.status != "RUNNING":
            return None
        updated = replace(
            row,
            status="FAILED",
            finished_at=finished_at or self._now(),
            failure_reason=failure_reason,
        )
        self.indexes[kind][row.id] = updated
        return updated

    def cancel_running(
        self,
        *,
        project_id: str,
        kind: IndexKind,
        index_id: str,
        canceled_by: str,
        canceled_at: datetime | None = None,
    ) -> IndexRecord | None:
        row = self.get_index(project_id=project_id, kind=kind, index_id=index_id)
        if row is None or row.status != "RUNNING":
            return None
        now = canceled_at or self._now()
        updated = replace(
            row,
            status="CANCELED",
            canceled_by=canceled_by,
            canceled_at=now,
            finished_at=now,
        )
        self.indexes[kind][row.id] = updated
        return updated

    def list_all_controlled_entities_for_index(
        self,
        *,
        entity_index_id: str,
    ) -> list[ControlledEntityRecord]:
        return list(self.controlled_entities.get(entity_index_id, []))

    def list_all_entity_occurrences_for_index(
        self,
        *,
        entity_index_id: str,
    ) -> list[EntityOccurrenceRecord]:
        return list(self.entity_occurrences.get(entity_index_id, []))


def _principal(
    *,
    user_id: str,
    project_role: str | None = None,
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


def _service() -> tuple[IndexService, FakeIndexStore, SpyAuditService]:
    store = FakeIndexStore()
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


def test_dedupe_key_is_reproducible_for_same_inputs() -> None:
    source_snapshot = {"refs": ["run-1"], "scope": "project"}
    build_params = {"includeTokenAnchors": True, "pipelineVersion": "10.0"}

    key1 = IndexService.compute_rebuild_dedupe_key(
        project_id="project-1",
        kind="SEARCH",
        source_snapshot_sha256=IndexService.compute_source_snapshot_sha256(source_snapshot),
        build_parameters_json=build_params,
    )
    key2 = IndexService.compute_rebuild_dedupe_key(
        project_id="project-1",
        kind="SEARCH",
        source_snapshot_sha256=IndexService.compute_source_snapshot_sha256(source_snapshot),
        build_parameters_json=build_params,
    )

    assert key1 == key2


def test_equivalent_rebuild_reuses_existing_generation_when_force_is_false() -> None:
    service, _store, _audit = _service()
    admin = _principal(user_id="user-admin", platform_roles=("ADMIN",))
    payload_snapshot = {"refs": ["run-1"], "scope": "project"}
    payload_params = {"pipelineVersion": "10.0"}

    created = service.rebuild_index(
        current_user=admin,
        project_id="project-1",
        kind="SEARCH",
        source_snapshot_json=payload_snapshot,
        build_parameters_json=payload_params,
    )
    reused = service.rebuild_index(
        current_user=admin,
        project_id="project-1",
        kind="SEARCH",
        source_snapshot_json=payload_snapshot,
        build_parameters_json=payload_params,
    )

    assert created.created is True
    assert reused.created is False
    assert created.index.id == reused.index.id
    assert reused.reason == "EXISTING_QUEUED"


def test_failed_generation_does_not_change_active_projection_pointer() -> None:
    service, store, _audit = _service()
    admin = _principal(user_id="user-admin", platform_roles=("ADMIN",))

    first = service.rebuild_index(
        current_user=admin,
        project_id="project-1",
        kind="SEARCH",
        source_snapshot_json={"refs": ["run-a"]},
        build_parameters_json={"pipelineVersion": "10.0"},
    )
    service.mark_index_started(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="SEARCH",
        index_id=first.index.id,
    )
    service.mark_index_finished(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="SEARCH",
        index_id=first.index.id,
    )
    service.activate_index(
        current_user=admin,
        project_id="project-1",
        kind="SEARCH",
        index_id=first.index.id,
    )

    second = service.rebuild_index(
        current_user=admin,
        project_id="project-1",
        kind="SEARCH",
        source_snapshot_json={"refs": ["run-b"]},
        build_parameters_json={"pipelineVersion": "10.1"},
    )
    service.mark_index_started(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="SEARCH",
        index_id=second.index.id,
    )
    service.mark_index_failed(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="SEARCH",
        index_id=second.index.id,
        failure_reason="synthetic failure",
    )

    projection = store.get_projection(project_id="project-1")
    assert projection is not None
    assert projection.active_search_index_id == first.index.id


def test_canceled_generation_does_not_change_active_projection_pointer() -> None:
    service, store, _audit = _service()
    admin = _principal(user_id="user-admin", platform_roles=("ADMIN",))

    first = service.rebuild_index(
        current_user=admin,
        project_id="project-1",
        kind="ENTITY",
        source_snapshot_json={"refs": ["run-a"]},
        build_parameters_json={"pipelineVersion": "10.0"},
    )
    service.mark_index_started(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="ENTITY",
        index_id=first.index.id,
    )
    service.mark_index_finished(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="ENTITY",
        index_id=first.index.id,
    )
    service.activate_index(
        current_user=admin,
        project_id="project-1",
        kind="ENTITY",
        index_id=first.index.id,
    )

    second = service.rebuild_index(
        current_user=admin,
        project_id="project-1",
        kind="ENTITY",
        source_snapshot_json={"refs": ["run-b"]},
        build_parameters_json={"pipelineVersion": "10.1"},
    )
    cancel_result = service.cancel_index(
        current_user=admin,
        project_id="project-1",
        kind="ENTITY",
        index_id=second.index.id,
    )
    assert cancel_result.terminal is True
    projection = store.get_projection(project_id="project-1")
    assert projection is not None
    assert projection.active_entity_index_id == first.index.id


def test_cancel_is_allowed_only_for_queued_or_running_generations() -> None:
    service, _store, _audit = _service()
    admin = _principal(user_id="user-admin", platform_roles=("ADMIN",))

    queued = service.rebuild_index(
        current_user=admin,
        project_id="project-1",
        kind="DERIVATIVE",
        source_snapshot_json={"refs": ["run-queued"]},
        build_parameters_json={"pipelineVersion": "10.0"},
    )
    queued_cancel = service.cancel_index(
        current_user=admin,
        project_id="project-1",
        kind="DERIVATIVE",
        index_id=queued.index.id,
    )
    assert queued_cancel.terminal is True
    assert queued_cancel.index.status == "CANCELED"

    running = service.rebuild_index(
        current_user=admin,
        project_id="project-1",
        kind="DERIVATIVE",
        source_snapshot_json={"refs": ["run-running"]},
        build_parameters_json={"pipelineVersion": "10.1"},
    )
    service.mark_index_started(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="DERIVATIVE",
        index_id=running.index.id,
    )
    running_cancel = service.cancel_index(
        current_user=admin,
        project_id="project-1",
        kind="DERIVATIVE",
        index_id=running.index.id,
    )
    assert running_cancel.terminal is False
    assert running_cancel.index.status == "RUNNING"
    assert running_cancel.index.cancel_requested is True

    service.mark_index_failed(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="DERIVATIVE",
        index_id=running.index.id,
        failure_reason="synthetic failure",
    )
    with pytest.raises(IndexConflictError):
        service.cancel_index(
            current_user=admin,
            project_id="project-1",
            kind="DERIVATIVE",
            index_id=running.index.id,
        )


def test_activation_updates_projection_and_rollback_reactivates_prior_generation() -> None:
    service, store, _audit = _service()
    admin = _principal(user_id="user-admin", platform_roles=("ADMIN",))

    run1 = service.rebuild_index(
        current_user=admin,
        project_id="project-1",
        kind="SEARCH",
        source_snapshot_json={"refs": ["run-1"]},
        build_parameters_json={"pipelineVersion": "10.0"},
    )
    service.mark_index_started(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="SEARCH",
        index_id=run1.index.id,
    )
    service.mark_index_finished(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="SEARCH",
        index_id=run1.index.id,
    )
    service.activate_index(
        current_user=admin,
        project_id="project-1",
        kind="SEARCH",
        index_id=run1.index.id,
    )
    run2 = service.rebuild_index(
        current_user=admin,
        project_id="project-1",
        kind="SEARCH",
        source_snapshot_json={"refs": ["run-2"]},
        build_parameters_json={"pipelineVersion": "10.1"},
    )
    service.mark_index_started(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="SEARCH",
        index_id=run2.index.id,
    )
    service.mark_index_finished(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="SEARCH",
        index_id=run2.index.id,
    )
    service.activate_index(
        current_user=admin,
        project_id="project-1",
        kind="SEARCH",
        index_id=run2.index.id,
    )

    before_rollback_count = len(store.indexes["SEARCH"])
    rollback_index, rollback_projection = service.activate_index(
        current_user=admin,
        project_id="project-1",
        kind="SEARCH",
        index_id=run1.index.id,
    )
    after_rollback_count = len(store.indexes["SEARCH"])

    assert rollback_index.id == run1.index.id
    assert rollback_projection.active_search_index_id == run1.index.id
    assert before_rollback_count == after_rollback_count


def test_entity_activation_blocks_when_canonicalization_validation_fails() -> None:
    service, store, _audit = _service()
    admin = _principal(user_id="user-admin", platform_roles=("ADMIN",))

    run = service.rebuild_index(
        current_user=admin,
        project_id="project-1",
        kind="ENTITY",
        source_snapshot_json={"eligibleInputCount": 1, "coveredInputCount": 1},
        build_parameters_json={"pipelineVersion": "10.2"},
    )
    service.mark_index_started(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="ENTITY",
        index_id=run.index.id,
    )
    service.mark_index_finished(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="ENTITY",
        index_id=run.index.id,
    )

    store.controlled_entities[run.index.id] = [
        ControlledEntityRecord(
            id="entity-1",
            project_id="project-1",
            entity_index_id=run.index.id,
            entity_type="PERSON",
            display_value="John Adams",
            canonical_value="john-adams",
            confidence_summary_json={"band": "HIGH"},
            occurrence_count=1,
            created_at=datetime.now(UTC),
        )
    ]

    with pytest.raises(IndexConflictError, match="canonicalization"):
        service.activate_index(
            current_user=admin,
            project_id="project-1",
            kind="ENTITY",
            index_id=run.index.id,
        )


def test_entity_activation_blocks_when_occurrence_provenance_is_incomplete() -> None:
    service, store, _audit = _service()
    admin = _principal(user_id="user-admin", platform_roles=("ADMIN",))

    run = service.rebuild_index(
        current_user=admin,
        project_id="project-1",
        kind="ENTITY",
        source_snapshot_json={"eligibleInputCount": 1, "coveredInputCount": 1},
        build_parameters_json={"pipelineVersion": "10.2"},
    )
    service.mark_index_started(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="ENTITY",
        index_id=run.index.id,
    )
    service.mark_index_finished(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="ENTITY",
        index_id=run.index.id,
    )

    store.controlled_entities[run.index.id] = [
        ControlledEntityRecord(
            id="entity-1",
            project_id="project-1",
            entity_index_id=run.index.id,
            entity_type="PERSON",
            display_value="John Adams",
            canonical_value="john adams",
            confidence_summary_json={"band": "HIGH"},
            occurrence_count=1,
            created_at=datetime.now(UTC),
        )
    ]
    store.entity_occurrences[run.index.id] = [
        EntityOccurrenceRecord(
            id="occ-1",
            entity_index_id=run.index.id,
            entity_id="entity-1",
            document_id="doc-1",
            run_id="run-1",
            page_id="page-1",
            line_id=None,
            token_id=None,
            source_kind="LINE",
            source_ref_id="line-1",
            page_number=1,
            confidence=0.95,
            occurrence_span_json={"start": 0, "end": 10},
            occurrence_span_basis_kind="LINE_TEXT",
            occurrence_span_basis_ref="line-1",
            token_geometry_json=None,
            created_at=datetime.now(UTC),
        )
    ]

    with pytest.raises(IndexConflictError, match="occurrence-provenance"):
        service.activate_index(
            current_user=admin,
            project_id="project-1",
            kind="ENTITY",
            index_id=run.index.id,
        )


def test_entity_activation_blocks_when_eligible_input_coverage_gate_fails() -> None:
    service, store, _audit = _service()
    admin = _principal(user_id="user-admin", platform_roles=("ADMIN",))

    run = service.rebuild_index(
        current_user=admin,
        project_id="project-1",
        kind="ENTITY",
        source_snapshot_json={"eligibleInputCount": 6, "coveredInputCount": 2},
        build_parameters_json={"pipelineVersion": "10.2"},
    )
    service.mark_index_started(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="ENTITY",
        index_id=run.index.id,
    )
    service.mark_index_finished(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="ENTITY",
        index_id=run.index.id,
    )

    store.controlled_entities[run.index.id] = [
        ControlledEntityRecord(
            id="entity-1",
            project_id="project-1",
            entity_index_id=run.index.id,
            entity_type="PERSON",
            display_value="John Adams",
            canonical_value="john adams",
            confidence_summary_json={"band": "HIGH"},
            occurrence_count=1,
            created_at=datetime.now(UTC),
        )
    ]
    store.entity_occurrences[run.index.id] = [
        EntityOccurrenceRecord(
            id="occ-1",
            entity_index_id=run.index.id,
            entity_id="entity-1",
            document_id="doc-1",
            run_id="run-1",
            page_id="page-1",
            line_id="line-1",
            token_id="token-1",
            source_kind="LINE",
            source_ref_id="line-1",
            page_number=1,
            confidence=0.95,
            occurrence_span_json={"start": 0, "end": 10},
            occurrence_span_basis_kind="LINE_TEXT",
            occurrence_span_basis_ref="line-1",
            token_geometry_json={"x": 1, "y": 2},
            created_at=datetime.now(UTC),
        )
    ]

    with pytest.raises(IndexConflictError, match="eligible-input coverage"):
        service.activate_index(
            current_user=admin,
            project_id="project-1",
            kind="ENTITY",
            index_id=run.index.id,
        )


def test_role_boundaries_allow_reads_for_members_but_mutations_only_for_admin() -> None:
    service, _store, _audit = _service()
    researcher = _principal(user_id="user-researcher")
    admin = _principal(user_id="user-admin", platform_roles=("ADMIN",))

    created = service.rebuild_index(
        current_user=admin,
        project_id="project-1",
        kind="SEARCH",
        source_snapshot_json={"refs": ["run-1"]},
        build_parameters_json={"pipelineVersion": "10.0"},
    )
    rows = service.list_indexes(
        current_user=researcher,
        project_id="project-1",
        kind="SEARCH",
    )
    assert [row.id for row in rows] == [created.index.id]

    with pytest.raises(IndexAccessDeniedError):
        service.rebuild_index(
            current_user=researcher,
            project_id="project-1",
            kind="SEARCH",
            source_snapshot_json={"refs": ["run-2"]},
            build_parameters_json={"pipelineVersion": "10.1"},
        )


def test_worker_lifecycle_audit_events_cover_all_index_families() -> None:
    service, _store, audit = _service()
    admin = _principal(user_id="user-admin", platform_roles=("ADMIN",))

    for kind in ("SEARCH", "ENTITY", "DERIVATIVE"):
        success = service.rebuild_index(
            current_user=admin,
            project_id="project-1",
            kind=kind,
            source_snapshot_json={"refs": [f"{kind.lower()}-success"]},
            build_parameters_json={"pipelineVersion": "10.0"},
        )
        service.mark_index_started(
            actor_user_id="worker-1",
            project_id="project-1",
            kind=kind,
            index_id=success.index.id,
        )
        service.mark_index_finished(
            actor_user_id="worker-1",
            project_id="project-1",
            kind=kind,
            index_id=success.index.id,
        )

        failed = service.rebuild_index(
            current_user=admin,
            project_id="project-1",
            kind=kind,
            source_snapshot_json={"refs": [f"{kind.lower()}-failed"]},
            build_parameters_json={"pipelineVersion": "10.1"},
        )
        service.mark_index_started(
            actor_user_id="worker-1",
            project_id="project-1",
            kind=kind,
            index_id=failed.index.id,
        )
        service.mark_index_failed(
            actor_user_id="worker-1",
            project_id="project-1",
            kind=kind,
            index_id=failed.index.id,
            failure_reason="synthetic failure",
        )

        canceled = service.rebuild_index(
            current_user=admin,
            project_id="project-1",
            kind=kind,
            source_snapshot_json={"refs": [f"{kind.lower()}-canceled"]},
            build_parameters_json={"pipelineVersion": "10.2"},
        )
        service.mark_index_started(
            actor_user_id="worker-1",
            project_id="project-1",
            kind=kind,
            index_id=canceled.index.id,
        )
        service.cancel_index(
            current_user=admin,
            project_id="project-1",
            kind=kind,
            index_id=canceled.index.id,
        )
        service.mark_index_finished(
            actor_user_id="worker-1",
            project_id="project-1",
            kind=kind,
            index_id=canceled.index.id,
        )

    events = _event_types(audit)
    assert "SEARCH_INDEX_RUN_STARTED" in events
    assert "SEARCH_INDEX_RUN_FINISHED" in events
    assert "SEARCH_INDEX_RUN_FAILED" in events
    assert "SEARCH_INDEX_RUN_CANCELED" in events
    assert "ENTITY_INDEX_RUN_STARTED" in events
    assert "ENTITY_INDEX_RUN_FINISHED" in events
    assert "ENTITY_INDEX_RUN_FAILED" in events
    assert "ENTITY_INDEX_RUN_CANCELED" in events
    assert "DERIVATIVE_INDEX_RUN_STARTED" in events
    assert "DERIVATIVE_INDEX_RUN_FINISHED" in events
    assert "DERIVATIVE_INDEX_RUN_FAILED" in events
    assert "DERIVATIVE_INDEX_RUN_CANCELED" in events
