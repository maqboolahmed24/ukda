from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Literal
from uuid import uuid4

from app.audit.service import AuditService, get_audit_service
from app.auth.models import SessionPrincipal
from app.core.config import Settings, get_settings
from app.exports.models import ExportCandidateSnapshotRecord
from app.exports.store import (
    ExportStore,
    ExportStoreConflictError,
    ExportStoreNotFoundError,
    ExportStoreUnavailableError,
)
from app.indexes.models import (
    ActiveProjectIndexesView,
    ControlledEntityRecord,
    CreateDerivativeIndexRowInput,
    CreateControlledEntityInput,
    CreateEntityOccurrenceInput,
    DerivativeIndexRowRecord,
    DerivativeScope,
    DerivativeSnapshotListItem,
    DerivativeSnapshotRecord,
    EntityOccurrenceRecord,
    EntityType,
    IndexKind,
    IndexRecord,
    OccurrenceSpanBasisKind,
    ProjectIndexProjectionRecord,
    SearchDocumentRecord,
    SearchQueryAuditRecord,
)
from app.indexes.store import IndexStore, IndexStoreUnavailableError
from app.projects.models import ProjectRole, ProjectSummary
from app.projects.store import ProjectStore, ProjectStoreUnavailableError
from app.telemetry.context import current_trace_id

_READ_ROLES: set[ProjectRole] = {"PROJECT_LEAD", "RESEARCHER", "REVIEWER"}
_ALLOWED_ENTITY_TYPES: set[EntityType] = {
    "PERSON",
    "PLACE",
    "ORGANISATION",
    "DATE",
}
_ALLOWED_OCCURRENCE_SPAN_BASIS_KINDS: set[OccurrenceSpanBasisKind] = {
    "LINE_TEXT",
    "PAGE_WINDOW_TEXT",
    "NONE",
}
_PERSON_PATTERN = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")
_ORGANISATION_PATTERN = re.compile(
    r"\b([A-Z][\w&'-]*(?:\s+[A-Z][\w&'-]*)*\s+"
    r"(?:Company|Council|Guild|Institute|Ltd|Limited|Parish|Society|Trust|University))\b"
)
_PLACE_PATTERN = re.compile(r"\b(?:in|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b")
_DATE_PATTERN = re.compile(
    r"\b(?:\d{1,2}\s+[A-Z][a-z]{2,8}\s+\d{4}|"
    r"[A-Z][a-z]{2,8}\s+\d{1,2},\s*\d{4}|"
    r"\d{4}-\d{2}-\d{2})\b"
)
_DERIVATIVE_FREEZE_ROLES: set[ProjectRole] = {"PROJECT_LEAD", "REVIEWER"}
_INDEX_QUALITY_READ_ROLES: set[str] = {"ADMIN", "AUDITOR"}
_SUPPRESSED_IDENTIFIER_KEYS: set[str] = {
    "address",
    "date_of_birth",
    "dob",
    "document_id",
    "email",
    "first_name",
    "full_name",
    "given_name",
    "identifier",
    "id_number",
    "last_name",
    "line_id",
    "name",
    "national_insurance_number",
    "nhs_number",
    "ni_number",
    "page_id",
    "passport_number",
    "person_name",
    "phone",
    "post_code",
    "postcode",
    "raw_identifier",
    "run_id",
    "source_identifier",
    "surname",
    "token_id",
    "user_id",
}
_SUPPRESSED_IDENTIFIER_CANONICAL_KEYS: set[str] = {
    re.sub(r"[^a-z0-9]+", "", value.lower()) for value in _SUPPRESSED_IDENTIFIER_KEYS
}
_DEFAULT_ANTIJOIN_QUASI_FIELDS: tuple[str, ...] = (
    "category",
    "period",
    "geography",
    "region",
    "year",
    "month",
)
_SEARCH_ELIGIBLE_INPUT_KEYS: tuple[str, ...] = (
    "eligibleInputCount",
    "eligible_input_count",
    "eligibleTranscriptBasisCount",
    "eligible_transcript_basis_count",
    "eligibleTokenAnchorInputCount",
    "eligible_token_anchor_input_count",
)
_SEARCH_TOKEN_ANCHOR_VALID_KEYS: tuple[str, ...] = (
    "tokenAnchorValidInputCount",
    "token_anchor_valid_input_count",
    "validTokenAnchorInputCount",
    "valid_token_anchor_input_count",
    "tokenAnchorCurrentCount",
    "token_anchor_current_count",
)
_SEARCH_TOKEN_ANCHOR_INVALID_KEYS: tuple[str, ...] = (
    "tokenAnchorInvalidInputCount",
    "token_anchor_invalid_input_count",
    "invalidTokenAnchorInputCount",
    "invalid_token_anchor_input_count",
)
_SEARCH_GEOMETRY_COVERED_KEYS: tuple[str, ...] = (
    "tokenGeometryCoveredInputCount",
    "token_geometry_covered_input_count",
    "geometryCoveredInputCount",
    "geometry_covered_input_count",
    "geometryCoveragePassCount",
    "geometry_coverage_pass_count",
    "coveredInputCount",
    "covered_input_count",
)
_SEARCH_GEOMETRY_MISSING_KEYS: tuple[str, ...] = (
    "tokenGeometryMissingInputCount",
    "token_geometry_missing_input_count",
    "geometryMissingInputCount",
    "geometry_missing_input_count",
)
_SEARCH_LINE_ONLY_EXCLUDED_KEYS: tuple[str, ...] = (
    "historicalLineOnlyExcludedCount",
    "historical_line_only_excluded_count",
    "lineOnlyExcludedCount",
    "line_only_excluded_count",
    "excludedHistoricalLineOnlyCount",
    "excluded_historical_line_only_count",
)
_SEARCH_LINE_ONLY_FALLBACK_ALLOWED_KEYS: tuple[str, ...] = (
    "historicalLineOnlyFallbackAllowed",
    "historical_line_only_fallback_allowed",
    "lineOnlyFallbackAllowed",
    "line_only_fallback_allowed",
)
_SEARCH_LINE_ONLY_FALLBACK_REASON_KEYS: tuple[str, ...] = (
    "historicalLineOnlyFallbackReason",
    "historical_line_only_fallback_reason",
    "lineOnlyFallbackReason",
    "line_only_fallback_reason",
)


class IndexAccessDeniedError(RuntimeError):
    """Current session is not permitted for the requested index action."""


class IndexNotFoundError(RuntimeError):
    """Requested project or index resource does not exist."""


class IndexValidationError(RuntimeError):
    """Index payload validation failed."""


class IndexConflictError(RuntimeError):
    """Index lifecycle transition conflicts with current state."""


@dataclass(frozen=True)
class _ProjectIndexAccessContext:
    summary: ProjectSummary
    project_role: ProjectRole | None
    is_admin: bool


@dataclass(frozen=True)
class IndexRebuildResult:
    index: IndexRecord
    created: bool
    reason: str


@dataclass(frozen=True)
class IndexCancelResult:
    index: IndexRecord
    terminal: bool


@dataclass(frozen=True)
class ProjectSearchResult:
    search_index_id: str
    items: list[SearchDocumentRecord]
    next_cursor: int | None


