from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.audit.dependencies import get_audit_request_context
from app.audit.models import AuditRequestContext
from app.audit.service import AuditService, get_audit_service
from app.auth.dependencies import require_authenticated_user, require_platform_roles
from app.auth.models import SessionPrincipal
from app.indexes.models import (
    ActiveProjectIndexesView,
    ControlledEntityRecord,
    DerivativeIndexRowRecord,
    DerivativeSnapshotRecord,
    IndexKind,
    IndexRecord,
    ProjectIndexProjectionRecord,
    SearchDocumentRecord,
    SearchQueryAuditRecord,
)
from app.indexes.service import (
    DerivativeCandidateFreezeResult,
    EntityOccurrenceLink,
    IndexFreshnessSnapshot,
    IndexAccessDeniedError,
    IndexConflictError,
    IndexQualityDetail,
    IndexQualitySummaryItem,
    IndexNotFoundError,
    IndexService,
    IndexValidationError,
    ProjectDerivativeDetailResult,
    ProjectDerivativeListResult,
    ProjectDerivativePreviewResult,
    ProjectEntityDetailResult,
    ProjectEntityListResult,
    ProjectEntityOccurrencesResult,
    ProjectIndexQualitySummary,
    ProjectSearchResult,
    ProjectSearchQueryAuditResult,
    SearchActivationGateBlocker,
    SearchActivationGateEvaluation,
    SearchCoverageSummary,
    get_index_service,
)
from app.indexes.store import IndexStoreUnavailableError

router = APIRouter(
    prefix="/projects/{project_id}",
    dependencies=[Depends(require_authenticated_user)],
)
admin_router = APIRouter(
    prefix="/admin/index-quality",
    dependencies=[Depends(require_authenticated_user)],
)

IndexKindLiteral = Literal["SEARCH", "ENTITY", "DERIVATIVE"]
IndexStatusLiteral = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]


class IndexResponse(BaseModel):
    id: str
    project_id: str = Field(serialization_alias="projectId")
    kind: IndexKindLiteral
    version: int
    source_snapshot_json: dict[str, object] = Field(serialization_alias="sourceSnapshotJson")
    source_snapshot_sha256: str = Field(serialization_alias="sourceSnapshotSha256")
    build_parameters_json: dict[str, object] = Field(serialization_alias="buildParametersJson")
    rebuild_dedupe_key: str = Field(serialization_alias="rebuildDedupeKey")
    status: IndexStatusLiteral
    supersedes_index_id: str | None = Field(default=None, serialization_alias="supersedesIndexId")
    superseded_by_index_id: str | None = Field(
        default=None,
        serialization_alias="supersededByIndexId",
    )
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    finished_at: datetime | None = Field(default=None, serialization_alias="finishedAt")
    cancel_requested: bool = Field(serialization_alias="cancelRequested")
    cancel_requested_by: str | None = Field(
        default=None,
        serialization_alias="cancelRequestedBy",
    )
    cancel_requested_at: datetime | None = Field(
        default=None,
        serialization_alias="cancelRequestedAt",
    )
    canceled_by: str | None = Field(default=None, serialization_alias="canceledBy")
    canceled_at: datetime | None = Field(default=None, serialization_alias="canceledAt")
    activated_by: str | None = Field(default=None, serialization_alias="activatedBy")
    activated_at: datetime | None = Field(default=None, serialization_alias="activatedAt")


class IndexStatusResponse(BaseModel):
    id: str
    project_id: str = Field(serialization_alias="projectId")
    kind: IndexKindLiteral
    status: IndexStatusLiteral
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    finished_at: datetime | None = Field(default=None, serialization_alias="finishedAt")
    cancel_requested: bool = Field(serialization_alias="cancelRequested")
    cancel_requested_at: datetime | None = Field(
        default=None,
        serialization_alias="cancelRequestedAt",
    )
    canceled_at: datetime | None = Field(default=None, serialization_alias="canceledAt")
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")


class IndexListResponse(BaseModel):
    items: list[IndexResponse]


class ProjectIndexProjectionResponse(BaseModel):
    project_id: str = Field(serialization_alias="projectId")
    active_search_index_id: str | None = Field(
        default=None,
        serialization_alias="activeSearchIndexId",
    )
    active_entity_index_id: str | None = Field(
        default=None,
        serialization_alias="activeEntityIndexId",
    )
    active_derivative_index_id: str | None = Field(
        default=None,
        serialization_alias="activeDerivativeIndexId",
    )
    updated_at: datetime = Field(serialization_alias="updatedAt")


class ActiveIndexesResponse(BaseModel):
    project_id: str = Field(serialization_alias="projectId")
    projection: ProjectIndexProjectionResponse | None
    search_index: IndexResponse | None = Field(default=None, serialization_alias="searchIndex")
    entity_index: IndexResponse | None = Field(default=None, serialization_alias="entityIndex")
    derivative_index: IndexResponse | None = Field(
        default=None,
        serialization_alias="derivativeIndex",
    )


class RebuildIndexRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    source_snapshot_json: dict[str, object] = Field(
        alias="sourceSnapshotJson",
        serialization_alias="sourceSnapshotJson",
    )
    build_parameters_json: dict[str, object] = Field(
        default_factory=dict,
        alias="buildParametersJson",
        serialization_alias="buildParametersJson",
    )
    supersedes_index_id: str | None = Field(
        default=None,
        alias="supersedesIndexId",
        serialization_alias="supersedesIndexId",
    )


class IndexRebuildResponse(BaseModel):
    index: IndexResponse
    created: bool
    reason: str


class IndexCancelResponse(BaseModel):
    index: IndexResponse
    terminal: bool


class IndexActivateResponse(BaseModel):
    index: IndexResponse
    projection: ProjectIndexProjectionResponse


class SearchHitResponse(BaseModel):
    search_document_id: str = Field(serialization_alias="searchDocumentId")
    search_index_id: str = Field(serialization_alias="searchIndexId")
    document_id: str = Field(serialization_alias="documentId")
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    page_number: int = Field(serialization_alias="pageNumber")
    line_id: str | None = Field(default=None, serialization_alias="lineId")
    token_id: str | None = Field(default=None, serialization_alias="tokenId")
    source_kind: Literal["LINE", "RESCUE_CANDIDATE", "PAGE_WINDOW"] = Field(
        serialization_alias="sourceKind"
    )
    source_ref_id: str = Field(serialization_alias="sourceRefId")
    match_span_json: dict[str, object] | None = Field(
        default=None,
        serialization_alias="matchSpanJson",
    )
    token_geometry_json: dict[str, object] | None = Field(
        default=None,
        serialization_alias="tokenGeometryJson",
    )
    search_text: str = Field(serialization_alias="searchText")
    search_metadata_json: dict[str, object] = Field(serialization_alias="searchMetadataJson")


class SearchQueryResponse(BaseModel):
    search_index_id: str = Field(serialization_alias="searchIndexId")
    items: list[SearchHitResponse]
    next_cursor: int | None = Field(default=None, serialization_alias="nextCursor")


class SearchResultOpenResponse(BaseModel):
    search_index_id: str = Field(serialization_alias="searchIndexId")
    search_document_id: str = Field(serialization_alias="searchDocumentId")
    document_id: str = Field(serialization_alias="documentId")
    run_id: str = Field(serialization_alias="runId")
    page_number: int = Field(serialization_alias="pageNumber")
    line_id: str | None = Field(default=None, serialization_alias="lineId")
    token_id: str | None = Field(default=None, serialization_alias="tokenId")
    source_kind: Literal["LINE", "RESCUE_CANDIDATE", "PAGE_WINDOW"] = Field(
        serialization_alias="sourceKind"
    )
    source_ref_id: str = Field(serialization_alias="sourceRefId")
    workspace_path: str = Field(serialization_alias="workspacePath")


class ControlledEntityResponse(BaseModel):
    id: str
    project_id: str = Field(serialization_alias="projectId")
    entity_index_id: str = Field(serialization_alias="entityIndexId")
    entity_type: Literal["PERSON", "PLACE", "ORGANISATION", "DATE"] = Field(
        serialization_alias="entityType"
    )
    display_value: str = Field(serialization_alias="displayValue")
    canonical_value: str = Field(serialization_alias="canonicalValue")
    confidence_summary_json: dict[str, object] = Field(
        serialization_alias="confidenceSummaryJson"
    )
    occurrence_count: int = Field(serialization_alias="occurrenceCount")
    created_at: datetime = Field(serialization_alias="createdAt")


