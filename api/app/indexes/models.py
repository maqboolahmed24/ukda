from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

IndexKind = Literal["SEARCH", "ENTITY", "DERIVATIVE"]
IndexStatus = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]
DerivativeSnapshotStatus = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]
DerivativeScope = Literal["active", "historical"]
SearchDocumentSourceKind = Literal["LINE", "RESCUE_CANDIDATE", "PAGE_WINDOW"]
EntityType = Literal["PERSON", "PLACE", "ORGANISATION", "DATE"]
OccurrenceSpanBasisKind = Literal["LINE_TEXT", "PAGE_WINDOW_TEXT", "NONE"]


@dataclass(frozen=True)
class IndexRecord:
    id: str
    project_id: str
    kind: IndexKind
    version: int
    source_snapshot_json: dict[str, object]
    source_snapshot_sha256: str
    build_parameters_json: dict[str, object]
    rebuild_dedupe_key: str
    status: IndexStatus
    supersedes_index_id: str | None
    superseded_by_index_id: str | None
    failure_reason: str | None
    created_by: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    cancel_requested_by: str | None
    cancel_requested_at: datetime | None
    canceled_by: str | None
    canceled_at: datetime | None
    activated_by: str | None
    activated_at: datetime | None

    @property
    def cancel_requested(self) -> bool:
        return self.cancel_requested_at is not None and self.status == "RUNNING"


@dataclass(frozen=True)
class ProjectIndexProjectionRecord:
    project_id: str
    active_search_index_id: str | None
    active_entity_index_id: str | None
    active_derivative_index_id: str | None
    updated_at: datetime


@dataclass(frozen=True)
class SearchDocumentRecord:
    id: str
    search_index_id: str
    document_id: str
    run_id: str
    page_id: str
    line_id: str | None
    token_id: str | None
    source_kind: SearchDocumentSourceKind
    source_ref_id: str
    page_number: int
    match_span_json: dict[str, object] | None
    token_geometry_json: dict[str, object] | None
    search_text: str
    search_metadata_json: dict[str, object]
    created_at: datetime


@dataclass(frozen=True)
class CreateSearchDocumentInput:
    document_id: str
    run_id: str
    page_id: str
    line_id: str | None
    token_id: str | None
    source_kind: SearchDocumentSourceKind
    source_ref_id: str
    page_number: int
    match_span_json: dict[str, object] | None
    token_geometry_json: dict[str, object] | None
    search_text: str
    search_metadata_json: dict[str, object]


@dataclass(frozen=True)
class SearchDocumentPage:
    items: list[SearchDocumentRecord]
    next_cursor: int | None


@dataclass(frozen=True)
class SearchQueryAuditRecord:
    id: str
    project_id: str
    actor_user_id: str
    search_index_id: str
    query_sha256: str
    query_text_key: str
    filters_json: dict[str, object]
    result_count: int
    created_at: datetime


@dataclass(frozen=True)
class SearchQueryAuditPage:
    items: list[SearchQueryAuditRecord]
    next_cursor: int | None


@dataclass(frozen=True)
class ControlledEntityRecord:
    id: str
    project_id: str
    entity_index_id: str
    entity_type: EntityType
    display_value: str
    canonical_value: str
    confidence_summary_json: dict[str, object]
    occurrence_count: int
    created_at: datetime


@dataclass(frozen=True)
class CreateControlledEntityInput:
    id: str
    entity_type: EntityType
    display_value: str
    canonical_value: str
    confidence_summary_json: dict[str, object]


@dataclass(frozen=True)
class ControlledEntityPage:
    items: list[ControlledEntityRecord]
    next_cursor: int | None


@dataclass(frozen=True)
class EntityOccurrenceRecord:
    id: str
    entity_index_id: str
    entity_id: str
    document_id: str
    run_id: str
    page_id: str
    line_id: str | None
    token_id: str | None
    source_kind: SearchDocumentSourceKind
    source_ref_id: str
    page_number: int
    confidence: float
    occurrence_span_json: dict[str, object] | None
    occurrence_span_basis_kind: OccurrenceSpanBasisKind
    occurrence_span_basis_ref: str | None
    token_geometry_json: dict[str, object] | None
    created_at: datetime


@dataclass(frozen=True)
class CreateEntityOccurrenceInput:
    id: str
    entity_id: str
    document_id: str
    run_id: str
    page_id: str
    line_id: str | None
    token_id: str | None
    source_kind: SearchDocumentSourceKind
    source_ref_id: str
    page_number: int
    confidence: float
    occurrence_span_json: dict[str, object] | None
    occurrence_span_basis_kind: OccurrenceSpanBasisKind
    occurrence_span_basis_ref: str | None
    token_geometry_json: dict[str, object] | None


@dataclass(frozen=True)
class EntityOccurrencePage:
    items: list[EntityOccurrenceRecord]
    next_cursor: int | None


@dataclass(frozen=True)
class DerivativeIndexRowRecord:
    id: str
    derivative_index_id: str
    derivative_snapshot_id: str
    derivative_kind: str
    source_snapshot_json: dict[str, object]
    display_payload_json: dict[str, object]
    suppressed_fields_json: dict[str, object]
    created_at: datetime


@dataclass(frozen=True)
class CreateDerivativeIndexRowInput:
    derivative_kind: str
    source_snapshot_json: dict[str, object]
    display_payload_json: dict[str, object]
    suppressed_fields_json: dict[str, object]


@dataclass(frozen=True)
class DerivativeIndexRowPage:
    items: list[DerivativeIndexRowRecord]
    next_cursor: int | None


@dataclass(frozen=True)
class DerivativeSnapshotRecord:
    id: str
    project_id: str
    derivative_index_id: str
    derivative_kind: str
    source_snapshot_json: dict[str, object]
    policy_version_ref: str
    status: DerivativeSnapshotStatus
    supersedes_derivative_snapshot_id: str | None
    superseded_by_derivative_snapshot_id: str | None
    storage_key: str | None
    snapshot_sha256: str | None
    candidate_snapshot_id: str | None
    created_by: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    failure_reason: str | None


@dataclass(frozen=True)
class DerivativeSnapshotListItem:
    snapshot: DerivativeSnapshotRecord
    is_active_generation: bool


@dataclass(frozen=True)
class ActiveProjectIndexesView:
    projection: ProjectIndexProjectionRecord | None
    search_index: IndexRecord | None
    entity_index: IndexRecord | None
    derivative_index: IndexRecord | None
