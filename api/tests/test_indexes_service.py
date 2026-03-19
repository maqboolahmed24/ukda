from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from app.auth.models import SessionPrincipal
from app.core.config import get_settings
from app.exports.models import ExportCandidateSnapshotRecord
from app.indexes.models import (
    CreateDerivativeIndexRowInput,
    ControlledEntityRecord,
    DerivativeIndexRowRecord,
    DerivativeSnapshotRecord,
    EntityOccurrenceRecord,
    IndexKind,
    IndexRecord,
    ProjectIndexProjectionRecord,
    SearchDocumentPage,
    SearchDocumentRecord,
    SearchQueryAuditPage,
    SearchQueryAuditRecord,
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
        self.derivative_snapshots: dict[str, DerivativeSnapshotRecord] = {}
        self.derivative_rows_by_snapshot: dict[str, list[DerivativeIndexRowRecord]] = {}
        self.search_documents: dict[str, list[SearchDocumentRecord]] = {}
        self.search_query_texts: dict[str, str] = {}
        self.search_query_audits: list[SearchQueryAuditRecord] = []
        self.projections: dict[str, ProjectIndexProjectionRecord] = {}
        self._derivative_row_sequence = 0
        self._search_query_text_sequence = 0
        self._search_query_audit_sequence = 0

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

    def get_index_by_id(self, *, kind: IndexKind, index_id: str) -> IndexRecord | None:
        return self.indexes[kind].get(index_id)

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

    def create_derivative_snapshot(
        self,
        *,
        project_id: str,
        derivative_index_id: str,
        snapshot_id: str,
        derivative_kind: str,
        source_snapshot_json: dict[str, object],
        policy_version_ref: str,
        status: str,
        created_by: str,
        supersedes_derivative_snapshot_id: str | None = None,
        storage_key: str | None = None,
        snapshot_sha256: str | None = None,
        candidate_snapshot_id: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        failure_reason: str | None = None,
        created_at: datetime | None = None,
    ) -> DerivativeSnapshotRecord:
        now = created_at or self._now()
        snapshot = DerivativeSnapshotRecord(
            id=snapshot_id,
            project_id=project_id,
            derivative_index_id=derivative_index_id,
            derivative_kind=derivative_kind,
            source_snapshot_json=dict(source_snapshot_json),
            policy_version_ref=policy_version_ref,
            status=status,  # type: ignore[arg-type]
            supersedes_derivative_snapshot_id=supersedes_derivative_snapshot_id,
            superseded_by_derivative_snapshot_id=None,
            storage_key=storage_key,
            snapshot_sha256=snapshot_sha256,
            candidate_snapshot_id=candidate_snapshot_id,
            created_by=created_by,
            created_at=now,
            started_at=started_at,
            finished_at=finished_at,
            failure_reason=failure_reason,
        )
        self.derivative_snapshots[snapshot.id] = snapshot
        if (
            supersedes_derivative_snapshot_id
            and supersedes_derivative_snapshot_id in self.derivative_snapshots
        ):
            superseded = self.derivative_snapshots[supersedes_derivative_snapshot_id]
            self.derivative_snapshots[superseded.id] = replace(
                superseded,
                superseded_by_derivative_snapshot_id=snapshot.id,
            )
        return snapshot

    def get_derivative_snapshot(
        self,
        *,
        project_id: str,
        derivative_snapshot_id: str,
    ) -> DerivativeSnapshotRecord | None:
        snapshot = self.derivative_snapshots.get(derivative_snapshot_id)
        if snapshot is None or snapshot.project_id != project_id:
            return None
        return snapshot

    def list_derivative_snapshots_for_index(
        self,
        *,
        project_id: str,
        derivative_index_id: str,
    ) -> list[DerivativeSnapshotRecord]:
        rows = [
            row
            for row in self.derivative_snapshots.values()
            if row.project_id == project_id and row.derivative_index_id == derivative_index_id
        ]
        return sorted(rows, key=lambda row: row.created_at, reverse=True)

    def list_unsuperseded_successful_derivative_snapshots(
        self,
        *,
        project_id: str,
    ) -> list[DerivativeSnapshotRecord]:
        rows = [
            row
            for row in self.derivative_snapshots.values()
            if row.project_id == project_id
            and row.status == "SUCCEEDED"
            and row.superseded_by_derivative_snapshot_id is None
        ]
        return sorted(rows, key=lambda row: row.created_at, reverse=True)

    def set_derivative_snapshot_candidate_snapshot_id(
        self,
        *,
        project_id: str,
        derivative_snapshot_id: str,
        candidate_snapshot_id: str,
    ) -> DerivativeSnapshotRecord | None:
        snapshot = self.get_derivative_snapshot(
            project_id=project_id,
            derivative_snapshot_id=derivative_snapshot_id,
        )
        if snapshot is None:
            return None
        resolved_candidate = snapshot.candidate_snapshot_id or candidate_snapshot_id
        updated = replace(snapshot, candidate_snapshot_id=resolved_candidate)
        self.derivative_snapshots[updated.id] = updated
        return updated

    def append_derivative_index_rows(
        self,
        *,
        project_id: str,
        derivative_index_id: str,
        derivative_snapshot_id: str,
        items: list[CreateDerivativeIndexRowInput],
    ) -> int:
        if len(items) == 0:
            return 0
        snapshot = self.get_derivative_snapshot(
            project_id=project_id,
            derivative_snapshot_id=derivative_snapshot_id,
        )
        if snapshot is None or snapshot.derivative_index_id != derivative_index_id:
            return 0
        bucket = self.derivative_rows_by_snapshot.setdefault(derivative_snapshot_id, [])
        created_at = self._now()
        for item in items:
            self._derivative_row_sequence += 1
            bucket.append(
                DerivativeIndexRowRecord(
                    id=f"derrow-{self._derivative_row_sequence}",
                    derivative_index_id=derivative_index_id,
                    derivative_snapshot_id=derivative_snapshot_id,
                    derivative_kind=item.derivative_kind,
                    source_snapshot_json=dict(item.source_snapshot_json),
                    display_payload_json=dict(item.display_payload_json),
                    suppressed_fields_json=dict(item.suppressed_fields_json),
                    created_at=created_at,
                )
            )
        return len(items)

    def list_all_derivative_rows_for_snapshot(
        self,
        *,
        derivative_index_id: str,
        derivative_snapshot_id: str,
    ) -> list[DerivativeIndexRowRecord]:
        rows = [
            row
            for row in self.derivative_rows_by_snapshot.get(derivative_snapshot_id, [])
            if row.derivative_index_id == derivative_index_id
        ]
        return sorted(rows, key=lambda row: (row.created_at, row.id))

    def list_all_derivative_rows_for_index(
        self,
        *,
        derivative_index_id: str,
    ) -> list[DerivativeIndexRowRecord]:
        rows = [
            row
            for snapshot_rows in self.derivative_rows_by_snapshot.values()
            for row in snapshot_rows
            if row.derivative_index_id == derivative_index_id
        ]
        return sorted(rows, key=lambda row: (row.created_at, row.id))

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
        del query_text
        rows = list(self.search_documents.get(search_index_id, []))
        filtered = []
        for row in rows:
            if document_id and row.document_id != document_id:
                continue
            if run_id and row.run_id != run_id:
                continue
            if page_number is not None and row.page_number != page_number:
                continue
            filtered.append(row)
        filtered = sorted(filtered, key=lambda row: (row.page_number, row.id))
        window = filtered[cursor : cursor + limit + 1]
        has_more = len(window) > limit
        items = window[:limit]
        return SearchDocumentPage(
            items=items,
            next_cursor=(cursor + limit) if has_more else None,
        )

    def store_search_query_text(
        self,
        *,
        project_id: str,
        query_text: str,
        key: str | None = None,
    ) -> str:
        del project_id
        if key is None:
            self._search_query_text_sequence += 1
            key = f"search-query-text-{self._search_query_text_sequence}"
        self.search_query_texts[key] = query_text
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
        audit_id: str | None = None,
    ) -> SearchQueryAuditRecord:
        self._search_query_audit_sequence += 1
        record = SearchQueryAuditRecord(
            id=audit_id or f"search-query-audit-{self._search_query_audit_sequence}",
            project_id=project_id,
            actor_user_id=actor_user_id,
            search_index_id=search_index_id,
            query_sha256=query_sha256,
            query_text_key=query_text_key,
            filters_json=dict(filters_json),
            result_count=result_count,
            created_at=self._now(),
        )
        self.search_query_audits.append(record)
        return record

    def list_search_query_audits(
        self,
        *,
        project_id: str,
        cursor: int,
        limit: int,
    ) -> SearchQueryAuditPage:
        rows = [
            row
            for row in self.search_query_audits
            if row.project_id == project_id
        ]
        rows = sorted(rows, key=lambda row: (row.created_at, row.id), reverse=True)
        window = rows[cursor : cursor + limit + 1]
        has_more = len(window) > limit
        items = window[:limit]
        return SearchQueryAuditPage(
            items=items,
            next_cursor=(cursor + limit) if has_more else None,
        )