class EntityOccurrenceResponse(BaseModel):
    id: str
    entity_index_id: str = Field(serialization_alias="entityIndexId")
    entity_id: str = Field(serialization_alias="entityId")
    document_id: str = Field(serialization_alias="documentId")
    run_id: str = Field(serialization_alias="runId")
    page_id: str = Field(serialization_alias="pageId")
    page_number: int = Field(serialization_alias="pageNumber")
    line_id: str | None = Field(default=None, serialization_alias="lineId")
    token_id: str | None = Field(default=None, serialization_alias="tokenId")
    source_kind: Literal["LINE", "RESCUE_CANDIDATE", "PAGE_WINDOW"] = Field(
        serialization_alias="sourceKind"
    )
    source_ref_id: str = Field(serialization_alias="sourceRefId")
    confidence: float
    occurrence_span_json: dict[str, object] | None = Field(
        default=None,
        serialization_alias="occurrenceSpanJson",
    )
    occurrence_span_basis_kind: Literal["LINE_TEXT", "PAGE_WINDOW_TEXT", "NONE"] = Field(
        serialization_alias="occurrenceSpanBasisKind"
    )
    occurrence_span_basis_ref: str | None = Field(
        default=None,
        serialization_alias="occurrenceSpanBasisRef",
    )
    token_geometry_json: dict[str, object] | None = Field(
        default=None,
        serialization_alias="tokenGeometryJson",
    )
    workspace_path: str = Field(serialization_alias="workspacePath")


class EntityListResponse(BaseModel):
    entity_index_id: str = Field(serialization_alias="entityIndexId")
    items: list[ControlledEntityResponse]
    next_cursor: int | None = Field(default=None, serialization_alias="nextCursor")


class EntityDetailResponse(BaseModel):
    entity_index_id: str = Field(serialization_alias="entityIndexId")
    entity: ControlledEntityResponse


class EntityOccurrencesResponse(BaseModel):
    entity_index_id: str = Field(serialization_alias="entityIndexId")
    entity: ControlledEntityResponse
    items: list[EntityOccurrenceResponse]
    next_cursor: int | None = Field(default=None, serialization_alias="nextCursor")


class DerivativeSnapshotResponse(BaseModel):
    id: str
    project_id: str = Field(serialization_alias="projectId")
    derivative_index_id: str = Field(serialization_alias="derivativeIndexId")
    derivative_kind: str = Field(serialization_alias="derivativeKind")
    source_snapshot_json: dict[str, object] = Field(
        serialization_alias="sourceSnapshotJson"
    )
    policy_version_ref: str = Field(serialization_alias="policyVersionRef")
    status: IndexStatusLiteral
    supersedes_derivative_snapshot_id: str | None = Field(
        default=None,
        serialization_alias="supersedesDerivativeSnapshotId",
    )
    superseded_by_derivative_snapshot_id: str | None = Field(
        default=None,
        serialization_alias="supersededByDerivativeSnapshotId",
    )
    storage_key: str | None = Field(default=None, serialization_alias="storageKey")
    snapshot_sha256: str | None = Field(default=None, serialization_alias="snapshotSha256")
    candidate_snapshot_id: str | None = Field(
        default=None,
        serialization_alias="candidateSnapshotId",
    )
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    finished_at: datetime | None = Field(default=None, serialization_alias="finishedAt")
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    is_active_generation: bool = Field(serialization_alias="isActiveGeneration")


class DerivativeListResponse(BaseModel):
    scope: Literal["active", "historical"]
    active_derivative_index_id: str | None = Field(
        default=None,
        serialization_alias="activeDerivativeIndexId",
    )
    items: list[DerivativeSnapshotResponse]


class DerivativeDetailResponse(BaseModel):
    derivative: DerivativeSnapshotResponse


class DerivativeStatusResponse(BaseModel):
    derivative_id: str = Field(serialization_alias="derivativeId")
    derivative_index_id: str = Field(serialization_alias="derivativeIndexId")
    status: IndexStatusLiteral
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    finished_at: datetime | None = Field(default=None, serialization_alias="finishedAt")
    failure_reason: str | None = Field(default=None, serialization_alias="failureReason")
    candidate_snapshot_id: str | None = Field(
        default=None,
        serialization_alias="candidateSnapshotId",
    )


class DerivativePreviewRowResponse(BaseModel):
    id: str
    derivative_index_id: str = Field(serialization_alias="derivativeIndexId")
    derivative_snapshot_id: str = Field(serialization_alias="derivativeSnapshotId")
    derivative_kind: str = Field(serialization_alias="derivativeKind")
    source_snapshot_json: dict[str, object] = Field(
        serialization_alias="sourceSnapshotJson"
    )
    display_payload_json: dict[str, object] = Field(
        serialization_alias="displayPayloadJson"
    )
    suppressed_fields_json: dict[str, object] = Field(
        serialization_alias="suppressedFieldsJson"
    )
    created_at: datetime = Field(serialization_alias="createdAt")


class DerivativePreviewResponse(BaseModel):
    derivative_index_id: str = Field(serialization_alias="derivativeIndexId")
    derivative_snapshot_id: str = Field(serialization_alias="derivativeSnapshotId")
    derivative_kind: str = Field(serialization_alias="derivativeKind")
    status: IndexStatusLiteral
    rows: list[DerivativePreviewRowResponse]
    preview_count: int = Field(serialization_alias="previewCount")


class DerivativeCandidateSnapshotResponse(BaseModel):
    id: str
    candidate_kind: str = Field(serialization_alias="candidateKind")
    source_phase: str = Field(serialization_alias="sourcePhase")
    source_artifact_kind: str = Field(serialization_alias="sourceArtifactKind")
    source_artifact_id: str = Field(serialization_alias="sourceArtifactId")
    created_at: datetime = Field(serialization_alias="createdAt")


class DerivativeCandidateSnapshotCreateResponse(BaseModel):
    derivative_id: str = Field(serialization_alias="derivativeId")
    derivative_index_id: str = Field(serialization_alias="derivativeIndexId")
    candidate_snapshot_id: str = Field(serialization_alias="candidateSnapshotId")
    created: bool
    candidate: DerivativeCandidateSnapshotResponse


IndexFreshnessStatusLiteral = Literal["current", "stale", "missing", "blocked"]
SearchActivationBlockerCodeLiteral = Literal[
    "RUN_NOT_SUCCEEDED",
    "SEARCH_ELIGIBLE_INPUTS_MISSING",
    "SEARCH_LINE_ONLY_EXCLUDED_INVALID",
    "SEARCH_LINE_ONLY_FALLBACK_MARKER_MISSING",
    "SEARCH_LINE_ONLY_FALLBACK_REASON_MISSING",
    "TOKEN_ANCHOR_VALIDITY_MISSING",
    "TOKEN_ANCHOR_VALIDITY_FAILED",
    "TOKEN_GEOMETRY_COVERAGE_MISSING",
    "TOKEN_GEOMETRY_COVERAGE_FAILED",
]


class SearchCoverageSummaryResponse(BaseModel):
    eligible_input_count: int | None = Field(
        default=None,
        serialization_alias="eligibleInputCount",
    )
    token_anchor_valid_input_count: int | None = Field(
        default=None,
        serialization_alias="tokenAnchorValidInputCount",
    )
    token_geometry_covered_input_count: int | None = Field(
        default=None,
        serialization_alias="tokenGeometryCoveredInputCount",
    )
    historical_line_only_excluded_count: int = Field(
        serialization_alias="historicalLineOnlyExcludedCount"
    )
    historical_line_only_fallback_allowed: bool = Field(
        serialization_alias="historicalLineOnlyFallbackAllowed"
    )
    historical_line_only_fallback_reason: str | None = Field(
        default=None,
        serialization_alias="historicalLineOnlyFallbackReason",
    )


class SearchActivationGateBlockerResponse(BaseModel):
    code: SearchActivationBlockerCodeLiteral
    message: str
    metadata: dict[str, object]


class SearchActivationGateEvaluationResponse(BaseModel):
    passed: bool
    blockers: list[SearchActivationGateBlockerResponse]


