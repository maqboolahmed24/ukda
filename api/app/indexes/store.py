from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from app.core.config import Settings
from app.indexes.models import (
    ControlledEntityPage,
    ControlledEntityRecord,
    CreateDerivativeIndexRowInput,
    CreateSearchDocumentInput,
    CreateControlledEntityInput,
    CreateEntityOccurrenceInput,
    DerivativeIndexRowPage,
    DerivativeIndexRowRecord,
    DerivativeSnapshotRecord,
    EntityOccurrencePage,
    EntityOccurrenceRecord,
    IndexKind,
    IndexRecord,
    ProjectIndexProjectionRecord,
    SearchDocumentPage,
    SearchDocumentRecord,
    SearchQueryAuditPage,
    SearchQueryAuditRecord,
)
from app.projects.store import ProjectStore

INDEX_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS search_indexes (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      version INTEGER NOT NULL,
      source_snapshot_json JSONB NOT NULL,
      source_snapshot_sha256 TEXT NOT NULL,
      build_parameters_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      rebuild_dedupe_key TEXT NOT NULL,
      status TEXT NOT NULL CHECK (
        status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED')
      ),
      supersedes_index_id TEXT REFERENCES search_indexes(id),
      superseded_by_index_id TEXT REFERENCES search_indexes(id),
      failure_reason TEXT,
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL,
      started_at TIMESTAMPTZ,
      finished_at TIMESTAMPTZ,
      cancel_requested_by TEXT REFERENCES users(id),
      cancel_requested_at TIMESTAMPTZ,
      canceled_by TEXT REFERENCES users(id),
      canceled_at TIMESTAMPTZ,
      activated_by TEXT REFERENCES users(id),
      activated_at TIMESTAMPTZ,
      UNIQUE (project_id, version)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_search_indexes_project_created
      ON search_indexes(project_id, created_at DESC, id DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_search_indexes_project_dedupe
      ON search_indexes(project_id, rebuild_dedupe_key, version DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS entity_indexes (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      version INTEGER NOT NULL,
      source_snapshot_json JSONB NOT NULL,
      source_snapshot_sha256 TEXT NOT NULL,
      build_parameters_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      rebuild_dedupe_key TEXT NOT NULL,
      status TEXT NOT NULL CHECK (
        status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED')
      ),
      supersedes_index_id TEXT REFERENCES entity_indexes(id),
      superseded_by_index_id TEXT REFERENCES entity_indexes(id),
      failure_reason TEXT,
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL,
      started_at TIMESTAMPTZ,
      finished_at TIMESTAMPTZ,
      cancel_requested_by TEXT REFERENCES users(id),
      cancel_requested_at TIMESTAMPTZ,
      canceled_by TEXT REFERENCES users(id),
      canceled_at TIMESTAMPTZ,
      activated_by TEXT REFERENCES users(id),
      activated_at TIMESTAMPTZ,
      UNIQUE (project_id, version)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_entity_indexes_project_created
      ON entity_indexes(project_id, created_at DESC, id DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_entity_indexes_project_dedupe
      ON entity_indexes(project_id, rebuild_dedupe_key, version DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS derivative_indexes (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      version INTEGER NOT NULL,
      source_snapshot_json JSONB NOT NULL,
      source_snapshot_sha256 TEXT NOT NULL,
      build_parameters_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      rebuild_dedupe_key TEXT NOT NULL,
      status TEXT NOT NULL CHECK (
        status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED')
      ),
      supersedes_index_id TEXT REFERENCES derivative_indexes(id),
      superseded_by_index_id TEXT REFERENCES derivative_indexes(id),
      failure_reason TEXT,
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL,
      started_at TIMESTAMPTZ,
      finished_at TIMESTAMPTZ,
      cancel_requested_by TEXT REFERENCES users(id),
      cancel_requested_at TIMESTAMPTZ,
      canceled_by TEXT REFERENCES users(id),
      canceled_at TIMESTAMPTZ,
      activated_by TEXT REFERENCES users(id),
      activated_at TIMESTAMPTZ,
      UNIQUE (project_id, version)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_derivative_indexes_project_created
      ON derivative_indexes(project_id, created_at DESC, id DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_derivative_indexes_project_dedupe
      ON derivative_indexes(project_id, rebuild_dedupe_key, version DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS search_documents (
      id TEXT PRIMARY KEY,
      search_index_id TEXT NOT NULL REFERENCES search_indexes(id) ON DELETE CASCADE,
      document_id TEXT NOT NULL,
      run_id TEXT NOT NULL,
      page_id TEXT NOT NULL,
      line_id TEXT,
      token_id TEXT,
      source_kind TEXT NOT NULL CHECK (
        source_kind IN ('LINE', 'RESCUE_CANDIDATE', 'PAGE_WINDOW')
      ),
      source_ref_id TEXT NOT NULL,
      page_number INTEGER NOT NULL,
      match_span_json JSONB,
      token_geometry_json JSONB,
      search_text TEXT NOT NULL,
      search_metadata_json JSONB NOT NULL,
      created_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_search_documents_index_page
      ON search_documents(search_index_id, page_number, id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_search_documents_index_doc_run_page
      ON search_documents(search_index_id, document_id, run_id, page_number, id)
    """,
    """
    DO $$
    BEGIN
      BEGIN
        CREATE EXTENSION IF NOT EXISTS pg_trgm;
      EXCEPTION
        WHEN insufficient_privilege THEN
          NULL;
      END;
    END
    $$;
    """,
    """
    DO $$
    BEGIN
      IF EXISTS (
        SELECT 1
        FROM pg_extension
        WHERE extname = 'pg_trgm'
      ) THEN
        EXECUTE
          'CREATE INDEX IF NOT EXISTS idx_search_documents_text_trgm '
          || 'ON search_documents USING GIN (search_text gin_trgm_ops)';
      END IF;
    END
    $$;
    """,
    """
    CREATE TABLE IF NOT EXISTS search_query_texts (
      key TEXT PRIMARY KEY,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      query_text TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_search_query_texts_project_created
      ON search_query_texts(project_id, created_at DESC, key DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS search_query_audits (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      actor_user_id TEXT NOT NULL REFERENCES users(id),
      search_index_id TEXT NOT NULL REFERENCES search_indexes(id) ON DELETE CASCADE,
      query_sha256 TEXT NOT NULL,
      query_text_key TEXT NOT NULL REFERENCES search_query_texts(key),
      filters_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      result_count INTEGER NOT NULL,
      created_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_search_query_audits_project_created
      ON search_query_audits(project_id, created_at DESC, id DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_search_query_audits_project_sha_created
      ON search_query_audits(project_id, query_sha256, created_at DESC, id DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS controlled_entities (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      entity_index_id TEXT NOT NULL REFERENCES entity_indexes(id) ON DELETE CASCADE,
      entity_type TEXT NOT NULL CHECK (
        entity_type IN ('PERSON', 'PLACE', 'ORGANISATION', 'DATE')
      ),
      display_value TEXT NOT NULL,
      canonical_value TEXT NOT NULL,
      confidence_summary_json JSONB NOT NULL,
      created_at TIMESTAMPTZ NOT NULL,
      UNIQUE (entity_index_id, entity_type, canonical_value)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_controlled_entities_index_type_value
      ON controlled_entities(entity_index_id, entity_type, canonical_value, id)
    """,
    """
    CREATE TABLE IF NOT EXISTS entity_occurrences (
      id TEXT PRIMARY KEY,
      entity_index_id TEXT NOT NULL REFERENCES entity_indexes(id) ON DELETE CASCADE,
      entity_id TEXT NOT NULL REFERENCES controlled_entities(id) ON DELETE CASCADE,
      document_id TEXT NOT NULL,
      run_id TEXT NOT NULL,
      page_id TEXT NOT NULL,
      line_id TEXT,
      token_id TEXT,
      source_kind TEXT NOT NULL CHECK (
        source_kind IN ('LINE', 'RESCUE_CANDIDATE', 'PAGE_WINDOW')
      ),
      source_ref_id TEXT NOT NULL,
      page_number INTEGER NOT NULL,
      confidence DOUBLE PRECISION NOT NULL,
      occurrence_span_json JSONB,
      occurrence_span_basis_kind TEXT NOT NULL CHECK (
        occurrence_span_basis_kind IN ('LINE_TEXT', 'PAGE_WINDOW_TEXT', 'NONE')
      ),
      occurrence_span_basis_ref TEXT,
      token_geometry_json JSONB,
      created_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_entity_occurrences_index_entity_page
      ON entity_occurrences(entity_index_id, entity_id, page_number, id)
    """,
    """
    CREATE TABLE IF NOT EXISTS derivative_snapshots (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      derivative_index_id TEXT NOT NULL REFERENCES derivative_indexes(id) ON DELETE CASCADE,
      derivative_kind TEXT NOT NULL,
      source_snapshot_json JSONB NOT NULL,
      policy_version_ref TEXT NOT NULL,
      status TEXT NOT NULL CHECK (
        status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED')
      ),
      supersedes_derivative_snapshot_id TEXT REFERENCES derivative_snapshots(id),
      superseded_by_derivative_snapshot_id TEXT REFERENCES derivative_snapshots(id),
      storage_key TEXT,
      snapshot_sha256 TEXT,
      candidate_snapshot_id TEXT,
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL,
      started_at TIMESTAMPTZ,
      finished_at TIMESTAMPTZ,
      failure_reason TEXT
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_derivative_snapshots_index_created
      ON derivative_snapshots(derivative_index_id, created_at DESC, id DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_derivative_snapshots_project_scope
      ON derivative_snapshots(project_id, status, superseded_by_derivative_snapshot_id, created_at DESC, id DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS derivative_index_rows (
      id TEXT PRIMARY KEY,
      derivative_index_id TEXT NOT NULL REFERENCES derivative_indexes(id) ON DELETE CASCADE,
      derivative_snapshot_id TEXT NOT NULL,
      derivative_kind TEXT NOT NULL,
      source_snapshot_json JSONB NOT NULL,
      display_payload_json JSONB NOT NULL,
      suppressed_fields_json JSONB NOT NULL,
      created_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_derivative_index_rows_index_created
      ON derivative_index_rows(derivative_index_id, created_at DESC, id DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_derivative_index_rows_snapshot_created
      ON derivative_index_rows(derivative_snapshot_id, derivative_index_id, created_at DESC, id DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS project_index_projections (
      project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
      active_search_index_id TEXT REFERENCES search_indexes(id),
      active_entity_index_id TEXT REFERENCES entity_indexes(id),
      active_derivative_index_id TEXT REFERENCES derivative_indexes(id),
      updated_at TIMESTAMPTZ NOT NULL
    )
    """,
)

_TABLE_BY_KIND: dict[IndexKind, str] = {
    "SEARCH": "search_indexes",
    "ENTITY": "entity_indexes",
    "DERIVATIVE": "derivative_indexes",
}


class IndexStoreUnavailableError(RuntimeError):
    """Index persistence could not be reached."""


class IndexStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._project_store = ProjectStore(settings)
        self._schema_initialized = False

    @staticmethod
    def _as_conninfo(database_url: str) -> str:
        if database_url.startswith("postgresql+psycopg://"):
            return database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        return database_url

    def _connect(self) -> psycopg.Connection:
        conninfo = self._as_conninfo(self._settings.database_url)
        return psycopg.connect(conninfo=conninfo, connect_timeout=2)

    @staticmethod
    def utcnow() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _as_index(kind: IndexKind, row: dict[str, object]) -> IndexRecord:
        source_snapshot_json = row.get("source_snapshot_json")
        build_parameters_json = row.get("build_parameters_json")
        return IndexRecord(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            kind=kind,
            version=int(row["version"]),
            source_snapshot_json=(
                dict(source_snapshot_json)
                if isinstance(source_snapshot_json, dict)
                else {}
            ),
            source_snapshot_sha256=str(row["source_snapshot_sha256"]),
            build_parameters_json=(
                dict(build_parameters_json)
                if isinstance(build_parameters_json, dict)
                else {}
            ),
            rebuild_dedupe_key=str(row["rebuild_dedupe_key"]),
            status=str(row["status"]),  # type: ignore[arg-type]
            supersedes_index_id=(
                str(row["supersedes_index_id"])
                if isinstance(row.get("supersedes_index_id"), str)
                else None
            ),
            superseded_by_index_id=(
                str(row["superseded_by_index_id"])
                if isinstance(row.get("superseded_by_index_id"), str)
                else None
            ),
            failure_reason=(
                str(row["failure_reason"])
                if isinstance(row.get("failure_reason"), str)
                else None
            ),
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
            started_at=row.get("started_at"),  # type: ignore[arg-type]
            finished_at=row.get("finished_at"),  # type: ignore[arg-type]
            cancel_requested_by=(
                str(row["cancel_requested_by"])
                if isinstance(row.get("cancel_requested_by"), str)
                else None
            ),
            cancel_requested_at=row.get("cancel_requested_at"),  # type: ignore[arg-type]
            canceled_by=(
                str(row["canceled_by"]) if isinstance(row.get("canceled_by"), str) else None
            ),
            canceled_at=row.get("canceled_at"),  # type: ignore[arg-type]
            activated_by=(
                str(row["activated_by"]) if isinstance(row.get("activated_by"), str) else None
            ),
            activated_at=row.get("activated_at"),  # type: ignore[arg-type]
        )

    @staticmethod
    def _as_projection(row: dict[str, object]) -> ProjectIndexProjectionRecord:
        return ProjectIndexProjectionRecord(
            project_id=str(row["project_id"]),
            active_search_index_id=(
                str(row["active_search_index_id"])
                if isinstance(row.get("active_search_index_id"), str)
                else None
            ),
            active_entity_index_id=(
                str(row["active_entity_index_id"])
                if isinstance(row.get("active_entity_index_id"), str)
                else None
            ),
            active_derivative_index_id=(
                str(row["active_derivative_index_id"])
                if isinstance(row.get("active_derivative_index_id"), str)
                else None
            ),
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @staticmethod
    def _as_search_document(row: dict[str, object]) -> SearchDocumentRecord:
        match_span_json = row.get("match_span_json")
        token_geometry_json = row.get("token_geometry_json")
        search_metadata_json = row.get("search_metadata_json")
        return SearchDocumentRecord(
            id=str(row["id"]),
            search_index_id=str(row["search_index_id"]),
            document_id=str(row["document_id"]),
            run_id=str(row["run_id"]),
            page_id=str(row["page_id"]),
            line_id=str(row["line_id"]) if isinstance(row.get("line_id"), str) else None,
            token_id=str(row["token_id"]) if isinstance(row.get("token_id"), str) else None,
            source_kind=str(row["source_kind"]),  # type: ignore[arg-type]
            source_ref_id=str(row["source_ref_id"]),
            page_number=int(row["page_number"]),
            match_span_json=(
                dict(match_span_json) if isinstance(match_span_json, dict) else None
            ),
            token_geometry_json=(
                dict(token_geometry_json)
                if isinstance(token_geometry_json, dict)
                else None
            ),
            search_text=str(row["search_text"]),
            search_metadata_json=(
                dict(search_metadata_json)
                if isinstance(search_metadata_json, dict)
                else {}
            ),
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @staticmethod
    def _as_search_query_audit(row: dict[str, object]) -> SearchQueryAuditRecord:
        filters_json = row.get("filters_json")
        result_count = row.get("result_count")
        return SearchQueryAuditRecord(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            actor_user_id=str(row["actor_user_id"]),
            search_index_id=str(row["search_index_id"]),
            query_sha256=str(row["query_sha256"]),
            query_text_key=str(row["query_text_key"]),
            filters_json=dict(filters_json) if isinstance(filters_json, dict) else {},
            result_count=int(result_count) if isinstance(result_count, int) else 0,
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @staticmethod
    def _as_controlled_entity(row: dict[str, object]) -> ControlledEntityRecord:
        confidence_summary_json = row.get("confidence_summary_json")
        occurrence_count = row.get("occurrence_count")
        return ControlledEntityRecord(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            entity_index_id=str(row["entity_index_id"]),
            entity_type=str(row["entity_type"]),  # type: ignore[arg-type]
            display_value=str(row["display_value"]),
            canonical_value=str(row["canonical_value"]),
            confidence_summary_json=(
                dict(confidence_summary_json)
                if isinstance(confidence_summary_json, dict)
                else {}
            ),
            occurrence_count=(
                int(occurrence_count)
                if isinstance(occurrence_count, int)
                else 0
            ),
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @staticmethod
    def _as_entity_occurrence(row: dict[str, object]) -> EntityOccurrenceRecord:
        occurrence_span_json = row.get("occurrence_span_json")
        token_geometry_json = row.get("token_geometry_json")
        return EntityOccurrenceRecord(
            id=str(row["id"]),
            entity_index_id=str(row["entity_index_id"]),
            entity_id=str(row["entity_id"]),
            document_id=str(row["document_id"]),
            run_id=str(row["run_id"]),
            page_id=str(row["page_id"]),
            line_id=str(row["line_id"]) if isinstance(row.get("line_id"), str) else None,
            token_id=str(row["token_id"]) if isinstance(row.get("token_id"), str) else None,
            source_kind=str(row["source_kind"]),  # type: ignore[arg-type]
            source_ref_id=str(row["source_ref_id"]),
            page_number=int(row["page_number"]),
            confidence=float(row["confidence"]),
            occurrence_span_json=(
                dict(occurrence_span_json)
                if isinstance(occurrence_span_json, dict)
                else None
            ),
            occurrence_span_basis_kind=str(
                row["occurrence_span_basis_kind"]
            ),  # type: ignore[arg-type]
            occurrence_span_basis_ref=(
                str(row["occurrence_span_basis_ref"])
                if isinstance(row.get("occurrence_span_basis_ref"), str)
                else None
            ),
            token_geometry_json=(
                dict(token_geometry_json)
                if isinstance(token_geometry_json, dict)
                else None
            ),
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @staticmethod
    def _as_derivative_snapshot(row: dict[str, object]) -> DerivativeSnapshotRecord:
        source_snapshot_json = row.get("source_snapshot_json")
        return DerivativeSnapshotRecord(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            derivative_index_id=str(row["derivative_index_id"]),
            derivative_kind=str(row["derivative_kind"]),
            source_snapshot_json=(
                dict(source_snapshot_json)
                if isinstance(source_snapshot_json, dict)
                else {}
            ),
            policy_version_ref=str(row["policy_version_ref"]),
            status=str(row["status"]),  # type: ignore[arg-type]
            supersedes_derivative_snapshot_id=(
                str(row["supersedes_derivative_snapshot_id"])
                if isinstance(row.get("supersedes_derivative_snapshot_id"), str)
                else None
            ),
            superseded_by_derivative_snapshot_id=(
                str(row["superseded_by_derivative_snapshot_id"])
                if isinstance(row.get("superseded_by_derivative_snapshot_id"), str)
                else None
            ),
            storage_key=(
                str(row["storage_key"])
                if isinstance(row.get("storage_key"), str)
                else None
            ),
            snapshot_sha256=(
                str(row["snapshot_sha256"])
                if isinstance(row.get("snapshot_sha256"), str)
                else None
            ),
            candidate_snapshot_id=(
                str(row["candidate_snapshot_id"])
                if isinstance(row.get("candidate_snapshot_id"), str)
                else None
            ),
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
            started_at=row.get("started_at"),  # type: ignore[arg-type]
            finished_at=row.get("finished_at"),  # type: ignore[arg-type]
            failure_reason=(
                str(row["failure_reason"])
                if isinstance(row.get("failure_reason"), str)
                else None
            ),
        )

    @staticmethod
    def _as_derivative_row(row: dict[str, object]) -> DerivativeIndexRowRecord:
        source_snapshot_json = row.get("source_snapshot_json")
        display_payload_json = row.get("display_payload_json")
        suppressed_fields_json = row.get("suppressed_fields_json")
        return DerivativeIndexRowRecord(
            id=str(row["id"]),
            derivative_index_id=str(row["derivative_index_id"]),
            derivative_snapshot_id=str(row["derivative_snapshot_id"]),
            derivative_kind=str(row["derivative_kind"]),
            source_snapshot_json=(
                dict(source_snapshot_json)
                if isinstance(source_snapshot_json, dict)
                else {}
            ),
            display_payload_json=(
                dict(display_payload_json)
                if isinstance(display_payload_json, dict)
                else {}
            ),
            suppressed_fields_json=(
                dict(suppressed_fields_json)
                if isinstance(suppressed_fields_json, dict)
                else {}
            ),
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    def ensure_schema(self) -> None:
        if self._schema_initialized:
            return

        try:
            self._project_store.ensure_schema()
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    for statement in INDEX_SCHEMA_STATEMENTS:
                        cursor.execute(statement)
                connection.commit()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Index schema could not be initialized.") from error

        self._schema_initialized = True

    @staticmethod
    def _table_for(kind: IndexKind) -> str:
        return _TABLE_BY_KIND[kind]

    def list_indexes(
        self,
        *,
        project_id: str,
        kind: IndexKind,
    ) -> list[IndexRecord]:
        self.ensure_schema()
        table = self._table_for(kind)
        sql = f"""
            SELECT
              id,
              project_id,
              version,
              source_snapshot_json,
              source_snapshot_sha256,
              build_parameters_json,
              rebuild_dedupe_key,
              status,
              supersedes_index_id,
              superseded_by_index_id,
              failure_reason,
              created_by,
              created_at,
              started_at,
              finished_at,
              cancel_requested_by,
              cancel_requested_at,
              canceled_by,
              canceled_at,
              activated_by,
              activated_at
            FROM {table}
            WHERE project_id = %(project_id)s
            ORDER BY version DESC, created_at DESC, id DESC
        """

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(sql, {"project_id": project_id})
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Index listing failed.") from error

        return [self._as_index(kind, row) for row in rows]

    def get_index(
        self,
        *,
        project_id: str,
        kind: IndexKind,
        index_id: str,
    ) -> IndexRecord | None:
        self.ensure_schema()
        table = self._table_for(kind)
        sql = f"""
            SELECT
              id,
              project_id,
              version,
              source_snapshot_json,
              source_snapshot_sha256,
              build_parameters_json,
              rebuild_dedupe_key,
              status,
              supersedes_index_id,
              superseded_by_index_id,
              failure_reason,
              created_by,
              created_at,
              started_at,
              finished_at,
              cancel_requested_by,
              cancel_requested_at,
              canceled_by,
              canceled_at,
              activated_by,
              activated_at
            FROM {table}
            WHERE project_id = %(project_id)s
              AND id = %(index_id)s
        """
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        sql,
                        {
                            "project_id": project_id,
                            "index_id": index_id,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Index lookup failed.") from error

        if row is None:
            return None
        return self._as_index(kind, row)

    def get_index_by_id(
        self,
        *,
        kind: IndexKind,
        index_id: str,
    ) -> IndexRecord | None:
        self.ensure_schema()
        table = self._table_for(kind)
        sql = f"""
            SELECT
              id,
              project_id,
              version,
              source_snapshot_json,
              source_snapshot_sha256,
              build_parameters_json,
              rebuild_dedupe_key,
              status,
              supersedes_index_id,
              superseded_by_index_id,
              failure_reason,
              created_by,
              created_at,
              started_at,
              finished_at,
              cancel_requested_by,
              cancel_requested_at,
              canceled_by,
              canceled_at,
              activated_by,
              activated_at
            FROM {table}
            WHERE id = %(index_id)s
        """
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(sql, {"index_id": index_id})
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Index lookup failed.") from error

        if row is None:
            return None
        return self._as_index(kind, row)

    def find_equivalent_index(
        self,
        *,
        project_id: str,
        kind: IndexKind,
        rebuild_dedupe_key: str,
    ) -> IndexRecord | None:
        self.ensure_schema()
        table = self._table_for(kind)
        sql = f"""
            SELECT
              id,
              project_id,
              version,
              source_snapshot_json,
              source_snapshot_sha256,
              build_parameters_json,
              rebuild_dedupe_key,
              status,
              supersedes_index_id,
              superseded_by_index_id,
              failure_reason,
              created_by,
              created_at,
              started_at,
              finished_at,
              cancel_requested_by,
              cancel_requested_at,
              canceled_by,
              canceled_at,
              activated_by,
              activated_at
            FROM {table}
            WHERE project_id = %(project_id)s
              AND rebuild_dedupe_key = %(rebuild_dedupe_key)s
              AND status IN ('QUEUED', 'RUNNING', 'SUCCEEDED')
            ORDER BY version DESC, created_at DESC, id DESC
            LIMIT 1
        """
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        sql,
                        {
                            "project_id": project_id,
                            "rebuild_dedupe_key": rebuild_dedupe_key,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Index dedupe lookup failed.") from error

        if row is None:
            return None
        return self._as_index(kind, row)

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
        self.ensure_schema()
        table = self._table_for(kind)

        insert_sql = f"""
            INSERT INTO {table} (
              id,
              project_id,
              version,
              source_snapshot_json,
              source_snapshot_sha256,
              build_parameters_json,
              rebuild_dedupe_key,
              status,
              supersedes_index_id,
              superseded_by_index_id,
              failure_reason,
              created_by,
              created_at,
              started_at,
              finished_at,
              cancel_requested_by,
              cancel_requested_at,
              canceled_by,
              canceled_at,
              activated_by,
              activated_at
            )
            VALUES (
              %(id)s,
              %(project_id)s,
              %(version)s,
              %(source_snapshot_json)s,
              %(source_snapshot_sha256)s,
              %(build_parameters_json)s,
              %(rebuild_dedupe_key)s,
              'QUEUED',
              %(supersedes_index_id)s,
              NULL,
              NULL,
              %(created_by)s,
              %(created_at)s,
              NULL,
              NULL,
              NULL,
              NULL,
              NULL,
              NULL,
              NULL,
              NULL
            )
            RETURNING
              id,
              project_id,
              version,
              source_snapshot_json,
              source_snapshot_sha256,
              build_parameters_json,
              rebuild_dedupe_key,
              status,
              supersedes_index_id,
              superseded_by_index_id,
              failure_reason,
              created_by,
              created_at,
              started_at,
              finished_at,
              cancel_requested_by,
              cancel_requested_at,
              canceled_by,
              canceled_at,
              activated_by,
              activated_at
        """
        next_version_sql = f"""
            SELECT COALESCE(MAX(version), 0) + 1 AS next_version
            FROM {table}
            WHERE project_id = %(project_id)s
        """
        supersede_sql = f"""
            UPDATE {table}
            SET superseded_by_index_id = %(next_index_id)s
            WHERE project_id = %(project_id)s
              AND id = %(supersedes_index_id)s
              AND superseded_by_index_id IS NULL
        """

        created_at = self.utcnow()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(next_version_sql, {"project_id": project_id})
                    next_version_row = cursor.fetchone()
                    if next_version_row is None:
                        next_version = 1
                    else:
                        next_version = int(next_version_row["next_version"])

                    cursor.execute(
                        insert_sql,
                        {
                            "id": index_id,
                            "project_id": project_id,
                            "version": next_version,
                            "source_snapshot_json": source_snapshot_json,
                            "source_snapshot_sha256": source_snapshot_sha256,
                            "build_parameters_json": build_parameters_json,
                            "rebuild_dedupe_key": rebuild_dedupe_key,
                            "supersedes_index_id": supersedes_index_id,
                            "created_by": created_by,
                            "created_at": created_at,
                        },
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise IndexStoreUnavailableError("Index insert returned no row.")

                    if isinstance(supersedes_index_id, str):
                        cursor.execute(
                            supersede_sql,
                            {
                                "project_id": project_id,
                                "supersedes_index_id": supersedes_index_id,
                                "next_index_id": index_id,
                            },
                        )

                connection.commit()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Index creation failed.") from error

        return self._as_index(kind, row)

    def mark_running(
        self,
        *,
        project_id: str,
        kind: IndexKind,
        index_id: str,
        started_at: datetime | None = None,
    ) -> IndexRecord | None:
        self.ensure_schema()
        table = self._table_for(kind)
        started = started_at or self.utcnow()
        sql = f"""
            UPDATE {table}
            SET status = 'RUNNING',
                started_at = COALESCE(started_at, %(started_at)s),
                failure_reason = NULL
            WHERE project_id = %(project_id)s
              AND id = %(index_id)s
              AND status = 'QUEUED'
            RETURNING
              id,
              project_id,
              version,
              source_snapshot_json,
              source_snapshot_sha256,
              build_parameters_json,
              rebuild_dedupe_key,
              status,
              supersedes_index_id,
              superseded_by_index_id,
              failure_reason,
              created_by,
              created_at,
              started_at,
              finished_at,
              cancel_requested_by,
              cancel_requested_at,
              canceled_by,
              canceled_at,
              activated_by,
              activated_at
        """
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        sql,
                        {
                            "project_id": project_id,
                            "index_id": index_id,
                            "started_at": started,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Index start transition failed.") from error

        if row is None:
            return None
        return self._as_index(kind, row)

    def mark_succeeded(
        self,
        *,
        project_id: str,
        kind: IndexKind,
        index_id: str,
        finished_at: datetime | None = None,
    ) -> IndexRecord | None:
        self.ensure_schema()
        table = self._table_for(kind)
        finished = finished_at or self.utcnow()
        sql = f"""
            UPDATE {table}
            SET status = 'SUCCEEDED',
                finished_at = %(finished_at)s,
                failure_reason = NULL
            WHERE project_id = %(project_id)s
              AND id = %(index_id)s
              AND status = 'RUNNING'
            RETURNING
              id,
              project_id,
              version,
              source_snapshot_json,
              source_snapshot_sha256,
              build_parameters_json,
              rebuild_dedupe_key,
              status,
              supersedes_index_id,
              superseded_by_index_id,
              failure_reason,
              created_by,
              created_at,
              started_at,
              finished_at,
              cancel_requested_by,
              cancel_requested_at,
              canceled_by,
              canceled_at,
              activated_by,
              activated_at
        """
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        sql,
                        {
                            "project_id": project_id,
                            "index_id": index_id,
                            "finished_at": finished,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Index success transition failed.") from error

        if row is None:
            return None
        return self._as_index(kind, row)

    def mark_failed(
        self,
        *,
        project_id: str,
        kind: IndexKind,
        index_id: str,
        failure_reason: str,
        finished_at: datetime | None = None,
    ) -> IndexRecord | None:
        self.ensure_schema()
        table = self._table_for(kind)
        finished = finished_at or self.utcnow()
        sql = f"""
            UPDATE {table}
            SET status = 'FAILED',
                failure_reason = %(failure_reason)s,
                finished_at = %(finished_at)s
            WHERE project_id = %(project_id)s
              AND id = %(index_id)s
              AND status = 'RUNNING'
            RETURNING
              id,
              project_id,
              version,
              source_snapshot_json,
              source_snapshot_sha256,
              build_parameters_json,
              rebuild_dedupe_key,
              status,
              supersedes_index_id,
              superseded_by_index_id,
              failure_reason,
              created_by,
              created_at,
              started_at,
              finished_at,
              cancel_requested_by,
              cancel_requested_at,
              canceled_by,
              canceled_at,
              activated_by,
              activated_at
        """
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        sql,
                        {
                            "project_id": project_id,
                            "index_id": index_id,
                            "failure_reason": failure_reason,
                            "finished_at": finished,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Index failed transition failed.") from error

        if row is None:
            return None
        return self._as_index(kind, row)

    def cancel_queued(
        self,
        *,
        project_id: str,
        kind: IndexKind,
        index_id: str,
        canceled_by: str,
        canceled_at: datetime | None = None,
    ) -> IndexRecord | None:
        self.ensure_schema()
        table = self._table_for(kind)
        canceled = canceled_at or self.utcnow()
        sql = f"""
            UPDATE {table}
            SET status = 'CANCELED',
                canceled_by = %(canceled_by)s,
                canceled_at = %(canceled_at)s,
                finished_at = %(canceled_at)s
            WHERE project_id = %(project_id)s
              AND id = %(index_id)s
              AND status = 'QUEUED'
            RETURNING
              id,
              project_id,
              version,
              source_snapshot_json,
              source_snapshot_sha256,
              build_parameters_json,
              rebuild_dedupe_key,
              status,
              supersedes_index_id,
              superseded_by_index_id,
              failure_reason,
              created_by,
              created_at,
              started_at,
              finished_at,
              cancel_requested_by,
              cancel_requested_at,
              canceled_by,
              canceled_at,
              activated_by,
              activated_at
        """
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        sql,
                        {
                            "project_id": project_id,
                            "index_id": index_id,
                            "canceled_by": canceled_by,
                            "canceled_at": canceled,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Index queued cancel failed.") from error

        if row is None:
            return None
        return self._as_index(kind, row)

    def request_running_cancel(
        self,
        *,
        project_id: str,
        kind: IndexKind,
        index_id: str,
        requested_by: str,
        requested_at: datetime | None = None,
    ) -> IndexRecord | None:
        self.ensure_schema()
        table = self._table_for(kind)
        requested = requested_at or self.utcnow()
        sql = f"""
            UPDATE {table}
            SET cancel_requested_by = COALESCE(cancel_requested_by, %(requested_by)s),
                cancel_requested_at = COALESCE(cancel_requested_at, %(requested_at)s)
            WHERE project_id = %(project_id)s
              AND id = %(index_id)s
              AND status = 'RUNNING'
            RETURNING
              id,
              project_id,
              version,
              source_snapshot_json,
              source_snapshot_sha256,
              build_parameters_json,
              rebuild_dedupe_key,
              status,
              supersedes_index_id,
              superseded_by_index_id,
              failure_reason,
              created_by,
              created_at,
              started_at,
              finished_at,
              cancel_requested_by,
              cancel_requested_at,
              canceled_by,
              canceled_at,
              activated_by,
              activated_at
        """
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        sql,
                        {
                            "project_id": project_id,
                            "index_id": index_id,
                            "requested_by": requested_by,
                            "requested_at": requested,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Index running cancel request failed.") from error

        if row is None:
            return None
        return self._as_index(kind, row)

    def cancel_running(
        self,
        *,
        project_id: str,
        kind: IndexKind,
        index_id: str,
        canceled_by: str,
        canceled_at: datetime | None = None,
    ) -> IndexRecord | None:
        self.ensure_schema()
        table = self._table_for(kind)
        canceled = canceled_at or self.utcnow()
        sql = f"""
            UPDATE {table}
            SET status = 'CANCELED',
                canceled_by = %(canceled_by)s,
                canceled_at = %(canceled_at)s,
                finished_at = %(canceled_at)s
            WHERE project_id = %(project_id)s
              AND id = %(index_id)s
              AND status = 'RUNNING'
            RETURNING
              id,
              project_id,
              version,
              source_snapshot_json,
              source_snapshot_sha256,
              build_parameters_json,
              rebuild_dedupe_key,
              status,
              supersedes_index_id,
              superseded_by_index_id,
              failure_reason,
              created_by,
              created_at,
              started_at,
              finished_at,
              cancel_requested_by,
              cancel_requested_at,
              canceled_by,
              canceled_at,
              activated_by,
              activated_at
        """
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        sql,
                        {
                            "project_id": project_id,
                            "index_id": index_id,
                            "canceled_by": canceled_by,
                            "canceled_at": canceled,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Index running cancel failed.") from error

        if row is None:
            return None
        return self._as_index(kind, row)

    def set_activation_metadata(
        self,
        *,
        project_id: str,
        kind: IndexKind,
        index_id: str,
        activated_by: str,
        activated_at: datetime | None = None,
    ) -> IndexRecord | None:
        self.ensure_schema()
        table = self._table_for(kind)
        activated = activated_at or self.utcnow()
        sql = f"""
            UPDATE {table}
            SET activated_by = %(activated_by)s,
                activated_at = %(activated_at)s
            WHERE project_id = %(project_id)s
              AND id = %(index_id)s
            RETURNING
              id,
              project_id,
              version,
              source_snapshot_json,
              source_snapshot_sha256,
              build_parameters_json,
              rebuild_dedupe_key,
              status,
              supersedes_index_id,
              superseded_by_index_id,
              failure_reason,
              created_by,
              created_at,
              started_at,
              finished_at,
              cancel_requested_by,
              cancel_requested_at,
              canceled_by,
              canceled_at,
              activated_by,
              activated_at
        """
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        sql,
                        {
                            "project_id": project_id,
                            "index_id": index_id,
                            "activated_by": activated_by,
                            "activated_at": activated,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Index activation metadata update failed.") from error

        if row is None:
            return None
        return self._as_index(kind, row)

    def get_projection(
        self,
        *,
        project_id: str,
    ) -> ProjectIndexProjectionRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          project_id,
                          active_search_index_id,
                          active_entity_index_id,
                          active_derivative_index_id,
                          updated_at
                        FROM project_index_projections
                        WHERE project_id = %(project_id)s
                        """,
                        {"project_id": project_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Active index projection lookup failed.") from error

        if row is None:
            return None
        return self._as_projection(row)

    def upsert_projection(
        self,
        *,
        project_id: str,
        active_search_index_id: str | None,
        active_entity_index_id: str | None,
        active_derivative_index_id: str | None,
        updated_at: datetime | None = None,
    ) -> ProjectIndexProjectionRecord:
        self.ensure_schema()
        projection_updated_at = updated_at or self.utcnow()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO project_index_projections (
                          project_id,
                          active_search_index_id,
                          active_entity_index_id,
                          active_derivative_index_id,
                          updated_at
                        )
                        VALUES (
                          %(project_id)s,
                          %(active_search_index_id)s,
                          %(active_entity_index_id)s,
                          %(active_derivative_index_id)s,
                          %(updated_at)s
                        )
                        ON CONFLICT (project_id)
                        DO UPDATE SET
                          active_search_index_id = EXCLUDED.active_search_index_id,
                          active_entity_index_id = EXCLUDED.active_entity_index_id,
                          active_derivative_index_id = EXCLUDED.active_derivative_index_id,
                          updated_at = EXCLUDED.updated_at
                        RETURNING
                          project_id,
                          active_search_index_id,
                          active_entity_index_id,
                          active_derivative_index_id,
                          updated_at
                        """,
                        {
                            "project_id": project_id,
                            "active_search_index_id": active_search_index_id,
                            "active_entity_index_id": active_entity_index_id,
                            "active_derivative_index_id": active_derivative_index_id,
                            "updated_at": projection_updated_at,
                        },
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise IndexStoreUnavailableError("Projection upsert returned no row.")
                connection.commit()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Active index projection update failed.") from error

        return self._as_projection(row)

    def append_search_documents(
        self,
        *,
        project_id: str,
        search_index_id: str,
        items: list[CreateSearchDocumentInput],
    ) -> int:
        self.ensure_schema()
        if len(items) == 0:
            return 0
        search_index = self.get_index(
            project_id=project_id,
            kind="SEARCH",
            index_id=search_index_id,
        )
        if search_index is None:
            raise IndexStoreUnavailableError("Search index generation does not exist.")
        created_at = self.utcnow()
        sql = """
            INSERT INTO search_documents (
              id,
              search_index_id,
              document_id,
              run_id,
              page_id,
              line_id,
              token_id,
              source_kind,
              source_ref_id,
              page_number,
              match_span_json,
              token_geometry_json,
              search_text,
              search_metadata_json,
              created_at
            )
            VALUES (
              %(id)s,
              %(search_index_id)s,
              %(document_id)s,
              %(run_id)s,
              %(page_id)s,
              %(line_id)s,
              %(token_id)s,
              %(source_kind)s,
              %(source_ref_id)s,
              %(page_number)s,
              %(match_span_json)s,
              %(token_geometry_json)s,
              %(search_text)s,
              %(search_metadata_json)s,
              %(created_at)s
            )
        """
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    for item in items:
                        cursor.execute(
                            sql,
                            {
                                "id": f"searchdoc-{uuid4()}",
                                "search_index_id": search_index_id,
                                "document_id": item.document_id,
                                "run_id": item.run_id,
                                "page_id": item.page_id,
                                "line_id": item.line_id,
                                "token_id": item.token_id,
                                "source_kind": item.source_kind,
                                "source_ref_id": item.source_ref_id,
                                "page_number": item.page_number,
                                "match_span_json": item.match_span_json,
                                "token_geometry_json": item.token_geometry_json,
                                "search_text": item.search_text,
                                "search_metadata_json": item.search_metadata_json,
                                "created_at": created_at,
                            },
                        )
                connection.commit()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Search document append failed.") from error
        return len(items)

    def clear_entity_index_rows(
        self,
        *,
        project_id: str,
        entity_index_id: str,
    ) -> None:
        self.ensure_schema()
        index = self.get_index(
            project_id=project_id,
            kind="ENTITY",
            index_id=entity_index_id,
        )
        if index is None:
            raise IndexStoreUnavailableError("Entity index generation does not exist.")

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        DELETE FROM entity_occurrences
                        WHERE entity_index_id = %(entity_index_id)s
                        """,
                        {"entity_index_id": entity_index_id},
                    )
                    cursor.execute(
                        """
                        DELETE FROM controlled_entities
                        WHERE project_id = %(project_id)s
                          AND entity_index_id = %(entity_index_id)s
                        """,
                        {
                            "project_id": project_id,
                            "entity_index_id": entity_index_id,
                        },
                    )
                connection.commit()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Entity index row clear failed.") from error

    def append_controlled_entities(
        self,
        *,
        project_id: str,
        entity_index_id: str,
        items: list[CreateControlledEntityInput],
    ) -> int:
        self.ensure_schema()
        if len(items) == 0:
            return 0
        index = self.get_index(
            project_id=project_id,
            kind="ENTITY",
            index_id=entity_index_id,
        )
        if index is None:
            raise IndexStoreUnavailableError("Entity index generation does not exist.")

        created_at = self.utcnow()
        sql = """
            INSERT INTO controlled_entities (
              id,
              project_id,
              entity_index_id,
              entity_type,
              display_value,
              canonical_value,
              confidence_summary_json,
              created_at
            )
            VALUES (
              %(id)s,
              %(project_id)s,
              %(entity_index_id)s,
              %(entity_type)s,
              %(display_value)s,
              %(canonical_value)s,
              %(confidence_summary_json)s,
              %(created_at)s
            )
        """
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    for item in items:
                        cursor.execute(
                            sql,
                            {
                                "id": item.id,
                                "project_id": project_id,
                                "entity_index_id": entity_index_id,
                                "entity_type": item.entity_type,
                                "display_value": item.display_value,
                                "canonical_value": item.canonical_value,
                                "confidence_summary_json": item.confidence_summary_json,
                                "created_at": created_at,
                            },
                        )
                connection.commit()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Controlled entity append failed.") from error
        return len(items)

    def append_entity_occurrences(
        self,
        *,
        project_id: str,
        entity_index_id: str,
        items: list[CreateEntityOccurrenceInput],
    ) -> int:
        self.ensure_schema()
        if len(items) == 0:
            return 0
        index = self.get_index(
            project_id=project_id,
            kind="ENTITY",
            index_id=entity_index_id,
        )
        if index is None:
            raise IndexStoreUnavailableError("Entity index generation does not exist.")

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT id
                        FROM controlled_entities
                        WHERE project_id = %(project_id)s
                          AND entity_index_id = %(entity_index_id)s
                        """,
                        {
                            "project_id": project_id,
                            "entity_index_id": entity_index_id,
                        },
                    )
                    valid_entity_ids = {
                        str(row["id"])
                        for row in cursor.fetchall()
                        if isinstance(row.get("id"), str)
                    }

                    created_at = self.utcnow()
                    sql = """
                        INSERT INTO entity_occurrences (
                          id,
                          entity_index_id,
                          entity_id,
                          document_id,
                          run_id,
                          page_id,
                          line_id,
                          token_id,
                          source_kind,
                          source_ref_id,
                          page_number,
                          confidence,
                          occurrence_span_json,
                          occurrence_span_basis_kind,
                          occurrence_span_basis_ref,
                          token_geometry_json,
                          created_at
                        )
                        VALUES (
                          %(id)s,
                          %(entity_index_id)s,
                          %(entity_id)s,
                          %(document_id)s,
                          %(run_id)s,
                          %(page_id)s,
                          %(line_id)s,
                          %(token_id)s,
                          %(source_kind)s,
                          %(source_ref_id)s,
                          %(page_number)s,
                          %(confidence)s,
                          %(occurrence_span_json)s,
                          %(occurrence_span_basis_kind)s,
                          %(occurrence_span_basis_ref)s,
                          %(token_geometry_json)s,
                          %(created_at)s
                        )
                    """
                    for item in items:
                        if item.entity_id not in valid_entity_ids:
                            raise IndexStoreUnavailableError(
                                "Entity occurrence references a missing controlled entity."
                            )
                        cursor.execute(
                            sql,
                            {
                                "id": item.id,
                                "entity_index_id": entity_index_id,
                                "entity_id": item.entity_id,
                                "document_id": item.document_id,
                                "run_id": item.run_id,
                                "page_id": item.page_id,
                                "line_id": item.line_id,
                                "token_id": item.token_id,
                                "source_kind": item.source_kind,
                                "source_ref_id": item.source_ref_id,
                                "page_number": item.page_number,
                                "confidence": item.confidence,
                                "occurrence_span_json": item.occurrence_span_json,
                                "occurrence_span_basis_kind": item.occurrence_span_basis_kind,
                                "occurrence_span_basis_ref": item.occurrence_span_basis_ref,
                                "token_geometry_json": item.token_geometry_json,
                                "created_at": created_at,
                            },
                        )
                connection.commit()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Entity occurrence append failed.") from error
        return len(items)

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
        self.ensure_schema()
        index = self.get_index(
            project_id=project_id,
            kind="DERIVATIVE",
            index_id=derivative_index_id,
        )
        if index is None:
            raise IndexStoreUnavailableError("Derivative index generation does not exist.")
        snapshot_created_at = created_at or self.utcnow()
        normalized_kind = derivative_kind.strip()
        if not normalized_kind:
            raise IndexStoreUnavailableError("derivative_kind is required.")
        normalized_policy_ref = policy_version_ref.strip()
        if not normalized_policy_ref:
            raise IndexStoreUnavailableError("policy_version_ref is required.")

        row: dict[str, object] | None = None
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    if supersedes_derivative_snapshot_id is not None:
                        cursor.execute(
                            """
                            SELECT id
                            FROM derivative_snapshots
                            WHERE project_id = %(project_id)s
                              AND id = %(supersedes_derivative_snapshot_id)s
                            """,
                            {
                                "project_id": project_id,
                                "supersedes_derivative_snapshot_id": (
                                    supersedes_derivative_snapshot_id
                                ),
                            },
                        )
                        superseded_row = cursor.fetchone()
                        if superseded_row is None:
                            raise IndexStoreUnavailableError(
                                "supersedes_derivative_snapshot_id does not exist in project scope."
                            )

                    cursor.execute(
                        """
                        INSERT INTO derivative_snapshots (
                          id,
                          project_id,
                          derivative_index_id,
                          derivative_kind,
                          source_snapshot_json,
                          policy_version_ref,
                          status,
                          supersedes_derivative_snapshot_id,
                          superseded_by_derivative_snapshot_id,
                          storage_key,
                          snapshot_sha256,
                          candidate_snapshot_id,
                          created_by,
                          created_at,
                          started_at,
                          finished_at,
                          failure_reason
                        )
                        VALUES (
                          %(id)s,
                          %(project_id)s,
                          %(derivative_index_id)s,
                          %(derivative_kind)s,
                          %(source_snapshot_json)s,
                          %(policy_version_ref)s,
                          %(status)s,
                          %(supersedes_derivative_snapshot_id)s,
                          NULL,
                          %(storage_key)s,
                          %(snapshot_sha256)s,
                          %(candidate_snapshot_id)s,
                          %(created_by)s,
                          %(created_at)s,
                          %(started_at)s,
                          %(finished_at)s,
                          %(failure_reason)s
                        )
                        RETURNING
                          id,
                          project_id,
                          derivative_index_id,
                          derivative_kind,
                          source_snapshot_json,
                          policy_version_ref,
                          status,
                          supersedes_derivative_snapshot_id,
                          superseded_by_derivative_snapshot_id,
                          storage_key,
                          snapshot_sha256,
                          candidate_snapshot_id,
                          created_by,
                          created_at,
                          started_at,
                          finished_at,
                          failure_reason
                        """,
                        {
                            "id": snapshot_id,
                            "project_id": project_id,
                            "derivative_index_id": derivative_index_id,
                            "derivative_kind": normalized_kind,
                            "source_snapshot_json": source_snapshot_json,
                            "policy_version_ref": normalized_policy_ref,
                            "status": status,
                            "supersedes_derivative_snapshot_id": (
                                supersedes_derivative_snapshot_id
                            ),
                            "storage_key": storage_key,
                            "snapshot_sha256": snapshot_sha256,
                            "candidate_snapshot_id": candidate_snapshot_id,
                            "created_by": created_by,
                            "created_at": snapshot_created_at,
                            "started_at": started_at,
                            "finished_at": finished_at,
                            "failure_reason": failure_reason,
                        },
                    )
                    row = cursor.fetchone()

                    if supersedes_derivative_snapshot_id is not None:
                        cursor.execute(
                            """
                            UPDATE derivative_snapshots
                            SET superseded_by_derivative_snapshot_id = %(snapshot_id)s
                            WHERE project_id = %(project_id)s
                              AND id = %(supersedes_derivative_snapshot_id)s
                              AND superseded_by_derivative_snapshot_id IS NULL
                            """,
                            {
                                "project_id": project_id,
                                "snapshot_id": snapshot_id,
                                "supersedes_derivative_snapshot_id": (
                                    supersedes_derivative_snapshot_id
                                ),
                            },
                        )
                connection.commit()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Derivative snapshot creation failed.") from error

        if row is None:
            raise IndexStoreUnavailableError("Derivative snapshot creation returned no row.")
        return self._as_derivative_snapshot(row)

    def get_derivative_snapshot(
        self,
        *,
        project_id: str,
        derivative_snapshot_id: str,
    ) -> DerivativeSnapshotRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          derivative_index_id,
                          derivative_kind,
                          source_snapshot_json,
                          policy_version_ref,
                          status,
                          supersedes_derivative_snapshot_id,
                          superseded_by_derivative_snapshot_id,
                          storage_key,
                          snapshot_sha256,
                          candidate_snapshot_id,
                          created_by,
                          created_at,
                          started_at,
                          finished_at,
                          failure_reason
                        FROM derivative_snapshots
                        WHERE project_id = %(project_id)s
                          AND id = %(derivative_snapshot_id)s
                        """,
                        {
                            "project_id": project_id,
                            "derivative_snapshot_id": derivative_snapshot_id,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Derivative snapshot lookup failed.") from error
        if row is None:
            return None
        return self._as_derivative_snapshot(row)

    def list_derivative_snapshots_for_index(
        self,
        *,
        project_id: str,
        derivative_index_id: str,
    ) -> list[DerivativeSnapshotRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          derivative_index_id,
                          derivative_kind,
                          source_snapshot_json,
                          policy_version_ref,
                          status,
                          supersedes_derivative_snapshot_id,
                          superseded_by_derivative_snapshot_id,
                          storage_key,
                          snapshot_sha256,
                          candidate_snapshot_id,
                          created_by,
                          created_at,
                          started_at,
                          finished_at,
                          failure_reason
                        FROM derivative_snapshots
                        WHERE project_id = %(project_id)s
                          AND derivative_index_id = %(derivative_index_id)s
                        ORDER BY created_at DESC, id DESC
                        """,
                        {
                            "project_id": project_id,
                            "derivative_index_id": derivative_index_id,
                        },
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Derivative snapshot listing failed.") from error
        return [self._as_derivative_snapshot(row) for row in rows]

    def list_unsuperseded_successful_derivative_snapshots(
        self,
        *,
        project_id: str,
    ) -> list[DerivativeSnapshotRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          derivative_index_id,
                          derivative_kind,
                          source_snapshot_json,
                          policy_version_ref,
                          status,
                          supersedes_derivative_snapshot_id,
                          superseded_by_derivative_snapshot_id,
                          storage_key,
                          snapshot_sha256,
                          candidate_snapshot_id,
                          created_by,
                          created_at,
                          started_at,
                          finished_at,
                          failure_reason
                        FROM derivative_snapshots
                        WHERE project_id = %(project_id)s
                          AND status = 'SUCCEEDED'
                          AND superseded_by_derivative_snapshot_id IS NULL
                        ORDER BY created_at DESC, id DESC
                        """,
                        {"project_id": project_id},
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError(
                "Historical derivative snapshot listing failed."
            ) from error
        return [self._as_derivative_snapshot(row) for row in rows]

    def set_derivative_snapshot_candidate_snapshot_id(
        self,
        *,
        project_id: str,
        derivative_snapshot_id: str,
        candidate_snapshot_id: str,
    ) -> DerivativeSnapshotRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE derivative_snapshots
                        SET candidate_snapshot_id = COALESCE(
                          candidate_snapshot_id,
                          %(candidate_snapshot_id)s
                        )
                        WHERE project_id = %(project_id)s
                          AND id = %(derivative_snapshot_id)s
                        RETURNING
                          id,
                          project_id,
                          derivative_index_id,
                          derivative_kind,
                          source_snapshot_json,
                          policy_version_ref,
                          status,
                          supersedes_derivative_snapshot_id,
                          superseded_by_derivative_snapshot_id,
                          storage_key,
                          snapshot_sha256,
                          candidate_snapshot_id,
                          created_by,
                          created_at,
                          started_at,
                          finished_at,
                          failure_reason
                        """,
                        {
                            "project_id": project_id,
                            "derivative_snapshot_id": derivative_snapshot_id,
                            "candidate_snapshot_id": candidate_snapshot_id,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError(
                "Derivative snapshot candidate linkage failed."
            ) from error
        if row is None:
            return None
        return self._as_derivative_snapshot(row)

    def append_derivative_index_rows(
        self,
        *,
        project_id: str,
        derivative_index_id: str,
        derivative_snapshot_id: str,
        items: list[CreateDerivativeIndexRowInput],
    ) -> int:
        self.ensure_schema()
        if len(items) == 0:
            return 0
        index = self.get_index(
            project_id=project_id,
            kind="DERIVATIVE",
            index_id=derivative_index_id,
        )
        if index is None:
            raise IndexStoreUnavailableError("Derivative index generation does not exist.")
        snapshot = self.get_derivative_snapshot(
            project_id=project_id,
            derivative_snapshot_id=derivative_snapshot_id,
        )
        if snapshot is None or snapshot.derivative_index_id != derivative_index_id:
            raise IndexStoreUnavailableError(
                "Derivative snapshot does not exist for the requested derivative index generation."
            )
        created_at = self.utcnow()
        sql = """
            INSERT INTO derivative_index_rows (
              id,
              derivative_index_id,
              derivative_snapshot_id,
              derivative_kind,
              source_snapshot_json,
              display_payload_json,
              suppressed_fields_json,
              created_at
            )
            VALUES (
              %(id)s,
              %(derivative_index_id)s,
              %(derivative_snapshot_id)s,
              %(derivative_kind)s,
              %(source_snapshot_json)s,
              %(display_payload_json)s,
              %(suppressed_fields_json)s,
              %(created_at)s
            )
        """
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    for item in items:
                        cursor.execute(
                            sql,
                            {
                                "id": f"derrow-{uuid4()}",
                                "derivative_index_id": derivative_index_id,
                                "derivative_snapshot_id": derivative_snapshot_id,
                                "derivative_kind": item.derivative_kind,
                                "source_snapshot_json": item.source_snapshot_json,
                                "display_payload_json": item.display_payload_json,
                                "suppressed_fields_json": item.suppressed_fields_json,
                                "created_at": created_at,
                            },
                        )
                connection.commit()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Derivative index row append failed.") from error
        return len(items)

    def list_derivative_rows_for_snapshot(
        self,
        *,
        derivative_index_id: str,
        derivative_snapshot_id: str,
        cursor: int,
        limit: int,
    ) -> DerivativeIndexRowPage:
        self.ensure_schema()
        window_limit = limit + 1
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_obj:
                    cursor_obj.execute(
                        """
                        SELECT
                          id,
                          derivative_index_id,
                          derivative_snapshot_id,
                          derivative_kind,
                          source_snapshot_json,
                          display_payload_json,
                          suppressed_fields_json,
                          created_at
                        FROM derivative_index_rows
                        WHERE derivative_index_id = %(derivative_index_id)s
                          AND derivative_snapshot_id = %(derivative_snapshot_id)s
                        ORDER BY created_at ASC, id ASC
                        OFFSET %(cursor)s
                        LIMIT %(window_limit)s
                        """,
                        {
                            "derivative_index_id": derivative_index_id,
                            "derivative_snapshot_id": derivative_snapshot_id,
                            "cursor": cursor,
                            "window_limit": window_limit,
                        },
                    )
                    rows = cursor_obj.fetchall()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Derivative preview query failed.") from error

        has_more = len(rows) > limit
        materialized = rows[:limit]
        items = [self._as_derivative_row(row) for row in materialized]
        next_cursor = (cursor + limit) if has_more else None
        return DerivativeIndexRowPage(items=items, next_cursor=next_cursor)

    def list_all_derivative_rows_for_snapshot(
        self,
        *,
        derivative_index_id: str,
        derivative_snapshot_id: str,
    ) -> list[DerivativeIndexRowRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          derivative_index_id,
                          derivative_snapshot_id,
                          derivative_kind,
                          source_snapshot_json,
                          display_payload_json,
                          suppressed_fields_json,
                          created_at
                        FROM derivative_index_rows
                        WHERE derivative_index_id = %(derivative_index_id)s
                          AND derivative_snapshot_id = %(derivative_snapshot_id)s
                        ORDER BY created_at ASC, id ASC
                        """,
                        {
                            "derivative_index_id": derivative_index_id,
                            "derivative_snapshot_id": derivative_snapshot_id,
                        },
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Derivative preview listing failed.") from error
        return [self._as_derivative_row(row) for row in rows]

    def list_all_derivative_rows_for_index(
        self,
        *,
        derivative_index_id: str,
    ) -> list[DerivativeIndexRowRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          derivative_index_id,
                          derivative_snapshot_id,
                          derivative_kind,
                          source_snapshot_json,
                          display_payload_json,
                          suppressed_fields_json,
                          created_at
                        FROM derivative_index_rows
                        WHERE derivative_index_id = %(derivative_index_id)s
                        ORDER BY created_at ASC, id ASC
                        """,
                        {"derivative_index_id": derivative_index_id},
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Derivative row listing failed.") from error
        return [self._as_derivative_row(row) for row in rows]

    def list_controlled_entities_for_index(
        self,
        *,
        entity_index_id: str,
        query_text: str | None,
        entity_type: str | None,
        cursor: int,
        limit: int,
    ) -> ControlledEntityPage:
        self.ensure_schema()
        normalized_query = query_text.strip() if isinstance(query_text, str) else ""
        query_like = f"%{normalized_query}%" if normalized_query else ""
        window_limit = limit + 1

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_obj:
                    cursor_obj.execute(
                        """
                        SELECT
                          ce.id,
                          ce.project_id,
                          ce.entity_index_id,
                          ce.entity_type,
                          ce.display_value,
                          ce.canonical_value,
                          ce.confidence_summary_json,
                          ce.created_at,
                          COALESCE(occ.occurrence_count, 0) AS occurrence_count
                        FROM controlled_entities AS ce
                        LEFT JOIN (
                          SELECT
                            entity_id,
                            COUNT(*)::int AS occurrence_count
                          FROM entity_occurrences
                          WHERE entity_index_id = %(entity_index_id)s
                          GROUP BY entity_id
                        ) AS occ
                          ON occ.entity_id = ce.id
                        WHERE ce.entity_index_id = %(entity_index_id)s
                          AND (
                            %(query_like)s = ''
                            OR ce.display_value ILIKE %(query_like)s
                            OR ce.canonical_value ILIKE %(query_like)s
                          )
                          AND (
                            %(entity_type)s IS NULL
                            OR ce.entity_type = %(entity_type)s
                          )
                        ORDER BY ce.entity_type ASC, ce.canonical_value ASC, ce.id ASC
                        OFFSET %(cursor)s
                        LIMIT %(window_limit)s
                        """,
                        {
                            "entity_index_id": entity_index_id,
                            "query_like": query_like,
                            "entity_type": entity_type,
                            "cursor": cursor,
                            "window_limit": window_limit,
                        },
                    )
                    rows = cursor_obj.fetchall()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Controlled entity query failed.") from error

        has_more = len(rows) > limit
        materialized = rows[:limit]
        items = [self._as_controlled_entity(row) for row in materialized]
        next_cursor = (cursor + limit) if has_more else None
        return ControlledEntityPage(items=items, next_cursor=next_cursor)

    def get_controlled_entity_for_index(
        self,
        *,
        entity_index_id: str,
        entity_id: str,
    ) -> ControlledEntityRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          ce.id,
                          ce.project_id,
                          ce.entity_index_id,
                          ce.entity_type,
                          ce.display_value,
                          ce.canonical_value,
                          ce.confidence_summary_json,
                          ce.created_at,
                          (
                            SELECT COUNT(*)::int
                            FROM entity_occurrences AS occ
                            WHERE occ.entity_index_id = ce.entity_index_id
                              AND occ.entity_id = ce.id
                          ) AS occurrence_count
                        FROM controlled_entities AS ce
                        WHERE ce.entity_index_id = %(entity_index_id)s
                          AND ce.id = %(entity_id)s
                        """,
                        {
                            "entity_index_id": entity_index_id,
                            "entity_id": entity_id,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Controlled entity lookup failed.") from error
        if row is None:
            return None
        return self._as_controlled_entity(row)

    def list_all_controlled_entities_for_index(
        self,
        *,
        entity_index_id: str,
    ) -> list[ControlledEntityRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          ce.id,
                          ce.project_id,
                          ce.entity_index_id,
                          ce.entity_type,
                          ce.display_value,
                          ce.canonical_value,
                          ce.confidence_summary_json,
                          ce.created_at,
                          (
                            SELECT COUNT(*)::int
                            FROM entity_occurrences AS occ
                            WHERE occ.entity_index_id = ce.entity_index_id
                              AND occ.entity_id = ce.id
                          ) AS occurrence_count
                        FROM controlled_entities AS ce
                        WHERE ce.entity_index_id = %(entity_index_id)s
                        ORDER BY ce.entity_type ASC, ce.canonical_value ASC, ce.id ASC
                        """,
                        {"entity_index_id": entity_index_id},
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Controlled entity listing failed.") from error
        return [self._as_controlled_entity(row) for row in rows]

    def list_entity_occurrences_for_index(
        self,
        *,
        entity_index_id: str,
        entity_id: str,
        cursor: int,
        limit: int,
    ) -> EntityOccurrencePage:
        self.ensure_schema()
        window_limit = limit + 1
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_obj:
                    cursor_obj.execute(
                        """
                        SELECT
                          id,
                          entity_index_id,
                          entity_id,
                          document_id,
                          run_id,
                          page_id,
                          line_id,
                          token_id,
                          source_kind,
                          source_ref_id,
                          page_number,
                          confidence,
                          occurrence_span_json,
                          occurrence_span_basis_kind,
                          occurrence_span_basis_ref,
                          token_geometry_json,
                          created_at
                        FROM entity_occurrences
                        WHERE entity_index_id = %(entity_index_id)s
                          AND entity_id = %(entity_id)s
                        ORDER BY page_number ASC, document_id ASC, run_id ASC, id ASC
                        OFFSET %(cursor)s
                        LIMIT %(window_limit)s
                        """,
                        {
                            "entity_index_id": entity_index_id,
                            "entity_id": entity_id,
                            "cursor": cursor,
                            "window_limit": window_limit,
                        },
                    )
                    rows = cursor_obj.fetchall()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Entity occurrence query failed.") from error

        has_more = len(rows) > limit
        materialized = rows[:limit]
        items = [self._as_entity_occurrence(row) for row in materialized]
        next_cursor = (cursor + limit) if has_more else None
        return EntityOccurrencePage(items=items, next_cursor=next_cursor)

    def list_all_entity_occurrences_for_index(
        self,
        *,
        entity_index_id: str,
    ) -> list[EntityOccurrenceRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          entity_index_id,
                          entity_id,
                          document_id,
                          run_id,
                          page_id,
                          line_id,
                          token_id,
                          source_kind,
                          source_ref_id,
                          page_number,
                          confidence,
                          occurrence_span_json,
                          occurrence_span_basis_kind,
                          occurrence_span_basis_ref,
                          token_geometry_json,
                          created_at
                        FROM entity_occurrences
                        WHERE entity_index_id = %(entity_index_id)s
                        ORDER BY page_number ASC, document_id ASC, run_id ASC, id ASC
                        """,
                        {"entity_index_id": entity_index_id},
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Entity occurrence listing failed.") from error
        return [self._as_entity_occurrence(row) for row in rows]

    def get_search_document_for_index(
        self,
        *,
        search_index_id: str,
        search_document_id: str,
    ) -> SearchDocumentRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          search_index_id,
                          document_id,
                          run_id,
                          page_id,
                          line_id,
                          token_id,
                          source_kind,
                          source_ref_id,
                          page_number,
                          match_span_json,
                          token_geometry_json,
                          search_text,
                          search_metadata_json,
                          created_at
                        FROM search_documents
                        WHERE search_index_id = %(search_index_id)s
                          AND id = %(search_document_id)s
                        """,
                        {
                            "search_index_id": search_index_id,
                            "search_document_id": search_document_id,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Search document lookup failed.") from error
        if row is None:
            return None
        return self._as_search_document(row)

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
        self.ensure_schema()
        query_like = f"%{query_text}%"
        window_limit = limit + 1
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_obj:
                    cursor_obj.execute(
                        """
                        SELECT
                          id,
                          search_index_id,
                          document_id,
                          run_id,
                          page_id,
                          line_id,
                          token_id,
                          source_kind,
                          source_ref_id,
                          page_number,
                          match_span_json,
                          token_geometry_json,
                          search_text,
                          search_metadata_json,
                          created_at
                        FROM search_documents
                        WHERE search_index_id = %(search_index_id)s
                          AND search_text ILIKE %(query_like)s
                          AND (
                            %(document_id)s IS NULL
                            OR document_id = %(document_id)s
                          )
                          AND (
                            %(run_id)s IS NULL
                            OR run_id = %(run_id)s
                          )
                          AND (
                            %(page_number)s IS NULL
                            OR page_number = %(page_number)s
                          )
                        ORDER BY page_number ASC, document_id ASC, run_id ASC, id ASC
                        OFFSET %(cursor)s
                        LIMIT %(window_limit)s
                        """,
                        {
                            "search_index_id": search_index_id,
                            "query_like": query_like,
                            "document_id": document_id,
                            "run_id": run_id,
                            "page_number": page_number,
                            "cursor": cursor,
                            "window_limit": window_limit,
                        },
                    )
                    rows = cursor_obj.fetchall()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Search document query failed.") from error

        has_more = len(rows) > limit
        materialized = rows[:limit]
        items = [self._as_search_document(row) for row in materialized]
        next_cursor = (cursor + limit) if has_more else None
        return SearchDocumentPage(items=items, next_cursor=next_cursor)

    def store_search_query_text(
        self,
        *,
        project_id: str,
        query_text: str,
        key: str | None = None,
    ) -> str:
        self.ensure_schema()
        text = query_text
        if len(text) == 0:
            raise IndexStoreUnavailableError("query_text must be non-empty.")
        query_text_key = key or f"searchquerytext-{uuid4()}"
        created_at = self.utcnow()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO search_query_texts (
                          key,
                          project_id,
                          query_text,
                          created_at
                        )
                        VALUES (
                          %(key)s,
                          %(project_id)s,
                          %(query_text)s,
                          %(created_at)s
                        )
                        """,
                        {
                            "key": query_text_key,
                            "project_id": project_id,
                            "query_text": text,
                            "created_at": created_at,
                        },
                    )
                connection.commit()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Search query text storage failed.") from error
        return query_text_key

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
        self.ensure_schema()
        created_at = self.utcnow()
        resolved_audit_id = audit_id or f"searchqueryaudit-{uuid4()}"
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO search_query_audits (
                          id,
                          project_id,
                          actor_user_id,
                          search_index_id,
                          query_sha256,
                          query_text_key,
                          filters_json,
                          result_count,
                          created_at
                        )
                        VALUES (
                          %(id)s,
                          %(project_id)s,
                          %(actor_user_id)s,
                          %(search_index_id)s,
                          %(query_sha256)s,
                          %(query_text_key)s,
                          %(filters_json)s,
                          %(result_count)s,
                          %(created_at)s
                        )
                        RETURNING
                          id,
                          project_id,
                          actor_user_id,
                          search_index_id,
                          query_sha256,
                          query_text_key,
                          filters_json,
                          result_count,
                          created_at
                        """,
                        {
                            "id": resolved_audit_id,
                            "project_id": project_id,
                            "actor_user_id": actor_user_id,
                            "search_index_id": search_index_id,
                            "query_sha256": query_sha256,
                            "query_text_key": query_text_key,
                            "filters_json": filters_json,
                            "result_count": max(0, result_count),
                            "created_at": created_at,
                        },
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise IndexStoreUnavailableError(
                            "Search query audit insert returned no row."
                        )
                connection.commit()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Search query audit append failed.") from error
        return self._as_search_query_audit(row)

    def list_search_query_audits(
        self,
        *,
        project_id: str,
        cursor: int,
        limit: int,
    ) -> SearchQueryAuditPage:
        self.ensure_schema()
        window_limit = limit + 1
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_obj:
                    cursor_obj.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          actor_user_id,
                          search_index_id,
                          query_sha256,
                          query_text_key,
                          filters_json,
                          result_count,
                          created_at
                        FROM search_query_audits
                        WHERE project_id = %(project_id)s
                        ORDER BY created_at DESC, id DESC
                        OFFSET %(cursor)s
                        LIMIT %(window_limit)s
                        """,
                        {
                            "project_id": project_id,
                            "cursor": cursor,
                            "window_limit": window_limit,
                        },
                    )
                    rows = cursor_obj.fetchall()
        except psycopg.Error as error:
            raise IndexStoreUnavailableError("Search query audit listing failed.") from error

        has_more = len(rows) > limit
        materialized = rows[:limit]
        items = [self._as_search_query_audit(row) for row in materialized]
        next_cursor = (cursor + limit) if has_more else None
        return SearchQueryAuditPage(items=items, next_cursor=next_cursor)