class FakeExportStore:
    def __init__(self) -> None:
        self.candidates: dict[str, ExportCandidateSnapshotRecord] = {}

    def create_or_get_derivative_candidate_snapshot(
        self,
        *,
        project_id: str,
        derivative_snapshot_id: str,
        derivative_index_id: str,
        derivative_kind: str,
        source_snapshot_json: dict[str, object],
        policy_version_ref: str,
        storage_key: str,
        snapshot_sha256: str,
        suppressed_field_names: tuple[str, ...],
        row_count: int,
        created_by: str,
    ) -> tuple[ExportCandidateSnapshotRecord, bool]:
        for candidate in self.candidates.values():
            if (
                candidate.project_id == project_id
                and candidate.source_artifact_kind == "DERIVATIVE_SNAPSHOT"
                and candidate.source_artifact_id == derivative_snapshot_id
            ):
                return candidate, False

        candidate_id = f"candidate-{derivative_snapshot_id}"
        candidate = ExportCandidateSnapshotRecord(
            id=candidate_id,
            project_id=project_id,
            source_phase="PHASE10",
            source_artifact_kind="DERIVATIVE_SNAPSHOT",
            source_run_id=str(source_snapshot_json.get("sourceRunId"))
            if "sourceRunId" in source_snapshot_json
            else None,
            source_artifact_id=derivative_snapshot_id,
            governance_run_id=None,
            governance_manifest_id=None,
            governance_ledger_id=None,
            governance_manifest_sha256=None,
            governance_ledger_sha256=None,
            policy_snapshot_hash=None,
            policy_id=None,
            policy_family_id=None,
            policy_version=policy_version_ref,
            candidate_kind="SAFEGUARDED_DERIVATIVE",
            artefact_manifest_json={
                "schemaVersion": 1,
                "derivativeSnapshot": {
                    "derivativeSnapshotId": derivative_snapshot_id,
                    "derivativeIndexId": derivative_index_id,
                    "derivativeKind": derivative_kind,
                },
                "storageKey": storage_key,
                "snapshotSha256": snapshot_sha256,
                "suppressedFieldNames": list(suppressed_field_names),
                "rowCount": row_count,
            },
            candidate_sha256=f"candidate-sha-{candidate_id}",
            eligibility_status="ELIGIBLE",
            supersedes_candidate_snapshot_id=None,
            superseded_by_candidate_snapshot_id=None,
            created_by=created_by,
            created_at=datetime.now(UTC),
        )
        self.candidates[candidate.id] = candidate
        return candidate, True

    def get_candidate(
        self,
        *,
        project_id: str,
        candidate_id: str,
    ) -> ExportCandidateSnapshotRecord:
        candidate = self.candidates.get(candidate_id)
        if candidate is None or candidate.project_id != project_id:
            raise RuntimeError("Candidate not found.")
        return candidate


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
    export_store = FakeExportStore()
    service = IndexService(
        settings=get_settings(),
        store=store,  # type: ignore[arg-type]
        project_store=FakeProjectStore(),  # type: ignore[arg-type]
        audit_service=audit,  # type: ignore[arg-type]
        export_store=export_store,  # type: ignore[arg-type]
    )
    return service, store, audit


