from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from uuid import uuid4

from app.audit.service import AuditService, get_audit_service
from app.auth.models import SessionPrincipal
from app.core.config import Settings, get_settings
from app.indexes.models import (
    ActiveProjectIndexesView,
    ControlledEntityRecord,
    CreateControlledEntityInput,
    CreateEntityOccurrenceInput,
    EntityOccurrenceRecord,
    EntityType,
    IndexKind,
    IndexRecord,
    OccurrenceSpanBasisKind,
    ProjectIndexProjectionRecord,
    SearchDocumentRecord,
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
    ) -> None:
        self._settings = settings
        self._store = store or IndexStore(settings)
        self._project_store = project_store or ProjectStore(settings)
        self._audit_service = audit_service or get_audit_service()

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
        if row.status != "SUCCEEDED":
            raise IndexConflictError("Only SUCCEEDED index generations can be activated.")
        if kind == "ENTITY":
            self._validate_entity_index_activation(row=row)

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
