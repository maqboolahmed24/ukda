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
from app.exports.models import ExportCandidateSnapshotRecord
from app.indexes.models import (
    ActiveProjectIndexesView,
    DerivativeIndexRowRecord,
    DerivativeSnapshotListItem,
    DerivativeSnapshotRecord,
    IndexKind,
    IndexRecord,
    ProjectIndexProjectionRecord,
    SearchQueryAuditRecord,
)
from app.indexes.service import (
    DerivativeCandidateFreezeResult,
    IndexFreshnessSnapshot,
    ProjectDerivativeDetailResult,
    ProjectDerivativeListResult,
    ProjectDerivativePreviewResult,
    IndexQualityDetail,
    IndexQualitySummaryItem,
    IndexAccessDeniedError,
    IndexCancelResult,
    IndexConflictError,
    IndexNotFoundError,
    IndexRebuildResult,
    ProjectIndexQualitySummary,
    ProjectSearchQueryAuditResult,
    SearchActivationGateEvaluation,
    SearchCoverageSummary,
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
        self.derivative_snapshots: dict[str, DerivativeSnapshotRecord] = {}
        self.derivative_rows: dict[str, list[DerivativeIndexRowRecord]] = {}
        self.candidates: dict[str, ExportCandidateSnapshotRecord] = {}
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
        self._seed_row("DERIVATIVE", "derivative-2", status="SUCCEEDED", version=2)
        self._seed_derivative_snapshot(
            snapshot_id="derivative-snapshot-1",
            derivative_index_id="derivative-1",
            status="SUCCEEDED",
            supersedes_derivative_snapshot_id=None,
            superseded_by_derivative_snapshot_id="derivative-snapshot-2",
            candidate_snapshot_id="candidate-derivative-snapshot-1",
            created_at=now - timedelta(days=1),
        )
        self._seed_derivative_snapshot(
            snapshot_id="derivative-snapshot-2",
            derivative_index_id="derivative-2",
            status="SUCCEEDED",
            supersedes_derivative_snapshot_id="derivative-snapshot-1",
            superseded_by_derivative_snapshot_id=None,
            candidate_snapshot_id=None,
            created_at=now - timedelta(hours=2),
        )
        self.candidates["candidate-derivative-snapshot-1"] = self._make_candidate(
            candidate_id="candidate-derivative-snapshot-1",
            snapshot_id="derivative-snapshot-1",
            derivative_index_id="derivative-1",
            derivative_kind="SAFE_ENTITY_COUNTS",
            policy_version_ref="policy-v1",
            created_by="user-admin",
            created_at=now - timedelta(days=1),
        )
        self.projection = replace(
            self.projection,
            active_search_index_id="search-1",
            active_entity_index_id="entity-1",
            active_derivative_index_id="derivative-2",
            updated_at=now,
        )
        self.search_query_audits: list[SearchQueryAuditRecord] = [
            SearchQueryAuditRecord(
                id="search-query-audit-1",
                project_id="project-1",
                actor_user_id="user-researcher",
                search_index_id="search-1",
                query_sha256="sha-query-1",
                query_text_key="search-query-text-1",
                filters_json={"documentId": "doc-1"},
                result_count=3,
                created_at=now - timedelta(minutes=5),
            )
        ]

    @staticmethod
    def _is_admin(current_user: SessionPrincipal) -> bool:
        return "ADMIN" in set(current_user.platform_roles)

    @staticmethod
    def _role_for_user(current_user: SessionPrincipal) -> str:
        if FakeIndexService._is_admin(current_user):
            return "ADMIN"
        if current_user.user_id == "user-auditor":
            return "AUDITOR"
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

    def _require_index_quality_read(self, *, current_user: SessionPrincipal) -> None:
        role = self._role_for_user(current_user)
        if role in {"ADMIN", "AUDITOR"}:
            return
        raise IndexAccessDeniedError(
            "Index quality reads require ADMIN or AUDITOR platform role."
        )

    def _require_derivative_freeze(
        self, *, current_user: SessionPrincipal, project_id: str
    ) -> None:
        self._require_project(project_id)
        role = self._role_for_user(current_user)
        if role in {"ADMIN", "PROJECT_LEAD", "REVIEWER"}:
            return
        raise IndexAccessDeniedError(
            "Candidate freeze is restricted to project leads, reviewers, or administrators."
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

    def _seed_derivative_snapshot(
        self,
        *,
        snapshot_id: str,
        derivative_index_id: str,
        status: str,
        supersedes_derivative_snapshot_id: str | None,
        superseded_by_derivative_snapshot_id: str | None,
        candidate_snapshot_id: str | None,
        created_at: datetime,
    ) -> None:
        snapshot = DerivativeSnapshotRecord(
            id=snapshot_id,
            project_id="project-1",
            derivative_index_id=derivative_index_id,
            derivative_kind="SAFE_ENTITY_COUNTS",
            source_snapshot_json={
                "sourceRunId": f"run-{snapshot_id}",
                "antiJoinQuasiIdentifierFields": ["category", "period", "region"],
                "antiJoinMinimumGroupSize": 2,
            },
            policy_version_ref="policy-v1",
            status=status,  # type: ignore[arg-type]
            supersedes_derivative_snapshot_id=supersedes_derivative_snapshot_id,
            superseded_by_derivative_snapshot_id=superseded_by_derivative_snapshot_id,
            storage_key=f"indexes/derivatives/project-1/{derivative_index_id}/{snapshot_id}.json",
            snapshot_sha256=f"sha-{snapshot_id}",
            candidate_snapshot_id=candidate_snapshot_id,
            created_by="user-admin",
            created_at=created_at,
            started_at=created_at - timedelta(seconds=10),
            finished_at=created_at,
            failure_reason=None,
        )
        self.derivative_snapshots[snapshot.id] = snapshot
        self.derivative_rows[snapshot.id] = [
            DerivativeIndexRowRecord(
                id=f"derrow-{snapshot.id}-1",
                derivative_index_id=snapshot.derivative_index_id,
                derivative_snapshot_id=snapshot.id,
                derivative_kind=snapshot.derivative_kind,
                source_snapshot_json={
                    "category": "occupation",
                    "period": "1841",
                    "region": "yorkshire",
                },
                display_payload_json={
                    "category": "occupation",
                    "period": "1841",
                    "region": "yorkshire",
                    "value": "farm labourer",
                    "count": 3,
                },
                suppressed_fields_json={
                    "fields": {"source.person_name": "IDENTIFIER_SUPPRESSED"},
                    "suppressedCount": 1,
                },
                created_at=created_at,
            )
        ]

    @staticmethod
    def _make_candidate(
        *,
        candidate_id: str,
        snapshot_id: str,
        derivative_index_id: str,
        derivative_kind: str,
        policy_version_ref: str,
        created_by: str,
        created_at: datetime,
    ) -> ExportCandidateSnapshotRecord:
        return ExportCandidateSnapshotRecord(
            id=candidate_id,
            project_id="project-1",
            source_phase="PHASE10",
            source_artifact_kind="DERIVATIVE_SNAPSHOT",
            source_run_id=f"run-{snapshot_id}",
            source_artifact_id=snapshot_id,
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
                    "derivativeSnapshotId": snapshot_id,
                    "derivativeIndexId": derivative_index_id,
                    "derivativeKind": derivative_kind,
                },
            },
            candidate_sha256=f"candidate-sha-{candidate_id}",
            eligibility_status="ELIGIBLE",
            supersedes_candidate_snapshot_id=None,
            superseded_by_candidate_snapshot_id=None,
            created_by=created_by,
            created_at=created_at,
        )

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

    def list_project_derivatives(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        scope: str | None,
    ) -> ProjectDerivativeListResult:
        self._require_read(current_user=current_user, project_id=project_id)
        normalized_scope = (scope or "active").strip().lower()
        if normalized_scope not in {"active", "historical"}:
            raise IndexConflictError("scope must be one of: active, historical.")
        active_derivative_index_id = self.projection.active_derivative_index_id
        if normalized_scope == "active" and active_derivative_index_id is None:
            raise IndexConflictError("No active derivative index is available for this project.")

        items: dict[str, DerivativeSnapshotListItem] = {}
        if active_derivative_index_id is not None:
            for snapshot in sorted(
                self.derivative_snapshots.values(),
                key=lambda row: row.created_at,
                reverse=True,
            ):
                if snapshot.derivative_index_id != active_derivative_index_id:
                    continue
                items[snapshot.id] = DerivativeSnapshotListItem(
                    snapshot=snapshot,
                    is_active_generation=True,
                )

        if normalized_scope == "historical":
            for snapshot in sorted(
                self.derivative_snapshots.values(),
                key=lambda row: row.created_at,
                reverse=True,
            ):
                if snapshot.status != "SUCCEEDED":
                    continue
                if snapshot.superseded_by_derivative_snapshot_id is not None:
                    continue
                items.setdefault(
                    snapshot.id,
                    DerivativeSnapshotListItem(
                        snapshot=snapshot,
                        is_active_generation=(
                            snapshot.derivative_index_id == active_derivative_index_id
                        ),
                    ),
                )

        return ProjectDerivativeListResult(
            scope=normalized_scope,  # type: ignore[arg-type]
            active_derivative_index_id=active_derivative_index_id,
            items=list(items.values()),
        )

    def get_project_derivative_detail(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        derivative_id: str,
    ) -> ProjectDerivativeDetailResult:
        self._require_read(current_user=current_user, project_id=project_id)
        snapshot = self.derivative_snapshots.get(derivative_id)
        if snapshot is None or snapshot.project_id != project_id:
            raise IndexNotFoundError("Derivative snapshot was not found.")
        return ProjectDerivativeDetailResult(snapshot=snapshot)

    def get_project_derivative_status(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        derivative_id: str,
    ) -> ProjectDerivativeDetailResult:
        return self.get_project_derivative_detail(
            current_user=current_user,
            project_id=project_id,
            derivative_id=derivative_id,
        )

    def preview_project_derivative(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        derivative_id: str,
    ) -> ProjectDerivativePreviewResult:
        detail = self.get_project_derivative_detail(
            current_user=current_user,
            project_id=project_id,
            derivative_id=derivative_id,
        )
        rows = list(self.derivative_rows.get(detail.snapshot.id, []))
        return ProjectDerivativePreviewResult(snapshot=detail.snapshot, rows=rows)

    def freeze_derivative_candidate_snapshot(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        derivative_id: str,
    ) -> DerivativeCandidateFreezeResult:
        self._require_derivative_freeze(current_user=current_user, project_id=project_id)
        snapshot = self.derivative_snapshots.get(derivative_id)
        if snapshot is None or snapshot.project_id != project_id:
            raise IndexNotFoundError("Derivative snapshot was not found.")
        if snapshot.status != "SUCCEEDED":
            raise IndexConflictError(
                "Candidate freeze is allowed only for SUCCEEDED derivative snapshots."
            )
        if snapshot.superseded_by_derivative_snapshot_id is not None:
            raise IndexConflictError("Superseded derivative snapshots cannot be frozen.")

        rows = self.derivative_rows.get(snapshot.id, [])
        if len(rows) == 0:
            raise IndexConflictError(
                "Candidate freeze is blocked until derivative preview rows are materialized."
            )

        if snapshot.candidate_snapshot_id:
            existing = self.candidates.get(snapshot.candidate_snapshot_id)
            if existing is None:
                raise IndexConflictError(
                    "Derivative snapshot references a missing candidate snapshot."
                )
            return DerivativeCandidateFreezeResult(
                snapshot=snapshot,
                candidate=existing,
                created=False,
            )

        candidate_id = f"candidate-{snapshot.id}"
        candidate = self._make_candidate(
            candidate_id=candidate_id,
            snapshot_id=snapshot.id,
            derivative_index_id=snapshot.derivative_index_id,
            derivative_kind=snapshot.derivative_kind,
            policy_version_ref=snapshot.policy_version_ref,
            created_by=current_user.user_id,
            created_at=datetime.now(UTC),
        )
        self.candidates[candidate.id] = candidate
        updated = replace(snapshot, candidate_snapshot_id=candidate.id)
        self.derivative_snapshots[updated.id] = updated
        return DerivativeCandidateFreezeResult(
            snapshot=updated,
            candidate=candidate,
            created=True,
        )

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

    def get_index_quality_summary(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> ProjectIndexQualitySummary:
        self._require_project(project_id)
        self._require_index_quality_read(current_user=current_user)

        items: list[IndexQualitySummaryItem] = []
        for kind in ("SEARCH", "ENTITY", "DERIVATIVE"):
            if kind == "SEARCH":
                active_index_id = self.projection.active_search_index_id
            elif kind == "ENTITY":
                active_index_id = self.projection.active_entity_index_id
            else:
                active_index_id = self.projection.active_derivative_index_id

            rows = sorted(
                self.rows[kind].values(),
                key=lambda row: row.version,
                reverse=True,
            )
            active_row = self.rows[kind].get(active_index_id or "")
            latest_succeeded = next(
                (row for row in rows if row.status == "SUCCEEDED"),
                None,
            )
            freshness_status = "missing"
            reason: str | None = None
            if active_row is not None and latest_succeeded is not None:
                if active_row.id == latest_succeeded.id:
                    freshness_status = "current"
                else:
                    freshness_status = "stale"
                    reason = "A newer SUCCEEDED generation exists but is not active."
            elif active_row is not None:
                freshness_status = "blocked"
                reason = "No SUCCEEDED generation is available."
            elif latest_succeeded is not None:
                freshness_status = "missing"
                reason = "No active index projection pointer is set."

            search_coverage: SearchCoverageSummary | None = None
            blocker_count = 0
            if kind == "SEARCH":
                source_snapshot = (
                    active_row.source_snapshot_json
                    if active_row is not None
                    else latest_succeeded.source_snapshot_json
                    if latest_succeeded is not None
                    else {}
                )
                eligible = source_snapshot.get("eligibleInputCount")
                valid = source_snapshot.get("tokenAnchorValidInputCount")
                covered = source_snapshot.get("tokenGeometryCoveredInputCount")
                search_coverage = SearchCoverageSummary(
                    eligible_input_count=int(eligible) if isinstance(eligible, int) else None,
                    token_anchor_valid_input_count=(
                        int(valid) if isinstance(valid, int) else None
                    ),
                    token_geometry_covered_input_count=(
                        int(covered) if isinstance(covered, int) else None
                    ),
                    historical_line_only_excluded_count=0,
                    historical_line_only_fallback_allowed=False,
                    historical_line_only_fallback_reason=None,
                )
                if (
                    search_coverage.eligible_input_count is not None
                    and search_coverage.token_anchor_valid_input_count is not None
                    and search_coverage.token_anchor_valid_input_count
                    < search_coverage.eligible_input_count
                ):
                    blocker_count = 1

            items.append(
                IndexQualitySummaryItem(
                    kind=kind,
                    freshness=IndexFreshnessSnapshot(
                        status=freshness_status,  # type: ignore[arg-type]
                        active_index_id=active_row.id if active_row else None,
                        active_version=active_row.version if active_row else None,
                        active_status=active_row.status if active_row else None,
                        latest_succeeded_index_id=(
                            latest_succeeded.id if latest_succeeded else None
                        ),
                        latest_succeeded_version=(
                            latest_succeeded.version if latest_succeeded else None
                        ),
                        latest_succeeded_finished_at=(
                            latest_succeeded.finished_at if latest_succeeded else None
                        ),
                        stale_generation_gap=(
                            latest_succeeded.version - active_row.version
                            if freshness_status == "stale"
                            and active_row is not None
                            and latest_succeeded is not None
                            else None
                        ),
                        reason=reason,
                        blocked_codes=[],
                    ),
                    search_coverage=search_coverage,
                    search_activation_blocker_count=blocker_count,
                )
            )

        return ProjectIndexQualitySummary(
            project_id=project_id,
            projection_updated_at=self.projection.updated_at,
            items=items,
        )

    def get_index_quality_detail(
        self,
        *,
        current_user: SessionPrincipal,
        kind: IndexKind,
        index_id: str,
    ) -> IndexQualityDetail:
        self._require_index_quality_read(current_user=current_user)
        row = self.rows[kind].get(index_id)
        if row is None:
            raise IndexNotFoundError("Index generation not found.")
        summary = self.get_index_quality_summary(
            current_user=current_user,
            project_id=row.project_id,
        )
        summary_item = next(item for item in summary.items if item.kind == kind)
        latest_succeeded = summary_item.freshness.latest_succeeded_index_id
        return IndexQualityDetail(
            project_id=row.project_id,
            kind=kind,
            index=row,
            freshness=summary_item.freshness,
            active_index_id=summary_item.freshness.active_index_id,
            is_active_generation=summary_item.freshness.active_index_id == row.id,
            is_latest_succeeded_generation=latest_succeeded == row.id,
            rollback_eligible=(
                kind == "SEARCH"
                and row.status == "SUCCEEDED"
                and summary_item.freshness.active_index_id != row.id
            ),
            search_coverage=summary_item.search_coverage if kind == "SEARCH" else None,
            search_activation_evaluation=(
                SearchActivationGateEvaluation(
                    passed=summary_item.search_activation_blocker_count == 0,
                    blockers=[],
                )
                if kind == "SEARCH"
                else None
            ),
        )

    def list_search_query_audits(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        cursor: int,
        limit: int,
    ) -> ProjectSearchQueryAuditResult:
        self._require_project(project_id)
        self._require_index_quality_read(current_user=current_user)
        rows = [row for row in self.search_query_audits if row.project_id == project_id]
        rows = sorted(rows, key=lambda row: (row.created_at, row.id), reverse=True)
        page = rows[cursor : cursor + limit + 1]
        has_more = len(page) > limit
        items = page[:limit]
        return ProjectSearchQueryAuditResult(
            project_id=project_id,
            items=items,
            next_cursor=(cursor + limit) if has_more else None,
        )

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


def test_derivative_preview_routes_emit_audit_events_and_scope_historical_snapshots() -> None:
    _service, spy_audit = _install_fakes(_principal(user_id="user-lead"))

    active_list = client.get("/projects/project-1/derivatives")
    historical_list = client.get("/projects/project-1/derivatives?scope=historical")
    detail = client.get("/projects/project-1/derivatives/derivative-snapshot-2")
    status_response = client.get("/projects/project-1/derivatives/derivative-snapshot-2/status")
    preview = client.get("/projects/project-1/derivatives/derivative-snapshot-2/preview")

    assert active_list.status_code == 200
    assert historical_list.status_code == 200
    assert detail.status_code == 200
    assert status_response.status_code == 200
    assert preview.status_code == 200
    assert active_list.json()["scope"] == "active"
    assert historical_list.json()["scope"] == "historical"
    assert historical_list.json()["items"][0]["id"] == "derivative-snapshot-2"
    assert preview.json()["rows"][0]["derivativeSnapshotId"] == "derivative-snapshot-2"

    events = _event_types(spy_audit)
    assert "DERIVATIVE_LIST_VIEWED" in events
    assert "DERIVATIVE_DETAIL_VIEWED" in events
    assert "DERIVATIVE_STATUS_VIEWED" in events
    assert "DERIVATIVE_PREVIEW_VIEWED" in events


def test_derivative_candidate_freeze_is_idempotent_and_emits_audit() -> None:
    _service, spy_audit = _install_fakes(_principal(user_id="user-reviewer"))

    first = client.post(
        "/projects/project-1/derivatives/derivative-snapshot-2/candidate-snapshots"
    )
    second = client.post(
        "/projects/project-1/derivatives/derivative-snapshot-2/candidate-snapshots"
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["created"] is True
    assert second.json()["created"] is False
    assert first.json()["candidateSnapshotId"] == second.json()["candidateSnapshotId"]

    events = _event_types(spy_audit)
    assert "DERIVATIVE_CANDIDATE_SNAPSHOT_CREATED" in events


def test_derivative_candidate_freeze_rejects_researcher_role() -> None:
    _service, spy_audit = _install_fakes(_principal(user_id="user-researcher"))

    response = client.post(
        "/projects/project-1/derivatives/derivative-snapshot-2/candidate-snapshots"
    )

    assert response.status_code == 403
    assert "ACCESS_DENIED" in _event_types(spy_audit)


def test_derivative_activate_route_emits_derivative_activated_audit_event() -> None:
    fake_service, spy_audit = _install_fakes(
        _principal(user_id="user-admin", platform_roles=("ADMIN",))
    )
    fake_service._seed_row("DERIVATIVE", "derivative-3", status="SUCCEEDED", version=3)

    response = client.post("/projects/project-1/derivative-indexes/derivative-3/activate")

    assert response.status_code == 200
    assert response.json()["projection"]["activeDerivativeIndexId"] == "derivative-3"
    assert "DERIVATIVE_INDEX_ACTIVATED" in _event_types(spy_audit)


def test_search_activate_route_emits_search_activated_audit_event() -> None:
    fake_service, spy_audit = _install_fakes(
        _principal(user_id="user-admin", platform_roles=("ADMIN",))
    )
    fake_service._seed_row("SEARCH", "search-2", status="SUCCEEDED", version=2)

    response = client.post("/projects/project-1/search-indexes/search-2/activate")

    assert response.status_code == 200
    assert response.json()["projection"]["activeSearchIndexId"] == "search-2"
    assert "SEARCH_INDEX_ACTIVATED" in _event_types(spy_audit)


def test_admin_index_quality_summary_route_emits_audit_event() -> None:
    _service, spy_audit = _install_fakes(
        _principal(user_id="user-admin", platform_roles=("ADMIN",))
    )

    response = client.get("/admin/index-quality?projectId=project-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["projectId"] == "project-1"
    assert len(payload["items"]) == 3
    assert "INDEX_QUALITY_VIEWED" in _event_types(spy_audit)


def test_admin_index_quality_detail_route_for_auditor_emits_audit_event() -> None:
    _service, spy_audit = _install_fakes(
        _principal(user_id="user-auditor", platform_roles=("AUDITOR",))
    )

    response = client.get("/admin/index-quality/SEARCH/search-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["projectId"] == "project-1"
    assert payload["kind"] == "SEARCH"
    assert payload["index"]["id"] == "search-1"
    assert "INDEX_QUALITY_DETAIL_VIEWED" in _event_types(spy_audit)


def test_admin_index_quality_query_audits_route_emits_audit_event() -> None:
    _service, spy_audit = _install_fakes(
        _principal(user_id="user-auditor", platform_roles=("AUDITOR",))
    )

    response = client.get("/admin/index-quality/query-audits?projectId=project-1&limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["projectId"] == "project-1"
    assert len(payload["items"]) == 1
    assert payload["items"][0]["querySha256"] == "sha-query-1"
    assert payload["items"][0]["queryTextKey"] == "search-query-text-1"
    assert "INDEX_QUALITY_QUERY_AUDITS_VIEWED" in _event_types(spy_audit)


@pytest.mark.parametrize(
    "path",
    [
        "/admin/index-quality?projectId=project-1",
        "/admin/index-quality/SEARCH/search-1",
        "/admin/index-quality/query-audits?projectId=project-1",
    ],
)
def test_admin_index_quality_routes_require_admin_or_auditor_platform_role(
    path: str,
) -> None:
    _service, spy_audit = _install_fakes(_principal(user_id="user-lead"))

    response = client.get(path)

    assert response.status_code == 403
    assert "ACCESS_DENIED" in _event_types(spy_audit)