class IndexFreshnessSnapshotResponse(BaseModel):
    status: IndexFreshnessStatusLiteral
    active_index_id: str | None = Field(default=None, serialization_alias="activeIndexId")
    active_version: int | None = Field(default=None, serialization_alias="activeVersion")
    active_status: IndexStatusLiteral | None = Field(
        default=None,
        serialization_alias="activeStatus",
    )
    latest_succeeded_index_id: str | None = Field(
        default=None,
        serialization_alias="latestSucceededIndexId",
    )
    latest_succeeded_version: int | None = Field(
        default=None,
        serialization_alias="latestSucceededVersion",
    )
    latest_succeeded_finished_at: datetime | None = Field(
        default=None,
        serialization_alias="latestSucceededFinishedAt",
    )
    stale_generation_gap: int | None = Field(
        default=None,
        serialization_alias="staleGenerationGap",
    )
    reason: str | None = None
    blocked_codes: list[str] = Field(serialization_alias="blockedCodes")


class IndexQualitySummaryItemResponse(BaseModel):
    kind: IndexKindLiteral
    freshness: IndexFreshnessSnapshotResponse
    search_coverage: SearchCoverageSummaryResponse | None = Field(
        default=None,
        serialization_alias="searchCoverage",
    )
    search_activation_blocker_count: int = Field(
        serialization_alias="searchActivationBlockerCount"
    )


class IndexQualitySummaryResponse(BaseModel):
    project_id: str = Field(serialization_alias="projectId")
    projection_updated_at: datetime | None = Field(
        default=None,
        serialization_alias="projectionUpdatedAt",
    )
    items: list[IndexQualitySummaryItemResponse]


class IndexQualityDetailResponse(BaseModel):
    project_id: str = Field(serialization_alias="projectId")
    kind: IndexKindLiteral
    index: IndexResponse
    freshness: IndexFreshnessSnapshotResponse
    active_index_id: str | None = Field(default=None, serialization_alias="activeIndexId")
    is_active_generation: bool = Field(serialization_alias="isActiveGeneration")
    is_latest_succeeded_generation: bool = Field(
        serialization_alias="isLatestSucceededGeneration"
    )
    rollback_eligible: bool = Field(serialization_alias="rollbackEligible")
    search_coverage: SearchCoverageSummaryResponse | None = Field(
        default=None,
        serialization_alias="searchCoverage",
    )
    search_activation_evaluation: SearchActivationGateEvaluationResponse | None = Field(
        default=None,
        serialization_alias="searchActivationEvaluation",
    )


class SearchQueryAuditRecordResponse(BaseModel):
    id: str
    project_id: str = Field(serialization_alias="projectId")
    actor_user_id: str = Field(serialization_alias="actorUserId")
    search_index_id: str = Field(serialization_alias="searchIndexId")
    query_sha256: str = Field(serialization_alias="querySha256")
    query_text_key: str = Field(serialization_alias="queryTextKey")
    filters_json: dict[str, object] = Field(serialization_alias="filtersJson")
    result_count: int = Field(serialization_alias="resultCount")
    created_at: datetime = Field(serialization_alias="createdAt")


class SearchQueryAuditListResponse(BaseModel):
    project_id: str = Field(serialization_alias="projectId")
    items: list[SearchQueryAuditRecordResponse]
    next_cursor: int | None = Field(default=None, serialization_alias="nextCursor")


def _as_derivative_snapshot_response(
    row: DerivativeSnapshotRecord,
    *,
    is_active_generation: bool,
) -> DerivativeSnapshotResponse:
    return DerivativeSnapshotResponse(
        id=row.id,
        project_id=row.project_id,
        derivative_index_id=row.derivative_index_id,
        derivative_kind=row.derivative_kind,
        source_snapshot_json=row.source_snapshot_json,
        policy_version_ref=row.policy_version_ref,
        status=row.status,
        supersedes_derivative_snapshot_id=row.supersedes_derivative_snapshot_id,
        superseded_by_derivative_snapshot_id=row.superseded_by_derivative_snapshot_id,
        storage_key=row.storage_key,
        snapshot_sha256=row.snapshot_sha256,
        candidate_snapshot_id=row.candidate_snapshot_id,
        created_by=row.created_by,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
        failure_reason=row.failure_reason,
        is_active_generation=is_active_generation,
    )


def _as_derivative_row_response(row: DerivativeIndexRowRecord) -> DerivativePreviewRowResponse:
    return DerivativePreviewRowResponse(
        id=row.id,
        derivative_index_id=row.derivative_index_id,
        derivative_snapshot_id=row.derivative_snapshot_id,
        derivative_kind=row.derivative_kind,
        source_snapshot_json=row.source_snapshot_json,
        display_payload_json=row.display_payload_json,
        suppressed_fields_json=row.suppressed_fields_json,
        created_at=row.created_at,
    )


def _as_index_response(row: IndexRecord) -> IndexResponse:
    return IndexResponse(
        id=row.id,
        project_id=row.project_id,
        kind=row.kind,
        version=row.version,
        source_snapshot_json=row.source_snapshot_json,
        source_snapshot_sha256=row.source_snapshot_sha256,
        build_parameters_json=row.build_parameters_json,
        rebuild_dedupe_key=row.rebuild_dedupe_key,
        status=row.status,
        supersedes_index_id=row.supersedes_index_id,
        superseded_by_index_id=row.superseded_by_index_id,
        failure_reason=row.failure_reason,
        created_by=row.created_by,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
        cancel_requested=row.cancel_requested,
        cancel_requested_by=row.cancel_requested_by,
        cancel_requested_at=row.cancel_requested_at,
        canceled_by=row.canceled_by,
        canceled_at=row.canceled_at,
        activated_by=row.activated_by,
        activated_at=row.activated_at,
    )


def _as_status_response(row: IndexRecord) -> IndexStatusResponse:
    return IndexStatusResponse(
        id=row.id,
        project_id=row.project_id,
        kind=row.kind,
        status=row.status,
        started_at=row.started_at,
        finished_at=row.finished_at,
        cancel_requested=row.cancel_requested,
        cancel_requested_at=row.cancel_requested_at,
        canceled_at=row.canceled_at,
        failure_reason=row.failure_reason,
    )


def _as_projection_response(row: ProjectIndexProjectionRecord) -> ProjectIndexProjectionResponse:
    return ProjectIndexProjectionResponse(
        project_id=row.project_id,
        active_search_index_id=row.active_search_index_id,
        active_entity_index_id=row.active_entity_index_id,
        active_derivative_index_id=row.active_derivative_index_id,
        updated_at=row.updated_at,
    )


def _as_active_response(project_id: str, view: ActiveProjectIndexesView) -> ActiveIndexesResponse:
    return ActiveIndexesResponse(
        project_id=project_id,
        projection=(
            _as_projection_response(view.projection) if view.projection is not None else None
        ),
        search_index=(
            _as_index_response(view.search_index) if view.search_index is not None else None
        ),
        entity_index=(
            _as_index_response(view.entity_index) if view.entity_index is not None else None
        ),
        derivative_index=(
            _as_index_response(view.derivative_index)
            if view.derivative_index is not None
            else None
        ),
    )


def _as_search_hit_response(row: SearchDocumentRecord) -> SearchHitResponse:
    return SearchHitResponse(
        search_document_id=row.id,
        search_index_id=row.search_index_id,
        document_id=row.document_id,
        run_id=row.run_id,
        page_id=row.page_id,
        page_number=row.page_number,
        line_id=row.line_id,
        token_id=row.token_id,
        source_kind=row.source_kind,
        source_ref_id=row.source_ref_id,
        match_span_json=row.match_span_json,
        token_geometry_json=row.token_geometry_json,
        search_text=row.search_text,
        search_metadata_json=row.search_metadata_json,
    )


def _as_controlled_entity_response(row: ControlledEntityRecord) -> ControlledEntityResponse:
    return ControlledEntityResponse(
        id=row.id,
        project_id=row.project_id,
        entity_index_id=row.entity_index_id,
        entity_type=row.entity_type,
        display_value=row.display_value,
        canonical_value=row.canonical_value,
        confidence_summary_json=row.confidence_summary_json,
        occurrence_count=row.occurrence_count,
        created_at=row.created_at,
    )