def _event_types(spy: SpyAuditService) -> set[str]:
    return {
        str(event_type)
        for event in spy.recorded
        if isinstance((event_type := event.get("event_type")), str)
    }


def _search_snapshot(ref: str, *, eligible: int = 1, valid: int = 1, covered: int = 1) -> dict[str, object]:
    return {
        "refs": [ref],
        "eligibleInputCount": eligible,
        "tokenAnchorValidInputCount": valid,
        "tokenGeometryCoveredInputCount": covered,
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
        source_snapshot_json=_search_snapshot("run-a"),
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
        source_snapshot_json=_search_snapshot("run-b"),
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
        source_snapshot_json=_search_snapshot("run-1"),
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
        source_snapshot_json=_search_snapshot("run-2"),
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


def test_search_activation_blocks_when_token_anchor_validity_gate_fails() -> None:
    service, _store, _audit = _service()
    admin = _principal(user_id="user-admin", platform_roles=("ADMIN",))
    run = service.rebuild_index(
        current_user=admin,
        project_id="project-1",
        kind="SEARCH",
        source_snapshot_json=_search_snapshot(
            "run-token-fail",
            eligible=3,
            valid=2,
            covered=3,
        ),
        build_parameters_json={"pipelineVersion": "10.4"},
    )
    service.mark_index_started(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="SEARCH",
        index_id=run.index.id,
    )
    service.mark_index_finished(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="SEARCH",
        index_id=run.index.id,
    )

    with pytest.raises(IndexConflictError, match="TOKEN_ANCHOR_VALIDITY_FAILED"):
        service.activate_index(
            current_user=admin,
            project_id="project-1",
            kind="SEARCH",
            index_id=run.index.id,
        )


def test_search_activation_blocks_when_geometry_coverage_gate_fails() -> None:
    service, _store, _audit = _service()
    admin = _principal(user_id="user-admin", platform_roles=("ADMIN",))
    run = service.rebuild_index(
        current_user=admin,
        project_id="project-1",
        kind="SEARCH",
        source_snapshot_json=_search_snapshot(
            "run-geometry-fail",
            eligible=4,
            valid=4,
            covered=2,
        ),
        build_parameters_json={"pipelineVersion": "10.4"},
    )
    service.mark_index_started(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="SEARCH",
        index_id=run.index.id,
    )
    service.mark_index_finished(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="SEARCH",
        index_id=run.index.id,
    )

    with pytest.raises(IndexConflictError, match="TOKEN_GEOMETRY_COVERAGE_FAILED"):
        service.activate_index(
            current_user=admin,
            project_id="project-1",
            kind="SEARCH",
            index_id=run.index.id,
        )


def test_index_quality_summary_reports_stale_search_generation_when_newer_success_exists() -> None:
    service, _store, _audit = _service()
    admin = _principal(user_id="user-admin", platform_roles=("ADMIN",))
    run1 = service.rebuild_index(
        current_user=admin,
        project_id="project-1",
        kind="SEARCH",
        source_snapshot_json=_search_snapshot("run-freshness-1"),
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
        source_snapshot_json=_search_snapshot("run-freshness-2"),
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

    summary = service.get_index_quality_summary(
        current_user=admin,
        project_id="project-1",
    )
    search_item = next(item for item in summary.items if item.kind == "SEARCH")

    assert search_item.freshness.status == "stale"
    assert search_item.freshness.active_index_id == run1.index.id
    assert search_item.freshness.latest_succeeded_index_id == run2.index.id
    assert search_item.freshness.stale_generation_gap == 1


def test_search_query_execution_appends_audit_with_hash_and_controlled_text_key() -> None:
    service, store, audit = _service()
    researcher = _principal(user_id="user-researcher")
    admin = _principal(user_id="user-admin", platform_roles=("ADMIN",))
    run = service.rebuild_index(
        current_user=admin,
        project_id="project-1",
        kind="SEARCH",
        source_snapshot_json=_search_snapshot("run-search-query"),
        build_parameters_json={"pipelineVersion": "10.1"},
    )
    service.mark_index_started(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="SEARCH",
        index_id=run.index.id,
    )
    service.mark_index_finished(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="SEARCH",
        index_id=run.index.id,
    )
    service.activate_index(
        current_user=admin,
        project_id="project-1",
        kind="SEARCH",
        index_id=run.index.id,
    )
    store.search_documents[run.index.id] = [
        SearchDocumentRecord(
            id="searchdoc-1",
            search_index_id=run.index.id,
            document_id="doc-1",
            run_id="txrun-1",
            page_id="page-1",
            line_id="line-1",
            token_id="token-1",
            source_kind="LINE",
            source_ref_id="line-1",
            page_number=1,
            match_span_json={"start": 0, "end": 5},
            token_geometry_json={"x": 1, "y": 1, "w": 2, "h": 1},
            search_text="John Smith letter",
            search_metadata_json={},
            created_at=datetime.now(UTC),
        )
    ]

    result = service.search_project(
        current_user=researcher,
        project_id="project-1",
        query_text="  John   Smith ",
        document_id="doc-1",
        run_id=None,
        page_number=1,
        cursor=0,
        limit=25,
        route="/projects/{project_id}/search",
    )

    assert result.search_index_id == run.index.id
    assert len(result.items) == 1
    assert len(store.search_query_audits) == 1
    audit_row = store.search_query_audits[0]
    assert audit_row.actor_user_id == researcher.user_id
    assert audit_row.search_index_id == run.index.id
    assert audit_row.query_sha256 == IndexService._query_sha256("John   Smith")
    assert audit_row.filters_json == {"documentId": "doc-1", "pageNumber": 1}
    assert audit_row.result_count == 1
    assert store.search_query_texts[audit_row.query_text_key] == "John   Smith"

    executed_event = next(
        event for event in audit.recorded if event.get("event_type") == "SEARCH_QUERY_EXECUTED"
    )
    metadata = executed_event.get("metadata")
    assert isinstance(metadata, dict)
    assert "query_text" not in metadata
    assert metadata.get("query_text_key") == audit_row.query_text_key


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


def _create_succeeded_derivative_index(
    service: IndexService,
    *,
    admin: SessionPrincipal,
    source_snapshot_json: dict[str, object],
    build_parameters_json: dict[str, object] | None = None,
) -> str:
    created = service.rebuild_index(
        current_user=admin,
        project_id="project-1",
        kind="DERIVATIVE",
        source_snapshot_json=source_snapshot_json,
        build_parameters_json=build_parameters_json or {"pipelineVersion": "10.0"},
    )
    service.mark_index_started(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="DERIVATIVE",
        index_id=created.index.id,
    )
    service.mark_index_finished(
        actor_user_id="worker-1",
        project_id="project-1",
        kind="DERIVATIVE",
        index_id=created.index.id,
    )
    return created.index.id


def test_derivative_activation_blocks_when_suppression_policy_checks_fail() -> None:
    service, store, _audit = _service()
    admin = _principal(user_id="user-admin", platform_roles=("ADMIN",))
    derivative_index_id = _create_succeeded_derivative_index(
        service,
        admin=admin,
        source_snapshot_json={"eligibleInputCount": 1, "coveredInputCount": 1},
    )
    snapshot = store.create_derivative_snapshot(
        project_id="project-1",
        derivative_index_id=derivative_index_id,
        snapshot_id="dersnap-suppression-fail",
        derivative_kind="SAFE_ENTITY_COUNTS",
        source_snapshot_json={
            "antiJoinQuasiIdentifierFields": ["category", "period", "region"],
            "antiJoinMinimumGroupSize": 2,
        },
        policy_version_ref="policy-v1",
        status="SUCCEEDED",
        created_by=admin.user_id,
        storage_key="indexes/derivatives/project-1/suppression-fail.json",
        snapshot_sha256="sha-suppression-fail",
        started_at=datetime.now(UTC) - timedelta(seconds=3),
        finished_at=datetime.now(UTC),
    )
    store.append_derivative_index_rows(
        project_id="project-1",
        derivative_index_id=derivative_index_id,
        derivative_snapshot_id=snapshot.id,
        items=[
            CreateDerivativeIndexRowInput(
                derivative_kind="SAFE_ENTITY_COUNTS",
                source_snapshot_json={"category": "occupation"},
                display_payload_json={
                    "category": "occupation",
                    "period": "1841",
                    "region": "yorkshire",
                    "person_name": "John Adams",
                    "count": 2,
                },
                suppressed_fields_json={"fields": {}, "suppressedCount": 0},
            )
        ],
    )

    with pytest.raises(IndexConflictError, match="suppression-policy"):
        service.activate_index(
            current_user=admin,
            project_id="project-1",
            kind="DERIVATIVE",
            index_id=derivative_index_id,
        )


def test_derivative_activation_blocks_when_antijoin_checks_fail() -> None:
    service, store, _audit = _service()
    admin = _principal(user_id="user-admin", platform_roles=("ADMIN",))
    derivative_index_id = _create_succeeded_derivative_index(
        service,
        admin=admin,
        source_snapshot_json={"eligibleInputCount": 1, "coveredInputCount": 1},
    )
    snapshot = store.create_derivative_snapshot(
        project_id="project-1",
        derivative_index_id=derivative_index_id,
        snapshot_id="dersnap-antijoin-fail",
        derivative_kind="SAFE_ENTITY_COUNTS",
        source_snapshot_json={
            "antiJoinQuasiIdentifierFields": ["category", "period", "region"],
            "antiJoinMinimumGroupSize": 2,
        },
        policy_version_ref="policy-v1",
        status="SUCCEEDED",
        created_by=admin.user_id,
        storage_key="indexes/derivatives/project-1/antijoin-fail.json",
        snapshot_sha256="sha-antijoin-fail",
        started_at=datetime.now(UTC) - timedelta(seconds=3),
        finished_at=datetime.now(UTC),
    )
    store.append_derivative_index_rows(
        project_id="project-1",
        derivative_index_id=derivative_index_id,
        derivative_snapshot_id=snapshot.id,
        items=[
            CreateDerivativeIndexRowInput(
                derivative_kind="SAFE_ENTITY_COUNTS",
                source_snapshot_json={"category": "occupation"},
                display_payload_json={
                    "category": "occupation",
                    "period": "1841",
                    "region": "yorkshire",
                    "value": "farm labourer",
                    "count": 1,
                },
                suppressed_fields_json={"fields": {}, "suppressedCount": 0},
            )
        ],
    )

    with pytest.raises(IndexConflictError, match="anti-join disclosure"):
        service.activate_index(
            current_user=admin,
            project_id="project-1",
            kind="DERIVATIVE",
            index_id=derivative_index_id,
        )


def test_derivative_activation_blocks_when_snapshot_completeness_gate_fails() -> None:
    service, store, _audit = _service()
    admin = _principal(user_id="user-admin", platform_roles=("ADMIN",))
    derivative_index_id = _create_succeeded_derivative_index(
        service,
        admin=admin,
        source_snapshot_json={"eligibleInputCount": 2, "coveredInputCount": 2},
    )
    store.create_derivative_snapshot(
        project_id="project-1",
        derivative_index_id=derivative_index_id,
        snapshot_id="dersnap-completeness-fail",
        derivative_kind="SAFE_ENTITY_COUNTS",
        source_snapshot_json={
            "antiJoinQuasiIdentifierFields": ["category"],
            "antiJoinMinimumGroupSize": 2,
        },
        policy_version_ref="policy-v1",
        status="SUCCEEDED",
        created_by=admin.user_id,
        storage_key=None,
        snapshot_sha256="sha-completeness-fail",
        started_at=datetime.now(UTC) - timedelta(seconds=3),
        finished_at=datetime.now(UTC),
    )

    with pytest.raises(IndexConflictError, match="snapshot completeness"):
        service.activate_index(
            current_user=admin,
            project_id="project-1",
            kind="DERIVATIVE",
            index_id=derivative_index_id,
        )


def test_derivative_candidate_freeze_is_idempotent_for_unsuperseded_snapshot() -> None:
    service, store, _audit = _service()
    admin = _principal(user_id="user-admin", platform_roles=("ADMIN",))
    reviewer = _principal(user_id="user-reviewer")
    derivative_index_id = _create_succeeded_derivative_index(
        service,
        admin=admin,
        source_snapshot_json={"eligibleInputCount": 2, "coveredInputCount": 2},
    )
    snapshot = store.create_derivative_snapshot(
        project_id="project-1",
        derivative_index_id=derivative_index_id,
        snapshot_id="dersnap-freeze-ok",
        derivative_kind="SAFE_ENTITY_COUNTS",
        source_snapshot_json={
            "antiJoinQuasiIdentifierFields": ["category", "period", "region"],
            "antiJoinMinimumGroupSize": 2,
        },
        policy_version_ref="policy-v1",
        status="SUCCEEDED",
        created_by=admin.user_id,
        storage_key="indexes/derivatives/project-1/freeze-ok.json",
        snapshot_sha256="sha-freeze-ok",
        started_at=datetime.now(UTC) - timedelta(seconds=3),
        finished_at=datetime.now(UTC),
    )
    store.append_derivative_index_rows(
        project_id="project-1",
        derivative_index_id=derivative_index_id,
        derivative_snapshot_id=snapshot.id,
        items=[
            CreateDerivativeIndexRowInput(
                derivative_kind="SAFE_ENTITY_COUNTS",
                source_snapshot_json={"basis": "entity-index-1"},
                display_payload_json={
                    "category": "occupation",
                    "period": "1841",
                    "region": "yorkshire",
                    "value": "farm labourer",
                    "count": 3,
                },
                suppressed_fields_json={"fields": {}, "suppressedCount": 0},
            ),
            CreateDerivativeIndexRowInput(
                derivative_kind="SAFE_ENTITY_COUNTS",
                source_snapshot_json={"basis": "entity-index-1"},
                display_payload_json={
                    "category": "occupation",
                    "period": "1841",
                    "region": "yorkshire",
                    "value": "maid servant",
                    "count": 2,
                },
                suppressed_fields_json={"fields": {}, "suppressedCount": 0},
            ),
        ],
    )

    first = service.freeze_derivative_candidate_snapshot(
        current_user=reviewer,
        project_id="project-1",
        derivative_id=snapshot.id,
    )
    second = service.freeze_derivative_candidate_snapshot(
        current_user=reviewer,
        project_id="project-1",
        derivative_id=snapshot.id,
    )

    assert first.created is True
    assert second.created is False
    assert first.candidate.id == second.candidate.id
    assert first.snapshot.candidate_snapshot_id == first.candidate.id


def test_derivative_candidate_freeze_rejects_superseded_snapshots() -> None:
    service, store, _audit = _service()
    admin = _principal(user_id="user-admin", platform_roles=("ADMIN",))
    reviewer = _principal(user_id="user-reviewer")
    derivative_index_id = _create_succeeded_derivative_index(
        service,
        admin=admin,
        source_snapshot_json={"eligibleInputCount": 2, "coveredInputCount": 2},
    )
    superseded = store.create_derivative_snapshot(
        project_id="project-1",
        derivative_index_id=derivative_index_id,
        snapshot_id="dersnap-freeze-superseded",
        derivative_kind="SAFE_ENTITY_COUNTS",
        source_snapshot_json={
            "antiJoinQuasiIdentifierFields": ["category", "period", "region"],
            "antiJoinMinimumGroupSize": 2,
        },
        policy_version_ref="policy-v1",
        status="SUCCEEDED",
        created_by=admin.user_id,
        storage_key="indexes/derivatives/project-1/freeze-superseded.json",
        snapshot_sha256="sha-freeze-superseded",
        started_at=datetime.now(UTC) - timedelta(seconds=5),
        finished_at=datetime.now(UTC) - timedelta(seconds=4),
    )
    store.create_derivative_snapshot(
        project_id="project-1",
        derivative_index_id=derivative_index_id,
        snapshot_id="dersnap-freeze-replacement",
        derivative_kind="SAFE_ENTITY_COUNTS",
        source_snapshot_json={
            "antiJoinQuasiIdentifierFields": ["category", "period", "region"],
            "antiJoinMinimumGroupSize": 2,
        },
        policy_version_ref="policy-v1",
        status="SUCCEEDED",
        created_by=admin.user_id,
        supersedes_derivative_snapshot_id=superseded.id,
        storage_key="indexes/derivatives/project-1/freeze-replacement.json",
        snapshot_sha256="sha-freeze-replacement",
        started_at=datetime.now(UTC) - timedelta(seconds=3),
        finished_at=datetime.now(UTC) - timedelta(seconds=2),
    )
    store.append_derivative_index_rows(
        project_id="project-1",
        derivative_index_id=derivative_index_id,
        derivative_snapshot_id=superseded.id,
        items=[
            CreateDerivativeIndexRowInput(
                derivative_kind="SAFE_ENTITY_COUNTS",
                source_snapshot_json={},
                display_payload_json={
                    "category": "occupation",
                    "period": "1841",
                    "region": "yorkshire",
                    "value": "farm labourer",
                    "count": 2,
                },
                suppressed_fields_json={"fields": {}, "suppressedCount": 0},
            ),
            CreateDerivativeIndexRowInput(
                derivative_kind="SAFE_ENTITY_COUNTS",
                source_snapshot_json={},
                display_payload_json={
                    "category": "occupation",
                    "period": "1841",
                    "region": "yorkshire",
                    "value": "maid servant",
                    "count": 2,
                },
                suppressed_fields_json={"fields": {}, "suppressedCount": 0},
            ),
        ],
    )

    with pytest.raises(IndexConflictError, match="Superseded derivative snapshots cannot be frozen"):
        service.freeze_derivative_candidate_snapshot(
            current_user=reviewer,
            project_id="project-1",
            derivative_id=superseded.id,
        )