IndexFreshnessStatus = Literal["current", "stale", "missing", "blocked"]
SearchActivationBlockerCode = Literal[
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


@dataclass(frozen=True)
class SearchActivationGateBlocker:
    code: SearchActivationBlockerCode
    message: str
    metadata: dict[str, object]


@dataclass(frozen=True)
class SearchActivationGateEvaluation:
    passed: bool
    blockers: list[SearchActivationGateBlocker]


@dataclass(frozen=True)
class SearchCoverageSummary:
    eligible_input_count: int | None
    token_anchor_valid_input_count: int | None
    token_geometry_covered_input_count: int | None
    historical_line_only_excluded_count: int
    historical_line_only_fallback_allowed: bool
    historical_line_only_fallback_reason: str | None


@dataclass(frozen=True)
class IndexFreshnessSnapshot:
    status: IndexFreshnessStatus
    active_index_id: str | None
    active_version: int | None
    active_status: str | None
    latest_succeeded_index_id: str | None
    latest_succeeded_version: int | None
    latest_succeeded_finished_at: datetime | None
    stale_generation_gap: int | None
    reason: str | None
    blocked_codes: list[str]


@dataclass(frozen=True)
class IndexQualitySummaryItem:
    kind: IndexKind
    freshness: IndexFreshnessSnapshot
    search_coverage: SearchCoverageSummary | None
    search_activation_blocker_count: int


@dataclass(frozen=True)
class ProjectIndexQualitySummary:
    project_id: str
    projection_updated_at: datetime | None
    items: list[IndexQualitySummaryItem]


@dataclass(frozen=True)
class IndexQualityDetail:
    project_id: str
    kind: IndexKind
    index: IndexRecord
    freshness: IndexFreshnessSnapshot
    active_index_id: str | None
    is_active_generation: bool
    is_latest_succeeded_generation: bool
    rollback_eligible: bool
    search_coverage: SearchCoverageSummary | None
    search_activation_evaluation: SearchActivationGateEvaluation | None


@dataclass(frozen=True)
class ProjectSearchQueryAuditResult:
    project_id: str
    items: list[SearchQueryAuditRecord]
    next_cursor: int | None


@dataclass(frozen=True)
class EntityExtractionSource:
    document_id: str
    run_id: str
    page_id: str
    line_id: str | None
    token_id: str | None
    source_kind: str
    source_ref_id: str
    page_number: int
    source_text: str
    confidence: float
    token_geometry_json: dict[str, object] | None = None


@dataclass(frozen=True)
class EntityOccurrenceLink:
    id: str
    entity_index_id: str
    entity_id: str
    document_id: str
    run_id: str
    page_id: str
    page_number: int
    line_id: str | None
    token_id: str | None
    source_kind: str
    source_ref_id: str
    confidence: float
    occurrence_span_json: dict[str, object] | None
    occurrence_span_basis_kind: OccurrenceSpanBasisKind
    occurrence_span_basis_ref: str | None
    token_geometry_json: dict[str, object] | None


@dataclass(frozen=True)
class ProjectEntityListResult:
    entity_index_id: str
    items: list[ControlledEntityRecord]
    next_cursor: int | None


@dataclass(frozen=True)
class ProjectEntityDetailResult:
    entity_index_id: str
    entity: ControlledEntityRecord


@dataclass(frozen=True)
class ProjectEntityOccurrencesResult:
    entity_index_id: str
    entity: ControlledEntityRecord
    items: list[EntityOccurrenceLink]
    next_cursor: int | None


@dataclass(frozen=True)
class DerivativeMaterializedRow:
    derivative_kind: str
    source_snapshot_json: dict[str, object]
    display_payload_json: dict[str, object]


@dataclass(frozen=True)
class DerivativeMaterializationResult:
    snapshot: DerivativeSnapshotRecord
    rows_written: int
    blocked: bool
    blocked_reason: str | None


@dataclass(frozen=True)
class ProjectDerivativeListResult:
    scope: DerivativeScope
    active_derivative_index_id: str | None
    items: list[DerivativeSnapshotListItem]


@dataclass(frozen=True)
class ProjectDerivativeDetailResult:
    snapshot: DerivativeSnapshotRecord


@dataclass(frozen=True)
class ProjectDerivativePreviewResult:
    snapshot: DerivativeSnapshotRecord
    rows: list[DerivativeIndexRowRecord]


@dataclass(frozen=True)
class DerivativeCandidateFreezeResult:
    snapshot: DerivativeSnapshotRecord
    candidate: ExportCandidateSnapshotRecord
    created: bool


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _normalize_json_object(field_name: str, value: object | None) -> dict[str, object]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise IndexValidationError(f"{field_name} must be a JSON object.")
    return dict(value)


def _index_object_type(kind: IndexKind) -> str:
    if kind == "SEARCH":
        return "search_index"
    if kind == "ENTITY":
        return "entity_index"
    return "derivative_index"


def _run_created_event(kind: IndexKind) -> str:
    if kind == "SEARCH":
        return "SEARCH_INDEX_RUN_CREATED"
    if kind == "ENTITY":
        return "ENTITY_INDEX_RUN_CREATED"
    return "DERIVATIVE_INDEX_RUN_CREATED"


def _run_started_event(kind: IndexKind) -> str:
    if kind == "SEARCH":
        return "SEARCH_INDEX_RUN_STARTED"
    if kind == "ENTITY":
        return "ENTITY_INDEX_RUN_STARTED"
    return "DERIVATIVE_INDEX_RUN_STARTED"


def _run_finished_event(kind: IndexKind) -> str:
    if kind == "SEARCH":
        return "SEARCH_INDEX_RUN_FINISHED"
    if kind == "ENTITY":
        return "ENTITY_INDEX_RUN_FINISHED"
    return "DERIVATIVE_INDEX_RUN_FINISHED"


def _run_failed_event(kind: IndexKind) -> str:
    if kind == "SEARCH":
        return "SEARCH_INDEX_RUN_FAILED"
    if kind == "ENTITY":
        return "ENTITY_INDEX_RUN_FAILED"
    return "DERIVATIVE_INDEX_RUN_FAILED"


def _run_canceled_event(kind: IndexKind) -> str:
    if kind == "SEARCH":
        return "SEARCH_INDEX_RUN_CANCELED"
    if kind == "ENTITY":
        return "ENTITY_INDEX_RUN_CANCELED"
    return "DERIVATIVE_INDEX_RUN_CANCELED"


class IndexService:
    def __init__(
        self,
        *,
        settings: Settings,
        store: IndexStore | None = None,
        project_store: ProjectStore | None = None,
        audit_service: AuditService | None = None,
        export_store: ExportStore | None = None,
    ) -> None:
        self._settings = settings
        self._store = store or IndexStore(settings)
        self._project_store = project_store or ProjectStore(settings)
        self._audit_service = audit_service or get_audit_service()
        self._export_store = export_store or ExportStore(settings)

    @staticmethod
    def _is_admin(current_user: SessionPrincipal) -> bool:
        return "ADMIN" in set(current_user.platform_roles)

    def _resolve_project_access(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> _ProjectIndexAccessContext:
        is_admin = self._is_admin(current_user)
        try:
            member_summary = self._project_store.get_project_summary_for_user(
                project_id=project_id,
                user_id=current_user.user_id,
            )
            if member_summary is not None:
                return _ProjectIndexAccessContext(
                    summary=member_summary,
                    project_role=member_summary.current_user_role,
                    is_admin=is_admin,
                )

            if is_admin:
                summary = self._project_store.get_project_summary(project_id=project_id)
                if summary is None:
                    raise IndexNotFoundError("Project not found.")
                return _ProjectIndexAccessContext(
                    summary=summary,
                    project_role=None,
                    is_admin=True,
                )
        except ProjectStoreUnavailableError as error:
            raise IndexStoreUnavailableError("Project access lookup failed.") from error

        raise IndexAccessDeniedError(
            "Project membership is required for index management routes."
        )

    @staticmethod
    def _require_read_access(context: _ProjectIndexAccessContext) -> None:
        if context.is_admin:
            return
        if context.project_role in _READ_ROLES:
            return
        raise IndexAccessDeniedError(
            "Current role cannot view project-scoped index metadata routes."
        )

    @staticmethod
    def _require_mutation_access(context: _ProjectIndexAccessContext) -> None:
        if context.is_admin:
            return
        raise IndexAccessDeniedError(
            "Index rebuild, cancel, and activate operations require ADMIN."
        )

    @staticmethod
    def _require_derivative_candidate_freeze_access(
        context: _ProjectIndexAccessContext,
    ) -> None:
        if context.is_admin:
            return
        if context.project_role in _DERIVATIVE_FREEZE_ROLES:
            return
        raise IndexAccessDeniedError(
            "Derivative candidate freeze requires PROJECT_LEAD, REVIEWER, or ADMIN."
        )

    @staticmethod
    def _require_index_quality_read_access(current_user: SessionPrincipal) -> None:
        current_roles = set(current_user.platform_roles)
        if any(role in _INDEX_QUALITY_READ_ROLES for role in current_roles):
            return
        raise IndexAccessDeniedError(
            "Index quality reads require ADMIN or AUDITOR platform role."
        )

    @staticmethod
    def compute_source_snapshot_sha256(source_snapshot_json: dict[str, object]) -> str:
        return hashlib.sha256(_canonical_json(source_snapshot_json).encode("utf-8")).hexdigest()

    @staticmethod
    def compute_rebuild_dedupe_key(
        *,
        project_id: str,
        kind: IndexKind,
        source_snapshot_sha256: str,
        build_parameters_json: dict[str, object],
    ) -> str:
        dedupe_payload = {
            "project_id": project_id,
            "index_kind": kind,
            "source_snapshot_sha256": source_snapshot_sha256,
            "build_parameters": build_parameters_json,
        }
        return hashlib.sha256(_canonical_json(dedupe_payload).encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_query_for_hash(query_text: str) -> str:
        return " ".join(query_text.strip().split()).lower()

    @classmethod
    def _query_sha256(cls, query_text: str) -> str:
        normalized = cls._normalize_query_for_hash(query_text)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _search_filters_json(
        *,
        document_id: str | None,
        run_id: str | None,
        page_number: int | None,
    ) -> dict[str, object]:
        filters: dict[str, object] = {}
        if isinstance(document_id, str) and document_id.strip():
            filters["documentId"] = document_id.strip()
        if isinstance(run_id, str) and run_id.strip():
            filters["runId"] = run_id.strip()
        if isinstance(page_number, int):
            filters["pageNumber"] = page_number
        return filters

    @staticmethod
    def canonicalize_entity_value(entity_type: EntityType, display_value: str) -> str:
        normalized = " ".join(display_value.strip().split())
        if not normalized:
            return ""

        if entity_type == "DATE":
            iso_match = re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized)
            if iso_match:
                return normalized
            dm_match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})", normalized)
            if dm_match:
                day = int(dm_match.group(1))
                month_name = dm_match.group(2).lower()
                year = int(dm_match.group(3))
                month_map = {
                    "jan": 1,
                    "january": 1,
                    "feb": 2,
                    "february": 2,
                    "mar": 3,
                    "march": 3,
                    "apr": 4,
                    "april": 4,
                    "may": 5,
                    "jun": 6,
                    "june": 6,
                    "jul": 7,
                    "july": 7,
                    "aug": 8,
                    "august": 8,
                    "sep": 9,
                    "sept": 9,
                    "september": 9,
                    "oct": 10,
                    "october": 10,
                    "nov": 11,
                    "november": 11,
                    "dec": 12,
                    "december": 12,
                }
                month = month_map.get(month_name)
                if month and 1 <= day <= 31:
                    return f"{year:04d}-{month:02d}-{day:02d}"
            return normalized.lower()

        lowered = normalized.lower()
        lowered = re.sub(r"[^\w\s-]", "", lowered)
        return " ".join(lowered.split())

    def list_indexes(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        kind: IndexKind,
    ) -> list[IndexRecord]:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_read_access(context)
        return self._store.list_indexes(project_id=project_id, kind=kind)

    def get_index(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        kind: IndexKind,
        index_id: str,
    ) -> IndexRecord:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_read_access(context)
        row = self._store.get_index(project_id=project_id, kind=kind, index_id=index_id)
        if row is None:
            raise IndexNotFoundError("Index generation not found.")
        return row

    def get_active_indexes(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> ActiveProjectIndexesView:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_read_access(context)
        projection = self._store.get_projection(project_id=project_id)
        search_index = (
            self._store.get_index(
                project_id=project_id,
                kind="SEARCH",
                index_id=projection.active_search_index_id,
            )
            if projection and projection.active_search_index_id
            else None
        )
        entity_index = (
            self._store.get_index(
                project_id=project_id,
                kind="ENTITY",
                index_id=projection.active_entity_index_id,
            )
            if projection and projection.active_entity_index_id
            else None
        )
        derivative_index = (
            self._store.get_index(
                project_id=project_id,
                kind="DERIVATIVE",
                index_id=projection.active_derivative_index_id,
            )
            if projection and projection.active_derivative_index_id
            else None
        )
        return ActiveProjectIndexesView(
            projection=projection,
            search_index=search_index,
            entity_index=entity_index,
            derivative_index=derivative_index,
        )

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
        route: str | None = None,
    ) -> ProjectSearchResult:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_read_access(context)
        normalized_query = query_text.strip()
        if len(normalized_query) == 0:
            raise IndexValidationError("q must be a non-empty search query.")
        if len(normalized_query) > 600:
            raise IndexValidationError("q must be 600 characters or fewer.")
        if cursor < 0:
            raise IndexValidationError("cursor must be greater than or equal to 0.")
        if limit < 1 or limit > 100:
            raise IndexValidationError("limit must be between 1 and 100.")
        if page_number is not None and page_number < 1:
            raise IndexValidationError("pageNumber must be greater than or equal to 1.")

        projection = self._store.get_projection(project_id=project_id)
        if projection is None or projection.active_search_index_id is None:
            raise IndexConflictError("No active search index is available for this project.")

        page = self._store.list_search_documents_for_index(
            search_index_id=projection.active_search_index_id,
            query_text=normalized_query,
            document_id=document_id,
            run_id=run_id,
            page_number=page_number,
            cursor=cursor,
            limit=limit,
        )
        query_sha256 = self._query_sha256(normalized_query)
        query_text_key = self._store.store_search_query_text(
            project_id=project_id,
            query_text=normalized_query,
        )
        filters_json = self._search_filters_json(
            document_id=document_id,
            run_id=run_id,
            page_number=page_number,
        )
        self._store.append_search_query_audit(
            project_id=project_id,
            actor_user_id=current_user.user_id,
            search_index_id=projection.active_search_index_id,
            query_sha256=query_sha256,
            query_text_key=query_text_key,
            filters_json=filters_json,
            result_count=len(page.items),
        )
        self._audit_service.record_event_best_effort(
            event_type="SEARCH_QUERY_EXECUTED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="search_index",
            object_id=projection.active_search_index_id,
            metadata={
                "route": route or "/projects/{project_id}/search",
                "search_index_id": projection.active_search_index_id,
                "query_sha256": query_sha256,
                "query_text_key": query_text_key,
                "filters_json": filters_json,
                "result_count": len(page.items),
            },
            request_id=current_trace_id() or f"search-query:{projection.active_search_index_id}",
        )
        return ProjectSearchResult(
            search_index_id=projection.active_search_index_id,
            items=page.items,
            next_cursor=page.next_cursor,
        )

    def open_search_result(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        search_document_id: str,
        route: str,
    ) -> SearchDocumentRecord:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_read_access(context)

        projection = self._store.get_projection(project_id=project_id)
        if projection is None or projection.active_search_index_id is None:
            raise IndexConflictError("No active search index is available for this project.")

        row = self._store.get_search_document_for_index(
            search_index_id=projection.active_search_index_id,
            search_document_id=search_document_id,
        )
        if row is None:
            raise IndexNotFoundError("Search result was not found in the active search index.")

        self._audit_service.record_event_best_effort(
            event_type="SEARCH_RESULT_OPENED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            object_type="search_document",
            object_id=row.id,
            metadata={
                "route": route,
                "search_index_id": projection.active_search_index_id,
                "document_id": row.document_id,
                "run_id": row.run_id,
                "page_number": row.page_number,
                "line_id": row.line_id or "",
                "token_id": row.token_id or "",
                "source_kind": row.source_kind,
                "source_ref_id": row.source_ref_id,
            },
            request_id=current_trace_id() or f"search-open:{row.id}",
        )
        return row

    @staticmethod
    def _resolve_occurrence_span_basis(
        *,
        source_kind: str,
        line_id: str | None,
        source_ref_id: str,
    ) -> tuple[OccurrenceSpanBasisKind, str | None]:
        if source_kind == "PAGE_WINDOW":
            return "PAGE_WINDOW_TEXT", source_ref_id
        if isinstance(line_id, str) and line_id.strip():
            return "LINE_TEXT", line_id.strip()
        return "NONE", None

    @staticmethod
    def _extract_matches(text: str) -> list[tuple[EntityType, str, tuple[int, int]]]:
        matches: list[tuple[EntityType, str, tuple[int, int]]] = []

        for match in _DATE_PATTERN.finditer(text):
            value = match.group(0).strip()
            if value:
                matches.append(("DATE", value, (match.start(), match.end())))

        for match in _ORGANISATION_PATTERN.finditer(text):
            value = match.group(1).strip()
            if value:
                matches.append(("ORGANISATION", value, (match.start(1), match.end(1))))

        for match in _PLACE_PATTERN.finditer(text):
            value = match.group(1).strip()
            if value:
                matches.append(("PLACE", value, (match.start(1), match.end(1))))

        for match in _PERSON_PATTERN.finditer(text):
            value = match.group(1).strip()
            if value:
                matches.append(("PERSON", value, (match.start(1), match.end(1))))

        return matches

    def materialize_controlled_entities(
        self,
        *,
        actor_user_id: str,
        project_id: str,
        entity_index_id: str,
        sources: list[EntityExtractionSource],
    ) -> dict[str, int]:
        row = self._store.get_index(
            project_id=project_id,
            kind="ENTITY",
            index_id=entity_index_id,
        )
        if row is None:
            raise IndexNotFoundError("Entity index generation not found.")

        grouped: dict[tuple[EntityType, str], dict[str, object]] = {}
        occurrences_by_key: dict[tuple[EntityType, str], list[CreateEntityOccurrenceInput]] = {}

        for source in sources:
            source_text = " ".join(source.source_text.split())
            if len(source_text) == 0:
                continue
            source_kind = source.source_kind.strip().upper()
            if source_kind not in {"LINE", "RESCUE_CANDIDATE", "PAGE_WINDOW"}:
                source_kind = "LINE"

            for entity_type, display_value, span in self._extract_matches(source_text):
                canonical_value = self.canonicalize_entity_value(entity_type, display_value)
                if not canonical_value:
                    continue

                key = (entity_type, canonical_value)
                aggregate = grouped.get(key)
                if aggregate is None:
                    aggregate = {
                        "display_value": display_value,
                        "confidences": [],
                        "occurrence_count": 0,
                    }
                    grouped[key] = aggregate

                confidences = aggregate["confidences"]
                if isinstance(confidences, list):
                    confidences.append(source.confidence)
                aggregate["occurrence_count"] = int(aggregate["occurrence_count"]) + 1
                if len(display_value) > len(str(aggregate["display_value"])):
                    aggregate["display_value"] = display_value

                entity_id = hashlib.sha256(
                    _canonical_json(
                        {
                            "entity_index_id": entity_index_id,
                            "entity_type": entity_type,
                            "canonical_value": canonical_value,
                        }
                    ).encode("utf-8")
                ).hexdigest()[:24]
                entity_id = f"entity-{entity_id}"

                span_basis_kind, span_basis_ref = self._resolve_occurrence_span_basis(
                    source_kind=source_kind,
                    line_id=source.line_id,
                    source_ref_id=source.source_ref_id,
                )
                occurrence_span_json: dict[str, object] | None
                if span_basis_kind == "NONE":
                    occurrence_span_json = None
                else:
                    occurrence_span_json = {"start": int(span[0]), "end": int(span[1])}

                occurrence_fingerprint = hashlib.sha256(
                    _canonical_json(
                        {
                            "entity_index_id": entity_index_id,
                            "entity_id": entity_id,
                            "document_id": source.document_id,
                            "run_id": source.run_id,
                            "page_id": source.page_id,
                            "line_id": source.line_id,
                            "token_id": source.token_id,
                            "source_kind": source_kind,
                            "source_ref_id": source.source_ref_id,
                            "page_number": source.page_number,
                            "span": occurrence_span_json,
                        }
                    ).encode("utf-8")
                ).hexdigest()[:24]

                occurrences_by_key.setdefault(key, []).append(
                    CreateEntityOccurrenceInput(
                        id=f"entocc-{occurrence_fingerprint}",
                        entity_id=entity_id,
                        document_id=source.document_id,
                        run_id=source.run_id,
                        page_id=source.page_id,
                        line_id=source.line_id,
                        token_id=source.token_id,
                        source_kind=source_kind,  # type: ignore[arg-type]
                        source_ref_id=source.source_ref_id,
                        page_number=source.page_number,
                        confidence=source.confidence,
                        occurrence_span_json=occurrence_span_json,
                        occurrence_span_basis_kind=span_basis_kind,
                        occurrence_span_basis_ref=span_basis_ref,
                        token_geometry_json=source.token_geometry_json,
                    )
                )

        entity_rows: list[CreateControlledEntityInput] = []
        occurrence_rows: list[CreateEntityOccurrenceInput] = []
        for key in sorted(grouped.keys(), key=lambda item: (item[0], item[1])):
            entity_type, canonical_value = key
            aggregate = grouped[key]
            confidences = aggregate.get("confidences")
            confidence_values = [
                float(value)
                for value in confidences
                if isinstance(confidences, list) and isinstance(value, (int, float))
            ]
            occurrence_count = int(aggregate.get("occurrence_count", 0))
            avg_confidence = (
                sum(confidence_values) / len(confidence_values)
                if confidence_values
                else 0.0
            )
            confidence_band = (
                "HIGH"
                if avg_confidence >= 0.85
                else "MEDIUM"
                if avg_confidence >= 0.6
                else "LOW"
            )
            entity_id = hashlib.sha256(
                _canonical_json(
                    {
                        "entity_index_id": entity_index_id,
                        "entity_type": entity_type,
                        "canonical_value": canonical_value,
                    }
                ).encode("utf-8")
            ).hexdigest()[:24]
            entity_id = f"entity-{entity_id}"
            entity_rows.append(
                CreateControlledEntityInput(
                    id=entity_id,
                    entity_type=entity_type,
                    display_value=str(aggregate.get("display_value", canonical_value)),
                    canonical_value=canonical_value,
                    confidence_summary_json={
                        "band": confidence_band,
                        "min": min(confidence_values) if confidence_values else 0.0,
                        "max": max(confidence_values) if confidence_values else 0.0,
                        "average": round(avg_confidence, 4),
                        "occurrenceCount": occurrence_count,
                        "method": "heuristic-v1",
                    },
                )
            )
            occurrence_rows.extend(occurrences_by_key.get(key, []))

        self._store.clear_entity_index_rows(
            project_id=project_id,
            entity_index_id=entity_index_id,
        )
        entities_written = self._store.append_controlled_entities(
            project_id=project_id,
            entity_index_id=entity_index_id,
            items=entity_rows,
        )
        occurrences_written = self._store.append_entity_occurrences(
            project_id=project_id,
            entity_index_id=entity_index_id,
            items=occurrence_rows,
        )
        self._audit_service.record_event_best_effort(
            event_type="ENTITY_INDEX_RUN_FINISHED",
            actor_user_id=actor_user_id,
            project_id=project_id,
            object_type="entity_index",
            object_id=entity_index_id,
            metadata={
                "route": "worker:entity-materialize",
                "index_id": entity_index_id,
                "index_kind": "ENTITY",
                "status": row.status,
                "version": row.version,
            },
            request_id=current_trace_id() or f"entity-materialize:{entity_index_id}",
        )
        return {
            "entities": entities_written,
            "occurrences": occurrences_written,
            "sources": len(sources),
        }

    def _active_entity_index_id_or_raise(self, *, project_id: str) -> str:
        projection = self._store.get_projection(project_id=project_id)
        if projection is None or projection.active_entity_index_id is None:
            raise IndexConflictError("No active entity index is available for this project.")
        return projection.active_entity_index_id

    @staticmethod
    def _normalize_entity_type(entity_type: str | None) -> EntityType | None:
        if entity_type is None:
            return None
        normalized = entity_type.strip().upper()
        if not normalized:
            return None
        if normalized not in _ALLOWED_ENTITY_TYPES:
            raise IndexValidationError(
                "entityType must be one of PERSON, PLACE, ORGANISATION, DATE."
            )
        return normalized  # type: ignore[return-value]

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
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_read_access(context)
        normalized_query = query_text.strip() if isinstance(query_text, str) else ""
        if len(normalized_query) > 600:
            raise IndexValidationError("q must be 600 characters or fewer.")
        if cursor < 0:
            raise IndexValidationError("cursor must be greater than or equal to 0.")
        if limit < 1 or limit > 100:
            raise IndexValidationError("limit must be between 1 and 100.")

        normalized_type = self._normalize_entity_type(entity_type)
        entity_index_id = self._active_entity_index_id_or_raise(project_id=project_id)
        page = self._store.list_controlled_entities_for_index(
            entity_index_id=entity_index_id,
            query_text=normalized_query,
            entity_type=normalized_type,
            cursor=cursor,
            limit=limit,
        )
        return ProjectEntityListResult(
            entity_index_id=entity_index_id,
            items=page.items,
            next_cursor=page.next_cursor,
        )

    def get_project_entity_detail(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        entity_id: str,
    ) -> ProjectEntityDetailResult:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_read_access(context)
        entity_index_id = self._active_entity_index_id_or_raise(project_id=project_id)
        row = self._store.get_controlled_entity_for_index(
            entity_index_id=entity_index_id,
            entity_id=entity_id,
        )
        if row is None:
            raise IndexNotFoundError("Entity was not found in the active entity index.")
        return ProjectEntityDetailResult(entity_index_id=entity_index_id, entity=row)

    def list_project_entity_occurrences(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        entity_id: str,
        cursor: int,
        limit: int,
    ) -> ProjectEntityOccurrencesResult:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_read_access(context)
        if cursor < 0:
            raise IndexValidationError("cursor must be greater than or equal to 0.")
        if limit < 1 or limit > 100:
            raise IndexValidationError("limit must be between 1 and 100.")

        entity_index_id = self._active_entity_index_id_or_raise(project_id=project_id)
        entity = self._store.get_controlled_entity_for_index(
            entity_index_id=entity_index_id,
            entity_id=entity_id,
        )
        if entity is None:
            raise IndexNotFoundError("Entity was not found in the active entity index.")

        page = self._store.list_entity_occurrences_for_index(
            entity_index_id=entity_index_id,
            entity_id=entity_id,
            cursor=cursor,
            limit=limit,
        )
        items = [
            EntityOccurrenceLink(
                id=row.id,
                entity_index_id=row.entity_index_id,
                entity_id=row.entity_id,
                document_id=row.document_id,
                run_id=row.run_id,
                page_id=row.page_id,
                page_number=row.page_number,
                line_id=row.line_id,
                token_id=row.token_id,
                source_kind=row.source_kind,
                source_ref_id=row.source_ref_id,
                confidence=row.confidence,
                occurrence_span_json=row.occurrence_span_json,
                occurrence_span_basis_kind=row.occurrence_span_basis_kind,
                occurrence_span_basis_ref=row.occurrence_span_basis_ref,
                token_geometry_json=row.token_geometry_json,
            )
            for row in page.items
        ]
        return ProjectEntityOccurrencesResult(
            entity_index_id=entity_index_id,
            entity=entity,
            items=items,
            next_cursor=page.next_cursor,
        )

    def _validate_entity_index_activation(self, *, row: IndexRecord) -> None:
        entities = self._store.list_all_controlled_entities_for_index(entity_index_id=row.id)
        occurrences = self._store.list_all_entity_occurrences_for_index(entity_index_id=row.id)

        canonicalization_issues = self._find_entity_canonicalization_issues(entities)
        if canonicalization_issues:
            raise IndexConflictError(
                "Entity index activation blocked: canonicalization validation failed."
            )

        provenance_issues = self._find_entity_occurrence_provenance_issues(occurrences)
        if provenance_issues:
            raise IndexConflictError(
                "Entity index activation blocked: occurrence-provenance completeness failed."
            )

        coverage_passed = self._passes_entity_coverage_gate(
            source_snapshot=row.source_snapshot_json,
            entity_count=len(entities),
            occurrence_count=len(occurrences),
        )
        if not coverage_passed:
            raise IndexConflictError(
                "Entity index activation blocked: eligible-input coverage gates failed."
            )

    def _validate_derivative_index_activation(self, *, row: IndexRecord) -> None:
        snapshots = self._store.list_derivative_snapshots_for_index(
            project_id=row.project_id,
            derivative_index_id=row.id,
        )
        all_rows = self._store.list_all_derivative_rows_for_index(derivative_index_id=row.id)
        successful_snapshot_count = 0
        for snapshot in snapshots:
            if snapshot.status != "SUCCEEDED":
                raise IndexConflictError(
                    "Derivative index activation blocked: snapshot completeness gates failed."
                )
            if not snapshot.storage_key or not snapshot.storage_key.strip():
                raise IndexConflictError(
                    "Derivative index activation blocked: snapshot completeness gates failed."
                )
            if not snapshot.snapshot_sha256 or not snapshot.snapshot_sha256.strip():
                raise IndexConflictError(
                    "Derivative index activation blocked: snapshot completeness gates failed."
                )
            rows = self._store.list_all_derivative_rows_for_snapshot(
                derivative_index_id=row.id,
                derivative_snapshot_id=snapshot.id,
            )
            if len(rows) == 0:
                raise IndexConflictError(
                    "Derivative index activation blocked: snapshot completeness gates failed."
                )
            successful_snapshot_count += 1

            identifier_issues = self._find_derivative_identifier_leaks(rows=rows)
            if identifier_issues:
                raise IndexConflictError(
                    "Derivative index activation blocked: suppression-policy checks failed."
                )
            anti_join_issues = self._find_derivative_antijoin_issues(
                payloads=[row.display_payload_json for row in rows],
                source_snapshot=snapshot.source_snapshot_json,
            )
            if anti_join_issues:
                raise IndexConflictError(
                    "Derivative index activation blocked: anti-join disclosure checks failed."
                )

        coverage_passed = self._passes_derivative_snapshot_completeness_gate(
            source_snapshot=row.source_snapshot_json,
            successful_snapshot_count=successful_snapshot_count,
            row_count=len(all_rows),
        )
        if not coverage_passed:
            raise IndexConflictError(
                "Derivative index activation blocked: snapshot completeness gates failed."
            )

    def _find_entity_canonicalization_issues(
        self,
        entities: list[ControlledEntityRecord],
    ) -> list[str]:
        issues: list[str] = []
        for row in entities:
            if row.entity_type not in _ALLOWED_ENTITY_TYPES:
                issues.append(row.id)
                continue
            if not row.display_value.strip():
                issues.append(row.id)
                continue
            expected = self.canonicalize_entity_value(row.entity_type, row.display_value)
            if not expected or expected != row.canonical_value:
                issues.append(row.id)
        return issues

    def _find_entity_occurrence_provenance_issues(
        self,
        occurrences: list[EntityOccurrenceRecord],
    ) -> list[str]:
        issues: list[str] = []
        for row in occurrences:
            if row.source_kind not in {"LINE", "RESCUE_CANDIDATE", "PAGE_WINDOW"}:
                issues.append(row.id)
                continue
            if row.page_number < 1:
                issues.append(row.id)
                continue
            required_fields = [
                row.entity_id,
                row.document_id,
                row.run_id,
                row.page_id,
                row.source_ref_id,
            ]
            if any(not value.strip() for value in required_fields):
                issues.append(row.id)
                continue
            if row.source_kind == "LINE" and not (row.line_id and row.line_id.strip()):
                issues.append(row.id)
                continue

            if row.occurrence_span_basis_kind not in _ALLOWED_OCCURRENCE_SPAN_BASIS_KINDS:
                issues.append(row.id)
                continue
            if row.occurrence_span_basis_kind == "LINE_TEXT":
                if not row.line_id or row.occurrence_span_basis_ref != row.line_id:
                    issues.append(row.id)
                    continue
            if row.occurrence_span_basis_kind == "PAGE_WINDOW_TEXT":
                if row.source_kind != "PAGE_WINDOW":
                    issues.append(row.id)
                    continue
                if row.occurrence_span_basis_ref != row.source_ref_id:
                    issues.append(row.id)
                    continue
            if row.occurrence_span_basis_kind == "NONE":
                if row.occurrence_span_json is not None:
                    issues.append(row.id)
                    continue

            if row.occurrence_span_json is not None:
                if row.occurrence_span_basis_kind == "NONE":
                    issues.append(row.id)
                    continue
                if not row.occurrence_span_basis_ref:
                    issues.append(row.id)
                    continue
                span_start = row.occurrence_span_json.get("start")
                span_end = row.occurrence_span_json.get("end")
                if not isinstance(span_start, int) or not isinstance(span_end, int):
                    issues.append(row.id)
                    continue
                if span_end <= span_start or span_start < 0:
                    issues.append(row.id)
                    continue

        return issues

    @staticmethod
    def _read_snapshot_int(
        snapshot: dict[str, object],
        keys: list[str],
    ) -> int | None:
        for key in keys:
            value = snapshot.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                return value
            if isinstance(value, float) and value.is_integer():
                return int(value)
            if isinstance(value, str):
                trimmed = value.strip()
                if trimmed and trimmed.lstrip("-").isdigit():
                    return int(trimmed)
        return None

    @staticmethod
    def _read_snapshot_bool(
        snapshot: dict[str, object],
        keys: tuple[str, ...] | list[str],
    ) -> bool | None:
        for key in keys:
            value = snapshot.get(key)
            if isinstance(value, bool):
                return value
            if isinstance(value, int):
                if value in {0, 1}:
                    return bool(value)
                continue
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"true", "1", "yes"}:
                    return True
                if normalized in {"false", "0", "no"}:
                    return False
        return None

    @staticmethod
    def _read_snapshot_text(
        snapshot: dict[str, object],
        keys: tuple[str, ...] | list[str],
    ) -> str | None:
        for key in keys:
            value = snapshot.get(key)
            if isinstance(value, str):
                normalized = " ".join(value.strip().split())
                if normalized:
                    return normalized
        return None

    def _build_search_coverage_summary(
        self,
        *,
        source_snapshot: dict[str, object],
    ) -> SearchCoverageSummary:
        eligible_input_count = self._read_snapshot_int(
            source_snapshot,
            list(_SEARCH_ELIGIBLE_INPUT_KEYS),
        )
        token_anchor_valid_input_count = self._read_snapshot_int(
            source_snapshot,
            list(_SEARCH_TOKEN_ANCHOR_VALID_KEYS),
        )
        token_anchor_invalid_input_count = self._read_snapshot_int(
            source_snapshot,
            list(_SEARCH_TOKEN_ANCHOR_INVALID_KEYS),
        )
        token_geometry_covered_input_count = self._read_snapshot_int(
            source_snapshot,
            list(_SEARCH_GEOMETRY_COVERED_KEYS),
        )
        token_geometry_missing_input_count = self._read_snapshot_int(
            source_snapshot,
            list(_SEARCH_GEOMETRY_MISSING_KEYS),
        )
        historical_line_only_excluded_count = (
            self._read_snapshot_int(
                source_snapshot,
                list(_SEARCH_LINE_ONLY_EXCLUDED_KEYS),
            )
            or 0
        )
        historical_line_only_fallback_allowed = bool(
            self._read_snapshot_bool(
                source_snapshot,
                _SEARCH_LINE_ONLY_FALLBACK_ALLOWED_KEYS,
            )
        )
        historical_line_only_fallback_reason = self._read_snapshot_text(
            source_snapshot,
            _SEARCH_LINE_ONLY_FALLBACK_REASON_KEYS,
        )

        if (
            eligible_input_count is None
            and token_anchor_valid_input_count is not None
            and token_anchor_invalid_input_count is not None
        ):
            eligible_input_count = (
                token_anchor_valid_input_count + max(token_anchor_invalid_input_count, 0)
            )
        if (
            eligible_input_count is None
            and token_geometry_covered_input_count is not None
            and token_geometry_missing_input_count is not None
        ):
            eligible_input_count = (
                token_geometry_covered_input_count
                + max(token_geometry_missing_input_count, 0)
            )
        if eligible_input_count is None and historical_line_only_excluded_count > 0:
            eligible_input_count = historical_line_only_excluded_count

        return SearchCoverageSummary(
            eligible_input_count=eligible_input_count,
            token_anchor_valid_input_count=token_anchor_valid_input_count,
            token_geometry_covered_input_count=token_geometry_covered_input_count,
            historical_line_only_excluded_count=historical_line_only_excluded_count,
            historical_line_only_fallback_allowed=historical_line_only_fallback_allowed,
            historical_line_only_fallback_reason=historical_line_only_fallback_reason,
        )

    def evaluate_search_activation_gate(
        self,
        *,
        row: IndexRecord,
    ) -> SearchActivationGateEvaluation:
        blockers: list[SearchActivationGateBlocker] = []

        if row.status != "SUCCEEDED":
            blockers.append(
                SearchActivationGateBlocker(
                    code="RUN_NOT_SUCCEEDED",
                    message="Only SUCCEEDED search index generations can be activated.",
                    metadata={"status": row.status},
                )
            )

        coverage = self._build_search_coverage_summary(
            source_snapshot=row.source_snapshot_json
        )
        eligible = coverage.eligible_input_count
        excluded = max(0, coverage.historical_line_only_excluded_count)
        if eligible is None:
            blockers.append(
                SearchActivationGateBlocker(
                    code="SEARCH_ELIGIBLE_INPUTS_MISSING",
                    message=(
                        "Activation requires explicit eligible-input counters for search "
                        "token-anchor and geometry gates."
                    ),
                    metadata={"source_snapshot_keys": sorted(row.source_snapshot_json.keys())},
                )
            )
            return SearchActivationGateEvaluation(passed=False, blockers=blockers)

        if eligible < 0 or excluded > eligible:
            blockers.append(
                SearchActivationGateBlocker(
                    code="SEARCH_LINE_ONLY_EXCLUDED_INVALID",
                    message=(
                        "Historical line-only exclusion counters must be non-negative and "
                        "cannot exceed eligible inputs."
                    ),
                    metadata={
                        "eligible_input_count": eligible,
                        "historical_line_only_excluded_count": excluded,
                    },
                )
            )
            return SearchActivationGateEvaluation(passed=False, blockers=blockers)

        requires_token_coverage = max(0, eligible - excluded)
        if excluded > 0:
            if not coverage.historical_line_only_fallback_allowed:
                blockers.append(
                    SearchActivationGateBlocker(
                        code="SEARCH_LINE_ONLY_FALLBACK_MARKER_MISSING",
                        message=(
                            "Historical line-only exclusions require explicit fallback "
                            "markers in the source snapshot."
                        ),
                        metadata={"historical_line_only_excluded_count": excluded},
                    )
                )
            if coverage.historical_line_only_fallback_reason is None:
                blockers.append(
                    SearchActivationGateBlocker(
                        code="SEARCH_LINE_ONLY_FALLBACK_REASON_MISSING",
                        message=(
                            "Historical line-only exclusions require an explicit fallback "
                            "reason marker."
                        ),
                        metadata={"historical_line_only_excluded_count": excluded},
                    )
                )

        if requires_token_coverage > 0:
            token_anchor_valid = coverage.token_anchor_valid_input_count
            token_geometry_covered = coverage.token_geometry_covered_input_count
            if token_anchor_valid is None:
                blockers.append(
                    SearchActivationGateBlocker(
                        code="TOKEN_ANCHOR_VALIDITY_MISSING",
                        message=(
                            "Activation requires token-anchor validity counters for all "
                            "eligible transcript inputs."
                        ),
                        metadata={"required_covered_input_count": requires_token_coverage},
                    )
                )
            elif token_anchor_valid < requires_token_coverage:
                blockers.append(
                    SearchActivationGateBlocker(
                        code="TOKEN_ANCHOR_VALIDITY_FAILED",
                        message=(
                            "Token-anchor validity coverage is below the required eligible "
                            "input floor."
                        ),
                        metadata={
                            "required_covered_input_count": requires_token_coverage,
                            "token_anchor_valid_input_count": token_anchor_valid,
                        },
                    )
                )
            if token_geometry_covered is None:
                blockers.append(
                    SearchActivationGateBlocker(
                        code="TOKEN_GEOMETRY_COVERAGE_MISSING",
                        message=(
                            "Activation requires token-geometry coverage counters for all "
                            "eligible transcript inputs."
                        ),
                        metadata={"required_covered_input_count": requires_token_coverage},
                    )
                )
            elif token_geometry_covered < requires_token_coverage:
                blockers.append(
                    SearchActivationGateBlocker(
                        code="TOKEN_GEOMETRY_COVERAGE_FAILED",
                        message=(
                            "Token-geometry coverage is below the required eligible-input floor."
                        ),
                        metadata={
                            "required_covered_input_count": requires_token_coverage,
                            "token_geometry_covered_input_count": token_geometry_covered,
                        },
                    )
                )

        return SearchActivationGateEvaluation(
            passed=len(blockers) == 0,
            blockers=blockers,
        )

    @staticmethod
    def _format_activation_blockers(blockers: list[SearchActivationGateBlocker]) -> str:
        if len(blockers) == 0:
            return ""
        return ", ".join(blocker.code for blocker in blockers)

    def _passes_entity_coverage_gate(
        self,
        *,
        source_snapshot: dict[str, object],
        entity_count: int,
        occurrence_count: int,
    ) -> bool:
        eligible = self._read_snapshot_int(
            source_snapshot,
            [
                "eligibleInputCount",
                "eligible_input_count",
                "eligibleTranscriptBasisCount",
                "eligible_basis_count",
            ],
        )
        covered = self._read_snapshot_int(
            source_snapshot,
            [
                "coveredInputCount",
                "covered_input_count",
                "indexedOccurrenceBasisCount",
                "indexed_basis_count",
            ],
        )

        if eligible is None:
            # Preserve no-data projects and earlier snapshots that do not expose
            # explicit coverage counters.
            return (entity_count == 0 and occurrence_count == 0) or occurrence_count > 0
        if eligible <= 0:
            return True
        if covered is not None:
            return covered >= eligible
        return occurrence_count > 0

    def _active_derivative_index_id_or_raise(self, *, project_id: str) -> str:
        projection = self._store.get_projection(project_id=project_id)
        if projection is None or projection.active_derivative_index_id is None:
            raise IndexConflictError("No active derivative index is available for this project.")
        return projection.active_derivative_index_id

    @staticmethod
    def _normalize_derivative_scope(scope: str | None) -> DerivativeScope:
        normalized = (scope or "active").strip().lower()
        if normalized not in {"active", "historical"}:
            raise IndexValidationError("scope must be one of: active, historical.")
        return normalized  # type: ignore[return-value]

    @staticmethod
    def _normalize_field_token(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    def _value_for_field(
        self,
        *,
        payload: dict[str, object],
        field_name: str,
    ) -> object | None:
        if field_name in payload:
            return payload.get(field_name)
        target = self._normalize_field_token(field_name)
        for key, value in payload.items():
            if not isinstance(key, str):
                continue
            if self._normalize_field_token(key) == target:
                return value
        return None

    def _collect_identifier_field_paths(
        self,
        value: object,
        *,
        prefix: str = "",
    ) -> set[str]:
        leaks: set[str] = set()
        if isinstance(value, dict):
            for raw_key, raw_child in value.items():
                if not isinstance(raw_key, str):
                    continue
                field_path = f"{prefix}.{raw_key}" if prefix else raw_key
                key_token = self._normalize_field_token(raw_key)
                if key_token in _SUPPRESSED_IDENTIFIER_CANONICAL_KEYS:
                    leaks.add(field_path)
                    continue
                leaks.update(
                    self._collect_identifier_field_paths(
                        raw_child,
                        prefix=field_path,
                    )
                )
        elif isinstance(value, list):
            for idx, item in enumerate(value):
                field_path = f"{prefix}[{idx}]" if prefix else f"[{idx}]"
                leaks.update(
                    self._collect_identifier_field_paths(
                        item,
                        prefix=field_path,
                    )
                )
        return leaks

    def _suppress_derivative_payload(
        self,
        payload: dict[str, object],
    ) -> tuple[dict[str, object], dict[str, object]]:
        suppressed_fields: dict[str, str] = {}

        def scrub(value: object, *, prefix: str = "") -> object:
            if isinstance(value, dict):
                cleaned: dict[str, object] = {}
                for raw_key, raw_child in value.items():
                    if not isinstance(raw_key, str):
                        continue
                    field_path = f"{prefix}.{raw_key}" if prefix else raw_key
                    key_token = self._normalize_field_token(raw_key)
                    if key_token in _SUPPRESSED_IDENTIFIER_CANONICAL_KEYS:
                        suppressed_fields[field_path] = "IDENTIFIER_SUPPRESSED"
                        continue
                    cleaned[raw_key] = scrub(raw_child, prefix=field_path)
                return cleaned
            if isinstance(value, list):
                return [scrub(item, prefix=f"{prefix}[{index}]") for index, item in enumerate(value)]
            return value

        cleaned_payload = scrub(payload)
        if not isinstance(cleaned_payload, dict):
            cleaned_payload = {}
        suppressed_json: dict[str, object] = {
            "fields": suppressed_fields,
            "suppressedCount": len(suppressed_fields),
        }
        return cleaned_payload, suppressed_json

    def _extract_antijoin_quasi_fields(
        self,
        *,
        source_snapshot: dict[str, object],
        payloads: list[dict[str, object]],
    ) -> list[str]:
        for key in (
            "antiJoinQuasiIdentifierFields",
            "anti_join_quasi_identifier_fields",
            "quasiIdentifierFields",
            "quasi_identifier_fields",
        ):
            raw = source_snapshot.get(key)
            if not isinstance(raw, list):
                continue
            fields = [
                value.strip()
                for value in raw
                if isinstance(value, str) and value.strip()
            ]
            if fields:
                return fields

        if not payloads:
            return []
        sample = payloads[0]
        inferred: list[str] = []
        for candidate in _DEFAULT_ANTIJOIN_QUASI_FIELDS:
            value = self._value_for_field(payload=sample, field_name=candidate)
            if value is not None:
                inferred.append(candidate)
        return inferred

    def _extract_antijoin_threshold(self, *, source_snapshot: dict[str, object]) -> int:
        threshold = self._read_snapshot_int(
            source_snapshot,
            [
                "antiJoinMinimumGroupSize",
                "anti_join_min_group_size",
                "kAnonymityFloor",
                "k_anonymity_floor",
            ],
        )
        if threshold is None:
            return 2
        return max(2, threshold)

    def _find_derivative_antijoin_issues(
        self,
        *,
        payloads: list[dict[str, object]],
        source_snapshot: dict[str, object],
    ) -> list[str]:
        if not payloads:
            return []
        quasi_fields = self._extract_antijoin_quasi_fields(
            source_snapshot=source_snapshot,
            payloads=payloads,
        )
        if not quasi_fields:
            return []
        threshold = self._extract_antijoin_threshold(source_snapshot=source_snapshot)
        groups: dict[tuple[str, ...], int] = {}
        for payload in payloads:
            group_key: list[str] = []
            for field in quasi_fields:
                value = self._value_for_field(payload=payload, field_name=field)
                if value is None:
                    group_key.append("<missing>")
                elif isinstance(value, str):
                    normalized = value.strip().lower()
                    group_key.append(normalized if normalized else "<blank>")
                else:
                    group_key.append(str(value))
            tuple_key = tuple(group_key)
            groups[tuple_key] = groups.get(tuple_key, 0) + 1

        issues: list[str] = []
        for group_key, count in groups.items():
            if count >= threshold:
                continue
            descriptor = ", ".join(
                f"{field}={value}" for field, value in zip(quasi_fields, group_key)
            )
            issues.append(descriptor)
        return issues

    def _find_derivative_identifier_leaks(
        self,
        *,
        rows: list[DerivativeIndexRowRecord],
    ) -> list[str]:
        issues: list[str] = []
        for row in rows:
            leaks = self._collect_identifier_field_paths(row.display_payload_json)
            if leaks:
                issues.append(row.id)
                continue
            fields_node = row.suppressed_fields_json.get("fields")
            if not isinstance(fields_node, dict):
                issues.append(row.id)
        return issues

    def _passes_derivative_snapshot_completeness_gate(
        self,
        *,
        source_snapshot: dict[str, object],
        successful_snapshot_count: int,
        row_count: int,
    ) -> bool:
        eligible = self._read_snapshot_int(
            source_snapshot,
            [
                "eligibleInputCount",
                "eligible_input_count",
                "eligibleDerivativeInputCount",
                "eligible_derivative_input_count",
            ],
        )
        covered = self._read_snapshot_int(
            source_snapshot,
            [
                "coveredInputCount",
                "covered_input_count",
                "coveredDerivativeInputCount",
                "covered_derivative_input_count",
                "coveredDerivativeSnapshotCount",
                "covered_derivative_snapshot_count",
            ],
        )
        if eligible is None:
            if successful_snapshot_count == 0:
                return row_count == 0
            return row_count > 0
        if eligible <= 0:
            return True
        if covered is not None:
            return covered >= eligible and successful_snapshot_count > 0 and row_count > 0
        return successful_snapshot_count > 0 and row_count > 0

    def materialize_derivative_snapshot(
        self,
        *,
        actor_user_id: str,
        project_id: str,
        derivative_index_id: str,
        derivative_kind: str,
        source_snapshot_json: dict[str, object],
        policy_version_ref: str,
        rows: list[DerivativeMaterializedRow],
        supersedes_derivative_snapshot_id: str | None = None,
    ) -> DerivativeMaterializationResult:
        index = self._store.get_index(
            project_id=project_id,
            kind="DERIVATIVE",
            index_id=derivative_index_id,
        )
        if index is None:
            raise IndexNotFoundError("Derivative index generation not found.")

        normalized_kind = derivative_kind.strip()
        if not normalized_kind:
            raise IndexValidationError("derivativeKind must be a non-empty string.")
        normalized_policy = policy_version_ref.strip()
        if not normalized_policy:
            raise IndexValidationError("policyVersionRef must be a non-empty string.")
        normalized_source_snapshot = _normalize_json_object(
            "sourceSnapshotJson",
            source_snapshot_json,
        )

        normalized_rows = sorted(
            rows,
            key=lambda item: _canonical_json(
                {
                    "derivative_kind": item.derivative_kind,
                    "source_snapshot_json": item.source_snapshot_json,
                    "display_payload_json": item.display_payload_json,
                }
            ),
        )
        row_inputs: list[CreateDerivativeIndexRowInput] = []
        payloads_for_checks: list[dict[str, object]] = []
        for item in normalized_rows:
            row_source_snapshot = _normalize_json_object(
                "rowSourceSnapshotJson",
                item.source_snapshot_json,
            )
            row_display_payload = _normalize_json_object(
                "displayPayloadJson",
                item.display_payload_json,
            )
            cleaned_payload, suppressed_fields_json = self._suppress_derivative_payload(
                row_display_payload
            )
            row_inputs.append(
                CreateDerivativeIndexRowInput(
                    derivative_kind=item.derivative_kind.strip() or normalized_kind,
                    source_snapshot_json=row_source_snapshot,
                    display_payload_json=cleaned_payload,
                    suppressed_fields_json=suppressed_fields_json,
                )
            )
            payloads_for_checks.append(cleaned_payload)

        anti_join_issues = self._find_derivative_antijoin_issues(
            payloads=payloads_for_checks,
            source_snapshot=normalized_source_snapshot,
        )

        blocked = len(anti_join_issues) > 0
        blocked_reason = (
            "Anti-join disclosure checks failed for one or more quasi-identifier groups."
            if blocked
            else None
        )
        snapshot_id = f"dersnap-{uuid4()}"
        started_at = self._store.utcnow()
        finished_at = started_at
        snapshot_material = {
            "derivativeSnapshotId": snapshot_id,
            "derivativeIndexId": derivative_index_id,
            "derivativeKind": normalized_kind,
            "policyVersionRef": normalized_policy,
            "sourceSnapshotJson": normalized_source_snapshot,
            "rows": [
                {
                    "derivativeKind": row.derivative_kind,
                    "sourceSnapshotJson": row.source_snapshot_json,
                    "displayPayloadJson": row.display_payload_json,
                    "suppressedFieldsJson": row.suppressed_fields_json,
                }
                for row in row_inputs
            ],
        }
        snapshot_sha256 = (
            hashlib.sha256(_canonical_json(snapshot_material).encode("utf-8")).hexdigest()
            if not blocked
            else None
        )
        storage_key = (
            f"indexes/derivatives/{project_id}/{derivative_index_id}/{snapshot_id}.json"
            if snapshot_sha256 is not None
            else None
        )
        snapshot = self._store.create_derivative_snapshot(
            project_id=project_id,
            derivative_index_id=derivative_index_id,
            snapshot_id=snapshot_id,
            derivative_kind=normalized_kind,
            source_snapshot_json=normalized_source_snapshot,
            policy_version_ref=normalized_policy,
            status="FAILED" if blocked else "SUCCEEDED",
            supersedes_derivative_snapshot_id=supersedes_derivative_snapshot_id,
            storage_key=storage_key,
            snapshot_sha256=snapshot_sha256,
            candidate_snapshot_id=None,
            created_by=actor_user_id,
            started_at=started_at,
            finished_at=finished_at,
            failure_reason=blocked_reason,
        )
        rows_written = self._store.append_derivative_index_rows(
            project_id=project_id,
            derivative_index_id=derivative_index_id,
            derivative_snapshot_id=snapshot.id,
            items=row_inputs,
        )
        return DerivativeMaterializationResult(
            snapshot=snapshot,
            rows_written=rows_written,
            blocked=blocked,
            blocked_reason=blocked_reason,
        )

    def list_project_derivatives(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        scope: str | None,
    ) -> ProjectDerivativeListResult:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_read_access(context)
        normalized_scope = self._normalize_derivative_scope(scope)
        projection = self._store.get_projection(project_id=project_id)
        active_derivative_index_id = (
            projection.active_derivative_index_id if projection else None
        )

        if normalized_scope == "active" and active_derivative_index_id is None:
            raise IndexConflictError("No active derivative index is available for this project.")

        items: dict[str, DerivativeSnapshotListItem] = {}
        if active_derivative_index_id is not None:
            active_rows = self._store.list_derivative_snapshots_for_index(
                project_id=project_id,
                derivative_index_id=active_derivative_index_id,
            )
            for row in active_rows:
                items[row.id] = DerivativeSnapshotListItem(
                    snapshot=row,
                    is_active_generation=True,
                )

        if normalized_scope == "historical":
            historical_rows = self._store.list_unsuperseded_successful_derivative_snapshots(
                project_id=project_id
            )
            for row in historical_rows:
                if row.id in items:
                    continue
                items[row.id] = DerivativeSnapshotListItem(
                    snapshot=row,
                    is_active_generation=row.derivative_index_id == active_derivative_index_id,
                )

        sorted_items = sorted(
            items.values(),
            key=lambda item: (item.snapshot.created_at, item.snapshot.id),
            reverse=True,
        )
        return ProjectDerivativeListResult(
            scope=normalized_scope,
            active_derivative_index_id=active_derivative_index_id,
            items=sorted_items,
        )

    def get_project_derivative_detail(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        derivative_id: str,
    ) -> ProjectDerivativeDetailResult:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_read_access(context)
        snapshot = self._store.get_derivative_snapshot(
            project_id=project_id,
            derivative_snapshot_id=derivative_id,
        )
        if snapshot is None:
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
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_read_access(context)
        snapshot = self._store.get_derivative_snapshot(
            project_id=project_id,
            derivative_snapshot_id=derivative_id,
        )
        if snapshot is None:
            raise IndexNotFoundError("Derivative snapshot was not found.")
        rows = self._store.list_all_derivative_rows_for_snapshot(
            derivative_index_id=snapshot.derivative_index_id,
            derivative_snapshot_id=snapshot.id,
        )
        return ProjectDerivativePreviewResult(snapshot=snapshot, rows=rows)

    def _validate_derivative_snapshot_for_candidate_freeze(
        self,
        *,
        snapshot: DerivativeSnapshotRecord,
        rows: list[DerivativeIndexRowRecord],
    ) -> None:
        if snapshot.status != "SUCCEEDED":
            raise IndexConflictError(
                "Candidate freeze is allowed only for SUCCEEDED derivative snapshots."
            )
        if not snapshot.storage_key or not snapshot.storage_key.strip():
            raise IndexConflictError(
                "Candidate freeze is blocked until storage_key is populated."
            )
        if not snapshot.snapshot_sha256 or not snapshot.snapshot_sha256.strip():
            raise IndexConflictError(
                "Candidate freeze is blocked until snapshot_sha256 is populated."
            )
        if snapshot.superseded_by_derivative_snapshot_id is not None:
            raise IndexConflictError("Superseded derivative snapshots cannot be frozen.")
        if len(rows) == 0:
            raise IndexConflictError(
                "Candidate freeze is blocked until derivative preview rows are materialized."
            )
        identifier_issues = self._find_derivative_identifier_leaks(rows=rows)
        if identifier_issues:
            raise IndexConflictError(
                "Candidate freeze blocked: no raw identifier fields may remain in derivative previews."
            )
        anti_join_issues = self._find_derivative_antijoin_issues(
            payloads=[row.display_payload_json for row in rows],
            source_snapshot=snapshot.source_snapshot_json,
        )
        if anti_join_issues:
            raise IndexConflictError(
                "Candidate freeze blocked: anti-join disclosure checks failed."
            )

    def freeze_derivative_candidate_snapshot(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        derivative_id: str,
    ) -> DerivativeCandidateFreezeResult:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_derivative_candidate_freeze_access(context)

        snapshot = self._store.get_derivative_snapshot(
            project_id=project_id,
            derivative_snapshot_id=derivative_id,
        )
        if snapshot is None:
            raise IndexNotFoundError("Derivative snapshot was not found.")
        index = self._store.get_index(
            project_id=project_id,
            kind="DERIVATIVE",
            index_id=snapshot.derivative_index_id,
        )
        if index is None:
            raise IndexConflictError(
                "Derivative snapshot does not belong to an available derivative index generation."
            )

        if snapshot.candidate_snapshot_id:
            try:
                existing = self._export_store.get_candidate(
                    project_id=project_id,
                    candidate_id=snapshot.candidate_snapshot_id,
                )
            except ExportStoreNotFoundError as error:
                raise IndexConflictError(
                    "Derivative snapshot references a missing candidate snapshot."
                ) from error
            except (ExportStoreConflictError, ExportStoreUnavailableError) as error:
                raise IndexStoreUnavailableError(
                    "Export candidate snapshot lookup failed."
                ) from error
            return DerivativeCandidateFreezeResult(
                snapshot=snapshot,
                candidate=existing,
                created=False,
            )

        rows = self._store.list_all_derivative_rows_for_snapshot(
            derivative_index_id=snapshot.derivative_index_id,
            derivative_snapshot_id=snapshot.id,
        )
        self._validate_derivative_snapshot_for_candidate_freeze(
            snapshot=snapshot,
            rows=rows,
        )

        suppressed_fields: set[str] = set()
        for row in rows:
            fields_node = row.suppressed_fields_json.get("fields")
            if not isinstance(fields_node, dict):
                continue
            for field_name in fields_node.keys():
                if isinstance(field_name, str) and field_name.strip():
                    suppressed_fields.add(field_name.strip())

        try:
            candidate, created = self._export_store.create_or_get_derivative_candidate_snapshot(
                project_id=project_id,
                derivative_snapshot_id=snapshot.id,
                derivative_index_id=snapshot.derivative_index_id,
                derivative_kind=snapshot.derivative_kind,
                source_snapshot_json=snapshot.source_snapshot_json,
                policy_version_ref=snapshot.policy_version_ref,
                storage_key=snapshot.storage_key or "",
                snapshot_sha256=snapshot.snapshot_sha256 or "",
                suppressed_field_names=tuple(sorted(suppressed_fields)),
                row_count=len(rows),
                created_by=current_user.user_id,
            )
        except ExportStoreConflictError as error:
            raise IndexConflictError(str(error)) from error
        except ExportStoreUnavailableError as error:
            raise IndexStoreUnavailableError(
                "Export candidate snapshot store is unavailable."
            ) from error

        linked_snapshot = self._store.set_derivative_snapshot_candidate_snapshot_id(
            project_id=project_id,
            derivative_snapshot_id=snapshot.id,
            candidate_snapshot_id=candidate.id,
        )
        if linked_snapshot is None:
            raise IndexNotFoundError("Derivative snapshot was not found.")

        resolved_candidate_id = linked_snapshot.candidate_snapshot_id or candidate.id
        if resolved_candidate_id != candidate.id:
            try:
                candidate = self._export_store.get_candidate(
                    project_id=project_id,
                    candidate_id=resolved_candidate_id,
                )
            except ExportStoreNotFoundError as error:
                raise IndexConflictError(
                    "Derivative snapshot references a missing candidate snapshot."
                ) from error
            except (ExportStoreConflictError, ExportStoreUnavailableError) as error:
                raise IndexStoreUnavailableError(
                    "Export candidate snapshot lookup failed."
                ) from error
            created = False

        return DerivativeCandidateFreezeResult(
            snapshot=linked_snapshot,
            candidate=candidate,
            created=created,
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
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_mutation_access(context)

        normalized_snapshot = _normalize_json_object("sourceSnapshotJson", source_snapshot_json)
        if len(normalized_snapshot) == 0:
            raise IndexValidationError("sourceSnapshotJson must be a non-empty JSON object.")
        normalized_params = _normalize_json_object("buildParametersJson", build_parameters_json)

        source_snapshot_sha256 = self.compute_source_snapshot_sha256(normalized_snapshot)
        rebuild_dedupe_key = self.compute_rebuild_dedupe_key(
            project_id=project_id,
            kind=kind,
            source_snapshot_sha256=source_snapshot_sha256,
            build_parameters_json=normalized_params,
        )

        if not force:
            existing = self._store.find_equivalent_index(
                project_id=project_id,
                kind=kind,
                rebuild_dedupe_key=rebuild_dedupe_key,
            )
            if existing is not None:
                return IndexRebuildResult(
                    index=existing,
                    created=False,
                    reason=f"EXISTING_{existing.status}",
                )

        projection = self._store.get_projection(project_id=project_id)
        fallback_supersedes: str | None = None
        if kind == "SEARCH":
            fallback_supersedes = projection.active_search_index_id if projection else None
        elif kind == "ENTITY":
            fallback_supersedes = projection.active_entity_index_id if projection else None
        else:
            fallback_supersedes = projection.active_derivative_index_id if projection else None

        resolved_supersedes_id = supersedes_index_id or fallback_supersedes
        if isinstance(resolved_supersedes_id, str):
            superseded = self._store.get_index(
                project_id=project_id,
                kind=kind,
                index_id=resolved_supersedes_id,
            )
            if superseded is None:
                raise IndexValidationError(
                    "supersedesIndexId does not exist in this index lineage."
                )

        created = self._store.create_index_generation(
            project_id=project_id,
            kind=kind,
            index_id=str(uuid4()),
            source_snapshot_json=normalized_snapshot,
            source_snapshot_sha256=source_snapshot_sha256,
            build_parameters_json=normalized_params,
            rebuild_dedupe_key=rebuild_dedupe_key,
            created_by=current_user.user_id,
            supersedes_index_id=resolved_supersedes_id,
        )
        return IndexRebuildResult(index=created, created=True, reason="CREATED")

    def cancel_index(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        kind: IndexKind,
        index_id: str,
    ) -> IndexCancelResult:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_mutation_access(context)
        row = self._store.get_index(project_id=project_id, kind=kind, index_id=index_id)
        if row is None:
            raise IndexNotFoundError("Index generation not found.")

        if row.status == "QUEUED":
            canceled = self._store.cancel_queued(
                project_id=project_id,
                kind=kind,
                index_id=index_id,
                canceled_by=current_user.user_id,
            )
            if canceled is None:
                raise IndexConflictError("Cancel is allowed only for QUEUED or RUNNING indexes.")
            return IndexCancelResult(index=canceled, terminal=True)

        if row.status == "RUNNING":
            requested = self._store.request_running_cancel(
                project_id=project_id,
                kind=kind,
                index_id=index_id,
                requested_by=current_user.user_id,
            )
            if requested is None:
                raise IndexConflictError("Cancel is allowed only for QUEUED or RUNNING indexes.")
            return IndexCancelResult(index=requested, terminal=False)

        raise IndexConflictError("Cancel is allowed only for QUEUED or RUNNING indexes.")

    def activate_index(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        kind: IndexKind,
        index_id: str,
    ) -> tuple[IndexRecord, ProjectIndexProjectionRecord]:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_mutation_access(context)
        row = self._store.get_index(project_id=project_id, kind=kind, index_id=index_id)
        if row is None:
            raise IndexNotFoundError("Index generation not found.")
        if kind == "SEARCH":
            evaluation = self.evaluate_search_activation_gate(row=row)
            if not evaluation.passed:
                blocker_codes = self._format_activation_blockers(evaluation.blockers)
                raise IndexConflictError(
                    "Search index activation blocked: recall-first token-anchor and "
                    f"geometry coverage gates failed ({blocker_codes})."
                )
        elif row.status != "SUCCEEDED":
            raise IndexConflictError("Only SUCCEEDED index generations can be activated.")

        if kind == "ENTITY":
            self._validate_entity_index_activation(row=row)
        elif kind == "DERIVATIVE":
            self._validate_derivative_index_activation(row=row)

        current_projection = self._store.get_projection(project_id=project_id)
        active_search_index_id = (
            current_projection.active_search_index_id if current_projection else None
        )
        active_entity_index_id = (
            current_projection.active_entity_index_id if current_projection else None
        )
        active_derivative_index_id = (
            current_projection.active_derivative_index_id if current_projection else None
        )
        if kind == "SEARCH":
            active_search_index_id = row.id
        elif kind == "ENTITY":
            active_entity_index_id = row.id
        else:
            active_derivative_index_id = row.id

        projection = self._store.upsert_projection(
            project_id=project_id,
            active_search_index_id=active_search_index_id,
            active_entity_index_id=active_entity_index_id,
            active_derivative_index_id=active_derivative_index_id,
        )
        activated = self._store.set_activation_metadata(
            project_id=project_id,
            kind=kind,
            index_id=row.id,
            activated_by=current_user.user_id,
        )
        if activated is None:
            raise IndexNotFoundError("Index generation not found.")
        return activated, projection

    @staticmethod
    def _active_index_id_for_kind(
        *,
        projection: ProjectIndexProjectionRecord | None,
        kind: IndexKind,
    ) -> str | None:
        if projection is None:
            return None
        if kind == "SEARCH":
            return projection.active_search_index_id
        if kind == "ENTITY":
            return projection.active_entity_index_id
        return projection.active_derivative_index_id

    @staticmethod
    def _latest_succeeded_index(rows: list[IndexRecord]) -> IndexRecord | None:
        for row in rows:
            if row.status == "SUCCEEDED":
                return row
        return None

    @staticmethod
    def _latest_index(rows: list[IndexRecord]) -> IndexRecord | None:
        if len(rows) == 0:
            return None
        return rows[0]

    def _resolve_freshness_snapshot(
        self,
        *,
        kind: IndexKind,
        rows: list[IndexRecord],
        projection: ProjectIndexProjectionRecord | None,
    ) -> IndexFreshnessSnapshot:
        active_index_id = self._active_index_id_for_kind(projection=projection, kind=kind)
        active_row = next((row for row in rows if row.id == active_index_id), None)
        latest_succeeded = self._latest_succeeded_index(rows)
        latest_row = self._latest_index(rows)
        blocked_codes: list[str] = []
        reason: str | None = None

        if active_index_id is None:
            if latest_succeeded is None:
                if latest_row is None:
                    status: IndexFreshnessStatus = "missing"
                    reason = "No index generations are present."
                else:
                    status = "blocked"
                    reason = "No SUCCEEDED generation is available to activate."
                    blocked_codes.append("NO_SUCCEEDED_GENERATION")
            elif kind == "SEARCH":
                evaluation = self.evaluate_search_activation_gate(row=latest_succeeded)
                if not evaluation.passed:
                    status = "blocked"
                    reason = (
                        "Latest SUCCEEDED search generation cannot be activated until "
                        "recall-first gates pass."
                    )
                    blocked_codes.extend([blocker.code for blocker in evaluation.blockers])
                else:
                    status = "missing"
                    reason = "No active index projection pointer is set."
            else:
                status = "missing"
                reason = "No active index projection pointer is set."
        elif active_row is None:
            status = "blocked"
            reason = "Active projection references a missing index generation."
            blocked_codes.append("ACTIVE_INDEX_MISSING")
        elif latest_succeeded is None:
            status = "blocked"
            reason = "No SUCCEEDED generation is available."
            blocked_codes.append("NO_SUCCEEDED_GENERATION")
        else:
            if kind == "SEARCH":
                active_evaluation = self.evaluate_search_activation_gate(row=active_row)
                if not active_evaluation.passed:
                    status = "blocked"
                    reason = (
                        "Active search generation no longer satisfies recall-first "
                        "activation gates."
                    )
                    blocked_codes.extend(
                        [blocker.code for blocker in active_evaluation.blockers]
                    )
                elif active_row.id == latest_succeeded.id:
                    status = "current"
                else:
                    status = "stale"
                    reason = "A newer SUCCEEDED generation exists but is not active."
            elif active_row.id == latest_succeeded.id:
                status = "current"
            else:
                status = "stale"
                reason = "A newer SUCCEEDED generation exists but is not active."

        stale_generation_gap: int | None = None
        if (
            status == "stale"
            and latest_succeeded is not None
            and active_row is not None
            and latest_succeeded.version >= active_row.version
        ):
            stale_generation_gap = latest_succeeded.version - active_row.version

        return IndexFreshnessSnapshot(
            status=status,
            active_index_id=active_index_id,
            active_version=active_row.version if active_row is not None else None,
            active_status=active_row.status if active_row is not None else None,
            latest_succeeded_index_id=(
                latest_succeeded.id if latest_succeeded is not None else None
            ),
            latest_succeeded_version=(
                latest_succeeded.version if latest_succeeded is not None else None
            ),
            latest_succeeded_finished_at=(
                latest_succeeded.finished_at if latest_succeeded is not None else None
            ),
            stale_generation_gap=stale_generation_gap,
            reason=reason,
            blocked_codes=blocked_codes,
        )

    def _require_existing_project(self, *, project_id: str) -> None:
        try:
            project = self._project_store.get_project_summary(project_id=project_id)
        except ProjectStoreUnavailableError as error:
            raise IndexStoreUnavailableError("Project access lookup failed.") from error
        if project is None:
            raise IndexNotFoundError("Project not found.")

    def get_index_quality_summary(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> ProjectIndexQualitySummary:
        self._require_index_quality_read_access(current_user)
        self._require_existing_project(project_id=project_id)
        projection = self._store.get_projection(project_id=project_id)

        items: list[IndexQualitySummaryItem] = []
        for kind in ("SEARCH", "ENTITY", "DERIVATIVE"):
            rows = self._store.list_indexes(project_id=project_id, kind=kind)
            freshness = self._resolve_freshness_snapshot(
                kind=kind,
                rows=rows,
                projection=projection,
            )
            active_row = (
                next(
                    (
                        row
                        for row in rows
                        if row.id == self._active_index_id_for_kind(
                            projection=projection,
                            kind=kind,
                        )
                    ),
                    None,
                )
                if kind == "SEARCH"
                else None
            )
            latest_succeeded = (
                self._latest_succeeded_index(rows) if kind == "SEARCH" else None
            )
            search_reference_row = active_row or latest_succeeded
            if search_reference_row is not None:
                search_coverage = self._build_search_coverage_summary(
                    source_snapshot=search_reference_row.source_snapshot_json
                )
                blocker_count = len(
                    self.evaluate_search_activation_gate(row=search_reference_row).blockers
                )
            else:
                search_coverage = None
                blocker_count = 0

            items.append(
                IndexQualitySummaryItem(
                    kind=kind,
                    freshness=freshness,
                    search_coverage=search_coverage,
                    search_activation_blocker_count=blocker_count,
                )
            )

        return ProjectIndexQualitySummary(
            project_id=project_id,
            projection_updated_at=projection.updated_at if projection else None,
            items=items,
        )

    def get_index_quality_detail(
        self,
        *,
        current_user: SessionPrincipal,
        kind: IndexKind,
        index_id: str,
    ) -> IndexQualityDetail:
        self._require_index_quality_read_access(current_user)
        row = self._store.get_index_by_id(kind=kind, index_id=index_id)
        if row is None:
            raise IndexNotFoundError("Index generation not found.")
        self._require_existing_project(project_id=row.project_id)

        projection = self._store.get_projection(project_id=row.project_id)
        rows = self._store.list_indexes(project_id=row.project_id, kind=kind)
        freshness = self._resolve_freshness_snapshot(
            kind=kind,
            rows=rows,
            projection=projection,
        )
        active_index_id = self._active_index_id_for_kind(projection=projection, kind=kind)
        latest_succeeded = self._latest_succeeded_index(rows)
        is_active_generation = active_index_id == row.id
        is_latest_succeeded_generation = (
            latest_succeeded is not None and latest_succeeded.id == row.id
        )
        rollback_eligible = kind == "SEARCH" and row.status == "SUCCEEDED" and not is_active_generation
        search_coverage = (
            self._build_search_coverage_summary(source_snapshot=row.source_snapshot_json)
            if kind == "SEARCH"
            else None
        )
        search_activation_evaluation = (
            self.evaluate_search_activation_gate(row=row) if kind == "SEARCH" else None
        )

        return IndexQualityDetail(
            project_id=row.project_id,
            kind=kind,
            index=row,
            freshness=freshness,
            active_index_id=active_index_id,
            is_active_generation=is_active_generation,
            is_latest_succeeded_generation=is_latest_succeeded_generation,
            rollback_eligible=rollback_eligible,
            search_coverage=search_coverage,
            search_activation_evaluation=search_activation_evaluation,
        )

    def list_search_query_audits(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        cursor: int,
        limit: int,
    ) -> ProjectSearchQueryAuditResult:
        self._require_index_quality_read_access(current_user)
        self._require_existing_project(project_id=project_id)
        if cursor < 0:
            raise IndexValidationError("cursor must be greater than or equal to 0.")
        if limit < 1 or limit > 100:
            raise IndexValidationError("limit must be between 1 and 100.")

        page = self._store.list_search_query_audits(
            project_id=project_id,
            cursor=cursor,
            limit=limit,
        )
        return ProjectSearchQueryAuditResult(
            project_id=project_id,
            items=page.items,
            next_cursor=page.next_cursor,
        )

    def mark_index_started(
        self,
        *,
        actor_user_id: str,
        project_id: str,
        kind: IndexKind,
        index_id: str,
    ) -> IndexRecord:
        started = self._store.mark_running(
            project_id=project_id,
            kind=kind,
            index_id=index_id,
        )
        if started is None:
            raise IndexConflictError("Start is allowed only for QUEUED index generations.")
        self._record_lifecycle_event(
            event_type=_run_started_event(kind),
            actor_user_id=actor_user_id,
            project_id=project_id,
            kind=kind,
            index=started,
        )
        return started

    def mark_index_finished(
        self,
        *,
        actor_user_id: str,
        project_id: str,
        kind: IndexKind,
        index_id: str,
    ) -> IndexRecord:
        running = self._store.get_index(project_id=project_id, kind=kind, index_id=index_id)
        if running is None:
            raise IndexNotFoundError("Index generation not found.")
        if running.status != "RUNNING":
            raise IndexConflictError("Finish is allowed only for RUNNING index generations.")

        if running.cancel_requested:
            canceled = self._store.cancel_running(
                project_id=project_id,
                kind=kind,
                index_id=index_id,
                canceled_by=actor_user_id,
            )
            if canceled is None:
                raise IndexConflictError("Running cancellation could not be finalized.")
            self._record_lifecycle_event(
                event_type=_run_canceled_event(kind),
                actor_user_id=actor_user_id,
                project_id=project_id,
                kind=kind,
                index=canceled,
            )
            return canceled

        finished = self._store.mark_succeeded(
            project_id=project_id,
            kind=kind,
            index_id=index_id,
        )
        if finished is None:
            raise IndexConflictError("Finish is allowed only for RUNNING index generations.")
        self._record_lifecycle_event(
            event_type=_run_finished_event(kind),
            actor_user_id=actor_user_id,
            project_id=project_id,
            kind=kind,
            index=finished,
        )
        return finished

    def mark_index_failed(
        self,
        *,
        actor_user_id: str,
        project_id: str,
        kind: IndexKind,
        index_id: str,
        failure_reason: str,
    ) -> IndexRecord:
        reason = failure_reason.strip()
        if len(reason) == 0:
            raise IndexValidationError("failureReason must be a non-empty string.")
        failed = self._store.mark_failed(
            project_id=project_id,
            kind=kind,
            index_id=index_id,
            failure_reason=reason[:1200],
        )
        if failed is None:
            raise IndexConflictError("Failure is allowed only for RUNNING index generations.")
        self._record_lifecycle_event(
            event_type=_run_failed_event(kind),
            actor_user_id=actor_user_id,
            project_id=project_id,
            kind=kind,
            index=failed,
            extra_metadata={"reason": failed.failure_reason or ""},
        )
        return failed

    def _record_lifecycle_event(
        self,
        *,
        event_type: str,
        actor_user_id: str,
        project_id: str,
        kind: IndexKind,
        index: IndexRecord,
        extra_metadata: dict[str, object] | None = None,
    ) -> None:
        metadata: dict[str, object] = {
            "index_id": index.id,
            "index_kind": kind,
            "status": index.status,
            "version": index.version,
            "route": "worker:index-lifecycle",
        }
        if extra_metadata:
            metadata.update(extra_metadata)
        self._audit_service.record_event_best_effort(
            event_type=event_type,  # type: ignore[arg-type]
            actor_user_id=actor_user_id,
            project_id=project_id,
            object_type=_index_object_type(kind),
            object_id=index.id,
            metadata=metadata,
            request_id=current_trace_id() or f"index-worker:{index.id}",
        )

    def record_run_created_audit(
        self,
        *,
        actor_user_id: str,
        project_id: str,
        kind: IndexKind,
        index: IndexRecord,
        route: str,
        reason: str,
    ) -> None:
        self._audit_service.record_event_best_effort(
            event_type=_run_created_event(kind),  # type: ignore[arg-type]
            actor_user_id=actor_user_id,
            project_id=project_id,
            object_type=_index_object_type(kind),
            object_id=index.id,
            metadata={
                "route": route,
                "index_id": index.id,
                "status": index.status,
                "version": index.version,
                "reason": reason,
            },
        )

    def record_run_canceled_audit(
        self,
        *,
        actor_user_id: str,
        project_id: str,
        kind: IndexKind,
        index: IndexRecord,
        route: str,
        mode: str,
    ) -> None:
        self._audit_service.record_event_best_effort(
            event_type=_run_canceled_event(kind),  # type: ignore[arg-type]
            actor_user_id=actor_user_id,
            project_id=project_id,
            object_type=_index_object_type(kind),
            object_id=index.id,
            metadata={
                "route": route,
                "index_id": index.id,
                "status": index.status,
                "version": index.version,
                "mode": mode,
            },
        )


@lru_cache
def get_index_service() -> IndexService:
    settings = get_settings()
    return IndexService(settings=settings)
