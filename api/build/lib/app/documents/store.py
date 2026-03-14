import hashlib
import json
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row
from uuid import uuid4

from app.core.config import Settings
from app.documents.models import (
    ApprovedModelRecord,
    ApprovedModelRole,
    ApprovedModelServingInterface,
    ApprovedModelStatus,
    ApprovedModelType,
    ProjectModelAssignmentRecord,
    ProjectModelAssignmentStatus,
    TrainingDatasetKind,
    TrainingDatasetRecord,
    DocumentTranscriptionProjectionRecord,
    LineTranscriptionResultRecord,
    PageTranscriptionResultRecord,
    TokenAnchorStatus,
    TokenTranscriptionResultRecord,
    TranscriptionConfidenceBasis,
    TranscriptionLineSchemaValidationStatus,
    TranscriptionOutputProjectionRecord,
    TranscriptionProjectionBasis,
    TranscriptionRunEngine,
    TranscriptionRunRecord,
    TranscriptionRunStatus,
    TranscriptionTokenSourceKind,
    TranscriptVersionRecord,
    DownstreamBasisState,
    LayoutActivationBlockerCode,
    LayoutActivationBlockerRecord,
    LayoutActivationDownstreamImpactRecord,
    LayoutActivationGateRecord,
    DocumentLayoutProjectionRecord,
    DocumentPreprocessProjectionRecord,
    DocumentImportRecord,
    DocumentImportStatus,
    DocumentPageRecord,
    DocumentListFilters,
    LayoutRecallCheckRecord,
    LayoutRescueCandidateKind,
    LayoutRescueCandidateRecord,
    LayoutRescueCandidateStatus,
    LayoutVersionRecord,
    LayoutVersionKind,
    LayoutLineArtifactRecord,
    LayoutRunKind,
    LayoutRunRecord,
    LayoutRunStatus,
    PageLayoutResultStatus,
    PageLayoutResultRecord,
    PageRecallStatus,
    PagePreprocessResultRecord,
    PreprocessProfileRegistryRecord,
    PreprocessPageResultStatus,
    PreprocessDownstreamBasisReferencesRecord,
    PreprocessQualityGateStatus,
    PreprocessRunRecord,
    PreprocessRunScope,
    PreprocessRunStatus,
    SourceColorMode,
    DocumentProcessingRunKind,
    DocumentProcessingRunRecord,
    DocumentProcessingRunStatus,
    DocumentUploadSessionRecord,
    DocumentUploadSessionStatus,
    DocumentRecord,
    DocumentStatus,
    PageStatus,
)
from app.documents.preprocessing import (
    hash_params_canonical,
    list_preprocess_profile_definitions,
    serialize_params_canonical,
)
from app.projects.store import ProjectStore