def _workspace_path_from_hit(project_id: str, row: SearchDocumentRecord) -> str:
    base = (
        f"/projects/{quote(project_id, safe='')}"
        f"/documents/{quote(row.document_id, safe='')}"
        "/transcription/workspace"
    )
    params: dict[str, str | int] = {
        "page": row.page_number,
        "runId": row.run_id,
    }
    if isinstance(row.line_id, str) and row.line_id.strip():
        params["lineId"] = row.line_id.strip()
    if isinstance(row.token_id, str) and row.token_id.strip():
        params["tokenId"] = row.token_id.strip()
    if isinstance(row.source_kind, str) and row.source_kind.strip():
        params["sourceKind"] = row.source_kind.strip()
    if isinstance(row.source_ref_id, str) and row.source_ref_id.strip():
        params["sourceRefId"] = row.source_ref_id.strip()
    return f"{base}?{urlencode(sorted(params.items()))}"


def _workspace_path_from_occurrence(project_id: str, row: EntityOccurrenceLink) -> str:
    base = (
        f"/projects/{quote(project_id, safe='')}"
        f"/documents/{quote(row.document_id, safe='')}"
        "/transcription/workspace"
    )
    params: dict[str, str | int] = {
        "page": row.page_number,
        "runId": row.run_id,
    }
    if isinstance(row.line_id, str) and row.line_id.strip():
        params["lineId"] = row.line_id.strip()
    if isinstance(row.token_id, str) and row.token_id.strip():
        params["tokenId"] = row.token_id.strip()
    if isinstance(row.source_kind, str) and row.source_kind.strip():
        params["sourceKind"] = row.source_kind.strip()
    if isinstance(row.source_ref_id, str) and row.source_ref_id.strip():
        params["sourceRefId"] = row.source_ref_id.strip()
    return f"{base}?{urlencode(sorted(params.items()))}"


def _as_entity_occurrence_response(
    project_id: str,
    row: EntityOccurrenceLink,
) -> EntityOccurrenceResponse:
    return EntityOccurrenceResponse(
        id=row.id,
        entity_index_id=row.entity_index_id,
        entity_id=row.entity_id,
        document_id=row.document_id,
        run_id=row.run_id,
        page_id=row.page_id,
        page_number=row.page_number,
        line_id=row.line_id,
        token_id=row.token_id,
        source_kind=row.source_kind,  # type: ignore[arg-type]
        source_ref_id=row.source_ref_id,
        confidence=row.confidence,
        occurrence_span_json=row.occurrence_span_json,
        occurrence_span_basis_kind=row.occurrence_span_basis_kind,
        occurrence_span_basis_ref=row.occurrence_span_basis_ref,
        token_geometry_json=row.token_geometry_json,
        workspace_path=_workspace_path_from_occurrence(project_id, row),
    )


def _as_search_coverage_response(
    coverage: SearchCoverageSummary | None,
) -> SearchCoverageSummaryResponse | None:
    if coverage is None:
        return None
    return SearchCoverageSummaryResponse(
        eligible_input_count=coverage.eligible_input_count,
        token_anchor_valid_input_count=coverage.token_anchor_valid_input_count,
        token_geometry_covered_input_count=coverage.token_geometry_covered_input_count,
        historical_line_only_excluded_count=coverage.historical_line_only_excluded_count,
        historical_line_only_fallback_allowed=coverage.historical_line_only_fallback_allowed,
        historical_line_only_fallback_reason=coverage.historical_line_only_fallback_reason,
    )


def _as_search_activation_blocker_response(
    blocker: SearchActivationGateBlocker,
) -> SearchActivationGateBlockerResponse:
    return SearchActivationGateBlockerResponse(
        code=blocker.code,
        message=blocker.message,
        metadata=blocker.metadata,
    )


def _as_search_activation_evaluation_response(
    evaluation: SearchActivationGateEvaluation | None,
) -> SearchActivationGateEvaluationResponse | None:
    if evaluation is None:
        return None
    return SearchActivationGateEvaluationResponse(
        passed=evaluation.passed,
        blockers=[
            _as_search_activation_blocker_response(blocker)
            for blocker in evaluation.blockers
        ],
    )


def _as_freshness_response(
    freshness: IndexFreshnessSnapshot,
) -> IndexFreshnessSnapshotResponse:
    return IndexFreshnessSnapshotResponse(
        status=freshness.status,
        active_index_id=freshness.active_index_id,
        active_version=freshness.active_version,
        active_status=freshness.active_status,
        latest_succeeded_index_id=freshness.latest_succeeded_index_id,
        latest_succeeded_version=freshness.latest_succeeded_version,
        latest_succeeded_finished_at=freshness.latest_succeeded_finished_at,
        stale_generation_gap=freshness.stale_generation_gap,
        reason=freshness.reason,
        blocked_codes=list(freshness.blocked_codes),
    )


def _as_index_quality_summary_item_response(
    item: IndexQualitySummaryItem,
) -> IndexQualitySummaryItemResponse:
    return IndexQualitySummaryItemResponse(
        kind=item.kind,
        freshness=_as_freshness_response(item.freshness),
        search_coverage=_as_search_coverage_response(item.search_coverage),
        search_activation_blocker_count=item.search_activation_blocker_count,
    )


def _as_index_quality_summary_response(
    summary: ProjectIndexQualitySummary,
) -> IndexQualitySummaryResponse:
    return IndexQualitySummaryResponse(
        project_id=summary.project_id,
        projection_updated_at=summary.projection_updated_at,
        items=[
            _as_index_quality_summary_item_response(item)
            for item in summary.items
        ],
    )


def _as_index_quality_detail_response(
    detail: IndexQualityDetail,
) -> IndexQualityDetailResponse:
    return IndexQualityDetailResponse(
        project_id=detail.project_id,
        kind=detail.kind,
        index=_as_index_response(detail.index),
        freshness=_as_freshness_response(detail.freshness),
        active_index_id=detail.active_index_id,
        is_active_generation=detail.is_active_generation,
        is_latest_succeeded_generation=detail.is_latest_succeeded_generation,
        rollback_eligible=detail.rollback_eligible,
        search_coverage=_as_search_coverage_response(detail.search_coverage),
        search_activation_evaluation=_as_search_activation_evaluation_response(
            detail.search_activation_evaluation
        ),
    )


def _as_search_query_audit_record_response(
    row: SearchQueryAuditRecord,
) -> SearchQueryAuditRecordResponse:
    return SearchQueryAuditRecordResponse(
        id=row.id,
        project_id=row.project_id,
        actor_user_id=row.actor_user_id,
        search_index_id=row.search_index_id,
        query_sha256=row.query_sha256,
        query_text_key=row.query_text_key,
        filters_json=row.filters_json,
        result_count=row.result_count,
        created_at=row.created_at,
    )


def _parse_index_kind(value: str) -> IndexKind:
    normalized = value.strip().upper()
    if normalized == "SEARCH":
        return "SEARCH"
    if normalized == "ENTITY":
        return "ENTITY"
    if normalized == "DERIVATIVE":
        return "DERIVATIVE"
    raise IndexValidationError("indexKind must be one of SEARCH, ENTITY, DERIVATIVE.")


def _read_roles() -> list[str]:
    return ["PROJECT_LEAD", "RESEARCHER", "REVIEWER", "ADMIN"]


def _record_access_denied(
    *,
    audit_service: AuditService,
    request_context: AuditRequestContext,
    actor_user_id: str,
    project_id: str,
    required_roles: list[str],
) -> None:
    audit_service.record_event_best_effort(
        event_type="ACCESS_DENIED",
        actor_user_id=actor_user_id,
        project_id=project_id,
        metadata={
            "route": request_context.route_template,
            "required_roles": required_roles,
            "status_code": status.HTTP_403_FORBIDDEN,
        },
        request_context=request_context,
    )