DOCUMENT_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS documents (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      original_filename TEXT NOT NULL,
      stored_filename TEXT,
      content_type_detected TEXT,
      bytes BIGINT CHECK (bytes IS NULL OR bytes >= 0),
      sha256 TEXT,
      page_count INTEGER CHECK (page_count IS NULL OR page_count >= 0),
      status TEXT NOT NULL CHECK (
        status IN (
          'UPLOADING',
          'QUEUED',
          'SCANNING',
          'EXTRACTING',
          'READY',
          'FAILED',
          'CANCELED'
        )
      ),
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_documents_project_created
      ON documents(project_id, created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_documents_project_updated
      ON documents(project_id, updated_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_documents_project_status
      ON documents(project_id, status)
    """,
    """
    CREATE TABLE IF NOT EXISTS document_imports (
      id TEXT PRIMARY KEY,
      document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      status TEXT NOT NULL CHECK (
        status IN (
          'UPLOADING',
          'QUEUED',
          'SCANNING',
          'ACCEPTED',
          'REJECTED',
          'FAILED',
          'CANCELED'
        )
      ),
      failure_reason TEXT,
      created_by TEXT NOT NULL REFERENCES users(id),
      accepted_at TIMESTAMPTZ,
      rejected_at TIMESTAMPTZ,
      canceled_by TEXT REFERENCES users(id),
      canceled_at TIMESTAMPTZ,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_document_imports_document_created
      ON document_imports(document_id, created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS document_processing_runs (
      id TEXT PRIMARY KEY,
      document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      attempt_number INTEGER NOT NULL DEFAULT 1 CHECK (attempt_number >= 1),
      run_kind TEXT NOT NULL CHECK (
        run_kind IN ('UPLOAD', 'SCAN', 'EXTRACTION', 'THUMBNAIL_RENDER')
      ),
      supersedes_processing_run_id TEXT REFERENCES document_processing_runs(id),
      superseded_by_processing_run_id TEXT REFERENCES document_processing_runs(id),
      status TEXT NOT NULL CHECK (
        status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED')
      ),
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      started_at TIMESTAMPTZ,
      finished_at TIMESTAMPTZ,
      canceled_by TEXT REFERENCES users(id),
      canceled_at TIMESTAMPTZ,
      failure_reason TEXT
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_document_processing_runs_document_created
      ON document_processing_runs(document_id, created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_document_processing_runs_lineage
      ON document_processing_runs(document_id, run_kind, attempt_number DESC)
    """,
    """
    ALTER TABLE document_processing_runs
    ADD COLUMN IF NOT EXISTS attempt_number INTEGER NOT NULL DEFAULT 1
    """,
    """
    ALTER TABLE document_processing_runs
    ADD COLUMN IF NOT EXISTS superseded_by_processing_run_id TEXT
      REFERENCES document_processing_runs(id)
    """,
    """
    CREATE TABLE IF NOT EXISTS document_upload_sessions (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      import_id TEXT NOT NULL REFERENCES document_imports(id) ON DELETE CASCADE,
      original_filename TEXT NOT NULL,
      status TEXT NOT NULL CHECK (
        status IN ('ACTIVE', 'ASSEMBLING', 'FAILED', 'CANCELED', 'COMPLETED')
      ),
      expected_sha256 TEXT,
      expected_total_bytes BIGINT CHECK (expected_total_bytes IS NULL OR expected_total_bytes >= 0),
      bytes_received BIGINT NOT NULL DEFAULT 0 CHECK (bytes_received >= 0),
      last_chunk_index INTEGER NOT NULL DEFAULT -1 CHECK (last_chunk_index >= -1),
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      completed_at TIMESTAMPTZ,
      canceled_at TIMESTAMPTZ,
      failure_reason TEXT
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_document_upload_sessions_project_created
      ON document_upload_sessions(project_id, created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS document_upload_session_chunks (
      session_id TEXT NOT NULL REFERENCES document_upload_sessions(id) ON DELETE CASCADE,
      chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
      byte_length INTEGER NOT NULL CHECK (byte_length > 0),
      sha256 TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (session_id, chunk_index)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pages (
      id TEXT PRIMARY KEY,
      document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      page_index INTEGER NOT NULL CHECK (page_index >= 0),
      width INTEGER NOT NULL CHECK (width >= 0),
      height INTEGER NOT NULL CHECK (height >= 0),
      dpi INTEGER CHECK (dpi IS NULL OR dpi >= 0),
      source_width INTEGER NOT NULL DEFAULT 0 CHECK (source_width >= 0),
      source_height INTEGER NOT NULL DEFAULT 0 CHECK (source_height >= 0),
      source_dpi INTEGER CHECK (source_dpi IS NULL OR source_dpi >= 0),
      source_color_mode TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK (
        source_color_mode IN ('RGB', 'RGBA', 'GRAY', 'CMYK', 'UNKNOWN')
      ),
      status TEXT NOT NULL CHECK (
        status IN ('PENDING', 'READY', 'FAILED', 'CANCELED')
      ),
      derived_image_key TEXT,
      derived_image_sha256 TEXT,
      thumbnail_key TEXT,
      thumbnail_sha256 TEXT,
      failure_reason TEXT,
      canceled_by TEXT REFERENCES users(id),
      canceled_at TIMESTAMPTZ,
      viewer_rotation INTEGER NOT NULL DEFAULT 0,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE (document_id, page_index)
    )
    """,
    """
    ALTER TABLE pages
    ADD COLUMN IF NOT EXISTS source_width INTEGER NOT NULL DEFAULT 0
    """,
    """
    ALTER TABLE pages
    ADD COLUMN IF NOT EXISTS source_height INTEGER NOT NULL DEFAULT 0
    """,
    """
    ALTER TABLE pages
    ADD COLUMN IF NOT EXISTS source_dpi INTEGER
    """,
    """
    ALTER TABLE pages
    ADD COLUMN IF NOT EXISTS source_color_mode TEXT NOT NULL DEFAULT 'UNKNOWN'
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_pages_document_index
      ON pages(document_id, page_index ASC)
    """,
    """
    CREATE TABLE IF NOT EXISTS preprocess_runs (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      parent_run_id TEXT REFERENCES preprocess_runs(id),
      attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
      run_scope TEXT NOT NULL DEFAULT 'FULL_DOCUMENT' CHECK (
        run_scope IN ('FULL_DOCUMENT', 'PAGE_SUBSET', 'COMPOSED_FULL_DOCUMENT')
      ),
      target_page_ids_json JSONB,
      composed_from_run_ids_json JSONB,
      superseded_by_run_id TEXT REFERENCES preprocess_runs(id),
      profile_id TEXT NOT NULL,
      profile_version TEXT NOT NULL DEFAULT 'v1',
      profile_revision INTEGER NOT NULL DEFAULT 1 CHECK (profile_revision >= 1),
      profile_label TEXT NOT NULL DEFAULT '',
      profile_description TEXT NOT NULL DEFAULT '',
      profile_params_hash TEXT NOT NULL DEFAULT '',
      profile_is_advanced BOOLEAN NOT NULL DEFAULT FALSE,
      profile_is_gated BOOLEAN NOT NULL DEFAULT FALSE,
      params_json JSONB NOT NULL,
      params_hash TEXT NOT NULL,
      pipeline_version TEXT NOT NULL,
      container_digest TEXT NOT NULL,
      manifest_object_key TEXT,
      manifest_sha256 TEXT,
      manifest_schema_version INTEGER NOT NULL DEFAULT 1 CHECK (manifest_schema_version >= 1),
      status TEXT NOT NULL CHECK (
        status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED')
      ),
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      started_at TIMESTAMPTZ,
      finished_at TIMESTAMPTZ,
      failure_reason TEXT
    )
    """,
    """
    ALTER TABLE preprocess_runs
    ADD COLUMN IF NOT EXISTS profile_version TEXT NOT NULL DEFAULT 'v1'
    """,
    """
    ALTER TABLE preprocess_runs
    ADD COLUMN IF NOT EXISTS run_scope TEXT NOT NULL DEFAULT 'FULL_DOCUMENT'
    """,
    """
    ALTER TABLE preprocess_runs
    ADD COLUMN IF NOT EXISTS target_page_ids_json JSONB
    """,
    """
    ALTER TABLE preprocess_runs
    ADD COLUMN IF NOT EXISTS composed_from_run_ids_json JSONB
    """,
    """
    ALTER TABLE preprocess_runs
    ADD COLUMN IF NOT EXISTS profile_revision INTEGER NOT NULL DEFAULT 1
    """,
    """
    ALTER TABLE preprocess_runs
    ADD COLUMN IF NOT EXISTS profile_label TEXT NOT NULL DEFAULT ''
    """,
    """
    ALTER TABLE preprocess_runs
    ADD COLUMN IF NOT EXISTS profile_description TEXT NOT NULL DEFAULT ''
    """,
    """
    ALTER TABLE preprocess_runs
    ADD COLUMN IF NOT EXISTS profile_params_hash TEXT NOT NULL DEFAULT ''
    """,
    """
    ALTER TABLE preprocess_runs
    ADD COLUMN IF NOT EXISTS profile_is_advanced BOOLEAN NOT NULL DEFAULT FALSE
    """,
    """
    ALTER TABLE preprocess_runs
    ADD COLUMN IF NOT EXISTS profile_is_gated BOOLEAN NOT NULL DEFAULT FALSE
    """,
    """
    ALTER TABLE preprocess_runs
    ADD COLUMN IF NOT EXISTS manifest_object_key TEXT
    """,
    """
    ALTER TABLE preprocess_runs
    ADD COLUMN IF NOT EXISTS manifest_sha256 TEXT
    """,
    """
    ALTER TABLE preprocess_runs
    ADD COLUMN IF NOT EXISTS manifest_schema_version INTEGER NOT NULL DEFAULT 1
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_preprocess_runs_document_created
      ON preprocess_runs(project_id, document_id, created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_preprocess_runs_document_attempt
      ON preprocess_runs(project_id, document_id, attempt_number DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS page_preprocess_results (
      run_id TEXT NOT NULL REFERENCES preprocess_runs(id) ON DELETE CASCADE,
      page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
      page_index INTEGER NOT NULL CHECK (page_index >= 0),
      status TEXT NOT NULL CHECK (
        status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED')
      ),
      quality_gate_status TEXT NOT NULL CHECK (
        quality_gate_status IN ('PASS', 'REVIEW_REQUIRED', 'BLOCKED')
      ),
      input_object_key TEXT,
      input_sha256 TEXT,
      source_result_run_id TEXT REFERENCES preprocess_runs(id),
      output_object_key_gray TEXT,
      output_object_key_bin TEXT,
      metrics_object_key TEXT,
      metrics_sha256 TEXT,
      metrics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      sha256_gray TEXT,
      sha256_bin TEXT,
      warnings_json JSONB NOT NULL DEFAULT '[]'::jsonb,
      failure_reason TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (run_id, page_id)
    )
    """,
    """
    ALTER TABLE page_preprocess_results
    ADD COLUMN IF NOT EXISTS input_sha256 TEXT
    """,
    """
    ALTER TABLE page_preprocess_results
    ADD COLUMN IF NOT EXISTS source_result_run_id TEXT REFERENCES preprocess_runs(id)
    """,
    """
    ALTER TABLE page_preprocess_results
    ADD COLUMN IF NOT EXISTS metrics_object_key TEXT
    """,
    """
    ALTER TABLE page_preprocess_results
    ADD COLUMN IF NOT EXISTS metrics_sha256 TEXT
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_page_preprocess_results_run_page
      ON page_preprocess_results(run_id, page_index ASC)
    """,
    """
    CREATE TABLE IF NOT EXISTS document_preprocess_projections (
      document_id TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      active_preprocess_run_id TEXT REFERENCES preprocess_runs(id),
      active_profile_id TEXT,
      active_profile_version TEXT,
      active_profile_revision INTEGER,
      active_params_hash TEXT,
      active_pipeline_version TEXT,
      active_container_digest TEXT,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    ALTER TABLE document_preprocess_projections
    ADD COLUMN IF NOT EXISTS active_profile_version TEXT
    """,
    """
    ALTER TABLE document_preprocess_projections
    ADD COLUMN IF NOT EXISTS active_profile_revision INTEGER
    """,
    """
    ALTER TABLE document_preprocess_projections
    ADD COLUMN IF NOT EXISTS active_params_hash TEXT
    """,
    """
    ALTER TABLE document_preprocess_projections
    ADD COLUMN IF NOT EXISTS active_pipeline_version TEXT
    """,
    """
    ALTER TABLE document_preprocess_projections
    ADD COLUMN IF NOT EXISTS active_container_digest TEXT
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_document_preprocess_projection_project_document
      ON document_preprocess_projections(project_id, document_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS layout_runs (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      input_preprocess_run_id TEXT NOT NULL REFERENCES preprocess_runs(id),
      run_kind TEXT NOT NULL CHECK (
        run_kind IN ('AUTO')
      ),
      parent_run_id TEXT REFERENCES layout_runs(id),
      attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
      superseded_by_run_id TEXT REFERENCES layout_runs(id),
      model_id TEXT,
      profile_id TEXT,
      params_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      params_hash TEXT NOT NULL,
      pipeline_version TEXT NOT NULL,
      container_digest TEXT NOT NULL,
      status TEXT NOT NULL CHECK (
        status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED')
      ),
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      started_at TIMESTAMPTZ,
      finished_at TIMESTAMPTZ,
      failure_reason TEXT
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_layout_runs_document_created
      ON layout_runs(project_id, document_id, created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_layout_runs_document_attempt
      ON layout_runs(project_id, document_id, attempt_number DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_layout_runs_input_preprocess
      ON layout_runs(project_id, document_id, input_preprocess_run_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS page_layout_results (
      run_id TEXT NOT NULL REFERENCES layout_runs(id) ON DELETE CASCADE,
      page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
      page_index INTEGER NOT NULL CHECK (page_index >= 0),
      status TEXT NOT NULL CHECK (
        status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED')
      ),
      page_recall_status TEXT NOT NULL CHECK (
        page_recall_status IN ('COMPLETE', 'NEEDS_RESCUE', 'NEEDS_MANUAL_REVIEW')
      ),
      active_layout_version_id TEXT,
      page_xml_key TEXT,
      overlay_json_key TEXT,
      page_xml_sha256 TEXT,
      overlay_json_sha256 TEXT,
      metrics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      warnings_json JSONB NOT NULL DEFAULT '[]'::jsonb,
      failure_reason TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (run_id, page_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_page_layout_results_run_page
      ON page_layout_results(run_id, page_index ASC)
    """,
    """
    CREATE TABLE IF NOT EXISTS layout_versions (
      id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL REFERENCES layout_runs(id) ON DELETE CASCADE,
      page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
      base_version_id TEXT REFERENCES layout_versions(id),
      superseded_by_version_id TEXT REFERENCES layout_versions(id),
      version_kind TEXT NOT NULL DEFAULT 'SEGMENTATION_EDIT' CHECK (
        version_kind IN ('SEGMENTATION_EDIT', 'READING_ORDER_EDIT')
      ),
      version_etag TEXT NOT NULL UNIQUE,
      page_xml_key TEXT NOT NULL,
      overlay_json_key TEXT NOT NULL,
      page_xml_sha256 TEXT NOT NULL,
      overlay_json_sha256 TEXT NOT NULL,
      run_snapshot_hash TEXT NOT NULL DEFAULT '',
      canonical_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      reading_order_groups_json JSONB NOT NULL DEFAULT '[]'::jsonb,
      reading_order_meta_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_layout_versions_run_page_created
      ON layout_versions(run_id, page_id, created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_layout_versions_base
      ON layout_versions(base_version_id)
    """,
    """
    ALTER TABLE layout_versions
    ADD COLUMN IF NOT EXISTS version_kind TEXT NOT NULL DEFAULT 'SEGMENTATION_EDIT'
    """,
    """
    ALTER TABLE layout_versions
    ADD COLUMN IF NOT EXISTS run_snapshot_hash TEXT NOT NULL DEFAULT ''
    """,
    """
    ALTER TABLE layout_versions
    DROP CONSTRAINT IF EXISTS layout_versions_version_kind_check
    """,
    """
    ALTER TABLE layout_versions
    ADD CONSTRAINT layout_versions_version_kind_check
    CHECK (version_kind IN ('SEGMENTATION_EDIT', 'READING_ORDER_EDIT'))
    """,
    """
    CREATE TABLE IF NOT EXISTS layout_recall_checks (
      run_id TEXT NOT NULL REFERENCES layout_runs(id) ON DELETE CASCADE,
      page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
      recall_check_version TEXT NOT NULL,
      missed_text_risk_score DOUBLE PRECISION CHECK (
        missed_text_risk_score IS NULL
        OR (missed_text_risk_score >= 0 AND missed_text_risk_score <= 1)
      ),
      signals_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (run_id, page_id, recall_check_version)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_layout_recall_checks_run_page
      ON layout_recall_checks(run_id, page_id, created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS layout_rescue_candidates (
      id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL REFERENCES layout_runs(id) ON DELETE CASCADE,
      page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
      candidate_kind TEXT NOT NULL CHECK (
        candidate_kind IN ('LINE_EXPANSION', 'PAGE_WINDOW')
      ),
      geometry_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      confidence DOUBLE PRECISION CHECK (
        confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
      ),
      source_signal TEXT,
      status TEXT NOT NULL CHECK (
        status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'RESOLVED')
      ),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_layout_rescue_candidates_run_page
      ON layout_rescue_candidates(run_id, page_id, created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS layout_line_artifacts (
      run_id TEXT NOT NULL REFERENCES layout_runs(id) ON DELETE CASCADE,
      page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
      layout_version_id TEXT NOT NULL,
      line_id TEXT NOT NULL,
      region_id TEXT,
      line_crop_key TEXT NOT NULL,
      region_crop_key TEXT,
      page_thumbnail_key TEXT NOT NULL,
      context_window_json_key TEXT NOT NULL,
      artifacts_sha256 TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (run_id, page_id, layout_version_id, line_id)
    )
    """,
    """
    DO $$
    BEGIN
      IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'layout_line_artifacts'
      )
      AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'layout_line_artifacts'
          AND column_name = 'layout_version_id'
      ) THEN
        ALTER TABLE layout_line_artifacts RENAME TO layout_line_artifacts_legacy;
        CREATE TABLE layout_line_artifacts (
          run_id TEXT NOT NULL REFERENCES layout_runs(id) ON DELETE CASCADE,
          page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
          layout_version_id TEXT NOT NULL,
          line_id TEXT NOT NULL,
          region_id TEXT,
          line_crop_key TEXT NOT NULL,
          region_crop_key TEXT,
          page_thumbnail_key TEXT NOT NULL,
          context_window_json_key TEXT NOT NULL,
          artifacts_sha256 TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (run_id, page_id, layout_version_id, line_id)
        );
        INSERT INTO layout_line_artifacts (
          run_id,
          page_id,
          layout_version_id,
          line_id,
          region_id,
          line_crop_key,
          region_crop_key,
          page_thumbnail_key,
          context_window_json_key,
          artifacts_sha256,
          created_at
        )
        SELECT
          lla.run_id,
          lla.page_id,
          COALESCE(
            plr.active_layout_version_id,
            'legacy-' || md5(lla.run_id || '|' || lla.page_id || '|' || lla.line_id)
          ),
          lla.line_id,
          lla.region_id,
          lla.line_crop_key,
          lla.region_crop_key,
          lla.page_thumbnail_key,
          lla.context_window_json_key,
          lla.artifacts_sha256,
          lla.created_at
        FROM layout_line_artifacts_legacy AS lla
        LEFT JOIN page_layout_results AS plr
          ON plr.run_id = lla.run_id
         AND plr.page_id = lla.page_id;
        DROP TABLE layout_line_artifacts_legacy;
      END IF;
    END
    $$;
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_layout_line_artifacts_run_page
      ON layout_line_artifacts(run_id, page_id, layout_version_id, line_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS document_layout_projections (
      document_id TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      active_layout_run_id TEXT,
      active_input_preprocess_run_id TEXT REFERENCES preprocess_runs(id),
      active_layout_snapshot_hash TEXT,
      downstream_transcription_state TEXT NOT NULL DEFAULT 'NOT_STARTED' CHECK (
        downstream_transcription_state IN ('NOT_STARTED', 'CURRENT', 'STALE')
      ),
      downstream_transcription_invalidated_at TIMESTAMPTZ,
      downstream_transcription_invalidated_reason TEXT,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    ALTER TABLE document_layout_projections
    ADD COLUMN IF NOT EXISTS active_layout_run_id TEXT
    """,
    """
    ALTER TABLE document_layout_projections
    ADD COLUMN IF NOT EXISTS active_input_preprocess_run_id TEXT
      REFERENCES preprocess_runs(id)
    """,
    """
    ALTER TABLE document_layout_projections
    ADD COLUMN IF NOT EXISTS active_layout_snapshot_hash TEXT
    """,
    """
    ALTER TABLE document_layout_projections
    ADD COLUMN IF NOT EXISTS downstream_transcription_state TEXT NOT NULL DEFAULT 'NOT_STARTED'
    """,
    """
    ALTER TABLE document_layout_projections
    ADD COLUMN IF NOT EXISTS downstream_transcription_invalidated_at TIMESTAMPTZ
    """,
    """
    ALTER TABLE document_layout_projections
    ADD COLUMN IF NOT EXISTS downstream_transcription_invalidated_reason TEXT
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_document_layout_projection_project_document
      ON document_layout_projections(project_id, document_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS document_transcription_projections (
      document_id TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      active_transcription_run_id TEXT,
      active_layout_run_id TEXT,
      active_layout_snapshot_hash TEXT,
      active_preprocess_run_id TEXT REFERENCES preprocess_runs(id),
      downstream_redaction_state TEXT NOT NULL DEFAULT 'NOT_STARTED' CHECK (
        downstream_redaction_state IN ('NOT_STARTED', 'CURRENT', 'STALE')
      ),
      downstream_redaction_invalidated_at TIMESTAMPTZ,
      downstream_redaction_invalidated_reason TEXT,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    ALTER TABLE document_transcription_projections
    ADD COLUMN IF NOT EXISTS active_transcription_run_id TEXT
    """,
    """
    ALTER TABLE document_transcription_projections
    ADD COLUMN IF NOT EXISTS active_layout_run_id TEXT
    """,
    """
    ALTER TABLE document_transcription_projections
    ADD COLUMN IF NOT EXISTS active_layout_snapshot_hash TEXT
    """,
    """
    ALTER TABLE document_transcription_projections
    ADD COLUMN IF NOT EXISTS active_preprocess_run_id TEXT
      REFERENCES preprocess_runs(id)
    """,
    """
    ALTER TABLE document_transcription_projections
    ADD COLUMN IF NOT EXISTS downstream_redaction_state TEXT NOT NULL DEFAULT 'NOT_STARTED'
    """,
    """
    ALTER TABLE document_transcription_projections
    ADD COLUMN IF NOT EXISTS downstream_redaction_invalidated_at TIMESTAMPTZ
    """,
    """
    ALTER TABLE document_transcription_projections
    ADD COLUMN IF NOT EXISTS downstream_redaction_invalidated_reason TEXT
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_document_transcription_projection_project_document
      ON document_transcription_projections(project_id, document_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS approved_models (
      id TEXT PRIMARY KEY,
      model_type TEXT NOT NULL CHECK (
        model_type IN ('VLM', 'LLM', 'HTR')
      ),
      model_role TEXT NOT NULL CHECK (
        model_role IN ('TRANSCRIPTION_PRIMARY', 'TRANSCRIPTION_FALLBACK', 'ASSIST')
      ),
      model_family TEXT NOT NULL,
      model_version TEXT NOT NULL,
      serving_interface TEXT NOT NULL CHECK (
        serving_interface IN ('OPENAI_CHAT', 'OPENAI_EMBEDDING', 'ENGINE_NATIVE', 'RULES_NATIVE')
      ),
      engine_family TEXT NOT NULL,
      deployment_unit TEXT NOT NULL,
      artifact_subpath TEXT NOT NULL,
      checksum_sha256 TEXT NOT NULL,
      runtime_profile TEXT NOT NULL,
      response_contract_version TEXT NOT NULL,
      metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      status TEXT NOT NULL CHECK (
        status IN ('APPROVED', 'DEPRECATED', 'ROLLED_BACK')
      ),
      approved_by TEXT REFERENCES users(id),
      approved_at TIMESTAMPTZ,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_approved_models_role_status
      ON approved_models(model_role, status, updated_at DESC)
    """,
    """
    INSERT INTO approved_models (
      id,
      model_type,
      model_role,
      model_family,
      model_version,
      serving_interface,
      engine_family,
      deployment_unit,
      artifact_subpath,
      checksum_sha256,
      runtime_profile,
      response_contract_version,
      metadata_json,
      status,
      approved_by,
      approved_at
    )
    VALUES (
      'model-transcription-primary-qwen2.5-vl-3b-instruct',
      'VLM',
      'TRANSCRIPTION_PRIMARY',
      'Qwen2.5-VL',
      '3B-Instruct',
      'OPENAI_CHAT',
      'QWEN_VL',
      'internal-vlm',
      'internal-vlm/qwen2.5-vl-3b-instruct',
      repeat('0', 64),
      'default',
      'v1',
      '{"phase":"4.0","owner":"transcription"}'::jsonb,
      'APPROVED',
      NULL,
      NULL
    )
    ON CONFLICT (id) DO NOTHING
    """,
    """
    INSERT INTO approved_models (
      id,
      model_type,
      model_role,
      model_family,
      model_version,
      serving_interface,
      engine_family,
      deployment_unit,
      artifact_subpath,
      checksum_sha256,
      runtime_profile,
      response_contract_version,
      metadata_json,
      status,
      approved_by,
      approved_at
    )
    VALUES (
      'model-assist-qwen3-4b',
      'LLM',
      'ASSIST',
      'Qwen3',
      '4B',
      'OPENAI_CHAT',
      'QWEN',
      'internal-llm',
      'internal-llm/qwen3-4b',
      repeat('1', 64),
      'assist-default',
      'v1',
      '{"phase":"4.4","owner":"review-assist"}'::jsonb,
      'APPROVED',
      NULL,
      NULL
    )
    ON CONFLICT (id) DO NOTHING
    """,
    """
    INSERT INTO approved_models (
      id,
      model_type,
      model_role,
      model_family,
      model_version,
      serving_interface,
      engine_family,
      deployment_unit,
      artifact_subpath,
      checksum_sha256,
      runtime_profile,
      response_contract_version,
      metadata_json,
      status,
      approved_by,
      approved_at
    )
    VALUES (
      'model-transcription-fallback-kraken',
      'HTR',
      'TRANSCRIPTION_FALLBACK',
      'Kraken',
      'baseline',
      'ENGINE_NATIVE',
      'KRAKEN',
      'kraken',
      'kraken/default',
      repeat('2', 64),
      'fallback-default',
      'v1',
      '{"phase":"4.4","owner":"transcription-fallback"}'::jsonb,
      'APPROVED',
      NULL,
      NULL
    )
    ON CONFLICT (id) DO NOTHING
    """,
    """
    CREATE TABLE IF NOT EXISTS project_model_assignments (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      model_role TEXT NOT NULL CHECK (
        model_role IN ('TRANSCRIPTION_PRIMARY', 'TRANSCRIPTION_FALLBACK', 'ASSIST')
      ),
      approved_model_id TEXT NOT NULL REFERENCES approved_models(id),
      status TEXT NOT NULL CHECK (
        status IN ('DRAFT', 'ACTIVE', 'RETIRED')
      ),
      assignment_reason TEXT NOT NULL,
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      activated_by TEXT REFERENCES users(id),
      activated_at TIMESTAMPTZ,
      retired_by TEXT REFERENCES users(id),
      retired_at TIMESTAMPTZ
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_project_model_assignments_project_role_status
      ON project_model_assignments(project_id, model_role, status, created_at DESC)
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_project_model_assignments_active_role
      ON project_model_assignments(project_id, model_role)
      WHERE status = 'ACTIVE'
    """,
    """
    CREATE TABLE IF NOT EXISTS training_datasets (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      source_approved_model_id TEXT REFERENCES approved_models(id),
      project_model_assignment_id TEXT REFERENCES project_model_assignments(id) ON DELETE SET NULL,
      dataset_kind TEXT NOT NULL CHECK (
        dataset_kind IN ('TRANSCRIPTION_TRAINING')
      ),
      page_count INTEGER NOT NULL CHECK (page_count >= 0),
      storage_key TEXT NOT NULL,
      dataset_sha256 TEXT NOT NULL,
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_training_datasets_assignment
      ON training_datasets(project_id, project_model_assignment_id, created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_training_datasets_model
      ON training_datasets(project_id, source_approved_model_id, created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS transcription_runs (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      input_preprocess_run_id TEXT NOT NULL REFERENCES preprocess_runs(id),
      input_layout_run_id TEXT NOT NULL REFERENCES layout_runs(id),
      input_layout_snapshot_hash TEXT NOT NULL,
      engine TEXT NOT NULL CHECK (
        engine IN ('VLM_LINE_CONTEXT', 'REVIEW_COMPOSED', 'KRAKEN_LINE', 'TROCR_LINE', 'DAN_PAGE')
      ),
      model_id TEXT NOT NULL REFERENCES approved_models(id),
      project_model_assignment_id TEXT REFERENCES project_model_assignments(id) ON DELETE SET NULL,
      prompt_template_id TEXT,
      prompt_template_sha256 TEXT,
      response_schema_version INTEGER NOT NULL DEFAULT 1 CHECK (response_schema_version >= 1),
      confidence_basis TEXT NOT NULL CHECK (
        confidence_basis IN ('MODEL_NATIVE', 'READ_AGREEMENT', 'FALLBACK_DISAGREEMENT')
      ),
      confidence_calibration_version TEXT NOT NULL DEFAULT 'v1',
      params_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      pipeline_version TEXT NOT NULL,
      container_digest TEXT NOT NULL,
      attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
      supersedes_transcription_run_id TEXT,
      superseded_by_transcription_run_id TEXT,
      status TEXT NOT NULL CHECK (
        status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED')
      ),
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      started_at TIMESTAMPTZ,
      finished_at TIMESTAMPTZ,
      canceled_by TEXT REFERENCES users(id),
      canceled_at TIMESTAMPTZ,
      failure_reason TEXT
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_transcription_runs_project_document_created
      ON transcription_runs(project_id, document_id, created_at DESC, id DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_transcription_runs_supersedes
      ON transcription_runs(supersedes_transcription_run_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS page_transcription_results (
      run_id TEXT NOT NULL REFERENCES transcription_runs(id) ON DELETE CASCADE,
      page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
      page_index INTEGER NOT NULL CHECK (page_index >= 0),
      status TEXT NOT NULL CHECK (
        status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED')
      ),
      pagexml_out_key TEXT,
      pagexml_out_sha256 TEXT,
      raw_model_response_key TEXT,
      raw_model_response_sha256 TEXT,
      hocr_out_key TEXT,
      hocr_out_sha256 TEXT,
      metrics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      warnings_json JSONB NOT NULL DEFAULT '[]'::jsonb,
      failure_reason TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (run_id, page_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_page_transcription_results_run_page
      ON page_transcription_results(run_id, page_index ASC, page_id ASC)
    """,
    """
    CREATE TABLE IF NOT EXISTS line_transcription_results (
      run_id TEXT NOT NULL REFERENCES transcription_runs(id) ON DELETE CASCADE,
      page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
      line_id TEXT NOT NULL,
      text_diplomatic TEXT NOT NULL DEFAULT '',
      conf_line DOUBLE PRECISION CHECK (
        conf_line IS NULL OR (conf_line >= 0 AND conf_line <= 1)
      ),
      confidence_basis TEXT NOT NULL CHECK (
        confidence_basis IN ('MODEL_NATIVE', 'READ_AGREEMENT', 'FALLBACK_DISAGREEMENT')
      ),
      confidence_calibration_version TEXT NOT NULL DEFAULT 'v1',
      alignment_json_key TEXT,
      char_boxes_key TEXT,
      schema_validation_status TEXT NOT NULL CHECK (
        schema_validation_status IN ('VALID', 'FALLBACK_USED', 'INVALID')
      ),
      flags_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      machine_output_sha256 TEXT,
      active_transcript_version_id TEXT,
      version_etag TEXT NOT NULL,
      token_anchor_status TEXT NOT NULL CHECK (
        token_anchor_status IN ('CURRENT', 'STALE', 'REFRESH_REQUIRED')
      ),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (run_id, page_id, line_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_line_transcription_results_run_page
      ON line_transcription_results(run_id, page_id, line_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_line_transcription_results_anchor_status
      ON line_transcription_results(run_id, token_anchor_status)
    """,
    """
    CREATE TABLE IF NOT EXISTS token_transcription_results (
      run_id TEXT NOT NULL REFERENCES transcription_runs(id) ON DELETE CASCADE,
      page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
      line_id TEXT,
      token_id TEXT NOT NULL,
      token_index INTEGER NOT NULL CHECK (token_index >= 0),
      token_text TEXT NOT NULL,
      token_confidence DOUBLE PRECISION CHECK (
        token_confidence IS NULL OR (token_confidence >= 0 AND token_confidence <= 1)
      ),
      bbox_json JSONB,
      polygon_json JSONB,
      source_kind TEXT NOT NULL CHECK (
        source_kind IN ('LINE', 'RESCUE_CANDIDATE', 'PAGE_WINDOW')
      ),
      source_ref_id TEXT NOT NULL,
      projection_basis TEXT NOT NULL CHECK (
        projection_basis IN ('ENGINE_OUTPUT', 'REVIEW_CORRECTED')
      ),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (run_id, page_id, token_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_token_transcription_results_run_page_line
      ON token_transcription_results(run_id, page_id, line_id, token_index)
    """,
    """
    CREATE TABLE IF NOT EXISTS transcript_versions (
      id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL REFERENCES transcription_runs(id) ON DELETE CASCADE,
      page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
      line_id TEXT NOT NULL,
      base_version_id TEXT,
      superseded_by_version_id TEXT,
      version_etag TEXT NOT NULL,
      text_diplomatic TEXT NOT NULL,
      editor_user_id TEXT NOT NULL REFERENCES users(id),
      edit_reason TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_transcript_versions_run_page_line_created
      ON transcript_versions(run_id, page_id, line_id, created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS transcription_output_projections (
      run_id TEXT NOT NULL REFERENCES transcription_runs(id) ON DELETE CASCADE,
      document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
      corrected_pagexml_key TEXT NOT NULL,
      corrected_pagexml_sha256 TEXT NOT NULL,
      corrected_text_sha256 TEXT NOT NULL,
      source_pagexml_sha256 TEXT NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (run_id, page_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_transcription_output_projections_document
      ON transcription_output_projections(document_id, page_id, updated_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS preprocess_profile_registry (
      profile_id TEXT NOT NULL,
      profile_version TEXT NOT NULL,
      profile_revision INTEGER NOT NULL CHECK (profile_revision >= 1),
      label TEXT NOT NULL,
      description TEXT NOT NULL,
      params_json JSONB NOT NULL,
      params_hash TEXT NOT NULL,
      is_advanced BOOLEAN NOT NULL DEFAULT FALSE,
      is_gated BOOLEAN NOT NULL DEFAULT FALSE,
      supersedes_profile_id TEXT,
      supersedes_profile_revision INTEGER,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (profile_id, profile_revision),
      UNIQUE (profile_id, profile_version),
      UNIQUE (profile_id, params_hash),
      FOREIGN KEY (supersedes_profile_id, supersedes_profile_revision)
        REFERENCES preprocess_profile_registry(profile_id, profile_revision),
      CHECK (
        (supersedes_profile_id IS NULL AND supersedes_profile_revision IS NULL)
        OR (supersedes_profile_id IS NOT NULL AND supersedes_profile_revision IS NOT NULL)
      )
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_preprocess_profile_registry_profile
      ON preprocess_profile_registry(profile_id, profile_revision DESC)
    """,
)


class DocumentStoreUnavailableError(RuntimeError):
    """Document persistence could not be reached."""


class DocumentNotFoundError(RuntimeError):
    """Document record was not found for the requested project."""


class DocumentProcessingRunConflictError(RuntimeError):
    """Processing-run mutation conflicted with lineage constraints."""


class DocumentPreprocessRunConflictError(RuntimeError):
    """Preprocess-run mutation conflicted with lineage or state constraints."""


class DocumentLayoutRunConflictError(RuntimeError):
    """Layout-run mutation conflicted with lineage or state constraints."""

    def __init__(
        self,
        message: str,
        *,
        activation_gate: LayoutActivationGateRecord | None = None,
    ) -> None:
        super().__init__(message)
        self.activation_gate = activation_gate


class DocumentTranscriptionRunConflictError(RuntimeError):
    """Transcription-run mutation conflicted with lineage or state constraints."""


class DocumentModelCatalogConflictError(RuntimeError):
    """Approved-model catalog mutation violated validation or integrity rules."""


class DocumentModelAssignmentConflictError(RuntimeError):
    """Project model-assignment mutation violated lifecycle or compatibility rules."""


class DocumentUploadSessionNotFoundError(RuntimeError):
    """Upload session record was not found for the requested project."""


class DocumentUploadSessionConflictError(RuntimeError):
    """Upload session transition conflicted with current state."""


_LAYOUT_ACTIVATION_INVALIDATION_REASON = (
    "LAYOUT_ACTIVATION_SUPERSEDED: Active layout run changed; "
    "transcription basis requires refresh."
)


class DocumentStore:
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
    def _assert_document_status(status: str) -> DocumentStatus:
        if status not in {
            "UPLOADING",
            "QUEUED",
            "SCANNING",
            "EXTRACTING",
            "READY",
            "FAILED",
            "CANCELED",
        }:
            raise DocumentStoreUnavailableError("Unexpected document status persisted.")
        return status  # type: ignore[return-value]

    @staticmethod
    def _assert_document_import_status(status: str) -> DocumentImportStatus:
        if status not in {
            "UPLOADING",
            "QUEUED",
            "SCANNING",
            "ACCEPTED",
            "REJECTED",
            "FAILED",
            "CANCELED",
        }:
            raise DocumentStoreUnavailableError("Unexpected document-import status persisted.")
        return status  # type: ignore[return-value]

    @staticmethod
    def _assert_processing_run_kind(value: str) -> DocumentProcessingRunKind:
        if value not in {"UPLOAD", "SCAN", "EXTRACTION", "THUMBNAIL_RENDER"}:
            raise DocumentStoreUnavailableError("Unexpected processing run kind persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_processing_run_status(value: str) -> DocumentProcessingRunStatus:
        if value not in {"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"}:
            raise DocumentStoreUnavailableError("Unexpected processing run status persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_upload_session_status(value: str) -> DocumentUploadSessionStatus:
        if value not in {"ACTIVE", "ASSEMBLING", "FAILED", "CANCELED", "COMPLETED"}:
            raise DocumentStoreUnavailableError("Unexpected upload session status persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_page_status(value: str) -> PageStatus:
        if value not in {"PENDING", "READY", "FAILED", "CANCELED"}:
            raise DocumentStoreUnavailableError("Unexpected page status persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_preprocess_run_status(value: str) -> PreprocessRunStatus:
        if value not in {"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"}:
            raise DocumentStoreUnavailableError("Unexpected preprocess run status persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_layout_run_kind(value: str) -> LayoutRunKind:
        if value not in {"AUTO"}:
            raise DocumentStoreUnavailableError("Unexpected layout run kind persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_layout_run_status(value: str) -> LayoutRunStatus:
        if value not in {"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"}:
            raise DocumentStoreUnavailableError("Unexpected layout run status persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_transcription_run_status(value: str) -> TranscriptionRunStatus:
        if value not in {"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"}:
            raise DocumentStoreUnavailableError(
                "Unexpected transcription run status persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_transcription_run_engine(value: str) -> TranscriptionRunEngine:
        if value not in {
            "VLM_LINE_CONTEXT",
            "REVIEW_COMPOSED",
            "KRAKEN_LINE",
            "TROCR_LINE",
            "DAN_PAGE",
        }:
            raise DocumentStoreUnavailableError(
                "Unexpected transcription run engine persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_transcription_confidence_basis(
        value: str,
    ) -> TranscriptionConfidenceBasis:
        if value not in {"MODEL_NATIVE", "READ_AGREEMENT", "FALLBACK_DISAGREEMENT"}:
            raise DocumentStoreUnavailableError(
                "Unexpected transcription confidence basis persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_transcription_line_schema_status(
        value: str,
    ) -> TranscriptionLineSchemaValidationStatus:
        if value not in {"VALID", "FALLBACK_USED", "INVALID"}:
            raise DocumentStoreUnavailableError(
                "Unexpected transcription schema-validation status persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_token_anchor_status(value: str) -> TokenAnchorStatus:
        if value not in {"CURRENT", "STALE", "REFRESH_REQUIRED"}:
            raise DocumentStoreUnavailableError(
                "Unexpected token-anchor status persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_transcription_token_source_kind(
        value: str,
    ) -> TranscriptionTokenSourceKind:
        if value not in {"LINE", "RESCUE_CANDIDATE", "PAGE_WINDOW"}:
            raise DocumentStoreUnavailableError(
                "Unexpected transcription token source kind persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_transcription_projection_basis(
        value: str,
    ) -> TranscriptionProjectionBasis:
        if value not in {"ENGINE_OUTPUT", "REVIEW_CORRECTED"}:
            raise DocumentStoreUnavailableError(
                "Unexpected transcription projection basis persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_approved_model_type(value: str) -> ApprovedModelType:
        if value not in {"VLM", "LLM", "HTR"}:
            raise DocumentStoreUnavailableError("Unexpected approved model type persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_approved_model_role(value: str) -> ApprovedModelRole:
        if value not in {"TRANSCRIPTION_PRIMARY", "TRANSCRIPTION_FALLBACK", "ASSIST"}:
            raise DocumentStoreUnavailableError("Unexpected approved model role persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_approved_model_serving_interface(
        value: str,
    ) -> ApprovedModelServingInterface:
        if value not in {"OPENAI_CHAT", "OPENAI_EMBEDDING", "ENGINE_NATIVE", "RULES_NATIVE"}:
            raise DocumentStoreUnavailableError(
                "Unexpected approved model serving interface persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_approved_model_status(value: str) -> ApprovedModelStatus:
        if value not in {"APPROVED", "DEPRECATED", "ROLLED_BACK"}:
            raise DocumentStoreUnavailableError("Unexpected approved model status persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_project_model_assignment_status(value: str) -> ProjectModelAssignmentStatus:
        if value not in {"DRAFT", "ACTIVE", "RETIRED"}:
            raise DocumentStoreUnavailableError(
                "Unexpected project model-assignment status persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_training_dataset_kind(value: str) -> TrainingDatasetKind:
        if value not in {"TRANSCRIPTION_TRAINING"}:
            raise DocumentStoreUnavailableError("Unexpected training dataset kind persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_preprocess_run_scope(value: str) -> PreprocessRunScope:
        if value not in {"FULL_DOCUMENT", "PAGE_SUBSET", "COMPOSED_FULL_DOCUMENT"}:
            raise DocumentStoreUnavailableError("Unexpected preprocess run scope persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_preprocess_page_result_status(value: str) -> PreprocessPageResultStatus:
        if value not in {"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"}:
            raise DocumentStoreUnavailableError(
                "Unexpected preprocess page result status persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_page_layout_result_status(value: str) -> PageLayoutResultStatus:
        if value not in {"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"}:
            raise DocumentStoreUnavailableError(
                "Unexpected page layout result status persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_page_recall_status(value: str) -> PageRecallStatus:
        if value not in {"COMPLETE", "NEEDS_RESCUE", "NEEDS_MANUAL_REVIEW"}:
            raise DocumentStoreUnavailableError("Unexpected page recall status persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_layout_version_kind(value: str) -> LayoutVersionKind:
        if value not in {"SEGMENTATION_EDIT", "READING_ORDER_EDIT"}:
            raise DocumentStoreUnavailableError("Unexpected layout version kind persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_layout_rescue_candidate_kind(value: str) -> LayoutRescueCandidateKind:
        if value not in {"LINE_EXPANSION", "PAGE_WINDOW"}:
            raise DocumentStoreUnavailableError(
                "Unexpected layout rescue candidate kind persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_layout_rescue_candidate_status(value: str) -> LayoutRescueCandidateStatus:
        if value not in {"PENDING", "ACCEPTED", "REJECTED", "RESOLVED"}:
            raise DocumentStoreUnavailableError(
                "Unexpected layout rescue candidate status persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_preprocess_quality_gate_status(value: str) -> PreprocessQualityGateStatus:
        if value not in {"PASS", "REVIEW_REQUIRED", "BLOCKED"}:
            raise DocumentStoreUnavailableError(
                "Unexpected preprocess quality-gate status persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_source_color_mode(value: str) -> SourceColorMode:
        if value not in {"RGB", "RGBA", "GRAY", "CMYK", "UNKNOWN"}:
            raise DocumentStoreUnavailableError("Unexpected page source color mode persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_downstream_basis_state(value: str) -> DownstreamBasisState:
        if value not in {"NOT_STARTED", "CURRENT", "STALE"}:
            raise DocumentStoreUnavailableError(
                "Unexpected downstream basis state persisted."
            )
        return value  # type: ignore[return-value]

    @classmethod
    def _as_document_record(cls, row: dict[str, object]) -> DocumentRecord:
        return DocumentRecord(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            original_filename=str(row["original_filename"]),
            stored_filename=(
                row["stored_filename"]
                if isinstance(row["stored_filename"], str)
                else None
            ),
            content_type_detected=(
                row["content_type_detected"]
                if isinstance(row["content_type_detected"], str)
                else None
            ),
            bytes=row["bytes"] if isinstance(row["bytes"], int) else None,
            sha256=row["sha256"] if isinstance(row["sha256"], str) else None,
            page_count=row["page_count"] if isinstance(row["page_count"], int) else None,
            status=cls._assert_document_status(str(row["status"])),
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_document_import_record(cls, row: dict[str, object]) -> DocumentImportRecord:
        return DocumentImportRecord(
            id=str(row["id"]),
            document_id=str(row["document_id"]),
            status=cls._assert_document_import_status(str(row["status"])),
            failure_reason=(
                row["failure_reason"]
                if isinstance(row["failure_reason"], str)
                else None
            ),
            created_by=str(row["created_by"]),
            accepted_at=row["accepted_at"],  # type: ignore[arg-type]
            rejected_at=row["rejected_at"],  # type: ignore[arg-type]
            canceled_by=row["canceled_by"] if isinstance(row["canceled_by"], str) else None,
            canceled_at=row["canceled_at"],  # type: ignore[arg-type]
            created_at=row["created_at"],  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_processing_run_record(cls, row: dict[str, object]) -> DocumentProcessingRunRecord:
        return DocumentProcessingRunRecord(
            id=str(row["id"]),
            document_id=str(row["document_id"]),
            attempt_number=int(row["attempt_number"]),
            run_kind=cls._assert_processing_run_kind(str(row["run_kind"])),
            supersedes_processing_run_id=(
                row["supersedes_processing_run_id"]
                if isinstance(row["supersedes_processing_run_id"], str)
                else None
            ),
            superseded_by_processing_run_id=(
                row["superseded_by_processing_run_id"]
                if isinstance(row["superseded_by_processing_run_id"], str)
                else None
            ),
            status=cls._assert_processing_run_status(str(row["status"])),
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
            started_at=row["started_at"],  # type: ignore[arg-type]
            finished_at=row["finished_at"],  # type: ignore[arg-type]
            canceled_by=row["canceled_by"] if isinstance(row["canceled_by"], str) else None,
            canceled_at=row["canceled_at"],  # type: ignore[arg-type]
            failure_reason=row["failure_reason"] if isinstance(row["failure_reason"], str) else None,
        )

    @classmethod
    def _as_upload_session_record(cls, row: dict[str, object]) -> DocumentUploadSessionRecord:
        return DocumentUploadSessionRecord(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            document_id=str(row["document_id"]),
            import_id=str(row["import_id"]),
            original_filename=str(row["original_filename"]),
            status=cls._assert_upload_session_status(str(row["status"])),
            expected_sha256=row["expected_sha256"] if isinstance(row["expected_sha256"], str) else None,
            expected_total_bytes=(
                int(row["expected_total_bytes"])
                if isinstance(row["expected_total_bytes"], int)
                else None
            ),
            bytes_received=int(row["bytes_received"]),
            last_chunk_index=int(row["last_chunk_index"]),
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
            completed_at=row["completed_at"],  # type: ignore[arg-type]
            canceled_at=row["canceled_at"],  # type: ignore[arg-type]
            failure_reason=row["failure_reason"] if isinstance(row["failure_reason"], str) else None,
        )

    @classmethod
    def _as_page_record(cls, row: dict[str, object]) -> DocumentPageRecord:
        return DocumentPageRecord(
            id=str(row["id"]),
            document_id=str(row["document_id"]),
            page_index=int(row["page_index"]),
            width=int(row["width"]),
            height=int(row["height"]),
            dpi=row["dpi"] if isinstance(row["dpi"], int) else None,
            source_width=int(row["source_width"]),
            source_height=int(row["source_height"]),
            source_dpi=row["source_dpi"] if isinstance(row["source_dpi"], int) else None,
            source_color_mode=cls._assert_source_color_mode(str(row["source_color_mode"])),
            status=cls._assert_page_status(str(row["status"])),
            derived_image_key=(
                row["derived_image_key"] if isinstance(row["derived_image_key"], str) else None
            ),
            derived_image_sha256=(
                row["derived_image_sha256"]
                if isinstance(row["derived_image_sha256"], str)
                else None
            ),
            thumbnail_key=row["thumbnail_key"] if isinstance(row["thumbnail_key"], str) else None,
            thumbnail_sha256=(
                row["thumbnail_sha256"] if isinstance(row["thumbnail_sha256"], str) else None
            ),
            failure_reason=(
                row["failure_reason"] if isinstance(row["failure_reason"], str) else None
            ),
            canceled_by=row["canceled_by"] if isinstance(row["canceled_by"], str) else None,
            canceled_at=row["canceled_at"],  # type: ignore[arg-type]
            viewer_rotation=int(row["viewer_rotation"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_preprocess_run_record(cls, row: dict[str, object]) -> PreprocessRunRecord:
        params_json = row.get("params_json") if isinstance(row.get("params_json"), dict) else {}
        target_page_ids_json: list[str] | None = None
        raw_target_page_ids = row.get("target_page_ids_json")
        if isinstance(raw_target_page_ids, list):
            target_page_ids_json = [str(value) for value in raw_target_page_ids]
        composed_from_run_ids_json: list[str] | None = None
        raw_composed_from_run_ids = row.get("composed_from_run_ids_json")
        if isinstance(raw_composed_from_run_ids, list):
            composed_from_run_ids_json = [str(value) for value in raw_composed_from_run_ids]
        return PreprocessRunRecord(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            document_id=str(row["document_id"]),
            parent_run_id=row["parent_run_id"] if isinstance(row["parent_run_id"], str) else None,
            attempt_number=int(row["attempt_number"]),
            superseded_by_run_id=(
                row["superseded_by_run_id"]
                if isinstance(row["superseded_by_run_id"], str)
                else None
            ),
            profile_id=str(row["profile_id"]),
            params_json=params_json,
            params_hash=str(row["params_hash"]),
            pipeline_version=str(row["pipeline_version"]),
            container_digest=str(row["container_digest"]),
            status=cls._assert_preprocess_run_status(str(row["status"])),
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
            started_at=row["started_at"],  # type: ignore[arg-type]
            finished_at=row["finished_at"],  # type: ignore[arg-type]
            failure_reason=row["failure_reason"] if isinstance(row["failure_reason"], str) else None,
            profile_version=(
                str(row["profile_version"])
                if isinstance(row.get("profile_version"), str)
                else "v1"
            ),
            profile_revision=(
                int(row["profile_revision"])
                if isinstance(row.get("profile_revision"), int)
                else 1
            ),
            profile_label=(
                str(row["profile_label"]) if isinstance(row.get("profile_label"), str) else ""
            ),
            profile_description=(
                str(row["profile_description"])
                if isinstance(row.get("profile_description"), str)
                else ""
            ),
            profile_params_hash=(
                str(row["profile_params_hash"])
                if isinstance(row.get("profile_params_hash"), str)
                else ""
            ),
            profile_is_advanced=bool(row.get("profile_is_advanced", False)),
            profile_is_gated=bool(row.get("profile_is_gated", False)),
            manifest_object_key=(
                str(row["manifest_object_key"])
                if isinstance(row.get("manifest_object_key"), str)
                else None
            ),
            manifest_sha256=(
                str(row["manifest_sha256"])
                if isinstance(row.get("manifest_sha256"), str)
                else None
            ),
            manifest_schema_version=(
                int(row["manifest_schema_version"])
                if isinstance(row.get("manifest_schema_version"), int)
                else 1
            ),
            run_scope=cls._assert_preprocess_run_scope(
                str(row.get("run_scope") or "FULL_DOCUMENT")
            ),
            target_page_ids_json=target_page_ids_json,
            composed_from_run_ids_json=composed_from_run_ids_json,
        )

    @classmethod
    def _as_preprocess_page_result_record(
        cls,
        row: dict[str, object],
    ) -> PagePreprocessResultRecord:
        metrics_json = row["metrics_json"] if isinstance(row["metrics_json"], dict) else {}
        warnings_json: list[str] = []
        if isinstance(row["warnings_json"], list):
            warnings_json = [str(entry) for entry in row["warnings_json"]]
        return PagePreprocessResultRecord(
            run_id=str(row["run_id"]),
            page_id=str(row["page_id"]),
            page_index=int(row["page_index"]),
            status=cls._assert_preprocess_page_result_status(str(row["status"])),
            quality_gate_status=cls._assert_preprocess_quality_gate_status(
                str(row["quality_gate_status"])
            ),
            input_object_key=(
                row["input_object_key"] if isinstance(row["input_object_key"], str) else None
            ),
            output_object_key_gray=(
                row["output_object_key_gray"]
                if isinstance(row["output_object_key_gray"], str)
                else None
            ),
            output_object_key_bin=(
                row["output_object_key_bin"]
                if isinstance(row["output_object_key_bin"], str)
                else None
            ),
            metrics_json=metrics_json,
            sha256_gray=row["sha256_gray"] if isinstance(row["sha256_gray"], str) else None,
            sha256_bin=row["sha256_bin"] if isinstance(row["sha256_bin"], str) else None,
            warnings_json=warnings_json,
            failure_reason=row["failure_reason"] if isinstance(row["failure_reason"], str) else None,
            created_at=row["created_at"],  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
            input_sha256=(
                str(row["input_sha256"]) if isinstance(row.get("input_sha256"), str) else None
            ),
            source_result_run_id=(
                str(row["source_result_run_id"])
                if isinstance(row.get("source_result_run_id"), str)
                else None
            ),
            metrics_object_key=(
                str(row["metrics_object_key"])
                if isinstance(row.get("metrics_object_key"), str)
                else None
            ),
            metrics_sha256=(
                str(row["metrics_sha256"])
                if isinstance(row.get("metrics_sha256"), str)
                else None
            ),
        )

    @classmethod
    def _as_layout_run_record(cls, row: dict[str, object]) -> LayoutRunRecord:
        params_json = row.get("params_json") if isinstance(row.get("params_json"), dict) else {}
        return LayoutRunRecord(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            document_id=str(row["document_id"]),
            input_preprocess_run_id=str(row["input_preprocess_run_id"]),
            run_kind=cls._assert_layout_run_kind(str(row["run_kind"])),
            parent_run_id=(
                str(row["parent_run_id"])
                if isinstance(row.get("parent_run_id"), str)
                else None
            ),
            attempt_number=int(row["attempt_number"]),
            superseded_by_run_id=(
                str(row["superseded_by_run_id"])
                if isinstance(row.get("superseded_by_run_id"), str)
                else None
            ),
            model_id=str(row["model_id"]) if isinstance(row.get("model_id"), str) else None,
            profile_id=(
                str(row["profile_id"]) if isinstance(row.get("profile_id"), str) else None
            ),
            params_json=params_json,
            params_hash=str(row["params_hash"]),
            pipeline_version=str(row["pipeline_version"]),
            container_digest=str(row["container_digest"]),
            status=cls._assert_layout_run_status(str(row["status"])),
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
            started_at=row["started_at"],  # type: ignore[arg-type]
            finished_at=row["finished_at"],  # type: ignore[arg-type]
            failure_reason=(
                str(row["failure_reason"])
                if isinstance(row.get("failure_reason"), str)
                else None
            ),
        )

    @classmethod
    def _as_approved_model_record(cls, row: dict[str, object]) -> ApprovedModelRecord:
        metadata_json = row.get("metadata_json") if isinstance(row.get("metadata_json"), dict) else {}
        return ApprovedModelRecord(
            id=str(row["id"]),
            model_type=cls._assert_approved_model_type(str(row["model_type"])),
            model_role=cls._assert_approved_model_role(str(row["model_role"])),
            model_family=str(row["model_family"]),
            model_version=str(row["model_version"]),
            serving_interface=cls._assert_approved_model_serving_interface(
                str(row["serving_interface"])
            ),
            engine_family=str(row["engine_family"]),
            deployment_unit=str(row["deployment_unit"]),
            artifact_subpath=str(row["artifact_subpath"]),
            checksum_sha256=str(row["checksum_sha256"]),
            runtime_profile=str(row["runtime_profile"]),
            response_contract_version=str(row["response_contract_version"]),
            metadata_json=metadata_json,
            status=cls._assert_approved_model_status(str(row["status"])),
            approved_by=(
                str(row["approved_by"]) if isinstance(row.get("approved_by"), str) else None
            ),
            approved_at=row.get("approved_at"),  # type: ignore[arg-type]
            created_at=row["created_at"],  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_project_model_assignment_record(
        cls,
        row: dict[str, object],
    ) -> ProjectModelAssignmentRecord:
        return ProjectModelAssignmentRecord(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            model_role=cls._assert_approved_model_role(str(row["model_role"])),
            approved_model_id=str(row["approved_model_id"]),
            status=cls._assert_project_model_assignment_status(str(row["status"])),
            assignment_reason=str(row["assignment_reason"]),
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
            activated_by=(
                str(row["activated_by"])
                if isinstance(row.get("activated_by"), str)
                else None
            ),
            activated_at=row.get("activated_at"),  # type: ignore[arg-type]
            retired_by=(
                str(row["retired_by"]) if isinstance(row.get("retired_by"), str) else None
            ),
            retired_at=row.get("retired_at"),  # type: ignore[arg-type]
        )

    @classmethod
    def _as_training_dataset_record(
        cls,
        row: dict[str, object],
    ) -> TrainingDatasetRecord:
        return TrainingDatasetRecord(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            source_approved_model_id=(
                str(row["source_approved_model_id"])
                if isinstance(row.get("source_approved_model_id"), str)
                else None
            ),
            project_model_assignment_id=(
                str(row["project_model_assignment_id"])
                if isinstance(row.get("project_model_assignment_id"), str)
                else None
            ),
            dataset_kind=cls._assert_training_dataset_kind(str(row["dataset_kind"])),
            page_count=int(row["page_count"]),
            storage_key=str(row["storage_key"]),
            dataset_sha256=str(row["dataset_sha256"]),
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_transcription_run_record(
        cls,
        row: dict[str, object],
    ) -> TranscriptionRunRecord:
        params_json = row.get("params_json") if isinstance(row.get("params_json"), dict) else {}
        return TranscriptionRunRecord(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            document_id=str(row["document_id"]),
            input_preprocess_run_id=str(row["input_preprocess_run_id"]),
            input_layout_run_id=str(row["input_layout_run_id"]),
            input_layout_snapshot_hash=str(row["input_layout_snapshot_hash"]),
            engine=cls._assert_transcription_run_engine(str(row["engine"])),
            model_id=str(row["model_id"]),
            project_model_assignment_id=(
                str(row["project_model_assignment_id"])
                if isinstance(row.get("project_model_assignment_id"), str)
                else None
            ),
            prompt_template_id=(
                str(row["prompt_template_id"])
                if isinstance(row.get("prompt_template_id"), str)
                else None
            ),
            prompt_template_sha256=(
                str(row["prompt_template_sha256"])
                if isinstance(row.get("prompt_template_sha256"), str)
                else None
            ),
            response_schema_version=(
                int(row["response_schema_version"])
                if isinstance(row.get("response_schema_version"), int)
                else 1
            ),
            confidence_basis=cls._assert_transcription_confidence_basis(
                str(row.get("confidence_basis") or "MODEL_NATIVE")
            ),
            confidence_calibration_version=str(
                row.get("confidence_calibration_version") or "v1"
            ),
            params_json=params_json,
            pipeline_version=str(row["pipeline_version"]),
            container_digest=str(row["container_digest"]),
            attempt_number=int(row["attempt_number"]),
            supersedes_transcription_run_id=(
                str(row["supersedes_transcription_run_id"])
                if isinstance(row.get("supersedes_transcription_run_id"), str)
                else None
            ),
            superseded_by_transcription_run_id=(
                str(row["superseded_by_transcription_run_id"])
                if isinstance(row.get("superseded_by_transcription_run_id"), str)
                else None
            ),
            status=cls._assert_transcription_run_status(str(row["status"])),
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
            started_at=row.get("started_at"),  # type: ignore[arg-type]
            finished_at=row.get("finished_at"),  # type: ignore[arg-type]
            canceled_by=(
                str(row["canceled_by"]) if isinstance(row.get("canceled_by"), str) else None
            ),
            canceled_at=row.get("canceled_at"),  # type: ignore[arg-type]
            failure_reason=(
                str(row["failure_reason"])
                if isinstance(row.get("failure_reason"), str)
                else None
            ),
        )

    @classmethod
    def _as_page_transcription_result_record(
        cls,
        row: dict[str, object],
    ) -> PageTranscriptionResultRecord:
        metrics_json = row.get("metrics_json") if isinstance(row.get("metrics_json"), dict) else {}
        warnings_json: list[str] = []
        if isinstance(row.get("warnings_json"), list):
            warnings_json = [str(value) for value in row["warnings_json"]]
        return PageTranscriptionResultRecord(
            run_id=str(row["run_id"]),
            page_id=str(row["page_id"]),
            page_index=int(row["page_index"]),
            status=cls._assert_transcription_run_status(str(row["status"])),
            pagexml_out_key=(
                str(row["pagexml_out_key"])
                if isinstance(row.get("pagexml_out_key"), str)
                else None
            ),
            pagexml_out_sha256=(
                str(row["pagexml_out_sha256"])
                if isinstance(row.get("pagexml_out_sha256"), str)
                else None
            ),
            raw_model_response_key=(
                str(row["raw_model_response_key"])
                if isinstance(row.get("raw_model_response_key"), str)
                else None
            ),
            raw_model_response_sha256=(
                str(row["raw_model_response_sha256"])
                if isinstance(row.get("raw_model_response_sha256"), str)
                else None
            ),
            hocr_out_key=(
                str(row["hocr_out_key"]) if isinstance(row.get("hocr_out_key"), str) else None
            ),
            hocr_out_sha256=(
                str(row["hocr_out_sha256"])
                if isinstance(row.get("hocr_out_sha256"), str)
                else None
            ),
            metrics_json=metrics_json,
            warnings_json=warnings_json,
            failure_reason=(
                str(row["failure_reason"])
                if isinstance(row.get("failure_reason"), str)
                else None
            ),
            created_at=row["created_at"],  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_line_transcription_result_record(
        cls,
        row: dict[str, object],
    ) -> LineTranscriptionResultRecord:
        flags_json = row.get("flags_json") if isinstance(row.get("flags_json"), dict) else {}
        conf_line = row.get("conf_line")
        return LineTranscriptionResultRecord(
            run_id=str(row["run_id"]),
            page_id=str(row["page_id"]),
            line_id=str(row["line_id"]),
            text_diplomatic=str(row.get("text_diplomatic") or ""),
            conf_line=float(conf_line) if isinstance(conf_line, (float, int)) else None,
            confidence_basis=cls._assert_transcription_confidence_basis(
                str(row.get("confidence_basis") or "MODEL_NATIVE")
            ),
            confidence_calibration_version=str(
                row.get("confidence_calibration_version") or "v1"
            ),
            alignment_json_key=(
                str(row["alignment_json_key"])
                if isinstance(row.get("alignment_json_key"), str)
                else None
            ),
            char_boxes_key=(
                str(row["char_boxes_key"])
                if isinstance(row.get("char_boxes_key"), str)
                else None
            ),
            schema_validation_status=cls._assert_transcription_line_schema_status(
                str(row.get("schema_validation_status") or "VALID")
            ),
            flags_json=flags_json,
            machine_output_sha256=(
                str(row["machine_output_sha256"])
                if isinstance(row.get("machine_output_sha256"), str)
                else None
            ),
            active_transcript_version_id=(
                str(row["active_transcript_version_id"])
                if isinstance(row.get("active_transcript_version_id"), str)
                else None
            ),
            version_etag=str(row["version_etag"]),
            token_anchor_status=cls._assert_token_anchor_status(
                str(row.get("token_anchor_status") or "REFRESH_REQUIRED")
            ),
            created_at=row["created_at"],  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_token_transcription_result_record(
        cls,
        row: dict[str, object],
    ) -> TokenTranscriptionResultRecord:
        bbox_json = row.get("bbox_json") if isinstance(row.get("bbox_json"), dict) else None
        polygon_json = (
            row.get("polygon_json") if isinstance(row.get("polygon_json"), dict) else None
        )
        token_confidence = row.get("token_confidence")
        return TokenTranscriptionResultRecord(
            run_id=str(row["run_id"]),
            page_id=str(row["page_id"]),
            line_id=str(row["line_id"]) if isinstance(row.get("line_id"), str) else None,
            token_id=str(row["token_id"]),
            token_index=int(row["token_index"]),
            token_text=str(row.get("token_text") or ""),
            token_confidence=(
                float(token_confidence)
                if isinstance(token_confidence, (float, int))
                else None
            ),
            bbox_json=bbox_json,
            polygon_json=polygon_json,
            source_kind=cls._assert_transcription_token_source_kind(
                str(row.get("source_kind") or "LINE")
            ),
            source_ref_id=str(row.get("source_ref_id") or ""),
            projection_basis=cls._assert_transcription_projection_basis(
                str(row.get("projection_basis") or "ENGINE_OUTPUT")
            ),
            created_at=row["created_at"],  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_transcript_version_record(
        cls,
        row: dict[str, object],
    ) -> TranscriptVersionRecord:
        return TranscriptVersionRecord(
            id=str(row["id"]),
            run_id=str(row["run_id"]),
            page_id=str(row["page_id"]),
            line_id=str(row["line_id"]),
            base_version_id=(
                str(row["base_version_id"])
                if isinstance(row.get("base_version_id"), str)
                else None
            ),
            superseded_by_version_id=(
                str(row["superseded_by_version_id"])
                if isinstance(row.get("superseded_by_version_id"), str)
                else None
            ),
            version_etag=str(row["version_etag"]),
            text_diplomatic=str(row.get("text_diplomatic") or ""),
            editor_user_id=str(row["editor_user_id"]),
            edit_reason=str(row["edit_reason"]) if isinstance(row.get("edit_reason"), str) else None,
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_transcription_projection_record(
        cls,
        row: dict[str, object],
    ) -> DocumentTranscriptionProjectionRecord:
        return DocumentTranscriptionProjectionRecord(
            document_id=str(row["document_id"]),
            project_id=str(row["project_id"]),
            active_transcription_run_id=(
                str(row["active_transcription_run_id"])
                if isinstance(row.get("active_transcription_run_id"), str)
                else None
            ),
            active_layout_run_id=(
                str(row["active_layout_run_id"])
                if isinstance(row.get("active_layout_run_id"), str)
                else None
            ),
            active_layout_snapshot_hash=(
                str(row["active_layout_snapshot_hash"])
                if isinstance(row.get("active_layout_snapshot_hash"), str)
                else None
            ),
            active_preprocess_run_id=(
                str(row["active_preprocess_run_id"])
                if isinstance(row.get("active_preprocess_run_id"), str)
                else None
            ),
            downstream_redaction_state=cls._assert_downstream_basis_state(
                str(row.get("downstream_redaction_state") or "NOT_STARTED")
            ),
            downstream_redaction_invalidated_at=row.get(
                "downstream_redaction_invalidated_at"
            ),  # type: ignore[arg-type]
            downstream_redaction_invalidated_reason=(
                str(row["downstream_redaction_invalidated_reason"])
                if isinstance(row.get("downstream_redaction_invalidated_reason"), str)
                else None
            ),
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_transcription_output_projection_record(
        cls,
        row: dict[str, object],
    ) -> TranscriptionOutputProjectionRecord:
        return TranscriptionOutputProjectionRecord(
            run_id=str(row["run_id"]),
            document_id=str(row["document_id"]),
            page_id=str(row["page_id"]),
            corrected_pagexml_key=str(row["corrected_pagexml_key"]),
            corrected_pagexml_sha256=str(row["corrected_pagexml_sha256"]),
            corrected_text_sha256=str(row["corrected_text_sha256"]),
            source_pagexml_sha256=str(row["source_pagexml_sha256"]),
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @staticmethod
    def _layout_activation_page_refs(
        rows: list[dict[str, object]],
    ) -> tuple[tuple[str, ...], tuple[int, ...]]:
        page_ids = tuple(
            sorted(
                {
                    str(row["page_id"])
                    for row in rows
                    if isinstance(row.get("page_id"), str)
                }
            )
        )
        page_numbers = tuple(
            sorted(
                {
                    int(row["page_index"]) + 1
                    for row in rows
                    if isinstance(row.get("page_index"), int)
                    or isinstance(row.get("page_index"), float)
                }
            )
        )
        return page_ids, page_numbers

    def _build_layout_activation_blocker(
        self,
        *,
        code: LayoutActivationBlockerCode,
        message: str,
        rows: list[dict[str, object]] | None = None,
        count_override: int | None = None,
    ) -> LayoutActivationBlockerRecord:
        safe_rows = rows or []
        page_ids, page_numbers = self._layout_activation_page_refs(safe_rows)
        if count_override is not None:
            count = max(0, int(count_override))
        elif page_numbers:
            count = len(page_numbers)
        elif page_ids:
            count = len(page_ids)
        else:
            count = 0
        return LayoutActivationBlockerRecord(
            code=code,
            message=message,
            count=count,
            page_ids=page_ids,
            page_numbers=page_numbers,
        )

    @staticmethod
    def _format_layout_activation_gate_detail(
        gate: LayoutActivationGateRecord,
    ) -> str:
        if gate.eligible or not gate.blockers:
            return "Activation is blocked by layout gate validation."
        first = gate.blockers[0]
        suffix = (
            f" (+{gate.blocker_count - 1} additional blocker(s))"
            if gate.blocker_count > 1
            else ""
        )
        return f"Activation is blocked [{first.code}]: {first.message}{suffix}"

    def _evaluate_layout_activation_gate_from_cursor(
        self,
        *,
        cursor: object,
        project_id: str,
        document_id: str,
        run_id: str,
        run_status: LayoutRunStatus,
        lock_rows: bool,
    ) -> LayoutActivationGateRecord:
        gate_cursor = cursor
        if not hasattr(gate_cursor, "execute") or not hasattr(gate_cursor, "fetchall"):
            raise DocumentStoreUnavailableError("Layout activation gate evaluation failed.")
        lock_clause = "FOR UPDATE" if lock_rows else ""
        blockers: list[LayoutActivationBlockerRecord] = []

        if run_status != "SUCCEEDED":
            blockers.append(
                self._build_layout_activation_blocker(
                    code="LAYOUT_RUN_NOT_SUCCEEDED",
                    message=(
                        "Only SUCCEEDED layout runs can be activated; "
                        f"current status is {run_status}."
                    ),
                    count_override=1,
                )
            )

        gate_cursor.execute(
            f"""
            SELECT
              plr.page_id,
              plr.page_index,
              plr.status,
              plr.page_recall_status
            FROM page_layout_results AS plr
            WHERE plr.run_id = %(run_id)s
            ORDER BY plr.page_index ASC
            {lock_clause}
            """,
            {"run_id": run_id},
        )
        page_rows = gate_cursor.fetchall()
        if not page_rows:
            blockers.append(
                self._build_layout_activation_blocker(
                    code="LAYOUT_RECALL_PAGE_RESULTS_MISSING",
                    message="Run has no page layout results.",
                    count_override=1,
                )
            )
        else:
            explicit_recall_rows = [
                row
                for row in page_rows
                if str(row.get("page_recall_status") or "").strip()
                not in {"COMPLETE", "NEEDS_RESCUE", "NEEDS_MANUAL_REVIEW"}
            ]
            if explicit_recall_rows:
                blockers.append(
                    self._build_layout_activation_blocker(
                        code="LAYOUT_RECALL_STATUS_MISSING",
                        message=(
                            f"{len(explicit_recall_rows)} page(s) are missing explicit "
                            "page recall status."
                        ),
                        rows=explicit_recall_rows,
                    )
                )

            unresolved_rows = [
                row
                for row in page_rows
                if str(row.get("status") or "").strip() != "SUCCEEDED"
            ]
            if unresolved_rows:
                blockers.append(
                    self._build_layout_activation_blocker(
                        code="LAYOUT_RECALL_STATUS_UNRESOLVED",
                        message=(
                            f"{len(unresolved_rows)} page(s) are not in SUCCEEDED status."
                        ),
                        rows=unresolved_rows,
                    )
                )

            gate_cursor.execute(
                """
                SELECT
                  plr.page_id,
                  plr.page_index
                FROM page_layout_results AS plr
                LEFT JOIN layout_recall_checks AS lrc
                  ON lrc.run_id = plr.run_id
                 AND lrc.page_id = plr.page_id
                WHERE plr.run_id = %(run_id)s
                  AND lrc.run_id IS NULL
                ORDER BY plr.page_index ASC
                """,
                {"run_id": run_id},
            )
            missing_recall_rows = gate_cursor.fetchall()
            if missing_recall_rows:
                blockers.append(
                    self._build_layout_activation_blocker(
                        code="LAYOUT_RECALL_CHECK_MISSING",
                        message=(
                            f"{len(missing_recall_rows)} page(s) are missing "
                            "persisted recall-check records."
                        ),
                        rows=missing_recall_rows,
                    )
                )

            gate_cursor.execute(
                """
                SELECT
                  plr.page_id,
                  plr.page_index,
                  COUNT(*)::INT AS pending_candidates
                FROM page_layout_results AS plr
                INNER JOIN layout_rescue_candidates AS lrc
                  ON lrc.run_id = plr.run_id
                 AND lrc.page_id = plr.page_id
                 AND lrc.status = 'PENDING'
                WHERE plr.run_id = %(run_id)s
                GROUP BY plr.page_id, plr.page_index
                ORDER BY plr.page_index ASC
                """,
                {"run_id": run_id},
            )
            pending_rows = gate_cursor.fetchall()
            if pending_rows:
                pending_count = sum(
                    int(row.get("pending_candidates") or 0) for row in pending_rows
                )
                blockers.append(
                    self._build_layout_activation_blocker(
                        code="LAYOUT_RESCUE_PENDING",
                        message=(
                            f"{len(pending_rows)} page(s) still have PENDING "
                            "rescue candidates."
                        ),
                        rows=pending_rows,
                        count_override=pending_count
                        if pending_count > 0
                        else len(pending_rows),
                    )
                )

            gate_cursor.execute(
                """
                SELECT
                  plr.page_id,
                  plr.page_index
                FROM page_layout_results AS plr
                LEFT JOIN LATERAL (
                  SELECT
                    COUNT(*)::INT AS accepted_count
                  FROM layout_rescue_candidates AS lrc
                  WHERE lrc.run_id = plr.run_id
                    AND lrc.page_id = plr.page_id
                    AND lrc.status = 'ACCEPTED'
                ) AS accepted ON TRUE
                WHERE plr.run_id = %(run_id)s
                  AND plr.page_recall_status = 'NEEDS_RESCUE'
                  AND COALESCE(accepted.accepted_count, 0) = 0
                ORDER BY plr.page_index ASC
                """,
                {"run_id": run_id},
            )
            rescue_acceptance_rows = gate_cursor.fetchall()
            if rescue_acceptance_rows:
                blockers.append(
                    self._build_layout_activation_blocker(
                        code="LAYOUT_RESCUE_ACCEPTANCE_MISSING",
                        message=(
                            f"{len(rescue_acceptance_rows)} NEEDS_RESCUE page(s) "
                            "have no ACCEPTED rescue candidate."
                        ),
                        rows=rescue_acceptance_rows,
                    )
                )

        layout_snapshot_hash = self._compute_layout_run_snapshot_hash(
            cursor=gate_cursor,
            run_id=run_id,
            lock_rows=lock_rows,
        )
        gate_cursor.execute(
            f"""
            SELECT
              tp.active_transcription_run_id,
              tp.active_layout_run_id,
              tp.active_layout_snapshot_hash
            FROM document_transcription_projections AS tp
            WHERE tp.project_id = %(project_id)s
              AND tp.document_id = %(document_id)s
            LIMIT 1
            {lock_clause}
            """,
            {"project_id": project_id, "document_id": document_id},
        )
        transcription_projection = gate_cursor.fetchone()
        active_transcription_run_id = (
            str(transcription_projection["active_transcription_run_id"])
            if transcription_projection is not None
            and isinstance(transcription_projection.get("active_transcription_run_id"), str)
            and str(transcription_projection["active_transcription_run_id"]).strip() != ""
            else None
        )
        has_active_transcription_projection = active_transcription_run_id is not None
        projection_layout_run_id = (
            str(transcription_projection["active_layout_run_id"])
            if transcription_projection is not None
            and isinstance(transcription_projection.get("active_layout_run_id"), str)
            and str(transcription_projection["active_layout_run_id"]).strip() != ""
            else None
        )
        projection_layout_snapshot_hash = (
            str(transcription_projection["active_layout_snapshot_hash"])
            if transcription_projection is not None
            and isinstance(
                transcription_projection.get("active_layout_snapshot_hash"), str
            )
            and str(transcription_projection["active_layout_snapshot_hash"]).strip() != ""
            else None
        )

        if not has_active_transcription_projection:
            downstream_impact = LayoutActivationDownstreamImpactRecord(
                transcription_state_after_activation="NOT_STARTED",
                invalidates_existing_transcription_basis=False,
                reason=None,
                has_active_transcription_projection=False,
                active_transcription_run_id=None,
            )
        else:
            is_basis_current = (
                projection_layout_run_id == run_id
                and projection_layout_snapshot_hash is not None
                and projection_layout_snapshot_hash == layout_snapshot_hash
            )
            downstream_impact = LayoutActivationDownstreamImpactRecord(
                transcription_state_after_activation=(
                    "CURRENT" if is_basis_current else "STALE"
                ),
                invalidates_existing_transcription_basis=not is_basis_current,
                reason=None if is_basis_current else _LAYOUT_ACTIVATION_INVALIDATION_REASON,
                has_active_transcription_projection=True,
                active_transcription_run_id=active_transcription_run_id,
            )

        return LayoutActivationGateRecord(
            eligible=len(blockers) == 0,
            blocker_count=len(blockers),
            blockers=tuple(blockers),
            evaluated_at=datetime.now(timezone.utc),
            downstream_impact=downstream_impact,
        )

    def evaluate_layout_activation_gate(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> LayoutActivationGateRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          lr.status
                        FROM layout_runs AS lr
                        WHERE lr.project_id = %(project_id)s
                          AND lr.document_id = %(document_id)s
                          AND lr.id = %(run_id)s
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    run_row = cursor.fetchone()
                    if run_row is None:
                        raise DocumentNotFoundError("Layout run not found.")
                    gate = self._evaluate_layout_activation_gate_from_cursor(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                        run_status=self._assert_layout_run_status(str(run_row["status"])),
                        lock_rows=False,
                    )
        except DocumentNotFoundError:
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Layout activation gate evaluation failed."
            ) from error
        return gate

    @classmethod
    def _as_page_layout_result_record(cls, row: dict[str, object]) -> PageLayoutResultRecord:
        metrics_json = row.get("metrics_json") if isinstance(row.get("metrics_json"), dict) else {}
        warnings_json: list[str] = []
        raw_warnings_json = row.get("warnings_json")
        if isinstance(raw_warnings_json, list):
            warnings_json = [str(entry) for entry in raw_warnings_json]
        return PageLayoutResultRecord(
            run_id=str(row["run_id"]),
            page_id=str(row["page_id"]),
            page_index=int(row["page_index"]),
            status=cls._assert_page_layout_result_status(str(row["status"])),
            page_recall_status=cls._assert_page_recall_status(
                str(row.get("page_recall_status") or "NEEDS_MANUAL_REVIEW")
            ),
            active_layout_version_id=(
                str(row["active_layout_version_id"])
                if isinstance(row.get("active_layout_version_id"), str)
                else None
            ),
            page_xml_key=(
                str(row["page_xml_key"]) if isinstance(row.get("page_xml_key"), str) else None
            ),
            overlay_json_key=(
                str(row["overlay_json_key"])
                if isinstance(row.get("overlay_json_key"), str)
                else None
            ),
            page_xml_sha256=(
                str(row["page_xml_sha256"])
                if isinstance(row.get("page_xml_sha256"), str)
                else None
            ),
            overlay_json_sha256=(
                str(row["overlay_json_sha256"])
                if isinstance(row.get("overlay_json_sha256"), str)
                else None
            ),
            metrics_json=metrics_json,
            warnings_json=warnings_json,
            failure_reason=(
                str(row["failure_reason"])
                if isinstance(row.get("failure_reason"), str)
                else None
            ),
            created_at=row["created_at"],  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_layout_version_record(
        cls,
        row: dict[str, object],
    ) -> LayoutVersionRecord:
        canonical_payload_json = (
            row.get("canonical_payload_json")
            if isinstance(row.get("canonical_payload_json"), dict)
            else {}
        )
        reading_order_groups_json = (
            row.get("reading_order_groups_json")
            if isinstance(row.get("reading_order_groups_json"), list)
            else []
        )
        normalized_groups: list[dict[str, object]] = []
        for raw_group in reading_order_groups_json:
            if isinstance(raw_group, dict):
                normalized_groups.append(dict(raw_group))
        reading_order_meta_json = (
            row.get("reading_order_meta_json")
            if isinstance(row.get("reading_order_meta_json"), dict)
            else {}
        )
        return LayoutVersionRecord(
            id=str(row["id"]),
            run_id=str(row["run_id"]),
            page_id=str(row["page_id"]),
            base_version_id=(
                str(row["base_version_id"])
                if isinstance(row.get("base_version_id"), str)
                else None
            ),
            superseded_by_version_id=(
                str(row["superseded_by_version_id"])
                if isinstance(row.get("superseded_by_version_id"), str)
                else None
            ),
            version_kind=cls._assert_layout_version_kind(str(row["version_kind"])),
            version_etag=str(row["version_etag"]),
            page_xml_key=str(row["page_xml_key"]),
            overlay_json_key=str(row["overlay_json_key"]),
            page_xml_sha256=str(row["page_xml_sha256"]),
            overlay_json_sha256=str(row["overlay_json_sha256"]),
            run_snapshot_hash=str(row["run_snapshot_hash"]),
            canonical_payload_json=canonical_payload_json,
            reading_order_groups_json=normalized_groups,
            reading_order_meta_json=reading_order_meta_json,
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_layout_line_artifact_record(
        cls,
        row: dict[str, object],
    ) -> LayoutLineArtifactRecord:
        return LayoutLineArtifactRecord(
            run_id=str(row["run_id"]),
            page_id=str(row["page_id"]),
            layout_version_id=str(row["layout_version_id"]),
            line_id=str(row["line_id"]),
            region_id=(
                str(row["region_id"]) if isinstance(row.get("region_id"), str) else None
            ),
            line_crop_key=str(row["line_crop_key"]),
            region_crop_key=(
                str(row["region_crop_key"])
                if isinstance(row.get("region_crop_key"), str)
                else None
            ),
            page_thumbnail_key=str(row["page_thumbnail_key"]),
            context_window_json_key=str(row["context_window_json_key"]),
            artifacts_sha256=str(row["artifacts_sha256"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_layout_recall_check_record(
        cls,
        row: dict[str, object],
    ) -> LayoutRecallCheckRecord:
        signals_json = row.get("signals_json") if isinstance(row.get("signals_json"), dict) else {}
        return LayoutRecallCheckRecord(
            run_id=str(row["run_id"]),
            page_id=str(row["page_id"]),
            recall_check_version=str(row["recall_check_version"]),
            missed_text_risk_score=(
                float(row["missed_text_risk_score"])
                if isinstance(row.get("missed_text_risk_score"), (int, float))
                else None
            ),
            signals_json=signals_json,
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_layout_rescue_candidate_record(
        cls,
        row: dict[str, object],
    ) -> LayoutRescueCandidateRecord:
        geometry_json = row.get("geometry_json") if isinstance(row.get("geometry_json"), dict) else {}
        return LayoutRescueCandidateRecord(
            id=str(row["id"]),
            run_id=str(row["run_id"]),
            page_id=str(row["page_id"]),
            candidate_kind=cls._assert_layout_rescue_candidate_kind(
                str(row["candidate_kind"])
            ),
            geometry_json=geometry_json,
            confidence=(
                float(row["confidence"])
                if isinstance(row.get("confidence"), (int, float))
                else None
            ),
            source_signal=(
                str(row["source_signal"])
                if isinstance(row.get("source_signal"), str)
                else None
            ),
            status=cls._assert_layout_rescue_candidate_status(str(row["status"])),
            created_at=row["created_at"],  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_layout_projection_record(
        cls,
        row: dict[str, object],
    ) -> DocumentLayoutProjectionRecord:
        return DocumentLayoutProjectionRecord(
            document_id=str(row["document_id"]),
            project_id=str(row["project_id"]),
            active_layout_run_id=(
                str(row["active_layout_run_id"])
                if isinstance(row.get("active_layout_run_id"), str)
                else None
            ),
            active_input_preprocess_run_id=(
                str(row["active_input_preprocess_run_id"])
                if isinstance(row.get("active_input_preprocess_run_id"), str)
                else None
            ),
            updated_at=row["updated_at"],  # type: ignore[arg-type]
            active_layout_snapshot_hash=(
                str(row["active_layout_snapshot_hash"])
                if isinstance(row.get("active_layout_snapshot_hash"), str)
                else None
            ),
            downstream_transcription_state=cls._assert_downstream_basis_state(
                str(row.get("downstream_transcription_state") or "NOT_STARTED")
            ),
            downstream_transcription_invalidated_at=row.get(
                "downstream_transcription_invalidated_at"
            ),  # type: ignore[arg-type]
            downstream_transcription_invalidated_reason=(
                str(row["downstream_transcription_invalidated_reason"])
                if isinstance(row.get("downstream_transcription_invalidated_reason"), str)
                else None
            ),
        )

    @classmethod
    def _as_preprocess_projection_record(
        cls,
        row: dict[str, object],
    ) -> DocumentPreprocessProjectionRecord:
        return DocumentPreprocessProjectionRecord(
            document_id=str(row["document_id"]),
            project_id=str(row["project_id"]),
            active_preprocess_run_id=(
                row["active_preprocess_run_id"]
                if isinstance(row["active_preprocess_run_id"], str)
                else None
            ),
            active_profile_id=(
                row["active_profile_id"] if isinstance(row["active_profile_id"], str) else None
            ),
            updated_at=row["updated_at"],  # type: ignore[arg-type]
            active_profile_version=(
                str(row["active_profile_version"])
                if isinstance(row.get("active_profile_version"), str)
                else None
            ),
            active_profile_revision=(
                int(row["active_profile_revision"])
                if isinstance(row.get("active_profile_revision"), int)
                else None
            ),
            active_params_hash=(
                str(row["active_params_hash"])
                if isinstance(row.get("active_params_hash"), str)
                else None
            ),
            active_pipeline_version=(
                str(row["active_pipeline_version"])
                if isinstance(row.get("active_pipeline_version"), str)
                else None
            ),
            active_container_digest=(
                str(row["active_container_digest"])
                if isinstance(row.get("active_container_digest"), str)
                else None
            ),
            layout_basis_state=cls._assert_downstream_basis_state(
                str(row.get("layout_basis_state") or "NOT_STARTED")
            ),
            layout_basis_run_id=(
                str(row["layout_basis_run_id"])
                if isinstance(row.get("layout_basis_run_id"), str)
                else None
            ),
            transcription_basis_state=cls._assert_downstream_basis_state(
                str(row.get("transcription_basis_state") or "NOT_STARTED")
            ),
            transcription_basis_run_id=(
                str(row["transcription_basis_run_id"])
                if isinstance(row.get("transcription_basis_run_id"), str)
                else None
            ),
        )

    @classmethod
    def _as_preprocess_profile_registry_record(
        cls,
        row: dict[str, object],
    ) -> PreprocessProfileRegistryRecord:
        params_json = row["params_json"] if isinstance(row["params_json"], dict) else {}
        return PreprocessProfileRegistryRecord(
            profile_id=str(row["profile_id"]),
            profile_version=str(row["profile_version"]),
            profile_revision=int(row["profile_revision"]),
            label=str(row["label"]),
            description=str(row["description"]),
            params_json=params_json,
            params_hash=str(row["params_hash"]),
            is_advanced=bool(row["is_advanced"]),
            is_gated=bool(row["is_gated"]),
            supersedes_profile_id=(
                str(row["supersedes_profile_id"])
                if isinstance(row["supersedes_profile_id"], str)
                else None
            ),
            supersedes_profile_revision=(
                int(row["supersedes_profile_revision"])
                if isinstance(row["supersedes_profile_revision"], int)
                else None
            ),
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @staticmethod
    def _serialize_json_payload(payload: dict[str, object]) -> str:
        return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))

    def _seed_preprocess_profile_registry(self, cursor: psycopg.Cursor) -> None:
        for definition in list_preprocess_profile_definitions():
            cursor.execute(
                """
                INSERT INTO preprocess_profile_registry (
                  profile_id,
                  profile_version,
                  profile_revision,
                  label,
                  description,
                  params_json,
                  params_hash,
                  is_advanced,
                  is_gated,
                  supersedes_profile_id,
                  supersedes_profile_revision
                )
                VALUES (
                  %(profile_id)s,
                  %(profile_version)s,
                  %(profile_revision)s,
                  %(label)s,
                  %(description)s,
                  %(params_json)s::jsonb,
                  %(params_hash)s,
                  %(is_advanced)s,
                  %(is_gated)s,
                  %(supersedes_profile_id)s,
                  %(supersedes_profile_revision)s
                )
                ON CONFLICT (profile_id, profile_revision) DO NOTHING
                """,
                {
                    "profile_id": definition.profile_id,
                    "profile_version": definition.profile_version,
                    "profile_revision": definition.profile_revision,
                    "label": definition.label,
                    "description": definition.description,
                    "params_json": self._serialize_json_payload(definition.params_json),
                    "params_hash": definition.params_hash,
                    "is_advanced": definition.is_advanced,
                    "is_gated": definition.is_gated,
                    "supersedes_profile_id": definition.supersedes_profile_id,
                    "supersedes_profile_revision": definition.supersedes_profile_revision,
                },
            )

    def get_latest_preprocess_profile(
        self,
        *,
        profile_id: str,
    ) -> PreprocessProfileRegistryRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          ppr.profile_id,
                          ppr.profile_version,
                          ppr.profile_revision,
                          ppr.label,
                          ppr.description,
                          ppr.params_json,
                          ppr.params_hash,
                          ppr.is_advanced,
                          ppr.is_gated,
                          ppr.supersedes_profile_id,
                          ppr.supersedes_profile_revision,
                          ppr.created_at
                        FROM preprocess_profile_registry AS ppr
                        WHERE ppr.profile_id = %(profile_id)s
                        ORDER BY ppr.profile_revision DESC
                        LIMIT 1
                        """,
                        {"profile_id": profile_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Preprocess profile registry read failed.") from error
        if row is None:
            return None
        return self._as_preprocess_profile_registry_record(row)

    def list_preprocess_profiles(self) -> list[PreprocessProfileRegistryRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          ppr.profile_id,
                          ppr.profile_version,
                          ppr.profile_revision,
                          ppr.label,
                          ppr.description,
                          ppr.params_json,
                          ppr.params_hash,
                          ppr.is_advanced,
                          ppr.is_gated,
                          ppr.supersedes_profile_id,
                          ppr.supersedes_profile_revision,
                          ppr.created_at
                        FROM preprocess_profile_registry AS ppr
                        ORDER BY ppr.profile_id ASC, ppr.profile_revision DESC
                        """
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Preprocess profile listing failed.") from error
        return [self._as_preprocess_profile_registry_record(row) for row in rows]

    def ensure_schema(self) -> None:
        if self._schema_initialized:
            return

        try:
            self._project_store.ensure_schema()
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    for statement in DOCUMENT_SCHEMA_STATEMENTS:
                        cursor.execute(statement)
                    self._seed_preprocess_profile_registry(cursor)
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Document schema could not be initialized."
            ) from error

        self._schema_initialized = True

    def list_documents(
        self,
        *,
        project_id: str,
        filters: DocumentListFilters,
    ) -> tuple[list[DocumentRecord], int | None]:
        self.ensure_schema()
        sort_column = {
            "updated": "d.updated_at",
            "created": "d.created_at",
            "name": "LOWER(d.original_filename)",
        }[filters.sort]
        sort_direction = "ASC" if filters.direction == "asc" else "DESC"
        tie_breaker_direction = "ASC" if filters.direction == "asc" else "DESC"

        conditions = ["d.project_id = %(project_id)s"]
        params: dict[str, object] = {
            "project_id": project_id,
            "limit": filters.page_size + 1,
            "offset": filters.cursor,
        }
        if filters.q:
            conditions.append("d.original_filename ILIKE %(query)s")
            params["query"] = f"%{filters.q}%"
        if filters.status:
            conditions.append("d.status = %(status)s")
            params["status"] = filters.status
        if filters.uploader:
            conditions.append("d.created_by ILIKE %(uploader)s")
            params["uploader"] = f"%{filters.uploader}%"
        if filters.from_timestamp:
            conditions.append("d.created_at >= %(from_timestamp)s")
            params["from_timestamp"] = filters.from_timestamp
        if filters.to_timestamp:
            conditions.append("d.created_at <= %(to_timestamp)s")
            params["to_timestamp"] = filters.to_timestamp

        where_clause = " AND ".join(conditions)
        query = f"""
            SELECT
              d.id,
              d.project_id,
              d.original_filename,
              d.stored_filename,
              d.content_type_detected,
              d.bytes,
              d.sha256,
              d.page_count,
              d.status,
              d.created_by,
              d.created_at,
              d.updated_at
            FROM documents AS d
            WHERE {where_clause}
            ORDER BY {sort_column} {sort_direction}, d.id {tie_breaker_direction}
            LIMIT %(limit)s
            OFFSET %(offset)s
        """

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(query, params)
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Document listing failed.") from error

        has_more = len(rows) > filters.page_size
        selected_rows = rows[: filters.page_size]
        next_cursor = filters.cursor + filters.page_size if has_more else None
        return [self._as_document_record(row) for row in selected_rows], next_cursor

    def get_document(
        self,
        *,
        project_id: str,
        document_id: str,
    ) -> DocumentRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          d.id,
                          d.project_id,
                          d.original_filename,
                          d.stored_filename,
                          d.content_type_detected,
                          d.bytes,
                          d.sha256,
                          d.page_count,
                          d.status,
                          d.created_by,
                          d.created_at,
                          d.updated_at
                        FROM documents AS d
                        WHERE d.project_id = %(project_id)s
                          AND d.id = %(document_id)s
                        LIMIT 1
                        """,
                        {"project_id": project_id, "document_id": document_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Document detail read failed.") from error

        if row is None:
            return None
        return self._as_document_record(row)

    def list_document_timeline(
        self,
        *,
        project_id: str,
        document_id: str,
        limit: int = 100,
    ) -> list[DocumentProcessingRunRecord]:
        self.ensure_schema()
        if self.get_document(project_id=project_id, document_id=document_id) is None:
            raise DocumentNotFoundError("Document not found.")

        safe_limit = max(1, min(limit, 200))

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          pr.id,
                          pr.document_id,
                          pr.attempt_number,
                          pr.run_kind,
                          pr.supersedes_processing_run_id,
                          pr.superseded_by_processing_run_id,
                          pr.status,
                          pr.created_by,
                          pr.created_at,
                          pr.started_at,
                          pr.finished_at,
                          pr.canceled_by,
                          pr.canceled_at,
                          pr.failure_reason
                        FROM document_processing_runs AS pr
                        INNER JOIN documents AS d
                          ON d.id = pr.document_id
                        WHERE d.project_id = %(project_id)s
                          AND pr.document_id = %(document_id)s
                        ORDER BY pr.created_at DESC, pr.id DESC
                        LIMIT %(limit)s
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "limit": safe_limit,
                        },
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Document timeline read failed.") from error

        return [self._as_processing_run_record(row) for row in rows]

    def get_processing_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentProcessingRunRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          pr.id,
                          pr.document_id,
                          pr.attempt_number,
                          pr.run_kind,
                          pr.supersedes_processing_run_id,
                          pr.superseded_by_processing_run_id,
                          pr.status,
                          pr.created_by,
                          pr.created_at,
                          pr.started_at,
                          pr.finished_at,
                          pr.canceled_by,
                          pr.canceled_at,
                          pr.failure_reason
                        FROM document_processing_runs AS pr
                        INNER JOIN documents AS d
                          ON d.id = pr.document_id
                        WHERE d.project_id = %(project_id)s
                          AND pr.document_id = %(document_id)s
                          AND pr.id = %(run_id)s
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Document processing run read failed.") from error
        if row is None:
            return None
        return self._as_processing_run_record(row)

    def get_latest_processing_run_by_kind(
        self,
        *,
        project_id: str,
        document_id: str,
        run_kind: DocumentProcessingRunKind,
        include_superseded: bool = False,
    ) -> DocumentProcessingRunRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          pr.id,
                          pr.document_id,
                          pr.attempt_number,
                          pr.run_kind,
                          pr.supersedes_processing_run_id,
                          pr.superseded_by_processing_run_id,
                          pr.status,
                          pr.created_by,
                          pr.created_at,
                          pr.started_at,
                          pr.finished_at,
                          pr.canceled_by,
                          pr.canceled_at,
                          pr.failure_reason
                        FROM document_processing_runs AS pr
                        INNER JOIN documents AS d
                          ON d.id = pr.document_id
                        WHERE d.project_id = %(project_id)s
                          AND pr.document_id = %(document_id)s
                          AND pr.run_kind = %(run_kind)s
                          AND (
                            %(include_superseded)s
                            OR pr.superseded_by_processing_run_id IS NULL
                          )
                        ORDER BY pr.attempt_number DESC, pr.created_at DESC, pr.id DESC
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_kind": run_kind,
                            "include_superseded": include_superseded,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Document processing run lineage read failed."
            ) from error
        if row is None:
            return None
        return self._as_processing_run_record(row)

    def create_upload_records(
        self,
        *,
        project_id: str,
        document_id: str,
        import_id: str,
        original_filename: str,
        created_by: str,
    ) -> None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO documents (
                          id,
                          project_id,
                          original_filename,
                          status,
                          created_by
                        )
                        VALUES (
                          %(document_id)s,
                          %(project_id)s,
                          %(original_filename)s,
                          'UPLOADING',
                          %(created_by)s
                        )
                        """,
                        {
                            "document_id": document_id,
                            "project_id": project_id,
                            "original_filename": original_filename,
                            "created_by": created_by,
                        },
                    )
                    cursor.execute(
                        """
                        INSERT INTO document_imports (
                          id,
                          document_id,
                          status,
                          created_by
                        )
                        VALUES (
                          %(import_id)s,
                          %(document_id)s,
                          'UPLOADING',
                          %(created_by)s
                        )
                        """,
                        {
                            "import_id": import_id,
                            "document_id": document_id,
                            "created_by": created_by,
                        },
                    )
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Document upload could not be initialized.") from error

    def create_upload_session(
        self,
        *,
        project_id: str,
        session_id: str,
        document_id: str,
        import_id: str,
        original_filename: str,
        created_by: str,
        expected_sha256: str | None = None,
        expected_total_bytes: int | None = None,
    ) -> DocumentUploadSessionRecord:
        self.ensure_schema()
        if expected_total_bytes is not None and expected_total_bytes < 0:
            raise DocumentUploadSessionConflictError(
                "expected_total_bytes must be zero or greater."
            )
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO documents (
                          id,
                          project_id,
                          original_filename,
                          status,
                          created_by
                        )
                        VALUES (
                          %(document_id)s,
                          %(project_id)s,
                          %(original_filename)s,
                          'UPLOADING',
                          %(created_by)s
                        )
                        """,
                        {
                            "document_id": document_id,
                            "project_id": project_id,
                            "original_filename": original_filename,
                            "created_by": created_by,
                        },
                    )
                    cursor.execute(
                        """
                        INSERT INTO document_imports (
                          id,
                          document_id,
                          status,
                          created_by
                        )
                        VALUES (
                          %(import_id)s,
                          %(document_id)s,
                          'UPLOADING',
                          %(created_by)s
                        )
                        """,
                        {
                            "import_id": import_id,
                            "document_id": document_id,
                            "created_by": created_by,
                        },
                    )
                    cursor.execute(
                        """
                        INSERT INTO document_upload_sessions (
                          id,
                          project_id,
                          document_id,
                          import_id,
                          original_filename,
                          status,
                          expected_sha256,
                          expected_total_bytes,
                          bytes_received,
                          last_chunk_index,
                          created_by
                        )
                        VALUES (
                          %(id)s,
                          %(project_id)s,
                          %(document_id)s,
                          %(import_id)s,
                          %(original_filename)s,
                          'ACTIVE',
                          %(expected_sha256)s,
                          %(expected_total_bytes)s,
                          0,
                          -1,
                          %(created_by)s
                        )
                        """,
                        {
                            "id": session_id,
                            "project_id": project_id,
                            "document_id": document_id,
                            "import_id": import_id,
                            "original_filename": original_filename,
                            "expected_sha256": expected_sha256,
                            "expected_total_bytes": expected_total_bytes,
                            "created_by": created_by,
                        },
                    )
                    cursor.execute(
                        """
                        SELECT
                          us.id,
                          us.project_id,
                          us.document_id,
                          us.import_id,
                          us.original_filename,
                          us.status,
                          us.expected_sha256,
                          us.expected_total_bytes,
                          us.bytes_received,
                          us.last_chunk_index,
                          us.created_by,
                          us.created_at,
                          us.updated_at,
                          us.completed_at,
                          us.canceled_at,
                          us.failure_reason
                        FROM document_upload_sessions AS us
                        WHERE us.id = %(session_id)s
                        LIMIT 1
                        """,
                        {"session_id": session_id},
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Upload session initialization failed.") from error
        if row is None:
            raise DocumentStoreUnavailableError("Upload session initialization failed.")
        return self._as_upload_session_record(row)

    def get_upload_session(
        self,
        *,
        project_id: str,
        session_id: str,
    ) -> DocumentUploadSessionRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          us.id,
                          us.project_id,
                          us.document_id,
                          us.import_id,
                          us.original_filename,
                          us.status,
                          us.expected_sha256,
                          us.expected_total_bytes,
                          us.bytes_received,
                          us.last_chunk_index,
                          us.created_by,
                          us.created_at,
                          us.updated_at,
                          us.completed_at,
                          us.canceled_at,
                          us.failure_reason
                        FROM document_upload_sessions AS us
                        WHERE us.project_id = %(project_id)s
                          AND us.id = %(session_id)s
                        LIMIT 1
                        """,
                        {"project_id": project_id, "session_id": session_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Upload session read failed.") from error
        if row is None:
            return None
        return self._as_upload_session_record(row)

    def append_upload_session_chunk(
        self,
        *,
        project_id: str,
        session_id: str,
        chunk_index: int,
        byte_length: int,
        sha256: str,
    ) -> DocumentUploadSessionRecord:
        self.ensure_schema()
        if chunk_index < 0:
            raise DocumentUploadSessionConflictError("chunk_index must be zero or greater.")
        if byte_length < 1:
            raise DocumentUploadSessionConflictError("Chunk payload is empty.")

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "SELECT pg_advisory_xact_lock(hashtext(%(lock_key)s))",
                        {"lock_key": f"upload-session|{project_id}|{session_id}"},
                    )
                    cursor.execute(
                        """
                        SELECT
                          us.id,
                          us.project_id,
                          us.document_id,
                          us.import_id,
                          us.original_filename,
                          us.status,
                          us.expected_sha256,
                          us.expected_total_bytes,
                          us.bytes_received,
                          us.last_chunk_index,
                          us.created_by,
                          us.created_at,
                          us.updated_at,
                          us.completed_at,
                          us.canceled_at,
                          us.failure_reason
                        FROM document_upload_sessions AS us
                        WHERE us.project_id = %(project_id)s
                          AND us.id = %(session_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {"project_id": project_id, "session_id": session_id},
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise DocumentUploadSessionNotFoundError("Upload session not found.")
                    session = self._as_upload_session_record(row)
                    if session.status != "ACTIVE":
                        raise DocumentUploadSessionConflictError(
                            f"Upload session is {session.status} and cannot accept chunks."
                        )

                    expected_next_chunk = session.last_chunk_index + 1
                    if chunk_index < expected_next_chunk:
                        cursor.execute(
                            """
                            SELECT
                              c.byte_length,
                              c.sha256
                            FROM document_upload_session_chunks AS c
                            WHERE c.session_id = %(session_id)s
                              AND c.chunk_index = %(chunk_index)s
                            LIMIT 1
                            """,
                            {"session_id": session_id, "chunk_index": chunk_index},
                        )
                        existing = cursor.fetchone()
                        if existing is None:
                            raise DocumentUploadSessionConflictError(
                                "Chunk index conflicts with persisted upload state."
                            )
                        if int(existing["byte_length"]) != byte_length or str(existing["sha256"]) != sha256:
                            raise DocumentUploadSessionConflictError(
                                "Chunk replay hash mismatch; restart upload session."
                            )
                    elif chunk_index > expected_next_chunk:
                        raise DocumentUploadSessionConflictError(
                            f"Chunk index gap detected. Resume from chunk {expected_next_chunk}."
                        )
                    else:
                        cursor.execute(
                            """
                            INSERT INTO document_upload_session_chunks (
                              session_id,
                              chunk_index,
                              byte_length,
                              sha256
                            )
                            VALUES (
                              %(session_id)s,
                              %(chunk_index)s,
                              %(byte_length)s,
                              %(sha256)s
                            )
                            """,
                            {
                                "session_id": session_id,
                                "chunk_index": chunk_index,
                                "byte_length": byte_length,
                                "sha256": sha256,
                            },
                        )
                        cursor.execute(
                            """
                            UPDATE document_upload_sessions
                            SET
                              bytes_received = bytes_received + %(byte_length)s,
                              last_chunk_index = %(chunk_index)s,
                              updated_at = NOW()
                            WHERE id = %(session_id)s
                            """,
                            {
                                "session_id": session_id,
                                "chunk_index": chunk_index,
                                "byte_length": byte_length,
                            },
                        )

                    cursor.execute(
                        """
                        SELECT
                          us.id,
                          us.project_id,
                          us.document_id,
                          us.import_id,
                          us.original_filename,
                          us.status,
                          us.expected_sha256,
                          us.expected_total_bytes,
                          us.bytes_received,
                          us.last_chunk_index,
                          us.created_by,
                          us.created_at,
                          us.updated_at,
                          us.completed_at,
                          us.canceled_at,
                          us.failure_reason
                        FROM document_upload_sessions AS us
                        WHERE us.id = %(session_id)s
                        LIMIT 1
                        """,
                        {"session_id": session_id},
                    )
                    updated_row = cursor.fetchone()
                connection.commit()
        except (DocumentUploadSessionNotFoundError, DocumentUploadSessionConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Upload chunk state write failed.") from error

        if updated_row is None:
            raise DocumentStoreUnavailableError("Upload chunk state write failed.")
        return self._as_upload_session_record(updated_row)

    def mark_upload_session_status(
        self,
        *,
        project_id: str,
        session_id: str,
        status: DocumentUploadSessionStatus,
        failure_reason: str | None = None,
    ) -> DocumentUploadSessionRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE document_upload_sessions AS us
                        SET
                          status = %(status)s,
                          failure_reason = CASE
                            WHEN %(status)s = 'FAILED' THEN %(failure_reason)s
                            ELSE us.failure_reason
                          END,
                          completed_at = CASE
                            WHEN %(status)s = 'COMPLETED' THEN NOW()
                            ELSE us.completed_at
                          END,
                          canceled_at = CASE
                            WHEN %(status)s = 'CANCELED' THEN NOW()
                            ELSE us.canceled_at
                          END,
                          updated_at = NOW()
                        WHERE us.project_id = %(project_id)s
                          AND us.id = %(session_id)s
                        RETURNING
                          us.id,
                          us.project_id,
                          us.document_id,
                          us.import_id,
                          us.original_filename,
                          us.status,
                          us.expected_sha256,
                          us.expected_total_bytes,
                          us.bytes_received,
                          us.last_chunk_index,
                          us.created_by,
                          us.created_at,
                          us.updated_at,
                          us.completed_at,
                          us.canceled_at,
                          us.failure_reason
                        """,
                        {
                            "status": status,
                            "failure_reason": failure_reason,
                            "project_id": project_id,
                            "session_id": session_id,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Upload session transition failed.") from error
        if row is None:
            raise DocumentUploadSessionNotFoundError("Upload session not found.")
        return self._as_upload_session_record(row)

    def get_project_byte_usage(self, *, project_id: str) -> int:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT COALESCE(SUM(d.bytes), 0) AS total_bytes
                        FROM documents AS d
                        WHERE d.project_id = %(project_id)s
                          AND d.status <> 'CANCELED'
                        """,
                        {"project_id": project_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Document quota usage could not be read.") from error

        if row is None:
            return 0
        total = row.get("total_bytes")
        return int(total) if isinstance(total, int) else 0

    def get_project_document_count(self, *, project_id: str) -> int:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT COUNT(*)::BIGINT AS total_documents
                        FROM documents AS d
                        WHERE d.project_id = %(project_id)s
                          AND d.status <> 'CANCELED'
                        """,
                        {"project_id": project_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Document count read failed.") from error
        if row is None:
            return 0
        total = row.get("total_documents")
        return int(total) if isinstance(total, int) else 0

    def get_project_page_usage(self, *, project_id: str) -> int:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT COUNT(*)::BIGINT AS total_pages
                        FROM pages AS p
                        INNER JOIN documents AS d
                          ON d.id = p.document_id
                        WHERE d.project_id = %(project_id)s
                          AND d.status <> 'CANCELED'
                        """,
                        {"project_id": project_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Page usage read failed.") from error
        if row is None:
            return 0
        total = row.get("total_pages")
        return int(total) if isinstance(total, int) else 0

    def get_import_snapshot(
        self,
        *,
        project_id: str,
        import_id: str,
    ) -> tuple[DocumentRecord, DocumentImportRecord] | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          d.id,
                          d.project_id,
                          d.original_filename,
                          d.stored_filename,
                          d.content_type_detected,
                          d.bytes,
                          d.sha256,
                          d.page_count,
                          d.status,
                          d.created_by,
                          d.created_at,
                          d.updated_at,
                          di.id AS import_id,
                          di.document_id,
                          di.status AS import_status,
                          di.failure_reason,
                          di.created_by AS import_created_by,
                          di.accepted_at,
                          di.rejected_at,
                          di.canceled_by,
                          di.canceled_at,
                          di.created_at AS import_created_at,
                          di.updated_at AS import_updated_at
                        FROM document_imports AS di
                        INNER JOIN documents AS d
                          ON d.id = di.document_id
                        WHERE d.project_id = %(project_id)s
                          AND di.id = %(import_id)s
                        LIMIT 1
                        """,
                        {"project_id": project_id, "import_id": import_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Document import detail read failed.") from error

        if row is None:
            return None
        document_record = self._as_document_record(row)
        import_record = self._as_document_import_record(
            {
                "id": row["import_id"],
                "document_id": row["document_id"],
                "status": row["import_status"],
                "failure_reason": row["failure_reason"],
                "created_by": row["import_created_by"],
                "accepted_at": row["accepted_at"],
                "rejected_at": row["rejected_at"],
                "canceled_by": row["canceled_by"],
                "canceled_at": row["canceled_at"],
                "created_at": row["import_created_at"],
                "updated_at": row["import_updated_at"],
            }
        )
        return document_record, import_record

    def mark_upload_queued(
        self,
        *,
        project_id: str,
        import_id: str,
        stored_filename: str,
        content_type_detected: str,
        byte_count: int,
        sha256: str,
    ) -> None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE documents AS d
                        SET
                          stored_filename = %(stored_filename)s,
                          content_type_detected = %(content_type_detected)s,
                          bytes = %(byte_count)s,
                          sha256 = %(sha256)s,
                          status = 'QUEUED',
                          updated_at = NOW()
                        FROM document_imports AS di
                        WHERE di.id = %(import_id)s
                          AND di.document_id = d.id
                          AND d.project_id = %(project_id)s
                        """,
                        {
                            "stored_filename": stored_filename,
                            "content_type_detected": content_type_detected,
                            "byte_count": byte_count,
                            "sha256": sha256,
                            "import_id": import_id,
                            "project_id": project_id,
                        },
                    )
                    cursor.execute(
                        """
                        UPDATE document_imports AS di
                        SET
                          status = 'QUEUED',
                          failure_reason = NULL,
                          updated_at = NOW()
                        FROM documents AS d
                        WHERE di.id = %(import_id)s
                          AND di.document_id = d.id
                          AND d.project_id = %(project_id)s
                        """,
                        {"import_id": import_id, "project_id": project_id},
                    )
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Document upload queue handoff failed.") from error

    def mark_import_failed(
        self,
        *,
        project_id: str,
        import_id: str,
        failure_reason: str,
    ) -> None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE document_imports AS di
                        SET
                          status = 'FAILED',
                          failure_reason = %(failure_reason)s,
                          updated_at = NOW()
                        FROM documents AS d
                        WHERE di.id = %(import_id)s
                          AND di.document_id = d.id
                          AND d.project_id = %(project_id)s
                        """,
                        {
                            "import_id": import_id,
                            "project_id": project_id,
                            "failure_reason": failure_reason,
                        },
                    )
                    cursor.execute(
                        """
                        UPDATE documents AS d
                        SET
                          status = 'FAILED',
                          updated_at = NOW()
                        FROM document_imports AS di
                        WHERE di.id = %(import_id)s
                          AND di.document_id = d.id
                          AND d.project_id = %(project_id)s
                        """,
                        {"import_id": import_id, "project_id": project_id},
                    )
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Document import failure write failed.") from error

    def transition_import_to_scanning(
        self,
        *,
        project_id: str,
        import_id: str,
    ) -> bool:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE document_imports AS di
                        SET
                          status = 'SCANNING',
                          updated_at = NOW()
                        FROM documents AS d
                        WHERE di.id = %(import_id)s
                          AND di.document_id = d.id
                          AND d.project_id = %(project_id)s
                          AND di.status = 'QUEUED'
                        RETURNING di.id
                        """,
                        {"import_id": import_id, "project_id": project_id},
                    )
                    changed = cursor.fetchone() is not None
                    if changed:
                        cursor.execute(
                            """
                            UPDATE documents AS d
                            SET
                              status = 'SCANNING',
                              updated_at = NOW()
                            FROM document_imports AS di
                            WHERE di.id = %(import_id)s
                              AND di.document_id = d.id
                              AND d.project_id = %(project_id)s
                            """,
                            {"import_id": import_id, "project_id": project_id},
                        )
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Document scan transition failed.") from error
        return changed

    def mark_scan_passed(
        self,
        *,
        project_id: str,
        import_id: str,
    ) -> None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE document_imports AS di
                        SET
                          status = 'ACCEPTED',
                          failure_reason = NULL,
                          accepted_at = NOW(),
                          updated_at = NOW()
                        FROM documents AS d
                        WHERE di.id = %(import_id)s
                          AND di.document_id = d.id
                          AND d.project_id = %(project_id)s
                          AND di.status = 'SCANNING'
                        """,
                        {"import_id": import_id, "project_id": project_id},
                    )
                    cursor.execute(
                        """
                        UPDATE documents AS d
                        SET
                          status = 'EXTRACTING',
                          updated_at = NOW()
                        FROM document_imports AS di
                        WHERE di.id = %(import_id)s
                          AND di.document_id = d.id
                          AND d.project_id = %(project_id)s
                        """,
                        {"import_id": import_id, "project_id": project_id},
                    )
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Document scan pass write failed.") from error

    def mark_scan_rejected(
        self,
        *,
        project_id: str,
        import_id: str,
        failure_reason: str,
    ) -> None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE document_imports AS di
                        SET
                          status = 'REJECTED',
                          failure_reason = %(failure_reason)s,
                          rejected_at = NOW(),
                          updated_at = NOW()
                        FROM documents AS d
                        WHERE di.id = %(import_id)s
                          AND di.document_id = d.id
                          AND d.project_id = %(project_id)s
                          AND di.status = 'SCANNING'
                        """,
                        {
                            "import_id": import_id,
                            "project_id": project_id,
                            "failure_reason": failure_reason,
                        },
                    )
                    cursor.execute(
                        """
                        UPDATE documents AS d
                        SET
                          status = 'FAILED',
                          updated_at = NOW()
                        FROM document_imports AS di
                        WHERE di.id = %(import_id)s
                          AND di.document_id = d.id
                          AND d.project_id = %(project_id)s
                        """,
                        {"import_id": import_id, "project_id": project_id},
                    )
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Document scan rejection write failed.") from error

    def cancel_import(
        self,
        *,
        project_id: str,
        import_id: str,
        canceled_by: str,
    ) -> bool:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE document_imports AS di
                        SET
                          status = 'CANCELED',
                          canceled_by = %(canceled_by)s,
                          canceled_at = NOW(),
                          updated_at = NOW()
                        FROM documents AS d
                        WHERE di.id = %(import_id)s
                          AND di.document_id = d.id
                          AND d.project_id = %(project_id)s
                          AND di.status IN ('UPLOADING', 'QUEUED')
                        RETURNING di.id
                        """,
                        {
                            "import_id": import_id,
                            "project_id": project_id,
                            "canceled_by": canceled_by,
                        },
                    )
                    changed = cursor.fetchone() is not None
                    if changed:
                        cursor.execute(
                            """
                            UPDATE documents AS d
                            SET
                              status = 'CANCELED',
                              updated_at = NOW()
                            FROM document_imports AS di
                            WHERE di.id = %(import_id)s
                              AND di.document_id = d.id
                              AND d.project_id = %(project_id)s
                            """,
                            {"import_id": import_id, "project_id": project_id},
                        )
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Document import cancel write failed.") from error
        return changed

    def create_processing_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_kind: DocumentProcessingRunKind,
        created_by: str,
        status: DocumentProcessingRunStatus = "QUEUED",
        supersedes_processing_run_id: str | None = None,
    ) -> DocumentProcessingRunRecord:
        self.ensure_schema()
        run_id = str(uuid4())
        started_at = "NOW()" if status == "RUNNING" else "NULL"
        finished_at = "NOW()" if status in {"SUCCEEDED", "FAILED", "CANCELED"} else "NULL"
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "SELECT pg_advisory_xact_lock(hashtext(%(lock_key)s))",
                        {"lock_key": f"document_processing_runs|{document_id}|{run_kind}"},
                    )
                    cursor.execute(
                        """
                        SELECT d.id
                        FROM documents AS d
                        WHERE d.project_id = %(project_id)s
                          AND d.id = %(document_id)s
                        LIMIT 1
                        """,
                        {"project_id": project_id, "document_id": document_id},
                    )
                    if cursor.fetchone() is None:
                        raise DocumentNotFoundError("Document not found.")

                    attempt_number = 1
                    supersedes_row: dict[str, object] | None = None
                    if supersedes_processing_run_id is not None:
                        cursor.execute(
                            """
                            SELECT
                              pr.id,
                              pr.document_id,
                              pr.attempt_number,
                              pr.run_kind,
                              pr.superseded_by_processing_run_id
                            FROM document_processing_runs AS pr
                            INNER JOIN documents AS d
                              ON d.id = pr.document_id
                            WHERE d.project_id = %(project_id)s
                              AND pr.document_id = %(document_id)s
                              AND pr.id = %(run_id)s
                            LIMIT 1
                            FOR UPDATE
                            """,
                            {
                                "project_id": project_id,
                                "document_id": document_id,
                                "run_id": supersedes_processing_run_id,
                            },
                        )
                        supersedes_row = cursor.fetchone()
                        if supersedes_row is None:
                            raise DocumentProcessingRunConflictError(
                                "Superseded processing run was not found."
                            )
                        if str(supersedes_row["run_kind"]) != run_kind:
                            raise DocumentProcessingRunConflictError(
                                "Retry lineage requires the same processing run kind."
                            )
                        if supersedes_row["superseded_by_processing_run_id"] is not None:
                            raise DocumentProcessingRunConflictError(
                                "Retry target is already superseded."
                            )
                        attempt_number = int(supersedes_row["attempt_number"]) + 1
                    else:
                        cursor.execute(
                            """
                            SELECT COALESCE(MAX(pr.attempt_number), 0) AS max_attempt_number
                            FROM document_processing_runs AS pr
                            INNER JOIN documents AS d
                              ON d.id = pr.document_id
                            WHERE d.project_id = %(project_id)s
                              AND pr.document_id = %(document_id)s
                              AND pr.run_kind = %(run_kind)s
                            """,
                            {
                                "project_id": project_id,
                                "document_id": document_id,
                                "run_kind": run_kind,
                            },
                        )
                        max_row = cursor.fetchone()
                        if max_row is not None:
                            attempt_number = int(max_row["max_attempt_number"]) + 1

                    cursor.execute(
                        f"""
                        INSERT INTO document_processing_runs (
                          id,
                          document_id,
                          attempt_number,
                          run_kind,
                          supersedes_processing_run_id,
                          superseded_by_processing_run_id,
                          status,
                          created_by,
                          started_at,
                          finished_at
                        )
                        VALUES (
                          %(id)s,
                          %(document_id)s,
                          %(attempt_number)s,
                          %(run_kind)s,
                          %(supersedes_processing_run_id)s,
                          NULL,
                          %(status)s,
                          %(created_by)s,
                          {started_at},
                          {finished_at}
                        )
                        """,
                        {
                            "id": run_id,
                            "document_id": document_id,
                            "attempt_number": attempt_number,
                            "run_kind": run_kind,
                            "supersedes_processing_run_id": supersedes_processing_run_id,
                            "status": status,
                            "created_by": created_by,
                        },
                    )
                    if supersedes_row is not None:
                        cursor.execute(
                            """
                            UPDATE document_processing_runs
                            SET superseded_by_processing_run_id = %(new_run_id)s
                            WHERE id = %(superseded_run_id)s
                            """,
                            {
                                "new_run_id": run_id,
                                "superseded_run_id": str(supersedes_row["id"]),
                            },
                        )
                    cursor.execute(
                        """
                        SELECT
                          pr.id,
                          pr.document_id,
                          pr.attempt_number,
                          pr.run_kind,
                          pr.supersedes_processing_run_id,
                          pr.superseded_by_processing_run_id,
                          pr.status,
                          pr.created_by,
                          pr.created_at,
                          pr.started_at,
                          pr.finished_at,
                          pr.canceled_by,
                          pr.canceled_at,
                          pr.failure_reason
                        FROM document_processing_runs AS pr
                        WHERE pr.id = %(run_id)s
                        LIMIT 1
                        """,
                        {"run_id": run_id},
                    )
                    row = cursor.fetchone()
                connection.commit()
        except (DocumentNotFoundError, DocumentProcessingRunConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Document processing run create failed.") from error

        if row is None:
            raise DocumentStoreUnavailableError("Document processing run create failed.")
        return self._as_processing_run_record(row)

    def transition_processing_run(
        self,
        *,
        project_id: str,
        run_id: str,
        status: DocumentProcessingRunStatus,
        failure_reason: str | None = None,
        canceled_by: str | None = None,
    ) -> DocumentProcessingRunRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE document_processing_runs AS pr
                        SET
                          status = %(status)s,
                          started_at = CASE
                            WHEN %(status)s = 'RUNNING' THEN COALESCE(pr.started_at, NOW())
                            ELSE pr.started_at
                          END,
                          finished_at = CASE
                            WHEN %(status)s IN ('SUCCEEDED', 'FAILED', 'CANCELED') THEN NOW()
                            ELSE pr.finished_at
                          END,
                          canceled_by = CASE
                            WHEN %(status)s = 'CANCELED' THEN %(canceled_by)s
                            ELSE pr.canceled_by
                          END,
                          canceled_at = CASE
                            WHEN %(status)s = 'CANCELED' THEN NOW()
                            ELSE pr.canceled_at
                          END,
                          failure_reason = CASE
                            WHEN %(status)s = 'FAILED' THEN %(failure_reason)s
                            ELSE pr.failure_reason
                          END
                        FROM documents AS d
                        WHERE pr.id = %(run_id)s
                          AND pr.document_id = d.id
                          AND d.project_id = %(project_id)s
                        RETURNING
                          pr.id,
                          pr.document_id,
                          pr.attempt_number,
                          pr.run_kind,
                          pr.supersedes_processing_run_id,
                          pr.superseded_by_processing_run_id,
                          pr.status,
                          pr.created_by,
                          pr.created_at,
                          pr.started_at,
                          pr.finished_at,
                          pr.canceled_by,
                          pr.canceled_at,
                          pr.failure_reason
                        """,
                        {
                            "status": status,
                            "run_id": run_id,
                            "project_id": project_id,
                            "failure_reason": failure_reason,
                            "canceled_by": canceled_by,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Document processing run transition failed.") from error

        if row is None:
            raise DocumentNotFoundError("Document processing run not found.")
        return self._as_processing_run_record(row)

    def list_document_pages(
        self,
        *,
        project_id: str,
        document_id: str,
    ) -> list[DocumentPageRecord]:
        self.ensure_schema()
        if self.get_document(project_id=project_id, document_id=document_id) is None:
            raise DocumentNotFoundError("Document not found.")
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          p.id,
                          p.document_id,
                          p.page_index,
                          p.width,
                          p.height,
                          p.dpi,
                          p.source_width,
                          p.source_height,
                          p.source_dpi,
                          p.source_color_mode,
                          p.status,
                          p.derived_image_key,
                          p.derived_image_sha256,
                          p.thumbnail_key,
                          p.thumbnail_sha256,
                          p.failure_reason,
                          p.canceled_by,
                          p.canceled_at,
                          p.viewer_rotation,
                          p.created_at,
                          p.updated_at
                        FROM pages AS p
                        WHERE p.document_id = %(document_id)s
                        ORDER BY p.page_index ASC
                        """,
                        {"document_id": document_id},
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Document pages read failed.") from error
        return [self._as_page_record(row) for row in rows]

    def get_document_page(
        self,
        *,
        project_id: str,
        document_id: str,
        page_id: str,
    ) -> DocumentPageRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          p.id,
                          p.document_id,
                          p.page_index,
                          p.width,
                          p.height,
                          p.dpi,
                          p.source_width,
                          p.source_height,
                          p.source_dpi,
                          p.source_color_mode,
                          p.status,
                          p.derived_image_key,
                          p.derived_image_sha256,
                          p.thumbnail_key,
                          p.thumbnail_sha256,
                          p.failure_reason,
                          p.canceled_by,
                          p.canceled_at,
                          p.viewer_rotation,
                          p.created_at,
                          p.updated_at
                        FROM pages AS p
                        INNER JOIN documents AS d
                          ON d.id = p.document_id
                        WHERE p.id = %(page_id)s
                          AND p.document_id = %(document_id)s
                          AND d.project_id = %(project_id)s
                        LIMIT 1
                        """,
                        {
                            "page_id": page_id,
                            "document_id": document_id,
                            "project_id": project_id,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Document page read failed.") from error
        if row is None:
            return None
        return self._as_page_record(row)

    def replace_document_pages(
        self,
        *,
        project_id: str,
        document_id: str,
        pages: list[dict[str, object]],
    ) -> list[DocumentPageRecord]:
        self.ensure_schema()
        if self.get_document(project_id=project_id, document_id=document_id) is None:
            raise DocumentNotFoundError("Document not found.")

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "DELETE FROM pages WHERE document_id = %(document_id)s",
                        {"document_id": document_id},
                    )
                    for payload in pages:
                        cursor.execute(
                            """
                            INSERT INTO pages (
                              id,
                              document_id,
                              page_index,
                              width,
                              height,
                              dpi,
                              source_width,
                              source_height,
                              source_dpi,
                              source_color_mode,
                              status,
                              derived_image_key,
                              derived_image_sha256,
                              viewer_rotation
                            )
                            VALUES (
                              %(id)s,
                              %(document_id)s,
                              %(page_index)s,
                              %(width)s,
                              %(height)s,
                              %(dpi)s,
                              %(source_width)s,
                              %(source_height)s,
                              %(source_dpi)s,
                              %(source_color_mode)s,
                              %(status)s,
                              %(derived_image_key)s,
                              %(derived_image_sha256)s,
                              %(viewer_rotation)s
                            )
                            """,
                            {
                                "id": str(payload["id"]),
                                "document_id": document_id,
                                "page_index": int(payload["page_index"]),
                                "width": int(payload["width"]),
                                "height": int(payload["height"]),
                                "dpi": payload["dpi"],
                                "source_width": int(
                                    payload.get("source_width", payload["width"])
                                ),
                                "source_height": int(
                                    payload.get("source_height", payload["height"])
                                ),
                                "source_dpi": payload.get(
                                    "source_dpi",
                                    payload["dpi"],
                                ),
                                "source_color_mode": str(
                                    payload.get("source_color_mode", "UNKNOWN")
                                ),
                                "status": str(payload["status"]),
                                "derived_image_key": payload["derived_image_key"],
                                "derived_image_sha256": payload["derived_image_sha256"],
                                "viewer_rotation": int(payload.get("viewer_rotation", 0)),
                            },
                        )
                    cursor.execute(
                        """
                        UPDATE documents
                        SET
                          page_count = %(page_count)s,
                          updated_at = NOW()
                        WHERE id = %(document_id)s
                          AND project_id = %(project_id)s
                        """,
                        {
                            "page_count": len(pages),
                            "document_id": document_id,
                            "project_id": project_id,
                        },
                    )
                    cursor.execute(
                        """
                        SELECT
                          p.id,
                          p.document_id,
                          p.page_index,
                          p.width,
                          p.height,
                          p.dpi,
                          p.source_width,
                          p.source_height,
                          p.source_dpi,
                          p.source_color_mode,
                          p.status,
                          p.derived_image_key,
                          p.derived_image_sha256,
                          p.thumbnail_key,
                          p.thumbnail_sha256,
                          p.failure_reason,
                          p.canceled_by,
                          p.canceled_at,
                          p.viewer_rotation,
                          p.created_at,
                          p.updated_at
                        FROM pages AS p
                        WHERE p.document_id = %(document_id)s
                        ORDER BY p.page_index ASC
                        """,
                        {"document_id": document_id},
                    )
                    rows = cursor.fetchall()
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Document pages update failed.") from error

        return [self._as_page_record(row) for row in rows]

    def set_document_status(
        self,
        *,
        project_id: str,
        document_id: str,
        status: DocumentStatus,
    ) -> None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE documents
                        SET
                          status = %(status)s,
                          updated_at = NOW()
                        WHERE id = %(document_id)s
                          AND project_id = %(project_id)s
                        """,
                        {
                            "status": status,
                            "document_id": document_id,
                            "project_id": project_id,
                        },
                    )
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Document status update failed.") from error

    def update_page_thumbnail(
        self,
        *,
        project_id: str,
        document_id: str,
        page_id: str,
        thumbnail_key: str,
        thumbnail_sha256: str,
    ) -> DocumentPageRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE pages AS p
                        SET
                          thumbnail_key = %(thumbnail_key)s,
                          thumbnail_sha256 = %(thumbnail_sha256)s,
                          status = 'READY',
                          updated_at = NOW()
                        FROM documents AS d
                        WHERE p.id = %(page_id)s
                          AND p.document_id = d.id
                          AND p.document_id = %(document_id)s
                          AND d.project_id = %(project_id)s
                        RETURNING
                          p.id,
                          p.document_id,
                          p.page_index,
                          p.width,
                          p.height,
                          p.dpi,
                          p.source_width,
                          p.source_height,
                          p.source_dpi,
                          p.source_color_mode,
                          p.status,
                          p.derived_image_key,
                          p.derived_image_sha256,
                          p.thumbnail_key,
                          p.thumbnail_sha256,
                          p.failure_reason,
                          p.canceled_by,
                          p.canceled_at,
                          p.viewer_rotation,
                          p.created_at,
                          p.updated_at
                        """,
                        {
                            "thumbnail_key": thumbnail_key,
                            "thumbnail_sha256": thumbnail_sha256,
                            "page_id": page_id,
                            "document_id": document_id,
                            "project_id": project_id,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Document thumbnail update failed.") from error
        if row is None:
            raise DocumentNotFoundError("Page not found.")
        return self._as_page_record(row)

    def update_page_rotation(
        self,
        *,
        project_id: str,
        document_id: str,
        page_id: str,
        viewer_rotation: int,
    ) -> DocumentPageRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE pages AS p
                        SET
                          viewer_rotation = %(viewer_rotation)s,
                          updated_at = NOW()
                        FROM documents AS d
                        WHERE p.id = %(page_id)s
                          AND p.document_id = d.id
                          AND p.document_id = %(document_id)s
                          AND d.project_id = %(project_id)s
                        RETURNING
                          p.id,
                          p.document_id,
                          p.page_index,
                          p.width,
                          p.height,
                          p.dpi,
                          p.source_width,
                          p.source_height,
                          p.source_dpi,
                          p.source_color_mode,
                          p.status,
                          p.derived_image_key,
                          p.derived_image_sha256,
                          p.thumbnail_key,
                          p.thumbnail_sha256,
                          p.failure_reason,
                          p.canceled_by,
                          p.canceled_at,
                          p.viewer_rotation,
                          p.created_at,
                          p.updated_at
                        """,
                        {
                            "viewer_rotation": viewer_rotation,
                            "page_id": page_id,
                            "document_id": document_id,
                            "project_id": project_id,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Page rotation update failed.") from error
        if row is None:
            raise DocumentNotFoundError("Page not found.")
        return self._as_page_record(row)

    @staticmethod
    def _hash_preprocess_params(params_json: dict[str, object]) -> str:
        return hash_params_canonical(params_json)

    @staticmethod
    def _hash_layout_params(params_json: dict[str, object]) -> str:
        payload = json.dumps(
            params_json,
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def create_preprocess_run(
        self,
        *,
        project_id: str,
        document_id: str,
        created_by: str,
        profile_id: str,
        profile_version: str = "v1",
        profile_revision: int = 1,
        profile_label: str = "",
        profile_description: str = "",
        profile_params_hash: str = "",
        profile_is_advanced: bool = False,
        profile_is_gated: bool = False,
        params_json: dict[str, object],
        pipeline_version: str,
        container_digest: str,
        manifest_schema_version: int = 2,
        parent_run_id: str | None = None,
        supersedes_run_id: str | None = None,
        run_scope: PreprocessRunScope = "FULL_DOCUMENT",
        target_page_ids_json: list[str] | None = None,
        composed_from_run_ids_json: list[str] | None = None,
    ) -> PreprocessRunRecord:
        self.ensure_schema()
        run_id = str(uuid4())
        params_hash = self._hash_preprocess_params(params_json)
        params_payload = serialize_params_canonical(params_json)

        normalized_scope = self._assert_preprocess_run_scope(str(run_scope))

        normalized_target_page_ids: list[str] | None = None
        if isinstance(target_page_ids_json, list):
            normalized_target_page_ids = []
            seen_target_page_ids: set[str] = set()
            for raw_page_id in target_page_ids_json:
                page_id = str(raw_page_id).strip()
                if not page_id or page_id in seen_target_page_ids:
                    continue
                seen_target_page_ids.add(page_id)
                normalized_target_page_ids.append(page_id)
            if not normalized_target_page_ids:
                normalized_target_page_ids = None

        normalized_composed_from_run_ids: list[str] | None = None
        if isinstance(composed_from_run_ids_json, list):
            normalized_composed_from_run_ids = []
            seen_composed_run_ids: set[str] = set()
            for raw_run_id in composed_from_run_ids_json:
                candidate = str(raw_run_id).strip()
                if not candidate or candidate in seen_composed_run_ids:
                    continue
                seen_composed_run_ids.add(candidate)
                normalized_composed_from_run_ids.append(candidate)
            if not normalized_composed_from_run_ids:
                normalized_composed_from_run_ids = None

        if normalized_target_page_ids:
            if normalized_scope == "FULL_DOCUMENT":
                normalized_scope = "PAGE_SUBSET"
        elif normalized_scope == "PAGE_SUBSET":
            raise DocumentPreprocessRunConflictError(
                "PAGE_SUBSET preprocess runs require target_page_ids."
            )

        if normalized_scope != "PAGE_SUBSET":
            normalized_target_page_ids = None
        if normalized_scope != "COMPOSED_FULL_DOCUMENT":
            normalized_composed_from_run_ids = None

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "SELECT pg_advisory_xact_lock(hashtext(%(lock_key)s))",
                        {"lock_key": f"preprocess_runs|{document_id}"},
                    )
                    cursor.execute(
                        """
                        SELECT d.id
                        FROM documents AS d
                        WHERE d.project_id = %(project_id)s
                          AND d.id = %(document_id)s
                        LIMIT 1
                        """,
                        {"project_id": project_id, "document_id": document_id},
                    )
                    if cursor.fetchone() is None:
                        raise DocumentNotFoundError("Document not found.")

                    if parent_run_id is not None:
                        cursor.execute(
                            """
                            SELECT pr.id
                            FROM preprocess_runs AS pr
                            WHERE pr.project_id = %(project_id)s
                              AND pr.document_id = %(document_id)s
                              AND pr.id = %(parent_run_id)s
                            LIMIT 1
                            """,
                            {
                                "project_id": project_id,
                                "document_id": document_id,
                                "parent_run_id": parent_run_id,
                            },
                        )
                        if cursor.fetchone() is None:
                            raise DocumentPreprocessRunConflictError(
                                "Parent preprocess run was not found."
                            )

                    if supersedes_run_id is not None:
                        cursor.execute(
                            """
                            SELECT
                              pr.id,
                              pr.superseded_by_run_id
                            FROM preprocess_runs AS pr
                            WHERE pr.project_id = %(project_id)s
                              AND pr.document_id = %(document_id)s
                              AND pr.id = %(supersedes_run_id)s
                            LIMIT 1
                            FOR UPDATE
                            """,
                            {
                                "project_id": project_id,
                                "document_id": document_id,
                                "supersedes_run_id": supersedes_run_id,
                            },
                        )
                        supersedes_row = cursor.fetchone()
                        if supersedes_row is None:
                            raise DocumentPreprocessRunConflictError(
                                "Superseded preprocess run was not found."
                            )
                        if supersedes_row["superseded_by_run_id"] is not None:
                            raise DocumentPreprocessRunConflictError(
                                "Superseded preprocess run is already superseded."
                            )

                    cursor.execute(
                        """
                        SELECT COALESCE(MAX(pr.attempt_number), 0) AS max_attempt_number
                        FROM preprocess_runs AS pr
                        WHERE pr.project_id = %(project_id)s
                          AND pr.document_id = %(document_id)s
                        """,
                        {"project_id": project_id, "document_id": document_id},
                    )
                    max_row = cursor.fetchone()
                    attempt_number = (
                        int(max_row["max_attempt_number"]) + 1 if max_row is not None else 1
                    )

                    cursor.execute(
                        """
                        INSERT INTO preprocess_runs (
                          id,
                          project_id,
                          document_id,
                          parent_run_id,
                          attempt_number,
                          run_scope,
                          target_page_ids_json,
                          composed_from_run_ids_json,
                          superseded_by_run_id,
                          profile_id,
                          profile_version,
                          profile_revision,
                          profile_label,
                          profile_description,
                          profile_params_hash,
                          profile_is_advanced,
                          profile_is_gated,
                          params_json,
                          params_hash,
                          pipeline_version,
                          container_digest,
                          manifest_schema_version,
                          status,
                          created_by
                        )
                        VALUES (
                          %(id)s,
                          %(project_id)s,
                          %(document_id)s,
                          %(parent_run_id)s,
                          %(attempt_number)s,
                          %(run_scope)s,
                          %(target_page_ids_json)s::jsonb,
                          %(composed_from_run_ids_json)s::jsonb,
                          NULL,
                          %(profile_id)s,
                          %(profile_version)s,
                          %(profile_revision)s,
                          %(profile_label)s,
                          %(profile_description)s,
                          %(profile_params_hash)s,
                          %(profile_is_advanced)s,
                          %(profile_is_gated)s,
                          %(params_json)s::jsonb,
                          %(params_hash)s,
                          %(pipeline_version)s,
                          %(container_digest)s,
                          %(manifest_schema_version)s,
                          'QUEUED',
                          %(created_by)s
                        )
                        """,
                        {
                            "id": run_id,
                            "project_id": project_id,
                            "document_id": document_id,
                            "parent_run_id": parent_run_id,
                            "attempt_number": attempt_number,
                            "run_scope": normalized_scope,
                            "target_page_ids_json": (
                                json.dumps(normalized_target_page_ids)
                                if normalized_target_page_ids is not None
                                else None
                            ),
                            "composed_from_run_ids_json": (
                                json.dumps(normalized_composed_from_run_ids)
                                if normalized_composed_from_run_ids is not None
                                else None
                            ),
                            "profile_id": profile_id,
                            "profile_version": profile_version,
                            "profile_revision": max(1, profile_revision),
                            "profile_label": profile_label,
                            "profile_description": profile_description,
                            "profile_params_hash": profile_params_hash,
                            "profile_is_advanced": profile_is_advanced,
                            "profile_is_gated": profile_is_gated,
                            "params_json": params_payload,
                            "params_hash": params_hash,
                            "pipeline_version": pipeline_version,
                            "container_digest": container_digest,
                            "manifest_schema_version": max(1, manifest_schema_version),
                            "created_by": created_by,
                        },
                    )
                    if supersedes_run_id is not None:
                        cursor.execute(
                            """
                            UPDATE preprocess_runs
                            SET superseded_by_run_id = %(new_run_id)s
                            WHERE id = %(superseded_run_id)s
                            """,
                            {
                                "new_run_id": run_id,
                                "superseded_run_id": supersedes_run_id,
                            },
                        )

                    cursor.execute(
                        """
                        SELECT
                          p.id,
                          p.page_index,
                          p.dpi,
                          p.source_dpi,
                          p.derived_image_key,
                          p.derived_image_sha256
                        FROM pages AS p
                        WHERE p.document_id = %(document_id)s
                        ORDER BY p.page_index ASC
                        """,
                        {"document_id": document_id},
                    )
                    page_rows = cursor.fetchall()
                    if normalized_target_page_ids is not None:
                        page_rows_by_id = {
                            str(page_row["id"]): page_row for page_row in page_rows
                        }
                        missing_page_ids = [
                            page_id
                            for page_id in normalized_target_page_ids
                            if page_id not in page_rows_by_id
                        ]
                        if missing_page_ids:
                            raise DocumentPreprocessRunConflictError(
                                "One or more target pages are not part of the document."
                            )
                        page_rows = [
                            page_rows_by_id[page_id] for page_id in normalized_target_page_ids
                        ]
                    for page_row in page_rows:
                        source_dpi = (
                            int(page_row["source_dpi"])
                            if isinstance(page_row["source_dpi"], int)
                            else (
                                int(page_row["dpi"])
                                if isinstance(page_row["dpi"], int)
                                else None
                            )
                        )
                        if source_dpi is None:
                            quality_gate_status = "REVIEW_REQUIRED"
                            warnings = ["LOW_DPI"]
                        elif source_dpi < 150:
                            quality_gate_status = "BLOCKED"
                            warnings = ["LOW_DPI"]
                        elif source_dpi < 200:
                            quality_gate_status = "REVIEW_REQUIRED"
                            warnings = ["LOW_DPI"]
                        else:
                            quality_gate_status = "PASS"
                            warnings = []

                        cursor.execute(
                            """
                            INSERT INTO page_preprocess_results (
                              run_id,
                              page_id,
                              page_index,
                              status,
                              quality_gate_status,
                              input_object_key,
                              input_sha256,
                              source_result_run_id,
                              output_object_key_gray,
                              output_object_key_bin,
                              metrics_object_key,
                              metrics_sha256,
                              metrics_json,
                              sha256_gray,
                              sha256_bin,
                              warnings_json,
                              failure_reason
                            )
                            VALUES (
                              %(run_id)s,
                              %(page_id)s,
                              %(page_index)s,
                              'QUEUED',
                              %(quality_gate_status)s,
                              %(input_object_key)s,
                              %(input_sha256)s,
                              %(source_result_run_id)s,
                              NULL,
                              NULL,
                              NULL,
                              NULL,
                              '{}'::jsonb,
                              NULL,
                              NULL,
                              %(warnings_json)s::jsonb,
                              NULL
                            )
                            """,
                            {
                                "run_id": run_id,
                                "page_id": str(page_row["id"]),
                                "page_index": int(page_row["page_index"]),
                                "quality_gate_status": quality_gate_status,
                                "input_object_key": (
                                    page_row["derived_image_key"]
                                    if isinstance(page_row["derived_image_key"], str)
                                    else None
                                ),
                                "input_sha256": (
                                    page_row["derived_image_sha256"]
                                    if isinstance(page_row["derived_image_sha256"], str)
                                    else None
                                ),
                                "source_result_run_id": run_id,
                                "warnings_json": json.dumps(warnings),
                            },
                        )

                    cursor.execute(
                        """
                        SELECT
                          pr.id,
                          pr.project_id,
                          pr.document_id,
                          pr.parent_run_id,
                          pr.attempt_number,
                          pr.run_scope,
                          pr.target_page_ids_json,
                          pr.composed_from_run_ids_json,
                          pr.superseded_by_run_id,
                          pr.profile_id,
                          pr.profile_version,
                          pr.profile_revision,
                          pr.profile_label,
                          pr.profile_description,
                          pr.profile_params_hash,
                          pr.profile_is_advanced,
                          pr.profile_is_gated,
                          pr.params_json,
                          pr.params_hash,
                          pr.pipeline_version,
                          pr.container_digest,
                          pr.manifest_object_key,
                          pr.manifest_sha256,
                          pr.manifest_schema_version,
                          pr.status,
                          pr.created_by,
                          pr.created_at,
                          pr.started_at,
                          pr.finished_at,
                          pr.failure_reason
                        FROM preprocess_runs AS pr
                        WHERE pr.id = %(run_id)s
                        LIMIT 1
                        """,
                        {"run_id": run_id},
                    )
                    row = cursor.fetchone()
                connection.commit()
        except (DocumentNotFoundError, DocumentPreprocessRunConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Preprocess run create failed.") from error

        if row is None:
            raise DocumentStoreUnavailableError("Preprocess run create failed.")
        return self._as_preprocess_run_record(row)

    def list_preprocess_runs(
        self,
        *,
        project_id: str,
        document_id: str,
        cursor: int = 0,
        page_size: int = 50,
    ) -> tuple[list[PreprocessRunRecord], int | None]:
        self.ensure_schema()
        if self.get_document(project_id=project_id, document_id=document_id) is None:
            raise DocumentNotFoundError("Document not found.")
        safe_page_size = max(1, min(page_size, 200))
        safe_cursor = max(0, cursor)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_handle:
                    cursor_handle.execute(
                        """
                        SELECT
                          pr.id,
                          pr.project_id,
                          pr.document_id,
                          pr.parent_run_id,
                          pr.attempt_number,
                          pr.run_scope,
                          pr.target_page_ids_json,
                          pr.composed_from_run_ids_json,
                          pr.superseded_by_run_id,
                          pr.profile_id,
                          pr.profile_version,
                          pr.profile_revision,
                          pr.profile_label,
                          pr.profile_description,
                          pr.profile_params_hash,
                          pr.profile_is_advanced,
                          pr.profile_is_gated,
                          pr.params_json,
                          pr.params_hash,
                          pr.pipeline_version,
                          pr.container_digest,
                          pr.manifest_object_key,
                          pr.manifest_sha256,
                          pr.manifest_schema_version,
                          pr.status,
                          pr.created_by,
                          pr.created_at,
                          pr.started_at,
                          pr.finished_at,
                          pr.failure_reason
                        FROM preprocess_runs AS pr
                        WHERE pr.project_id = %(project_id)s
                          AND pr.document_id = %(document_id)s
                        ORDER BY pr.created_at DESC, pr.id DESC
                        LIMIT %(limit)s
                        OFFSET %(offset)s
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "limit": safe_page_size + 1,
                            "offset": safe_cursor,
                        },
                    )
                    rows = cursor_handle.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Preprocess runs read failed.") from error

        has_more = len(rows) > safe_page_size
        selected_rows = rows[:safe_page_size]
        next_cursor = safe_cursor + safe_page_size if has_more else None
        return [self._as_preprocess_run_record(row) for row in selected_rows], next_cursor

    def get_preprocess_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> PreprocessRunRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          pr.id,
                          pr.project_id,
                          pr.document_id,
                          pr.parent_run_id,
                          pr.attempt_number,
                          pr.run_scope,
                          pr.target_page_ids_json,
                          pr.composed_from_run_ids_json,
                          pr.superseded_by_run_id,
                          pr.profile_id,
                          pr.profile_version,
                          pr.profile_revision,
                          pr.profile_label,
                          pr.profile_description,
                          pr.profile_params_hash,
                          pr.profile_is_advanced,
                          pr.profile_is_gated,
                          pr.params_json,
                          pr.params_hash,
                          pr.pipeline_version,
                          pr.container_digest,
                          pr.manifest_object_key,
                          pr.manifest_sha256,
                          pr.manifest_schema_version,
                          pr.status,
                          pr.created_by,
                          pr.created_at,
                          pr.started_at,
                          pr.finished_at,
                          pr.failure_reason
                        FROM preprocess_runs AS pr
                        WHERE pr.project_id = %(project_id)s
                          AND pr.document_id = %(document_id)s
                          AND pr.id = %(run_id)s
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Preprocess run read failed.") from error
        if row is None:
            return None
        return self._as_preprocess_run_record(row)

    def get_preprocess_projection(
        self,
        *,
        project_id: str,
        document_id: str,
    ) -> DocumentPreprocessProjectionRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          dp.document_id,
                          dp.project_id,
                          dp.active_preprocess_run_id,
                          dp.active_profile_id,
                          dp.active_profile_version,
                          dp.active_profile_revision,
                          dp.active_params_hash,
                          dp.active_pipeline_version,
                          dp.active_container_digest,
                          lp.active_input_preprocess_run_id AS layout_basis_run_id,
                          CASE
                            WHEN lp.document_id IS NULL THEN 'NOT_STARTED'
                            WHEN lp.active_input_preprocess_run_id = dp.active_preprocess_run_id
                              THEN 'CURRENT'
                            ELSE 'STALE'
                          END AS layout_basis_state,
                          tp.active_preprocess_run_id AS transcription_basis_run_id,
                          CASE
                            WHEN tp.document_id IS NULL THEN 'NOT_STARTED'
                            WHEN tp.active_preprocess_run_id = dp.active_preprocess_run_id
                              THEN 'CURRENT'
                            ELSE 'STALE'
                          END AS transcription_basis_state,
                          dp.updated_at
                        FROM document_preprocess_projections AS dp
                        LEFT JOIN document_layout_projections AS lp
                          ON lp.document_id = dp.document_id
                         AND lp.project_id = dp.project_id
                        LEFT JOIN document_transcription_projections AS tp
                          ON tp.document_id = dp.document_id
                         AND tp.project_id = dp.project_id
                        WHERE dp.project_id = %(project_id)s
                          AND dp.document_id = %(document_id)s
                        LIMIT 1
                        """,
                        {"project_id": project_id, "document_id": document_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Preprocess projection read failed.") from error
        if row is None:
            return None
        return self._as_preprocess_projection_record(row)

    def get_preprocess_downstream_basis_references(
        self,
        *,
        project_id: str,
        document_id: str,
    ) -> PreprocessDownstreamBasisReferencesRecord:
        self.ensure_schema()
        has_layout_projection = False
        layout_active_input_preprocess_run_id: str | None = None
        has_transcription_projection = False
        transcription_active_preprocess_run_id: str | None = None
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT lp.active_input_preprocess_run_id
                        FROM document_layout_projections AS lp
                        WHERE lp.project_id = %(project_id)s
                          AND lp.document_id = %(document_id)s
                        LIMIT 1
                        """,
                        {"project_id": project_id, "document_id": document_id},
                    )
                    layout_row = cursor.fetchone()
                    if layout_row is not None:
                        has_layout_projection = True
                        layout_active_input_preprocess_run_id = (
                            str(layout_row["active_input_preprocess_run_id"])
                            if isinstance(
                                layout_row.get("active_input_preprocess_run_id"), str
                            )
                            else None
                        )

                    cursor.execute(
                        """
                        SELECT tp.active_preprocess_run_id
                        FROM document_transcription_projections AS tp
                        WHERE tp.project_id = %(project_id)s
                          AND tp.document_id = %(document_id)s
                        LIMIT 1
                        """,
                        {"project_id": project_id, "document_id": document_id},
                    )
                    transcription_row = cursor.fetchone()
                    if transcription_row is not None:
                        has_transcription_projection = True
                        transcription_active_preprocess_run_id = (
                            str(transcription_row["active_preprocess_run_id"])
                            if isinstance(
                                transcription_row.get("active_preprocess_run_id"), str
                            )
                            else None
                        )
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Downstream projection basis read failed."
            ) from error
        return PreprocessDownstreamBasisReferencesRecord(
            has_layout_projection=has_layout_projection,
            layout_active_input_preprocess_run_id=layout_active_input_preprocess_run_id,
            has_transcription_projection=has_transcription_projection,
            transcription_active_preprocess_run_id=transcription_active_preprocess_run_id,
        )

    def get_active_preprocess_run(
        self,
        *,
        project_id: str,
        document_id: str,
    ) -> PreprocessRunRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          pr.id,
                          pr.project_id,
                          pr.document_id,
                          pr.parent_run_id,
                          pr.attempt_number,
                          pr.run_scope,
                          pr.target_page_ids_json,
                          pr.composed_from_run_ids_json,
                          pr.superseded_by_run_id,
                          pr.profile_id,
                          pr.profile_version,
                          pr.profile_revision,
                          pr.profile_label,
                          pr.profile_description,
                          pr.profile_params_hash,
                          pr.profile_is_advanced,
                          pr.profile_is_gated,
                          pr.params_json,
                          pr.params_hash,
                          pr.pipeline_version,
                          pr.container_digest,
                          pr.manifest_object_key,
                          pr.manifest_sha256,
                          pr.manifest_schema_version,
                          pr.status,
                          pr.created_by,
                          pr.created_at,
                          pr.started_at,
                          pr.finished_at,
                          pr.failure_reason
                        FROM document_preprocess_projections AS dp
                        INNER JOIN preprocess_runs AS pr
                          ON pr.id = dp.active_preprocess_run_id
                        WHERE dp.project_id = %(project_id)s
                          AND dp.document_id = %(document_id)s
                        LIMIT 1
                        """,
                        {"project_id": project_id, "document_id": document_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Active preprocess run read failed.") from error
        if row is None:
            return None
        return self._as_preprocess_run_record(row)

    def list_preprocess_page_results(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        status: PreprocessPageResultStatus | None = None,
        warning: str | None = None,
        cursor: int = 0,
        page_size: int = 100,
    ) -> tuple[list[PagePreprocessResultRecord], int | None]:
        self.ensure_schema()
        safe_page_size = max(1, min(page_size, 500))
        safe_cursor = max(0, cursor)
        conditions = [
            "prr.run_id = %(run_id)s",
            "pr.project_id = %(project_id)s",
            "pr.document_id = %(document_id)s",
        ]
        params: dict[str, object] = {
            "run_id": run_id,
            "project_id": project_id,
            "document_id": document_id,
            "limit": safe_page_size + 1,
            "offset": safe_cursor,
        }
        if status is not None:
            conditions.append("prr.status = %(status)s")
            params["status"] = status
        if isinstance(warning, str) and warning.strip():
            conditions.append("prr.warnings_json ? %(warning)s")
            params["warning"] = warning.strip()
        where_clause = " AND ".join(conditions)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_handle:
                    cursor_handle.execute(
                        f"""
                        SELECT
                          prr.run_id,
                          prr.page_id,
                          prr.page_index,
                          prr.status,
                          prr.quality_gate_status,
                          prr.input_object_key,
                          prr.input_sha256,
                          prr.source_result_run_id,
                          prr.output_object_key_gray,
                          prr.output_object_key_bin,
                          prr.metrics_object_key,
                          prr.metrics_sha256,
                          prr.metrics_json,
                          prr.sha256_gray,
                          prr.sha256_bin,
                          prr.warnings_json,
                          prr.failure_reason,
                          prr.created_at,
                          prr.updated_at
                        FROM page_preprocess_results AS prr
                        INNER JOIN preprocess_runs AS pr
                          ON pr.id = prr.run_id
                        WHERE {where_clause}
                        ORDER BY prr.page_index ASC, prr.page_id ASC
                        LIMIT %(limit)s
                        OFFSET %(offset)s
                        """,
                        params,
                    )
                    rows = cursor_handle.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Preprocess page-result listing failed."
            ) from error

        has_more = len(rows) > safe_page_size
        selected_rows = rows[:safe_page_size]
        next_cursor = safe_cursor + safe_page_size if has_more else None
        return (
            [self._as_preprocess_page_result_record(row) for row in selected_rows],
            next_cursor,
        )

    def get_preprocess_page_result(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> PagePreprocessResultRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          prr.run_id,
                          prr.page_id,
                          prr.page_index,
                          prr.status,
                          prr.quality_gate_status,
                          prr.input_object_key,
                          prr.input_sha256,
                          prr.source_result_run_id,
                          prr.output_object_key_gray,
                          prr.output_object_key_bin,
                          prr.metrics_object_key,
                          prr.metrics_sha256,
                          prr.metrics_json,
                          prr.sha256_gray,
                          prr.sha256_bin,
                          prr.warnings_json,
                          prr.failure_reason,
                          prr.created_at,
                          prr.updated_at
                        FROM page_preprocess_results AS prr
                        INNER JOIN preprocess_runs AS pr
                          ON pr.id = prr.run_id
                        WHERE prr.run_id = %(run_id)s
                          AND prr.page_id = %(page_id)s
                          AND pr.project_id = %(project_id)s
                          AND pr.document_id = %(document_id)s
                        LIMIT 1
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "project_id": project_id,
                            "document_id": document_id,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Preprocess page-result read failed.") from error
        if row is None:
            return None
        return self._as_preprocess_page_result_record(row)

    def create_layout_run(
        self,
        *,
        project_id: str,
        document_id: str,
        created_by: str,
        input_preprocess_run_id: str,
        model_id: str | None,
        profile_id: str | None,
        params_json: dict[str, object],
        pipeline_version: str,
        container_digest: str,
        parent_run_id: str | None = None,
        supersedes_run_id: str | None = None,
        run_kind: LayoutRunKind = "AUTO",
    ) -> LayoutRunRecord:
        self.ensure_schema()
        params_hash = self._hash_layout_params(params_json)
        params_payload = self._serialize_json_payload(params_json)
        normalized_run_kind = self._assert_layout_run_kind(str(run_kind))
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "SELECT pg_advisory_xact_lock(hashtext(%(lock_key)s))",
                        {"lock_key": f"layout_runs|{document_id}"},
                    )
                    cursor.execute(
                        """
                        SELECT d.id
                        FROM documents AS d
                        WHERE d.project_id = %(project_id)s
                          AND d.id = %(document_id)s
                        LIMIT 1
                        """,
                        {"project_id": project_id, "document_id": document_id},
                    )
                    if cursor.fetchone() is None:
                        raise DocumentNotFoundError("Document not found.")

                    cursor.execute(
                        """
                        SELECT pr.id, pr.status
                        FROM preprocess_runs AS pr
                        WHERE pr.project_id = %(project_id)s
                          AND pr.document_id = %(document_id)s
                          AND pr.id = %(input_preprocess_run_id)s
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "input_preprocess_run_id": input_preprocess_run_id,
                        },
                    )
                    preprocess_row = cursor.fetchone()
                    if preprocess_row is None:
                        raise DocumentLayoutRunConflictError(
                            "Input preprocess run was not found."
                        )
                    preprocess_status = self._assert_preprocess_run_status(
                        str(preprocess_row["status"])
                    )
                    if preprocess_status != "SUCCEEDED":
                        raise DocumentLayoutRunConflictError(
                            "Layout runs require a SUCCEEDED preprocess input run."
                        )

                    if parent_run_id is not None:
                        cursor.execute(
                            """
                            SELECT lr.id
                            FROM layout_runs AS lr
                            WHERE lr.project_id = %(project_id)s
                              AND lr.document_id = %(document_id)s
                              AND lr.id = %(parent_run_id)s
                            LIMIT 1
                            """,
                            {
                                "project_id": project_id,
                                "document_id": document_id,
                                "parent_run_id": parent_run_id,
                            },
                        )
                        if cursor.fetchone() is None:
                            raise DocumentLayoutRunConflictError(
                                "Parent layout run was not found."
                            )

                    if supersedes_run_id is not None:
                        cursor.execute(
                            """
                            SELECT
                              lr.id,
                              lr.superseded_by_run_id
                            FROM layout_runs AS lr
                            WHERE lr.project_id = %(project_id)s
                              AND lr.document_id = %(document_id)s
                              AND lr.id = %(supersedes_run_id)s
                            LIMIT 1
                            FOR UPDATE
                            """,
                            {
                                "project_id": project_id,
                                "document_id": document_id,
                                "supersedes_run_id": supersedes_run_id,
                            },
                        )
                        supersedes_row = cursor.fetchone()
                        if supersedes_row is None:
                            raise DocumentLayoutRunConflictError(
                                "Superseded layout run was not found."
                            )
                        if supersedes_row["superseded_by_run_id"] is not None:
                            raise DocumentLayoutRunConflictError(
                                "Superseded layout run is already superseded."
                            )

                    cursor.execute(
                        """
                        SELECT COALESCE(MAX(lr.attempt_number), 0) AS max_attempt_number
                        FROM layout_runs AS lr
                        WHERE lr.project_id = %(project_id)s
                          AND lr.document_id = %(document_id)s
                        """,
                        {"project_id": project_id, "document_id": document_id},
                    )
                    max_row = cursor.fetchone()
                    attempt_number = (
                        int(max_row["max_attempt_number"]) + 1 if max_row is not None else 1
                    )

                    run_id = str(uuid4())
                    cursor.execute(
                        """
                        INSERT INTO layout_runs (
                          id,
                          project_id,
                          document_id,
                          input_preprocess_run_id,
                          run_kind,
                          parent_run_id,
                          attempt_number,
                          superseded_by_run_id,
                          model_id,
                          profile_id,
                          params_json,
                          params_hash,
                          pipeline_version,
                          container_digest,
                          status,
                          created_by
                        )
                        VALUES (
                          %(id)s,
                          %(project_id)s,
                          %(document_id)s,
                          %(input_preprocess_run_id)s,
                          %(run_kind)s,
                          %(parent_run_id)s,
                          %(attempt_number)s,
                          NULL,
                          %(model_id)s,
                          %(profile_id)s,
                          %(params_json)s::jsonb,
                          %(params_hash)s,
                          %(pipeline_version)s,
                          %(container_digest)s,
                          'QUEUED',
                          %(created_by)s
                        )
                        """,
                        {
                            "id": run_id,
                            "project_id": project_id,
                            "document_id": document_id,
                            "input_preprocess_run_id": input_preprocess_run_id,
                            "run_kind": normalized_run_kind,
                            "parent_run_id": parent_run_id,
                            "attempt_number": attempt_number,
                            "model_id": model_id,
                            "profile_id": profile_id,
                            "params_json": params_payload,
                            "params_hash": params_hash,
                            "pipeline_version": pipeline_version,
                            "container_digest": container_digest,
                            "created_by": created_by,
                        },
                    )
                    if supersedes_run_id is not None:
                        cursor.execute(
                            """
                            UPDATE layout_runs
                            SET superseded_by_run_id = %(new_run_id)s
                            WHERE id = %(superseded_run_id)s
                            """,
                            {
                                "new_run_id": run_id,
                                "superseded_run_id": supersedes_run_id,
                            },
                        )

                    cursor.execute(
                        """
                        SELECT
                          p.id,
                          p.page_index
                        FROM pages AS p
                        WHERE p.document_id = %(document_id)s
                        ORDER BY p.page_index ASC
                        """,
                        {"document_id": document_id},
                    )
                    page_rows = cursor.fetchall()
                    for page_row in page_rows:
                        cursor.execute(
                            """
                            INSERT INTO page_layout_results (
                              run_id,
                              page_id,
                              page_index,
                              status,
                              page_recall_status,
                              active_layout_version_id,
                              page_xml_key,
                              overlay_json_key,
                              page_xml_sha256,
                              overlay_json_sha256,
                              metrics_json,
                              warnings_json,
                              failure_reason
                            )
                            VALUES (
                              %(run_id)s,
                              %(page_id)s,
                              %(page_index)s,
                              'QUEUED',
                              'NEEDS_MANUAL_REVIEW',
                              NULL,
                              NULL,
                              NULL,
                              NULL,
                              NULL,
                              '{}'::jsonb,
                              '[]'::jsonb,
                              NULL
                            )
                            """,
                            {
                                "run_id": run_id,
                                "page_id": str(page_row["id"]),
                                "page_index": int(page_row["page_index"]),
                            },
                        )

                    cursor.execute(
                        """
                        SELECT
                          lr.id,
                          lr.project_id,
                          lr.document_id,
                          lr.input_preprocess_run_id,
                          lr.run_kind,
                          lr.parent_run_id,
                          lr.attempt_number,
                          lr.superseded_by_run_id,
                          lr.model_id,
                          lr.profile_id,
                          lr.params_json,
                          lr.params_hash,
                          lr.pipeline_version,
                          lr.container_digest,
                          lr.status,
                          lr.created_by,
                          lr.created_at,
                          lr.started_at,
                          lr.finished_at,
                          lr.failure_reason
                        FROM layout_runs AS lr
                        WHERE lr.id = %(run_id)s
                        LIMIT 1
                        """,
                        {"run_id": run_id},
                    )
                    row = cursor.fetchone()
                connection.commit()
        except (DocumentNotFoundError, DocumentLayoutRunConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Layout run create failed.") from error

        if row is None:
            raise DocumentStoreUnavailableError("Layout run create failed.")
        return self._as_layout_run_record(row)

    def list_layout_runs(
        self,
        *,
        project_id: str,
        document_id: str,
        cursor: int = 0,
        page_size: int = 50,
    ) -> tuple[list[LayoutRunRecord], int | None]:
        self.ensure_schema()
        if self.get_document(project_id=project_id, document_id=document_id) is None:
            raise DocumentNotFoundError("Document not found.")
        safe_page_size = max(1, min(page_size, 200))
        safe_cursor = max(0, cursor)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_handle:
                    cursor_handle.execute(
                        """
                        SELECT
                          lr.id,
                          lr.project_id,
                          lr.document_id,
                          lr.input_preprocess_run_id,
                          lr.run_kind,
                          lr.parent_run_id,
                          lr.attempt_number,
                          lr.superseded_by_run_id,
                          lr.model_id,
                          lr.profile_id,
                          lr.params_json,
                          lr.params_hash,
                          lr.pipeline_version,
                          lr.container_digest,
                          lr.status,
                          lr.created_by,
                          lr.created_at,
                          lr.started_at,
                          lr.finished_at,
                          lr.failure_reason
                        FROM layout_runs AS lr
                        WHERE lr.project_id = %(project_id)s
                          AND lr.document_id = %(document_id)s
                        ORDER BY lr.created_at DESC, lr.id DESC
                        LIMIT %(limit)s
                        OFFSET %(offset)s
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "limit": safe_page_size + 1,
                            "offset": safe_cursor,
                        },
                    )
                    rows = cursor_handle.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Layout runs read failed.") from error

        has_more = len(rows) > safe_page_size
        selected_rows = rows[:safe_page_size]
        next_cursor = safe_cursor + safe_page_size if has_more else None
        return [self._as_layout_run_record(row) for row in selected_rows], next_cursor

    def get_layout_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> LayoutRunRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          lr.id,
                          lr.project_id,
                          lr.document_id,
                          lr.input_preprocess_run_id,
                          lr.run_kind,
                          lr.parent_run_id,
                          lr.attempt_number,
                          lr.superseded_by_run_id,
                          lr.model_id,
                          lr.profile_id,
                          lr.params_json,
                          lr.params_hash,
                          lr.pipeline_version,
                          lr.container_digest,
                          lr.status,
                          lr.created_by,
                          lr.created_at,
                          lr.started_at,
                          lr.finished_at,
                          lr.failure_reason
                        FROM layout_runs AS lr
                        WHERE lr.project_id = %(project_id)s
                          AND lr.document_id = %(document_id)s
                          AND lr.id = %(run_id)s
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Layout run read failed.") from error
        if row is None:
            return None
        return self._as_layout_run_record(row)

    def get_layout_projection(
        self,
        *,
        project_id: str,
        document_id: str,
    ) -> DocumentLayoutProjectionRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          lp.document_id,
                          lp.project_id,
                          lp.active_layout_run_id,
                          lp.active_input_preprocess_run_id,
                          lp.active_layout_snapshot_hash,
                          lp.downstream_transcription_state,
                          lp.downstream_transcription_invalidated_at,
                          lp.downstream_transcription_invalidated_reason,
                          lp.updated_at
                        FROM document_layout_projections AS lp
                        WHERE lp.project_id = %(project_id)s
                          AND lp.document_id = %(document_id)s
                        LIMIT 1
                        """,
                        {"project_id": project_id, "document_id": document_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Layout projection read failed.") from error
        if row is None:
            return None
        return self._as_layout_projection_record(row)

    def get_active_layout_run(
        self,
        *,
        project_id: str,
        document_id: str,
    ) -> LayoutRunRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          lr.id,
                          lr.project_id,
                          lr.document_id,
                          lr.input_preprocess_run_id,
                          lr.run_kind,
                          lr.parent_run_id,
                          lr.attempt_number,
                          lr.superseded_by_run_id,
                          lr.model_id,
                          lr.profile_id,
                          lr.params_json,
                          lr.params_hash,
                          lr.pipeline_version,
                          lr.container_digest,
                          lr.status,
                          lr.created_by,
                          lr.created_at,
                          lr.started_at,
                          lr.finished_at,
                          lr.failure_reason
                        FROM document_layout_projections AS lp
                        INNER JOIN layout_runs AS lr
                          ON lr.id = lp.active_layout_run_id
                        WHERE lp.project_id = %(project_id)s
                          AND lp.document_id = %(document_id)s
                        LIMIT 1
                        """,
                        {"project_id": project_id, "document_id": document_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Active layout run read failed.") from error
        if row is None:
            return None
        return self._as_layout_run_record(row)

    def mark_layout_downstream_transcription_stale(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        reason: str,
        active_layout_snapshot_hash: str | None = None,
    ) -> DocumentLayoutProjectionRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE document_layout_projections AS lp
                        SET
                          downstream_transcription_state = 'STALE',
                          downstream_transcription_invalidated_at = NOW(),
                          downstream_transcription_invalidated_reason = %(reason)s,
                          active_layout_snapshot_hash = COALESCE(
                            %(active_layout_snapshot_hash)s,
                            lp.active_layout_snapshot_hash
                          ),
                          updated_at = NOW()
                        WHERE lp.project_id = %(project_id)s
                          AND lp.document_id = %(document_id)s
                          AND lp.active_layout_run_id = %(run_id)s
                        RETURNING
                          lp.document_id,
                          lp.project_id,
                          lp.active_layout_run_id,
                          lp.active_input_preprocess_run_id,
                          lp.active_layout_snapshot_hash,
                          lp.downstream_transcription_state,
                          lp.downstream_transcription_invalidated_at,
                          lp.downstream_transcription_invalidated_reason,
                          lp.updated_at
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                            "reason": reason,
                            "active_layout_snapshot_hash": active_layout_snapshot_hash,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Layout downstream invalidation failed."
            ) from error
        if row is None:
            return None
        return self._as_layout_projection_record(row)

    def list_page_layout_results(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        status: PageLayoutResultStatus | None = None,
        page_recall_status: PageRecallStatus | None = None,
        cursor: int = 0,
        page_size: int = 100,
    ) -> tuple[list[PageLayoutResultRecord], int | None]:
        self.ensure_schema()
        safe_page_size = max(1, min(page_size, 500))
        safe_cursor = max(0, cursor)
        conditions = [
            "plr.run_id = %(run_id)s",
            "lr.project_id = %(project_id)s",
            "lr.document_id = %(document_id)s",
        ]
        params: dict[str, object] = {
            "run_id": run_id,
            "project_id": project_id,
            "document_id": document_id,
            "limit": safe_page_size + 1,
            "offset": safe_cursor,
        }
        if status is not None:
            conditions.append("plr.status = %(status)s")
            params["status"] = status
        if page_recall_status is not None:
            conditions.append("plr.page_recall_status = %(page_recall_status)s")
            params["page_recall_status"] = page_recall_status
        where_clause = " AND ".join(conditions)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_handle:
                    cursor_handle.execute(
                        f"""
                        SELECT
                          plr.run_id,
                          plr.page_id,
                          plr.page_index,
                          plr.status,
                          plr.page_recall_status,
                          plr.active_layout_version_id,
                          plr.page_xml_key,
                          plr.overlay_json_key,
                          plr.page_xml_sha256,
                          plr.overlay_json_sha256,
                          plr.metrics_json,
                          plr.warnings_json,
                          plr.failure_reason,
                          plr.created_at,
                          plr.updated_at
                        FROM page_layout_results AS plr
                        INNER JOIN layout_runs AS lr
                          ON lr.id = plr.run_id
                        WHERE {where_clause}
                        ORDER BY plr.page_index ASC, plr.page_id ASC
                        LIMIT %(limit)s
                        OFFSET %(offset)s
                        """,
                        params,
                    )
                    rows = cursor_handle.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Page layout-result listing failed."
            ) from error

        has_more = len(rows) > safe_page_size
        selected_rows = rows[:safe_page_size]
        next_cursor = safe_cursor + safe_page_size if has_more else None
        return [self._as_page_layout_result_record(row) for row in selected_rows], next_cursor

    def get_layout_page_result(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> PageLayoutResultRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          plr.run_id,
                          plr.page_id,
                          plr.page_index,
                          plr.status,
                          plr.page_recall_status,
                          plr.active_layout_version_id,
                          plr.page_xml_key,
                          plr.overlay_json_key,
                          plr.page_xml_sha256,
                          plr.overlay_json_sha256,
                          plr.metrics_json,
                          plr.warnings_json,
                          plr.failure_reason,
                          plr.created_at,
                          plr.updated_at
                        FROM page_layout_results AS plr
                        INNER JOIN layout_runs AS lr
                          ON lr.id = plr.run_id
                        WHERE plr.run_id = %(run_id)s
                          AND plr.page_id = %(page_id)s
                          AND lr.project_id = %(project_id)s
                          AND lr.document_id = %(document_id)s
                        LIMIT 1
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "project_id": project_id,
                            "document_id": document_id,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Layout page-result read failed.") from error
        if row is None:
            return None
        return self._as_page_layout_result_record(row)

    def list_approved_models(
        self,
        *,
        model_role: ApprovedModelRole | None = None,
        status: ApprovedModelStatus | None = None,
    ) -> list[ApprovedModelRecord]:
        self.ensure_schema()
        conditions: list[str] = []
        params: dict[str, object] = {}
        if model_role is not None:
            conditions.append("am.model_role = %(model_role)s")
            params["model_role"] = model_role
        if status is not None:
            conditions.append("am.status = %(status)s")
            params["status"] = status
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        f"""
                        SELECT
                          am.id,
                          am.model_type,
                          am.model_role,
                          am.model_family,
                          am.model_version,
                          am.serving_interface,
                          am.engine_family,
                          am.deployment_unit,
                          am.artifact_subpath,
                          am.checksum_sha256,
                          am.runtime_profile,
                          am.response_contract_version,
                          am.metadata_json,
                          am.status,
                          am.approved_by,
                          am.approved_at,
                          am.created_at,
                          am.updated_at
                        FROM approved_models AS am
                        {where_clause}
                        ORDER BY am.model_role ASC, am.updated_at DESC, am.id DESC
                        """,
                        params,
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Approved-model listing failed.") from error
        return [self._as_approved_model_record(row) for row in rows]

    def get_approved_model(self, *, model_id: str) -> ApprovedModelRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          am.id,
                          am.model_type,
                          am.model_role,
                          am.model_family,
                          am.model_version,
                          am.serving_interface,
                          am.engine_family,
                          am.deployment_unit,
                          am.artifact_subpath,
                          am.checksum_sha256,
                          am.runtime_profile,
                          am.response_contract_version,
                          am.metadata_json,
                          am.status,
                          am.approved_by,
                          am.approved_at,
                          am.created_at,
                          am.updated_at
                        FROM approved_models AS am
                        WHERE am.id = %(model_id)s
                        LIMIT 1
                        """,
                        {"model_id": model_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Approved-model lookup failed.") from error
        if row is None:
            return None
        return self._as_approved_model_record(row)

    def create_approved_model(
        self,
        *,
        model_type: ApprovedModelType,
        model_role: ApprovedModelRole,
        model_family: str,
        model_version: str,
        serving_interface: ApprovedModelServingInterface,
        engine_family: str,
        deployment_unit: str,
        artifact_subpath: str,
        checksum_sha256: str,
        runtime_profile: str,
        response_contract_version: str,
        metadata_json: dict[str, object] | None,
        created_by: str,
    ) -> ApprovedModelRecord:
        self.ensure_schema()
        safe_model_type = self._assert_approved_model_type(str(model_type))
        safe_model_role = self._assert_approved_model_role(str(model_role))
        safe_serving_interface = self._assert_approved_model_serving_interface(
            str(serving_interface)
        )
        safe_model_family = model_family.strip()
        safe_model_version = model_version.strip()
        safe_engine_family = engine_family.strip()
        safe_deployment_unit = deployment_unit.strip()
        safe_artifact_subpath = artifact_subpath.strip().strip("/")
        safe_runtime_profile = runtime_profile.strip()
        safe_response_contract_version = response_contract_version.strip()
        safe_checksum = checksum_sha256.strip().lower()
        if (
            len(safe_checksum) != 64
            or any(ch not in "0123456789abcdef" for ch in safe_checksum)
        ):
            raise DocumentModelCatalogConflictError(
                "checksumSha256 must be a 64-character hexadecimal string."
            )
        if not safe_model_family or len(safe_model_family) > 120:
            raise DocumentModelCatalogConflictError(
                "modelFamily must be between 1 and 120 characters."
            )
        if not safe_model_version or len(safe_model_version) > 120:
            raise DocumentModelCatalogConflictError(
                "modelVersion must be between 1 and 120 characters."
            )
        if not safe_engine_family or len(safe_engine_family) > 120:
            raise DocumentModelCatalogConflictError(
                "engineFamily must be between 1 and 120 characters."
            )
        if not safe_deployment_unit or len(safe_deployment_unit) > 160:
            raise DocumentModelCatalogConflictError(
                "deploymentUnit must be between 1 and 160 characters."
            )
        if not safe_artifact_subpath or len(safe_artifact_subpath) > 240:
            raise DocumentModelCatalogConflictError(
                "artifactSubpath must be between 1 and 240 characters."
            )
        if safe_artifact_subpath.startswith("..") or "/../" in f"/{safe_artifact_subpath}/":
            raise DocumentModelCatalogConflictError(
                "artifactSubpath must stay within the model artifact root."
            )
        if not safe_runtime_profile or len(safe_runtime_profile) > 120:
            raise DocumentModelCatalogConflictError(
                "runtimeProfile must be between 1 and 120 characters."
            )
        if (
            not safe_response_contract_version
            or len(safe_response_contract_version) > 120
        ):
            raise DocumentModelCatalogConflictError(
                "responseContractVersion must be between 1 and 120 characters."
            )
        metadata_payload = metadata_json if isinstance(metadata_json, dict) else {}
        metadata_serialized = self._serialize_json_payload(metadata_payload)

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    model_id = str(uuid4())
                    cursor.execute(
                        """
                        INSERT INTO approved_models (
                          id,
                          model_type,
                          model_role,
                          model_family,
                          model_version,
                          serving_interface,
                          engine_family,
                          deployment_unit,
                          artifact_subpath,
                          checksum_sha256,
                          runtime_profile,
                          response_contract_version,
                          metadata_json,
                          status,
                          approved_by,
                          approved_at
                        )
                        VALUES (
                          %(id)s,
                          %(model_type)s,
                          %(model_role)s,
                          %(model_family)s,
                          %(model_version)s,
                          %(serving_interface)s,
                          %(engine_family)s,
                          %(deployment_unit)s,
                          %(artifact_subpath)s,
                          %(checksum_sha256)s,
                          %(runtime_profile)s,
                          %(response_contract_version)s,
                          %(metadata_json)s::jsonb,
                          'APPROVED',
                          %(approved_by)s,
                          NOW()
                        )
                        RETURNING
                          id,
                          model_type,
                          model_role,
                          model_family,
                          model_version,
                          serving_interface,
                          engine_family,
                          deployment_unit,
                          artifact_subpath,
                          checksum_sha256,
                          runtime_profile,
                          response_contract_version,
                          metadata_json,
                          status,
                          approved_by,
                          approved_at,
                          created_at,
                          updated_at
                        """,
                        {
                            "id": model_id,
                            "model_type": safe_model_type,
                            "model_role": safe_model_role,
                            "model_family": safe_model_family,
                            "model_version": safe_model_version,
                            "serving_interface": safe_serving_interface,
                            "engine_family": safe_engine_family,
                            "deployment_unit": safe_deployment_unit,
                            "artifact_subpath": safe_artifact_subpath,
                            "checksum_sha256": safe_checksum,
                            "runtime_profile": safe_runtime_profile,
                            "response_contract_version": safe_response_contract_version,
                            "metadata_json": metadata_serialized,
                            "approved_by": created_by,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Approved-model create failed.") from error
        if row is None:
            raise DocumentStoreUnavailableError("Approved-model create failed.")
        return self._as_approved_model_record(row)

    def list_project_model_assignments(
        self,
        *,
        project_id: str,
    ) -> list[ProjectModelAssignmentRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          pma.id,
                          pma.project_id,
                          pma.model_role,
                          pma.approved_model_id,
                          pma.status,
                          pma.assignment_reason,
                          pma.created_by,
                          pma.created_at,
                          pma.activated_by,
                          pma.activated_at,
                          pma.retired_by,
                          pma.retired_at
                        FROM project_model_assignments AS pma
                        WHERE pma.project_id = %(project_id)s
                        ORDER BY
                          CASE pma.status
                            WHEN 'ACTIVE' THEN 0
                            WHEN 'DRAFT' THEN 1
                            ELSE 2
                          END ASC,
                          pma.created_at DESC,
                          pma.id DESC
                        """,
                        {"project_id": project_id},
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Project model-assignment listing failed.") from error
        return [self._as_project_model_assignment_record(row) for row in rows]

    def get_project_model_assignment(
        self,
        *,
        project_id: str,
        assignment_id: str,
    ) -> ProjectModelAssignmentRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          pma.id,
                          pma.project_id,
                          pma.model_role,
                          pma.approved_model_id,
                          pma.status,
                          pma.assignment_reason,
                          pma.created_by,
                          pma.created_at,
                          pma.activated_by,
                          pma.activated_at,
                          pma.retired_by,
                          pma.retired_at
                        FROM project_model_assignments AS pma
                        WHERE pma.project_id = %(project_id)s
                          AND pma.id = %(assignment_id)s
                        LIMIT 1
                        """,
                        {"project_id": project_id, "assignment_id": assignment_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Project model-assignment read failed.") from error
        if row is None:
            return None
        return self._as_project_model_assignment_record(row)

    def get_active_project_model_assignment(
        self,
        *,
        project_id: str,
        model_role: ApprovedModelRole,
    ) -> ProjectModelAssignmentRecord | None:
        self.ensure_schema()
        safe_model_role = self._assert_approved_model_role(str(model_role))
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          pma.id,
                          pma.project_id,
                          pma.model_role,
                          pma.approved_model_id,
                          pma.status,
                          pma.assignment_reason,
                          pma.created_by,
                          pma.created_at,
                          pma.activated_by,
                          pma.activated_at,
                          pma.retired_by,
                          pma.retired_at
                        FROM project_model_assignments AS pma
                        WHERE pma.project_id = %(project_id)s
                          AND pma.model_role = %(model_role)s
                          AND pma.status = 'ACTIVE'
                        ORDER BY pma.activated_at DESC NULLS LAST, pma.created_at DESC
                        LIMIT 1
                        """,
                        {"project_id": project_id, "model_role": safe_model_role},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Project active model-assignment lookup failed."
            ) from error
        if row is None:
            return None
        return self._as_project_model_assignment_record(row)

    def create_project_model_assignment(
        self,
        *,
        project_id: str,
        model_role: ApprovedModelRole,
        approved_model_id: str,
        assignment_reason: str,
        created_by: str,
    ) -> ProjectModelAssignmentRecord:
        self.ensure_schema()
        safe_model_role = self._assert_approved_model_role(str(model_role))
        safe_reason = assignment_reason.strip()
        if not safe_reason or len(safe_reason) > 800:
            raise DocumentModelAssignmentConflictError(
                "assignmentReason must be between 1 and 800 characters."
            )
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT p.id
                        FROM projects AS p
                        WHERE p.id = %(project_id)s
                        LIMIT 1
                        """,
                        {"project_id": project_id},
                    )
                    if cursor.fetchone() is None:
                        raise DocumentNotFoundError("Project not found.")

                    cursor.execute(
                        """
                        SELECT am.id, am.model_role, am.status
                        FROM approved_models AS am
                        WHERE am.id = %(approved_model_id)s
                        LIMIT 1
                        """,
                        {"approved_model_id": approved_model_id},
                    )
                    model_row = cursor.fetchone()
                    if model_row is None:
                        raise DocumentModelAssignmentConflictError(
                            "approvedModelId was not found in approved model catalog."
                        )
                    model_row_role = self._assert_approved_model_role(
                        str(model_row["model_role"])
                    )
                    if model_row_role != safe_model_role:
                        raise DocumentModelAssignmentConflictError(
                            "Assignment role must match the approved model role."
                        )
                    if (
                        self._assert_approved_model_status(str(model_row["status"]))
                        != "APPROVED"
                    ):
                        raise DocumentModelAssignmentConflictError(
                            "Assignments may reference only APPROVED models."
                        )

                    assignment_id = str(uuid4())
                    cursor.execute(
                        """
                        INSERT INTO project_model_assignments (
                          id,
                          project_id,
                          model_role,
                          approved_model_id,
                          status,
                          assignment_reason,
                          created_by,
                          activated_by,
                          activated_at,
                          retired_by,
                          retired_at
                        )
                        VALUES (
                          %(id)s,
                          %(project_id)s,
                          %(model_role)s,
                          %(approved_model_id)s,
                          'DRAFT',
                          %(assignment_reason)s,
                          %(created_by)s,
                          NULL,
                          NULL,
                          NULL,
                          NULL
                        )
                        RETURNING
                          id,
                          project_id,
                          model_role,
                          approved_model_id,
                          status,
                          assignment_reason,
                          created_by,
                          created_at,
                          activated_by,
                          activated_at,
                          retired_by,
                          retired_at
                        """,
                        {
                            "id": assignment_id,
                            "project_id": project_id,
                            "model_role": safe_model_role,
                            "approved_model_id": approved_model_id,
                            "assignment_reason": safe_reason,
                            "created_by": created_by,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except (DocumentNotFoundError, DocumentModelAssignmentConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Project model-assignment create failed."
            ) from error
        if row is None:
            raise DocumentStoreUnavailableError("Project model-assignment create failed.")
        return self._as_project_model_assignment_record(row)

    def activate_project_model_assignment(
        self,
        *,
        project_id: str,
        assignment_id: str,
        activated_by: str,
    ) -> ProjectModelAssignmentRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          pma.id,
                          pma.project_id,
                          pma.model_role,
                          pma.approved_model_id,
                          pma.status,
                          pma.assignment_reason,
                          pma.created_by,
                          pma.created_at,
                          pma.activated_by,
                          pma.activated_at,
                          pma.retired_by,
                          pma.retired_at
                        FROM project_model_assignments AS pma
                        WHERE pma.project_id = %(project_id)s
                          AND pma.id = %(assignment_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {"project_id": project_id, "assignment_id": assignment_id},
                    )
                    assignment_row = cursor.fetchone()
                    if assignment_row is None:
                        return None
                    assignment = self._as_project_model_assignment_record(assignment_row)
                    if assignment.status == "RETIRED":
                        raise DocumentModelAssignmentConflictError(
                            "Retired assignments cannot be activated."
                        )
                    cursor.execute(
                        """
                        SELECT am.id, am.model_role, am.status
                        FROM approved_models AS am
                        WHERE am.id = %(approved_model_id)s
                        LIMIT 1
                        """,
                        {"approved_model_id": assignment.approved_model_id},
                    )
                    model_row = cursor.fetchone()
                    if model_row is None:
                        raise DocumentModelAssignmentConflictError(
                            "Assignment references a missing approved model."
                        )
                    model_row_role = self._assert_approved_model_role(
                        str(model_row["model_role"])
                    )
                    if model_row_role != assignment.model_role:
                        raise DocumentModelAssignmentConflictError(
                            "Assignment role does not match approved model role."
                        )
                    if (
                        self._assert_approved_model_status(str(model_row["status"]))
                        != "APPROVED"
                    ):
                        raise DocumentModelAssignmentConflictError(
                            "Only APPROVED models can be activated for project assignments."
                        )

                    cursor.execute(
                        """
                        UPDATE project_model_assignments
                        SET
                          status = 'RETIRED',
                          retired_by = %(retired_by)s,
                          retired_at = NOW()
                        WHERE project_id = %(project_id)s
                          AND model_role = %(model_role)s
                          AND status = 'ACTIVE'
                          AND id <> %(assignment_id)s
                        """,
                        {
                            "project_id": project_id,
                            "model_role": assignment.model_role,
                            "assignment_id": assignment.id,
                            "retired_by": activated_by,
                        },
                    )
                    cursor.execute(
                        """
                        UPDATE project_model_assignments
                        SET
                          status = 'ACTIVE',
                          activated_by = %(activated_by)s,
                          activated_at = NOW(),
                          retired_by = NULL,
                          retired_at = NULL
                        WHERE project_id = %(project_id)s
                          AND id = %(assignment_id)s
                        RETURNING
                          id,
                          project_id,
                          model_role,
                          approved_model_id,
                          status,
                          assignment_reason,
                          created_by,
                          created_at,
                          activated_by,
                          activated_at,
                          retired_by,
                          retired_at
                        """,
                        {
                            "project_id": project_id,
                            "assignment_id": assignment.id,
                            "activated_by": activated_by,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except DocumentModelAssignmentConflictError:
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Project model-assignment activation failed."
            ) from error
        if row is None:
            return None
        return self._as_project_model_assignment_record(row)

    def retire_project_model_assignment(
        self,
        *,
        project_id: str,
        assignment_id: str,
        retired_by: str,
    ) -> ProjectModelAssignmentRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE project_model_assignments
                        SET
                          status = 'RETIRED',
                          retired_by = %(retired_by)s,
                          retired_at = NOW()
                        WHERE project_id = %(project_id)s
                          AND id = %(assignment_id)s
                        RETURNING
                          id,
                          project_id,
                          model_role,
                          approved_model_id,
                          status,
                          assignment_reason,
                          created_by,
                          created_at,
                          activated_by,
                          activated_at,
                          retired_by,
                          retired_at
                        """,
                        {
                            "project_id": project_id,
                            "assignment_id": assignment_id,
                            "retired_by": retired_by,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Project model-assignment retirement failed."
            ) from error
        if row is None:
            return None
        return self._as_project_model_assignment_record(row)

    def list_training_datasets_for_assignment(
        self,
        *,
        project_id: str,
        assignment_id: str,
    ) -> list[TrainingDatasetRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          td.id,
                          td.project_id,
                          td.source_approved_model_id,
                          td.project_model_assignment_id,
                          td.dataset_kind,
                          td.page_count,
                          td.storage_key,
                          td.dataset_sha256,
                          td.created_by,
                          td.created_at
                        FROM training_datasets AS td
                        WHERE td.project_id = %(project_id)s
                          AND td.project_model_assignment_id = %(assignment_id)s
                        ORDER BY td.created_at DESC, td.id DESC
                        """,
                        {"project_id": project_id, "assignment_id": assignment_id},
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Training-dataset listing failed."
            ) from error
        return [self._as_training_dataset_record(row) for row in rows]

    def get_approved_transcription_model(
        self,
        *,
        preferred_model_id: str | None = None,
        preferred_model_role: ApprovedModelRole = "TRANSCRIPTION_PRIMARY",
    ) -> ApprovedModelRecord | None:
        self.ensure_schema()
        safe_model_role = self._assert_approved_model_role(str(preferred_model_role))
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    if isinstance(preferred_model_id, str) and preferred_model_id.strip():
                        cursor.execute(
                            """
                            SELECT
                              am.id,
                              am.model_type,
                              am.model_role,
                              am.model_family,
                              am.model_version,
                              am.serving_interface,
                              am.engine_family,
                              am.deployment_unit,
                              am.artifact_subpath,
                              am.checksum_sha256,
                              am.runtime_profile,
                              am.response_contract_version,
                              am.metadata_json,
                              am.status,
                              am.approved_by,
                              am.approved_at,
                              am.created_at,
                              am.updated_at
                            FROM approved_models AS am
                            WHERE am.id = %(model_id)s
                              AND am.status = 'APPROVED'
                            LIMIT 1
                            """,
                            {"model_id": preferred_model_id.strip()},
                        )
                        preferred = cursor.fetchone()
                        if preferred is not None:
                            return self._as_approved_model_record(preferred)

                    cursor.execute(
                        """
                        SELECT
                          am.id,
                          am.model_type,
                          am.model_role,
                          am.model_family,
                          am.model_version,
                          am.serving_interface,
                          am.engine_family,
                          am.deployment_unit,
                          am.artifact_subpath,
                          am.checksum_sha256,
                          am.runtime_profile,
                          am.response_contract_version,
                          am.metadata_json,
                          am.status,
                          am.approved_by,
                          am.approved_at,
                          am.created_at,
                          am.updated_at
                        FROM approved_models AS am
                        WHERE am.model_role = %(model_role)s
                          AND am.status = 'APPROVED'
                        ORDER BY am.updated_at DESC, am.id DESC
                        LIMIT 1
                        """,
                        {"model_role": safe_model_role},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Approved-model lookup failed.") from error
        if row is None:
            return None
        return self._as_approved_model_record(row)

    def create_transcription_run(
        self,
        *,
        project_id: str,
        document_id: str,
        created_by: str,
        input_preprocess_run_id: str,
        input_layout_run_id: str,
        input_layout_snapshot_hash: str,
        engine: TranscriptionRunEngine,
        model_id: str,
        project_model_assignment_id: str | None,
        prompt_template_id: str | None,
        prompt_template_sha256: str | None,
        response_schema_version: int,
        confidence_basis: TranscriptionConfidenceBasis,
        confidence_calibration_version: str,
        params_json: dict[str, object],
        pipeline_version: str,
        container_digest: str,
        supersedes_transcription_run_id: str | None = None,
    ) -> TranscriptionRunRecord:
        self.ensure_schema()
        params_payload = self._serialize_json_payload(params_json)
        normalized_engine = self._assert_transcription_run_engine(str(engine))
        normalized_confidence_basis = self._assert_transcription_confidence_basis(
            str(confidence_basis)
        )
        safe_schema_version = max(1, int(response_schema_version))
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "SELECT pg_advisory_xact_lock(hashtext(%(lock_key)s))",
                        {"lock_key": f"transcription_runs|{document_id}"},
                    )
                    cursor.execute(
                        """
                        SELECT d.id
                        FROM documents AS d
                        WHERE d.project_id = %(project_id)s
                          AND d.id = %(document_id)s
                        LIMIT 1
                        """,
                        {"project_id": project_id, "document_id": document_id},
                    )
                    if cursor.fetchone() is None:
                        raise DocumentNotFoundError("Document not found.")

                    cursor.execute(
                        """
                        SELECT pr.id, pr.status
                        FROM preprocess_runs AS pr
                        WHERE pr.project_id = %(project_id)s
                          AND pr.document_id = %(document_id)s
                          AND pr.id = %(input_preprocess_run_id)s
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "input_preprocess_run_id": input_preprocess_run_id,
                        },
                    )
                    preprocess_row = cursor.fetchone()
                    if preprocess_row is None:
                        raise DocumentTranscriptionRunConflictError(
                            "Input preprocess run was not found."
                        )
                    preprocess_status = self._assert_preprocess_run_status(
                        str(preprocess_row["status"])
                    )
                    if preprocess_status != "SUCCEEDED":
                        raise DocumentTranscriptionRunConflictError(
                            "Transcription runs require a SUCCEEDED preprocess input run."
                        )

                    cursor.execute(
                        """
                        SELECT lr.id, lr.status
                        FROM layout_runs AS lr
                        WHERE lr.project_id = %(project_id)s
                          AND lr.document_id = %(document_id)s
                          AND lr.id = %(input_layout_run_id)s
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "input_layout_run_id": input_layout_run_id,
                        },
                    )
                    layout_row = cursor.fetchone()
                    if layout_row is None:
                        raise DocumentTranscriptionRunConflictError(
                            "Input layout run was not found."
                        )
                    layout_status = self._assert_layout_run_status(str(layout_row["status"]))
                    if layout_status != "SUCCEEDED":
                        raise DocumentTranscriptionRunConflictError(
                            "Transcription runs require a SUCCEEDED layout input run."
                        )

                    cursor.execute(
                        """
                        SELECT am.id, am.model_role
                        FROM approved_models AS am
                        WHERE am.id = %(model_id)s
                          AND am.status = 'APPROVED'
                        LIMIT 1
                        """,
                        {"model_id": model_id},
                    )
                    model_row = cursor.fetchone()
                    if model_row is None:
                        raise DocumentTranscriptionRunConflictError(
                            "Transcription model must be an APPROVED model."
                        )
                    model_role = self._assert_approved_model_role(str(model_row["model_role"]))
                    expected_role: ApprovedModelRole = (
                        "TRANSCRIPTION_FALLBACK"
                        if normalized_engine in {"KRAKEN_LINE", "TROCR_LINE", "DAN_PAGE"}
                        else "TRANSCRIPTION_PRIMARY"
                    )
                    if model_role != expected_role:
                        raise DocumentTranscriptionRunConflictError(
                            "Transcription engine and approved model role are incompatible."
                        )

                    if project_model_assignment_id is not None:
                        cursor.execute(
                            """
                            SELECT
                              pma.id,
                              pma.model_role,
                              pma.approved_model_id,
                              pma.status
                            FROM project_model_assignments AS pma
                            WHERE pma.project_id = %(project_id)s
                              AND pma.id = %(project_model_assignment_id)s
                            LIMIT 1
                            """,
                            {
                                "project_id": project_id,
                                "project_model_assignment_id": project_model_assignment_id,
                            },
                        )
                        assignment_row = cursor.fetchone()
                        if assignment_row is None:
                            raise DocumentTranscriptionRunConflictError(
                                "Project model assignment was not found."
                            )
                        assignment_role = self._assert_approved_model_role(
                            str(assignment_row["model_role"])
                        )
                        assignment_status = self._assert_project_model_assignment_status(
                            str(assignment_row["status"])
                        )
                        if assignment_role != expected_role:
                            raise DocumentTranscriptionRunConflictError(
                                "Project model assignment role is incompatible with engine."
                            )
                        if str(assignment_row["approved_model_id"]) != model_id:
                            raise DocumentTranscriptionRunConflictError(
                                "Project model assignment does not resolve to the selected model."
                            )
                        if assignment_status != "ACTIVE":
                            raise DocumentTranscriptionRunConflictError(
                                "Only ACTIVE project model assignments can launch transcription runs."
                            )

                    if supersedes_transcription_run_id is not None:
                        cursor.execute(
                            """
                            SELECT
                              tr.id,
                              tr.superseded_by_transcription_run_id
                            FROM transcription_runs AS tr
                            WHERE tr.project_id = %(project_id)s
                              AND tr.document_id = %(document_id)s
                              AND tr.id = %(supersedes_transcription_run_id)s
                            LIMIT 1
                            FOR UPDATE
                            """,
                            {
                                "project_id": project_id,
                                "document_id": document_id,
                                "supersedes_transcription_run_id": supersedes_transcription_run_id,
                            },
                        )
                        superseded_row = cursor.fetchone()
                        if superseded_row is None:
                            raise DocumentTranscriptionRunConflictError(
                                "Superseded transcription run was not found."
                            )
                        if superseded_row["superseded_by_transcription_run_id"] is not None:
                            raise DocumentTranscriptionRunConflictError(
                                "Superseded transcription run is already superseded."
                            )

                    cursor.execute(
                        """
                        SELECT COALESCE(MAX(tr.attempt_number), 0) AS max_attempt_number
                        FROM transcription_runs AS tr
                        WHERE tr.project_id = %(project_id)s
                          AND tr.document_id = %(document_id)s
                        """,
                        {"project_id": project_id, "document_id": document_id},
                    )
                    max_attempt_row = cursor.fetchone()
                    attempt_number = (
                        int(max_attempt_row["max_attempt_number"]) + 1
                        if max_attempt_row is not None
                        else 1
                    )

                    run_id = str(uuid4())
                    cursor.execute(
                        """
                        INSERT INTO transcription_runs (
                          id,
                          project_id,
                          document_id,
                          input_preprocess_run_id,
                          input_layout_run_id,
                          input_layout_snapshot_hash,
                          engine,
                          model_id,
                          project_model_assignment_id,
                          prompt_template_id,
                          prompt_template_sha256,
                          response_schema_version,
                          confidence_basis,
                          confidence_calibration_version,
                          params_json,
                          pipeline_version,
                          container_digest,
                          attempt_number,
                          supersedes_transcription_run_id,
                          superseded_by_transcription_run_id,
                          status,
                          created_by,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          failure_reason
                        )
                        VALUES (
                          %(id)s,
                          %(project_id)s,
                          %(document_id)s,
                          %(input_preprocess_run_id)s,
                          %(input_layout_run_id)s,
                          %(input_layout_snapshot_hash)s,
                          %(engine)s,
                          %(model_id)s,
                          %(project_model_assignment_id)s,
                          %(prompt_template_id)s,
                          %(prompt_template_sha256)s,
                          %(response_schema_version)s,
                          %(confidence_basis)s,
                          %(confidence_calibration_version)s,
                          %(params_json)s::jsonb,
                          %(pipeline_version)s,
                          %(container_digest)s,
                          %(attempt_number)s,
                          %(supersedes_transcription_run_id)s,
                          NULL,
                          'QUEUED',
                          %(created_by)s,
                          NULL,
                          NULL,
                          NULL,
                          NULL,
                          NULL
                        )
                        """,
                        {
                            "id": run_id,
                            "project_id": project_id,
                            "document_id": document_id,
                            "input_preprocess_run_id": input_preprocess_run_id,
                            "input_layout_run_id": input_layout_run_id,
                            "input_layout_snapshot_hash": input_layout_snapshot_hash,
                            "engine": normalized_engine,
                            "model_id": model_id,
                            "project_model_assignment_id": project_model_assignment_id,
                            "prompt_template_id": prompt_template_id,
                            "prompt_template_sha256": prompt_template_sha256,
                            "response_schema_version": safe_schema_version,
                            "confidence_basis": normalized_confidence_basis,
                            "confidence_calibration_version": confidence_calibration_version,
                            "params_json": params_payload,
                            "pipeline_version": pipeline_version,
                            "container_digest": container_digest,
                            "attempt_number": attempt_number,
                            "supersedes_transcription_run_id": supersedes_transcription_run_id,
                            "created_by": created_by,
                        },
                    )
                    if supersedes_transcription_run_id is not None:
                        cursor.execute(
                            """
                            UPDATE transcription_runs
                            SET superseded_by_transcription_run_id = %(new_run_id)s
                            WHERE id = %(old_run_id)s
                            """,
                            {
                                "new_run_id": run_id,
                                "old_run_id": supersedes_transcription_run_id,
                            },
                        )

                    cursor.execute(
                        """
                        SELECT p.id, p.page_index
                        FROM pages AS p
                        WHERE p.document_id = %(document_id)s
                        ORDER BY p.page_index ASC
                        """,
                        {"document_id": document_id},
                    )
                    page_rows = cursor.fetchall()
                    for page_row in page_rows:
                        cursor.execute(
                            """
                            INSERT INTO page_transcription_results (
                              run_id,
                              page_id,
                              page_index,
                              status,
                              pagexml_out_key,
                              pagexml_out_sha256,
                              raw_model_response_key,
                              raw_model_response_sha256,
                              hocr_out_key,
                              hocr_out_sha256,
                              metrics_json,
                              warnings_json,
                              failure_reason
                            )
                            VALUES (
                              %(run_id)s,
                              %(page_id)s,
                              %(page_index)s,
                              'QUEUED',
                              NULL,
                              NULL,
                              NULL,
                              NULL,
                              NULL,
                              NULL,
                              '{}'::jsonb,
                              '[]'::jsonb,
                              NULL
                            )
                            ON CONFLICT (run_id, page_id) DO NOTHING
                            """,
                            {
                                "run_id": run_id,
                                "page_id": str(page_row["id"]),
                                "page_index": int(page_row["page_index"]),
                            },
                        )

                    cursor.execute(
                        """
                        SELECT
                          tr.id,
                          tr.project_id,
                          tr.document_id,
                          tr.input_preprocess_run_id,
                          tr.input_layout_run_id,
                          tr.input_layout_snapshot_hash,
                          tr.engine,
                          tr.model_id,
                          tr.project_model_assignment_id,
                          tr.prompt_template_id,
                          tr.prompt_template_sha256,
                          tr.response_schema_version,
                          tr.confidence_basis,
                          tr.confidence_calibration_version,
                          tr.params_json,
                          tr.pipeline_version,
                          tr.container_digest,
                          tr.attempt_number,
                          tr.supersedes_transcription_run_id,
                          tr.superseded_by_transcription_run_id,
                          tr.status,
                          tr.created_by,
                          tr.created_at,
                          tr.started_at,
                          tr.finished_at,
                          tr.canceled_by,
                          tr.canceled_at,
                          tr.failure_reason
                        FROM transcription_runs AS tr
                        WHERE tr.id = %(run_id)s
                        LIMIT 1
                        """,
                        {"run_id": run_id},
                    )
                    row = cursor.fetchone()
                connection.commit()
        except (DocumentNotFoundError, DocumentTranscriptionRunConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Transcription run create failed.") from error
        if row is None:
            raise DocumentStoreUnavailableError("Transcription run create failed.")
        return self._as_transcription_run_record(row)

    def list_transcription_runs(
        self,
        *,
        project_id: str,
        document_id: str,
        cursor: int = 0,
        page_size: int = 50,
    ) -> tuple[list[TranscriptionRunRecord], int | None]:
        self.ensure_schema()
        if self.get_document(project_id=project_id, document_id=document_id) is None:
            raise DocumentNotFoundError("Document not found.")
        safe_page_size = max(1, min(page_size, 200))
        safe_cursor = max(0, cursor)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_handle:
                    cursor_handle.execute(
                        """
                        SELECT
                          tr.id,
                          tr.project_id,
                          tr.document_id,
                          tr.input_preprocess_run_id,
                          tr.input_layout_run_id,
                          tr.input_layout_snapshot_hash,
                          tr.engine,
                          tr.model_id,
                          tr.project_model_assignment_id,
                          tr.prompt_template_id,
                          tr.prompt_template_sha256,
                          tr.response_schema_version,
                          tr.confidence_basis,
                          tr.confidence_calibration_version,
                          tr.params_json,
                          tr.pipeline_version,
                          tr.container_digest,
                          tr.attempt_number,
                          tr.supersedes_transcription_run_id,
                          tr.superseded_by_transcription_run_id,
                          tr.status,
                          tr.created_by,
                          tr.created_at,
                          tr.started_at,
                          tr.finished_at,
                          tr.canceled_by,
                          tr.canceled_at,
                          tr.failure_reason
                        FROM transcription_runs AS tr
                        WHERE tr.project_id = %(project_id)s
                          AND tr.document_id = %(document_id)s
                        ORDER BY tr.created_at DESC, tr.id DESC
                        LIMIT %(limit)s
                        OFFSET %(offset)s
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "limit": safe_page_size + 1,
                            "offset": safe_cursor,
                        },
                    )
                    rows = cursor_handle.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Transcription runs read failed.") from error

        has_more = len(rows) > safe_page_size
        selected_rows = rows[:safe_page_size]
        next_cursor = safe_cursor + safe_page_size if has_more else None
        return (
            [self._as_transcription_run_record(row) for row in selected_rows],
            next_cursor,
        )

    def get_transcription_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> TranscriptionRunRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          tr.id,
                          tr.project_id,
                          tr.document_id,
                          tr.input_preprocess_run_id,
                          tr.input_layout_run_id,
                          tr.input_layout_snapshot_hash,
                          tr.engine,
                          tr.model_id,
                          tr.project_model_assignment_id,
                          tr.prompt_template_id,
                          tr.prompt_template_sha256,
                          tr.response_schema_version,
                          tr.confidence_basis,
                          tr.confidence_calibration_version,
                          tr.params_json,
                          tr.pipeline_version,
                          tr.container_digest,
                          tr.attempt_number,
                          tr.supersedes_transcription_run_id,
                          tr.superseded_by_transcription_run_id,
                          tr.status,
                          tr.created_by,
                          tr.created_at,
                          tr.started_at,
                          tr.finished_at,
                          tr.canceled_by,
                          tr.canceled_at,
                          tr.failure_reason
                        FROM transcription_runs AS tr
                        WHERE tr.project_id = %(project_id)s
                          AND tr.document_id = %(document_id)s
                          AND tr.id = %(run_id)s
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Transcription run read failed.") from error
        if row is None:
            return None
        return self._as_transcription_run_record(row)

    def get_transcription_projection(
        self,
        *,
        project_id: str,
        document_id: str,
    ) -> DocumentTranscriptionProjectionRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          tp.document_id,
                          tp.project_id,
                          tp.active_transcription_run_id,
                          tp.active_layout_run_id,
                          tp.active_layout_snapshot_hash,
                          tp.active_preprocess_run_id,
                          tp.downstream_redaction_state,
                          tp.downstream_redaction_invalidated_at,
                          tp.downstream_redaction_invalidated_reason,
                          tp.updated_at
                        FROM document_transcription_projections AS tp
                        WHERE tp.project_id = %(project_id)s
                          AND tp.document_id = %(document_id)s
                        LIMIT 1
                        """,
                        {"project_id": project_id, "document_id": document_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Transcription projection read failed.") from error
        if row is None:
            return None
        return self._as_transcription_projection_record(row)

    def get_active_transcription_run(
        self,
        *,
        project_id: str,
        document_id: str,
    ) -> TranscriptionRunRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          tr.id,
                          tr.project_id,
                          tr.document_id,
                          tr.input_preprocess_run_id,
                          tr.input_layout_run_id,
                          tr.input_layout_snapshot_hash,
                          tr.engine,
                          tr.model_id,
                          tr.project_model_assignment_id,
                          tr.prompt_template_id,
                          tr.prompt_template_sha256,
                          tr.response_schema_version,
                          tr.confidence_basis,
                          tr.confidence_calibration_version,
                          tr.params_json,
                          tr.pipeline_version,
                          tr.container_digest,
                          tr.attempt_number,
                          tr.supersedes_transcription_run_id,
                          tr.superseded_by_transcription_run_id,
                          tr.status,
                          tr.created_by,
                          tr.created_at,
                          tr.started_at,
                          tr.finished_at,
                          tr.canceled_by,
                          tr.canceled_at,
                          tr.failure_reason
                        FROM document_transcription_projections AS tp
                        INNER JOIN transcription_runs AS tr
                          ON tr.id = tp.active_transcription_run_id
                        WHERE tp.project_id = %(project_id)s
                          AND tp.document_id = %(document_id)s
                        LIMIT 1
                        """,
                        {"project_id": project_id, "document_id": document_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Active transcription run read failed."
            ) from error
        if row is None:
            return None
        return self._as_transcription_run_record(row)

    def list_page_transcription_results(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        status: TranscriptionRunStatus | None = None,
        cursor: int = 0,
        page_size: int = 100,
    ) -> tuple[list[PageTranscriptionResultRecord], int | None]:
        self.ensure_schema()
        safe_page_size = max(1, min(page_size, 500))
        safe_cursor = max(0, cursor)
        conditions = [
            "ptr.run_id = %(run_id)s",
            "tr.project_id = %(project_id)s",
            "tr.document_id = %(document_id)s",
        ]
        params: dict[str, object] = {
            "run_id": run_id,
            "project_id": project_id,
            "document_id": document_id,
            "limit": safe_page_size + 1,
            "offset": safe_cursor,
        }
        if status is not None:
            conditions.append("ptr.status = %(status)s")
            params["status"] = status
        where_clause = " AND ".join(conditions)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_handle:
                    cursor_handle.execute(
                        f"""
                        SELECT
                          ptr.run_id,
                          ptr.page_id,
                          ptr.page_index,
                          ptr.status,
                          ptr.pagexml_out_key,
                          ptr.pagexml_out_sha256,
                          ptr.raw_model_response_key,
                          ptr.raw_model_response_sha256,
                          ptr.hocr_out_key,
                          ptr.hocr_out_sha256,
                          ptr.metrics_json,
                          ptr.warnings_json,
                          ptr.failure_reason,
                          ptr.created_at,
                          ptr.updated_at
                        FROM page_transcription_results AS ptr
                        INNER JOIN transcription_runs AS tr
                          ON tr.id = ptr.run_id
                        WHERE {where_clause}
                        ORDER BY ptr.page_index ASC, ptr.page_id ASC
                        LIMIT %(limit)s
                        OFFSET %(offset)s
                        """,
                        params,
                    )
                    rows = cursor_handle.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Transcription page-result listing failed."
            ) from error
        has_more = len(rows) > safe_page_size
        selected_rows = rows[:safe_page_size]
        next_cursor = safe_cursor + safe_page_size if has_more else None
        return (
            [self._as_page_transcription_result_record(row) for row in selected_rows],
            next_cursor,
        )

    def get_page_transcription_result(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> PageTranscriptionResultRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          ptr.run_id,
                          ptr.page_id,
                          ptr.page_index,
                          ptr.status,
                          ptr.pagexml_out_key,
                          ptr.pagexml_out_sha256,
                          ptr.raw_model_response_key,
                          ptr.raw_model_response_sha256,
                          ptr.hocr_out_key,
                          ptr.hocr_out_sha256,
                          ptr.metrics_json,
                          ptr.warnings_json,
                          ptr.failure_reason,
                          ptr.created_at,
                          ptr.updated_at
                        FROM page_transcription_results AS ptr
                        INNER JOIN transcription_runs AS tr
                          ON tr.id = ptr.run_id
                        WHERE ptr.run_id = %(run_id)s
                          AND ptr.page_id = %(page_id)s
                          AND tr.project_id = %(project_id)s
                          AND tr.document_id = %(document_id)s
                        LIMIT 1
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "project_id": project_id,
                            "document_id": document_id,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Transcription page-result read failed."
            ) from error
        if row is None:
            return None
        return self._as_page_transcription_result_record(row)

    def list_line_transcription_results(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> list[LineTranscriptionResultRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          ltr.run_id,
                          ltr.page_id,
                          ltr.line_id,
                          ltr.text_diplomatic,
                          ltr.conf_line,
                          ltr.confidence_basis,
                          ltr.confidence_calibration_version,
                          ltr.alignment_json_key,
                          ltr.char_boxes_key,
                          ltr.schema_validation_status,
                          ltr.flags_json,
                          ltr.machine_output_sha256,
                          ltr.active_transcript_version_id,
                          ltr.version_etag,
                          ltr.token_anchor_status,
                          ltr.created_at,
                          ltr.updated_at
                        FROM line_transcription_results AS ltr
                        INNER JOIN transcription_runs AS tr
                          ON tr.id = ltr.run_id
                        WHERE ltr.run_id = %(run_id)s
                          AND ltr.page_id = %(page_id)s
                          AND tr.project_id = %(project_id)s
                          AND tr.document_id = %(document_id)s
                        ORDER BY ltr.line_id ASC
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "project_id": project_id,
                            "document_id": document_id,
                        },
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Transcription line-result listing failed."
            ) from error
        return [self._as_line_transcription_result_record(row) for row in rows]

    def list_token_transcription_results(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> list[TokenTranscriptionResultRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          ttr.run_id,
                          ttr.page_id,
                          ttr.line_id,
                          ttr.token_id,
                          ttr.token_index,
                          ttr.token_text,
                          ttr.token_confidence,
                          ttr.bbox_json,
                          ttr.polygon_json,
                          ttr.source_kind,
                          ttr.source_ref_id,
                          ttr.projection_basis,
                          ttr.created_at,
                          ttr.updated_at
                        FROM token_transcription_results AS ttr
                        INNER JOIN transcription_runs AS tr
                          ON tr.id = ttr.run_id
                        WHERE ttr.run_id = %(run_id)s
                          AND ttr.page_id = %(page_id)s
                          AND tr.project_id = %(project_id)s
                          AND tr.document_id = %(document_id)s
                        ORDER BY ttr.token_index ASC, ttr.token_id ASC
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "project_id": project_id,
                            "document_id": document_id,
                        },
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Transcription token-result listing failed."
            ) from error
        return [self._as_token_transcription_result_record(row) for row in rows]

    def cancel_transcription_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        canceled_by: str,
    ) -> TranscriptionRunRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT tr.id, tr.status
                        FROM transcription_runs AS tr
                        WHERE tr.project_id = %(project_id)s
                          AND tr.document_id = %(document_id)s
                          AND tr.id = %(run_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    current = cursor.fetchone()
                    if current is None:
                        raise DocumentNotFoundError("Transcription run not found.")
                    current_status = self._assert_transcription_run_status(
                        str(current["status"])
                    )
                    if current_status not in {"QUEUED", "RUNNING"}:
                        raise DocumentTranscriptionRunConflictError(
                            "Transcription run can be canceled only while QUEUED or RUNNING."
                        )

                    cursor.execute(
                        """
                        UPDATE transcription_runs
                        SET
                          status = 'CANCELED',
                          canceled_by = %(canceled_by)s,
                          canceled_at = NOW(),
                          finished_at = NOW(),
                          failure_reason = COALESCE(failure_reason, %(failure_reason)s)
                        WHERE id = %(run_id)s
                        """,
                        {
                            "run_id": run_id,
                            "canceled_by": canceled_by,
                            "failure_reason": f"Canceled by {canceled_by}.",
                        },
                    )
                    cursor.execute(
                        """
                        UPDATE page_transcription_results
                        SET
                          status = 'CANCELED',
                          failure_reason = COALESCE(failure_reason, 'Run canceled before completion.'),
                          updated_at = NOW()
                        WHERE run_id = %(run_id)s
                          AND status IN ('QUEUED', 'RUNNING')
                        """,
                        {"run_id": run_id},
                    )
                    cursor.execute(
                        """
                        SELECT
                          tr.id,
                          tr.project_id,
                          tr.document_id,
                          tr.input_preprocess_run_id,
                          tr.input_layout_run_id,
                          tr.input_layout_snapshot_hash,
                          tr.engine,
                          tr.model_id,
                          tr.project_model_assignment_id,
                          tr.prompt_template_id,
                          tr.prompt_template_sha256,
                          tr.response_schema_version,
                          tr.confidence_basis,
                          tr.confidence_calibration_version,
                          tr.params_json,
                          tr.pipeline_version,
                          tr.container_digest,
                          tr.attempt_number,
                          tr.supersedes_transcription_run_id,
                          tr.superseded_by_transcription_run_id,
                          tr.status,
                          tr.created_by,
                          tr.created_at,
                          tr.started_at,
                          tr.finished_at,
                          tr.canceled_by,
                          tr.canceled_at,
                          tr.failure_reason
                        FROM transcription_runs AS tr
                        WHERE tr.id = %(run_id)s
                        LIMIT 1
                        """,
                        {"run_id": run_id},
                    )
                    row = cursor.fetchone()
                connection.commit()
        except (DocumentNotFoundError, DocumentTranscriptionRunConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Transcription run cancel failed.") from error
        if row is None:
            raise DocumentStoreUnavailableError("Transcription run cancel failed.")
        return self._as_transcription_run_record(row)

    def activate_transcription_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentTranscriptionProjectionRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          tr.id,
                          tr.status,
                          tr.input_layout_run_id,
                          tr.input_layout_snapshot_hash,
                          tr.input_preprocess_run_id
                        FROM transcription_runs AS tr
                        WHERE tr.project_id = %(project_id)s
                          AND tr.document_id = %(document_id)s
                          AND tr.id = %(run_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    run_row = cursor.fetchone()
                    if run_row is None:
                        raise DocumentNotFoundError("Transcription run not found.")
                    run_status = self._assert_transcription_run_status(str(run_row["status"]))
                    if run_status != "SUCCEEDED":
                        raise DocumentTranscriptionRunConflictError(
                            "Only SUCCEEDED transcription runs can be activated."
                        )
                    input_layout_run_id = str(run_row["input_layout_run_id"])
                    input_layout_snapshot_hash = str(run_row["input_layout_snapshot_hash"])
                    input_preprocess_run_id = str(run_row["input_preprocess_run_id"])

                    cursor.execute(
                        """
                        SELECT
                          lp.active_layout_run_id,
                          lp.active_layout_snapshot_hash
                        FROM document_layout_projections AS lp
                        WHERE lp.project_id = %(project_id)s
                          AND lp.document_id = %(document_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {"project_id": project_id, "document_id": document_id},
                    )
                    layout_projection = cursor.fetchone()
                    if layout_projection is None:
                        raise DocumentTranscriptionRunConflictError(
                            "Activation requires an active layout projection."
                        )
                    active_layout_run_id = (
                        str(layout_projection["active_layout_run_id"])
                        if isinstance(layout_projection.get("active_layout_run_id"), str)
                        else None
                    )
                    active_layout_snapshot_hash = (
                        str(layout_projection["active_layout_snapshot_hash"])
                        if isinstance(
                            layout_projection.get("active_layout_snapshot_hash"), str
                        )
                        else None
                    )
                    if active_layout_run_id != input_layout_run_id:
                        raise DocumentTranscriptionRunConflictError(
                            "Transcription run layout basis is stale against active layout projection."
                        )
                    if (
                        active_layout_snapshot_hash is not None
                        and active_layout_snapshot_hash != input_layout_snapshot_hash
                    ):
                        raise DocumentTranscriptionRunConflictError(
                            "Transcription run snapshot hash no longer matches active layout basis."
                        )

                    cursor.execute(
                        """
                        SELECT
                          plr.page_id,
                          plr.page_index
                        FROM page_layout_results AS plr
                        WHERE plr.run_id = %(layout_run_id)s
                          AND plr.page_recall_status <> 'NEEDS_MANUAL_REVIEW'
                        ORDER BY plr.page_index ASC, plr.page_id ASC
                        """,
                        {"layout_run_id": input_layout_run_id},
                    )
                    required_anchor_rows = cursor.fetchall()
                    required_page_ids = {
                        str(row["page_id"])
                        for row in required_anchor_rows
                        if isinstance(row.get("page_id"), str)
                    }
                    if required_page_ids:
                        cursor.execute(
                            """
                            SELECT
                              ttr.page_id,
                              COUNT(*)::INT AS token_count
                            FROM token_transcription_results AS ttr
                            WHERE ttr.run_id = %(run_id)s
                              AND ttr.page_id = ANY(%(page_ids)s)
                            GROUP BY ttr.page_id
                            """,
                            {"run_id": run_id, "page_ids": list(required_page_ids)},
                        )
                        token_rows = cursor.fetchall()
                        token_counts = {
                            str(row["page_id"]): int(row["token_count"])
                            for row in token_rows
                            if isinstance(row.get("page_id"), str)
                        }
                        missing_pages = [
                            row
                            for row in required_anchor_rows
                            if token_counts.get(str(row["page_id"]), 0) <= 0
                        ]
                        if missing_pages:
                            first_missing = missing_pages[0]
                            missing_page_number = (
                                int(first_missing["page_index"]) + 1
                                if isinstance(first_missing.get("page_index"), int)
                                else "unknown"
                            )
                            raise DocumentTranscriptionRunConflictError(
                                "Activation requires token anchors for all eligible pages; "
                                f"missing anchors on page {missing_page_number}."
                            )

                    cursor.execute(
                        """
                        SELECT
                          ltr.page_id,
                          ltr.line_id,
                          ltr.token_anchor_status
                        FROM line_transcription_results AS ltr
                        INNER JOIN page_layout_results AS plr
                          ON plr.page_id = ltr.page_id
                         AND plr.run_id = %(layout_run_id)s
                        WHERE ltr.run_id = %(run_id)s
                          AND plr.page_recall_status <> 'NEEDS_MANUAL_REVIEW'
                          AND ltr.token_anchor_status <> 'CURRENT'
                        ORDER BY ltr.page_id ASC, ltr.line_id ASC
                        LIMIT 1
                        """,
                        {
                            "layout_run_id": input_layout_run_id,
                            "run_id": run_id,
                        },
                    )
                    stale_anchor_row = cursor.fetchone()
                    if stale_anchor_row is not None:
                        raise DocumentTranscriptionRunConflictError(
                            "Activation requires CURRENT token-anchor status for all eligible lines."
                        )

                    cursor.execute(
                        """
                        INSERT INTO document_transcription_projections (
                          document_id,
                          project_id,
                          active_transcription_run_id,
                          active_layout_run_id,
                          active_layout_snapshot_hash,
                          active_preprocess_run_id,
                          downstream_redaction_state,
                          downstream_redaction_invalidated_at,
                          downstream_redaction_invalidated_reason,
                          updated_at
                        )
                        VALUES (
                          %(document_id)s,
                          %(project_id)s,
                          %(run_id)s,
                          %(active_layout_run_id)s,
                          %(active_layout_snapshot_hash)s,
                          %(active_preprocess_run_id)s,
                          'NOT_STARTED',
                          NULL,
                          NULL,
                          NOW()
                        )
                        ON CONFLICT (document_id) DO UPDATE
                        SET
                          project_id = EXCLUDED.project_id,
                          active_transcription_run_id = EXCLUDED.active_transcription_run_id,
                          active_layout_run_id = EXCLUDED.active_layout_run_id,
                          active_layout_snapshot_hash = EXCLUDED.active_layout_snapshot_hash,
                          active_preprocess_run_id = EXCLUDED.active_preprocess_run_id,
                          downstream_redaction_state = 'NOT_STARTED',
                          downstream_redaction_invalidated_at = NULL,
                          downstream_redaction_invalidated_reason = NULL,
                          updated_at = NOW()
                        """,
                        {
                            "document_id": document_id,
                            "project_id": project_id,
                            "run_id": run_id,
                            "active_layout_run_id": input_layout_run_id,
                            "active_layout_snapshot_hash": input_layout_snapshot_hash,
                            "active_preprocess_run_id": input_preprocess_run_id,
                        },
                    )

                    cursor.execute(
                        """
                        UPDATE document_layout_projections AS lp
                        SET
                          downstream_transcription_state = 'CURRENT',
                          downstream_transcription_invalidated_at = NULL,
                          downstream_transcription_invalidated_reason = NULL,
                          updated_at = NOW()
                        WHERE lp.project_id = %(project_id)s
                          AND lp.document_id = %(document_id)s
                          AND lp.active_layout_run_id = %(active_layout_run_id)s
                          AND (
                            lp.active_layout_snapshot_hash = %(active_layout_snapshot_hash)s
                            OR lp.active_layout_snapshot_hash IS NULL
                          )
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "active_layout_run_id": input_layout_run_id,
                            "active_layout_snapshot_hash": input_layout_snapshot_hash,
                        },
                    )

                    cursor.execute(
                        """
                        SELECT
                          tp.document_id,
                          tp.project_id,
                          tp.active_transcription_run_id,
                          tp.active_layout_run_id,
                          tp.active_layout_snapshot_hash,
                          tp.active_preprocess_run_id,
                          tp.downstream_redaction_state,
                          tp.downstream_redaction_invalidated_at,
                          tp.downstream_redaction_invalidated_reason,
                          tp.updated_at
                        FROM document_transcription_projections AS tp
                        WHERE tp.project_id = %(project_id)s
                          AND tp.document_id = %(document_id)s
                        LIMIT 1
                        """,
                        {"project_id": project_id, "document_id": document_id},
                    )
                    projection_row = cursor.fetchone()
                connection.commit()
        except (DocumentNotFoundError, DocumentTranscriptionRunConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Transcription run activation failed.") from error
        if projection_row is None:
            raise DocumentStoreUnavailableError("Transcription run activation failed.")
        return self._as_transcription_projection_record(projection_row)

    def get_layout_active_version(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> LayoutVersionRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          lv.id,
                          lv.run_id,
                          lv.page_id,
                          lv.base_version_id,
                          lv.superseded_by_version_id,
                          lv.version_kind,
                          lv.version_etag,
                          lv.page_xml_key,
                          lv.overlay_json_key,
                          lv.page_xml_sha256,
                          lv.overlay_json_sha256,
                          lv.run_snapshot_hash,
                          lv.canonical_payload_json,
                          lv.reading_order_groups_json,
                          lv.reading_order_meta_json,
                          lv.created_by,
                          lv.created_at
                        FROM page_layout_results AS plr
                        INNER JOIN layout_runs AS lr
                          ON lr.id = plr.run_id
                        INNER JOIN layout_versions AS lv
                          ON lv.id = plr.active_layout_version_id
                        WHERE plr.run_id = %(run_id)s
                          AND plr.page_id = %(page_id)s
                          AND lr.project_id = %(project_id)s
                          AND lr.document_id = %(document_id)s
                        LIMIT 1
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "project_id": project_id,
                            "document_id": document_id,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Active layout version read failed."
            ) from error
        if row is None:
            return None
        return self._as_layout_version_record(row)

    def _compute_layout_run_snapshot_hash(
        self,
        *,
        cursor: object,
        run_id: str,
        lock_rows: bool = True,
        replacement_page_id: str | None = None,
        replacement_version_id: str | None = None,
    ) -> str:
        snapshot_cursor = cursor
        if not hasattr(snapshot_cursor, "execute") or not hasattr(snapshot_cursor, "fetchall"):
            raise DocumentStoreUnavailableError("Layout snapshot hash computation failed.")
        lock_clause = "FOR UPDATE" if lock_rows else ""
        snapshot_cursor.execute(
            f"""
            SELECT
              plr.page_id,
              plr.active_layout_version_id
            FROM page_layout_results AS plr
            WHERE plr.run_id = %(run_id)s
            ORDER BY plr.page_index ASC, plr.page_id ASC
            {lock_clause}
            """,
            {"run_id": run_id},
        )
        rows = snapshot_cursor.fetchall()
        seed_parts: list[str] = [run_id]
        for row in rows:
            page_id = str(row["page_id"])
            active_version_id = (
                str(row["active_layout_version_id"])
                if isinstance(row.get("active_layout_version_id"), str)
                else None
            )
            if (
                replacement_page_id is not None
                and replacement_version_id is not None
                and page_id == replacement_page_id
            ):
                active_version_id = replacement_version_id
            seed_parts.append(f"{page_id}:{active_version_id or 'none'}")
        return hashlib.sha256("|".join(seed_parts).encode("utf-8")).hexdigest()

    def bootstrap_layout_page_version(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        version_id: str,
        version_etag: str,
        page_xml_key: str,
        overlay_json_key: str,
        page_xml_sha256: str,
        overlay_json_sha256: str,
        version_kind: LayoutVersionKind,
        canonical_payload_json: dict[str, object],
        reading_order_groups_json: list[dict[str, object]],
        reading_order_meta_json: dict[str, object],
        created_by: str,
    ) -> tuple[LayoutVersionRecord, PageLayoutResultRecord]:
        self.ensure_schema()
        canonical_payload_raw = json.dumps(
            canonical_payload_json,
            sort_keys=True,
            ensure_ascii=True,
        )
        reading_order_groups_raw = json.dumps(
            reading_order_groups_json,
            sort_keys=True,
            ensure_ascii=True,
        )
        reading_order_meta_raw = json.dumps(
            reading_order_meta_json,
            sort_keys=True,
            ensure_ascii=True,
        )
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          plr.run_id,
                          plr.page_id,
                          plr.active_layout_version_id,
                          plr.status,
                          plr.page_recall_status,
                          plr.page_index,
                          plr.page_xml_key,
                          plr.overlay_json_key,
                          plr.page_xml_sha256,
                          plr.overlay_json_sha256,
                          plr.metrics_json,
                          plr.warnings_json,
                          plr.failure_reason,
                          plr.created_at,
                          plr.updated_at
                        FROM page_layout_results AS plr
                        INNER JOIN layout_runs AS lr
                          ON lr.id = plr.run_id
                        WHERE plr.run_id = %(run_id)s
                          AND plr.page_id = %(page_id)s
                          AND lr.project_id = %(project_id)s
                          AND lr.document_id = %(document_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "project_id": project_id,
                            "document_id": document_id,
                        },
                    )
                    page_row = cursor.fetchone()
                    if page_row is None:
                        raise DocumentNotFoundError("Layout page result not found.")
                    active_version_id = (
                        str(page_row["active_layout_version_id"])
                        if isinstance(page_row.get("active_layout_version_id"), str)
                        else None
                    )
                    if active_version_id is not None:
                        cursor.execute(
                            """
                            SELECT
                              lv.id,
                              lv.run_id,
                              lv.page_id,
                              lv.base_version_id,
                              lv.superseded_by_version_id,
                              lv.version_kind,
                              lv.version_etag,
                              lv.page_xml_key,
                              lv.overlay_json_key,
                              lv.page_xml_sha256,
                              lv.overlay_json_sha256,
                              lv.run_snapshot_hash,
                              lv.canonical_payload_json,
                              lv.reading_order_groups_json,
                              lv.reading_order_meta_json,
                              lv.created_by,
                              lv.created_at
                            FROM layout_versions AS lv
                            WHERE lv.id = %(version_id)s
                            LIMIT 1
                            """,
                            {"version_id": active_version_id},
                        )
                        existing = cursor.fetchone()
                        if existing is None:
                            raise DocumentLayoutRunConflictError(
                                "Active layout version projection is inconsistent."
                            )
                        connection.commit()
                        return (
                            self._as_layout_version_record(existing),
                            self._as_page_layout_result_record(page_row),
                        )

                    cursor.execute(
                        """
                        INSERT INTO layout_versions (
                          id,
                          run_id,
                          page_id,
                          base_version_id,
                          superseded_by_version_id,
                          version_kind,
                          version_etag,
                          page_xml_key,
                          overlay_json_key,
                          page_xml_sha256,
                          overlay_json_sha256,
                          run_snapshot_hash,
                          canonical_payload_json,
                          reading_order_groups_json,
                          reading_order_meta_json,
                          created_by
                        )
                        VALUES (
                          %(id)s,
                          %(run_id)s,
                          %(page_id)s,
                          NULL,
                          NULL,
                          %(version_kind)s,
                          %(version_etag)s,
                          %(page_xml_key)s,
                          %(overlay_json_key)s,
                          %(page_xml_sha256)s,
                          %(overlay_json_sha256)s,
                          %(run_snapshot_hash)s,
                          %(canonical_payload_json)s::jsonb,
                          %(reading_order_groups_json)s::jsonb,
                          %(reading_order_meta_json)s::jsonb,
                          %(created_by)s
                        )
                        RETURNING
                          id,
                          run_id,
                          page_id,
                          base_version_id,
                          superseded_by_version_id,
                          version_kind,
                          version_etag,
                          page_xml_key,
                          overlay_json_key,
                          page_xml_sha256,
                          overlay_json_sha256,
                          run_snapshot_hash,
                          canonical_payload_json,
                          reading_order_groups_json,
                          reading_order_meta_json,
                          created_by,
                          created_at
                        """,
                        {
                            "id": version_id,
                            "run_id": run_id,
                            "page_id": page_id,
                            "version_kind": version_kind,
                            "version_etag": version_etag,
                            "page_xml_key": page_xml_key,
                            "overlay_json_key": overlay_json_key,
                            "page_xml_sha256": page_xml_sha256,
                            "overlay_json_sha256": overlay_json_sha256,
                            "run_snapshot_hash": self._compute_layout_run_snapshot_hash(
                                cursor=cursor,
                                run_id=run_id,
                                replacement_page_id=page_id,
                                replacement_version_id=version_id,
                            ),
                            "canonical_payload_json": canonical_payload_raw,
                            "reading_order_groups_json": reading_order_groups_raw,
                            "reading_order_meta_json": reading_order_meta_raw,
                            "created_by": created_by,
                        },
                    )
                    version_row = cursor.fetchone()
                    cursor.execute(
                        """
                        UPDATE page_layout_results AS plr
                        SET
                          active_layout_version_id = %(active_layout_version_id)s,
                          updated_at = NOW()
                        FROM layout_runs AS lr
                        WHERE plr.run_id = %(run_id)s
                          AND plr.page_id = %(page_id)s
                          AND lr.id = plr.run_id
                          AND lr.project_id = %(project_id)s
                          AND lr.document_id = %(document_id)s
                        RETURNING
                          plr.run_id,
                          plr.page_id,
                          plr.page_index,
                          plr.status,
                          plr.page_recall_status,
                          plr.active_layout_version_id,
                          plr.page_xml_key,
                          plr.overlay_json_key,
                          plr.page_xml_sha256,
                          plr.overlay_json_sha256,
                          plr.metrics_json,
                          plr.warnings_json,
                          plr.failure_reason,
                          plr.created_at,
                          plr.updated_at
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "project_id": project_id,
                            "document_id": document_id,
                            "active_layout_version_id": version_id,
                        },
                    )
                    updated_page_row = cursor.fetchone()
                connection.commit()
        except (DocumentNotFoundError, DocumentLayoutRunConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Layout version bootstrap failed."
            ) from error
        if version_row is None or updated_page_row is None:
            raise DocumentStoreUnavailableError("Layout version bootstrap failed.")
        return (
            self._as_layout_version_record(version_row),
            self._as_page_layout_result_record(updated_page_row),
        )

    def append_layout_page_version(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        version_id: str,
        expected_version_etag: str,
        page_xml_key: str,
        overlay_json_key: str,
        page_xml_sha256: str,
        overlay_json_sha256: str,
        version_kind: LayoutVersionKind,
        canonical_payload_json: dict[str, object],
        reading_order_groups_json: list[dict[str, object]],
        reading_order_meta_json: dict[str, object],
        created_by: str,
    ) -> tuple[LayoutVersionRecord, PageLayoutResultRecord]:
        self.ensure_schema()
        canonical_payload_raw = json.dumps(
            canonical_payload_json,
            sort_keys=True,
            ensure_ascii=True,
        )
        reading_order_groups_raw = json.dumps(
            reading_order_groups_json,
            sort_keys=True,
            ensure_ascii=True,
        )
        reading_order_meta_raw = json.dumps(
            reading_order_meta_json,
            sort_keys=True,
            ensure_ascii=True,
        )
        version_etag_seed = (
            f"{run_id}|{page_id}|{version_id}|{page_xml_sha256}|{overlay_json_sha256}"
        )
        version_etag = hashlib.sha256(version_etag_seed.encode("utf-8")).hexdigest()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          plr.run_id,
                          plr.page_id,
                          plr.page_index,
                          plr.status,
                          plr.page_recall_status,
                          plr.active_layout_version_id,
                          plr.page_xml_key,
                          plr.overlay_json_key,
                          plr.page_xml_sha256,
                          plr.overlay_json_sha256,
                          plr.metrics_json,
                          plr.warnings_json,
                          plr.failure_reason,
                          plr.created_at,
                          plr.updated_at
                        FROM page_layout_results AS plr
                        INNER JOIN layout_runs AS lr
                          ON lr.id = plr.run_id
                        WHERE plr.run_id = %(run_id)s
                          AND plr.page_id = %(page_id)s
                          AND lr.project_id = %(project_id)s
                          AND lr.document_id = %(document_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "project_id": project_id,
                            "document_id": document_id,
                        },
                    )
                    page_row = cursor.fetchone()
                    if page_row is None:
                        raise DocumentNotFoundError("Layout page result not found.")
                    active_version_id = (
                        str(page_row["active_layout_version_id"])
                        if isinstance(page_row.get("active_layout_version_id"), str)
                        else None
                    )
                    if active_version_id is None:
                        raise DocumentLayoutRunConflictError(
                            "Layout page has no active version for optimistic update."
                        )
                    cursor.execute(
                        """
                        SELECT
                          lv.id,
                          lv.run_id,
                          lv.page_id,
                          lv.base_version_id,
                          lv.superseded_by_version_id,
                          lv.version_kind,
                          lv.version_etag,
                          lv.page_xml_key,
                          lv.overlay_json_key,
                          lv.page_xml_sha256,
                          lv.overlay_json_sha256,
                          lv.run_snapshot_hash,
                          lv.canonical_payload_json,
                          lv.reading_order_groups_json,
                          lv.reading_order_meta_json,
                          lv.created_by,
                          lv.created_at
                        FROM layout_versions AS lv
                        WHERE lv.id = %(version_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {"version_id": active_version_id},
                    )
                    active_version_row = cursor.fetchone()
                    if active_version_row is None:
                        raise DocumentLayoutRunConflictError(
                            "Active layout version projection is inconsistent."
                        )
                    active_etag = str(active_version_row["version_etag"])
                    if active_etag != expected_version_etag:
                        raise DocumentLayoutRunConflictError(
                            "Layout update conflicts with a newer saved layout version."
                        )

                    cursor.execute(
                        """
                        INSERT INTO layout_versions (
                          id,
                          run_id,
                          page_id,
                          base_version_id,
                          superseded_by_version_id,
                          version_kind,
                          version_etag,
                          page_xml_key,
                          overlay_json_key,
                          page_xml_sha256,
                          overlay_json_sha256,
                          run_snapshot_hash,
                          canonical_payload_json,
                          reading_order_groups_json,
                          reading_order_meta_json,
                          created_by
                        )
                        VALUES (
                          %(id)s,
                          %(run_id)s,
                          %(page_id)s,
                          %(base_version_id)s,
                          NULL,
                          %(version_kind)s,
                          %(version_etag)s,
                          %(page_xml_key)s,
                          %(overlay_json_key)s,
                          %(page_xml_sha256)s,
                          %(overlay_json_sha256)s,
                          %(run_snapshot_hash)s,
                          %(canonical_payload_json)s::jsonb,
                          %(reading_order_groups_json)s::jsonb,
                          %(reading_order_meta_json)s::jsonb,
                          %(created_by)s
                        )
                        RETURNING
                          id,
                          run_id,
                          page_id,
                          base_version_id,
                          superseded_by_version_id,
                          version_kind,
                          version_etag,
                          page_xml_key,
                          overlay_json_key,
                          page_xml_sha256,
                          overlay_json_sha256,
                          run_snapshot_hash,
                          canonical_payload_json,
                          reading_order_groups_json,
                          reading_order_meta_json,
                          created_by,
                          created_at
                        """,
                        {
                            "id": version_id,
                            "run_id": run_id,
                            "page_id": page_id,
                            "base_version_id": active_version_id,
                            "version_kind": version_kind,
                            "version_etag": version_etag,
                            "page_xml_key": page_xml_key,
                            "overlay_json_key": overlay_json_key,
                            "page_xml_sha256": page_xml_sha256,
                            "overlay_json_sha256": overlay_json_sha256,
                            "run_snapshot_hash": self._compute_layout_run_snapshot_hash(
                                cursor=cursor,
                                run_id=run_id,
                                replacement_page_id=page_id,
                                replacement_version_id=version_id,
                            ),
                            "canonical_payload_json": canonical_payload_raw,
                            "reading_order_groups_json": reading_order_groups_raw,
                            "reading_order_meta_json": reading_order_meta_raw,
                            "created_by": created_by,
                        },
                    )
                    new_version_row = cursor.fetchone()
                    cursor.execute(
                        """
                        UPDATE layout_versions
                        SET superseded_by_version_id = %(superseded_by_version_id)s
                        WHERE id = %(id)s
                          AND superseded_by_version_id IS NULL
                        """,
                        {
                            "id": active_version_id,
                            "superseded_by_version_id": version_id,
                        },
                    )
                    cursor.execute(
                        """
                        UPDATE page_layout_results AS plr
                        SET
                          active_layout_version_id = %(active_layout_version_id)s,
                          page_xml_key = %(page_xml_key)s,
                          overlay_json_key = %(overlay_json_key)s,
                          page_xml_sha256 = %(page_xml_sha256)s,
                          overlay_json_sha256 = %(overlay_json_sha256)s,
                          updated_at = NOW()
                        FROM layout_runs AS lr
                        WHERE plr.run_id = %(run_id)s
                          AND plr.page_id = %(page_id)s
                          AND lr.id = plr.run_id
                          AND lr.project_id = %(project_id)s
                          AND lr.document_id = %(document_id)s
                        RETURNING
                          plr.run_id,
                          plr.page_id,
                          plr.page_index,
                          plr.status,
                          plr.page_recall_status,
                          plr.active_layout_version_id,
                          plr.page_xml_key,
                          plr.overlay_json_key,
                          plr.page_xml_sha256,
                          plr.overlay_json_sha256,
                          plr.metrics_json,
                          plr.warnings_json,
                          plr.failure_reason,
                          plr.created_at,
                          plr.updated_at
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "project_id": project_id,
                            "document_id": document_id,
                            "active_layout_version_id": version_id,
                            "page_xml_key": page_xml_key,
                            "overlay_json_key": overlay_json_key,
                            "page_xml_sha256": page_xml_sha256,
                            "overlay_json_sha256": overlay_json_sha256,
                        },
                    )
                    updated_page_row = cursor.fetchone()
                connection.commit()
        except (DocumentNotFoundError, DocumentLayoutRunConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Layout version append failed."
            ) from error
        if new_version_row is None or updated_page_row is None:
            raise DocumentStoreUnavailableError("Layout version append failed.")
        return (
            self._as_layout_version_record(new_version_row),
            self._as_page_layout_result_record(updated_page_row),
        )

    def get_layout_recall_check(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> LayoutRecallCheckRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          lrc.run_id,
                          lrc.page_id,
                          lrc.recall_check_version,
                          lrc.missed_text_risk_score,
                          lrc.signals_json,
                          lrc.created_at
                        FROM layout_recall_checks AS lrc
                        INNER JOIN layout_runs AS lr
                          ON lr.id = lrc.run_id
                        WHERE lrc.run_id = %(run_id)s
                          AND lrc.page_id = %(page_id)s
                          AND lr.project_id = %(project_id)s
                          AND lr.document_id = %(document_id)s
                        ORDER BY lrc.created_at DESC, lrc.recall_check_version DESC
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                            "page_id": page_id,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Layout recall-check read failed.") from error
        if row is None:
            return None
        return self._as_layout_recall_check_record(row)

    def upsert_layout_recall_check(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        recall_check_version: str,
        missed_text_risk_score: float | None,
        signals_json: dict[str, object],
    ) -> LayoutRecallCheckRecord:
        self.ensure_schema()
        version = recall_check_version.strip()
        if not version:
            raise DocumentStoreUnavailableError("Layout recall-check version is required.")
        if len(version) > 120:
            raise DocumentStoreUnavailableError(
                "Layout recall-check version must be 120 characters or fewer."
            )
        if missed_text_risk_score is not None and (
            missed_text_risk_score < 0 or missed_text_risk_score > 1
        ):
            raise DocumentStoreUnavailableError(
                "Layout missed-text risk score must be between 0 and 1."
            )
        payload = json.dumps(signals_json, ensure_ascii=True, sort_keys=True)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          plr.page_id
                        FROM page_layout_results AS plr
                        INNER JOIN layout_runs AS lr
                          ON lr.id = plr.run_id
                        WHERE plr.run_id = %(run_id)s
                          AND plr.page_id = %(page_id)s
                          AND lr.project_id = %(project_id)s
                          AND lr.document_id = %(document_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                            "page_id": page_id,
                        },
                    )
                    page_row = cursor.fetchone()
                    if page_row is None:
                        raise DocumentNotFoundError("Layout page result not found.")

                    cursor.execute(
                        """
                        INSERT INTO layout_recall_checks (
                          run_id,
                          page_id,
                          recall_check_version,
                          missed_text_risk_score,
                          signals_json,
                          created_at
                        )
                        VALUES (
                          %(run_id)s,
                          %(page_id)s,
                          %(recall_check_version)s,
                          %(missed_text_risk_score)s,
                          %(signals_json)s::jsonb,
                          NOW()
                        )
                        ON CONFLICT (run_id, page_id, recall_check_version) DO UPDATE
                        SET
                          missed_text_risk_score = EXCLUDED.missed_text_risk_score,
                          signals_json = EXCLUDED.signals_json,
                          created_at = NOW()
                        RETURNING
                          run_id,
                          page_id,
                          recall_check_version,
                          missed_text_risk_score,
                          signals_json,
                          created_at
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "recall_check_version": version,
                            "missed_text_risk_score": missed_text_risk_score,
                            "signals_json": payload,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except DocumentNotFoundError:
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Layout recall-check persistence failed."
            ) from error
        if row is None:
            raise DocumentStoreUnavailableError("Layout recall-check persistence failed.")
        return self._as_layout_recall_check_record(row)

    def list_layout_rescue_candidates(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> list[LayoutRescueCandidateRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          lrc.id,
                          lrc.run_id,
                          lrc.page_id,
                          lrc.candidate_kind,
                          lrc.geometry_json,
                          lrc.confidence,
                          lrc.source_signal,
                          lrc.status,
                          lrc.created_at,
                          lrc.updated_at
                        FROM layout_rescue_candidates AS lrc
                        INNER JOIN layout_runs AS lr
                          ON lr.id = lrc.run_id
                        WHERE lrc.run_id = %(run_id)s
                          AND lrc.page_id = %(page_id)s
                          AND lr.project_id = %(project_id)s
                          AND lr.document_id = %(document_id)s
                        ORDER BY lrc.created_at ASC, lrc.id ASC
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                            "page_id": page_id,
                        },
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Layout rescue-candidate listing failed."
            ) from error
        return [self._as_layout_rescue_candidate_record(row) for row in rows]

    def replace_layout_rescue_candidates(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        candidates: list[dict[str, object]],
    ) -> list[LayoutRescueCandidateRecord]:
        self.ensure_schema()
        normalized_rows: list[dict[str, object]] = []
        seen_ids: set[str] = set()
        for candidate in candidates:
            raw_id = candidate.get("id")
            if not isinstance(raw_id, str) or not raw_id.strip():
                raise DocumentStoreUnavailableError("Layout rescue candidate id is required.")
            candidate_id = raw_id.strip()
            if candidate_id in seen_ids:
                raise DocumentStoreUnavailableError(
                    "Layout rescue candidate ids must be unique per page."
                )
            seen_ids.add(candidate_id)
            raw_kind = candidate.get("candidate_kind")
            raw_status = candidate.get("status")
            raw_geometry = candidate.get("geometry_json")
            if raw_kind not in {"LINE_EXPANSION", "PAGE_WINDOW"}:
                raise DocumentStoreUnavailableError(
                    "Layout rescue candidate kind is invalid."
                )
            if raw_status not in {"PENDING", "ACCEPTED", "REJECTED", "RESOLVED"}:
                raise DocumentStoreUnavailableError(
                    "Layout rescue candidate status is invalid."
                )
            if not isinstance(raw_geometry, dict):
                raise DocumentStoreUnavailableError(
                    "Layout rescue candidate geometry must be an object."
                )
            raw_confidence = candidate.get("confidence")
            confidence: float | None = None
            if raw_confidence is not None:
                if not isinstance(raw_confidence, (int, float)):
                    raise DocumentStoreUnavailableError(
                        "Layout rescue candidate confidence must be numeric when provided."
                    )
                confidence = float(raw_confidence)
                if confidence < 0 or confidence > 1:
                    raise DocumentStoreUnavailableError(
                        "Layout rescue candidate confidence must be between 0 and 1."
                    )
            source_signal = (
                str(candidate["source_signal"]).strip()
                if isinstance(candidate.get("source_signal"), str)
                and str(candidate["source_signal"]).strip()
                else None
            )
            normalized_rows.append(
                {
                    "id": candidate_id,
                    "candidate_kind": raw_kind,
                    "geometry_json": raw_geometry,
                    "confidence": confidence,
                    "source_signal": source_signal,
                    "status": raw_status,
                }
            )

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          plr.page_id
                        FROM page_layout_results AS plr
                        INNER JOIN layout_runs AS lr
                          ON lr.id = plr.run_id
                        WHERE plr.run_id = %(run_id)s
                          AND plr.page_id = %(page_id)s
                          AND lr.project_id = %(project_id)s
                          AND lr.document_id = %(document_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                            "page_id": page_id,
                        },
                    )
                    page_row = cursor.fetchone()
                    if page_row is None:
                        raise DocumentNotFoundError("Layout page result not found.")

                    cursor.execute(
                        """
                        DELETE FROM layout_rescue_candidates
                        WHERE run_id = %(run_id)s
                          AND page_id = %(page_id)s
                        """,
                        {"run_id": run_id, "page_id": page_id},
                    )

                    for row_payload in normalized_rows:
                        cursor.execute(
                            """
                            INSERT INTO layout_rescue_candidates (
                              id,
                              run_id,
                              page_id,
                              candidate_kind,
                              geometry_json,
                              confidence,
                              source_signal,
                              status,
                              created_at,
                              updated_at
                            )
                            VALUES (
                              %(id)s,
                              %(run_id)s,
                              %(page_id)s,
                              %(candidate_kind)s,
                              %(geometry_json)s::jsonb,
                              %(confidence)s,
                              %(source_signal)s,
                              %(status)s,
                              NOW(),
                              NOW()
                            )
                            """,
                            {
                                "id": row_payload["id"],
                                "run_id": run_id,
                                "page_id": page_id,
                                "candidate_kind": row_payload["candidate_kind"],
                                "geometry_json": json.dumps(
                                    row_payload["geometry_json"],
                                    ensure_ascii=True,
                                    sort_keys=True,
                                ),
                                "confidence": row_payload["confidence"],
                                "source_signal": row_payload["source_signal"],
                                "status": row_payload["status"],
                            },
                        )

                    cursor.execute(
                        """
                        SELECT
                          lrc.id,
                          lrc.run_id,
                          lrc.page_id,
                          lrc.candidate_kind,
                          lrc.geometry_json,
                          lrc.confidence,
                          lrc.source_signal,
                          lrc.status,
                          lrc.created_at,
                          lrc.updated_at
                        FROM layout_rescue_candidates AS lrc
                        WHERE lrc.run_id = %(run_id)s
                          AND lrc.page_id = %(page_id)s
                        ORDER BY lrc.created_at ASC, lrc.id ASC
                        """,
                        {"run_id": run_id, "page_id": page_id},
                    )
                    rows = cursor.fetchall()
                connection.commit()
        except DocumentNotFoundError:
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Layout rescue-candidate persistence failed."
            ) from error
        return [self._as_layout_rescue_candidate_record(row) for row in rows]

    def list_layout_line_artifacts(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        layout_version_id: str | None = None,
    ) -> list[LayoutLineArtifactRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          lla.run_id,
                          lla.page_id,
                          lla.layout_version_id,
                          lla.line_id,
                          lla.region_id,
                          lla.line_crop_key,
                          lla.region_crop_key,
                          lla.page_thumbnail_key,
                          lla.context_window_json_key,
                          lla.artifacts_sha256,
                          lla.created_at
                        FROM layout_line_artifacts AS lla
                        INNER JOIN layout_runs AS lr
                          ON lr.id = lla.run_id
                        INNER JOIN page_layout_results AS plr
                          ON plr.run_id = lla.run_id
                         AND plr.page_id = lla.page_id
                        WHERE lla.run_id = %(run_id)s
                          AND lla.page_id = %(page_id)s
                          AND lr.project_id = %(project_id)s
                          AND lr.document_id = %(document_id)s
                          AND (
                            (
                              %(layout_version_id)s IS NOT NULL
                              AND lla.layout_version_id = %(layout_version_id)s
                            )
                            OR (
                              %(layout_version_id)s IS NULL
                              AND lla.layout_version_id = plr.active_layout_version_id
                            )
                          )
                        ORDER BY lla.line_id ASC
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "project_id": project_id,
                            "document_id": document_id,
                            "layout_version_id": layout_version_id,
                        },
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Layout line-artifact listing failed."
            ) from error
        return [self._as_layout_line_artifact_record(row) for row in rows]

    def get_layout_line_artifact(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        line_id: str,
        layout_version_id: str | None = None,
    ) -> LayoutLineArtifactRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          lla.run_id,
                          lla.page_id,
                          lla.layout_version_id,
                          lla.line_id,
                          lla.region_id,
                          lla.line_crop_key,
                          lla.region_crop_key,
                          lla.page_thumbnail_key,
                          lla.context_window_json_key,
                          lla.artifacts_sha256,
                          lla.created_at
                        FROM layout_line_artifacts AS lla
                        INNER JOIN layout_runs AS lr
                          ON lr.id = lla.run_id
                        INNER JOIN page_layout_results AS plr
                          ON plr.run_id = lla.run_id
                         AND plr.page_id = lla.page_id
                        WHERE lla.run_id = %(run_id)s
                          AND lla.page_id = %(page_id)s
                          AND lla.line_id = %(line_id)s
                          AND lr.project_id = %(project_id)s
                          AND lr.document_id = %(document_id)s
                          AND (
                            (
                              %(layout_version_id)s IS NOT NULL
                              AND lla.layout_version_id = %(layout_version_id)s
                            )
                            OR (
                              %(layout_version_id)s IS NULL
                              AND lla.layout_version_id = plr.active_layout_version_id
                            )
                          )
                        LIMIT 1
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "line_id": line_id,
                            "project_id": project_id,
                            "document_id": document_id,
                            "layout_version_id": layout_version_id,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Layout line-artifact read failed.") from error
        if row is None:
            return None
        return self._as_layout_line_artifact_record(row)

    def replace_layout_line_artifacts(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        layout_version_id: str,
        artifacts: list[dict[str, object]],
    ) -> list[LayoutLineArtifactRecord]:
        self.ensure_schema()
        normalized_layout_version_id = layout_version_id.strip()
        if not normalized_layout_version_id:
            raise DocumentStoreUnavailableError("Layout line artifact version is required.")
        normalized_rows: list[dict[str, object]] = []
        seen_line_ids: set[str] = set()
        for artifact in artifacts:
            raw_line_id = artifact.get("line_id")
            if not isinstance(raw_line_id, str) or not raw_line_id.strip():
                raise DocumentStoreUnavailableError("Layout line artifact line_id is required.")
            line_id = raw_line_id.strip()
            if line_id in seen_line_ids:
                raise DocumentStoreUnavailableError("Layout line artifact line_id must be unique.")
            seen_line_ids.add(line_id)

            raw_line_crop_key = artifact.get("line_crop_key")
            raw_page_thumbnail_key = artifact.get("page_thumbnail_key")
            raw_context_window_key = artifact.get("context_window_json_key")
            raw_artifacts_sha256 = artifact.get("artifacts_sha256")
            if (
                not isinstance(raw_line_crop_key, str)
                or not raw_line_crop_key.strip()
                or not isinstance(raw_page_thumbnail_key, str)
                or not raw_page_thumbnail_key.strip()
                or not isinstance(raw_context_window_key, str)
                or not raw_context_window_key.strip()
                or not isinstance(raw_artifacts_sha256, str)
                or len(raw_artifacts_sha256.strip()) != 64
            ):
                raise DocumentStoreUnavailableError(
                    "Layout line artifact payload is invalid."
                )
            normalized_rows.append(
                {
                    "line_id": line_id,
                    "region_id": (
                        str(artifact["region_id"]).strip()
                        if isinstance(artifact.get("region_id"), str)
                        and str(artifact["region_id"]).strip()
                        else None
                    ),
                    "line_crop_key": raw_line_crop_key.strip(),
                    "region_crop_key": (
                        str(artifact["region_crop_key"]).strip()
                        if isinstance(artifact.get("region_crop_key"), str)
                        and str(artifact["region_crop_key"]).strip()
                        else None
                    ),
                    "page_thumbnail_key": raw_page_thumbnail_key.strip(),
                    "context_window_json_key": raw_context_window_key.strip(),
                    "artifacts_sha256": raw_artifacts_sha256.strip(),
                }
            )

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          plr.page_id
                        FROM page_layout_results AS plr
                        INNER JOIN layout_runs AS lr
                          ON lr.id = plr.run_id
                        WHERE plr.run_id = %(run_id)s
                          AND plr.page_id = %(page_id)s
                          AND lr.project_id = %(project_id)s
                          AND lr.document_id = %(document_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "project_id": project_id,
                            "document_id": document_id,
                        },
                    )
                    page_row = cursor.fetchone()
                    if page_row is None:
                        raise DocumentNotFoundError("Layout page result not found.")
                    cursor.execute(
                        """
                        SELECT
                          lv.id
                        FROM layout_versions AS lv
                        WHERE lv.id = %(layout_version_id)s
                          AND lv.run_id = %(run_id)s
                          AND lv.page_id = %(page_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "layout_version_id": normalized_layout_version_id,
                            "run_id": run_id,
                            "page_id": page_id,
                        },
                    )
                    version_row = cursor.fetchone()
                    if version_row is None:
                        raise DocumentNotFoundError("Layout version not found.")

                    cursor.execute(
                        """
                        DELETE FROM layout_line_artifacts
                        WHERE run_id = %(run_id)s
                          AND page_id = %(page_id)s
                          AND layout_version_id = %(layout_version_id)s
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "layout_version_id": normalized_layout_version_id,
                        },
                    )

                    for artifact_row in normalized_rows:
                        cursor.execute(
                            """
                            INSERT INTO layout_line_artifacts (
                              run_id,
                              page_id,
                              layout_version_id,
                              line_id,
                              region_id,
                              line_crop_key,
                              region_crop_key,
                              page_thumbnail_key,
                              context_window_json_key,
                              artifacts_sha256
                            )
                            VALUES (
                              %(run_id)s,
                              %(page_id)s,
                              %(layout_version_id)s,
                              %(line_id)s,
                              %(region_id)s,
                              %(line_crop_key)s,
                              %(region_crop_key)s,
                              %(page_thumbnail_key)s,
                              %(context_window_json_key)s,
                              %(artifacts_sha256)s
                            )
                            """,
                            {
                                "run_id": run_id,
                                "page_id": page_id,
                                "layout_version_id": normalized_layout_version_id,
                                "line_id": artifact_row["line_id"],
                                "region_id": artifact_row["region_id"],
                                "line_crop_key": artifact_row["line_crop_key"],
                                "region_crop_key": artifact_row["region_crop_key"],
                                "page_thumbnail_key": artifact_row["page_thumbnail_key"],
                                "context_window_json_key": artifact_row[
                                    "context_window_json_key"
                                ],
                                "artifacts_sha256": artifact_row["artifacts_sha256"],
                            },
                        )

                    cursor.execute(
                        """
                        SELECT
                          lla.run_id,
                          lla.page_id,
                          lla.layout_version_id,
                          lla.line_id,
                          lla.region_id,
                          lla.line_crop_key,
                          lla.region_crop_key,
                          lla.page_thumbnail_key,
                          lla.context_window_json_key,
                          lla.artifacts_sha256,
                          lla.created_at
                        FROM layout_line_artifacts AS lla
                        WHERE lla.run_id = %(run_id)s
                          AND lla.page_id = %(page_id)s
                          AND lla.layout_version_id = %(layout_version_id)s
                        ORDER BY lla.line_id ASC
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "layout_version_id": normalized_layout_version_id,
                        },
                    )
                    rows = cursor.fetchall()
                connection.commit()
        except DocumentNotFoundError:
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Layout line-artifact persistence failed."
            ) from error
        return [self._as_layout_line_artifact_record(row) for row in rows]

    def complete_layout_page_result(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        page_xml_key: str,
        overlay_json_key: str,
        page_xml_sha256: str,
        overlay_json_sha256: str,
        metrics_json: dict[str, object],
        warnings_json: list[str],
        page_recall_status: PageRecallStatus,
        active_layout_version_id: str | None = None,
    ) -> PageLayoutResultRecord:
        self.ensure_schema()
        metrics_payload = json.dumps(metrics_json, sort_keys=True, ensure_ascii=True)
        warnings_payload = json.dumps(warnings_json, sort_keys=True, ensure_ascii=True)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE page_layout_results AS plr
                        SET
                          status = 'SUCCEEDED',
                          page_recall_status = %(page_recall_status)s,
                          page_xml_key = %(page_xml_key)s,
                          overlay_json_key = %(overlay_json_key)s,
                          page_xml_sha256 = %(page_xml_sha256)s,
                          overlay_json_sha256 = %(overlay_json_sha256)s,
                          metrics_json = %(metrics_json)s::jsonb,
                          warnings_json = %(warnings_json)s::jsonb,
                          active_layout_version_id = COALESCE(
                            %(active_layout_version_id)s,
                            plr.active_layout_version_id
                          ),
                          failure_reason = NULL,
                          updated_at = NOW()
                        FROM layout_runs AS lr
                        WHERE plr.run_id = %(run_id)s
                          AND plr.page_id = %(page_id)s
                          AND lr.id = plr.run_id
                          AND lr.project_id = %(project_id)s
                          AND lr.document_id = %(document_id)s
                        RETURNING
                          plr.run_id,
                          plr.page_id,
                          plr.page_index,
                          plr.status,
                          plr.page_recall_status,
                          plr.active_layout_version_id,
                          plr.page_xml_key,
                          plr.overlay_json_key,
                          plr.page_xml_sha256,
                          plr.overlay_json_sha256,
                          plr.metrics_json,
                          plr.warnings_json,
                          plr.failure_reason,
                          plr.created_at,
                          plr.updated_at
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "project_id": project_id,
                            "document_id": document_id,
                            "page_recall_status": page_recall_status,
                            "page_xml_key": page_xml_key,
                            "overlay_json_key": overlay_json_key,
                            "page_xml_sha256": page_xml_sha256,
                            "overlay_json_sha256": overlay_json_sha256,
                            "metrics_json": metrics_payload,
                            "warnings_json": warnings_payload,
                            "active_layout_version_id": active_layout_version_id,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Layout page completion failed.") from error
        if row is None:
            raise DocumentNotFoundError("Layout page result not found.")
        return self._as_page_layout_result_record(row)

    def mark_layout_run_running(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> LayoutRunRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          lr.id,
                          lr.status
                        FROM layout_runs AS lr
                        WHERE lr.project_id = %(project_id)s
                          AND lr.document_id = %(document_id)s
                          AND lr.id = %(run_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    current = cursor.fetchone()
                    if current is None:
                        raise DocumentNotFoundError("Layout run not found.")
                    status = self._assert_layout_run_status(str(current["status"]))
                    if status == "QUEUED":
                        cursor.execute(
                            """
                            UPDATE layout_runs
                            SET
                              status = 'RUNNING',
                              started_at = COALESCE(started_at, NOW()),
                              failure_reason = NULL
                            WHERE id = %(run_id)s
                            """,
                            {"run_id": run_id},
                        )
                        cursor.execute(
                            """
                            UPDATE page_layout_results
                            SET
                              status = 'RUNNING',
                              updated_at = NOW()
                            WHERE run_id = %(run_id)s
                              AND status = 'QUEUED'
                            """,
                            {"run_id": run_id},
                        )
                    cursor.execute(
                        """
                        SELECT
                          lr.id,
                          lr.project_id,
                          lr.document_id,
                          lr.input_preprocess_run_id,
                          lr.run_kind,
                          lr.parent_run_id,
                          lr.attempt_number,
                          lr.superseded_by_run_id,
                          lr.model_id,
                          lr.profile_id,
                          lr.params_json,
                          lr.params_hash,
                          lr.pipeline_version,
                          lr.container_digest,
                          lr.status,
                          lr.created_by,
                          lr.created_at,
                          lr.started_at,
                          lr.finished_at,
                          lr.failure_reason
                        FROM layout_runs AS lr
                        WHERE lr.id = %(run_id)s
                        LIMIT 1
                        """,
                        {"run_id": run_id},
                    )
                    row = cursor.fetchone()
                connection.commit()
        except DocumentNotFoundError:
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Layout run transition failed.") from error
        if row is None:
            raise DocumentStoreUnavailableError("Layout run transition failed.")
        return self._as_layout_run_record(row)

    def mark_layout_page_running(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> PageLayoutResultRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE page_layout_results AS plr
                        SET
                          status = 'RUNNING',
                          updated_at = NOW()
                        FROM layout_runs AS lr
                        WHERE plr.run_id = %(run_id)s
                          AND plr.page_id = %(page_id)s
                          AND lr.id = plr.run_id
                          AND lr.project_id = %(project_id)s
                          AND lr.document_id = %(document_id)s
                          AND plr.status IN ('QUEUED', 'RUNNING')
                        RETURNING
                          plr.run_id,
                          plr.page_id,
                          plr.page_index,
                          plr.status,
                          plr.page_recall_status,
                          plr.active_layout_version_id,
                          plr.page_xml_key,
                          plr.overlay_json_key,
                          plr.page_xml_sha256,
                          plr.overlay_json_sha256,
                          plr.metrics_json,
                          plr.warnings_json,
                          plr.failure_reason,
                          plr.created_at,
                          plr.updated_at
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "project_id": project_id,
                            "document_id": document_id,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Layout page transition failed.") from error
        if row is None:
            current = self.get_layout_page_result(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_id=page_id,
            )
            if current is None:
                raise DocumentNotFoundError("Layout page result not found.")
            return current
        return self._as_page_layout_result_record(row)

    def fail_layout_page_result(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        failure_reason: str,
    ) -> PageLayoutResultRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE page_layout_results AS plr
                        SET
                          status = 'FAILED',
                          failure_reason = %(failure_reason)s,
                          updated_at = NOW()
                        FROM layout_runs AS lr
                        WHERE plr.run_id = %(run_id)s
                          AND plr.page_id = %(page_id)s
                          AND lr.id = plr.run_id
                          AND lr.project_id = %(project_id)s
                          AND lr.document_id = %(document_id)s
                        RETURNING
                          plr.run_id,
                          plr.page_id,
                          plr.page_index,
                          plr.status,
                          plr.page_recall_status,
                          plr.active_layout_version_id,
                          plr.page_xml_key,
                          plr.overlay_json_key,
                          plr.page_xml_sha256,
                          plr.overlay_json_sha256,
                          plr.metrics_json,
                          plr.warnings_json,
                          plr.failure_reason,
                          plr.created_at,
                          plr.updated_at
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "project_id": project_id,
                            "document_id": document_id,
                            "failure_reason": failure_reason[:1000],
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Layout page failure update failed.") from error
        if row is None:
            raise DocumentNotFoundError("Layout page result not found.")
        return self._as_page_layout_result_record(row)

    def finalize_layout_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> LayoutRunRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          lr.id,
                          lr.status
                        FROM layout_runs AS lr
                        WHERE lr.project_id = %(project_id)s
                          AND lr.document_id = %(document_id)s
                          AND lr.id = %(run_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    current = cursor.fetchone()
                    if current is None:
                        raise DocumentNotFoundError("Layout run not found.")
                    run_status = self._assert_layout_run_status(str(current["status"]))
                    if run_status != "CANCELED":
                        cursor.execute(
                            """
                            SELECT
                              plr.status,
                              COUNT(*)::INT AS total
                            FROM page_layout_results AS plr
                            WHERE plr.run_id = %(run_id)s
                            GROUP BY plr.status
                            """,
                            {"run_id": run_id},
                        )
                        rows = cursor.fetchall()
                        status_counts: dict[PageLayoutResultStatus, int] = {
                            "QUEUED": 0,
                            "RUNNING": 0,
                            "SUCCEEDED": 0,
                            "FAILED": 0,
                            "CANCELED": 0,
                        }
                        for row in rows:
                            key = self._assert_page_layout_result_status(str(row["status"]))
                            status_counts[key] = int(row["total"])
                        final_status: LayoutRunStatus
                        final_failure_reason: str | None = None
                        if status_counts["FAILED"] > 0:
                            final_status = "FAILED"
                            final_failure_reason = (
                                "One or more layout page tasks failed."
                            )
                        elif status_counts["RUNNING"] > 0 or status_counts["QUEUED"] > 0:
                            final_status = "RUNNING"
                        elif status_counts["SUCCEEDED"] > 0 and status_counts["CANCELED"] == 0:
                            final_status = "SUCCEEDED"
                        elif status_counts["SUCCEEDED"] > 0:
                            final_status = "CANCELED"
                            final_failure_reason = "Run completed with canceled pages."
                        else:
                            final_status = "CANCELED"
                            final_failure_reason = "Run canceled before page completion."

                        if final_status in {"SUCCEEDED", "FAILED", "CANCELED"}:
                            cursor.execute(
                                """
                                UPDATE layout_runs
                                SET
                                  status = %(status)s,
                                  started_at = COALESCE(started_at, NOW()),
                                  finished_at = NOW(),
                                  failure_reason = %(failure_reason)s
                                WHERE id = %(run_id)s
                                """,
                                {
                                    "status": final_status,
                                    "failure_reason": final_failure_reason,
                                    "run_id": run_id,
                                },
                            )
                        elif final_status == "RUNNING":
                            cursor.execute(
                                """
                                UPDATE layout_runs
                                SET
                                  status = 'RUNNING',
                                  started_at = COALESCE(started_at, NOW())
                                WHERE id = %(run_id)s
                                """,
                                {"run_id": run_id},
                            )

                    cursor.execute(
                        """
                        SELECT
                          lr.id,
                          lr.project_id,
                          lr.document_id,
                          lr.input_preprocess_run_id,
                          lr.run_kind,
                          lr.parent_run_id,
                          lr.attempt_number,
                          lr.superseded_by_run_id,
                          lr.model_id,
                          lr.profile_id,
                          lr.params_json,
                          lr.params_hash,
                          lr.pipeline_version,
                          lr.container_digest,
                          lr.status,
                          lr.created_by,
                          lr.created_at,
                          lr.started_at,
                          lr.finished_at,
                          lr.failure_reason
                        FROM layout_runs AS lr
                        WHERE lr.id = %(run_id)s
                        LIMIT 1
                        """,
                        {"run_id": run_id},
                    )
                    row = cursor.fetchone()
                connection.commit()
        except DocumentNotFoundError:
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Layout run finalization failed.") from error
        if row is None:
            raise DocumentStoreUnavailableError("Layout run finalization failed.")
        return self._as_layout_run_record(row)

    def cancel_layout_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        canceled_by: str,
    ) -> LayoutRunRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          lr.id,
                          lr.status
                        FROM layout_runs AS lr
                        WHERE lr.project_id = %(project_id)s
                          AND lr.document_id = %(document_id)s
                          AND lr.id = %(run_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    current = cursor.fetchone()
                    if current is None:
                        raise DocumentNotFoundError("Layout run not found.")
                    current_status = self._assert_layout_run_status(str(current["status"]))
                    if current_status not in {"QUEUED", "RUNNING"}:
                        raise DocumentLayoutRunConflictError(
                            "Layout run can be canceled only while QUEUED or RUNNING."
                        )

                    cursor.execute(
                        """
                        UPDATE layout_runs
                        SET
                          status = 'CANCELED',
                          finished_at = NOW(),
                          failure_reason = COALESCE(failure_reason, %(failure_reason)s)
                        WHERE id = %(run_id)s
                        """,
                        {
                            "run_id": run_id,
                            "failure_reason": f"Canceled by {canceled_by}.",
                        },
                    )
                    cursor.execute(
                        """
                        UPDATE page_layout_results
                        SET
                          status = 'CANCELED',
                          failure_reason = COALESCE(failure_reason, 'Run canceled before completion.'),
                          updated_at = NOW()
                        WHERE run_id = %(run_id)s
                          AND status IN ('QUEUED', 'RUNNING')
                        """,
                        {"run_id": run_id},
                    )
                    cursor.execute(
                        """
                        SELECT
                          lr.id,
                          lr.project_id,
                          lr.document_id,
                          lr.input_preprocess_run_id,
                          lr.run_kind,
                          lr.parent_run_id,
                          lr.attempt_number,
                          lr.superseded_by_run_id,
                          lr.model_id,
                          lr.profile_id,
                          lr.params_json,
                          lr.params_hash,
                          lr.pipeline_version,
                          lr.container_digest,
                          lr.status,
                          lr.created_by,
                          lr.created_at,
                          lr.started_at,
                          lr.finished_at,
                          lr.failure_reason
                        FROM layout_runs AS lr
                        WHERE lr.id = %(run_id)s
                        LIMIT 1
                        """,
                        {"run_id": run_id},
                    )
                    row = cursor.fetchone()
                connection.commit()
        except (DocumentNotFoundError, DocumentLayoutRunConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Layout run cancel failed.") from error

        if row is None:
            raise DocumentStoreUnavailableError("Layout run cancel failed.")
        return self._as_layout_run_record(row)

    def activate_layout_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentLayoutProjectionRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          lr.id,
                          lr.input_preprocess_run_id,
                          lr.status
                        FROM layout_runs AS lr
                        WHERE lr.project_id = %(project_id)s
                          AND lr.document_id = %(document_id)s
                          AND lr.id = %(run_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    run_row = cursor.fetchone()
                    if run_row is None:
                        raise DocumentNotFoundError("Layout run not found.")
                    run_status = self._assert_layout_run_status(str(run_row["status"]))
                    gate = self._evaluate_layout_activation_gate_from_cursor(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                        run_status=run_status,
                        lock_rows=True,
                    )
                    if not gate.eligible:
                        raise DocumentLayoutRunConflictError(
                            self._format_layout_activation_gate_detail(gate),
                            activation_gate=gate,
                        )

                    layout_snapshot_hash = self._compute_layout_run_snapshot_hash(
                        cursor=cursor,
                        run_id=run_id,
                    )
                    downstream_state: DownstreamBasisState = (
                        gate.downstream_impact.transcription_state_after_activation
                    )
                    downstream_reason = gate.downstream_impact.reason
                    cursor.execute(
                        """
                        INSERT INTO document_layout_projections (
                          document_id,
                          project_id,
                          active_layout_run_id,
                          active_input_preprocess_run_id,
                          active_layout_snapshot_hash,
                          downstream_transcription_state,
                          downstream_transcription_invalidated_at,
                          downstream_transcription_invalidated_reason,
                          updated_at
                        )
                        VALUES (
                          %(document_id)s,
                          %(project_id)s,
                          %(run_id)s,
                          %(input_preprocess_run_id)s,
                          %(active_layout_snapshot_hash)s,
                          %(downstream_transcription_state)s,
                          CASE
                            WHEN %(downstream_transcription_state)s = 'STALE' THEN NOW()
                            ELSE NULL
                          END,
                          %(downstream_transcription_invalidated_reason)s,
                          NOW()
                        )
                        ON CONFLICT (document_id) DO UPDATE
                        SET
                          project_id = EXCLUDED.project_id,
                          active_layout_run_id = EXCLUDED.active_layout_run_id,
                          active_input_preprocess_run_id = EXCLUDED.active_input_preprocess_run_id,
                          active_layout_snapshot_hash = EXCLUDED.active_layout_snapshot_hash,
                          downstream_transcription_state = EXCLUDED.downstream_transcription_state,
                          downstream_transcription_invalidated_at = EXCLUDED.downstream_transcription_invalidated_at,
                          downstream_transcription_invalidated_reason = EXCLUDED.downstream_transcription_invalidated_reason,
                          updated_at = NOW()
                        """,
                        {
                            "document_id": document_id,
                            "project_id": project_id,
                            "run_id": run_id,
                            "input_preprocess_run_id": str(
                                run_row["input_preprocess_run_id"]
                            ),
                            "active_layout_snapshot_hash": layout_snapshot_hash,
                            "downstream_transcription_state": downstream_state,
                            "downstream_transcription_invalidated_reason": downstream_reason,
                        },
                    )
                    cursor.execute(
                        """
                        SELECT
                          lp.document_id,
                          lp.project_id,
                          lp.active_layout_run_id,
                          lp.active_input_preprocess_run_id,
                          lp.active_layout_snapshot_hash,
                          lp.downstream_transcription_state,
                          lp.downstream_transcription_invalidated_at,
                          lp.downstream_transcription_invalidated_reason,
                          lp.updated_at
                        FROM document_layout_projections AS lp
                        WHERE lp.project_id = %(project_id)s
                          AND lp.document_id = %(document_id)s
                        LIMIT 1
                        """,
                        {"project_id": project_id, "document_id": document_id},
                    )
                    projection = cursor.fetchone()
                connection.commit()
        except (DocumentNotFoundError, DocumentLayoutRunConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Layout run activation failed.") from error
        if projection is None:
            raise DocumentStoreUnavailableError("Layout run activation failed.")
        return self._as_layout_projection_record(projection)

    def mark_preprocess_run_running(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> PreprocessRunRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          pr.id,
                          pr.status
                        FROM preprocess_runs AS pr
                        WHERE pr.project_id = %(project_id)s
                          AND pr.document_id = %(document_id)s
                          AND pr.id = %(run_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    current = cursor.fetchone()
                    if current is None:
                        raise DocumentNotFoundError("Preprocess run not found.")
                    status = self._assert_preprocess_run_status(str(current["status"]))
                    if status == "QUEUED":
                        cursor.execute(
                            """
                            UPDATE preprocess_runs
                            SET
                              status = 'RUNNING',
                              started_at = COALESCE(started_at, NOW()),
                              failure_reason = NULL
                            WHERE id = %(run_id)s
                            """,
                            {"run_id": run_id},
                        )
                        cursor.execute(
                            """
                            UPDATE page_preprocess_results
                            SET
                              status = 'RUNNING',
                              updated_at = NOW()
                            WHERE run_id = %(run_id)s
                              AND status = 'QUEUED'
                            """,
                            {"run_id": run_id},
                        )
                    cursor.execute(
                        """
                        SELECT
                          pr.id,
                          pr.project_id,
                          pr.document_id,
                          pr.parent_run_id,
                          pr.attempt_number,
                          pr.run_scope,
                          pr.target_page_ids_json,
                          pr.composed_from_run_ids_json,
                          pr.superseded_by_run_id,
                          pr.profile_id,
                          pr.profile_version,
                          pr.profile_revision,
                          pr.profile_label,
                          pr.profile_description,
                          pr.profile_params_hash,
                          pr.profile_is_advanced,
                          pr.profile_is_gated,
                          pr.params_json,
                          pr.params_hash,
                          pr.pipeline_version,
                          pr.container_digest,
                          pr.manifest_object_key,
                          pr.manifest_sha256,
                          pr.manifest_schema_version,
                          pr.status,
                          pr.created_by,
                          pr.created_at,
                          pr.started_at,
                          pr.finished_at,
                          pr.failure_reason
                        FROM preprocess_runs AS pr
                        WHERE pr.id = %(run_id)s
                        LIMIT 1
                        """,
                        {"run_id": run_id},
                    )
                    row = cursor.fetchone()
                connection.commit()
        except DocumentNotFoundError:
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Preprocess run transition failed.") from error
        if row is None:
            raise DocumentStoreUnavailableError("Preprocess run transition failed.")
        return self._as_preprocess_run_record(row)

    def mark_preprocess_page_running(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> PagePreprocessResultRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE page_preprocess_results AS prr
                        SET
                          status = 'RUNNING',
                          updated_at = NOW()
                        FROM preprocess_runs AS pr
                        WHERE prr.run_id = %(run_id)s
                          AND prr.page_id = %(page_id)s
                          AND pr.id = prr.run_id
                          AND pr.project_id = %(project_id)s
                          AND pr.document_id = %(document_id)s
                          AND prr.status IN ('QUEUED', 'RUNNING')
                        RETURNING
                          prr.run_id,
                          prr.page_id,
                          prr.page_index,
                          prr.status,
                          prr.quality_gate_status,
                          prr.input_object_key,
                          prr.input_sha256,
                          prr.source_result_run_id,
                          prr.output_object_key_gray,
                          prr.output_object_key_bin,
                          prr.metrics_object_key,
                          prr.metrics_sha256,
                          prr.metrics_json,
                          prr.sha256_gray,
                          prr.sha256_bin,
                          prr.warnings_json,
                          prr.failure_reason,
                          prr.created_at,
                          prr.updated_at
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "project_id": project_id,
                            "document_id": document_id,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Preprocess page transition failed.") from error
        if row is None:
            current = self.get_preprocess_page_result(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_id=page_id,
            )
            if current is None:
                raise DocumentNotFoundError("Preprocess page result not found.")
            return current
        return self._as_preprocess_page_result_record(row)

    def complete_preprocess_page_result(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        output_object_key_gray: str,
        output_object_key_bin: str | None,
        metrics_object_key: str | None,
        metrics_sha256: str | None,
        metrics_json: dict[str, object],
        sha256_gray: str,
        sha256_bin: str | None,
        warnings_json: list[str],
        quality_gate_status: PreprocessQualityGateStatus,
    ) -> PagePreprocessResultRecord:
        self.ensure_schema()
        metrics_payload = json.dumps(metrics_json, sort_keys=True, ensure_ascii=True)
        warnings_payload = json.dumps(warnings_json, sort_keys=True, ensure_ascii=True)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE page_preprocess_results AS prr
                        SET
                          status = 'SUCCEEDED',
                          quality_gate_status = %(quality_gate_status)s,
                          output_object_key_gray = %(output_object_key_gray)s,
                          output_object_key_bin = %(output_object_key_bin)s,
                          metrics_object_key = %(metrics_object_key)s,
                          metrics_sha256 = %(metrics_sha256)s,
                          metrics_json = %(metrics_json)s::jsonb,
                          sha256_gray = %(sha256_gray)s,
                          sha256_bin = %(sha256_bin)s,
                          warnings_json = %(warnings_json)s::jsonb,
                          failure_reason = NULL,
                          updated_at = NOW()
                        FROM preprocess_runs AS pr
                        WHERE prr.run_id = %(run_id)s
                          AND prr.page_id = %(page_id)s
                          AND pr.id = prr.run_id
                          AND pr.project_id = %(project_id)s
                          AND pr.document_id = %(document_id)s
                        RETURNING
                          prr.run_id,
                          prr.page_id,
                          prr.page_index,
                          prr.status,
                          prr.quality_gate_status,
                          prr.input_object_key,
                          prr.input_sha256,
                          prr.source_result_run_id,
                          prr.output_object_key_gray,
                          prr.output_object_key_bin,
                          prr.metrics_object_key,
                          prr.metrics_sha256,
                          prr.metrics_json,
                          prr.sha256_gray,
                          prr.sha256_bin,
                          prr.warnings_json,
                          prr.failure_reason,
                          prr.created_at,
                          prr.updated_at
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "project_id": project_id,
                            "document_id": document_id,
                            "quality_gate_status": quality_gate_status,
                            "output_object_key_gray": output_object_key_gray,
                            "output_object_key_bin": output_object_key_bin,
                            "metrics_object_key": metrics_object_key,
                            "metrics_sha256": metrics_sha256,
                            "metrics_json": metrics_payload,
                            "sha256_gray": sha256_gray,
                            "sha256_bin": sha256_bin,
                            "warnings_json": warnings_payload,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Preprocess page completion failed.") from error
        if row is None:
            raise DocumentNotFoundError("Preprocess page result not found.")
        return self._as_preprocess_page_result_record(row)

    def fail_preprocess_page_result(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        failure_reason: str,
    ) -> PagePreprocessResultRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE page_preprocess_results AS prr
                        SET
                          status = 'FAILED',
                          failure_reason = %(failure_reason)s,
                          updated_at = NOW()
                        FROM preprocess_runs AS pr
                        WHERE prr.run_id = %(run_id)s
                          AND prr.page_id = %(page_id)s
                          AND pr.id = prr.run_id
                          AND pr.project_id = %(project_id)s
                          AND pr.document_id = %(document_id)s
                        RETURNING
                          prr.run_id,
                          prr.page_id,
                          prr.page_index,
                          prr.status,
                          prr.quality_gate_status,
                          prr.input_object_key,
                          prr.input_sha256,
                          prr.source_result_run_id,
                          prr.output_object_key_gray,
                          prr.output_object_key_bin,
                          prr.metrics_object_key,
                          prr.metrics_sha256,
                          prr.metrics_json,
                          prr.sha256_gray,
                          prr.sha256_bin,
                          prr.warnings_json,
                          prr.failure_reason,
                          prr.created_at,
                          prr.updated_at
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "project_id": project_id,
                            "document_id": document_id,
                            "failure_reason": failure_reason[:1000],
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Preprocess page failure update failed.") from error
        if row is None:
            raise DocumentNotFoundError("Preprocess page result not found.")
        return self._as_preprocess_page_result_record(row)

    def finalize_preprocess_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> PreprocessRunRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          pr.id,
                          pr.status
                        FROM preprocess_runs AS pr
                        WHERE pr.project_id = %(project_id)s
                          AND pr.document_id = %(document_id)s
                          AND pr.id = %(run_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    current = cursor.fetchone()
                    if current is None:
                        raise DocumentNotFoundError("Preprocess run not found.")
                    run_status = self._assert_preprocess_run_status(str(current["status"]))
                    if run_status == "CANCELED":
                        pass
                    else:
                        cursor.execute(
                            """
                            SELECT
                              prr.status,
                              COUNT(*)::INT AS total
                            FROM page_preprocess_results AS prr
                            WHERE prr.run_id = %(run_id)s
                            GROUP BY prr.status
                            """,
                            {"run_id": run_id},
                        )
                        rows = cursor.fetchall()
                        status_counts: dict[PreprocessPageResultStatus, int] = {
                            "QUEUED": 0,
                            "RUNNING": 0,
                            "SUCCEEDED": 0,
                            "FAILED": 0,
                            "CANCELED": 0,
                        }
                        for row in rows:
                            key = self._assert_preprocess_page_result_status(str(row["status"]))
                            status_counts[key] = int(row["total"])
                        final_status: PreprocessRunStatus
                        final_failure_reason: str | None = None
                        if status_counts["FAILED"] > 0:
                            final_status = "FAILED"
                            final_failure_reason = (
                                "One or more preprocess page tasks failed."
                            )
                        elif status_counts["RUNNING"] > 0 or status_counts["QUEUED"] > 0:
                            final_status = "RUNNING"
                        elif status_counts["SUCCEEDED"] > 0 and status_counts["CANCELED"] == 0:
                            final_status = "SUCCEEDED"
                        elif status_counts["SUCCEEDED"] > 0:
                            final_status = "CANCELED"
                            final_failure_reason = "Run completed with canceled pages."
                        else:
                            final_status = "CANCELED"
                            final_failure_reason = "Run canceled before page completion."

                        if final_status in {"SUCCEEDED", "FAILED", "CANCELED"}:
                            cursor.execute(
                                """
                                UPDATE preprocess_runs
                                SET
                                  status = %(status)s,
                                  started_at = COALESCE(started_at, NOW()),
                                  finished_at = NOW(),
                                  failure_reason = %(failure_reason)s
                                WHERE id = %(run_id)s
                                """,
                                {
                                    "status": final_status,
                                    "failure_reason": final_failure_reason,
                                    "run_id": run_id,
                                },
                            )
                        elif final_status == "RUNNING":
                            cursor.execute(
                                """
                                UPDATE preprocess_runs
                                SET
                                  status = 'RUNNING',
                                  started_at = COALESCE(started_at, NOW())
                                WHERE id = %(run_id)s
                                """,
                                {"run_id": run_id},
                            )

                    cursor.execute(
                        """
                        SELECT
                          pr.id,
                          pr.project_id,
                          pr.document_id,
                          pr.parent_run_id,
                          pr.attempt_number,
                          pr.run_scope,
                          pr.target_page_ids_json,
                          pr.composed_from_run_ids_json,
                          pr.superseded_by_run_id,
                          pr.profile_id,
                          pr.profile_version,
                          pr.profile_revision,
                          pr.profile_label,
                          pr.profile_description,
                          pr.profile_params_hash,
                          pr.profile_is_advanced,
                          pr.profile_is_gated,
                          pr.params_json,
                          pr.params_hash,
                          pr.pipeline_version,
                          pr.container_digest,
                          pr.manifest_object_key,
                          pr.manifest_sha256,
                          pr.manifest_schema_version,
                          pr.status,
                          pr.created_by,
                          pr.created_at,
                          pr.started_at,
                          pr.finished_at,
                          pr.failure_reason
                        FROM preprocess_runs AS pr
                        WHERE pr.id = %(run_id)s
                        LIMIT 1
                        """,
                        {"run_id": run_id},
                    )
                    row = cursor.fetchone()
                connection.commit()
        except DocumentNotFoundError:
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Preprocess run finalization failed.") from error
        if row is None:
            raise DocumentStoreUnavailableError("Preprocess run finalization failed.")
        return self._as_preprocess_run_record(row)

    def record_preprocess_run_manifest(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        manifest_object_key: str,
        manifest_sha256: str,
        manifest_schema_version: int = 2,
    ) -> PreprocessRunRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          pr.id,
                          pr.manifest_object_key,
                          pr.manifest_sha256,
                          pr.manifest_schema_version
                        FROM preprocess_runs AS pr
                        WHERE pr.project_id = %(project_id)s
                          AND pr.document_id = %(document_id)s
                          AND pr.id = %(run_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    existing = cursor.fetchone()
                    if existing is None:
                        raise DocumentNotFoundError("Preprocess run not found.")

                    existing_key = (
                        str(existing["manifest_object_key"])
                        if isinstance(existing["manifest_object_key"], str)
                        else None
                    )
                    existing_hash = (
                        str(existing["manifest_sha256"])
                        if isinstance(existing["manifest_sha256"], str)
                        else None
                    )
                    existing_schema = (
                        int(existing["manifest_schema_version"])
                        if isinstance(existing["manifest_schema_version"], int)
                        else 1
                    )
                    if existing_key is not None or existing_hash is not None:
                        if (
                            existing_key != manifest_object_key
                            or existing_hash != manifest_sha256
                            or existing_schema != max(1, manifest_schema_version)
                        ):
                            raise DocumentPreprocessRunConflictError(
                                "Preprocess manifest is immutable once persisted."
                            )
                    else:
                        cursor.execute(
                            """
                            UPDATE preprocess_runs
                            SET
                              manifest_object_key = %(manifest_object_key)s,
                              manifest_sha256 = %(manifest_sha256)s,
                              manifest_schema_version = %(manifest_schema_version)s
                            WHERE id = %(run_id)s
                            """,
                            {
                                "run_id": run_id,
                                "manifest_object_key": manifest_object_key,
                                "manifest_sha256": manifest_sha256,
                                "manifest_schema_version": max(1, manifest_schema_version),
                            },
                        )

                    cursor.execute(
                        """
                        SELECT
                          pr.id,
                          pr.project_id,
                          pr.document_id,
                          pr.parent_run_id,
                          pr.attempt_number,
                          pr.run_scope,
                          pr.target_page_ids_json,
                          pr.composed_from_run_ids_json,
                          pr.superseded_by_run_id,
                          pr.profile_id,
                          pr.profile_version,
                          pr.profile_revision,
                          pr.profile_label,
                          pr.profile_description,
                          pr.profile_params_hash,
                          pr.profile_is_advanced,
                          pr.profile_is_gated,
                          pr.params_json,
                          pr.params_hash,
                          pr.pipeline_version,
                          pr.container_digest,
                          pr.manifest_object_key,
                          pr.manifest_sha256,
                          pr.manifest_schema_version,
                          pr.status,
                          pr.created_by,
                          pr.created_at,
                          pr.started_at,
                          pr.finished_at,
                          pr.failure_reason
                        FROM preprocess_runs AS pr
                        WHERE pr.id = %(run_id)s
                        LIMIT 1
                        """,
                        {"run_id": run_id},
                    )
                    row = cursor.fetchone()
                connection.commit()
        except (DocumentNotFoundError, DocumentPreprocessRunConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Preprocess run manifest persistence failed."
            ) from error
        if row is None:
            raise DocumentStoreUnavailableError("Preprocess run manifest persistence failed.")
        return self._as_preprocess_run_record(row)

    def cancel_preprocess_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        canceled_by: str,
    ) -> PreprocessRunRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          pr.id,
                          pr.status
                        FROM preprocess_runs AS pr
                        WHERE pr.project_id = %(project_id)s
                          AND pr.document_id = %(document_id)s
                          AND pr.id = %(run_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    current = cursor.fetchone()
                    if current is None:
                        raise DocumentNotFoundError("Preprocess run not found.")
                    current_status = self._assert_preprocess_run_status(str(current["status"]))
                    if current_status not in {"QUEUED", "RUNNING"}:
                        raise DocumentPreprocessRunConflictError(
                            "Preprocess run can be canceled only while QUEUED or RUNNING."
                        )

                    cursor.execute(
                        """
                        UPDATE preprocess_runs
                        SET
                          status = 'CANCELED',
                          finished_at = NOW(),
                          failure_reason = COALESCE(failure_reason, %(failure_reason)s)
                        WHERE id = %(run_id)s
                        """,
                        {
                            "run_id": run_id,
                            "failure_reason": f"Canceled by {canceled_by}.",
                        },
                    )
                    cursor.execute(
                        """
                        UPDATE page_preprocess_results
                        SET
                          status = 'CANCELED',
                          failure_reason = COALESCE(failure_reason, 'Run canceled before completion.'),
                          updated_at = NOW()
                        WHERE run_id = %(run_id)s
                          AND status IN ('QUEUED', 'RUNNING')
                        """,
                        {"run_id": run_id},
                    )
                    cursor.execute(
                        """
                        SELECT
                          pr.id,
                          pr.project_id,
                          pr.document_id,
                          pr.parent_run_id,
                          pr.attempt_number,
                          pr.run_scope,
                          pr.target_page_ids_json,
                          pr.composed_from_run_ids_json,
                          pr.superseded_by_run_id,
                          pr.profile_id,
                          pr.profile_version,
                          pr.profile_revision,
                          pr.profile_label,
                          pr.profile_description,
                          pr.profile_params_hash,
                          pr.profile_is_advanced,
                          pr.profile_is_gated,
                          pr.params_json,
                          pr.params_hash,
                          pr.pipeline_version,
                          pr.container_digest,
                          pr.manifest_object_key,
                          pr.manifest_sha256,
                          pr.manifest_schema_version,
                          pr.status,
                          pr.created_by,
                          pr.created_at,
                          pr.started_at,
                          pr.finished_at,
                          pr.failure_reason
                        FROM preprocess_runs AS pr
                        WHERE pr.id = %(run_id)s
                        LIMIT 1
                        """,
                        {"run_id": run_id},
                    )
                    row = cursor.fetchone()
                connection.commit()
        except (DocumentNotFoundError, DocumentPreprocessRunConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Preprocess run cancel failed.") from error

        if row is None:
            raise DocumentStoreUnavailableError("Preprocess run cancel failed.")
        return self._as_preprocess_run_record(row)

    def activate_preprocess_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentPreprocessProjectionRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          pr.id,
                          pr.profile_id,
                          pr.profile_version,
                          pr.profile_revision,
                          pr.params_hash,
                          pr.pipeline_version,
                          pr.container_digest,
                          pr.status
                        FROM preprocess_runs AS pr
                        WHERE pr.project_id = %(project_id)s
                          AND pr.document_id = %(document_id)s
                          AND pr.id = %(run_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    run_row = cursor.fetchone()
                    if run_row is None:
                        raise DocumentNotFoundError("Preprocess run not found.")
                    run_status = self._assert_preprocess_run_status(str(run_row["status"]))
                    if run_status != "SUCCEEDED":
                        raise DocumentPreprocessRunConflictError(
                            "Only SUCCEEDED preprocess runs can be activated."
                        )

                    cursor.execute(
                        """
                        SELECT 1
                        FROM page_preprocess_results AS prr
                        WHERE prr.run_id = %(run_id)s
                          AND prr.quality_gate_status = 'BLOCKED'
                        LIMIT 1
                        """,
                        {"run_id": run_id},
                    )
                    if cursor.fetchone() is not None:
                        raise DocumentPreprocessRunConflictError(
                            "Activation is blocked while any page is BLOCKED."
                        )

                    cursor.execute(
                        """
                        SELECT dp.active_preprocess_run_id
                        FROM document_preprocess_projections AS dp
                        WHERE dp.project_id = %(project_id)s
                          AND dp.document_id = %(document_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {"project_id": project_id, "document_id": document_id},
                    )
                    _ = cursor.fetchone()

                    cursor.execute(
                        """
                        INSERT INTO document_preprocess_projections (
                          document_id,
                          project_id,
                          active_preprocess_run_id,
                          active_profile_id,
                          active_profile_version,
                          active_profile_revision,
                          active_params_hash,
                          active_pipeline_version,
                          active_container_digest,
                          updated_at
                        )
                        VALUES (
                          %(document_id)s,
                          %(project_id)s,
                          %(run_id)s,
                          %(profile_id)s,
                          %(profile_version)s,
                          %(profile_revision)s,
                          %(params_hash)s,
                          %(pipeline_version)s,
                          %(container_digest)s,
                          NOW()
                        )
                        ON CONFLICT (document_id) DO UPDATE
                        SET
                          project_id = EXCLUDED.project_id,
                          active_preprocess_run_id = EXCLUDED.active_preprocess_run_id,
                          active_profile_id = EXCLUDED.active_profile_id,
                          active_profile_version = EXCLUDED.active_profile_version,
                          active_profile_revision = EXCLUDED.active_profile_revision,
                          active_params_hash = EXCLUDED.active_params_hash,
                          active_pipeline_version = EXCLUDED.active_pipeline_version,
                          active_container_digest = EXCLUDED.active_container_digest,
                          updated_at = NOW()
                        """,
                        {
                            "document_id": document_id,
                            "project_id": project_id,
                            "run_id": run_id,
                            "profile_id": str(run_row["profile_id"]),
                            "profile_version": str(run_row["profile_version"]),
                            "profile_revision": int(run_row["profile_revision"]),
                            "params_hash": str(run_row["params_hash"]),
                            "pipeline_version": str(run_row["pipeline_version"]),
                            "container_digest": str(run_row["container_digest"]),
                        },
                    )
                    cursor.execute(
                        """
                        SELECT
                          dp.document_id,
                          dp.project_id,
                          dp.active_preprocess_run_id,
                          dp.active_profile_id,
                          dp.active_profile_version,
                          dp.active_profile_revision,
                          dp.active_params_hash,
                          dp.active_pipeline_version,
                          dp.active_container_digest,
                          lp.active_input_preprocess_run_id AS layout_basis_run_id,
                          CASE
                            WHEN lp.document_id IS NULL THEN 'NOT_STARTED'
                            WHEN lp.active_input_preprocess_run_id = dp.active_preprocess_run_id
                              THEN 'CURRENT'
                            ELSE 'STALE'
                          END AS layout_basis_state,
                          tp.active_preprocess_run_id AS transcription_basis_run_id,
                          CASE
                            WHEN tp.document_id IS NULL THEN 'NOT_STARTED'
                            WHEN tp.active_preprocess_run_id = dp.active_preprocess_run_id
                              THEN 'CURRENT'
                            ELSE 'STALE'
                          END AS transcription_basis_state,
                          dp.updated_at
                        FROM document_preprocess_projections AS dp
                        LEFT JOIN document_layout_projections AS lp
                          ON lp.document_id = dp.document_id
                         AND lp.project_id = dp.project_id
                        LEFT JOIN document_transcription_projections AS tp
                          ON tp.document_id = dp.document_id
                         AND tp.project_id = dp.project_id
                        WHERE dp.project_id = %(project_id)s
                          AND dp.document_id = %(document_id)s
                        LIMIT 1
                        """,
                        {"project_id": project_id, "document_id": document_id},
                    )
                    projection = cursor.fetchone()
                connection.commit()
        except (DocumentNotFoundError, DocumentPreprocessRunConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Preprocess run activation failed.") from error
        if projection is None:
            raise DocumentStoreUnavailableError("Preprocess run activation failed.")
        return self._as_preprocess_projection_record(projection)