def _raise_http(
    *,
    error: Exception,
    current_user: SessionPrincipal,
    project_id: str,
    request_context: AuditRequestContext,
    audit_service: AuditService,
    required_roles: list[str],
) -> None:
    if isinstance(error, IndexAccessDeniedError):
        _record_access_denied(
            audit_service=audit_service,
            request_context=request_context,
            actor_user_id=current_user.user_id,
            project_id=project_id,
            required_roles=required_roles,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    if isinstance(error, IndexNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if isinstance(error, IndexConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    if isinstance(error, IndexValidationError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    if isinstance(error, IndexStoreUnavailableError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Index store is unavailable.",
        ) from error
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unexpected index management failure.",
    ) from error


def _list_view_event(kind: IndexKind) -> str:
    if kind == "SEARCH":
        return "SEARCH_INDEX_LIST_VIEWED"
    if kind == "ENTITY":
        return "ENTITY_INDEX_LIST_VIEWED"
    return "DERIVATIVE_INDEX_LIST_VIEWED"


def _detail_view_event(kind: IndexKind) -> str:
    if kind == "SEARCH":
        return "SEARCH_INDEX_DETAIL_VIEWED"
    if kind == "ENTITY":
        return "ENTITY_INDEX_DETAIL_VIEWED"
    return "DERIVATIVE_INDEX_DETAIL_VIEWED"


def _status_view_event(kind: IndexKind) -> str:
    if kind == "SEARCH":
        return "SEARCH_INDEX_STATUS_VIEWED"
    if kind == "ENTITY":
        return "ENTITY_INDEX_STATUS_VIEWED"
    return "DERIVATIVE_INDEX_STATUS_VIEWED"


def _list_indexes(
    *,
    kind: IndexKind,
    project_id: str,
    current_user: SessionPrincipal,
    request_context: AuditRequestContext,
    audit_service: AuditService,
    index_service: IndexService,
) -> IndexListResponse:
    try:
        rows = index_service.list_indexes(
            current_user=current_user,
            project_id=project_id,
            kind=kind,
        )
    except Exception as error:  # pragma: no cover
        _raise_http(
            error=error,
            current_user=current_user,
            project_id=project_id,
            request_context=request_context,
            audit_service=audit_service,
            required_roles=_read_roles(),
        )
    audit_service.record_event_best_effort(
        event_type=_list_view_event(kind),  # type: ignore[arg-type]
        actor_user_id=current_user.user_id,
        project_id=project_id,
        metadata={
            "route": request_context.route_template,
            "returned_count": len(rows),
        },
        request_context=request_context,
    )
    return IndexListResponse(items=[_as_index_response(row) for row in rows])


def _get_index(
    *,
    kind: IndexKind,
    project_id: str,
    index_id: str,
    current_user: SessionPrincipal,
    request_context: AuditRequestContext,
    audit_service: AuditService,
    index_service: IndexService,
) -> IndexRecord:
    try:
        row = index_service.get_index(
            current_user=current_user,
            project_id=project_id,
            kind=kind,
            index_id=index_id,
        )
    except Exception as error:  # pragma: no cover
        _raise_http(
            error=error,
            current_user=current_user,
            project_id=project_id,
            request_context=request_context,
            audit_service=audit_service,
            required_roles=_read_roles(),
        )
    return row


def _record_index_detail_audit(
    *,
    kind: IndexKind,
    row: IndexRecord,
    current_user: SessionPrincipal,
    request_context: AuditRequestContext,
    audit_service: AuditService,
) -> None:
    audit_service.record_event_best_effort(
        event_type=_detail_view_event(kind),  # type: ignore[arg-type]
        actor_user_id=current_user.user_id,
        project_id=row.project_id,
        object_type=f"{kind.lower()}_index",
        object_id=row.id,
        metadata={
            "route": request_context.route_template,
            "index_id": row.id,
            "status": row.status,
            "version": row.version,
        },
        request_context=request_context,
    )


def _record_index_status_audit(
    *,
    kind: IndexKind,
    row: IndexRecord,
    current_user: SessionPrincipal,
    request_context: AuditRequestContext,
    audit_service: AuditService,
) -> None:
    audit_service.record_event_best_effort(
        event_type=_status_view_event(kind),  # type: ignore[arg-type]
        actor_user_id=current_user.user_id,
        project_id=row.project_id,
        object_type=f"{kind.lower()}_index",
        object_id=row.id,
        metadata={
            "route": request_context.route_template,
            "index_id": row.id,
            "status": row.status,
        },
        request_context=request_context,
    )


def _rebuild_index(
    *,
    kind: IndexKind,
    project_id: str,
    payload: RebuildIndexRequest,
    force: bool,
    current_user: SessionPrincipal,
    request_context: AuditRequestContext,
    audit_service: AuditService,
    index_service: IndexService,
) -> IndexRebuildResponse:
    try:
        result = index_service.rebuild_index(
            current_user=current_user,
            project_id=project_id,
            kind=kind,
            source_snapshot_json=payload.source_snapshot_json,
            build_parameters_json=payload.build_parameters_json,
            force=force,
            supersedes_index_id=payload.supersedes_index_id,
        )
    except Exception as error:  # pragma: no cover
        _raise_http(
            error=error,
            current_user=current_user,
            project_id=project_id,
            request_context=request_context,
            audit_service=audit_service,
            required_roles=["ADMIN"],
        )

    if result.created:
        index_service.record_run_created_audit(
            actor_user_id=current_user.user_id,
            project_id=project_id,
            kind=kind,
            index=result.index,
            route=request_context.route_template,
            reason=result.reason,
        )

    return IndexRebuildResponse(
        index=_as_index_response(result.index),
        created=result.created,
        reason=result.reason,
    )


def _cancel_index(
    *,
    kind: IndexKind,
    project_id: str,
    index_id: str,
    current_user: SessionPrincipal,
    request_context: AuditRequestContext,
    audit_service: AuditService,
    index_service: IndexService,
) -> IndexCancelResponse:
    try:
        result = index_service.cancel_index(
            current_user=current_user,
            project_id=project_id,
            kind=kind,
            index_id=index_id,
        )
    except Exception as error:  # pragma: no cover
        _raise_http(
            error=error,
            current_user=current_user,
            project_id=project_id,
            request_context=request_context,
            audit_service=audit_service,
            required_roles=["ADMIN"],
        )

    mode = "TERMINAL" if result.terminal else "REQUESTED"
    index_service.record_run_canceled_audit(
        actor_user_id=current_user.user_id,
        project_id=project_id,
        kind=kind,
        index=result.index,
        route=request_context.route_template,
        mode=mode,
    )

    return IndexCancelResponse(
        index=_as_index_response(result.index),
        terminal=result.terminal,
    )


def _activate_index(
    *,
    kind: IndexKind,
    project_id: str,
    index_id: str,
    current_user: SessionPrincipal,
    request_context: AuditRequestContext,
    audit_service: AuditService,
    index_service: IndexService,
) -> IndexActivateResponse:
    try:
        index, projection = index_service.activate_index(
            current_user=current_user,
            project_id=project_id,
            kind=kind,
            index_id=index_id,
        )
    except Exception as error:  # pragma: no cover
        _raise_http(
            error=error,
            current_user=current_user,
            project_id=project_id,
            request_context=request_context,
            audit_service=audit_service,
            required_roles=["ADMIN"],
        )

    if kind == "SEARCH":
        audit_service.record_event_best_effort(
            event_type="SEARCH_INDEX_ACTIVATED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="search_index",
            object_id=index.id,
            metadata={
                "route": request_context.route_template,
                "index_id": index.id,
                "status": index.status,
                "version": index.version,
            },
            request_context=request_context,
        )
    elif kind == "DERIVATIVE":
        audit_service.record_event_best_effort(
            event_type="DERIVATIVE_INDEX_ACTIVATED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="derivative_index",
            object_id=index.id,
            metadata={
                "route": request_context.route_template,
                "index_id": index.id,
                "status": index.status,
                "version": index.version,
            },
            request_context=request_context,
        )

    return IndexActivateResponse(
        index=_as_index_response(index),
        projection=_as_projection_response(projection),
    )


@router.get("/indexes/active", response_model=ActiveIndexesResponse)
def get_project_active_indexes(
    project_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> ActiveIndexesResponse:
    try:
        view = index_service.get_active_indexes(
            current_user=current_user,
            project_id=project_id,
        )
    except Exception as error:  # pragma: no cover
        _raise_http(
            error=error,
            current_user=current_user,
            project_id=project_id,
            request_context=request_context,
            audit_service=audit_service,
            required_roles=_read_roles(),
        )

    audit_service.record_event_best_effort(
        event_type="INDEX_ACTIVE_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        metadata={
            "route": request_context.route_template,
            "active_search_index_id": (
                view.projection.active_search_index_id if view.projection else ""
            ),
            "active_entity_index_id": (
                view.projection.active_entity_index_id if view.projection else ""
            ),
            "active_derivative_index_id": (
                view.projection.active_derivative_index_id if view.projection else ""
            ),
        },
        request_context=request_context,
    )
    return _as_active_response(project_id, view)


@router.get("/search", response_model=SearchQueryResponse)
def search_project_transcripts(
    project_id: str,
    q: str = Query(min_length=1, max_length=600, alias="q"),
    document_id: str | None = Query(default=None, alias="documentId"),
    run_id: str | None = Query(default=None, alias="runId"),
    page_number: int | None = Query(default=None, ge=1, alias="pageNumber"),
    cursor: int = Query(default=0, ge=0, alias="cursor"),
    limit: int = Query(default=25, ge=1, le=100, alias="limit"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> SearchQueryResponse:
    try:
        result: ProjectSearchResult = index_service.search_project(
            current_user=current_user,
            project_id=project_id,
            query_text=q,
            document_id=document_id,
            run_id=run_id,
            page_number=page_number,
            cursor=cursor,
            limit=limit,
            route=request_context.route_template,
        )
    except Exception as error:  # pragma: no cover
        _raise_http(
            error=error,
            current_user=current_user,
            project_id=project_id,
            request_context=request_context,
            audit_service=audit_service,
            required_roles=_read_roles(),
        )
    return SearchQueryResponse(
        search_index_id=result.search_index_id,
        items=[_as_search_hit_response(item) for item in result.items],
        next_cursor=result.next_cursor,
    )


@router.post("/search/{search_document_id}/open", response_model=SearchResultOpenResponse)
def open_project_search_result(
    project_id: str,
    search_document_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> SearchResultOpenResponse:
    try:
        row = index_service.open_search_result(
            current_user=current_user,
            project_id=project_id,
            search_document_id=search_document_id,
            route=request_context.route_template,
        )
    except Exception as error:  # pragma: no cover
        _raise_http(
            error=error,
            current_user=current_user,
            project_id=project_id,
            request_context=request_context,
            audit_service=audit_service,
            required_roles=_read_roles(),
        )
    return SearchResultOpenResponse(
        search_index_id=row.search_index_id,
        search_document_id=row.id,
        document_id=row.document_id,
        run_id=row.run_id,
        page_number=row.page_number,
        line_id=row.line_id,
        token_id=row.token_id,
        source_kind=row.source_kind,
        source_ref_id=row.source_ref_id,
        workspace_path=_workspace_path_from_hit(project_id, row),
    )


@router.get("/entities", response_model=EntityListResponse)
def list_project_entities(
    project_id: str,
    q: str | None = Query(default=None, max_length=600, alias="q"),
    entity_type: str | None = Query(default=None, alias="entityType"),
    cursor: int = Query(default=0, ge=0, alias="cursor"),
    limit: int = Query(default=25, ge=1, le=100, alias="limit"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> EntityListResponse:
    try:
        result: ProjectEntityListResult = index_service.list_project_entities(
            current_user=current_user,
            project_id=project_id,
            query_text=q,
            entity_type=entity_type,
            cursor=cursor,
            limit=limit,
        )
    except Exception as error:  # pragma: no cover
        _raise_http(
            error=error,
            current_user=current_user,
            project_id=project_id,
            request_context=request_context,
            audit_service=audit_service,
            required_roles=_read_roles(),
        )

    audit_service.record_event_best_effort(
        event_type="ENTITY_LIST_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        metadata={
            "route": request_context.route_template,
            "entity_index_id": result.entity_index_id,
            "returned_count": len(result.items),
            "cursor": cursor,
            "query": (q or "").strip(),
            "entity_type_filter": (entity_type or "").strip(),
        },
        request_context=request_context,
    )
    return EntityListResponse(
        entity_index_id=result.entity_index_id,
        items=[_as_controlled_entity_response(item) for item in result.items],
        next_cursor=result.next_cursor,
    )


@router.get("/entities/{entity_id}", response_model=EntityDetailResponse)
def get_project_entity_detail(
    project_id: str,
    entity_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> EntityDetailResponse:
    try:
        result: ProjectEntityDetailResult = index_service.get_project_entity_detail(
            current_user=current_user,
            project_id=project_id,
            entity_id=entity_id,
        )
    except Exception as error:  # pragma: no cover
        _raise_http(
            error=error,
            current_user=current_user,
            project_id=project_id,
            request_context=request_context,
            audit_service=audit_service,
            required_roles=_read_roles(),
        )

    audit_service.record_event_best_effort(
        event_type="ENTITY_DETAIL_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="controlled_entity",
        object_id=result.entity.id,
        metadata={
            "route": request_context.route_template,
            "entity_index_id": result.entity_index_id,
            "entity_id": result.entity.id,
        },
        request_context=request_context,
    )
    return EntityDetailResponse(
        entity_index_id=result.entity_index_id,
        entity=_as_controlled_entity_response(result.entity),
    )


@router.get("/entities/{entity_id}/occurrences", response_model=EntityOccurrencesResponse)
def list_project_entity_occurrences(
    project_id: str,
    entity_id: str,
    cursor: int = Query(default=0, ge=0, alias="cursor"),
    limit: int = Query(default=25, ge=1, le=100, alias="limit"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> EntityOccurrencesResponse:
    try:
        result: ProjectEntityOccurrencesResult = index_service.list_project_entity_occurrences(
            current_user=current_user,
            project_id=project_id,
            entity_id=entity_id,
            cursor=cursor,
            limit=limit,
        )
    except Exception as error:  # pragma: no cover
        _raise_http(
            error=error,
            current_user=current_user,
            project_id=project_id,
            request_context=request_context,
            audit_service=audit_service,
            required_roles=_read_roles(),
        )

    audit_service.record_event_best_effort(
        event_type="ENTITY_OCCURRENCES_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="controlled_entity",
        object_id=result.entity.id,
        metadata={
            "route": request_context.route_template,
            "entity_index_id": result.entity_index_id,
            "entity_id": result.entity.id,
            "returned_count": len(result.items),
            "cursor": cursor,
        },
        request_context=request_context,
    )
    return EntityOccurrencesResponse(
        entity_index_id=result.entity_index_id,
        entity=_as_controlled_entity_response(result.entity),
        items=[
            _as_entity_occurrence_response(project_id, occurrence)
            for occurrence in result.items
        ],
        next_cursor=result.next_cursor,
    )


@router.get("/derivatives", response_model=DerivativeListResponse)
def list_project_derivatives(
    project_id: str,
    scope: Literal["active", "historical"] = Query(default="active", alias="scope"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> DerivativeListResponse:
    try:
        result: ProjectDerivativeListResult = index_service.list_project_derivatives(
            current_user=current_user,
            project_id=project_id,
            scope=scope,
        )
    except Exception as error:  # pragma: no cover
        _raise_http(
            error=error,
            current_user=current_user,
            project_id=project_id,
            request_context=request_context,
            audit_service=audit_service,
            required_roles=_read_roles(),
        )

    audit_service.record_event_best_effort(
        event_type="DERIVATIVE_LIST_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        metadata={
            "route": request_context.route_template,
            "scope": result.scope,
            "active_derivative_index_id": result.active_derivative_index_id or "",
            "returned_count": len(result.items),
        },
        request_context=request_context,
    )
    return DerivativeListResponse(
        scope=result.scope,
        active_derivative_index_id=result.active_derivative_index_id,
        items=[
            _as_derivative_snapshot_response(
                item.snapshot,
                is_active_generation=item.is_active_generation,
            )
            for item in result.items
        ],
    )


@router.get("/derivatives/{derivative_id}", response_model=DerivativeDetailResponse)
def get_project_derivative_detail(
    project_id: str,
    derivative_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> DerivativeDetailResponse:
    try:
        result: ProjectDerivativeDetailResult = index_service.get_project_derivative_detail(
            current_user=current_user,
            project_id=project_id,
            derivative_id=derivative_id,
        )
    except Exception as error:  # pragma: no cover
        _raise_http(
            error=error,
            current_user=current_user,
            project_id=project_id,
            request_context=request_context,
            audit_service=audit_service,
            required_roles=_read_roles(),
        )
    snapshot = result.snapshot
    audit_service.record_event_best_effort(
        event_type="DERIVATIVE_DETAIL_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="derivative_snapshot",
        object_id=snapshot.id,
        metadata={
            "route": request_context.route_template,
            "derivative_id": snapshot.id,
            "derivative_index_id": snapshot.derivative_index_id,
            "status": snapshot.status,
        },
        request_context=request_context,
    )
    return DerivativeDetailResponse(
        derivative=_as_derivative_snapshot_response(
            snapshot,
            is_active_generation=False,
        )
    )


@router.get("/derivatives/{derivative_id}/status", response_model=DerivativeStatusResponse)
def get_project_derivative_status(
    project_id: str,
    derivative_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> DerivativeStatusResponse:
    try:
        result: ProjectDerivativeDetailResult = index_service.get_project_derivative_status(
            current_user=current_user,
            project_id=project_id,
            derivative_id=derivative_id,
        )
    except Exception as error:  # pragma: no cover
        _raise_http(
            error=error,
            current_user=current_user,
            project_id=project_id,
            request_context=request_context,
            audit_service=audit_service,
            required_roles=_read_roles(),
        )
    snapshot = result.snapshot
    audit_service.record_event_best_effort(
        event_type="DERIVATIVE_STATUS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="derivative_snapshot",
        object_id=snapshot.id,
        metadata={
            "route": request_context.route_template,
            "derivative_id": snapshot.id,
            "derivative_index_id": snapshot.derivative_index_id,
            "status": snapshot.status,
        },
        request_context=request_context,
    )
    return DerivativeStatusResponse(
        derivative_id=snapshot.id,
        derivative_index_id=snapshot.derivative_index_id,
        status=snapshot.status,
        started_at=snapshot.started_at,
        finished_at=snapshot.finished_at,
        failure_reason=snapshot.failure_reason,
        candidate_snapshot_id=snapshot.candidate_snapshot_id,
    )


@router.get("/derivatives/{derivative_id}/preview", response_model=DerivativePreviewResponse)
def preview_project_derivative(
    project_id: str,
    derivative_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> DerivativePreviewResponse:
    try:
        result: ProjectDerivativePreviewResult = index_service.preview_project_derivative(
            current_user=current_user,
            project_id=project_id,
            derivative_id=derivative_id,
        )
    except Exception as error:  # pragma: no cover
        _raise_http(
            error=error,
            current_user=current_user,
            project_id=project_id,
            request_context=request_context,
            audit_service=audit_service,
            required_roles=_read_roles(),
        )
    snapshot = result.snapshot
    rows = result.rows
    audit_service.record_event_best_effort(
        event_type="DERIVATIVE_PREVIEW_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="derivative_snapshot",
        object_id=snapshot.id,
        metadata={
            "route": request_context.route_template,
            "derivative_id": snapshot.id,
            "derivative_index_id": snapshot.derivative_index_id,
            "row_count": len(rows),
            "status": snapshot.status,
        },
        request_context=request_context,
    )
    return DerivativePreviewResponse(
        derivative_index_id=snapshot.derivative_index_id,
        derivative_snapshot_id=snapshot.id,
        derivative_kind=snapshot.derivative_kind,
        status=snapshot.status,
        rows=[_as_derivative_row_response(row) for row in rows],
        preview_count=len(rows),
    )


@router.post(
    "/derivatives/{derivative_id}/candidate-snapshots",
    response_model=DerivativeCandidateSnapshotCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def freeze_project_derivative_candidate_snapshot(
    project_id: str,
    derivative_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> DerivativeCandidateSnapshotCreateResponse:
    try:
        result: DerivativeCandidateFreezeResult = (
            index_service.freeze_derivative_candidate_snapshot(
                current_user=current_user,
                project_id=project_id,
                derivative_id=derivative_id,
            )
        )
    except Exception as error:  # pragma: no cover
        _raise_http(
            error=error,
            current_user=current_user,
            project_id=project_id,
            request_context=request_context,
            audit_service=audit_service,
            required_roles=["PROJECT_LEAD", "REVIEWER", "ADMIN"],
        )

    audit_service.record_event_best_effort(
        event_type="DERIVATIVE_CANDIDATE_SNAPSHOT_CREATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="derivative_snapshot",
        object_id=result.snapshot.id,
        metadata={
            "route": request_context.route_template,
            "derivative_id": result.snapshot.id,
            "derivative_index_id": result.snapshot.derivative_index_id,
            "candidate_snapshot_id": result.candidate.id,
            "created": result.created,
        },
        request_context=request_context,
    )
    return DerivativeCandidateSnapshotCreateResponse(
        derivative_id=result.snapshot.id,
        derivative_index_id=result.snapshot.derivative_index_id,
        candidate_snapshot_id=result.candidate.id,
        created=result.created,
        candidate=DerivativeCandidateSnapshotResponse(
            id=result.candidate.id,
            candidate_kind=result.candidate.candidate_kind,
            source_phase=result.candidate.source_phase,
            source_artifact_kind=result.candidate.source_artifact_kind,
            source_artifact_id=result.candidate.source_artifact_id,
            created_at=result.candidate.created_at,
        ),
    )


@router.get("/search-indexes", response_model=IndexListResponse)
def list_project_search_indexes(
    project_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> IndexListResponse:
    return _list_indexes(
        kind="SEARCH",
        project_id=project_id,
        current_user=current_user,
        request_context=request_context,
        audit_service=audit_service,
        index_service=index_service,
    )


@router.post(
    "/search-indexes/rebuild",
    response_model=IndexRebuildResponse,
    status_code=status.HTTP_201_CREATED,
)
def rebuild_project_search_index(
    project_id: str,
    payload: RebuildIndexRequest,
    force: bool = Query(default=False),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> IndexRebuildResponse:
    response = _rebuild_index(
        kind="SEARCH",
        project_id=project_id,
        payload=payload,
        force=force,
        current_user=current_user,
        request_context=request_context,
        audit_service=audit_service,
        index_service=index_service,
    )
    return response


@router.get("/search-indexes/{index_id}", response_model=IndexResponse)
def get_project_search_index(
    project_id: str,
    index_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> IndexResponse:
    row = _get_index(
        kind="SEARCH",
        project_id=project_id,
        index_id=index_id,
        current_user=current_user,
        request_context=request_context,
        audit_service=audit_service,
        index_service=index_service,
    )
    _record_index_detail_audit(
        kind="SEARCH",
        row=row,
        current_user=current_user,
        request_context=request_context,
        audit_service=audit_service,
    )
    return _as_index_response(row)


@router.get("/search-indexes/{index_id}/status", response_model=IndexStatusResponse)
def get_project_search_index_status(
    project_id: str,
    index_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> IndexStatusResponse:
    row = _get_index(
        kind="SEARCH",
        project_id=project_id,
        index_id=index_id,
        current_user=current_user,
        request_context=request_context,
        audit_service=audit_service,
        index_service=index_service,
    )
    _record_index_status_audit(
        kind="SEARCH",
        row=row,
        current_user=current_user,
        request_context=request_context,
        audit_service=audit_service,
    )
    return _as_status_response(row)


@router.post("/search-indexes/{index_id}/cancel", response_model=IndexCancelResponse)
def cancel_project_search_index(
    project_id: str,
    index_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> IndexCancelResponse:
    return _cancel_index(
        kind="SEARCH",
        project_id=project_id,
        index_id=index_id,
        current_user=current_user,
        request_context=request_context,
        audit_service=audit_service,
        index_service=index_service,
    )


@router.post("/search-indexes/{index_id}/activate", response_model=IndexActivateResponse)
def activate_project_search_index(
    project_id: str,
    index_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> IndexActivateResponse:
    return _activate_index(
        kind="SEARCH",
        project_id=project_id,
        index_id=index_id,
        current_user=current_user,
        request_context=request_context,
        audit_service=audit_service,
        index_service=index_service,
    )


@router.get("/entity-indexes", response_model=IndexListResponse)
def list_project_entity_indexes(
    project_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> IndexListResponse:
    return _list_indexes(
        kind="ENTITY",
        project_id=project_id,
        current_user=current_user,
        request_context=request_context,
        audit_service=audit_service,
        index_service=index_service,
    )


@router.post(
    "/entity-indexes/rebuild",
    response_model=IndexRebuildResponse,
    status_code=status.HTTP_201_CREATED,
)
def rebuild_project_entity_index(
    project_id: str,
    payload: RebuildIndexRequest,
    force: bool = Query(default=False),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> IndexRebuildResponse:
    return _rebuild_index(
        kind="ENTITY",
        project_id=project_id,
        payload=payload,
        force=force,
        current_user=current_user,
        request_context=request_context,
        audit_service=audit_service,
        index_service=index_service,
    )


@router.get("/entity-indexes/{index_id}", response_model=IndexResponse)
def get_project_entity_index(
    project_id: str,
    index_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> IndexResponse:
    row = _get_index(
        kind="ENTITY",
        project_id=project_id,
        index_id=index_id,
        current_user=current_user,
        request_context=request_context,
        audit_service=audit_service,
        index_service=index_service,
    )
    _record_index_detail_audit(
        kind="ENTITY",
        row=row,
        current_user=current_user,
        request_context=request_context,
        audit_service=audit_service,
    )
    return _as_index_response(row)


@router.get("/entity-indexes/{index_id}/status", response_model=IndexStatusResponse)
def get_project_entity_index_status(
    project_id: str,
    index_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> IndexStatusResponse:
    row = _get_index(
        kind="ENTITY",
        project_id=project_id,
        index_id=index_id,
        current_user=current_user,
        request_context=request_context,
        audit_service=audit_service,
        index_service=index_service,
    )
    _record_index_status_audit(
        kind="ENTITY",
        row=row,
        current_user=current_user,
        request_context=request_context,
        audit_service=audit_service,
    )
    return _as_status_response(row)


@router.post("/entity-indexes/{index_id}/cancel", response_model=IndexCancelResponse)
def cancel_project_entity_index(
    project_id: str,
    index_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> IndexCancelResponse:
    return _cancel_index(
        kind="ENTITY",
        project_id=project_id,
        index_id=index_id,
        current_user=current_user,
        request_context=request_context,
        audit_service=audit_service,
        index_service=index_service,
    )


@router.post("/entity-indexes/{index_id}/activate", response_model=IndexActivateResponse)
def activate_project_entity_index(
    project_id: str,
    index_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> IndexActivateResponse:
    return _activate_index(
        kind="ENTITY",
        project_id=project_id,
        index_id=index_id,
        current_user=current_user,
        request_context=request_context,
        audit_service=audit_service,
        index_service=index_service,
    )


@router.get("/derivative-indexes", response_model=IndexListResponse)
def list_project_derivative_indexes(
    project_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> IndexListResponse:
    return _list_indexes(
        kind="DERIVATIVE",
        project_id=project_id,
        current_user=current_user,
        request_context=request_context,
        audit_service=audit_service,
        index_service=index_service,
    )


@router.post(
    "/derivative-indexes/rebuild",
    response_model=IndexRebuildResponse,
    status_code=status.HTTP_201_CREATED,
)
def rebuild_project_derivative_index(
    project_id: str,
    payload: RebuildIndexRequest,
    force: bool = Query(default=False),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> IndexRebuildResponse:
    return _rebuild_index(
        kind="DERIVATIVE",
        project_id=project_id,
        payload=payload,
        force=force,
        current_user=current_user,
        request_context=request_context,
        audit_service=audit_service,
        index_service=index_service,
    )


@router.get("/derivative-indexes/{index_id}", response_model=IndexResponse)
def get_project_derivative_index(
    project_id: str,
    index_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> IndexResponse:
    row = _get_index(
        kind="DERIVATIVE",
        project_id=project_id,
        index_id=index_id,
        current_user=current_user,
        request_context=request_context,
        audit_service=audit_service,
        index_service=index_service,
    )
    _record_index_detail_audit(
        kind="DERIVATIVE",
        row=row,
        current_user=current_user,
        request_context=request_context,
        audit_service=audit_service,
    )
    return _as_index_response(row)


@router.get("/derivative-indexes/{index_id}/status", response_model=IndexStatusResponse)
def get_project_derivative_index_status(
    project_id: str,
    index_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> IndexStatusResponse:
    row = _get_index(
        kind="DERIVATIVE",
        project_id=project_id,
        index_id=index_id,
        current_user=current_user,
        request_context=request_context,
        audit_service=audit_service,
        index_service=index_service,
    )
    _record_index_status_audit(
        kind="DERIVATIVE",
        row=row,
        current_user=current_user,
        request_context=request_context,
        audit_service=audit_service,
    )
    return _as_status_response(row)


@router.post("/derivative-indexes/{index_id}/cancel", response_model=IndexCancelResponse)
def cancel_project_derivative_index(
    project_id: str,
    index_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> IndexCancelResponse:
    return _cancel_index(
        kind="DERIVATIVE",
        project_id=project_id,
        index_id=index_id,
        current_user=current_user,
        request_context=request_context,
        audit_service=audit_service,
        index_service=index_service,
    )


@router.post("/derivative-indexes/{index_id}/activate", response_model=IndexActivateResponse)
def activate_project_derivative_index(
    project_id: str,
    index_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> IndexActivateResponse:
    return _activate_index(
        kind="DERIVATIVE",
        project_id=project_id,
        index_id=index_id,
        current_user=current_user,
        request_context=request_context,
        audit_service=audit_service,
        index_service=index_service,
    )


def _raise_admin_http(error: Exception) -> None:
    if isinstance(error, IndexAccessDeniedError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    if isinstance(error, IndexNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if isinstance(error, IndexConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    if isinstance(error, IndexValidationError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    if isinstance(error, IndexStoreUnavailableError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Index store is unavailable.",
        ) from error
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unexpected index quality failure.",
    ) from error


@admin_router.get(
    "",
    response_model=IndexQualitySummaryResponse,
    dependencies=[Depends(require_platform_roles("ADMIN", "AUDITOR"))],
)
def get_admin_index_quality_summary(
    project_id: str = Query(alias="projectId"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> IndexQualitySummaryResponse:
    try:
        summary = index_service.get_index_quality_summary(
            current_user=current_user,
            project_id=project_id,
        )
    except Exception as error:  # pragma: no cover
        _raise_admin_http(error)

    blocked_count = len(
        [item for item in summary.items if item.freshness.status == "blocked"]
    )
    stale_count = len([item for item in summary.items if item.freshness.status == "stale"])
    audit_service.record_event_best_effort(
        event_type="INDEX_QUALITY_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        metadata={
            "route": request_context.route_template,
            "project_id": project_id,
            "item_count": len(summary.items),
            "blocked_count": blocked_count,
            "stale_count": stale_count,
        },
        request_context=request_context,
    )
    return _as_index_quality_summary_response(summary)


@admin_router.get(
    "/query-audits",
    response_model=SearchQueryAuditListResponse,
    dependencies=[Depends(require_platform_roles("ADMIN", "AUDITOR"))],
)
def list_admin_search_query_audits(
    project_id: str = Query(alias="projectId"),
    cursor: int = Query(default=0, ge=0, alias="cursor"),
    limit: int = Query(default=50, ge=1, le=100, alias="limit"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> SearchQueryAuditListResponse:
    try:
        result: ProjectSearchQueryAuditResult = index_service.list_search_query_audits(
            current_user=current_user,
            project_id=project_id,
            cursor=cursor,
            limit=limit,
        )
    except Exception as error:  # pragma: no cover
        _raise_admin_http(error)

    audit_service.record_event_best_effort(
        event_type="INDEX_QUALITY_QUERY_AUDITS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        metadata={
            "route": request_context.route_template,
            "project_id": project_id,
            "cursor": cursor,
            "limit": limit,
            "returned_count": len(result.items),
        },
        request_context=request_context,
    )
    return SearchQueryAuditListResponse(
        project_id=result.project_id,
        items=[
            _as_search_query_audit_record_response(item)
            for item in result.items
        ],
        next_cursor=result.next_cursor,
    )


@admin_router.get(
    "/{index_kind}/{index_id}",
    response_model=IndexQualityDetailResponse,
    dependencies=[Depends(require_platform_roles("ADMIN", "AUDITOR"))],
)
def get_admin_index_quality_detail(
    index_kind: str,
    index_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    index_service: IndexService = Depends(get_index_service),
) -> IndexQualityDetailResponse:
    try:
        kind = _parse_index_kind(index_kind)
        detail = index_service.get_index_quality_detail(
            current_user=current_user,
            kind=kind,
            index_id=index_id,
        )
    except Exception as error:  # pragma: no cover
        _raise_admin_http(error)

    blocker_count = (
        len(detail.search_activation_evaluation.blockers)
        if detail.search_activation_evaluation is not None
        else 0
    )
    audit_service.record_event_best_effort(
        event_type="INDEX_QUALITY_DETAIL_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=detail.project_id,
        object_type="index_quality_detail",
        object_id=detail.index.id,
        metadata={
            "route": request_context.route_template,
            "project_id": detail.project_id,
            "index_id": detail.index.id,
            "index_kind": detail.kind,
            "freshness_status": detail.freshness.status,
            "is_active_generation": detail.is_active_generation,
            "is_latest_succeeded_generation": detail.is_latest_succeeded_generation,
            "rollback_eligible": detail.rollback_eligible,
            "search_activation_blocker_count": blocker_count,
        },
        request_context=request_context,
    )
    return _as_index_quality_detail_response(detail)
