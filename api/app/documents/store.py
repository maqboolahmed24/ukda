import hashlib
import json
from datetime import datetime, timezone
from typing import Mapping, Sequence

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
    TranscriptionRescueResolutionRecord,
    TranscriptionRescueResolutionStatus,
    TranscriptionCompareDecision,
    TranscriptionCompareDecisionEventRecord,
    TranscriptionCompareDecisionRecord,
    TokenTranscriptionResultRecord,
    TranscriptionConfidenceBasis,
    TranscriptionConfidenceBand,
    TranscriptionLineSchemaValidationStatus,
    TranscriptionOutputProjectionRecord,
    TranscriptionProjectionBasis,
    TranscriptionRunEngine,
    TranscriptionRunRecord,
    TranscriptionRunStatus,
    TranscriptionTokenSourceKind,
    RedactionAreaMaskRecord,
    RedactionDecisionActionType,
    RedactionDecisionEventRecord,
    RedactionDecisionStatus,
    RedactionFindingBasisPrimary,
    RedactionFindingRecord,
    RedactionFindingSpanBasisKind,
    RedactionOutputRecord,
    RedactionOutputStatus,
    RedactionOverrideRiskClassification,
    RedactionPageReviewEventRecord,
    RedactionPageReviewEventType,
    RedactionPageReviewRecord,
    RedactionPageReviewStatus,
    RedactionRunKind,
    RedactionRunOutputEventRecord,
    RedactionRunOutputEventType,
    RedactionRunOutputRecord,
    RedactionRunRecord,
    RedactionRunReviewEventRecord,
    RedactionRunReviewEventType,
    RedactionRunReviewRecord,
    RedactionRunReviewStatus,
    RedactionRunStatus,
    RedactionSecondReviewStatus,
    DocumentRedactionProjectionRecord,
    TranscriptVersionRecord,
    TranscriptVariantKind,
    TranscriptVariantLayerRecord,
    TranscriptVariantSuggestionDecision,
    TranscriptVariantSuggestionEventRecord,
    TranscriptVariantSuggestionRecord,
    TranscriptVariantSuggestionStatus,
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
from app.documents.redaction_geometry import (
    RedactionGeometryValidationError,
    normalize_area_mask_geometry,
    normalize_token_refs_and_bbox_refs,
)
from app.documents.redaction_preview import canonical_preview_manifest_sha256
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
    CREATE TABLE IF NOT EXISTS redaction_runs (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      input_transcription_run_id TEXT NOT NULL,
      input_layout_run_id TEXT REFERENCES layout_runs(id),
      run_kind TEXT NOT NULL CHECK (
        run_kind IN ('BASELINE', 'POLICY_RERUN')
      ),
      supersedes_redaction_run_id TEXT REFERENCES redaction_runs(id),
      superseded_by_redaction_run_id TEXT REFERENCES redaction_runs(id),
      policy_snapshot_id TEXT NOT NULL,
      policy_snapshot_json JSONB NOT NULL,
      policy_snapshot_hash TEXT NOT NULL,
      policy_id TEXT,
      policy_family_id TEXT,
      policy_version TEXT,
      detectors_version TEXT NOT NULL,
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
    CREATE INDEX IF NOT EXISTS idx_redaction_runs_scope_created
      ON redaction_runs(project_id, document_id, created_at DESC, id DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS redaction_findings (
      id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL REFERENCES redaction_runs(id) ON DELETE CASCADE,
      page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
      line_id TEXT,
      category TEXT NOT NULL,
      span_start INTEGER,
      span_end INTEGER,
      span_basis_kind TEXT NOT NULL CHECK (
        span_basis_kind IN ('LINE_TEXT', 'PAGE_WINDOW_TEXT', 'NONE')
      ),
      span_basis_ref TEXT,
      confidence DOUBLE PRECISION CHECK (
        confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
      ),
      basis_primary TEXT NOT NULL CHECK (
        basis_primary IN ('RULE', 'NER', 'HEURISTIC')
      ),
      basis_secondary_json JSONB,
      assist_explanation_key TEXT,
      assist_explanation_sha256 TEXT,
      bbox_refs JSONB NOT NULL DEFAULT '{}'::jsonb,
      token_refs_json JSONB,
      area_mask_id TEXT,
      decision_status TEXT NOT NULL CHECK (
        decision_status IN (
          'AUTO_APPLIED',
          'NEEDS_REVIEW',
          'APPROVED',
          'OVERRIDDEN',
          'FALSE_POSITIVE'
        )
      ),
      override_risk_classification TEXT CHECK (
        override_risk_classification IS NULL
        OR override_risk_classification IN ('STANDARD', 'HIGH')
      ),
      override_risk_reason_codes_json JSONB,
      decision_by TEXT REFERENCES users(id),
      decision_at TIMESTAMPTZ,
      decision_reason TEXT,
      decision_etag TEXT NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_redaction_findings_run_page
      ON redaction_findings(run_id, page_id, category, decision_status)
    """,
    """
    CREATE TABLE IF NOT EXISTS redaction_area_masks (
      id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL REFERENCES redaction_runs(id) ON DELETE CASCADE,
      page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
      geometry_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      mask_reason TEXT NOT NULL,
      version_etag TEXT NOT NULL,
      supersedes_area_mask_id TEXT REFERENCES redaction_area_masks(id),
      superseded_by_area_mask_id TEXT REFERENCES redaction_area_masks(id),
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_redaction_area_masks_run_page
      ON redaction_area_masks(run_id, page_id, created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS redaction_decision_events (
      id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL REFERENCES redaction_runs(id) ON DELETE CASCADE,
      page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
      finding_id TEXT NOT NULL REFERENCES redaction_findings(id) ON DELETE CASCADE,
      from_decision_status TEXT CHECK (
        from_decision_status IS NULL
        OR from_decision_status IN (
          'AUTO_APPLIED',
          'NEEDS_REVIEW',
          'APPROVED',
          'OVERRIDDEN',
          'FALSE_POSITIVE'
        )
      ),
      to_decision_status TEXT NOT NULL CHECK (
        to_decision_status IN (
          'AUTO_APPLIED',
          'NEEDS_REVIEW',
          'APPROVED',
          'OVERRIDDEN',
          'FALSE_POSITIVE'
        )
      ),
      action_type TEXT NOT NULL CHECK (
        action_type IN ('MASK', 'PSEUDONYMIZE', 'GENERALIZE')
      ),
      area_mask_id TEXT REFERENCES redaction_area_masks(id),
      actor_user_id TEXT NOT NULL REFERENCES users(id),
      reason TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_redaction_decision_events_scope
      ON redaction_decision_events(run_id, page_id, created_at DESC, id DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS redaction_page_reviews (
      run_id TEXT NOT NULL REFERENCES redaction_runs(id) ON DELETE CASCADE,
      page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
      review_status TEXT NOT NULL CHECK (
        review_status IN ('NOT_STARTED', 'IN_REVIEW', 'APPROVED', 'CHANGES_REQUESTED')
      ),
      review_etag TEXT NOT NULL,
      first_reviewed_by TEXT REFERENCES users(id),
      first_reviewed_at TIMESTAMPTZ,
      requires_second_review BOOLEAN NOT NULL DEFAULT FALSE,
      second_review_status TEXT NOT NULL CHECK (
        second_review_status IN ('NOT_REQUIRED', 'PENDING', 'APPROVED', 'CHANGES_REQUESTED')
      ),
      second_reviewed_by TEXT REFERENCES users(id),
      second_reviewed_at TIMESTAMPTZ,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (run_id, page_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_redaction_page_reviews_scope
      ON redaction_page_reviews(run_id, review_status, updated_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS redaction_page_review_events (
      id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL REFERENCES redaction_runs(id) ON DELETE CASCADE,
      page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
      event_type TEXT NOT NULL CHECK (
        event_type IN (
          'PAGE_OPENED',
          'PAGE_REVIEW_STARTED',
          'PAGE_APPROVED',
          'CHANGES_REQUESTED',
          'SECOND_REVIEW_REQUIRED',
          'SECOND_REVIEW_APPROVED',
          'SECOND_REVIEW_CHANGES_REQUESTED'
        )
      ),
      actor_user_id TEXT NOT NULL REFERENCES users(id),
      reason TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_redaction_page_review_events_scope
      ON redaction_page_review_events(run_id, page_id, created_at DESC, id DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS redaction_run_reviews (
      run_id TEXT PRIMARY KEY REFERENCES redaction_runs(id) ON DELETE CASCADE,
      review_status TEXT NOT NULL CHECK (
        review_status IN ('NOT_READY', 'IN_REVIEW', 'APPROVED', 'CHANGES_REQUESTED')
      ),
      review_started_by TEXT REFERENCES users(id),
      review_started_at TIMESTAMPTZ,
      approved_by TEXT REFERENCES users(id),
      approved_at TIMESTAMPTZ,
      approved_snapshot_key TEXT,
      approved_snapshot_sha256 TEXT,
      locked_at TIMESTAMPTZ,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS redaction_run_review_events (
      id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL REFERENCES redaction_runs(id) ON DELETE CASCADE,
      event_type TEXT NOT NULL CHECK (
        event_type IN ('RUN_REVIEW_OPENED', 'RUN_APPROVED', 'RUN_CHANGES_REQUESTED')
      ),
      actor_user_id TEXT NOT NULL REFERENCES users(id),
      reason TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_redaction_run_review_events_scope
      ON redaction_run_review_events(run_id, created_at DESC, id DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS document_redaction_projections (
      document_id TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      active_redaction_run_id TEXT REFERENCES redaction_runs(id),
      active_transcription_run_id TEXT,
      active_layout_run_id TEXT REFERENCES layout_runs(id),
      active_policy_snapshot_id TEXT,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_document_redaction_projections_scope
      ON document_redaction_projections(project_id, document_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS redaction_outputs (
      run_id TEXT NOT NULL REFERENCES redaction_runs(id) ON DELETE CASCADE,
      page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
      status TEXT NOT NULL CHECK (
        status IN ('PENDING', 'READY', 'FAILED', 'CANCELED')
      ),
      safeguarded_preview_key TEXT,
      preview_sha256 TEXT,
      started_at TIMESTAMPTZ,
      generated_at TIMESTAMPTZ,
      canceled_by TEXT REFERENCES users(id),
      canceled_at TIMESTAMPTZ,
      failure_reason TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (run_id, page_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_redaction_outputs_scope
      ON redaction_outputs(run_id, status, updated_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS redaction_run_outputs (
      run_id TEXT PRIMARY KEY REFERENCES redaction_runs(id) ON DELETE CASCADE,
      status TEXT NOT NULL CHECK (
        status IN ('PENDING', 'READY', 'FAILED', 'CANCELED')
      ),
      output_manifest_key TEXT,
      output_manifest_sha256 TEXT,
      page_count INTEGER NOT NULL DEFAULT 0 CHECK (page_count >= 0),
      started_at TIMESTAMPTZ,
      generated_at TIMESTAMPTZ,
      canceled_by TEXT REFERENCES users(id),
      canceled_at TIMESTAMPTZ,
      failure_reason TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS redaction_run_output_events (
      id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL REFERENCES redaction_runs(id) ON DELETE CASCADE,
      event_type TEXT NOT NULL CHECK (
        event_type IN (
          'RUN_OUTPUT_GENERATION_STARTED',
          'RUN_OUTPUT_GENERATION_SUCCEEDED',
          'RUN_OUTPUT_GENERATION_FAILED',
          'RUN_OUTPUT_GENERATION_CANCELED'
        )
      ),
      from_status TEXT CHECK (
        from_status IS NULL OR from_status IN ('PENDING', 'READY', 'FAILED', 'CANCELED')
      ),
      to_status TEXT NOT NULL CHECK (
        to_status IN ('PENDING', 'READY', 'FAILED', 'CANCELED')
      ),
      reason TEXT,
      actor_user_id TEXT REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_redaction_run_output_events_scope
      ON redaction_run_output_events(run_id, created_at DESC, id DESC)
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
    ALTER TABLE redaction_runs
    DROP CONSTRAINT IF EXISTS redaction_runs_input_transcription_run_id_fkey
    """,
    """
    ALTER TABLE redaction_runs
    ADD CONSTRAINT redaction_runs_input_transcription_run_id_fkey
      FOREIGN KEY (input_transcription_run_id)
      REFERENCES transcription_runs(id)
    """,
    """
    ALTER TABLE document_redaction_projections
    DROP CONSTRAINT IF EXISTS document_redaction_projections_active_transcription_run_id_fkey
    """,
    """
    ALTER TABLE document_redaction_projections
    ADD CONSTRAINT document_redaction_projections_active_transcription_run_id_fkey
      FOREIGN KEY (active_transcription_run_id)
      REFERENCES transcription_runs(id)
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
      reviewer_assignment_user_id TEXT REFERENCES users(id),
      reviewer_assignment_updated_by TEXT REFERENCES users(id),
      reviewer_assignment_updated_at TIMESTAMPTZ,
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
    ALTER TABLE page_transcription_results
    ADD COLUMN IF NOT EXISTS reviewer_assignment_user_id TEXT REFERENCES users(id)
    """,
    """
    ALTER TABLE page_transcription_results
    ADD COLUMN IF NOT EXISTS reviewer_assignment_updated_by TEXT REFERENCES users(id)
    """,
    """
    ALTER TABLE page_transcription_results
    ADD COLUMN IF NOT EXISTS reviewer_assignment_updated_at TIMESTAMPTZ
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
      confidence_band TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK (
        confidence_band IN ('HIGH', 'MEDIUM', 'LOW', 'UNKNOWN')
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
    ALTER TABLE line_transcription_results
    ADD COLUMN IF NOT EXISTS confidence_band TEXT NOT NULL DEFAULT 'UNKNOWN'
      CHECK (confidence_band IN ('HIGH', 'MEDIUM', 'LOW', 'UNKNOWN'))
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
    CREATE TABLE IF NOT EXISTS transcription_rescue_resolutions (
      run_id TEXT NOT NULL REFERENCES transcription_runs(id) ON DELETE CASCADE,
      page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
      resolution_status TEXT NOT NULL CHECK (
        resolution_status IN ('RESCUE_VERIFIED', 'MANUAL_REVIEW_RESOLVED')
      ),
      resolution_reason TEXT,
      updated_by TEXT NOT NULL REFERENCES users(id),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (run_id, page_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_transcription_rescue_resolutions_run
      ON transcription_rescue_resolutions(run_id, page_id, updated_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS transcript_variant_layers (
      id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL REFERENCES transcription_runs(id) ON DELETE CASCADE,
      page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
      variant_kind TEXT NOT NULL CHECK (
        variant_kind IN ('NORMALISED')
      ),
      base_transcript_version_id TEXT REFERENCES transcript_versions(id) ON DELETE SET NULL,
      base_version_set_sha256 TEXT,
      base_projection_sha256 TEXT NOT NULL,
      variant_text_key TEXT NOT NULL,
      variant_text_sha256 TEXT NOT NULL,
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_transcript_variant_layers_scope
      ON transcript_variant_layers(run_id, page_id, variant_kind, created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS transcript_variant_suggestions (
      id TEXT PRIMARY KEY,
      variant_layer_id TEXT NOT NULL REFERENCES transcript_variant_layers(id) ON DELETE CASCADE,
      line_id TEXT,
      suggestion_text TEXT NOT NULL,
      confidence DOUBLE PRECISION CHECK (
        confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
      ),
      status TEXT NOT NULL CHECK (
        status IN ('PENDING', 'ACCEPTED', 'REJECTED')
      ),
      decided_by TEXT REFERENCES users(id),
      decided_at TIMESTAMPTZ,
      decision_reason TEXT,
      metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_transcript_variant_suggestions_layer
      ON transcript_variant_suggestions(variant_layer_id, status, created_at ASC)
    """,
    """
    CREATE TABLE IF NOT EXISTS transcript_variant_suggestion_events (
      id TEXT PRIMARY KEY,
      suggestion_id TEXT NOT NULL REFERENCES transcript_variant_suggestions(id) ON DELETE CASCADE,
      variant_layer_id TEXT NOT NULL REFERENCES transcript_variant_layers(id) ON DELETE CASCADE,
      actor_user_id TEXT NOT NULL REFERENCES users(id),
      decision TEXT NOT NULL CHECK (
        decision IN ('ACCEPT', 'REJECT')
      ),
      from_status TEXT NOT NULL CHECK (
        from_status IN ('PENDING', 'ACCEPTED', 'REJECTED')
      ),
      to_status TEXT NOT NULL CHECK (
        to_status IN ('PENDING', 'ACCEPTED', 'REJECTED')
      ),
      reason TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_transcript_variant_suggestion_events_target
      ON transcript_variant_suggestion_events(
        suggestion_id,
        created_at DESC
      )
    """,
    """
    CREATE TABLE IF NOT EXISTS transcription_compare_decisions (
      id TEXT PRIMARY KEY,
      document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      base_run_id TEXT NOT NULL REFERENCES transcription_runs(id) ON DELETE CASCADE,
      candidate_run_id TEXT NOT NULL REFERENCES transcription_runs(id) ON DELETE CASCADE,
      page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
      line_id TEXT,
      token_id TEXT,
      decision TEXT NOT NULL CHECK (
        decision IN ('KEEP_BASE', 'PROMOTE_CANDIDATE')
      ),
      decision_etag TEXT NOT NULL,
      decided_by TEXT NOT NULL REFERENCES users(id),
      decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      decision_reason TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_transcription_compare_decisions_target
      ON transcription_compare_decisions(
        document_id,
        base_run_id,
        candidate_run_id,
        page_id,
        COALESCE(line_id, ''),
        COALESCE(token_id, '')
      )
    """,
    """
    CREATE TABLE IF NOT EXISTS transcription_compare_decision_events (
      id TEXT PRIMARY KEY,
      decision_id TEXT REFERENCES transcription_compare_decisions(id) ON DELETE SET NULL,
      document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      base_run_id TEXT NOT NULL REFERENCES transcription_runs(id) ON DELETE CASCADE,
      candidate_run_id TEXT NOT NULL REFERENCES transcription_runs(id) ON DELETE CASCADE,
      page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
      line_id TEXT,
      token_id TEXT,
      from_decision TEXT CHECK (
        from_decision IS NULL OR from_decision IN ('KEEP_BASE', 'PROMOTE_CANDIDATE')
      ),
      to_decision TEXT NOT NULL CHECK (
        to_decision IN ('KEEP_BASE', 'PROMOTE_CANDIDATE')
      ),
      actor_user_id TEXT NOT NULL REFERENCES users(id),
      reason TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_transcription_compare_decision_events_target
      ON transcription_compare_decision_events(
        document_id,
        base_run_id,
        candidate_run_id,
        page_id,
        created_at DESC
      )
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


class DocumentRedactionRunConflictError(RuntimeError):
    """Redaction-run mutation conflicted with lineage or state constraints."""


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
    def _assert_redaction_run_kind(value: str) -> RedactionRunKind:
        if value not in {"BASELINE", "POLICY_RERUN"}:
            raise DocumentStoreUnavailableError("Unexpected redaction run kind persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_redaction_run_status(value: str) -> RedactionRunStatus:
        if value not in {"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"}:
            raise DocumentStoreUnavailableError("Unexpected redaction run status persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_redaction_finding_span_basis_kind(
        value: str,
    ) -> RedactionFindingSpanBasisKind:
        if value not in {"LINE_TEXT", "PAGE_WINDOW_TEXT", "NONE"}:
            raise DocumentStoreUnavailableError(
                "Unexpected redaction finding span basis kind persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_redaction_finding_basis_primary(
        value: str,
    ) -> RedactionFindingBasisPrimary:
        if value not in {"RULE", "NER", "HEURISTIC"}:
            raise DocumentStoreUnavailableError(
                "Unexpected redaction finding basis primary persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_redaction_decision_status(value: str) -> RedactionDecisionStatus:
        if value not in {
            "AUTO_APPLIED",
            "NEEDS_REVIEW",
            "APPROVED",
            "OVERRIDDEN",
            "FALSE_POSITIVE",
        }:
            raise DocumentStoreUnavailableError(
                "Unexpected redaction decision status persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_redaction_override_risk_classification(
        value: str,
    ) -> RedactionOverrideRiskClassification:
        if value not in {"STANDARD", "HIGH"}:
            raise DocumentStoreUnavailableError(
                "Unexpected redaction override risk classification persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_redaction_decision_action_type(
        value: str,
    ) -> RedactionDecisionActionType:
        if value not in {"MASK", "PSEUDONYMIZE", "GENERALIZE"}:
            raise DocumentStoreUnavailableError(
                "Unexpected redaction decision action type persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_redaction_page_review_status(value: str) -> RedactionPageReviewStatus:
        if value not in {"NOT_STARTED", "IN_REVIEW", "APPROVED", "CHANGES_REQUESTED"}:
            raise DocumentStoreUnavailableError(
                "Unexpected redaction page-review status persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_redaction_second_review_status(
        value: str,
    ) -> RedactionSecondReviewStatus:
        if value not in {"NOT_REQUIRED", "PENDING", "APPROVED", "CHANGES_REQUESTED"}:
            raise DocumentStoreUnavailableError(
                "Unexpected redaction second-review status persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_redaction_page_review_event_type(
        value: str,
    ) -> RedactionPageReviewEventType:
        if value not in {
            "PAGE_OPENED",
            "PAGE_REVIEW_STARTED",
            "PAGE_APPROVED",
            "CHANGES_REQUESTED",
            "SECOND_REVIEW_REQUIRED",
            "SECOND_REVIEW_APPROVED",
            "SECOND_REVIEW_CHANGES_REQUESTED",
        }:
            raise DocumentStoreUnavailableError(
                "Unexpected redaction page-review event type persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_redaction_run_review_status(value: str) -> RedactionRunReviewStatus:
        if value not in {"NOT_READY", "IN_REVIEW", "APPROVED", "CHANGES_REQUESTED"}:
            raise DocumentStoreUnavailableError(
                "Unexpected redaction run-review status persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_redaction_run_review_event_type(
        value: str,
    ) -> RedactionRunReviewEventType:
        if value not in {"RUN_REVIEW_OPENED", "RUN_APPROVED", "RUN_CHANGES_REQUESTED"}:
            raise DocumentStoreUnavailableError(
                "Unexpected redaction run-review event type persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_redaction_output_status(value: str) -> RedactionOutputStatus:
        if value not in {"PENDING", "READY", "FAILED", "CANCELED"}:
            raise DocumentStoreUnavailableError(
                "Unexpected redaction output status persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_redaction_run_output_event_type(
        value: str,
    ) -> RedactionRunOutputEventType:
        if value not in {
            "RUN_OUTPUT_GENERATION_STARTED",
            "RUN_OUTPUT_GENERATION_SUCCEEDED",
            "RUN_OUTPUT_GENERATION_FAILED",
            "RUN_OUTPUT_GENERATION_CANCELED",
        }:
            raise DocumentStoreUnavailableError(
                "Unexpected redaction run-output event type persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _redaction_truthy(value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "y"}
        return False

    @classmethod
    def _extract_redaction_dual_review_categories(
        cls,
        policy_snapshot_json: object,
    ) -> set[str]:
        categories: set[str] = set()
        queue: list[object] = [policy_snapshot_json]
        while queue:
            value = queue.pop(0)
            if isinstance(value, list):
                queue.extend(value)
                continue
            if not isinstance(value, Mapping):
                continue
            for raw_key, nested in value.items():
                if not isinstance(raw_key, str):
                    queue.append(nested)
                    continue
                normalized_key = raw_key.strip().lower()
                dual_key = (
                    "dual" in normalized_key
                    or "second_review" in normalized_key
                    or "secondreview" in normalized_key
                )
                if dual_key and isinstance(nested, list):
                    for item in nested:
                        if isinstance(item, str) and item.strip():
                            categories.add(item.strip().upper())
                    continue
                if dual_key and isinstance(nested, Mapping):
                    for category, required in nested.items():
                        if not isinstance(category, str) or not category.strip():
                            continue
                        if cls._redaction_truthy(required):
                            categories.add(category.strip().upper())
                    continue
                queue.append(nested)
        return categories

    @classmethod
    def _redaction_has_disagreement_markers(
        cls,
        basis_secondary_json: object,
    ) -> bool:
        if not isinstance(basis_secondary_json, Mapping):
            return False
        queue: list[object] = [basis_secondary_json]
        while queue:
            value = queue.pop(0)
            if isinstance(value, list):
                queue.extend(value)
                continue
            if not isinstance(value, Mapping):
                continue
            for raw_key, nested in value.items():
                key = raw_key.strip().lower() if isinstance(raw_key, str) else ""
                if key and (
                    "detector_disagreement" in key
                    or "detectordisagreement" in key
                    or "ambiguous_overlap" in key
                    or "ambiguousoverlap" in key
                    or "overlap_ambiguous" in key
                    or "disagreement" in key
                    or "ambiguous" in key
                ):
                    if cls._redaction_truthy(nested):
                        return True
                queue.append(nested)
        return False

    @classmethod
    def _derive_redaction_override_risk(
        cls,
        *,
        to_decision_status: RedactionDecisionStatus,
        category: str,
        area_mask_id: str | None,
        basis_secondary_json: object,
        policy_snapshot_json: object,
    ) -> tuple[RedactionOverrideRiskClassification | None, list[str] | None]:
        if to_decision_status not in {"OVERRIDDEN", "FALSE_POSITIVE"}:
            return None, None
        reason_codes: list[str] = []
        if to_decision_status == "FALSE_POSITIVE":
            reason_codes.append("FALSE_POSITIVE_OVERRIDE")
        if isinstance(area_mask_id, str) and area_mask_id.strip():
            reason_codes.append("AREA_MASK_OVERRIDE")
        category_key = category.strip().upper()
        if category_key and category_key in cls._extract_redaction_dual_review_categories(
            policy_snapshot_json
        ):
            reason_codes.append("POLICY_DUAL_REVIEW_CATEGORY")
        if cls._redaction_has_disagreement_markers(basis_secondary_json):
            reason_codes.append("DETECTOR_DISAGREEMENT_OR_AMBIGUOUS_OVERLAP")
        if reason_codes:
            return "HIGH", reason_codes
        return "STANDARD", None

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
    def _assert_transcription_confidence_band(
        value: str,
    ) -> TranscriptionConfidenceBand:
        if value not in {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}:
            raise DocumentStoreUnavailableError(
                "Unexpected transcription confidence band persisted."
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
    def _assert_transcription_rescue_resolution_status(
        value: str,
    ) -> TranscriptionRescueResolutionStatus:
        if value not in {"RESCUE_VERIFIED", "MANUAL_REVIEW_RESOLVED"}:
            raise DocumentStoreUnavailableError(
                "Unexpected transcription rescue-resolution status persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_transcript_variant_kind(value: str) -> TranscriptVariantKind:
        if value not in {"NORMALISED"}:
            raise DocumentStoreUnavailableError(
                "Unexpected transcript variant kind persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_transcript_variant_suggestion_status(
        value: str,
    ) -> TranscriptVariantSuggestionStatus:
        if value not in {"PENDING", "ACCEPTED", "REJECTED"}:
            raise DocumentStoreUnavailableError(
                "Unexpected transcript variant suggestion status persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_transcript_variant_suggestion_decision(
        value: str,
    ) -> TranscriptVariantSuggestionDecision:
        if value not in {"ACCEPT", "REJECT"}:
            raise DocumentStoreUnavailableError(
                "Unexpected transcript variant suggestion decision persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _is_safe_transcription_source_ref_id(value: str) -> bool:
        candidate = value.strip()
        if candidate == "":
            return False
        lowered = candidate.lower()
        if lowered.startswith("controlled/") or lowered.startswith("file://"):
            return False
        if "/" in candidate or "\\" in candidate:
            return False
        if any(suffix in lowered for suffix in (".png", ".json", ".xml", ".hocr")):
            return False
        return True

    @staticmethod
    def _is_valid_token_bbox(
        bbox_json: dict[str, object] | None,
        *,
        page_width: float,
        page_height: float,
    ) -> bool:
        if not isinstance(bbox_json, dict):
            return False
        raw_x = bbox_json.get("x")
        raw_y = bbox_json.get("y")
        raw_width = bbox_json.get("width")
        raw_height = bbox_json.get("height")
        if not all(
            isinstance(value, (int, float))
            for value in (raw_x, raw_y, raw_width, raw_height)
        ):
            return False
        x = float(raw_x)
        y = float(raw_y)
        width = float(raw_width)
        height = float(raw_height)
        if width <= 0 or height <= 0:
            return False
        if x < 0 or y < 0:
            return False
        if x + width > page_width or y + height > page_height:
            return False
        return True

    @staticmethod
    def _is_valid_token_polygon(
        polygon_json: dict[str, object] | None,
        *,
        page_width: float,
        page_height: float,
    ) -> bool:
        if not isinstance(polygon_json, dict):
            return False
        points = polygon_json.get("points")
        if not isinstance(points, list) or len(points) < 3:
            return False
        for raw_point in points:
            if not isinstance(raw_point, dict):
                return False
            raw_x = raw_point.get("x")
            raw_y = raw_point.get("y")
            if not isinstance(raw_x, (int, float)) or not isinstance(raw_y, (int, float)):
                return False
            x = float(raw_x)
            y = float(raw_y)
            if x < 0 or y < 0:
                return False
            if x > page_width or y > page_height:
                return False
        return True

    @staticmethod
    def _assert_transcription_compare_decision(
        value: str,
    ) -> TranscriptionCompareDecision:
        if value not in {"KEEP_BASE", "PROMOTE_CANDIDATE"}:
            raise DocumentStoreUnavailableError(
                "Unexpected transcription compare decision persisted."
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
    def _as_redaction_run_record(
        cls,
        row: dict[str, object],
    ) -> RedactionRunRecord:
        return RedactionRunRecord(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            document_id=str(row["document_id"]),
            input_transcription_run_id=str(row["input_transcription_run_id"]),
            input_layout_run_id=(
                str(row["input_layout_run_id"])
                if isinstance(row.get("input_layout_run_id"), str)
                else None
            ),
            run_kind=cls._assert_redaction_run_kind(str(row["run_kind"])),
            supersedes_redaction_run_id=(
                str(row["supersedes_redaction_run_id"])
                if isinstance(row.get("supersedes_redaction_run_id"), str)
                else None
            ),
            superseded_by_redaction_run_id=(
                str(row["superseded_by_redaction_run_id"])
                if isinstance(row.get("superseded_by_redaction_run_id"), str)
                else None
            ),
            policy_snapshot_id=str(row["policy_snapshot_id"]),
            policy_snapshot_json=(
                dict(row["policy_snapshot_json"])
                if isinstance(row.get("policy_snapshot_json"), dict)
                else {}
            ),
            policy_snapshot_hash=str(row["policy_snapshot_hash"]),
            policy_id=str(row["policy_id"]) if isinstance(row.get("policy_id"), str) else None,
            policy_family_id=(
                str(row["policy_family_id"])
                if isinstance(row.get("policy_family_id"), str)
                else None
            ),
            policy_version=(
                str(row["policy_version"]) if isinstance(row.get("policy_version"), str) else None
            ),
            detectors_version=str(row["detectors_version"]),
            status=cls._assert_redaction_run_status(str(row["status"])),
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

    @classmethod
    def _as_redaction_finding_record(
        cls,
        row: dict[str, object],
    ) -> RedactionFindingRecord:
        return RedactionFindingRecord(
            id=str(row["id"]),
            run_id=str(row["run_id"]),
            page_id=str(row["page_id"]),
            line_id=str(row["line_id"]) if isinstance(row.get("line_id"), str) else None,
            category=str(row["category"]),
            span_start=(
                int(row["span_start"]) if isinstance(row.get("span_start"), int) else None
            ),
            span_end=int(row["span_end"]) if isinstance(row.get("span_end"), int) else None,
            span_basis_kind=cls._assert_redaction_finding_span_basis_kind(
                str(row["span_basis_kind"])
            ),
            span_basis_ref=(
                str(row["span_basis_ref"])
                if isinstance(row.get("span_basis_ref"), str)
                else None
            ),
            confidence=(
                float(row["confidence"])
                if isinstance(row.get("confidence"), (int, float))
                else None
            ),
            basis_primary=cls._assert_redaction_finding_basis_primary(str(row["basis_primary"])),
            basis_secondary_json=(
                dict(row["basis_secondary_json"])
                if isinstance(row.get("basis_secondary_json"), dict)
                else None
            ),
            assist_explanation_key=(
                str(row["assist_explanation_key"])
                if isinstance(row.get("assist_explanation_key"), str)
                else None
            ),
            assist_explanation_sha256=(
                str(row["assist_explanation_sha256"])
                if isinstance(row.get("assist_explanation_sha256"), str)
                else None
            ),
            bbox_refs=dict(row["bbox_refs"]) if isinstance(row.get("bbox_refs"), dict) else {},
            token_refs_json=(
                [
                    dict(item)
                    for item in row["token_refs_json"]
                    if isinstance(item, dict)
                ]
                if isinstance(row.get("token_refs_json"), list)
                else None
            ),
            area_mask_id=(
                str(row["area_mask_id"]) if isinstance(row.get("area_mask_id"), str) else None
            ),
            decision_status=cls._assert_redaction_decision_status(str(row["decision_status"])),
            override_risk_classification=(
                cls._assert_redaction_override_risk_classification(
                    str(row["override_risk_classification"])
                )
                if isinstance(row.get("override_risk_classification"), str)
                else None
            ),
            override_risk_reason_codes_json=(
                [str(item) for item in row["override_risk_reason_codes_json"]]
                if isinstance(row.get("override_risk_reason_codes_json"), list)
                else None
            ),
            decision_by=(
                str(row["decision_by"]) if isinstance(row.get("decision_by"), str) else None
            ),
            decision_at=row.get("decision_at"),  # type: ignore[arg-type]
            decision_reason=(
                str(row["decision_reason"])
                if isinstance(row.get("decision_reason"), str)
                else None
            ),
            decision_etag=str(row["decision_etag"]),
            updated_at=row["updated_at"],  # type: ignore[arg-type]
            created_at=row["created_at"],  # type: ignore[arg-type]
            action_type=cls._assert_redaction_decision_action_type(
                str(row.get("action_type") or "MASK")
            ),
        )

    @classmethod
    def _as_redaction_area_mask_record(
        cls,
        row: dict[str, object],
    ) -> RedactionAreaMaskRecord:
        return RedactionAreaMaskRecord(
            id=str(row["id"]),
            run_id=str(row["run_id"]),
            page_id=str(row["page_id"]),
            geometry_json=(
                dict(row["geometry_json"])
                if isinstance(row.get("geometry_json"), dict)
                else {}
            ),
            mask_reason=str(row.get("mask_reason") or ""),
            version_etag=str(row["version_etag"]),
            supersedes_area_mask_id=(
                str(row["supersedes_area_mask_id"])
                if isinstance(row.get("supersedes_area_mask_id"), str)
                else None
            ),
            superseded_by_area_mask_id=(
                str(row["superseded_by_area_mask_id"])
                if isinstance(row.get("superseded_by_area_mask_id"), str)
                else None
            ),
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_redaction_decision_event_record(
        cls,
        row: dict[str, object],
    ) -> RedactionDecisionEventRecord:
        return RedactionDecisionEventRecord(
            id=str(row["id"]),
            run_id=str(row["run_id"]),
            page_id=str(row["page_id"]),
            finding_id=str(row["finding_id"]),
            from_decision_status=(
                cls._assert_redaction_decision_status(str(row["from_decision_status"]))
                if isinstance(row.get("from_decision_status"), str)
                else None
            ),
            to_decision_status=cls._assert_redaction_decision_status(
                str(row["to_decision_status"])
            ),
            action_type=cls._assert_redaction_decision_action_type(str(row["action_type"])),
            area_mask_id=(
                str(row["area_mask_id"]) if isinstance(row.get("area_mask_id"), str) else None
            ),
            actor_user_id=str(row["actor_user_id"]),
            reason=str(row["reason"]) if isinstance(row.get("reason"), str) else None,
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_redaction_page_review_record(
        cls,
        row: dict[str, object],
    ) -> RedactionPageReviewRecord:
        return RedactionPageReviewRecord(
            run_id=str(row["run_id"]),
            page_id=str(row["page_id"]),
            review_status=cls._assert_redaction_page_review_status(str(row["review_status"])),
            review_etag=str(row["review_etag"]),
            first_reviewed_by=(
                str(row["first_reviewed_by"])
                if isinstance(row.get("first_reviewed_by"), str)
                else None
            ),
            first_reviewed_at=row.get("first_reviewed_at"),  # type: ignore[arg-type]
            requires_second_review=bool(row.get("requires_second_review", False)),
            second_review_status=cls._assert_redaction_second_review_status(
                str(row.get("second_review_status") or "NOT_REQUIRED")
            ),
            second_reviewed_by=(
                str(row["second_reviewed_by"])
                if isinstance(row.get("second_reviewed_by"), str)
                else None
            ),
            second_reviewed_at=row.get("second_reviewed_at"),  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_redaction_page_review_event_record(
        cls,
        row: dict[str, object],
    ) -> RedactionPageReviewEventRecord:
        return RedactionPageReviewEventRecord(
            id=str(row["id"]),
            run_id=str(row["run_id"]),
            page_id=str(row["page_id"]),
            event_type=cls._assert_redaction_page_review_event_type(str(row["event_type"])),
            actor_user_id=str(row["actor_user_id"]),
            reason=str(row["reason"]) if isinstance(row.get("reason"), str) else None,
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_redaction_run_review_record(
        cls,
        row: dict[str, object],
    ) -> RedactionRunReviewRecord:
        return RedactionRunReviewRecord(
            run_id=str(row["run_id"]),
            review_status=cls._assert_redaction_run_review_status(str(row["review_status"])),
            review_started_by=(
                str(row["review_started_by"])
                if isinstance(row.get("review_started_by"), str)
                else None
            ),
            review_started_at=row.get("review_started_at"),  # type: ignore[arg-type]
            approved_by=(
                str(row["approved_by"]) if isinstance(row.get("approved_by"), str) else None
            ),
            approved_at=row.get("approved_at"),  # type: ignore[arg-type]
            approved_snapshot_key=(
                str(row["approved_snapshot_key"])
                if isinstance(row.get("approved_snapshot_key"), str)
                else None
            ),
            approved_snapshot_sha256=(
                str(row["approved_snapshot_sha256"])
                if isinstance(row.get("approved_snapshot_sha256"), str)
                else None
            ),
            locked_at=row.get("locked_at"),  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_redaction_run_review_event_record(
        cls,
        row: dict[str, object],
    ) -> RedactionRunReviewEventRecord:
        return RedactionRunReviewEventRecord(
            id=str(row["id"]),
            run_id=str(row["run_id"]),
            event_type=cls._assert_redaction_run_review_event_type(str(row["event_type"])),
            actor_user_id=str(row["actor_user_id"]),
            reason=str(row["reason"]) if isinstance(row.get("reason"), str) else None,
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_redaction_projection_record(
        cls,
        row: dict[str, object],
    ) -> DocumentRedactionProjectionRecord:
        return DocumentRedactionProjectionRecord(
            document_id=str(row["document_id"]),
            project_id=str(row["project_id"]),
            active_redaction_run_id=(
                str(row["active_redaction_run_id"])
                if isinstance(row.get("active_redaction_run_id"), str)
                else None
            ),
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
            active_policy_snapshot_id=(
                str(row["active_policy_snapshot_id"])
                if isinstance(row.get("active_policy_snapshot_id"), str)
                else None
            ),
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_redaction_output_record(
        cls,
        row: dict[str, object],
    ) -> RedactionOutputRecord:
        return RedactionOutputRecord(
            run_id=str(row["run_id"]),
            page_id=str(row["page_id"]),
            status=cls._assert_redaction_output_status(str(row["status"])),
            safeguarded_preview_key=(
                str(row["safeguarded_preview_key"])
                if isinstance(row.get("safeguarded_preview_key"), str)
                else None
            ),
            preview_sha256=(
                str(row["preview_sha256"])
                if isinstance(row.get("preview_sha256"), str)
                else None
            ),
            started_at=row.get("started_at"),  # type: ignore[arg-type]
            generated_at=row.get("generated_at"),  # type: ignore[arg-type]
            canceled_by=(
                str(row["canceled_by"]) if isinstance(row.get("canceled_by"), str) else None
            ),
            canceled_at=row.get("canceled_at"),  # type: ignore[arg-type]
            failure_reason=(
                str(row["failure_reason"])
                if isinstance(row.get("failure_reason"), str)
                else None
            ),
            created_at=row["created_at"],  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_redaction_run_output_record(
        cls,
        row: dict[str, object],
    ) -> RedactionRunOutputRecord:
        return RedactionRunOutputRecord(
            run_id=str(row["run_id"]),
            status=cls._assert_redaction_output_status(str(row["status"])),
            output_manifest_key=(
                str(row["output_manifest_key"])
                if isinstance(row.get("output_manifest_key"), str)
                else None
            ),
            output_manifest_sha256=(
                str(row["output_manifest_sha256"])
                if isinstance(row.get("output_manifest_sha256"), str)
                else None
            ),
            page_count=int(row.get("page_count") or 0),
            started_at=row.get("started_at"),  # type: ignore[arg-type]
            generated_at=row.get("generated_at"),  # type: ignore[arg-type]
            canceled_by=(
                str(row["canceled_by"]) if isinstance(row.get("canceled_by"), str) else None
            ),
            canceled_at=row.get("canceled_at"),  # type: ignore[arg-type]
            failure_reason=(
                str(row["failure_reason"])
                if isinstance(row.get("failure_reason"), str)
                else None
            ),
            created_at=row["created_at"],  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_redaction_run_output_event_record(
        cls,
        row: dict[str, object],
    ) -> RedactionRunOutputEventRecord:
        return RedactionRunOutputEventRecord(
            id=str(row["id"]),
            run_id=str(row["run_id"]),
            event_type=cls._assert_redaction_run_output_event_type(str(row["event_type"])),
            from_status=(
                cls._assert_redaction_output_status(str(row["from_status"]))
                if isinstance(row.get("from_status"), str)
                else None
            ),
            to_status=cls._assert_redaction_output_status(str(row["to_status"])),
            reason=str(row["reason"]) if isinstance(row.get("reason"), str) else None,
            actor_user_id=(
                str(row["actor_user_id"])
                if isinstance(row.get("actor_user_id"), str)
                else None
            ),
            created_at=row["created_at"],  # type: ignore[arg-type]
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
            reviewer_assignment_user_id=(
                str(row["reviewer_assignment_user_id"])
                if isinstance(row.get("reviewer_assignment_user_id"), str)
                else None
            ),
            reviewer_assignment_updated_by=(
                str(row["reviewer_assignment_updated_by"])
                if isinstance(row.get("reviewer_assignment_updated_by"), str)
                else None
            ),
            reviewer_assignment_updated_at=(
                row["reviewer_assignment_updated_at"]  # type: ignore[assignment]
                if isinstance(row.get("reviewer_assignment_updated_at"), datetime)
                else None
            ),
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
            confidence_band=cls._assert_transcription_confidence_band(
                str(row.get("confidence_band") or "UNKNOWN")
            ),
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
    def _as_transcription_rescue_resolution_record(
        cls,
        row: dict[str, object],
    ) -> TranscriptionRescueResolutionRecord:
        return TranscriptionRescueResolutionRecord(
            run_id=str(row["run_id"]),
            page_id=str(row["page_id"]),
            resolution_status=cls._assert_transcription_rescue_resolution_status(
                str(row["resolution_status"])
            ),
            resolution_reason=(
                str(row["resolution_reason"])
                if isinstance(row.get("resolution_reason"), str)
                else None
            ),
            updated_by=str(row["updated_by"]),
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

    @classmethod
    def _as_transcript_variant_layer_record(
        cls,
        row: dict[str, object],
    ) -> TranscriptVariantLayerRecord:
        return TranscriptVariantLayerRecord(
            id=str(row["id"]),
            run_id=str(row["run_id"]),
            page_id=str(row["page_id"]),
            variant_kind=cls._assert_transcript_variant_kind(str(row["variant_kind"])),
            base_transcript_version_id=(
                str(row["base_transcript_version_id"])
                if isinstance(row.get("base_transcript_version_id"), str)
                else None
            ),
            base_version_set_sha256=(
                str(row["base_version_set_sha256"])
                if isinstance(row.get("base_version_set_sha256"), str)
                else None
            ),
            base_projection_sha256=str(row["base_projection_sha256"]),
            variant_text_key=str(row["variant_text_key"]),
            variant_text_sha256=str(row["variant_text_sha256"]),
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_transcript_variant_suggestion_record(
        cls,
        row: dict[str, object],
    ) -> TranscriptVariantSuggestionRecord:
        return TranscriptVariantSuggestionRecord(
            id=str(row["id"]),
            variant_layer_id=str(row["variant_layer_id"]),
            line_id=str(row["line_id"]) if isinstance(row.get("line_id"), str) else None,
            suggestion_text=str(row["suggestion_text"]),
            confidence=(
                float(row["confidence"])
                if isinstance(row.get("confidence"), (int, float))
                else None
            ),
            status=cls._assert_transcript_variant_suggestion_status(str(row["status"])),
            decided_by=(
                str(row["decided_by"]) if isinstance(row.get("decided_by"), str) else None
            ),
            decided_at=row.get("decided_at"),  # type: ignore[arg-type]
            decision_reason=(
                str(row["decision_reason"])
                if isinstance(row.get("decision_reason"), str)
                else None
            ),
            metadata_json=(
                dict(row["metadata_json"])
                if isinstance(row.get("metadata_json"), dict)
                else {}
            ),
            created_at=row["created_at"],  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_transcript_variant_suggestion_event_record(
        cls,
        row: dict[str, object],
    ) -> TranscriptVariantSuggestionEventRecord:
        return TranscriptVariantSuggestionEventRecord(
            id=str(row["id"]),
            suggestion_id=str(row["suggestion_id"]),
            variant_layer_id=str(row["variant_layer_id"]),
            actor_user_id=str(row["actor_user_id"]),
            decision=cls._assert_transcript_variant_suggestion_decision(
                str(row["decision"])
            ),
            from_status=cls._assert_transcript_variant_suggestion_status(
                str(row["from_status"])
            ),
            to_status=cls._assert_transcript_variant_suggestion_status(
                str(row["to_status"])
            ),
            reason=str(row["reason"]) if isinstance(row.get("reason"), str) else None,
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_transcription_compare_decision_record(
        cls,
        row: dict[str, object],
    ) -> TranscriptionCompareDecisionRecord:
        return TranscriptionCompareDecisionRecord(
            id=str(row["id"]),
            document_id=str(row["document_id"]),
            base_run_id=str(row["base_run_id"]),
            candidate_run_id=str(row["candidate_run_id"]),
            page_id=str(row["page_id"]),
            line_id=str(row["line_id"]) if isinstance(row.get("line_id"), str) else None,
            token_id=str(row["token_id"]) if isinstance(row.get("token_id"), str) else None,
            decision=cls._assert_transcription_compare_decision(str(row["decision"])),
            decision_etag=str(row["decision_etag"]),
            decided_by=str(row["decided_by"]),
            decided_at=row["decided_at"],  # type: ignore[arg-type]
            decision_reason=(
                str(row["decision_reason"])
                if isinstance(row.get("decision_reason"), str)
                else None
            ),
            created_at=row["created_at"],  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_transcription_compare_decision_event_record(
        cls,
        row: dict[str, object],
    ) -> TranscriptionCompareDecisionEventRecord:
        return TranscriptionCompareDecisionEventRecord(
            id=str(row["id"]),
            decision_id=(
                str(row["decision_id"])
                if isinstance(row.get("decision_id"), str)
                else None
            ),
            document_id=str(row["document_id"]),
            base_run_id=str(row["base_run_id"]),
            candidate_run_id=str(row["candidate_run_id"]),
            page_id=str(row["page_id"]),
            line_id=str(row["line_id"]) if isinstance(row.get("line_id"), str) else None,
            token_id=str(row["token_id"]) if isinstance(row.get("token_id"), str) else None,
            from_decision=(
                cls._assert_transcription_compare_decision(str(row["from_decision"]))
                if isinstance(row.get("from_decision"), str)
                else None
            ),
            to_decision=cls._assert_transcription_compare_decision(str(row["to_decision"])),
            actor_user_id=str(row["actor_user_id"]),
            reason=str(row["reason"]) if isinstance(row.get("reason"), str) else None,
            created_at=row["created_at"],  # type: ignore[arg-type]
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
                          ptr.reviewer_assignment_user_id,
                          ptr.reviewer_assignment_updated_by,
                          ptr.reviewer_assignment_updated_at,
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
                          ptr.reviewer_assignment_user_id,
                          ptr.reviewer_assignment_updated_by,
                          ptr.reviewer_assignment_updated_at,
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

    def update_page_transcription_assignment(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        reviewer_user_id: str | None,
        updated_by: str,
    ) -> PageTranscriptionResultRecord:
        self.ensure_schema()
        safe_updated_by = updated_by.strip()
        if not safe_updated_by:
            raise DocumentStoreUnavailableError(
                "Transcription page assignment update requires updated_by."
            )
        safe_reviewer_user_id = (
            reviewer_user_id.strip()
            if isinstance(reviewer_user_id, str) and reviewer_user_id.strip()
            else None
        )
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE page_transcription_results AS ptr
                        SET
                          reviewer_assignment_user_id = %(reviewer_user_id)s,
                          reviewer_assignment_updated_by = %(updated_by)s,
                          reviewer_assignment_updated_at = NOW(),
                          updated_at = NOW()
                        FROM transcription_runs AS tr
                        WHERE ptr.run_id = %(run_id)s
                          AND ptr.page_id = %(page_id)s
                          AND tr.id = ptr.run_id
                          AND tr.project_id = %(project_id)s
                          AND tr.document_id = %(document_id)s
                        RETURNING
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
                          ptr.reviewer_assignment_user_id,
                          ptr.reviewer_assignment_updated_by,
                          ptr.reviewer_assignment_updated_at,
                          ptr.created_at,
                          ptr.updated_at
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                            "page_id": page_id,
                            "reviewer_user_id": safe_reviewer_user_id,
                            "updated_by": safe_updated_by,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Transcription page assignment update failed."
            ) from error
        if row is None:
            raise DocumentNotFoundError("Transcription page result not found.")
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
                          ltr.confidence_band,
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

    def get_transcription_rescue_resolution(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> TranscriptionRescueResolutionRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          trr.run_id,
                          trr.page_id,
                          trr.resolution_status,
                          trr.resolution_reason,
                          trr.updated_by,
                          trr.updated_at
                        FROM transcription_rescue_resolutions AS trr
                        INNER JOIN transcription_runs AS tr
                          ON tr.id = trr.run_id
                        WHERE trr.run_id = %(run_id)s
                          AND trr.page_id = %(page_id)s
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
                "Transcription rescue-resolution read failed."
            ) from error
        if row is None:
            return None
        return self._as_transcription_rescue_resolution_record(row)

    def list_transcription_rescue_resolutions(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_ids: Sequence[str] | None = None,
    ) -> list[TranscriptionRescueResolutionRecord]:
        self.ensure_schema()
        normalized_page_ids = sorted(
            {
                item.strip()
                for item in (page_ids or ())
                if isinstance(item, str) and item.strip()
            }
        )
        if page_ids is not None and not normalized_page_ids:
            return []
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    if normalized_page_ids:
                        cursor.execute(
                            """
                            SELECT
                              trr.run_id,
                              trr.page_id,
                              trr.resolution_status,
                              trr.resolution_reason,
                              trr.updated_by,
                              trr.updated_at
                            FROM transcription_rescue_resolutions AS trr
                            INNER JOIN transcription_runs AS tr
                              ON tr.id = trr.run_id
                            WHERE trr.run_id = %(run_id)s
                              AND trr.page_id = ANY(%(page_ids)s)
                              AND tr.project_id = %(project_id)s
                              AND tr.document_id = %(document_id)s
                            ORDER BY trr.page_id ASC
                            """,
                            {
                                "run_id": run_id,
                                "page_ids": normalized_page_ids,
                                "project_id": project_id,
                                "document_id": document_id,
                            },
                        )
                    else:
                        cursor.execute(
                            """
                            SELECT
                              trr.run_id,
                              trr.page_id,
                              trr.resolution_status,
                              trr.resolution_reason,
                              trr.updated_by,
                              trr.updated_at
                            FROM transcription_rescue_resolutions AS trr
                            INNER JOIN transcription_runs AS tr
                              ON tr.id = trr.run_id
                            WHERE trr.run_id = %(run_id)s
                              AND tr.project_id = %(project_id)s
                              AND tr.document_id = %(document_id)s
                            ORDER BY trr.page_id ASC
                            """,
                            {
                                "run_id": run_id,
                                "project_id": project_id,
                                "document_id": document_id,
                            },
                        )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Transcription rescue-resolution listing failed."
            ) from error
        return [self._as_transcription_rescue_resolution_record(row) for row in rows]

    def upsert_transcription_rescue_resolution(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        resolution_status: TranscriptionRescueResolutionStatus,
        resolution_reason: str | None,
        updated_by: str,
    ) -> TranscriptionRescueResolutionRecord:
        self.ensure_schema()
        safe_status = self._assert_transcription_rescue_resolution_status(
            str(resolution_status)
        )
        safe_reason = (
            resolution_reason.strip()
            if isinstance(resolution_reason, str) and resolution_reason.strip()
            else None
        )
        if safe_reason is not None and len(safe_reason) > 600:
            raise DocumentStoreUnavailableError(
                "Transcription rescue-resolution reason must be 600 characters or fewer."
            )
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          tr.id,
                          tr.input_layout_run_id
                        FROM transcription_runs AS tr
                        WHERE tr.id = %(run_id)s
                          AND tr.project_id = %(project_id)s
                          AND tr.document_id = %(document_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "run_id": run_id,
                            "project_id": project_id,
                            "document_id": document_id,
                        },
                    )
                    run_row = cursor.fetchone()
                    if run_row is None:
                        raise DocumentNotFoundError("Transcription run not found.")
                    input_layout_run_id = str(run_row["input_layout_run_id"])

                    cursor.execute(
                        """
                        SELECT
                          plr.page_id
                        FROM page_layout_results AS plr
                        WHERE plr.run_id = %(layout_run_id)s
                          AND plr.page_id = %(page_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "layout_run_id": input_layout_run_id,
                            "page_id": page_id,
                        },
                    )
                    page_row = cursor.fetchone()
                    if page_row is None:
                        raise DocumentNotFoundError(
                            "Transcription rescue-resolution page target not found."
                        )

                    cursor.execute(
                        """
                        INSERT INTO transcription_rescue_resolutions (
                          run_id,
                          page_id,
                          resolution_status,
                          resolution_reason,
                          updated_by,
                          updated_at
                        )
                        VALUES (
                          %(run_id)s,
                          %(page_id)s,
                          %(resolution_status)s,
                          %(resolution_reason)s,
                          %(updated_by)s,
                          NOW()
                        )
                        ON CONFLICT (run_id, page_id) DO UPDATE
                        SET
                          resolution_status = EXCLUDED.resolution_status,
                          resolution_reason = EXCLUDED.resolution_reason,
                          updated_by = EXCLUDED.updated_by,
                          updated_at = NOW()
                        RETURNING
                          run_id,
                          page_id,
                          resolution_status,
                          resolution_reason,
                          updated_by,
                          updated_at
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "resolution_status": safe_status,
                            "resolution_reason": safe_reason,
                            "updated_by": updated_by,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except DocumentNotFoundError:
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Transcription rescue-resolution update failed."
            ) from error
        if row is None:
            raise DocumentStoreUnavailableError(
                "Transcription rescue-resolution update failed."
            )
        return self._as_transcription_rescue_resolution_record(row)

    def list_transcript_versions(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        line_id: str,
    ) -> list[TranscriptVersionRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          tv.id,
                          tv.run_id,
                          tv.page_id,
                          tv.line_id,
                          tv.base_version_id,
                          tv.superseded_by_version_id,
                          tv.version_etag,
                          tv.text_diplomatic,
                          tv.editor_user_id,
                          tv.edit_reason,
                          tv.created_at
                        FROM transcript_versions AS tv
                        INNER JOIN transcription_runs AS tr
                          ON tr.id = tv.run_id
                        WHERE tv.run_id = %(run_id)s
                          AND tv.page_id = %(page_id)s
                          AND tv.line_id = %(line_id)s
                          AND tr.project_id = %(project_id)s
                          AND tr.document_id = %(document_id)s
                        ORDER BY tv.created_at DESC, tv.id DESC
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "line_id": line_id,
                            "project_id": project_id,
                            "document_id": document_id,
                        },
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Transcript version listing failed."
            ) from error
        return [self._as_transcript_version_record(row) for row in rows]

    def get_transcript_version(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        line_id: str,
        version_id: str,
    ) -> TranscriptVersionRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          tv.id,
                          tv.run_id,
                          tv.page_id,
                          tv.line_id,
                          tv.base_version_id,
                          tv.superseded_by_version_id,
                          tv.version_etag,
                          tv.text_diplomatic,
                          tv.editor_user_id,
                          tv.edit_reason,
                          tv.created_at
                        FROM transcript_versions AS tv
                        INNER JOIN transcription_runs AS tr
                          ON tr.id = tv.run_id
                        WHERE tv.id = %(version_id)s
                          AND tv.run_id = %(run_id)s
                          AND tv.page_id = %(page_id)s
                          AND tv.line_id = %(line_id)s
                          AND tr.project_id = %(project_id)s
                          AND tr.document_id = %(document_id)s
                        LIMIT 1
                        """,
                        {
                            "version_id": version_id,
                            "run_id": run_id,
                            "page_id": page_id,
                            "line_id": line_id,
                            "project_id": project_id,
                            "document_id": document_id,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Transcript version read failed."
            ) from error
        if row is None:
            return None
        return self._as_transcript_version_record(row)

    def append_transcript_line_version(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        line_id: str,
        text_diplomatic: str,
        editor_user_id: str,
        expected_version_etag: str,
        edit_reason: str | None = None,
    ) -> tuple[TranscriptVersionRecord, LineTranscriptionResultRecord, bool]:
        self.ensure_schema()
        safe_line_id = line_id.strip()
        if not safe_line_id:
            raise DocumentTranscriptionRunConflictError("line_id is required.")
        safe_text = text_diplomatic
        if not isinstance(safe_text, str) or not safe_text.strip():
            raise DocumentTranscriptionRunConflictError(
                "text_diplomatic must contain visible characters."
            )
        safe_expected_etag = (
            expected_version_etag.strip()
            if isinstance(expected_version_etag, str)
            else ""
        )
        if not safe_expected_etag:
            raise DocumentTranscriptionRunConflictError("version_etag is required.")
        safe_reason = (
            edit_reason.strip()
            if isinstance(edit_reason, str) and edit_reason.strip()
            else None
        )
        if safe_reason is not None and len(safe_reason) > 600:
            raise DocumentTranscriptionRunConflictError(
                "edit_reason must be 600 characters or fewer."
            )

        created_version_row: dict[str, object] | None = None
        updated_line_row: dict[str, object] | None = None
        text_changed = False
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "SELECT pg_advisory_xact_lock(hashtext(%(lock_key)s))",
                        {
                            "lock_key": (
                                f"transcript_line_version|{run_id}|{page_id}|{safe_line_id}"
                            )
                        },
                    )
                    cursor.execute(
                        """
                        SELECT
                          ltr.run_id,
                          ltr.page_id,
                          ltr.line_id,
                          ltr.text_diplomatic,
                          ltr.conf_line,
                          ltr.confidence_band,
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
                          ltr.updated_at,
                          tv.text_diplomatic AS active_text_diplomatic
                        FROM line_transcription_results AS ltr
                        INNER JOIN transcription_runs AS tr
                          ON tr.id = ltr.run_id
                        LEFT JOIN transcript_versions AS tv
                          ON tv.id = ltr.active_transcript_version_id
                        WHERE ltr.run_id = %(run_id)s
                          AND ltr.page_id = %(page_id)s
                          AND ltr.line_id = %(line_id)s
                          AND tr.project_id = %(project_id)s
                          AND tr.document_id = %(document_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "line_id": safe_line_id,
                            "project_id": project_id,
                            "document_id": document_id,
                        },
                    )
                    current_line = cursor.fetchone()
                    if current_line is None:
                        raise DocumentNotFoundError("Transcription line result not found.")
                    if safe_expected_etag != str(current_line["version_etag"]):
                        raise DocumentTranscriptionRunConflictError(
                            "version_etag is stale for this transcript line."
                        )

                    current_active_version_id = (
                        str(current_line["active_transcript_version_id"])
                        if isinstance(current_line.get("active_transcript_version_id"), str)
                        and str(current_line["active_transcript_version_id"]).strip()
                        else None
                    )
                    current_active_text = (
                        str(current_line["active_text_diplomatic"])
                        if isinstance(current_line.get("active_text_diplomatic"), str)
                        else str(current_line["text_diplomatic"])
                    )
                    text_changed = current_active_text != safe_text
                    next_token_anchor_status = (
                        "REFRESH_REQUIRED"
                        if text_changed
                        else self._assert_token_anchor_status(
                            str(current_line["token_anchor_status"])
                        )
                    )

                    version_id = str(uuid4())
                    now_seed = datetime.now(timezone.utc).isoformat()
                    version_etag = hashlib.sha256(
                        (
                            f"{run_id}|{page_id}|{safe_line_id}|{version_id}|"
                            f"{safe_text}|{editor_user_id}|{now_seed}"
                        ).encode("utf-8")
                    ).hexdigest()

                    cursor.execute(
                        """
                        INSERT INTO transcript_versions (
                          id,
                          run_id,
                          page_id,
                          line_id,
                          base_version_id,
                          superseded_by_version_id,
                          version_etag,
                          text_diplomatic,
                          editor_user_id,
                          edit_reason,
                          created_at
                        )
                        VALUES (
                          %(id)s,
                          %(run_id)s,
                          %(page_id)s,
                          %(line_id)s,
                          %(base_version_id)s,
                          NULL,
                          %(version_etag)s,
                          %(text_diplomatic)s,
                          %(editor_user_id)s,
                          %(edit_reason)s,
                          NOW()
                        )
                        RETURNING
                          id,
                          run_id,
                          page_id,
                          line_id,
                          base_version_id,
                          superseded_by_version_id,
                          version_etag,
                          text_diplomatic,
                          editor_user_id,
                          edit_reason,
                          created_at
                        """,
                        {
                            "id": version_id,
                            "run_id": run_id,
                            "page_id": page_id,
                            "line_id": safe_line_id,
                            "base_version_id": current_active_version_id,
                            "version_etag": version_etag,
                            "text_diplomatic": safe_text,
                            "editor_user_id": editor_user_id,
                            "edit_reason": safe_reason,
                        },
                    )
                    created_version_row = cursor.fetchone()

                    if current_active_version_id is not None:
                        cursor.execute(
                            """
                            UPDATE transcript_versions
                            SET superseded_by_version_id = %(superseded_by_version_id)s
                            WHERE id = %(id)s
                            """,
                            {
                                "id": current_active_version_id,
                                "superseded_by_version_id": version_id,
                            },
                        )

                    cursor.execute(
                        """
                        UPDATE line_transcription_results
                        SET
                          active_transcript_version_id = %(active_transcript_version_id)s,
                          version_etag = %(version_etag)s,
                          token_anchor_status = %(token_anchor_status)s,
                          updated_at = NOW()
                        WHERE run_id = %(run_id)s
                          AND page_id = %(page_id)s
                          AND line_id = %(line_id)s
                        RETURNING
                          run_id,
                          page_id,
                          line_id,
                          text_diplomatic,
                          conf_line,
                          confidence_basis,
                          confidence_calibration_version,
                          alignment_json_key,
                          char_boxes_key,
                          schema_validation_status,
                          flags_json,
                          machine_output_sha256,
                          active_transcript_version_id,
                          version_etag,
                          token_anchor_status,
                          created_at,
                          updated_at
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "line_id": safe_line_id,
                            "active_transcript_version_id": version_id,
                            "version_etag": version_etag,
                            "token_anchor_status": next_token_anchor_status,
                        },
                    )
                    updated_line_row = cursor.fetchone()
                connection.commit()
        except (DocumentNotFoundError, DocumentTranscriptionRunConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Transcript line-version append failed."
            ) from error

        if created_version_row is None or updated_line_row is None:
            raise DocumentStoreUnavailableError("Transcript line-version append failed.")
        return (
            self._as_transcript_version_record(created_version_row),
            self._as_line_transcription_result_record(updated_line_row),
            text_changed,
        )

    def list_transcription_compare_decisions(
        self,
        *,
        project_id: str,
        document_id: str,
        base_run_id: str,
        candidate_run_id: str,
        page_id: str | None = None,
    ) -> list[TranscriptionCompareDecisionRecord]:
        self.ensure_schema()
        params: dict[str, object] = {
            "project_id": project_id,
            "document_id": document_id,
            "base_run_id": base_run_id,
            "candidate_run_id": candidate_run_id,
        }
        where_clauses = [
            "tcd.document_id = %(document_id)s",
            "tcd.base_run_id = %(base_run_id)s",
            "tcd.candidate_run_id = %(candidate_run_id)s",
            "base_run.project_id = %(project_id)s",
            "base_run.document_id = %(document_id)s",
            "candidate_run.project_id = %(project_id)s",
            "candidate_run.document_id = %(document_id)s",
        ]
        if isinstance(page_id, str) and page_id.strip():
            params["page_id"] = page_id.strip()
            where_clauses.append("tcd.page_id = %(page_id)s")
        where_clause = " AND ".join(where_clauses)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        f"""
                        SELECT
                          tcd.id,
                          tcd.document_id,
                          tcd.base_run_id,
                          tcd.candidate_run_id,
                          tcd.page_id,
                          tcd.line_id,
                          tcd.token_id,
                          tcd.decision,
                          tcd.decision_etag,
                          tcd.decided_by,
                          tcd.decided_at,
                          tcd.decision_reason,
                          tcd.created_at,
                          tcd.updated_at
                        FROM transcription_compare_decisions AS tcd
                        INNER JOIN transcription_runs AS base_run
                          ON base_run.id = tcd.base_run_id
                        INNER JOIN transcription_runs AS candidate_run
                          ON candidate_run.id = tcd.candidate_run_id
                        WHERE {where_clause}
                        ORDER BY tcd.page_id ASC, tcd.line_id ASC NULLS FIRST, tcd.token_id ASC NULLS FIRST
                        """,
                        params,
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Transcription compare decision listing failed."
            ) from error
        return [self._as_transcription_compare_decision_record(row) for row in rows]

    def list_transcription_compare_decision_events(
        self,
        *,
        project_id: str,
        document_id: str,
        base_run_id: str,
        candidate_run_id: str,
        page_ids: Sequence[str] | None = None,
    ) -> list[TranscriptionCompareDecisionEventRecord]:
        self.ensure_schema()
        params: dict[str, object] = {
            "project_id": project_id,
            "document_id": document_id,
            "base_run_id": base_run_id,
            "candidate_run_id": candidate_run_id,
        }
        where_clauses = [
            "tcde.document_id = %(document_id)s",
            "tcde.base_run_id = %(base_run_id)s",
            "tcde.candidate_run_id = %(candidate_run_id)s",
            "base_run.project_id = %(project_id)s",
            "base_run.document_id = %(document_id)s",
            "candidate_run.project_id = %(project_id)s",
            "candidate_run.document_id = %(document_id)s",
        ]
        normalized_page_ids = sorted(
            {
                item.strip()
                for item in (page_ids or ())
                if isinstance(item, str) and item.strip()
            }
        )
        if normalized_page_ids:
            params["page_ids"] = normalized_page_ids
            where_clauses.append("tcde.page_id = ANY(%(page_ids)s)")
        where_clause = " AND ".join(where_clauses)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        f"""
                        SELECT
                          tcde.id,
                          tcde.decision_id,
                          tcde.document_id,
                          tcde.base_run_id,
                          tcde.candidate_run_id,
                          tcde.page_id,
                          tcde.line_id,
                          tcde.token_id,
                          tcde.from_decision,
                          tcde.to_decision,
                          tcde.actor_user_id,
                          tcde.reason,
                          tcde.created_at
                        FROM transcription_compare_decision_events AS tcde
                        INNER JOIN transcription_runs AS base_run
                          ON base_run.id = tcde.base_run_id
                        INNER JOIN transcription_runs AS candidate_run
                          ON candidate_run.id = tcde.candidate_run_id
                        WHERE {where_clause}
                        ORDER BY tcde.created_at ASC, tcde.id ASC
                        """,
                        params,
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Transcription compare decision-event listing failed."
            ) from error
        return [self._as_transcription_compare_decision_event_record(row) for row in rows]

    def record_transcription_compare_decision(
        self,
        *,
        project_id: str,
        document_id: str,
        base_run_id: str,
        candidate_run_id: str,
        page_id: str,
        line_id: str | None,
        token_id: str | None,
        decision: TranscriptionCompareDecision,
        decided_by: str,
        decision_reason: str | None,
        expected_decision_etag: str | None = None,
    ) -> TranscriptionCompareDecisionRecord:
        self.ensure_schema()
        safe_decision = self._assert_transcription_compare_decision(str(decision))
        safe_page_id = page_id.strip()
        if not safe_page_id:
            raise DocumentTranscriptionRunConflictError(
                "Compare decision requires a page_id."
            )
        safe_line_id = line_id.strip() if isinstance(line_id, str) and line_id.strip() else None
        safe_token_id = (
            token_id.strip() if isinstance(token_id, str) and token_id.strip() else None
        )
        safe_reason = (
            decision_reason.strip()
            if isinstance(decision_reason, str) and decision_reason.strip()
            else None
        )
        if safe_reason is not None and len(safe_reason) > 600:
            raise DocumentTranscriptionRunConflictError(
                "Compare decision reason must be 600 characters or fewer."
            )
        safe_expected_etag = (
            expected_decision_etag.strip()
            if isinstance(expected_decision_etag, str) and expected_decision_etag.strip()
            else None
        )
        persisted_row: dict[str, object] | None = None
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "SELECT pg_advisory_xact_lock(hashtext(%(lock_key)s))",
                        {
                            "lock_key": (
                                "transcription_compare_decision|"
                                f"{document_id}|{base_run_id}|{candidate_run_id}|{safe_page_id}|"
                                f"{safe_line_id or '-'}|{safe_token_id or '-'}"
                            )
                        },
                    )
                    cursor.execute(
                        """
                        SELECT
                          base_run.id
                        FROM transcription_runs AS base_run
                        INNER JOIN transcription_runs AS candidate_run
                          ON candidate_run.id = %(candidate_run_id)s
                        WHERE base_run.id = %(base_run_id)s
                          AND base_run.project_id = %(project_id)s
                          AND base_run.document_id = %(document_id)s
                          AND candidate_run.project_id = %(project_id)s
                          AND candidate_run.document_id = %(document_id)s
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "base_run_id": base_run_id,
                            "candidate_run_id": candidate_run_id,
                        },
                    )
                    run_pair = cursor.fetchone()
                    if run_pair is None:
                        raise DocumentTranscriptionRunConflictError(
                            "Compare decision runs were not found in document scope."
                        )

                    cursor.execute(
                        """
                        SELECT 1
                        FROM page_transcription_results AS ptr
                        WHERE ptr.page_id = %(page_id)s
                          AND ptr.run_id IN (%(base_run_id)s, %(candidate_run_id)s)
                        LIMIT 1
                        """,
                        {
                            "page_id": safe_page_id,
                            "base_run_id": base_run_id,
                            "candidate_run_id": candidate_run_id,
                        },
                    )
                    page_exists = cursor.fetchone()
                    if page_exists is None:
                        raise DocumentTranscriptionRunConflictError(
                            "Compare decision page target was not found for compared runs."
                        )

                    cursor.execute(
                        """
                        SELECT
                          tcd.id,
                          tcd.document_id,
                          tcd.base_run_id,
                          tcd.candidate_run_id,
                          tcd.page_id,
                          tcd.line_id,
                          tcd.token_id,
                          tcd.decision,
                          tcd.decision_etag,
                          tcd.decided_by,
                          tcd.decided_at,
                          tcd.decision_reason,
                          tcd.created_at,
                          tcd.updated_at
                        FROM transcription_compare_decisions AS tcd
                        WHERE tcd.document_id = %(document_id)s
                          AND tcd.base_run_id = %(base_run_id)s
                          AND tcd.candidate_run_id = %(candidate_run_id)s
                          AND tcd.page_id = %(page_id)s
                          AND COALESCE(tcd.line_id, '') = COALESCE(%(line_id)s, '')
                          AND COALESCE(tcd.token_id, '') = COALESCE(%(token_id)s, '')
                        LIMIT 1
                        """,
                        {
                            "document_id": document_id,
                            "base_run_id": base_run_id,
                            "candidate_run_id": candidate_run_id,
                            "page_id": safe_page_id,
                            "line_id": safe_line_id,
                            "token_id": safe_token_id,
                        },
                    )
                    current_row = cursor.fetchone()
                    now_seed = datetime.now(timezone.utc).isoformat()
                    if current_row is None:
                        if safe_expected_etag is not None:
                            raise DocumentTranscriptionRunConflictError(
                                "decisionEtag cannot be provided for a new compare decision."
                            )
                        decision_id = str(uuid4())
                        next_etag = hashlib.sha256(
                            f"{decision_id}|{safe_decision}|{decided_by}|{now_seed}".encode(
                                "utf-8"
                            )
                        ).hexdigest()
                        cursor.execute(
                            """
                            INSERT INTO transcription_compare_decisions (
                              id,
                              document_id,
                              base_run_id,
                              candidate_run_id,
                              page_id,
                              line_id,
                              token_id,
                              decision,
                              decision_etag,
                              decided_by,
                              decided_at,
                              decision_reason
                            )
                            VALUES (
                              %(id)s,
                              %(document_id)s,
                              %(base_run_id)s,
                              %(candidate_run_id)s,
                              %(page_id)s,
                              %(line_id)s,
                              %(token_id)s,
                              %(decision)s,
                              %(decision_etag)s,
                              %(decided_by)s,
                              NOW(),
                              %(decision_reason)s
                            )
                            RETURNING
                              id,
                              document_id,
                              base_run_id,
                              candidate_run_id,
                              page_id,
                              line_id,
                              token_id,
                              decision,
                              decision_etag,
                              decided_by,
                              decided_at,
                              decision_reason,
                              created_at,
                              updated_at
                            """,
                            {
                                "id": decision_id,
                                "document_id": document_id,
                                "base_run_id": base_run_id,
                                "candidate_run_id": candidate_run_id,
                                "page_id": safe_page_id,
                                "line_id": safe_line_id,
                                "token_id": safe_token_id,
                                "decision": safe_decision,
                                "decision_etag": next_etag,
                                "decided_by": decided_by,
                                "decision_reason": safe_reason,
                            },
                        )
                        persisted_row = cursor.fetchone()
                        cursor.execute(
                            """
                            INSERT INTO transcription_compare_decision_events (
                              id,
                              decision_id,
                              document_id,
                              base_run_id,
                              candidate_run_id,
                              page_id,
                              line_id,
                              token_id,
                              from_decision,
                              to_decision,
                              actor_user_id,
                              reason
                            )
                            VALUES (
                              %(id)s,
                              %(decision_id)s,
                              %(document_id)s,
                              %(base_run_id)s,
                              %(candidate_run_id)s,
                              %(page_id)s,
                              %(line_id)s,
                              %(token_id)s,
                              NULL,
                              %(to_decision)s,
                              %(actor_user_id)s,
                              %(reason)s
                            )
                            """,
                            {
                                "id": str(uuid4()),
                                "decision_id": decision_id,
                                "document_id": document_id,
                                "base_run_id": base_run_id,
                                "candidate_run_id": candidate_run_id,
                                "page_id": safe_page_id,
                                "line_id": safe_line_id,
                                "token_id": safe_token_id,
                                "to_decision": safe_decision,
                                "actor_user_id": decided_by,
                                "reason": safe_reason,
                            },
                        )
                    else:
                        current_etag = str(current_row["decision_etag"])
                        if safe_expected_etag is None:
                            raise DocumentTranscriptionRunConflictError(
                                "decisionEtag is required when updating an existing compare decision."
                            )
                        if safe_expected_etag != current_etag:
                            raise DocumentTranscriptionRunConflictError(
                                "decisionEtag is stale for this compare decision target."
                            )
                        next_etag = hashlib.sha256(
                            f"{str(current_row['id'])}|{safe_decision}|{decided_by}|{now_seed}".encode(
                                "utf-8"
                            )
                        ).hexdigest()
                        cursor.execute(
                            """
                            UPDATE transcription_compare_decisions
                            SET
                              decision = %(decision)s,
                              decision_etag = %(decision_etag)s,
                              decided_by = %(decided_by)s,
                              decided_at = NOW(),
                              decision_reason = %(decision_reason)s,
                              updated_at = NOW()
                            WHERE id = %(id)s
                            RETURNING
                              id,
                              document_id,
                              base_run_id,
                              candidate_run_id,
                              page_id,
                              line_id,
                              token_id,
                              decision,
                              decision_etag,
                              decided_by,
                              decided_at,
                              decision_reason,
                              created_at,
                              updated_at
                            """,
                            {
                                "id": str(current_row["id"]),
                                "decision": safe_decision,
                                "decision_etag": next_etag,
                                "decided_by": decided_by,
                                "decision_reason": safe_reason,
                            },
                        )
                        persisted_row = cursor.fetchone()
                        cursor.execute(
                            """
                            INSERT INTO transcription_compare_decision_events (
                              id,
                              decision_id,
                              document_id,
                              base_run_id,
                              candidate_run_id,
                              page_id,
                              line_id,
                              token_id,
                              from_decision,
                              to_decision,
                              actor_user_id,
                              reason
                            )
                            VALUES (
                              %(id)s,
                              %(decision_id)s,
                              %(document_id)s,
                              %(base_run_id)s,
                              %(candidate_run_id)s,
                              %(page_id)s,
                              %(line_id)s,
                              %(token_id)s,
                              %(from_decision)s,
                              %(to_decision)s,
                              %(actor_user_id)s,
                              %(reason)s
                            )
                            """,
                            {
                                "id": str(uuid4()),
                                "decision_id": str(current_row["id"]),
                                "document_id": document_id,
                                "base_run_id": base_run_id,
                                "candidate_run_id": candidate_run_id,
                                "page_id": safe_page_id,
                                "line_id": safe_line_id,
                                "token_id": safe_token_id,
                                "from_decision": str(current_row["decision"]),
                                "to_decision": safe_decision,
                                "actor_user_id": decided_by,
                                "reason": safe_reason,
                            },
                        )
                connection.commit()
        except DocumentTranscriptionRunConflictError:
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Transcription compare decision persistence failed."
            ) from error
        if persisted_row is None:
            raise DocumentStoreUnavailableError(
                "Transcription compare decision persistence failed."
            )
        return self._as_transcription_compare_decision_record(persisted_row)

    def mark_transcription_run_running(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> TranscriptionRunRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          tr.id,
                          tr.status
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
                    status = self._assert_transcription_run_status(str(current["status"]))
                    if status == "QUEUED":
                        cursor.execute(
                            """
                            UPDATE transcription_runs
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
                            UPDATE page_transcription_results
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
        except DocumentNotFoundError:
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Transcription run transition failed."
            ) from error
        if row is None:
            raise DocumentStoreUnavailableError("Transcription run transition failed.")
        return self._as_transcription_run_record(row)

    def mark_transcription_page_running(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> PageTranscriptionResultRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE page_transcription_results AS ptr
                        SET
                          status = 'RUNNING',
                          updated_at = NOW()
                        FROM transcription_runs AS tr
                        WHERE ptr.run_id = %(run_id)s
                          AND ptr.page_id = %(page_id)s
                          AND tr.id = ptr.run_id
                          AND tr.project_id = %(project_id)s
                          AND tr.document_id = %(document_id)s
                          AND ptr.status IN ('QUEUED', 'RUNNING')
                        RETURNING
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
                          ptr.reviewer_assignment_user_id,
                          ptr.reviewer_assignment_updated_by,
                          ptr.reviewer_assignment_updated_at,
                          ptr.created_at,
                          ptr.updated_at
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
            raise DocumentStoreUnavailableError(
                "Transcription page transition failed."
            ) from error
        if row is None:
            current = self.get_page_transcription_result(
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
                page_id=page_id,
            )
            if current is None:
                raise DocumentNotFoundError("Transcription page result not found.")
            return current
        return self._as_page_transcription_result_record(row)

    def replace_line_transcription_results(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        rows: list[dict[str, object]],
    ) -> list[LineTranscriptionResultRecord]:
        self.ensure_schema()
        normalized_rows: list[dict[str, object]] = []
        seen_line_ids: set[str] = set()
        for row in rows:
            raw_line_id = row.get("line_id")
            if not isinstance(raw_line_id, str) or not raw_line_id.strip():
                raise DocumentStoreUnavailableError(
                    "Line transcription result line_id is required."
                )
            line_id = raw_line_id.strip()
            if line_id in seen_line_ids:
                raise DocumentStoreUnavailableError(
                    "Line transcription results must be unique per line_id."
                )
            seen_line_ids.add(line_id)
            text_diplomatic = (
                str(row["text_diplomatic"])
                if isinstance(row.get("text_diplomatic"), str)
                else ""
            )
            raw_conf = row.get("conf_line")
            conf_line: float | None = None
            if raw_conf is not None:
                if not isinstance(raw_conf, (int, float)):
                    raise DocumentStoreUnavailableError(
                        "Line transcription confidence must be numeric."
                    )
                conf_line = float(raw_conf)
                if conf_line < 0 or conf_line > 1:
                    raise DocumentStoreUnavailableError(
                        "Line transcription confidence must be between 0 and 1."
                    )
            confidence_basis = self._assert_transcription_confidence_basis(
                str(row.get("confidence_basis") or "MODEL_NATIVE")
            )
            confidence_band = self._assert_transcription_confidence_band(
                str(row.get("confidence_band") or "UNKNOWN")
            )
            confidence_calibration_version = str(
                row.get("confidence_calibration_version") or "v1"
            ).strip()
            if not confidence_calibration_version:
                confidence_calibration_version = "v1"
            alignment_json_key = (
                str(row["alignment_json_key"]).strip()
                if isinstance(row.get("alignment_json_key"), str)
                and str(row["alignment_json_key"]).strip()
                else None
            )
            char_boxes_key = (
                str(row["char_boxes_key"]).strip()
                if isinstance(row.get("char_boxes_key"), str)
                and str(row["char_boxes_key"]).strip()
                else None
            )
            schema_validation_status = self._assert_transcription_line_schema_status(
                str(row.get("schema_validation_status") or "INVALID")
            )
            flags_json = row.get("flags_json")
            if not isinstance(flags_json, dict):
                flags_json = {}
            machine_output_sha256 = (
                str(row["machine_output_sha256"]).strip()
                if isinstance(row.get("machine_output_sha256"), str)
                and str(row["machine_output_sha256"]).strip()
                else None
            )
            active_transcript_version_id = (
                str(row["active_transcript_version_id"]).strip()
                if isinstance(row.get("active_transcript_version_id"), str)
                and str(row["active_transcript_version_id"]).strip()
                else None
            )
            raw_version_etag = row.get("version_etag")
            if not isinstance(raw_version_etag, str) or not raw_version_etag.strip():
                raise DocumentStoreUnavailableError(
                    "Line transcription result version_etag is required."
                )
            version_etag = raw_version_etag.strip()
            token_anchor_status = self._assert_token_anchor_status(
                str(row.get("token_anchor_status") or "REFRESH_REQUIRED")
            )
            normalized_rows.append(
                {
                    "line_id": line_id,
                    "text_diplomatic": text_diplomatic,
                    "conf_line": conf_line,
                    "confidence_band": confidence_band,
                    "confidence_basis": confidence_basis,
                    "confidence_calibration_version": confidence_calibration_version,
                    "alignment_json_key": alignment_json_key,
                    "char_boxes_key": char_boxes_key,
                    "schema_validation_status": schema_validation_status,
                    "flags_json": flags_json,
                    "machine_output_sha256": machine_output_sha256,
                    "active_transcript_version_id": active_transcript_version_id,
                    "version_etag": version_etag,
                    "token_anchor_status": token_anchor_status,
                }
            )

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          ptr.page_id,
                          p.width,
                          p.height
                        FROM page_transcription_results AS ptr
                        INNER JOIN transcription_runs AS tr
                          ON tr.id = ptr.run_id
                        INNER JOIN pages AS p
                          ON p.id = ptr.page_id
                        WHERE ptr.run_id = %(run_id)s
                          AND ptr.page_id = %(page_id)s
                          AND tr.project_id = %(project_id)s
                          AND tr.document_id = %(document_id)s
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
                        raise DocumentNotFoundError("Transcription page result not found.")

                    cursor.execute(
                        """
                        DELETE FROM line_transcription_results
                        WHERE run_id = %(run_id)s
                          AND page_id = %(page_id)s
                        """,
                        {"run_id": run_id, "page_id": page_id},
                    )
                    for row_payload in normalized_rows:
                        cursor.execute(
                            """
                            INSERT INTO line_transcription_results (
                              run_id,
                              page_id,
                              line_id,
                              text_diplomatic,
                              conf_line,
                              confidence_band,
                              confidence_basis,
                              confidence_calibration_version,
                              alignment_json_key,
                              char_boxes_key,
                              schema_validation_status,
                              flags_json,
                              machine_output_sha256,
                              active_transcript_version_id,
                              version_etag,
                              token_anchor_status,
                              created_at,
                              updated_at
                            )
                            VALUES (
                              %(run_id)s,
                              %(page_id)s,
                              %(line_id)s,
                              %(text_diplomatic)s,
                              %(conf_line)s,
                              %(confidence_band)s,
                              %(confidence_basis)s,
                              %(confidence_calibration_version)s,
                              %(alignment_json_key)s,
                              %(char_boxes_key)s,
                              %(schema_validation_status)s,
                              %(flags_json)s::jsonb,
                              %(machine_output_sha256)s,
                              %(active_transcript_version_id)s,
                              %(version_etag)s,
                              %(token_anchor_status)s,
                              NOW(),
                              NOW()
                            )
                            """,
                            {
                                "run_id": run_id,
                                "page_id": page_id,
                                "line_id": row_payload["line_id"],
                                "text_diplomatic": row_payload["text_diplomatic"],
                                "conf_line": row_payload["conf_line"],
                                "confidence_band": row_payload["confidence_band"],
                                "confidence_basis": row_payload["confidence_basis"],
                                "confidence_calibration_version": row_payload[
                                    "confidence_calibration_version"
                                ],
                                "alignment_json_key": row_payload["alignment_json_key"],
                                "char_boxes_key": row_payload["char_boxes_key"],
                                "schema_validation_status": row_payload[
                                    "schema_validation_status"
                                ],
                                "flags_json": json.dumps(
                                    row_payload["flags_json"],
                                    ensure_ascii=True,
                                    sort_keys=True,
                                ),
                                "machine_output_sha256": row_payload[
                                    "machine_output_sha256"
                                ],
                                "active_transcript_version_id": row_payload[
                                    "active_transcript_version_id"
                                ],
                                "version_etag": row_payload["version_etag"],
                                "token_anchor_status": row_payload["token_anchor_status"],
                            },
                        )
                    cursor.execute(
                        """
                        SELECT
                          ltr.run_id,
                          ltr.page_id,
                          ltr.line_id,
                          ltr.text_diplomatic,
                          ltr.conf_line,
                          ltr.confidence_band,
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
                        WHERE ltr.run_id = %(run_id)s
                          AND ltr.page_id = %(page_id)s
                        ORDER BY ltr.line_id ASC
                        """,
                        {"run_id": run_id, "page_id": page_id},
                    )
                    persisted_rows = cursor.fetchall()
                connection.commit()
        except DocumentNotFoundError:
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Line transcription-result persistence failed."
            ) from error
        return [self._as_line_transcription_result_record(row) for row in persisted_rows]

    def replace_token_transcription_results(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        rows: list[dict[str, object]],
    ) -> list[TokenTranscriptionResultRecord]:
        self.ensure_schema()
        normalized_rows: list[dict[str, object]] = []
        seen_token_ids: set[str] = set()
        for row in rows:
            raw_token_id = row.get("token_id")
            if not isinstance(raw_token_id, str) or not raw_token_id.strip():
                raise DocumentStoreUnavailableError(
                    "Token transcription result token_id is required."
                )
            token_id = raw_token_id.strip()
            if token_id in seen_token_ids:
                raise DocumentStoreUnavailableError(
                    "Token transcription results must be unique per token_id."
                )
            seen_token_ids.add(token_id)
            raw_token_index = row.get("token_index")
            if not isinstance(raw_token_index, int) or raw_token_index < 0:
                raise DocumentStoreUnavailableError(
                    "Token transcription result token_index must be >= 0."
                )
            raw_token_text = row.get("token_text")
            if not isinstance(raw_token_text, str) or raw_token_text.strip() == "":
                raise DocumentStoreUnavailableError(
                    "Token transcription result token_text is required."
                )
            token_confidence = row.get("token_confidence")
            if token_confidence is not None and not isinstance(
                token_confidence, (int, float)
            ):
                raise DocumentStoreUnavailableError(
                    "Token transcription confidence must be numeric."
                )
            line_id = (
                str(row["line_id"]).strip()
                if isinstance(row.get("line_id"), str) and str(row["line_id"]).strip()
                else None
            )
            bbox_json = row.get("bbox_json")
            if bbox_json is not None and not isinstance(bbox_json, dict):
                raise DocumentStoreUnavailableError(
                    "Token transcription bbox_json must be an object."
                )
            polygon_json = row.get("polygon_json")
            if polygon_json is not None and not isinstance(polygon_json, dict):
                raise DocumentStoreUnavailableError(
                    "Token transcription polygon_json must be an object."
                )
            source_kind = self._assert_transcription_token_source_kind(
                str(row.get("source_kind") or "LINE")
            )
            raw_source_ref_id = row.get("source_ref_id")
            if not isinstance(raw_source_ref_id, str) or not raw_source_ref_id.strip():
                raise DocumentStoreUnavailableError(
                    "Token transcription source_ref_id is required."
                )
            source_ref_id = raw_source_ref_id.strip()
            if not self._is_safe_transcription_source_ref_id(source_ref_id):
                raise DocumentStoreUnavailableError(
                    "Token transcription source_ref_id must be an internal anchor reference."
                )
            projection_basis = self._assert_transcription_projection_basis(
                str(row.get("projection_basis") or "ENGINE_OUTPUT")
            )
            normalized_rows.append(
                {
                    "line_id": line_id,
                    "token_id": token_id,
                    "token_index": raw_token_index,
                    "token_text": raw_token_text,
                    "token_confidence": (
                        float(token_confidence)
                        if isinstance(token_confidence, (int, float))
                        else None
                    ),
                    "bbox_json": bbox_json if isinstance(bbox_json, dict) else None,
                    "polygon_json": (
                        polygon_json if isinstance(polygon_json, dict) else None
                    ),
                    "source_kind": source_kind,
                    "source_ref_id": source_ref_id,
                    "projection_basis": projection_basis,
                }
            )

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          ptr.page_id,
                          p.width,
                          p.height
                        FROM page_transcription_results AS ptr
                        INNER JOIN transcription_runs AS tr
                          ON tr.id = ptr.run_id
                        INNER JOIN pages AS p
                          ON p.id = ptr.page_id
                        WHERE ptr.run_id = %(run_id)s
                          AND ptr.page_id = %(page_id)s
                          AND tr.project_id = %(project_id)s
                          AND tr.document_id = %(document_id)s
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
                        raise DocumentNotFoundError("Transcription page result not found.")
                    page_width = float(page_row.get("width") or 0)
                    page_height = float(page_row.get("height") or 0)
                    if page_width <= 0 or page_height <= 0:
                        raise DocumentStoreUnavailableError(
                            "Token transcription result page dimensions are invalid."
                        )

                    cursor.execute(
                        """
                        SELECT ltr.line_id
                        FROM line_transcription_results AS ltr
                        WHERE ltr.run_id = %(run_id)s
                          AND ltr.page_id = %(page_id)s
                        """,
                        {"run_id": run_id, "page_id": page_id},
                    )
                    line_ids = {
                        str(item["line_id"])
                        for item in cursor.fetchall()
                        if isinstance(item.get("line_id"), str)
                    }
                    cursor.execute(
                        """
                        SELECT lrc.id
                        FROM layout_rescue_candidates AS lrc
                        INNER JOIN transcription_runs AS tr
                          ON tr.input_layout_run_id = lrc.run_id
                        WHERE tr.id = %(run_id)s
                          AND lrc.page_id = %(page_id)s
                          AND lrc.status IN ('ACCEPTED', 'RESOLVED')
                        """,
                        {"run_id": run_id, "page_id": page_id},
                    )
                    rescue_source_ids = {
                        str(item["id"])
                        for item in cursor.fetchall()
                        if isinstance(item.get("id"), str)
                    }

                    for row_payload in normalized_rows:
                        source_kind = str(row_payload["source_kind"])
                        source_ref_id = str(row_payload["source_ref_id"])
                        line_id = (
                            str(row_payload["line_id"])
                            if isinstance(row_payload.get("line_id"), str)
                            else None
                        )
                        if source_kind == "LINE":
                            if line_id is None or line_id != source_ref_id:
                                raise DocumentStoreUnavailableError(
                                    "Line-backed token anchors must link canonical line_id and source_ref_id."
                                )
                            if source_ref_id not in line_ids:
                                raise DocumentStoreUnavailableError(
                                    "Line-backed token source_ref_id must match an existing line anchor."
                                )
                        else:
                            if source_ref_id not in rescue_source_ids:
                                raise DocumentStoreUnavailableError(
                                    "Rescue-backed token source_ref_id must match an accepted rescue candidate."
                                )
                            if line_id is not None and line_id not in line_ids:
                                raise DocumentStoreUnavailableError(
                                    "Rescue-backed token line_id must reference a canonical line when present."
                                )

                        bbox_valid = self._is_valid_token_bbox(
                            row_payload.get("bbox_json"),  # type: ignore[arg-type]
                            page_width=page_width,
                            page_height=page_height,
                        )
                        polygon_valid = self._is_valid_token_polygon(
                            row_payload.get("polygon_json"),  # type: ignore[arg-type]
                            page_width=page_width,
                            page_height=page_height,
                        )
                        if not bbox_valid and not polygon_valid:
                            raise DocumentStoreUnavailableError(
                                "Token anchors require page-bounded bbox_json and/or polygon_json geometry."
                            )

                    cursor.execute(
                        """
                        DELETE FROM token_transcription_results
                        WHERE run_id = %(run_id)s
                          AND page_id = %(page_id)s
                        """,
                        {"run_id": run_id, "page_id": page_id},
                    )
                    for row_payload in normalized_rows:
                        cursor.execute(
                            """
                            INSERT INTO token_transcription_results (
                              run_id,
                              page_id,
                              line_id,
                              token_id,
                              token_index,
                              token_text,
                              token_confidence,
                              bbox_json,
                              polygon_json,
                              source_kind,
                              source_ref_id,
                              projection_basis,
                              created_at,
                              updated_at
                            )
                            VALUES (
                              %(run_id)s,
                              %(page_id)s,
                              %(line_id)s,
                              %(token_id)s,
                              %(token_index)s,
                              %(token_text)s,
                              %(token_confidence)s,
                              %(bbox_json)s::jsonb,
                              %(polygon_json)s::jsonb,
                              %(source_kind)s,
                              %(source_ref_id)s,
                              %(projection_basis)s,
                              NOW(),
                              NOW()
                            )
                            """,
                            {
                                "run_id": run_id,
                                "page_id": page_id,
                                "line_id": row_payload["line_id"],
                                "token_id": row_payload["token_id"],
                                "token_index": row_payload["token_index"],
                                "token_text": row_payload["token_text"],
                                "token_confidence": row_payload["token_confidence"],
                                "bbox_json": (
                                    json.dumps(
                                        row_payload["bbox_json"],
                                        ensure_ascii=True,
                                        sort_keys=True,
                                    )
                                    if row_payload["bbox_json"] is not None
                                    else None
                                ),
                                "polygon_json": (
                                    json.dumps(
                                        row_payload["polygon_json"],
                                        ensure_ascii=True,
                                        sort_keys=True,
                                    )
                                    if row_payload["polygon_json"] is not None
                                    else None
                                ),
                                "source_kind": row_payload["source_kind"],
                                "source_ref_id": row_payload["source_ref_id"],
                                "projection_basis": row_payload["projection_basis"],
                            },
                        )
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
                        WHERE ttr.run_id = %(run_id)s
                          AND ttr.page_id = %(page_id)s
                        ORDER BY ttr.token_index ASC, ttr.token_id ASC
                        """,
                        {"run_id": run_id, "page_id": page_id},
                    )
                    persisted_rows = cursor.fetchall()
                connection.commit()
        except DocumentNotFoundError:
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Token transcription-result persistence failed."
            ) from error
        return [self._as_token_transcription_result_record(row) for row in persisted_rows]

    def complete_transcription_page_result(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        pagexml_out_key: str,
        pagexml_out_sha256: str,
        raw_model_response_key: str,
        raw_model_response_sha256: str,
        metrics_json: dict[str, object],
        warnings_json: list[str],
        hocr_out_key: str | None = None,
        hocr_out_sha256: str | None = None,
    ) -> PageTranscriptionResultRecord:
        self.ensure_schema()
        metrics_payload = json.dumps(metrics_json, sort_keys=True, ensure_ascii=True)
        warnings_payload = json.dumps(warnings_json, sort_keys=True, ensure_ascii=True)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE page_transcription_results AS ptr
                        SET
                          status = 'SUCCEEDED',
                          pagexml_out_key = %(pagexml_out_key)s,
                          pagexml_out_sha256 = %(pagexml_out_sha256)s,
                          raw_model_response_key = %(raw_model_response_key)s,
                          raw_model_response_sha256 = %(raw_model_response_sha256)s,
                          hocr_out_key = %(hocr_out_key)s,
                          hocr_out_sha256 = %(hocr_out_sha256)s,
                          metrics_json = %(metrics_json)s::jsonb,
                          warnings_json = %(warnings_json)s::jsonb,
                          failure_reason = NULL,
                          updated_at = NOW()
                        FROM transcription_runs AS tr
                        WHERE ptr.run_id = %(run_id)s
                          AND ptr.page_id = %(page_id)s
                          AND tr.id = ptr.run_id
                          AND tr.project_id = %(project_id)s
                          AND tr.document_id = %(document_id)s
                        RETURNING
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
                          ptr.reviewer_assignment_user_id,
                          ptr.reviewer_assignment_updated_by,
                          ptr.reviewer_assignment_updated_at,
                          ptr.created_at,
                          ptr.updated_at
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "project_id": project_id,
                            "document_id": document_id,
                            "pagexml_out_key": pagexml_out_key,
                            "pagexml_out_sha256": pagexml_out_sha256,
                            "raw_model_response_key": raw_model_response_key,
                            "raw_model_response_sha256": raw_model_response_sha256,
                            "hocr_out_key": hocr_out_key,
                            "hocr_out_sha256": hocr_out_sha256,
                            "metrics_json": metrics_payload,
                            "warnings_json": warnings_payload,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Transcription page completion failed."
            ) from error
        if row is None:
            raise DocumentNotFoundError("Transcription page result not found.")
        return self._as_page_transcription_result_record(row)

    def fail_transcription_page_result(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        failure_reason: str,
        raw_model_response_key: str | None = None,
        raw_model_response_sha256: str | None = None,
        metrics_json: dict[str, object] | None = None,
        warnings_json: list[str] | None = None,
    ) -> PageTranscriptionResultRecord:
        self.ensure_schema()
        metrics_payload = json.dumps(metrics_json or {}, sort_keys=True, ensure_ascii=True)
        warnings_payload = json.dumps(warnings_json or [], sort_keys=True, ensure_ascii=True)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE page_transcription_results AS ptr
                        SET
                          status = 'FAILED',
                          raw_model_response_key = COALESCE(
                            %(raw_model_response_key)s,
                            ptr.raw_model_response_key
                          ),
                          raw_model_response_sha256 = COALESCE(
                            %(raw_model_response_sha256)s,
                            ptr.raw_model_response_sha256
                          ),
                          metrics_json = %(metrics_json)s::jsonb,
                          warnings_json = %(warnings_json)s::jsonb,
                          failure_reason = %(failure_reason)s,
                          updated_at = NOW()
                        FROM transcription_runs AS tr
                        WHERE ptr.run_id = %(run_id)s
                          AND ptr.page_id = %(page_id)s
                          AND tr.id = ptr.run_id
                          AND tr.project_id = %(project_id)s
                          AND tr.document_id = %(document_id)s
                        RETURNING
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
                          ptr.reviewer_assignment_user_id,
                          ptr.reviewer_assignment_updated_by,
                          ptr.reviewer_assignment_updated_at,
                          ptr.created_at,
                          ptr.updated_at
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "project_id": project_id,
                            "document_id": document_id,
                            "failure_reason": failure_reason[:1000],
                            "raw_model_response_key": raw_model_response_key,
                            "raw_model_response_sha256": raw_model_response_sha256,
                            "metrics_json": metrics_payload,
                            "warnings_json": warnings_payload,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Transcription page failure update failed."
            ) from error
        if row is None:
            raise DocumentNotFoundError("Transcription page result not found.")
        return self._as_page_transcription_result_record(row)

    def get_transcription_output_projection(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> TranscriptionOutputProjectionRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          top.run_id,
                          top.document_id,
                          top.page_id,
                          top.corrected_pagexml_key,
                          top.corrected_pagexml_sha256,
                          top.corrected_text_sha256,
                          top.source_pagexml_sha256,
                          top.updated_at
                        FROM transcription_output_projections AS top
                        INNER JOIN transcription_runs AS tr
                          ON tr.id = top.run_id
                        WHERE top.run_id = %(run_id)s
                          AND top.page_id = %(page_id)s
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
                "Transcription output projection read failed."
            ) from error
        if row is None:
            return None
        return self._as_transcription_output_projection_record(row)

    def upsert_transcription_output_projection(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        corrected_pagexml_key: str,
        corrected_pagexml_sha256: str,
        corrected_text_sha256: str,
        source_pagexml_sha256: str,
    ) -> TranscriptionOutputProjectionRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT tr.id
                        FROM transcription_runs AS tr
                        WHERE tr.id = %(run_id)s
                          AND tr.project_id = %(project_id)s
                          AND tr.document_id = %(document_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "run_id": run_id,
                            "project_id": project_id,
                            "document_id": document_id,
                        },
                    )
                    run_row = cursor.fetchone()
                    if run_row is None:
                        raise DocumentNotFoundError("Transcription run not found.")
                    cursor.execute(
                        """
                        INSERT INTO transcription_output_projections (
                          run_id,
                          document_id,
                          page_id,
                          corrected_pagexml_key,
                          corrected_pagexml_sha256,
                          corrected_text_sha256,
                          source_pagexml_sha256,
                          updated_at
                        )
                        VALUES (
                          %(run_id)s,
                          %(document_id)s,
                          %(page_id)s,
                          %(corrected_pagexml_key)s,
                          %(corrected_pagexml_sha256)s,
                          %(corrected_text_sha256)s,
                          %(source_pagexml_sha256)s,
                          NOW()
                        )
                        ON CONFLICT (run_id, page_id) DO UPDATE
                        SET
                          corrected_pagexml_key = EXCLUDED.corrected_pagexml_key,
                          corrected_pagexml_sha256 = EXCLUDED.corrected_pagexml_sha256,
                          corrected_text_sha256 = EXCLUDED.corrected_text_sha256,
                          source_pagexml_sha256 = EXCLUDED.source_pagexml_sha256,
                          updated_at = NOW()
                        RETURNING
                          run_id,
                          document_id,
                          page_id,
                          corrected_pagexml_key,
                          corrected_pagexml_sha256,
                          corrected_text_sha256,
                          source_pagexml_sha256,
                          updated_at
                        """,
                        {
                            "run_id": run_id,
                            "document_id": document_id,
                            "page_id": page_id,
                            "corrected_pagexml_key": corrected_pagexml_key,
                            "corrected_pagexml_sha256": corrected_pagexml_sha256,
                            "corrected_text_sha256": corrected_text_sha256,
                            "source_pagexml_sha256": source_pagexml_sha256,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except DocumentNotFoundError:
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Transcription output projection persistence failed."
            ) from error
        if row is None:
            raise DocumentStoreUnavailableError(
                "Transcription output projection persistence failed."
            )
        return self._as_transcription_output_projection_record(row)

    def finalize_transcription_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> TranscriptionRunRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          tr.id,
                          tr.status
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
                    run_status = self._assert_transcription_run_status(
                        str(current["status"])
                    )
                    if run_status != "CANCELED":
                        cursor.execute(
                            """
                            SELECT
                              ptr.status,
                              COUNT(*)::INT AS total
                            FROM page_transcription_results AS ptr
                            WHERE ptr.run_id = %(run_id)s
                            GROUP BY ptr.status
                            """,
                            {"run_id": run_id},
                        )
                        rows = cursor.fetchall()
                        status_counts: dict[TranscriptionRunStatus, int] = {
                            "QUEUED": 0,
                            "RUNNING": 0,
                            "SUCCEEDED": 0,
                            "FAILED": 0,
                            "CANCELED": 0,
                        }
                        for row in rows:
                            key = self._assert_transcription_run_status(str(row["status"]))
                            status_counts[key] = int(row["total"])
                        final_status: TranscriptionRunStatus
                        final_failure_reason: str | None = None
                        if status_counts["FAILED"] > 0:
                            final_status = "FAILED"
                            final_failure_reason = (
                                "One or more transcription page tasks failed."
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
                                UPDATE transcription_runs
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
                        else:
                            cursor.execute(
                                """
                                UPDATE transcription_runs
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
        except DocumentNotFoundError:
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Transcription run finalization failed."
            ) from error
        if row is None:
            raise DocumentStoreUnavailableError("Transcription run finalization failed.")
        return self._as_transcription_run_record(row)

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
                              plr.page_id,
                              plr.page_index,
                              ttr.token_id
                            FROM token_transcription_results AS ttr
                            INNER JOIN page_layout_results AS plr
                              ON plr.page_id = ttr.page_id
                             AND plr.run_id = %(layout_run_id)s
                            LEFT JOIN line_transcription_results AS ltr
                              ON ltr.run_id = ttr.run_id
                             AND ltr.page_id = ttr.page_id
                             AND ltr.line_id = ttr.source_ref_id
                            LEFT JOIN layout_rescue_candidates AS lrc
                              ON lrc.run_id = %(layout_run_id)s
                             AND lrc.page_id = ttr.page_id
                             AND lrc.id = ttr.source_ref_id
                             AND lrc.status IN ('ACCEPTED', 'RESOLVED')
                            WHERE ttr.run_id = %(run_id)s
                              AND plr.page_recall_status <> 'NEEDS_MANUAL_REVIEW'
                              AND (
                                ttr.source_ref_id LIKE 'controlled/%'
                                OR ttr.source_ref_id LIKE '%/%'
                                OR ttr.source_ref_id LIKE '%\\%'
                                OR (
                                  (ttr.bbox_json IS NULL OR ttr.bbox_json = '{}'::jsonb)
                                  AND (
                                    ttr.polygon_json IS NULL
                                    OR ttr.polygon_json = '{}'::jsonb
                                  )
                                )
                                OR (
                                  ttr.source_kind = 'LINE'
                                  AND (
                                    ttr.line_id IS NULL
                                    OR ttr.line_id <> ttr.source_ref_id
                                    OR ltr.line_id IS NULL
                                  )
                                )
                                OR (
                                  ttr.source_kind IN ('RESCUE_CANDIDATE', 'PAGE_WINDOW')
                                  AND lrc.id IS NULL
                                )
                              )
                            ORDER BY
                              plr.page_index ASC,
                              ttr.token_index ASC,
                              ttr.token_id ASC
                            LIMIT 1
                            """,
                            {
                                "layout_run_id": input_layout_run_id,
                                "run_id": run_id,
                            },
                        )
                        invalid_anchor_row = cursor.fetchone()
                        if invalid_anchor_row is not None:
                            invalid_page_number = (
                                int(invalid_anchor_row["page_index"]) + 1
                                if isinstance(invalid_anchor_row.get("page_index"), int)
                                else "unknown"
                            )
                            raise DocumentTranscriptionRunConflictError(
                                "TOKEN_ANCHOR_INVALID: Activation requires valid token anchors "
                                "with safe source references and geometry on all eligible pages; "
                                f"first invalid anchor on page {invalid_page_number}."
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

    def mark_transcription_downstream_redaction_stale(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        reason: str,
    ) -> DocumentTranscriptionProjectionRecord | None:
        self.ensure_schema()
        safe_reason = reason.strip()
        if not safe_reason:
            raise DocumentTranscriptionRunConflictError(
                "downstream invalidation reason is required."
            )
        if len(safe_reason) > 600:
            raise DocumentTranscriptionRunConflictError(
                "downstream invalidation reason must be 600 characters or fewer."
            )
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE document_transcription_projections AS tp
                        SET
                          downstream_redaction_state = 'STALE',
                          downstream_redaction_invalidated_at = NOW(),
                          downstream_redaction_invalidated_reason = %(reason)s,
                          updated_at = NOW()
                        WHERE tp.project_id = %(project_id)s
                          AND tp.document_id = %(document_id)s
                          AND tp.active_transcription_run_id = %(run_id)s
                        RETURNING
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
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                            "reason": safe_reason,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Downstream redaction invalidation update failed."
            ) from error
        if row is None:
            return None
        return self._as_transcription_projection_record(row)

    def list_transcript_variant_layers(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        variant_kind: TranscriptVariantKind = "NORMALISED",
    ) -> list[TranscriptVariantLayerRecord]:
        self.ensure_schema()
        safe_variant_kind = self._assert_transcript_variant_kind(str(variant_kind))
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          tvl.id,
                          tvl.run_id,
                          tvl.page_id,
                          tvl.variant_kind,
                          tvl.base_transcript_version_id,
                          tvl.base_version_set_sha256,
                          tvl.base_projection_sha256,
                          tvl.variant_text_key,
                          tvl.variant_text_sha256,
                          tvl.created_by,
                          tvl.created_at
                        FROM transcript_variant_layers AS tvl
                        INNER JOIN transcription_runs AS tr
                          ON tr.id = tvl.run_id
                        WHERE tvl.run_id = %(run_id)s
                          AND tvl.page_id = %(page_id)s
                          AND tvl.variant_kind = %(variant_kind)s
                          AND tr.project_id = %(project_id)s
                          AND tr.document_id = %(document_id)s
                        ORDER BY tvl.created_at DESC, tvl.id DESC
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "variant_kind": safe_variant_kind,
                            "project_id": project_id,
                            "document_id": document_id,
                        },
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Transcript variant-layer listing failed."
            ) from error
        return [self._as_transcript_variant_layer_record(row) for row in rows]

    def list_transcript_variant_suggestions(
        self,
        *,
        project_id: str,
        document_id: str,
        variant_layer_id: str,
    ) -> list[TranscriptVariantSuggestionRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          tvs.id,
                          tvs.variant_layer_id,
                          tvs.line_id,
                          tvs.suggestion_text,
                          tvs.confidence,
                          tvs.status,
                          tvs.decided_by,
                          tvs.decided_at,
                          tvs.decision_reason,
                          tvs.metadata_json,
                          tvs.created_at,
                          tvs.updated_at
                        FROM transcript_variant_suggestions AS tvs
                        INNER JOIN transcript_variant_layers AS tvl
                          ON tvl.id = tvs.variant_layer_id
                        INNER JOIN transcription_runs AS tr
                          ON tr.id = tvl.run_id
                        WHERE tvs.variant_layer_id = %(variant_layer_id)s
                          AND tr.project_id = %(project_id)s
                          AND tr.document_id = %(document_id)s
                        ORDER BY tvs.created_at ASC, tvs.id ASC
                        """,
                        {
                            "variant_layer_id": variant_layer_id,
                            "project_id": project_id,
                            "document_id": document_id,
                        },
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Transcript variant suggestion listing failed."
            ) from error
        return [self._as_transcript_variant_suggestion_record(row) for row in rows]

    def record_transcript_variant_suggestion_decision(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        variant_kind: TranscriptVariantKind,
        suggestion_id: str,
        decision: TranscriptVariantSuggestionDecision,
        actor_user_id: str,
        reason: str | None = None,
    ) -> tuple[TranscriptVariantSuggestionRecord, TranscriptVariantSuggestionEventRecord]:
        self.ensure_schema()
        safe_variant_kind = self._assert_transcript_variant_kind(str(variant_kind))
        safe_decision = self._assert_transcript_variant_suggestion_decision(str(decision))
        safe_suggestion_id = suggestion_id.strip()
        if not safe_suggestion_id:
            raise DocumentTranscriptionRunConflictError("suggestion_id is required.")
        safe_reason = reason.strip() if isinstance(reason, str) and reason.strip() else None
        if safe_reason is not None and len(safe_reason) > 600:
            raise DocumentTranscriptionRunConflictError(
                "decision reason must be 600 characters or fewer."
            )
        to_status: TranscriptVariantSuggestionStatus = (
            "ACCEPTED" if safe_decision == "ACCEPT" else "REJECTED"
        )

        updated_suggestion_row: dict[str, object] | None = None
        event_row: dict[str, object] | None = None
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "SELECT pg_advisory_xact_lock(hashtext(%(lock_key)s))",
                        {"lock_key": f"transcript_variant_suggestion|{safe_suggestion_id}"},
                    )
                    cursor.execute(
                        """
                        SELECT
                          tvs.id,
                          tvs.variant_layer_id,
                          tvs.status
                        FROM transcript_variant_suggestions AS tvs
                        INNER JOIN transcript_variant_layers AS tvl
                          ON tvl.id = tvs.variant_layer_id
                        INNER JOIN transcription_runs AS tr
                          ON tr.id = tvl.run_id
                        WHERE tvs.id = %(suggestion_id)s
                          AND tvl.run_id = %(run_id)s
                          AND tvl.page_id = %(page_id)s
                          AND tvl.variant_kind = %(variant_kind)s
                          AND tr.project_id = %(project_id)s
                          AND tr.document_id = %(document_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "suggestion_id": safe_suggestion_id,
                            "run_id": run_id,
                            "page_id": page_id,
                            "variant_kind": safe_variant_kind,
                            "project_id": project_id,
                            "document_id": document_id,
                        },
                    )
                    current = cursor.fetchone()
                    if current is None:
                        raise DocumentNotFoundError(
                            "Transcript variant suggestion not found."
                        )
                    from_status = self._assert_transcript_variant_suggestion_status(
                        str(current["status"])
                    )
                    cursor.execute(
                        """
                        UPDATE transcript_variant_suggestions
                        SET
                          status = %(status)s,
                          decided_by = %(decided_by)s,
                          decided_at = NOW(),
                          decision_reason = %(decision_reason)s,
                          updated_at = NOW()
                        WHERE id = %(id)s
                        RETURNING
                          id,
                          variant_layer_id,
                          line_id,
                          suggestion_text,
                          confidence,
                          status,
                          decided_by,
                          decided_at,
                          decision_reason,
                          metadata_json,
                          created_at,
                          updated_at
                        """,
                        {
                            "id": safe_suggestion_id,
                            "status": to_status,
                            "decided_by": actor_user_id,
                            "decision_reason": safe_reason,
                        },
                    )
                    updated_suggestion_row = cursor.fetchone()
                    cursor.execute(
                        """
                        INSERT INTO transcript_variant_suggestion_events (
                          id,
                          suggestion_id,
                          variant_layer_id,
                          actor_user_id,
                          decision,
                          from_status,
                          to_status,
                          reason
                        )
                        VALUES (
                          %(id)s,
                          %(suggestion_id)s,
                          %(variant_layer_id)s,
                          %(actor_user_id)s,
                          %(decision)s,
                          %(from_status)s,
                          %(to_status)s,
                          %(reason)s
                        )
                        RETURNING
                          id,
                          suggestion_id,
                          variant_layer_id,
                          actor_user_id,
                          decision,
                          from_status,
                          to_status,
                          reason,
                          created_at
                        """,
                        {
                            "id": str(uuid4()),
                            "suggestion_id": safe_suggestion_id,
                            "variant_layer_id": str(current["variant_layer_id"]),
                            "actor_user_id": actor_user_id,
                            "decision": safe_decision,
                            "from_status": from_status,
                            "to_status": to_status,
                            "reason": safe_reason,
                        },
                    )
                    event_row = cursor.fetchone()
                connection.commit()
        except (DocumentNotFoundError, DocumentTranscriptionRunConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Transcript variant suggestion decision persistence failed."
            ) from error
        if updated_suggestion_row is None or event_row is None:
            raise DocumentStoreUnavailableError(
                "Transcript variant suggestion decision persistence failed."
            )
        return (
            self._as_transcript_variant_suggestion_record(updated_suggestion_row),
            self._as_transcript_variant_suggestion_event_record(event_row),
        )

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

    @staticmethod
    def _compute_redaction_etag(*parts: str) -> str:
        seed = "|".join(parts)
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()

    @staticmethod
    def _derive_redaction_run_output_event_type(
        *,
        to_status: RedactionOutputStatus,
    ) -> RedactionRunOutputEventType:
        if to_status == "READY":
            return "RUN_OUTPUT_GENERATION_SUCCEEDED"
        if to_status == "FAILED":
            return "RUN_OUTPUT_GENERATION_FAILED"
        if to_status == "CANCELED":
            return "RUN_OUTPUT_GENERATION_CANCELED"
        return "RUN_OUTPUT_GENERATION_STARTED"

    def _append_redaction_run_output_event(
        self,
        *,
        cursor: psycopg.Cursor,
        run_id: str,
        from_status: RedactionOutputStatus | None,
        to_status: RedactionOutputStatus,
        reason: str | None = None,
        actor_user_id: str | None = None,
        created_at: datetime | None = None,
    ) -> None:
        event_id = str(uuid4())
        event_time = created_at or datetime.now(timezone.utc)
        cursor.execute(
            """
            INSERT INTO redaction_run_output_events (
              id,
              run_id,
              event_type,
              from_status,
              to_status,
              reason,
              actor_user_id,
              created_at
            )
            VALUES (
              %(id)s,
              %(run_id)s,
              %(event_type)s,
              %(from_status)s,
              %(to_status)s,
              %(reason)s,
              %(actor_user_id)s,
              %(created_at)s
            )
            """,
            {
                "id": event_id,
                "run_id": run_id,
                "event_type": self._derive_redaction_run_output_event_type(to_status=to_status),
                "from_status": from_status,
                "to_status": to_status,
                "reason": reason,
                "actor_user_id": actor_user_id,
                "created_at": event_time,
            },
        )

    def _build_redaction_approval_snapshot_bytes(
        self,
        *,
        cursor: psycopg.Cursor,
        run_id: str,
        captured_at: datetime,
    ) -> tuple[bytes, str]:
        cursor.execute(
            """
            SELECT
              id,
              project_id,
              document_id,
              input_transcription_run_id,
              input_layout_run_id,
              run_kind,
              policy_snapshot_hash,
              policy_id,
              policy_family_id,
              policy_version,
              status,
              created_at,
              started_at,
              finished_at
            FROM redaction_runs
            WHERE id = %(run_id)s
            LIMIT 1
            """,
            {"run_id": run_id},
        )
        run_row = cursor.fetchone()
        if run_row is None:
            raise DocumentNotFoundError("Redaction run not found.")

        cursor.execute(
            """
            SELECT
              review_status,
              review_started_by,
              review_started_at,
              approved_by,
              approved_at,
              approved_snapshot_sha256,
              locked_at
            FROM redaction_run_reviews
            WHERE run_id = %(run_id)s
            LIMIT 1
            """,
            {"run_id": run_id},
        )
        review_row = cursor.fetchone()
        if review_row is None:
            raise DocumentNotFoundError("Redaction run review not found.")

        cursor.execute(
            """
            SELECT
              status,
              output_manifest_key,
              output_manifest_sha256,
              page_count
            FROM redaction_run_outputs
            WHERE run_id = %(run_id)s
            LIMIT 1
            """,
            {"run_id": run_id},
        )
        run_output_row = cursor.fetchone()
        if run_output_row is None:
            raise DocumentNotFoundError("Redaction run output not found.")

        cursor.execute(
            """
            SELECT
              rf.id,
              rf.page_id,
              p.page_index,
              rf.line_id,
              rf.category,
              rf.span_start,
              rf.span_end,
              rf.span_basis_kind,
              rf.span_basis_ref,
              rf.token_refs_json,
              rf.bbox_refs,
              rf.confidence,
              rf.basis_primary,
              rf.basis_secondary_json,
              rf.decision_status,
              rf.area_mask_id,
              rf.decision_by,
              rf.decision_at,
              rf.decision_etag,
              rf.updated_at,
              latest_decision.action_type AS action_type
            FROM redaction_findings AS rf
            INNER JOIN pages AS p
              ON p.id = rf.page_id
            LEFT JOIN LATERAL (
              SELECT action_type
              FROM redaction_decision_events
              WHERE finding_id = rf.id
              ORDER BY created_at DESC, id DESC
              LIMIT 1
            ) AS latest_decision
              ON TRUE
            WHERE rf.run_id = %(run_id)s
            ORDER BY p.page_index ASC, rf.page_id ASC, rf.id ASC
            """,
            {"run_id": run_id},
        )
        finding_rows = cursor.fetchall()

        cursor.execute(
            """
            SELECT
              id,
              page_id,
              version_etag,
              supersedes_area_mask_id,
              superseded_by_area_mask_id,
              updated_at
            FROM redaction_area_masks
            WHERE run_id = %(run_id)s
            ORDER BY page_id ASC, created_at ASC, id ASC
            """,
            {"run_id": run_id},
        )
        mask_rows = cursor.fetchall()

        cursor.execute(
            """
            SELECT
              pr.page_id,
              p.page_index,
              pr.review_status,
              pr.review_etag,
              pr.first_reviewed_by,
              pr.first_reviewed_at,
              pr.requires_second_review,
              pr.second_review_status,
              pr.second_reviewed_by,
              pr.second_reviewed_at,
              pr.updated_at
            FROM redaction_page_reviews AS pr
            INNER JOIN pages AS p
              ON p.id = pr.page_id
            WHERE pr.run_id = %(run_id)s
            ORDER BY p.page_index ASC, pr.page_id ASC
            """,
            {"run_id": run_id},
        )
        page_review_rows = cursor.fetchall()

        cursor.execute(
            """
            SELECT
              ro.page_id,
              p.page_index,
              ro.status,
              ro.safeguarded_preview_key,
              ro.preview_sha256,
              ro.generated_at
            FROM redaction_outputs AS ro
            INNER JOIN pages AS p
              ON p.id = ro.page_id
            WHERE ro.run_id = %(run_id)s
            ORDER BY p.page_index ASC, ro.page_id ASC
            """,
            {"run_id": run_id},
        )
        output_rows = cursor.fetchall()

        snapshot_payload = {
            "schemaVersion": 3,
            "runId": run_id,
            "capturedAt": captured_at.isoformat(),
            "review": {
                "reviewStatus": str(review_row["review_status"]),
                "reviewStartedBy": (
                    str(review_row["review_started_by"])
                    if isinstance(review_row.get("review_started_by"), str)
                    else None
                ),
                "reviewStartedAt": (
                    review_row["review_started_at"].isoformat()
                    if isinstance(review_row.get("review_started_at"), datetime)
                    else None
                ),
                "approvedBy": (
                    str(review_row["approved_by"])
                    if isinstance(review_row.get("approved_by"), str)
                    else None
                ),
                "approvedAt": (
                    review_row["approved_at"].isoformat()
                    if isinstance(review_row.get("approved_at"), datetime)
                    else None
                ),
                "approvedSnapshotSha256": (
                    str(review_row["approved_snapshot_sha256"])
                    if isinstance(review_row.get("approved_snapshot_sha256"), str)
                    else None
                ),
                "lockedAt": (
                    review_row["locked_at"].isoformat()
                    if isinstance(review_row.get("locked_at"), datetime)
                    else None
                ),
            },
            "run": {
                "projectId": str(run_row["project_id"]),
                "documentId": str(run_row["document_id"]),
                "inputTranscriptionRunId": str(run_row["input_transcription_run_id"]),
                "inputLayoutRunId": (
                    str(run_row["input_layout_run_id"])
                    if isinstance(run_row.get("input_layout_run_id"), str)
                    else None
                ),
                "runKind": str(run_row["run_kind"]),
                "policySnapshotHash": str(run_row["policy_snapshot_hash"]),
                "policyId": (
                    str(run_row["policy_id"])
                    if isinstance(run_row.get("policy_id"), str)
                    else None
                ),
                "policyFamilyId": (
                    str(run_row["policy_family_id"])
                    if isinstance(run_row.get("policy_family_id"), str)
                    else None
                ),
                "policyVersion": (
                    str(run_row["policy_version"])
                    if isinstance(run_row.get("policy_version"), str)
                    else None
                ),
                "runStatus": str(run_row["status"]),
                "runCreatedAt": (
                    run_row["created_at"].isoformat()
                    if isinstance(run_row.get("created_at"), datetime)
                    else None
                ),
                "runStartedAt": (
                    run_row["started_at"].isoformat()
                    if isinstance(run_row.get("started_at"), datetime)
                    else None
                ),
                "runFinishedAt": (
                    run_row["finished_at"].isoformat()
                    if isinstance(run_row.get("finished_at"), datetime)
                    else None
                ),
            },
            "runOutput": {
                "status": str(run_output_row["status"]),
                "outputManifestKey": (
                    str(run_output_row["output_manifest_key"])
                    if isinstance(run_output_row.get("output_manifest_key"), str)
                    else None
                ),
                "outputManifestSha256": (
                    str(run_output_row["output_manifest_sha256"])
                    if isinstance(run_output_row.get("output_manifest_sha256"), str)
                    else None
                ),
                "pageCount": int(run_output_row.get("page_count") or 0),
            },
            "findings": [
                {
                    "id": str(item["id"]),
                    "pageId": str(item["page_id"]),
                    "pageIndex": int(item["page_index"]),
                    "lineId": (
                        str(item["line_id"])
                        if isinstance(item.get("line_id"), str)
                        else None
                    ),
                    "category": str(item["category"]),
                    "spanStart": (
                        int(item["span_start"])
                        if isinstance(item.get("span_start"), int)
                        else None
                    ),
                    "spanEnd": (
                        int(item["span_end"])
                        if isinstance(item.get("span_end"), int)
                        else None
                    ),
                    "spanBasisKind": (
                        str(item["span_basis_kind"])
                        if isinstance(item.get("span_basis_kind"), str)
                        else None
                    ),
                    "spanBasisRef": (
                        str(item["span_basis_ref"])
                        if isinstance(item.get("span_basis_ref"), str)
                        else None
                    ),
                    "tokenRefsJson": (
                        [
                            dict(entry)
                            for entry in item["token_refs_json"]
                            if isinstance(entry, Mapping)
                        ]
                        if isinstance(item.get("token_refs_json"), list)
                        else None
                    ),
                    "bboxRefs": (
                        dict(item["bbox_refs"])
                        if isinstance(item.get("bbox_refs"), Mapping)
                        else {}
                    ),
                    "confidence": (
                        float(item["confidence"])
                        if isinstance(item.get("confidence"), (int, float))
                        else None
                    ),
                    "basisPrimary": (
                        str(item["basis_primary"])
                        if isinstance(item.get("basis_primary"), str)
                        else None
                    ),
                    "basisSecondaryJson": (
                        dict(item["basis_secondary_json"])
                        if isinstance(item.get("basis_secondary_json"), Mapping)
                        else None
                    ),
                    "decisionStatus": str(item["decision_status"]),
                    "actionType": (
                        str(item["action_type"])
                        if isinstance(item.get("action_type"), str)
                        else "MASK"
                    ),
                    "areaMaskId": (
                        str(item["area_mask_id"])
                        if isinstance(item.get("area_mask_id"), str)
                        else None
                    ),
                    "decisionBy": (
                        str(item["decision_by"])
                        if isinstance(item.get("decision_by"), str)
                        else None
                    ),
                    "decisionAt": (
                        item["decision_at"].isoformat()
                        if isinstance(item.get("decision_at"), datetime)
                        else None
                    ),
                    "decisionEtag": str(item["decision_etag"]),
                    "updatedAt": (
                        item["updated_at"].isoformat()
                        if isinstance(item.get("updated_at"), datetime)
                        else None
                    ),
                }
                for item in finding_rows
            ],
            "areaMasks": [
                {
                    "id": str(item["id"]),
                    "pageId": str(item["page_id"]),
                    "versionEtag": str(item["version_etag"]),
                    "supersedesAreaMaskId": (
                        str(item["supersedes_area_mask_id"])
                        if isinstance(item.get("supersedes_area_mask_id"), str)
                        else None
                    ),
                    "supersededByAreaMaskId": (
                        str(item["superseded_by_area_mask_id"])
                        if isinstance(item.get("superseded_by_area_mask_id"), str)
                        else None
                    ),
                }
                for item in mask_rows
            ],
            "pageReviews": [
                {
                    "pageId": str(item["page_id"]),
                    "pageIndex": int(item["page_index"]),
                    "reviewStatus": str(item["review_status"]),
                    "reviewEtag": str(item["review_etag"]),
                    "firstReviewedBy": (
                        str(item["first_reviewed_by"])
                        if isinstance(item.get("first_reviewed_by"), str)
                        else None
                    ),
                    "firstReviewedAt": (
                        item["first_reviewed_at"].isoformat()
                        if isinstance(item.get("first_reviewed_at"), datetime)
                        else None
                    ),
                    "requiresSecondReview": bool(item.get("requires_second_review", False)),
                    "secondReviewStatus": str(item["second_review_status"]),
                    "secondReviewedBy": (
                        str(item["second_reviewed_by"])
                        if isinstance(item.get("second_reviewed_by"), str)
                        else None
                    ),
                    "secondReviewedAt": (
                        item["second_reviewed_at"].isoformat()
                        if isinstance(item.get("second_reviewed_at"), datetime)
                        else None
                    ),
                    "updatedAt": (
                        item["updated_at"].isoformat()
                        if isinstance(item.get("updated_at"), datetime)
                        else None
                    ),
                }
                for item in page_review_rows
            ],
            "outputs": [
                {
                    "pageId": str(item["page_id"]),
                    "pageIndex": int(item["page_index"]),
                    "status": str(item["status"]),
                    "safeguardedPreviewKey": (
                        str(item["safeguarded_preview_key"])
                        if isinstance(item.get("safeguarded_preview_key"), str)
                        else None
                    ),
                    "previewSha256": (
                        str(item["preview_sha256"])
                        if isinstance(item.get("preview_sha256"), str)
                        else None
                    ),
                    "generatedAt": (
                        item["generated_at"].isoformat()
                        if isinstance(item.get("generated_at"), datetime)
                        else None
                    ),
                }
                for item in output_rows
            ],
        }
        snapshot_bytes = json.dumps(
            snapshot_payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        snapshot_sha256 = hashlib.sha256(snapshot_bytes).hexdigest()
        return snapshot_bytes, snapshot_sha256

    def _refresh_redaction_run_output_status(
        self,
        *,
        cursor: psycopg.Cursor,
        run_id: str,
    ) -> None:
        cursor.execute(
            """
            SELECT
              rro.status,
              rro.started_at,
              rr.project_id,
              rr.document_id,
              rrv.approved_snapshot_sha256,
              rrv.locked_at
            FROM redaction_run_outputs AS rro
            INNER JOIN redaction_runs AS rr
              ON rr.id = rro.run_id
            LEFT JOIN redaction_run_reviews AS rrv
              ON rrv.run_id = rr.id
            WHERE rro.run_id = %(run_id)s
            LIMIT 1
            FOR UPDATE
            """,
            {"run_id": run_id},
        )
        run_output_row = cursor.fetchone()
        if run_output_row is None:
            return
        previous_status = self._assert_redaction_output_status(str(run_output_row["status"]))
        previous_started_at = run_output_row.get("started_at")
        project_id = str(run_output_row["project_id"])
        document_id = str(run_output_row["document_id"])
        approved_snapshot_sha256 = (
            str(run_output_row["approved_snapshot_sha256"])
            if isinstance(run_output_row.get("approved_snapshot_sha256"), str)
            and str(run_output_row["approved_snapshot_sha256"]).strip()
            else None
        )
        locked_at = (
            run_output_row.get("locked_at")
            if isinstance(run_output_row.get("locked_at"), datetime)
            else None
        )

        cursor.execute(
            """
            SELECT
              ro.page_id,
              ro.status,
              ro.safeguarded_preview_key,
              ro.failure_reason,
              ro.preview_sha256
            FROM redaction_outputs AS ro
            INNER JOIN pages AS p
              ON p.id = ro.page_id
            WHERE ro.run_id = %(run_id)s
            ORDER BY p.page_index ASC, ro.page_id ASC
            """,
            {"run_id": run_id},
        )
        output_rows = cursor.fetchall()
        total_count = len(output_rows)
        ready_count = 0
        failed_count = 0
        canceled_count = 0
        ready_manifest_rows: list[tuple[str, str]] = []
        failure_reasons: list[str] = []
        for row in output_rows:
            status = self._assert_redaction_output_status(str(row["status"]))
            preview_sha256 = (
                str(row["preview_sha256"])
                if isinstance(row.get("preview_sha256"), str) and str(row["preview_sha256"]).strip()
                else None
            )
            if status == "READY":
                ready_count += 1
                if preview_sha256 is not None and isinstance(row.get("page_id"), str):
                    page_id = str(row["page_id"])
                    ready_manifest_rows.append((page_id, preview_sha256))
            elif status == "FAILED":
                failed_count += 1
                if isinstance(row.get("failure_reason"), str) and str(row["failure_reason"]).strip():
                    failure_reasons.append(str(row["failure_reason"]).strip())
            elif status == "CANCELED":
                canceled_count += 1
        next_status: RedactionOutputStatus = "PENDING"
        if failed_count > 0:
            next_status = "FAILED"
        elif total_count > 0 and ready_count >= total_count:
            next_status = "READY"
        elif total_count > 0 and canceled_count >= total_count:
            next_status = "CANCELED"

        output_manifest_key: str | None = None
        output_manifest_sha256: str | None = None
        if (
            next_status == "READY"
            and ready_manifest_rows
            and len(ready_manifest_rows) == total_count
        ):
            approved_snapshot_payload: dict[str, object] | None = None
            if approved_snapshot_sha256 is not None and locked_at is not None:
                snapshot_bytes, snapshot_sha256 = self._build_redaction_approval_snapshot_bytes(
                    cursor=cursor,
                    run_id=run_id,
                    captured_at=locked_at,
                )
                if snapshot_sha256 != approved_snapshot_sha256:
                    raise DocumentStoreUnavailableError(
                        "Approved snapshot hash changed unexpectedly."
                    )
                try:
                    parsed_snapshot = json.loads(snapshot_bytes.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise DocumentStoreUnavailableError(
                        "Approved snapshot artifact payload is invalid JSON."
                    ) from error
                if not isinstance(parsed_snapshot, dict):
                    raise DocumentStoreUnavailableError("Approved snapshot payload is invalid.")
                approved_snapshot_payload = parsed_snapshot

            output_manifest_sha256 = canonical_preview_manifest_sha256(
                run_id=run_id,
                page_rows=ready_manifest_rows,
                approved_snapshot_sha256=approved_snapshot_sha256,
                approved_snapshot_payload=approved_snapshot_payload,
            )
            derived_prefix = self._settings.storage_controlled_derived_prefix.strip("/ ")
            output_manifest_key = (
                f"{derived_prefix}/{project_id}/{document_id}/redaction/{run_id}/output-manifest/"
                f"{output_manifest_sha256}.json"
            )
        failure_reason: str | None = None
        if next_status == "FAILED" and failure_reasons:
            failure_reason = failure_reasons[0][:600]

        started_at: datetime | None
        if next_status == "PENDING":
            if previous_status == "PENDING" and isinstance(previous_started_at, datetime):
                started_at = previous_started_at
            else:
                started_at = datetime.now(timezone.utc)
        elif isinstance(previous_started_at, datetime):
            started_at = previous_started_at
        else:
            started_at = datetime.now(timezone.utc)

        cursor.execute(
            """
            UPDATE redaction_run_outputs
            SET
              status = %(status)s,
              output_manifest_key = %(output_manifest_key)s,
              output_manifest_sha256 = %(output_manifest_sha256)s,
              page_count = %(page_count)s,
              started_at = %(started_at)s,
              generated_at = CASE
                WHEN %(status)s = 'READY' THEN NOW()
                ELSE NULL
              END,
              failure_reason = %(failure_reason)s,
              updated_at = NOW()
            WHERE run_id = %(run_id)s
            """,
            {
                "run_id": run_id,
                "status": next_status,
                "output_manifest_key": output_manifest_key,
                "output_manifest_sha256": output_manifest_sha256,
                "page_count": total_count,
                "started_at": started_at,
                "failure_reason": failure_reason,
            },
        )

        if previous_status != next_status:
            self._append_redaction_run_output_event(
                cursor=cursor,
                run_id=run_id,
                from_status=previous_status,
                to_status=next_status,
                reason=failure_reason,
            )

    def _refresh_redaction_page_second_review_requirement(
        self,
        *,
        cursor: psycopg.Cursor,
        run_id: str,
        page_id: str,
        actor_user_id: str,
    ) -> None:
        cursor.execute(
            """
            SELECT
              run_id,
              page_id,
              review_status,
              review_etag,
              first_reviewed_by,
              first_reviewed_at,
              requires_second_review,
              second_review_status,
              second_reviewed_by,
              second_reviewed_at,
              updated_at
            FROM redaction_page_reviews
            WHERE run_id = %(run_id)s
              AND page_id = %(page_id)s
            LIMIT 1
            FOR UPDATE
            """,
            {"run_id": run_id, "page_id": page_id},
        )
        row = cursor.fetchone()
        if row is None:
            return
        current_review = self._as_redaction_page_review_record(row)

        cursor.execute(
            """
            SELECT
              id,
              override_risk_reason_codes_json
            FROM redaction_findings
            WHERE run_id = %(run_id)s
              AND page_id = %(page_id)s
              AND decision_status IN ('OVERRIDDEN', 'FALSE_POSITIVE')
              AND override_risk_classification = 'HIGH'
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            {"run_id": run_id, "page_id": page_id},
        )
        high_risk_row = cursor.fetchone()
        requires_second_review = high_risk_row is not None

        next_second_review_status: RedactionSecondReviewStatus
        next_second_reviewed_by: str | None
        next_second_reviewed_at: datetime | None
        if requires_second_review:
            has_valid_second_reviewer = (
                isinstance(current_review.first_reviewed_by, str)
                and bool(current_review.first_reviewed_by.strip())
                and isinstance(current_review.second_reviewed_by, str)
                and bool(current_review.second_reviewed_by.strip())
                and current_review.second_reviewed_by != current_review.first_reviewed_by
            )
            if (
                current_review.second_review_status in {"APPROVED", "CHANGES_REQUESTED"}
                and has_valid_second_reviewer
            ):
                next_second_review_status = current_review.second_review_status
                next_second_reviewed_by = current_review.second_reviewed_by
                next_second_reviewed_at = current_review.second_reviewed_at
            else:
                next_second_review_status = "PENDING"
                next_second_reviewed_by = None
                next_second_reviewed_at = None
        else:
            next_second_review_status = "NOT_REQUIRED"
            next_second_reviewed_by = None
            next_second_reviewed_at = None

        if (
            current_review.requires_second_review == requires_second_review
            and current_review.second_review_status == next_second_review_status
            and current_review.second_reviewed_by == next_second_reviewed_by
            and current_review.second_reviewed_at == next_second_reviewed_at
        ):
            return

        now = datetime.now(timezone.utc)
        next_review_etag = self._compute_redaction_etag(
            run_id,
            page_id,
            current_review.review_status,
            "SECOND_REVIEW_REQUIREMENT_REFRESH",
            str(requires_second_review),
            str(next_second_review_status),
            now.isoformat(),
        )
        cursor.execute(
            """
            UPDATE redaction_page_reviews
            SET
              requires_second_review = %(requires_second_review)s,
              second_review_status = %(second_review_status)s,
              second_reviewed_by = %(second_reviewed_by)s,
              second_reviewed_at = %(second_reviewed_at)s,
              review_etag = %(review_etag)s,
              updated_at = NOW()
            WHERE run_id = %(run_id)s
              AND page_id = %(page_id)s
            """,
            {
                "run_id": run_id,
                "page_id": page_id,
                "requires_second_review": requires_second_review,
                "second_review_status": next_second_review_status,
                "second_reviewed_by": next_second_reviewed_by,
                "second_reviewed_at": next_second_reviewed_at,
                "review_etag": next_review_etag,
            },
        )

        if requires_second_review and not current_review.requires_second_review:
            reason_codes = (
                [
                    str(item)
                    for item in (high_risk_row.get("override_risk_reason_codes_json") or [])
                    if isinstance(item, str)
                ]
                if isinstance(high_risk_row, Mapping)
                else []
            )
            reason = (
                "Second review required due to high-risk override conditions"
                + (f": {', '.join(reason_codes)}" if reason_codes else ".")
            )
            cursor.execute(
                """
                INSERT INTO redaction_page_review_events (
                  id,
                  run_id,
                  page_id,
                  event_type,
                  actor_user_id,
                  reason,
                  created_at
                )
                VALUES (
                  %(id)s,
                  %(run_id)s,
                  %(page_id)s,
                  'SECOND_REVIEW_REQUIRED',
                  %(actor_user_id)s,
                  %(reason)s,
                  %(created_at)s
                )
                """,
                {
                    "id": str(uuid4()),
                    "run_id": run_id,
                    "page_id": page_id,
                    "actor_user_id": actor_user_id,
                    "reason": reason,
                    "created_at": now,
                },
            )

    def get_redaction_projection(
        self,
        *,
        project_id: str,
        document_id: str,
    ) -> DocumentRedactionProjectionRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          document_id,
                          project_id,
                          active_redaction_run_id,
                          active_transcription_run_id,
                          active_layout_run_id,
                          active_policy_snapshot_id,
                          updated_at
                        FROM document_redaction_projections
                        WHERE project_id = %(project_id)s
                          AND document_id = %(document_id)s
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Redaction projection lookup failed."
            ) from error
        if row is None:
            return None
        return self._as_redaction_projection_record(row)

    def list_redaction_runs(
        self,
        *,
        project_id: str,
        document_id: str,
        cursor: int = 0,
        page_size: int = 50,
    ) -> tuple[list[RedactionRunRecord], int | None]:
        self.ensure_schema()
        safe_cursor = max(0, cursor)
        safe_page_size = max(1, min(page_size, 200))
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as db_cursor:
                    db_cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          document_id,
                          input_transcription_run_id,
                          input_layout_run_id,
                          run_kind,
                          supersedes_redaction_run_id,
                          superseded_by_redaction_run_id,
                          policy_snapshot_id,
                          policy_snapshot_json,
                          policy_snapshot_hash,
                          policy_id,
                          policy_family_id,
                          policy_version,
                          detectors_version,
                          status,
                          created_by,
                          created_at,
                          started_at,
                          finished_at,
                          failure_reason
                        FROM redaction_runs
                        WHERE project_id = %(project_id)s
                          AND document_id = %(document_id)s
                        ORDER BY created_at DESC, id DESC
                        OFFSET %(cursor)s
                        LIMIT %(limit)s
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "cursor": safe_cursor,
                            "limit": safe_page_size + 1,
                        },
                    )
                    rows = db_cursor.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Redaction run listing failed.") from error
        items = [self._as_redaction_run_record(row) for row in rows[:safe_page_size]]
        next_cursor = (
            safe_cursor + safe_page_size if len(rows) > safe_page_size else None
        )
        return items, next_cursor

    def get_redaction_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> RedactionRunRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          document_id,
                          input_transcription_run_id,
                          input_layout_run_id,
                          run_kind,
                          supersedes_redaction_run_id,
                          superseded_by_redaction_run_id,
                          policy_snapshot_id,
                          policy_snapshot_json,
                          policy_snapshot_hash,
                          policy_id,
                          policy_family_id,
                          policy_version,
                          detectors_version,
                          status,
                          created_by,
                          created_at,
                          started_at,
                          finished_at,
                          failure_reason
                        FROM redaction_runs
                        WHERE project_id = %(project_id)s
                          AND document_id = %(document_id)s
                          AND id = %(run_id)s
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
            raise DocumentStoreUnavailableError("Redaction run lookup failed.") from error
        if row is None:
            return None
        return self._as_redaction_run_record(row)

    def get_active_redaction_run(
        self,
        *,
        project_id: str,
        document_id: str,
    ) -> RedactionRunRecord | None:
        projection = self.get_redaction_projection(
            project_id=project_id,
            document_id=document_id,
        )
        if projection is None or projection.active_redaction_run_id is None:
            return None
        return self.get_redaction_run(
            project_id=project_id,
            document_id=document_id,
            run_id=projection.active_redaction_run_id,
        )

    def create_redaction_run(
        self,
        *,
        project_id: str,
        document_id: str,
        created_by: str,
        input_transcription_run_id: str | None = None,
        input_layout_run_id: str | None = None,
        run_kind: RedactionRunKind = "BASELINE",
        supersedes_redaction_run_id: str | None = None,
        detectors_version: str = "phase-5.0-scaffold",
        policy_snapshot_id: str | None = None,
        policy_snapshot_json: Mapping[str, object] | None = None,
        policy_snapshot_hash: str | None = None,
        policy_id: str | None = None,
        policy_family_id: str | None = None,
        policy_version: str | None = None,
    ) -> RedactionRunRecord:
        self.ensure_schema()
        now = datetime.now(timezone.utc)
        run_id = str(uuid4())
        normalized_detectors_version = detectors_version.strip() or "phase-5.0-scaffold"
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          d.id AS document_id,
                          d.project_id,
                          p.baseline_policy_snapshot_id,
                          b.rules_json AS policy_snapshot_json,
                          b.snapshot_hash AS policy_snapshot_hash
                        FROM documents AS d
                        INNER JOIN projects AS p
                          ON p.id = d.project_id
                        LEFT JOIN baseline_policy_snapshots AS b
                          ON b.id = p.baseline_policy_snapshot_id
                        WHERE d.project_id = %(project_id)s
                          AND d.id = %(document_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                        },
                    )
                    document_row = cursor.fetchone()
                    if document_row is None:
                        raise DocumentNotFoundError("Document not found.")

                    resolved_transcription_run_id: str | None = (
                        input_transcription_run_id.strip()
                        if isinstance(input_transcription_run_id, str)
                        and input_transcription_run_id.strip()
                        else None
                    )
                    if resolved_transcription_run_id is None:
                        cursor.execute(
                            """
                            SELECT active_transcription_run_id
                            FROM document_transcription_projections
                            WHERE project_id = %(project_id)s
                              AND document_id = %(document_id)s
                            LIMIT 1
                            """,
                            {
                                "project_id": project_id,
                                "document_id": document_id,
                            },
                        )
                        projection_row = cursor.fetchone()
                        if (
                            projection_row is not None
                            and isinstance(
                                projection_row.get("active_transcription_run_id"),
                                str,
                            )
                        ):
                            resolved_transcription_run_id = str(
                                projection_row["active_transcription_run_id"]
                            )
                    if resolved_transcription_run_id is None:
                        cursor.execute(
                            """
                            SELECT id
                            FROM transcription_runs
                            WHERE project_id = %(project_id)s
                              AND document_id = %(document_id)s
                              AND status = 'SUCCEEDED'
                            ORDER BY created_at DESC, id DESC
                            LIMIT 1
                            """,
                            {
                                "project_id": project_id,
                                "document_id": document_id,
                            },
                        )
                        row = cursor.fetchone()
                        if row is not None:
                            resolved_transcription_run_id = str(row["id"])
                    if resolved_transcription_run_id is None:
                        raise DocumentRedactionRunConflictError(
                            "Redaction run creation requires a transcription basis."
                        )

                    cursor.execute(
                        """
                        SELECT
                          id,
                          input_layout_run_id,
                          status
                        FROM transcription_runs
                        WHERE project_id = %(project_id)s
                          AND document_id = %(document_id)s
                          AND id = %(run_id)s
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": resolved_transcription_run_id,
                        },
                    )
                    transcription_row = cursor.fetchone()
                    if transcription_row is None:
                        raise DocumentRedactionRunConflictError(
                            "Input transcription run was not found."
                        )
                    transcription_status = self._assert_transcription_run_status(
                        str(transcription_row["status"])
                    )
                    if transcription_status != "SUCCEEDED":
                        raise DocumentRedactionRunConflictError(
                            "Input transcription run must be SUCCEEDED."
                        )

                    resolved_layout_run_id: str | None = (
                        input_layout_run_id.strip()
                        if isinstance(input_layout_run_id, str)
                        and input_layout_run_id.strip()
                        else (
                            str(transcription_row["input_layout_run_id"])
                            if isinstance(transcription_row.get("input_layout_run_id"), str)
                            else None
                        )
                    )

                    normalized_supersedes_run_id = (
                        supersedes_redaction_run_id.strip()
                        if isinstance(supersedes_redaction_run_id, str)
                        and supersedes_redaction_run_id.strip()
                        else None
                    )
                    if normalized_supersedes_run_id is not None:
                        cursor.execute(
                            """
                            SELECT id
                            FROM redaction_runs
                            WHERE id = %(run_id)s
                              AND project_id = %(project_id)s
                              AND document_id = %(document_id)s
                            LIMIT 1
                            """,
                            {
                                "run_id": normalized_supersedes_run_id,
                                "project_id": project_id,
                                "document_id": document_id,
                            },
                        )
                        if cursor.fetchone() is None:
                            raise DocumentRedactionRunConflictError(
                                "supersedesRedactionRunId was not found."
                            )

                    normalized_policy_snapshot_id = (
                        policy_snapshot_id.strip()
                        if isinstance(policy_snapshot_id, str)
                        and policy_snapshot_id.strip()
                        else None
                    )
                    normalized_policy_snapshot_hash = (
                        policy_snapshot_hash.strip()
                        if isinstance(policy_snapshot_hash, str)
                        and policy_snapshot_hash.strip()
                        else None
                    )
                    normalized_policy_snapshot_json = (
                        dict(policy_snapshot_json)
                        if isinstance(policy_snapshot_json, Mapping)
                        else None
                    )
                    has_explicit_policy_snapshot = any(
                        value is not None
                        for value in (
                            normalized_policy_snapshot_id,
                            normalized_policy_snapshot_hash,
                            normalized_policy_snapshot_json,
                        )
                    )
                    if has_explicit_policy_snapshot and (
                        normalized_policy_snapshot_id is None
                        or normalized_policy_snapshot_hash is None
                        or normalized_policy_snapshot_json is None
                    ):
                        raise DocumentRedactionRunConflictError(
                            "Policy rerun creation requires policy snapshot id, payload, and hash."
                        )

                    resolved_policy_snapshot_id: str
                    resolved_policy_snapshot_hash: str
                    resolved_policy_snapshot_json: dict[str, object]
                    if has_explicit_policy_snapshot:
                        assert normalized_policy_snapshot_id is not None
                        assert normalized_policy_snapshot_hash is not None
                        assert normalized_policy_snapshot_json is not None
                        resolved_policy_snapshot_id = normalized_policy_snapshot_id
                        resolved_policy_snapshot_hash = normalized_policy_snapshot_hash
                        resolved_policy_snapshot_json = normalized_policy_snapshot_json
                    else:
                        baseline_snapshot_id = (
                            str(document_row["baseline_policy_snapshot_id"])
                            if isinstance(document_row.get("baseline_policy_snapshot_id"), str)
                            else None
                        )
                        baseline_snapshot_hash = (
                            str(document_row["policy_snapshot_hash"])
                            if isinstance(document_row.get("policy_snapshot_hash"), str)
                            else None
                        )
                        baseline_snapshot_json = (
                            dict(document_row["policy_snapshot_json"])
                            if isinstance(document_row.get("policy_snapshot_json"), Mapping)
                            else None
                        )
                        if (
                            baseline_snapshot_id is None
                            or baseline_snapshot_hash is None
                            or baseline_snapshot_json is None
                        ):
                            raise DocumentRedactionRunConflictError(
                                "Redaction run creation requires a baseline policy snapshot."
                            )
                        resolved_policy_snapshot_id = baseline_snapshot_id
                        resolved_policy_snapshot_hash = baseline_snapshot_hash
                        resolved_policy_snapshot_json = baseline_snapshot_json

                    normalized_policy_id = (
                        policy_id.strip()
                        if isinstance(policy_id, str) and policy_id.strip()
                        else None
                    )
                    normalized_policy_family_id = (
                        policy_family_id.strip()
                        if isinstance(policy_family_id, str) and policy_family_id.strip()
                        else None
                    )
                    normalized_policy_version = (
                        policy_version.strip()
                        if isinstance(policy_version, str) and policy_version.strip()
                        else None
                    )

                    cursor.execute(
                        """
                        INSERT INTO redaction_runs (
                          id,
                          project_id,
                          document_id,
                          input_transcription_run_id,
                          input_layout_run_id,
                          run_kind,
                          supersedes_redaction_run_id,
                          superseded_by_redaction_run_id,
                          policy_snapshot_id,
                          policy_snapshot_json,
                          policy_snapshot_hash,
                          policy_id,
                          policy_family_id,
                          policy_version,
                          detectors_version,
                          status,
                          created_by,
                          created_at,
                          started_at,
                          finished_at,
                          failure_reason
                        )
                        VALUES (
                          %(id)s,
                          %(project_id)s,
                          %(document_id)s,
                          %(input_transcription_run_id)s,
                          %(input_layout_run_id)s,
                          %(run_kind)s,
                          %(supersedes_redaction_run_id)s,
                          NULL,
                          %(policy_snapshot_id)s,
                          %(policy_snapshot_json)s::jsonb,
                          %(policy_snapshot_hash)s,
                          %(policy_id)s,
                          %(policy_family_id)s,
                          %(policy_version)s,
                          %(detectors_version)s,
                          'SUCCEEDED',
                          %(created_by)s,
                          %(created_at)s,
                          %(started_at)s,
                          %(finished_at)s,
                          NULL
                        )
                        """,
                        {
                            "id": run_id,
                            "project_id": project_id,
                            "document_id": document_id,
                            "input_transcription_run_id": resolved_transcription_run_id,
                            "input_layout_run_id": resolved_layout_run_id,
                            "run_kind": run_kind,
                            "supersedes_redaction_run_id": normalized_supersedes_run_id,
                            "policy_snapshot_id": resolved_policy_snapshot_id,
                            "policy_snapshot_json": json.dumps(
                                resolved_policy_snapshot_json,
                                ensure_ascii=True,
                                separators=(",", ":"),
                                sort_keys=True,
                            ),
                            "policy_snapshot_hash": resolved_policy_snapshot_hash,
                            "policy_id": normalized_policy_id,
                            "policy_family_id": normalized_policy_family_id,
                            "policy_version": normalized_policy_version,
                            "detectors_version": normalized_detectors_version,
                            "created_by": created_by,
                            "created_at": now,
                            "started_at": now,
                            "finished_at": now,
                        },
                    )
                    if normalized_supersedes_run_id is not None:
                        cursor.execute(
                            """
                            UPDATE redaction_runs
                            SET superseded_by_redaction_run_id = %(run_id)s
                            WHERE id = %(supersedes_run_id)s
                              AND superseded_by_redaction_run_id IS NULL
                            """,
                            {
                                "run_id": run_id,
                                "supersedes_run_id": normalized_supersedes_run_id,
                            },
                        )

                    cursor.execute(
                        """
                        INSERT INTO redaction_run_reviews (
                          run_id,
                          review_status,
                          review_started_by,
                          review_started_at,
                          approved_by,
                          approved_at,
                          approved_snapshot_key,
                          approved_snapshot_sha256,
                          locked_at,
                          updated_at
                        )
                        VALUES (
                          %(run_id)s,
                          'NOT_READY',
                          NULL,
                          NULL,
                          NULL,
                          NULL,
                          NULL,
                          NULL,
                          NULL,
                          NOW()
                        )
                        ON CONFLICT (run_id) DO NOTHING
                        """,
                        {"run_id": run_id},
                    )

                    cursor.execute(
                        """
                        SELECT id, page_index
                        FROM pages
                        WHERE document_id = %(document_id)s
                        ORDER BY page_index ASC, id ASC
                        """,
                        {"document_id": document_id},
                    )
                    page_rows = cursor.fetchall()
                    for page_row in page_rows:
                        page_id = str(page_row["id"])
                        review_etag = self._compute_redaction_etag(
                            run_id,
                            page_id,
                            "NOT_STARTED",
                            now.isoformat(),
                        )
                        cursor.execute(
                            """
                            INSERT INTO redaction_page_reviews (
                              run_id,
                              page_id,
                              review_status,
                              review_etag,
                              first_reviewed_by,
                              first_reviewed_at,
                              requires_second_review,
                              second_review_status,
                              second_reviewed_by,
                              second_reviewed_at,
                              updated_at
                            )
                            VALUES (
                              %(run_id)s,
                              %(page_id)s,
                              'NOT_STARTED',
                              %(review_etag)s,
                              NULL,
                              NULL,
                              FALSE,
                              'NOT_REQUIRED',
                              NULL,
                              NULL,
                              NOW()
                            )
                            ON CONFLICT (run_id, page_id) DO NOTHING
                            """,
                            {
                                "run_id": run_id,
                                "page_id": page_id,
                                "review_etag": review_etag,
                            },
                        )
                        cursor.execute(
                            """
                            INSERT INTO redaction_outputs (
                              run_id,
                              page_id,
                              status,
                              safeguarded_preview_key,
                              preview_sha256,
                              started_at,
                              generated_at,
                              canceled_by,
                              canceled_at,
                              failure_reason,
                              created_at,
                              updated_at
                            )
                            VALUES (
                              %(run_id)s,
                              %(page_id)s,
                              'PENDING',
                              NULL,
                              NULL,
                              NULL,
                              NULL,
                              NULL,
                              NULL,
                              NULL,
                              NOW(),
                              NOW()
                            )
                            ON CONFLICT (run_id, page_id) DO NOTHING
                            """,
                            {
                                "run_id": run_id,
                                "page_id": page_id,
                            },
                        )

                    cursor.execute(
                        """
                        INSERT INTO redaction_run_outputs (
                          run_id,
                          status,
                          output_manifest_key,
                          output_manifest_sha256,
                          page_count,
                          started_at,
                          generated_at,
                          canceled_by,
                          canceled_at,
                          failure_reason,
                          created_at,
                          updated_at
                        )
                        VALUES (
                          %(run_id)s,
                          'PENDING',
                          NULL,
                          NULL,
                          %(page_count)s,
                          NULL,
                          NULL,
                          NULL,
                          NULL,
                          NULL,
                          NOW(),
                          NOW()
                        )
                        ON CONFLICT (run_id) DO NOTHING
                        """,
                        {"run_id": run_id, "page_count": len(page_rows)},
                    )

                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          document_id,
                          input_transcription_run_id,
                          input_layout_run_id,
                          run_kind,
                          supersedes_redaction_run_id,
                          superseded_by_redaction_run_id,
                          policy_snapshot_id,
                          policy_snapshot_json,
                          policy_snapshot_hash,
                          policy_id,
                          policy_family_id,
                          policy_version,
                          detectors_version,
                          status,
                          created_by,
                          created_at,
                          started_at,
                          finished_at,
                          failure_reason
                        FROM redaction_runs
                        WHERE id = %(run_id)s
                        LIMIT 1
                        """,
                        {"run_id": run_id},
                    )
                    created_row = cursor.fetchone()
                connection.commit()
        except (
            DocumentNotFoundError,
            DocumentRedactionRunConflictError,
        ):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Redaction run creation failed.") from error
        if created_row is None:
            raise DocumentStoreUnavailableError("Redaction run creation failed.")
        return self._as_redaction_run_record(created_row)

    def replace_redaction_findings(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        findings: Sequence[dict[str, object]],
    ) -> list[RedactionFindingRecord]:
        self.ensure_schema()
        now = datetime.now(timezone.utc)
        normalized_rows: list[dict[str, object]] = []

        for index, finding in enumerate(findings):
            raw_page_id = finding.get("page_id")
            if not isinstance(raw_page_id, str) or not raw_page_id.strip():
                raise DocumentStoreUnavailableError(
                    f"Redaction finding row {index} requires page_id."
                )
            page_id = raw_page_id.strip()

            raw_line_id = finding.get("line_id")
            line_id = (
                raw_line_id.strip()
                if isinstance(raw_line_id, str) and raw_line_id.strip()
                else None
            )

            raw_category = finding.get("category")
            if not isinstance(raw_category, str) or not raw_category.strip():
                raise DocumentStoreUnavailableError(
                    f"Redaction finding row {index} requires category."
                )
            category = raw_category.strip()

            span_start = (
                int(finding["span_start"])
                if isinstance(finding.get("span_start"), int)
                else None
            )
            span_end = (
                int(finding["span_end"])
                if isinstance(finding.get("span_end"), int)
                else None
            )
            if (span_start is None) ^ (span_end is None):
                raise DocumentStoreUnavailableError(
                    f"Redaction finding row {index} must provide both span_start and span_end or neither."
                )
            if span_start is not None and span_end is not None and span_end <= span_start:
                raise DocumentStoreUnavailableError(
                    f"Redaction finding row {index} has invalid span range."
                )

            span_basis_kind = self._assert_redaction_finding_span_basis_kind(
                str(finding.get("span_basis_kind") or "NONE").strip().upper()
            )
            span_basis_ref = (
                str(finding["span_basis_ref"]).strip()
                if isinstance(finding.get("span_basis_ref"), str)
                and str(finding["span_basis_ref"]).strip()
                else None
            )

            confidence = (
                float(finding["confidence"])
                if isinstance(finding.get("confidence"), (int, float))
                else None
            )
            if confidence is not None and (confidence < 0.0 or confidence > 1.0):
                raise DocumentStoreUnavailableError(
                    f"Redaction finding row {index} confidence must be between 0 and 1."
                )

            basis_primary = self._assert_redaction_finding_basis_primary(
                str(finding.get("basis_primary") or "HEURISTIC").strip().upper()
            )

            basis_secondary_json = (
                dict(finding["basis_secondary_json"])
                if isinstance(finding.get("basis_secondary_json"), Mapping)
                else None
            )

            assist_explanation_key = (
                str(finding["assist_explanation_key"]).strip()
                if isinstance(finding.get("assist_explanation_key"), str)
                and str(finding["assist_explanation_key"]).strip()
                else None
            )
            assist_explanation_sha256 = (
                str(finding["assist_explanation_sha256"]).strip()
                if isinstance(finding.get("assist_explanation_sha256"), str)
                and str(finding["assist_explanation_sha256"]).strip()
                else None
            )

            raw_bbox_refs = (
                dict(finding["bbox_refs"])
                if isinstance(finding.get("bbox_refs"), Mapping)
                else {}
            )
            raw_token_refs_json = (
                [
                    dict(item)
                    for item in finding["token_refs_json"]
                    if isinstance(item, Mapping)
                ]
                if isinstance(finding.get("token_refs_json"), Sequence)
                and not isinstance(finding.get("token_refs_json"), (str, bytes))
                else None
            )

            area_mask_id = (
                str(finding["area_mask_id"]).strip()
                if isinstance(finding.get("area_mask_id"), str)
                and str(finding["area_mask_id"]).strip()
                else None
            )
            action_type = self._assert_redaction_decision_action_type(
                str(finding.get("action_type") or "MASK").strip().upper()
            )
            decision_status = self._assert_redaction_decision_status(
                str(finding.get("decision_status") or "NEEDS_REVIEW").strip().upper()
            )
            decision_reason = (
                str(finding["decision_reason"]).strip()
                if isinstance(finding.get("decision_reason"), str)
                and str(finding["decision_reason"]).strip()
                else None
            )
            if decision_reason is not None and len(decision_reason) > 600:
                raise DocumentStoreUnavailableError(
                    f"Redaction finding row {index} decision_reason must be 600 characters or fewer."
                )

            normalized_rows.append(
                {
                    "page_id": page_id,
                    "line_id": line_id,
                    "category": category,
                    "span_start": span_start,
                    "span_end": span_end,
                    "span_basis_kind": span_basis_kind,
                    "span_basis_ref": span_basis_ref,
                    "confidence": confidence,
                    "basis_primary": basis_primary,
                    "basis_secondary_json": basis_secondary_json,
                    "assist_explanation_key": assist_explanation_key,
                    "assist_explanation_sha256": assist_explanation_sha256,
                    "raw_bbox_refs": raw_bbox_refs,
                    "raw_token_refs_json": raw_token_refs_json,
                    "area_mask_id": area_mask_id,
                    "action_type": action_type,
                    "decision_status": decision_status,
                    "decision_reason": decision_reason,
                }
            )

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          rr.id,
                          rr.input_transcription_run_id,
                          rr.created_by,
                          rr.policy_snapshot_json
                        FROM redaction_runs AS rr
                        WHERE rr.id = %(run_id)s
                          AND rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "run_id": run_id,
                            "project_id": project_id,
                            "document_id": document_id,
                        },
                    )
                    run_row = cursor.fetchone()
                    if run_row is None:
                        raise DocumentNotFoundError("Redaction run not found.")
                    input_transcription_run_id = str(run_row["input_transcription_run_id"])
                    run_created_by = str(run_row["created_by"])
                    policy_snapshot_json = run_row.get("policy_snapshot_json")

                    cursor.execute(
                        """
                        SELECT p.id, p.width, p.height
                        FROM pages AS p
                        WHERE p.document_id = %(document_id)s
                        """,
                        {"document_id": document_id},
                    )
                    page_dimension_rows = cursor.fetchall()
                    page_dimensions: dict[str, tuple[int, int]] = {
                        str(item["id"]): (
                            int(item["width"]),
                            int(item["height"]),
                        )
                        for item in page_dimension_rows
                        if isinstance(item.get("id"), str)
                        and isinstance(item.get("width"), int)
                        and isinstance(item.get("height"), int)
                    }

                    cursor.execute(
                        """
                        SELECT t.page_id, t.token_id
                        FROM token_transcription_results AS t
                        WHERE t.run_id = %(run_id)s
                        """,
                        {"run_id": input_transcription_run_id},
                    )
                    token_rows = cursor.fetchall()
                    valid_token_ids_by_page: dict[str, set[str]] = {}
                    for item in token_rows:
                        if not isinstance(item.get("page_id"), str) or not isinstance(
                            item.get("token_id"), str
                        ):
                            continue
                        valid_token_ids_by_page.setdefault(str(item["page_id"]), set()).add(
                            str(item["token_id"])
                        )

                    validated_rows: list[dict[str, object]] = []
                    for index, row in enumerate(normalized_rows):
                        page_id = str(row["page_id"])
                        page_dimensions_for_row = page_dimensions.get(page_id)
                        if page_dimensions_for_row is None:
                            raise DocumentStoreUnavailableError(
                                f"Redaction finding row {index} references unknown page_id."
                            )
                        page_width, page_height = page_dimensions_for_row
                        try:
                            token_refs_json, bbox_refs = normalize_token_refs_and_bbox_refs(
                                token_refs_json=(
                                    row["raw_token_refs_json"]
                                    if isinstance(row.get("raw_token_refs_json"), Sequence)
                                    and not isinstance(
                                        row.get("raw_token_refs_json"), (str, bytes)
                                    )
                                    else None
                                ),
                                bbox_refs=(
                                    row["raw_bbox_refs"]
                                    if isinstance(row.get("raw_bbox_refs"), Mapping)
                                    else {}
                                ),
                                page_width=page_width,
                                page_height=page_height,
                                valid_token_ids=valid_token_ids_by_page.get(page_id, set()),
                            )
                        except RedactionGeometryValidationError as error:
                            raise DocumentStoreUnavailableError(
                                f"Redaction finding row {index} geometry is invalid: {error}"
                            ) from error
                        validated_rows.append(
                            {
                                **row,
                                "bbox_refs": bbox_refs,
                                "token_refs_json": token_refs_json,
                            }
                        )

                    cursor.execute(
                        """
                        DELETE FROM redaction_decision_events
                        WHERE run_id = %(run_id)s
                        """,
                        {"run_id": run_id},
                    )

                    cursor.execute(
                        """
                        DELETE FROM redaction_findings
                        WHERE run_id = %(run_id)s
                        """,
                        {"run_id": run_id},
                    )

                    for row in validated_rows:
                        finding_id = str(uuid4())
                        decision_etag = self._compute_redaction_etag(
                            run_id,
                            str(row["page_id"]),
                            str(row.get("line_id") or ""),
                            str(row["category"]),
                            str(row.get("span_start") if row.get("span_start") is not None else ""),
                            str(row.get("span_end") if row.get("span_end") is not None else ""),
                            str(row["decision_status"]),
                            finding_id,
                            now.isoformat(),
                        )
                        decision_at = (
                            now
                            if str(row["decision_status"]) == "AUTO_APPLIED"
                            else None
                        )
                        override_risk_classification: (
                            RedactionOverrideRiskClassification | None
                        ) = None
                        override_risk_reason_codes: list[str] | None = None
                        if row["decision_status"] in {"OVERRIDDEN", "FALSE_POSITIVE"}:
                            (
                                override_risk_classification,
                                override_risk_reason_codes,
                            ) = self._derive_redaction_override_risk(
                                decision_status=str(row["decision_status"]),
                                area_mask_id=(
                                    str(row["area_mask_id"])
                                    if isinstance(row.get("area_mask_id"), str)
                                    else None
                                ),
                                category=str(row["category"]),
                                basis_secondary_json=(
                                    row["basis_secondary_json"]
                                    if isinstance(row.get("basis_secondary_json"), Mapping)
                                    else None
                                ),
                                policy_snapshot_json=policy_snapshot_json,
                            )
                        cursor.execute(
                            """
                            INSERT INTO redaction_findings (
                              id,
                              run_id,
                              page_id,
                              line_id,
                              category,
                              span_start,
                              span_end,
                              span_basis_kind,
                              span_basis_ref,
                              confidence,
                              basis_primary,
                              basis_secondary_json,
                              assist_explanation_key,
                              assist_explanation_sha256,
                              bbox_refs,
                              token_refs_json,
                              area_mask_id,
                              decision_status,
                              override_risk_classification,
                              override_risk_reason_codes_json,
                              decision_by,
                              decision_at,
                              decision_reason,
                              decision_etag,
                              updated_at,
                              created_at
                            )
                            VALUES (
                              %(id)s,
                              %(run_id)s,
                              %(page_id)s,
                              %(line_id)s,
                              %(category)s,
                              %(span_start)s,
                              %(span_end)s,
                              %(span_basis_kind)s,
                              %(span_basis_ref)s,
                              %(confidence)s,
                              %(basis_primary)s,
                              %(basis_secondary_json)s::jsonb,
                              %(assist_explanation_key)s,
                              %(assist_explanation_sha256)s,
                              %(bbox_refs)s::jsonb,
                              %(token_refs_json)s::jsonb,
                              %(area_mask_id)s,
                              %(decision_status)s,
                              %(override_risk_classification)s,
                              %(override_risk_reason_codes_json)s::jsonb,
                              NULL,
                              %(decision_at)s,
                              %(decision_reason)s,
                              %(decision_etag)s,
                              %(updated_at)s,
                              %(created_at)s
                            )
                            """,
                            {
                                "id": finding_id,
                                "run_id": run_id,
                                "page_id": row["page_id"],
                                "line_id": row.get("line_id"),
                                "category": row["category"],
                                "span_start": row.get("span_start"),
                                "span_end": row.get("span_end"),
                                "span_basis_kind": row["span_basis_kind"],
                                "span_basis_ref": row.get("span_basis_ref"),
                                "confidence": row.get("confidence"),
                                "basis_primary": row["basis_primary"],
                                "basis_secondary_json": json.dumps(
                                    row.get("basis_secondary_json"),
                                    ensure_ascii=True,
                                    separators=(",", ":"),
                                    sort_keys=True,
                                )
                                if row.get("basis_secondary_json") is not None
                                else None,
                                "assist_explanation_key": row.get("assist_explanation_key"),
                                "assist_explanation_sha256": row.get(
                                    "assist_explanation_sha256"
                                ),
                                "bbox_refs": json.dumps(
                                    row.get("bbox_refs", {}),
                                    ensure_ascii=True,
                                    separators=(",", ":"),
                                    sort_keys=True,
                                ),
                                "token_refs_json": json.dumps(
                                    row.get("token_refs_json"),
                                    ensure_ascii=True,
                                    separators=(",", ":"),
                                    sort_keys=True,
                                )
                                if row.get("token_refs_json") is not None
                                else None,
                                "area_mask_id": row.get("area_mask_id"),
                                "decision_status": row["decision_status"],
                                "override_risk_classification": (
                                    override_risk_classification
                                ),
                                "override_risk_reason_codes_json": (
                                    json.dumps(
                                        override_risk_reason_codes,
                                        ensure_ascii=True,
                                        separators=(",", ":"),
                                        sort_keys=True,
                                    )
                                    if override_risk_reason_codes is not None
                                    else None
                                ),
                                "decision_at": decision_at,
                                "decision_reason": row.get("decision_reason"),
                                "decision_etag": decision_etag,
                                "updated_at": now,
                                "created_at": now,
                            },
                        )
                        cursor.execute(
                            """
                            INSERT INTO redaction_decision_events (
                              id,
                              run_id,
                              page_id,
                              finding_id,
                              from_decision_status,
                              to_decision_status,
                              action_type,
                              area_mask_id,
                              actor_user_id,
                              reason,
                              created_at
                            )
                            VALUES (
                              %(id)s,
                              %(run_id)s,
                              %(page_id)s,
                              %(finding_id)s,
                              NULL,
                              %(to_decision_status)s,
                              %(action_type)s,
                              %(area_mask_id)s,
                              %(actor_user_id)s,
                              %(reason)s,
                              %(created_at)s
                            )
                            """,
                            {
                                "id": str(uuid4()),
                                "run_id": run_id,
                                "page_id": row["page_id"],
                                "finding_id": finding_id,
                                "to_decision_status": row["decision_status"],
                                "action_type": row["action_type"],
                                "area_mask_id": row.get("area_mask_id"),
                                "actor_user_id": run_created_by,
                                "reason": row.get("decision_reason"),
                                "created_at": now,
                            },
                        )

                    cursor.execute(
                        """
                        SELECT page_id
                        FROM redaction_page_reviews
                        WHERE run_id = %(run_id)s
                        ORDER BY page_id ASC
                        """,
                        {"run_id": run_id},
                    )
                    review_page_rows = cursor.fetchall()
                    for page_row in review_page_rows:
                        if not isinstance(page_row.get("page_id"), str):
                            continue
                        self._refresh_redaction_page_second_review_requirement(
                            cursor=cursor,
                            run_id=run_id,
                            page_id=str(page_row["page_id"]),
                            actor_user_id=run_created_by,
                        )

                    cursor.execute(
                        """
                        SELECT
                          rf.id,
                          rf.run_id,
                          rf.page_id,
                          rf.line_id,
                          rf.category,
                          rf.span_start,
                          rf.span_end,
                          rf.span_basis_kind,
                          rf.span_basis_ref,
                          rf.confidence,
                          rf.basis_primary,
                          rf.basis_secondary_json,
                          rf.assist_explanation_key,
                          rf.assist_explanation_sha256,
                          rf.bbox_refs,
                          rf.token_refs_json,
                          rf.area_mask_id,
                          rf.decision_status,
                          rf.override_risk_classification,
                          rf.override_risk_reason_codes_json,
                          rf.decision_by,
                          rf.decision_at,
                          rf.decision_reason,
                          rf.decision_etag,
                          rf.updated_at,
                          rf.created_at,
                          COALESCE((
                            SELECT rde.action_type
                            FROM redaction_decision_events AS rde
                            WHERE rde.finding_id = rf.id
                            ORDER BY rde.created_at DESC, rde.id DESC
                            LIMIT 1
                          ), 'MASK') AS action_type
                        FROM redaction_findings AS rf
                        WHERE rf.run_id = %(run_id)s
                        ORDER BY rf.page_id ASC, rf.created_at ASC, rf.id ASC
                        """,
                        {"run_id": run_id},
                    )
                    rows = cursor.fetchall()
                connection.commit()
        except DocumentNotFoundError:
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Redaction finding replacement failed."
            ) from error

        return [self._as_redaction_finding_record(row) for row in rows]

    def cancel_redaction_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        canceled_by: str,
    ) -> RedactionRunRecord:
        self.ensure_schema()
        now = datetime.now(timezone.utc)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT rr.id, rr.status, rrv.review_status
                        FROM redaction_runs AS rr
                        LEFT JOIN redaction_run_reviews AS rrv
                          ON rrv.run_id = rr.id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                          AND rr.id = %(run_id)s
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
                        raise DocumentNotFoundError("Redaction run not found.")
                    review_status = (
                        self._assert_redaction_run_review_status(
                            str(run_row["review_status"])
                        )
                        if isinstance(run_row.get("review_status"), str)
                        else "NOT_READY"
                    )
                    if review_status == "APPROVED":
                        raise DocumentRedactionRunConflictError(
                            "Approved redaction runs cannot be canceled."
                        )
                    status = self._assert_redaction_run_status(str(run_row["status"]))
                    if status == "CANCELED":
                        raise DocumentRedactionRunConflictError(
                            "Redaction run is already canceled."
                        )
                    cursor.execute(
                        """
                        SELECT status
                        FROM redaction_run_outputs
                        WHERE run_id = %(run_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {"run_id": run_id},
                    )
                    run_output_row = cursor.fetchone()
                    previous_run_output_status = (
                        self._assert_redaction_output_status(str(run_output_row["status"]))
                        if run_output_row is not None and isinstance(run_output_row.get("status"), str)
                        else None
                    )
                    cursor.execute(
                        """
                        UPDATE redaction_runs
                        SET
                          status = 'CANCELED',
                          finished_at = NOW(),
                          failure_reason = %(reason)s
                        WHERE id = %(run_id)s
                        """,
                        {
                            "run_id": run_id,
                            "reason": f"Canceled by {canceled_by}.",
                        },
                    )
                    cursor.execute(
                        """
                        UPDATE redaction_outputs
                        SET
                          status = 'CANCELED',
                          canceled_by = %(canceled_by)s,
                          canceled_at = %(canceled_at)s,
                          updated_at = NOW()
                        WHERE run_id = %(run_id)s
                        """,
                        {
                            "run_id": run_id,
                            "canceled_by": canceled_by,
                            "canceled_at": now,
                        },
                    )
                    cursor.execute(
                        """
                        UPDATE redaction_run_outputs
                        SET
                          status = 'CANCELED',
                          canceled_by = %(canceled_by)s,
                          canceled_at = %(canceled_at)s,
                          updated_at = NOW()
                        WHERE run_id = %(run_id)s
                        """,
                        {
                            "run_id": run_id,
                            "canceled_by": canceled_by,
                            "canceled_at": now,
                        },
                    )
                    if previous_run_output_status != "CANCELED":
                        self._append_redaction_run_output_event(
                            cursor=cursor,
                            run_id=run_id,
                            from_status=previous_run_output_status,
                            to_status="CANCELED",
                            reason=f"Canceled by {canceled_by}.",
                            actor_user_id=canceled_by,
                            created_at=now,
                        )
                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          document_id,
                          input_transcription_run_id,
                          input_layout_run_id,
                          run_kind,
                          supersedes_redaction_run_id,
                          superseded_by_redaction_run_id,
                          policy_snapshot_id,
                          policy_snapshot_json,
                          policy_snapshot_hash,
                          policy_id,
                          policy_family_id,
                          policy_version,
                          detectors_version,
                          status,
                          created_by,
                          created_at,
                          started_at,
                          finished_at,
                          failure_reason
                        FROM redaction_runs
                        WHERE id = %(run_id)s
                        LIMIT 1
                        """,
                        {"run_id": run_id},
                    )
                    row = cursor.fetchone()
                connection.commit()
        except (DocumentNotFoundError, DocumentRedactionRunConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Redaction run cancel failed.") from error
        if row is None:
            raise DocumentStoreUnavailableError("Redaction run cancel failed.")
        return self._as_redaction_run_record(row)

    def activate_redaction_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentRedactionProjectionRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          rr.id,
                          rr.input_transcription_run_id,
                          rr.input_layout_run_id,
                          rr.policy_snapshot_id,
                          rr.status,
                          rrv.review_status
                        FROM redaction_runs AS rr
                        LEFT JOIN redaction_run_reviews AS rrv
                          ON rrv.run_id = rr.id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                          AND rr.id = %(run_id)s
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
                        raise DocumentNotFoundError("Redaction run not found.")
                    run_status = self._assert_redaction_run_status(str(run_row["status"]))
                    if run_status != "SUCCEEDED":
                        raise DocumentRedactionRunConflictError(
                            "Only SUCCEEDED redaction runs can be activated."
                        )
                    review_status = (
                        self._assert_redaction_run_review_status(
                            str(run_row["review_status"])
                        )
                        if isinstance(run_row.get("review_status"), str)
                        else "NOT_READY"
                    )
                    if review_status != "APPROVED":
                        raise DocumentRedactionRunConflictError(
                            "Activation requires APPROVED run review."
                        )

                    cursor.execute(
                        """
                        SELECT 1
                        FROM redaction_outputs
                        WHERE run_id = %(run_id)s
                          AND status != 'READY'
                        LIMIT 1
                        """,
                        {"run_id": run_id},
                    )
                    if cursor.fetchone() is not None:
                        raise DocumentRedactionRunConflictError(
                            "Activation requires all page preview outputs to be READY."
                        )

                    cursor.execute(
                        """
                        SELECT status
                        FROM redaction_run_outputs
                        WHERE run_id = %(run_id)s
                        LIMIT 1
                        """,
                        {"run_id": run_id},
                    )
                    output_row = cursor.fetchone()
                    if output_row is None or self._assert_redaction_output_status(
                        str(output_row["status"])
                    ) != "READY":
                        raise DocumentRedactionRunConflictError(
                            "Activation requires run-level safeguarded output to be READY."
                        )

                    cursor.execute(
                        """
                        INSERT INTO document_redaction_projections (
                          document_id,
                          project_id,
                          active_redaction_run_id,
                          active_transcription_run_id,
                          active_layout_run_id,
                          active_policy_snapshot_id,
                          updated_at
                        )
                        VALUES (
                          %(document_id)s,
                          %(project_id)s,
                          %(active_redaction_run_id)s,
                          %(active_transcription_run_id)s,
                          %(active_layout_run_id)s,
                          %(active_policy_snapshot_id)s,
                          NOW()
                        )
                        ON CONFLICT (document_id) DO UPDATE
                        SET
                          project_id = EXCLUDED.project_id,
                          active_redaction_run_id = EXCLUDED.active_redaction_run_id,
                          active_transcription_run_id = EXCLUDED.active_transcription_run_id,
                          active_layout_run_id = EXCLUDED.active_layout_run_id,
                          active_policy_snapshot_id = EXCLUDED.active_policy_snapshot_id,
                          updated_at = NOW()
                        """,
                        {
                            "document_id": document_id,
                            "project_id": project_id,
                            "active_redaction_run_id": run_id,
                            "active_transcription_run_id": str(
                                run_row["input_transcription_run_id"]
                            ),
                            "active_layout_run_id": (
                                str(run_row["input_layout_run_id"])
                                if isinstance(run_row.get("input_layout_run_id"), str)
                                else None
                            ),
                            "active_policy_snapshot_id": str(run_row["policy_snapshot_id"]),
                        },
                    )

                    cursor.execute(
                        """
                        UPDATE document_transcription_projections
                        SET
                          downstream_redaction_state = 'CURRENT',
                          downstream_redaction_invalidated_at = NULL,
                          downstream_redaction_invalidated_reason = NULL,
                          updated_at = NOW()
                        WHERE project_id = %(project_id)s
                          AND document_id = %(document_id)s
                          AND active_transcription_run_id = %(active_transcription_run_id)s
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "active_transcription_run_id": str(
                                run_row["input_transcription_run_id"]
                            ),
                        },
                    )

                    cursor.execute(
                        """
                        SELECT
                          document_id,
                          project_id,
                          active_redaction_run_id,
                          active_transcription_run_id,
                          active_layout_run_id,
                          active_policy_snapshot_id,
                          updated_at
                        FROM document_redaction_projections
                        WHERE project_id = %(project_id)s
                          AND document_id = %(document_id)s
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                        },
                    )
                    projection_row = cursor.fetchone()
                connection.commit()
        except (DocumentNotFoundError, DocumentRedactionRunConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Redaction run activation failed."
            ) from error
        if projection_row is None:
            raise DocumentStoreUnavailableError("Redaction run activation failed.")
        return self._as_redaction_projection_record(projection_row)

    def get_redaction_run_review(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> RedactionRunReviewRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          rrv.run_id,
                          rrv.review_status,
                          rrv.review_started_by,
                          rrv.review_started_at,
                          rrv.approved_by,
                          rrv.approved_at,
                          rrv.approved_snapshot_key,
                          rrv.approved_snapshot_sha256,
                          rrv.locked_at,
                          rrv.updated_at
                        FROM redaction_run_reviews AS rrv
                        INNER JOIN redaction_runs AS rr
                          ON rr.id = rrv.run_id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                          AND rr.id = %(run_id)s
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
            raise DocumentStoreUnavailableError(
                "Redaction run review lookup failed."
            ) from error
        if row is None:
            return None
        return self._as_redaction_run_review_record(row)

    def get_redaction_approval_snapshot_artifact(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> tuple[bytes, str]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          rrv.review_status,
                          rrv.locked_at,
                          rrv.approved_snapshot_sha256
                        FROM redaction_run_reviews AS rrv
                        INNER JOIN redaction_runs AS rr
                          ON rr.id = rrv.run_id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                          AND rr.id = %(run_id)s
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    review_row = cursor.fetchone()
                    if review_row is None:
                        raise DocumentNotFoundError("Redaction run review not found.")
                    review_status = self._assert_redaction_run_review_status(
                        str(review_row["review_status"])
                    )
                    if review_status != "APPROVED":
                        raise DocumentRedactionRunConflictError(
                            "Approved snapshot artifact is available only for APPROVED runs."
                        )
                    if not isinstance(review_row.get("locked_at"), datetime):
                        raise DocumentStoreUnavailableError(
                            "Approved redaction run lock timestamp is missing."
                        )
                    snapshot_bytes, snapshot_sha256 = self._build_redaction_approval_snapshot_bytes(
                        cursor=cursor,
                        run_id=run_id,
                        captured_at=review_row["locked_at"],  # type: ignore[arg-type]
                    )
                    persisted_sha256 = (
                        str(review_row["approved_snapshot_sha256"])
                        if isinstance(review_row.get("approved_snapshot_sha256"), str)
                        else None
                    )
                    if persisted_sha256 is not None and persisted_sha256 != snapshot_sha256:
                        raise DocumentStoreUnavailableError(
                            "Approved snapshot hash no longer matches locked review artifact."
                        )
        except (DocumentNotFoundError, DocumentRedactionRunConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Redaction approval snapshot reconstruction failed."
            ) from error
        return snapshot_bytes, snapshot_sha256

    def start_redaction_run_review(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        actor_user_id: str,
    ) -> RedactionRunReviewRecord:
        self.ensure_schema()
        now = datetime.now(timezone.utc)
        event_id = str(uuid4())
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT rr.status, rrv.review_status
                        FROM redaction_runs AS rr
                        INNER JOIN redaction_run_reviews AS rrv
                          ON rrv.run_id = rr.id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                          AND rr.id = %(run_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise DocumentNotFoundError("Redaction run not found.")
                    run_status = self._assert_redaction_run_status(str(row["status"]))
                    if run_status != "SUCCEEDED":
                        raise DocumentRedactionRunConflictError(
                            "Run review can start only after run status is SUCCEEDED."
                        )
                    current_status = self._assert_redaction_run_review_status(
                        str(row["review_status"])
                    )
                    if current_status == "APPROVED":
                        raise DocumentRedactionRunConflictError(
                            "Approved run review cannot be reopened."
                        )
                    if current_status != "NOT_READY":
                        raise DocumentRedactionRunConflictError(
                            "Run review start requires NOT_READY status."
                        )
                    cursor.execute(
                        """
                        SELECT 1
                        FROM redaction_page_reviews
                        WHERE run_id = %(run_id)s
                          AND review_status = 'NOT_STARTED'
                        LIMIT 1
                        """,
                        {"run_id": run_id},
                    )
                    if cursor.fetchone() is not None:
                        raise DocumentRedactionRunConflictError(
                            "Run review start requires every page to be reviewed at least once."
                        )
                    cursor.execute(
                        """
                        UPDATE redaction_run_reviews
                        SET
                          review_status = 'IN_REVIEW',
                          review_started_by = COALESCE(review_started_by, %(actor_user_id)s),
                          review_started_at = COALESCE(review_started_at, %(review_started_at)s),
                          updated_at = NOW()
                        WHERE run_id = %(run_id)s
                        """,
                        {
                            "run_id": run_id,
                            "actor_user_id": actor_user_id,
                            "review_started_at": now,
                        },
                    )
                    cursor.execute(
                        """
                        INSERT INTO redaction_run_review_events (
                          id,
                          run_id,
                          event_type,
                          actor_user_id,
                          reason,
                          created_at
                        )
                        VALUES (
                          %(id)s,
                          %(run_id)s,
                          'RUN_REVIEW_OPENED',
                          %(actor_user_id)s,
                          NULL,
                          %(created_at)s
                        )
                        """,
                        {
                            "id": event_id,
                            "run_id": run_id,
                            "actor_user_id": actor_user_id,
                            "created_at": now,
                        },
                    )
                    cursor.execute(
                        """
                        SELECT
                          run_id,
                          review_status,
                          review_started_by,
                          review_started_at,
                          approved_by,
                          approved_at,
                          approved_snapshot_key,
                          approved_snapshot_sha256,
                          locked_at,
                          updated_at
                        FROM redaction_run_reviews
                        WHERE run_id = %(run_id)s
                        LIMIT 1
                        """,
                        {"run_id": run_id},
                    )
                    review_row = cursor.fetchone()
                connection.commit()
        except (DocumentNotFoundError, DocumentRedactionRunConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Redaction run review start failed.") from error
        if review_row is None:
            raise DocumentStoreUnavailableError("Redaction run review start failed.")
        return self._as_redaction_run_review_record(review_row)

    def complete_redaction_run_review(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        actor_user_id: str,
        review_status: RedactionRunReviewStatus,
        reason: str | None = None,
        approved_snapshot_key: str | None = None,
        approved_snapshot_sha256: str | None = None,
    ) -> RedactionRunReviewRecord:
        self.ensure_schema()
        if review_status not in {"APPROVED", "CHANGES_REQUESTED"}:
            raise DocumentRedactionRunConflictError(
                "reviewStatus must be APPROVED or CHANGES_REQUESTED."
            )
        now = datetime.now(timezone.utc)
        event_id = str(uuid4())
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT rr.id, rrv.review_status
                        FROM redaction_runs AS rr
                        INNER JOIN redaction_run_reviews AS rrv
                          ON rrv.run_id = rr.id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                          AND rr.id = %(run_id)s
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
                        raise DocumentNotFoundError("Redaction run not found.")
                    current_status = self._assert_redaction_run_review_status(
                        str(current["review_status"])
                    )
                    if current_status != "IN_REVIEW":
                        raise DocumentRedactionRunConflictError(
                            "Run review completion requires IN_REVIEW state."
                        )

                    resolved_snapshot_key = (
                        approved_snapshot_key.strip()
                        if isinstance(approved_snapshot_key, str)
                        and approved_snapshot_key.strip()
                        else None
                    )
                    resolved_snapshot_sha256 = (
                        approved_snapshot_sha256.strip()
                        if isinstance(approved_snapshot_sha256, str)
                        and approved_snapshot_sha256.strip()
                        else None
                    )
                    if review_status != "APPROVED":
                        resolved_snapshot_key = None
                        resolved_snapshot_sha256 = None
                    locked_at: datetime | None = None
                    approved_at: datetime | None = None
                    approved_by: str | None = None

                    if review_status == "APPROVED":
                        cursor.execute(
                            """
                            SELECT 1
                            FROM redaction_page_reviews
                            WHERE run_id = %(run_id)s
                              AND (
                                review_status != 'APPROVED'
                                OR (
                                  requires_second_review = TRUE
                                  AND second_review_status != 'APPROVED'
                                )
                              )
                            LIMIT 1
                            """,
                            {"run_id": run_id},
                        )
                        if cursor.fetchone() is not None:
                            raise DocumentRedactionRunConflictError(
                                "Run approval requires every page review to be APPROVED."
                            )
                        _, computed_snapshot_sha256 = self._build_redaction_approval_snapshot_bytes(
                            cursor=cursor,
                            run_id=run_id,
                            captured_at=now,
                        )
                        if (
                            resolved_snapshot_sha256 is not None
                            and resolved_snapshot_sha256 != computed_snapshot_sha256
                        ):
                            raise DocumentRedactionRunConflictError(
                                "Approval snapshot changed during completion. Retry approval."
                            )
                        resolved_snapshot_sha256 = computed_snapshot_sha256
                        if resolved_snapshot_key is None:
                            derived_prefix = self._settings.storage_controlled_derived_prefix.strip(
                                "/ "
                            )
                            resolved_snapshot_key = (
                                f"{derived_prefix}/{project_id}/{document_id}/redaction/{run_id}/"
                                f"approved-snapshots/{resolved_snapshot_sha256}.json"
                            )
                        approved_at = now
                        approved_by = actor_user_id
                        locked_at = now

                    cursor.execute(
                        """
                        UPDATE redaction_run_reviews
                        SET
                          review_status = %(review_status)s,
                          approved_by = %(approved_by)s,
                          approved_at = %(approved_at)s,
                          approved_snapshot_key = %(approved_snapshot_key)s,
                          approved_snapshot_sha256 = %(approved_snapshot_sha256)s,
                          locked_at = %(locked_at)s,
                          updated_at = NOW()
                        WHERE run_id = %(run_id)s
                        """,
                        {
                            "run_id": run_id,
                            "review_status": review_status,
                            "approved_by": approved_by,
                            "approved_at": approved_at,
                            "approved_snapshot_key": resolved_snapshot_key,
                            "approved_snapshot_sha256": resolved_snapshot_sha256,
                            "locked_at": locked_at,
                        },
                    )
                    cursor.execute(
                        """
                        INSERT INTO redaction_run_review_events (
                          id,
                          run_id,
                          event_type,
                          actor_user_id,
                          reason,
                          created_at
                        )
                        VALUES (
                          %(id)s,
                          %(run_id)s,
                          %(event_type)s,
                          %(actor_user_id)s,
                          %(reason)s,
                          %(created_at)s
                        )
                        """,
                        {
                            "id": event_id,
                            "run_id": run_id,
                            "event_type": (
                                "RUN_APPROVED"
                                if review_status == "APPROVED"
                                else "RUN_CHANGES_REQUESTED"
                            ),
                            "actor_user_id": actor_user_id,
                            "reason": reason,
                            "created_at": now,
                        },
                    )
                    cursor.execute(
                        """
                        SELECT
                          run_id,
                          review_status,
                          review_started_by,
                          review_started_at,
                          approved_by,
                          approved_at,
                          approved_snapshot_key,
                          approved_snapshot_sha256,
                          locked_at,
                          updated_at
                        FROM redaction_run_reviews
                        WHERE run_id = %(run_id)s
                        LIMIT 1
                        """,
                        {"run_id": run_id},
                    )
                    review_row = cursor.fetchone()
                connection.commit()
        except (DocumentNotFoundError, DocumentRedactionRunConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Redaction run review completion failed."
            ) from error
        if review_row is None:
            raise DocumentStoreUnavailableError(
                "Redaction run review completion failed."
            )
        return self._as_redaction_run_review_record(review_row)

    def list_redaction_page_reviews(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        cursor: int = 0,
        page_size: int = 200,
    ) -> tuple[list[RedactionPageReviewRecord], int | None]:
        self.ensure_schema()
        safe_cursor = max(0, cursor)
        safe_page_size = max(1, min(page_size, 500))
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as db_cursor:
                    db_cursor.execute(
                        """
                        SELECT
                          pr.run_id,
                          pr.page_id,
                          pr.review_status,
                          pr.review_etag,
                          pr.first_reviewed_by,
                          pr.first_reviewed_at,
                          pr.requires_second_review,
                          pr.second_review_status,
                          pr.second_reviewed_by,
                          pr.second_reviewed_at,
                          pr.updated_at
                        FROM redaction_page_reviews AS pr
                        INNER JOIN redaction_runs AS rr
                          ON rr.id = pr.run_id
                        INNER JOIN pages AS p
                          ON p.id = pr.page_id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                          AND pr.run_id = %(run_id)s
                        ORDER BY p.page_index ASC, pr.page_id ASC
                        OFFSET %(cursor)s
                        LIMIT %(limit)s
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                            "cursor": safe_cursor,
                            "limit": safe_page_size + 1,
                        },
                    )
                    rows = db_cursor.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Redaction page-review listing failed."
            ) from error
        items = [self._as_redaction_page_review_record(row) for row in rows[:safe_page_size]]
        next_cursor = (
            safe_cursor + safe_page_size if len(rows) > safe_page_size else None
        )
        return items, next_cursor

    def get_redaction_page_review(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> RedactionPageReviewRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          pr.run_id,
                          pr.page_id,
                          pr.review_status,
                          pr.review_etag,
                          pr.first_reviewed_by,
                          pr.first_reviewed_at,
                          pr.requires_second_review,
                          pr.second_review_status,
                          pr.second_reviewed_by,
                          pr.second_reviewed_at,
                          pr.updated_at
                        FROM redaction_page_reviews AS pr
                        INNER JOIN redaction_runs AS rr
                          ON rr.id = pr.run_id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                          AND pr.run_id = %(run_id)s
                          AND pr.page_id = %(page_id)s
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
            raise DocumentStoreUnavailableError(
                "Redaction page-review lookup failed."
            ) from error
        if row is None:
            return None
        return self._as_redaction_page_review_record(row)

    def update_redaction_page_review(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        expected_review_etag: str,
        review_status: RedactionPageReviewStatus,
        actor_user_id: str,
        reason: str | None = None,
    ) -> RedactionPageReviewRecord:
        self.ensure_schema()
        now = datetime.now(timezone.utc)
        event_id = str(uuid4())
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          rrv.review_status,
                          rr.policy_snapshot_json
                        FROM redaction_run_reviews AS rrv
                        INNER JOIN redaction_runs AS rr
                          ON rr.id = rrv.run_id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                          AND rrv.run_id = %(run_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    run_review_row = cursor.fetchone()
                    if run_review_row is None:
                        raise DocumentNotFoundError("Redaction run not found.")
                    if self._assert_redaction_run_review_status(
                        str(run_review_row["review_status"])
                    ) == "APPROVED":
                        raise DocumentRedactionRunConflictError(
                            "Approved runs are locked and cannot be mutated."
                        )
                    policy_snapshot_json = run_review_row.get("policy_snapshot_json")

                    cursor.execute(
                        """
                        SELECT
                          pr.run_id,
                          pr.page_id,
                          pr.review_status,
                          pr.review_etag,
                          pr.first_reviewed_by,
                          pr.first_reviewed_at,
                          pr.requires_second_review,
                          pr.second_review_status,
                          pr.second_reviewed_by,
                          pr.second_reviewed_at,
                          pr.updated_at
                        FROM redaction_page_reviews AS pr
                        WHERE pr.run_id = %(run_id)s
                          AND pr.page_id = %(page_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                        },
                    )
                    current_row = cursor.fetchone()
                    if current_row is None:
                        raise DocumentNotFoundError("Redaction page review not found.")
                    current_review = self._as_redaction_page_review_record(current_row)
                    if current_review.review_etag != expected_review_etag:
                        raise DocumentRedactionRunConflictError(
                            "Redaction page review update conflicts with a newer change."
                        )

                    next_first_reviewed_by = (
                        current_review.first_reviewed_by
                        if current_review.first_reviewed_by is not None
                        else actor_user_id
                    )
                    next_first_reviewed_at = (
                        current_review.first_reviewed_at
                        if current_review.first_reviewed_at is not None
                        else now
                    )
                    effective_review_status = review_status
                    next_second_review_status = current_review.second_review_status
                    next_second_reviewed_by = current_review.second_reviewed_by
                    next_second_reviewed_at = current_review.second_reviewed_at
                    event_type: RedactionPageReviewEventType = "PAGE_REVIEW_STARTED"

                    if current_review.requires_second_review:
                        if (
                            current_review.first_reviewed_by is not None
                            and actor_user_id == current_review.first_reviewed_by
                            and current_review.review_status == "APPROVED"
                            and review_status in {"APPROVED", "CHANGES_REQUESTED"}
                        ):
                            raise DocumentRedactionRunConflictError(
                                "Second review must be completed by a different reviewer."
                            )
                        if (
                            current_review.first_reviewed_by is not None
                            and actor_user_id != current_review.first_reviewed_by
                            and current_review.review_status == "APPROVED"
                            and review_status in {"APPROVED", "CHANGES_REQUESTED"}
                        ):
                            next_second_review_status = (
                                "APPROVED"
                                if review_status == "APPROVED"
                                else "CHANGES_REQUESTED"
                            )
                            next_second_reviewed_by = actor_user_id
                            next_second_reviewed_at = now
                            event_type = (
                                "SECOND_REVIEW_APPROVED"
                                if review_status == "APPROVED"
                                else "SECOND_REVIEW_CHANGES_REQUESTED"
                            )
                            effective_review_status = review_status
                        else:
                            next_second_review_status = "PENDING"
                            next_second_reviewed_by = None
                            next_second_reviewed_at = None
                            if review_status == "APPROVED":
                                event_type = "PAGE_APPROVED"
                            elif review_status == "CHANGES_REQUESTED":
                                event_type = "CHANGES_REQUESTED"
                    else:
                        next_second_review_status = "NOT_REQUIRED"
                        next_second_reviewed_by = None
                        next_second_reviewed_at = None
                        if review_status == "APPROVED":
                            event_type = "PAGE_APPROVED"
                        elif review_status == "CHANGES_REQUESTED":
                            event_type = "CHANGES_REQUESTED"

                    next_etag = self._compute_redaction_etag(
                        run_id,
                        page_id,
                        effective_review_status,
                        str(next_second_review_status),
                        actor_user_id,
                        now.isoformat(),
                    )
                    cursor.execute(
                        """
                        UPDATE redaction_page_reviews
                        SET
                          review_status = %(review_status)s,
                          review_etag = %(review_etag)s,
                          first_reviewed_by = %(first_reviewed_by)s,
                          first_reviewed_at = %(first_reviewed_at)s,
                          second_review_status = %(second_review_status)s,
                          second_reviewed_by = %(second_reviewed_by)s,
                          second_reviewed_at = %(second_reviewed_at)s,
                          updated_at = NOW()
                        WHERE run_id = %(run_id)s
                          AND page_id = %(page_id)s
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                            "review_status": effective_review_status,
                            "review_etag": next_etag,
                            "first_reviewed_by": next_first_reviewed_by,
                            "first_reviewed_at": next_first_reviewed_at,
                            "second_review_status": next_second_review_status,
                            "second_reviewed_by": next_second_reviewed_by,
                            "second_reviewed_at": next_second_reviewed_at,
                        },
                    )

                    cursor.execute(
                        """
                        INSERT INTO redaction_page_review_events (
                          id,
                          run_id,
                          page_id,
                          event_type,
                          actor_user_id,
                          reason,
                          created_at
                        )
                        VALUES (
                          %(id)s,
                          %(run_id)s,
                          %(page_id)s,
                          %(event_type)s,
                          %(actor_user_id)s,
                          %(reason)s,
                          %(created_at)s
                        )
                        """,
                        {
                            "id": event_id,
                            "run_id": run_id,
                            "page_id": page_id,
                            "event_type": event_type,
                            "actor_user_id": actor_user_id,
                            "reason": reason,
                            "created_at": now,
                        },
                    )

                    cursor.execute(
                        """
                        SELECT
                          pr.run_id,
                          pr.page_id,
                          pr.review_status,
                          pr.review_etag,
                          pr.first_reviewed_by,
                          pr.first_reviewed_at,
                          pr.requires_second_review,
                          pr.second_review_status,
                          pr.second_reviewed_by,
                          pr.second_reviewed_at,
                          pr.updated_at
                        FROM redaction_page_reviews AS pr
                        WHERE pr.run_id = %(run_id)s
                          AND pr.page_id = %(page_id)s
                        LIMIT 1
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                        },
                    )
                    review_row = cursor.fetchone()
                connection.commit()
        except (DocumentNotFoundError, DocumentRedactionRunConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Redaction page-review update failed."
            ) from error
        if review_row is None:
            raise DocumentStoreUnavailableError("Redaction page-review update failed.")
        return self._as_redaction_page_review_record(review_row)

    def list_redaction_findings(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str | None = None,
        category: str | None = None,
        unresolved_only: bool = False,
    ) -> list[RedactionFindingRecord]:
        self.ensure_schema()
        clauses = [
            "rr.project_id = %(project_id)s",
            "rr.document_id = %(document_id)s",
            "rf.run_id = %(run_id)s",
        ]
        params: dict[str, object] = {
            "project_id": project_id,
            "document_id": document_id,
            "run_id": run_id,
        }
        if isinstance(page_id, str) and page_id.strip():
            clauses.append("rf.page_id = %(page_id)s")
            params["page_id"] = page_id.strip()
        if isinstance(category, str) and category.strip():
            clauses.append("rf.category = %(category)s")
            params["category"] = category.strip()
        if unresolved_only:
            clauses.append(
                "rf.decision_status IN ('NEEDS_REVIEW', 'OVERRIDDEN', 'FALSE_POSITIVE')"
            )
        where_sql = " AND ".join(clauses)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        f"""
                        SELECT
                          rf.id,
                          rf.run_id,
                          rf.page_id,
                          rf.line_id,
                          rf.category,
                          rf.span_start,
                          rf.span_end,
                          rf.span_basis_kind,
                          rf.span_basis_ref,
                          rf.confidence,
                          rf.basis_primary,
                          rf.basis_secondary_json,
                          rf.assist_explanation_key,
                          rf.assist_explanation_sha256,
                          rf.bbox_refs,
                          rf.token_refs_json,
                          rf.area_mask_id,
                          rf.decision_status,
                          rf.override_risk_classification,
                          rf.override_risk_reason_codes_json,
                          rf.decision_by,
                          rf.decision_at,
                          rf.decision_reason,
                          rf.decision_etag,
                          rf.updated_at,
                          rf.created_at,
                          COALESCE((
                            SELECT rde.action_type
                            FROM redaction_decision_events AS rde
                            WHERE rde.finding_id = rf.id
                            ORDER BY rde.created_at DESC, rde.id DESC
                            LIMIT 1
                          ), 'MASK') AS action_type,
                          rr.policy_snapshot_json
                        FROM redaction_findings AS rf
                        INNER JOIN redaction_runs AS rr
                          ON rr.id = rf.run_id
                        WHERE {where_sql}
                        ORDER BY rf.page_id ASC, rf.created_at ASC, rf.id ASC
                        """,
                        params,
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Redaction finding listing failed.") from error
        return [self._as_redaction_finding_record(row) for row in rows]

    def get_redaction_finding(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        finding_id: str,
    ) -> RedactionFindingRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          rf.id,
                          rf.run_id,
                          rf.page_id,
                          rf.line_id,
                          rf.category,
                          rf.span_start,
                          rf.span_end,
                          rf.span_basis_kind,
                          rf.span_basis_ref,
                          rf.confidence,
                          rf.basis_primary,
                          rf.basis_secondary_json,
                          rf.assist_explanation_key,
                          rf.assist_explanation_sha256,
                          rf.bbox_refs,
                          rf.token_refs_json,
                          rf.area_mask_id,
                          rf.decision_status,
                          rf.override_risk_classification,
                          rf.override_risk_reason_codes_json,
                          rf.decision_by,
                          rf.decision_at,
                          rf.decision_reason,
                          rf.decision_etag,
                          rf.updated_at,
                          rf.created_at,
                          COALESCE((
                            SELECT rde.action_type
                            FROM redaction_decision_events AS rde
                            WHERE rde.finding_id = rf.id
                            ORDER BY rde.created_at DESC, rde.id DESC
                            LIMIT 1
                          ), 'MASK') AS action_type
                        FROM redaction_findings AS rf
                        INNER JOIN redaction_runs AS rr
                          ON rr.id = rf.run_id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                          AND rf.run_id = %(run_id)s
                          AND rf.id = %(finding_id)s
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                            "finding_id": finding_id,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Redaction finding lookup failed.") from error
        if row is None:
            return None
        return self._as_redaction_finding_record(row)

    def update_redaction_finding_decision(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        finding_id: str,
        expected_decision_etag: str,
        to_decision_status: RedactionDecisionStatus,
        actor_user_id: str,
        reason: str | None = None,
        action_type: RedactionDecisionActionType = "MASK",
    ) -> RedactionFindingRecord:
        self.ensure_schema()
        now = datetime.now(timezone.utc)
        event_id = str(uuid4())
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          rrv.review_status,
                          rr.policy_snapshot_json
                        FROM redaction_run_reviews AS rrv
                        INNER JOIN redaction_runs AS rr
                          ON rr.id = rrv.run_id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                          AND rrv.run_id = %(run_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    run_review_row = cursor.fetchone()
                    if run_review_row is None:
                        raise DocumentNotFoundError("Redaction run not found.")
                    if self._assert_redaction_run_review_status(
                        str(run_review_row["review_status"])
                    ) == "APPROVED":
                        raise DocumentRedactionRunConflictError(
                            "Approved runs are locked and cannot be mutated."
                        )
                    policy_snapshot_json = run_review_row.get("policy_snapshot_json")

                    cursor.execute(
                        """
                        SELECT
                          rf.id,
                          rf.run_id,
                          rf.page_id,
                          rf.line_id,
                          rf.category,
                          rf.span_start,
                          rf.span_end,
                          rf.span_basis_kind,
                          rf.span_basis_ref,
                          rf.confidence,
                          rf.basis_primary,
                          rf.basis_secondary_json,
                          rf.assist_explanation_key,
                          rf.assist_explanation_sha256,
                          rf.bbox_refs,
                          rf.token_refs_json,
                          rf.area_mask_id,
                          rf.decision_status,
                          rf.override_risk_classification,
                          rf.override_risk_reason_codes_json,
                          rf.decision_by,
                          rf.decision_at,
                          rf.decision_reason,
                          rf.decision_etag,
                          rf.updated_at,
                          rf.created_at
                        FROM redaction_findings AS rf
                        INNER JOIN redaction_runs AS rr
                          ON rr.id = rf.run_id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                          AND rf.run_id = %(run_id)s
                          AND rf.id = %(finding_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                            "finding_id": finding_id,
                        },
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise DocumentNotFoundError("Redaction finding not found.")
                    current = self._as_redaction_finding_record(row)
                    if current.decision_etag != expected_decision_etag:
                        raise DocumentRedactionRunConflictError(
                            "Redaction finding update conflicts with a newer change."
                        )
                    override_risk_classification, override_risk_reason_codes = (
                        self._derive_redaction_override_risk(
                            to_decision_status=to_decision_status,
                            category=current.category,
                            area_mask_id=current.area_mask_id,
                            basis_secondary_json=current.basis_secondary_json,
                            policy_snapshot_json=row.get("policy_snapshot_json"),
                        )
                    )
                    next_etag = self._compute_redaction_etag(
                        run_id,
                        finding_id,
                        to_decision_status,
                        actor_user_id,
                        now.isoformat(),
                    )
                    cursor.execute(
                        """
                        UPDATE redaction_findings
                        SET
                          decision_status = %(decision_status)s,
                          decision_by = %(decision_by)s,
                          decision_at = %(decision_at)s,
                          decision_reason = %(decision_reason)s,
                          override_risk_classification = %(override_risk_classification)s,
                          override_risk_reason_codes_json = %(override_risk_reason_codes_json)s::jsonb,
                          decision_etag = %(decision_etag)s,
                          updated_at = NOW()
                        WHERE id = %(finding_id)s
                        """,
                        {
                            "finding_id": finding_id,
                            "decision_status": to_decision_status,
                            "decision_by": actor_user_id,
                            "decision_at": now,
                            "decision_reason": reason,
                            "override_risk_classification": override_risk_classification,
                            "override_risk_reason_codes_json": (
                                json.dumps(
                                    override_risk_reason_codes,
                                    ensure_ascii=True,
                                    separators=(",", ":"),
                                    sort_keys=False,
                                )
                                if override_risk_reason_codes is not None
                                else None
                            ),
                            "decision_etag": next_etag,
                        },
                    )
                    cursor.execute(
                        """
                        INSERT INTO redaction_decision_events (
                          id,
                          run_id,
                          page_id,
                          finding_id,
                          from_decision_status,
                          to_decision_status,
                          action_type,
                          area_mask_id,
                          actor_user_id,
                          reason,
                          created_at
                        )
                        VALUES (
                          %(id)s,
                          %(run_id)s,
                          %(page_id)s,
                          %(finding_id)s,
                          %(from_decision_status)s,
                          %(to_decision_status)s,
                          %(action_type)s,
                          %(area_mask_id)s,
                          %(actor_user_id)s,
                          %(reason)s,
                          %(created_at)s
                        )
                        """,
                        {
                            "id": event_id,
                            "run_id": run_id,
                            "page_id": current.page_id,
                            "finding_id": finding_id,
                            "from_decision_status": current.decision_status,
                            "to_decision_status": to_decision_status,
                            "action_type": action_type,
                            "area_mask_id": current.area_mask_id,
                            "actor_user_id": actor_user_id,
                            "reason": reason,
                            "created_at": now,
                        },
                    )
                    cursor.execute(
                        """
                        UPDATE redaction_outputs
                        SET
                          status = 'PENDING',
                          generated_at = NULL,
                          safeguarded_preview_key = NULL,
                          preview_sha256 = NULL,
                          updated_at = NOW()
                        WHERE run_id = %(run_id)s
                          AND page_id = %(page_id)s
                        """,
                        {
                            "run_id": run_id,
                            "page_id": current.page_id,
                        },
                    )
                    self._refresh_redaction_run_output_status(cursor=cursor, run_id=run_id)
                    self._refresh_redaction_page_second_review_requirement(
                        cursor=cursor,
                        run_id=run_id,
                        page_id=current.page_id,
                        actor_user_id=actor_user_id,
                    )
                    cursor.execute(
                        """
                        SELECT
                          rf.id,
                          rf.run_id,
                          rf.page_id,
                          rf.line_id,
                          rf.category,
                          rf.span_start,
                          rf.span_end,
                          rf.span_basis_kind,
                          rf.span_basis_ref,
                          rf.confidence,
                          rf.basis_primary,
                          rf.basis_secondary_json,
                          rf.assist_explanation_key,
                          rf.assist_explanation_sha256,
                          rf.bbox_refs,
                          rf.token_refs_json,
                          rf.area_mask_id,
                          rf.decision_status,
                          rf.override_risk_classification,
                          rf.override_risk_reason_codes_json,
                          rf.decision_by,
                          rf.decision_at,
                          rf.decision_reason,
                          rf.decision_etag,
                          rf.updated_at,
                          rf.created_at,
                          COALESCE((
                            SELECT rde.action_type
                            FROM redaction_decision_events AS rde
                            WHERE rde.finding_id = rf.id
                            ORDER BY rde.created_at DESC, rde.id DESC
                            LIMIT 1
                          ), 'MASK') AS action_type
                        FROM redaction_findings AS rf
                        WHERE rf.id = %(finding_id)s
                        LIMIT 1
                        """,
                        {"finding_id": finding_id},
                    )
                    updated_row = cursor.fetchone()
                connection.commit()
        except (DocumentNotFoundError, DocumentRedactionRunConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Redaction finding update failed."
            ) from error
        if updated_row is None:
            raise DocumentStoreUnavailableError("Redaction finding update failed.")
        return self._as_redaction_finding_record(updated_row)

    def list_redaction_area_masks(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> list[RedactionAreaMaskRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          ram.id,
                          ram.run_id,
                          ram.page_id,
                          ram.geometry_json,
                          ram.mask_reason,
                          ram.version_etag,
                          ram.supersedes_area_mask_id,
                          ram.superseded_by_area_mask_id,
                          ram.created_by,
                          ram.created_at,
                          ram.updated_at
                        FROM redaction_area_masks AS ram
                        INNER JOIN redaction_runs AS rr
                          ON rr.id = ram.run_id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                          AND ram.run_id = %(run_id)s
                          AND ram.page_id = %(page_id)s
                        ORDER BY ram.created_at ASC, ram.id ASC
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
            raise DocumentStoreUnavailableError("Redaction area-mask listing failed.") from error
        return [self._as_redaction_area_mask_record(row) for row in rows]

    def get_redaction_area_mask(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        mask_id: str,
    ) -> RedactionAreaMaskRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          ram.id,
                          ram.run_id,
                          ram.page_id,
                          ram.geometry_json,
                          ram.mask_reason,
                          ram.version_etag,
                          ram.supersedes_area_mask_id,
                          ram.superseded_by_area_mask_id,
                          ram.created_by,
                          ram.created_at,
                          ram.updated_at
                        FROM redaction_area_masks AS ram
                        INNER JOIN redaction_runs AS rr
                          ON rr.id = ram.run_id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                          AND ram.run_id = %(run_id)s
                          AND ram.page_id = %(page_id)s
                          AND ram.id = %(mask_id)s
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                            "page_id": page_id,
                            "mask_id": mask_id,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Redaction area-mask lookup failed.") from error
        if row is None:
            return None
        return self._as_redaction_area_mask_record(row)

    def get_redaction_area_mask_by_id(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        mask_id: str,
    ) -> RedactionAreaMaskRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          ram.id,
                          ram.run_id,
                          ram.page_id,
                          ram.geometry_json,
                          ram.mask_reason,
                          ram.version_etag,
                          ram.supersedes_area_mask_id,
                          ram.superseded_by_area_mask_id,
                          ram.created_by,
                          ram.created_at,
                          ram.updated_at
                        FROM redaction_area_masks AS ram
                        INNER JOIN redaction_runs AS rr
                          ON rr.id = ram.run_id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                          AND ram.run_id = %(run_id)s
                          AND ram.id = %(mask_id)s
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                            "mask_id": mask_id,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Redaction area-mask lookup failed.") from error
        if row is None:
            return None
        return self._as_redaction_area_mask_record(row)

    def create_redaction_area_mask(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        geometry_json: dict[str, object],
        mask_reason: str,
        actor_user_id: str,
        finding_id: str | None = None,
        expected_finding_decision_etag: str | None = None,
    ) -> tuple[RedactionAreaMaskRecord, RedactionFindingRecord | None]:
        self.ensure_schema()
        now = datetime.now(timezone.utc)
        event_id = str(uuid4())
        new_mask_id = str(uuid4())
        new_mask_etag = self._compute_redaction_etag(
            run_id,
            page_id,
            new_mask_id,
            actor_user_id,
            now.isoformat(),
        )
        linked_finding: RedactionFindingRecord | None = None
        new_mask_row: dict[str, object] | None = None
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT rrv.review_status
                        FROM redaction_run_reviews AS rrv
                        INNER JOIN redaction_runs AS rr
                          ON rr.id = rrv.run_id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                          AND rrv.run_id = %(run_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    run_review_row = cursor.fetchone()
                    if run_review_row is None:
                        raise DocumentNotFoundError("Redaction run not found.")
                    if self._assert_redaction_run_review_status(
                        str(run_review_row["review_status"])
                    ) == "APPROVED":
                        raise DocumentRedactionRunConflictError(
                            "Approved runs are locked and cannot be mutated."
                        )

                    cursor.execute(
                        """
                        SELECT p.width, p.height
                        FROM pages AS p
                        INNER JOIN documents AS d
                          ON d.id = p.document_id
                        WHERE p.id = %(page_id)s
                          AND p.document_id = %(document_id)s
                          AND d.project_id = %(project_id)s
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "page_id": page_id,
                        },
                    )
                    page_row = cursor.fetchone()
                    if page_row is None:
                        raise DocumentNotFoundError("Document page not found.")
                    page_width = int(page_row["width"])
                    page_height = int(page_row["height"])
                    try:
                        normalized_geometry_json = normalize_area_mask_geometry(
                            geometry_json,
                            page_width=page_width,
                            page_height=page_height,
                        )
                    except RedactionGeometryValidationError as error:
                        raise DocumentRedactionRunConflictError(
                            f"Area-mask geometry is invalid: {error}"
                        ) from error

                    cursor.execute(
                        """
                        INSERT INTO redaction_area_masks (
                          id,
                          run_id,
                          page_id,
                          geometry_json,
                          mask_reason,
                          version_etag,
                          supersedes_area_mask_id,
                          superseded_by_area_mask_id,
                          created_by,
                          created_at,
                          updated_at
                        )
                        VALUES (
                          %(id)s,
                          %(run_id)s,
                          %(page_id)s,
                          %(geometry_json)s::jsonb,
                          %(mask_reason)s,
                          %(version_etag)s,
                          NULL,
                          NULL,
                          %(created_by)s,
                          %(created_at)s,
                          %(updated_at)s
                        )
                        """,
                        {
                            "id": new_mask_id,
                            "run_id": run_id,
                            "page_id": page_id,
                            "geometry_json": json.dumps(
                                normalized_geometry_json,
                                ensure_ascii=True,
                                separators=(",", ":"),
                                sort_keys=True,
                            ),
                            "mask_reason": mask_reason,
                            "version_etag": new_mask_etag,
                            "created_by": actor_user_id,
                            "created_at": now,
                            "updated_at": now,
                        },
                    )

                    if isinstance(finding_id, str) and finding_id.strip():
                        cursor.execute(
                            """
                            SELECT
                              rf.id,
                              rf.run_id,
                              rf.page_id,
                              rf.line_id,
                              rf.category,
                              rf.span_start,
                              rf.span_end,
                              rf.span_basis_kind,
                              rf.span_basis_ref,
                              rf.confidence,
                              rf.basis_primary,
                              rf.basis_secondary_json,
                              rf.assist_explanation_key,
                              rf.assist_explanation_sha256,
                              rf.bbox_refs,
                              rf.token_refs_json,
                              rf.area_mask_id,
                              rf.decision_status,
                              rf.override_risk_classification,
                              rf.override_risk_reason_codes_json,
                              rf.decision_by,
                              rf.decision_at,
                              rf.decision_reason,
                              rf.decision_etag,
                              rf.updated_at,
                              rf.created_at
                            FROM redaction_findings AS rf
                            INNER JOIN redaction_runs AS rr
                              ON rr.id = rf.run_id
                            WHERE rr.project_id = %(project_id)s
                              AND rr.document_id = %(document_id)s
                              AND rf.run_id = %(run_id)s
                              AND rf.id = %(finding_id)s
                            LIMIT 1
                            FOR UPDATE
                            """,
                            {
                                "project_id": project_id,
                                "document_id": document_id,
                                "run_id": run_id,
                                "finding_id": finding_id.strip(),
                            },
                        )
                        finding_row = cursor.fetchone()
                        if finding_row is None:
                            raise DocumentNotFoundError(
                                "Linked redaction finding was not found."
                            )
                        linked_finding = self._as_redaction_finding_record(finding_row)
                        if linked_finding.page_id != page_id:
                            raise DocumentRedactionRunConflictError(
                                "Linked redaction finding must belong to the same page."
                            )
                        if (
                            isinstance(expected_finding_decision_etag, str)
                            and expected_finding_decision_etag.strip()
                            and linked_finding.decision_etag
                            != expected_finding_decision_etag.strip()
                        ):
                            raise DocumentRedactionRunConflictError(
                                "Linked redaction finding etag is stale."
                            )
                        next_finding_etag = self._compute_redaction_etag(
                            run_id,
                            linked_finding.id,
                            "AREA_MASK_CREATED",
                            now.isoformat(),
                        )
                        override_risk_classification, override_risk_reason_codes = (
                            self._derive_redaction_override_risk(
                                to_decision_status="OVERRIDDEN",
                                category=linked_finding.category,
                                area_mask_id=new_mask_id,
                                basis_secondary_json=linked_finding.basis_secondary_json,
                                policy_snapshot_json=policy_snapshot_json,
                            )
                        )
                        cursor.execute(
                            """
                            UPDATE redaction_findings
                            SET
                              area_mask_id = %(area_mask_id)s,
                              decision_status = 'OVERRIDDEN',
                              decision_by = %(decision_by)s,
                              decision_at = %(decision_at)s,
                              decision_reason = %(decision_reason)s,
                              override_risk_classification = %(override_risk_classification)s,
                              override_risk_reason_codes_json = %(override_risk_reason_codes_json)s::jsonb,
                              decision_etag = %(decision_etag)s,
                              updated_at = NOW()
                            WHERE id = %(finding_id)s
                            """,
                            {
                                "finding_id": linked_finding.id,
                                "area_mask_id": new_mask_id,
                                "decision_by": actor_user_id,
                                "decision_at": now,
                                "decision_reason": mask_reason,
                                "override_risk_classification": override_risk_classification,
                                "override_risk_reason_codes_json": (
                                    json.dumps(
                                        override_risk_reason_codes,
                                        ensure_ascii=True,
                                        separators=(",", ":"),
                                        sort_keys=False,
                                    )
                                    if override_risk_reason_codes is not None
                                    else None
                                ),
                                "decision_etag": next_finding_etag,
                            },
                        )
                        cursor.execute(
                            """
                            INSERT INTO redaction_decision_events (
                              id,
                              run_id,
                              page_id,
                              finding_id,
                              from_decision_status,
                              to_decision_status,
                              action_type,
                              area_mask_id,
                              actor_user_id,
                              reason,
                              created_at
                            )
                            VALUES (
                              %(id)s,
                              %(run_id)s,
                              %(page_id)s,
                              %(finding_id)s,
                              %(from_decision_status)s,
                              'OVERRIDDEN',
                              'MASK',
                              %(area_mask_id)s,
                              %(actor_user_id)s,
                              %(reason)s,
                              %(created_at)s
                            )
                            """,
                            {
                                "id": event_id,
                                "run_id": run_id,
                                "page_id": page_id,
                                "finding_id": linked_finding.id,
                                "from_decision_status": linked_finding.decision_status,
                                "area_mask_id": new_mask_id,
                                "actor_user_id": actor_user_id,
                                "reason": mask_reason,
                                "created_at": now,
                            },
                        )

                    cursor.execute(
                        """
                        UPDATE redaction_outputs
                        SET
                          status = 'PENDING',
                          generated_at = NULL,
                          safeguarded_preview_key = NULL,
                          preview_sha256 = NULL,
                          updated_at = NOW()
                        WHERE run_id = %(run_id)s
                          AND page_id = %(page_id)s
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                        },
                    )
                    self._refresh_redaction_run_output_status(cursor=cursor, run_id=run_id)
                    self._refresh_redaction_page_second_review_requirement(
                        cursor=cursor,
                        run_id=run_id,
                        page_id=page_id,
                        actor_user_id=actor_user_id,
                    )
                    cursor.execute(
                        """
                        SELECT
                          id,
                          run_id,
                          page_id,
                          geometry_json,
                          mask_reason,
                          version_etag,
                          supersedes_area_mask_id,
                          superseded_by_area_mask_id,
                          created_by,
                          created_at,
                          updated_at
                        FROM redaction_area_masks
                        WHERE id = %(mask_id)s
                        LIMIT 1
                        """,
                        {"mask_id": new_mask_id},
                    )
                    new_mask_row = cursor.fetchone()
                    if linked_finding is not None:
                        cursor.execute(
                            """
                            SELECT
                              rf.id,
                              rf.run_id,
                              rf.page_id,
                              rf.line_id,
                              rf.category,
                              rf.span_start,
                              rf.span_end,
                              rf.span_basis_kind,
                              rf.span_basis_ref,
                              rf.confidence,
                              rf.basis_primary,
                              rf.basis_secondary_json,
                              rf.assist_explanation_key,
                              rf.assist_explanation_sha256,
                              rf.bbox_refs,
                              rf.token_refs_json,
                              rf.area_mask_id,
                              rf.decision_status,
                              rf.override_risk_classification,
                              rf.override_risk_reason_codes_json,
                              rf.decision_by,
                              rf.decision_at,
                              rf.decision_reason,
                              rf.decision_etag,
                              rf.updated_at,
                              rf.created_at
                            FROM redaction_findings AS rf
                            WHERE rf.id = %(finding_id)s
                            LIMIT 1
                            """,
                            {"finding_id": linked_finding.id},
                        )
                        finding_row = cursor.fetchone()
                        linked_finding = (
                            self._as_redaction_finding_record(finding_row)
                            if finding_row is not None
                            else None
                        )
                connection.commit()
        except (DocumentNotFoundError, DocumentRedactionRunConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Redaction area-mask creation failed."
            ) from error
        if new_mask_row is None:
            raise DocumentStoreUnavailableError("Redaction area-mask creation failed.")
        return self._as_redaction_area_mask_record(new_mask_row), linked_finding

    def revise_redaction_area_mask(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        mask_id: str,
        expected_version_etag: str,
        geometry_json: dict[str, object],
        mask_reason: str,
        actor_user_id: str,
        finding_id: str | None = None,
        expected_finding_decision_etag: str | None = None,
    ) -> tuple[RedactionAreaMaskRecord, RedactionFindingRecord | None]:
        self.ensure_schema()
        now = datetime.now(timezone.utc)
        event_id = str(uuid4())
        new_mask_id = str(uuid4())
        new_mask_etag = self._compute_redaction_etag(
            run_id,
            page_id,
            new_mask_id,
            actor_user_id,
            now.isoformat(),
        )
        linked_finding: RedactionFindingRecord | None = None
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT rrv.review_status
                        FROM redaction_run_reviews AS rrv
                        INNER JOIN redaction_runs AS rr
                          ON rr.id = rrv.run_id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                          AND rrv.run_id = %(run_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    run_review_row = cursor.fetchone()
                    if run_review_row is None:
                        raise DocumentNotFoundError("Redaction run not found.")
                    if self._assert_redaction_run_review_status(
                        str(run_review_row["review_status"])
                    ) == "APPROVED":
                        raise DocumentRedactionRunConflictError(
                            "Approved runs are locked and cannot be mutated."
                        )

                    cursor.execute(
                        """
                        SELECT
                          ram.id,
                          ram.run_id,
                          ram.page_id,
                          ram.geometry_json,
                          ram.mask_reason,
                          ram.version_etag,
                          ram.supersedes_area_mask_id,
                          ram.superseded_by_area_mask_id,
                          ram.created_by,
                          ram.created_at,
                          ram.updated_at
                        FROM redaction_area_masks AS ram
                        INNER JOIN redaction_runs AS rr
                          ON rr.id = ram.run_id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                          AND ram.run_id = %(run_id)s
                          AND ram.page_id = %(page_id)s
                          AND ram.id = %(mask_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                            "page_id": page_id,
                            "mask_id": mask_id,
                        },
                    )
                    mask_row = cursor.fetchone()
                    if mask_row is None:
                        raise DocumentNotFoundError("Redaction area mask not found.")
                    current_mask = self._as_redaction_area_mask_record(mask_row)
                    if current_mask.version_etag != expected_version_etag:
                        raise DocumentRedactionRunConflictError(
                            "Redaction area-mask update conflicts with a newer change."
                        )
                    if current_mask.superseded_by_area_mask_id is not None:
                        raise DocumentRedactionRunConflictError(
                            "Only the latest area-mask revision can be updated."
                        )
                    cursor.execute(
                        """
                        SELECT p.width, p.height
                        FROM pages AS p
                        INNER JOIN documents AS d
                          ON d.id = p.document_id
                        WHERE p.id = %(page_id)s
                          AND p.document_id = %(document_id)s
                          AND d.project_id = %(project_id)s
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "page_id": page_id,
                        },
                    )
                    page_row = cursor.fetchone()
                    if page_row is None:
                        raise DocumentNotFoundError("Document page not found.")
                    try:
                        normalized_geometry_json = normalize_area_mask_geometry(
                            geometry_json,
                            page_width=int(page_row["width"]),
                            page_height=int(page_row["height"]),
                        )
                    except RedactionGeometryValidationError as error:
                        raise DocumentRedactionRunConflictError(
                            f"Area-mask geometry is invalid: {error}"
                        ) from error

                    cursor.execute(
                        """
                        INSERT INTO redaction_area_masks (
                          id,
                          run_id,
                          page_id,
                          geometry_json,
                          mask_reason,
                          version_etag,
                          supersedes_area_mask_id,
                          superseded_by_area_mask_id,
                          created_by,
                          created_at,
                          updated_at
                        )
                        VALUES (
                          %(id)s,
                          %(run_id)s,
                          %(page_id)s,
                          %(geometry_json)s::jsonb,
                          %(mask_reason)s,
                          %(version_etag)s,
                          %(supersedes_area_mask_id)s,
                          NULL,
                          %(created_by)s,
                          %(created_at)s,
                          %(updated_at)s
                        )
                        """,
                        {
                            "id": new_mask_id,
                            "run_id": run_id,
                            "page_id": page_id,
                            "geometry_json": json.dumps(
                                normalized_geometry_json,
                                ensure_ascii=True,
                                separators=(",", ":"),
                                sort_keys=True,
                            ),
                            "mask_reason": mask_reason,
                            "version_etag": new_mask_etag,
                            "supersedes_area_mask_id": mask_id,
                            "created_by": actor_user_id,
                            "created_at": now,
                            "updated_at": now,
                        },
                    )
                    cursor.execute(
                        """
                        UPDATE redaction_area_masks
                        SET
                          superseded_by_area_mask_id = %(superseded_by_area_mask_id)s,
                          updated_at = NOW()
                        WHERE id = %(id)s
                        """,
                        {
                            "id": mask_id,
                            "superseded_by_area_mask_id": new_mask_id,
                        },
                    )

                    if isinstance(finding_id, str) and finding_id.strip():
                        cursor.execute(
                            """
                            SELECT
                              rf.id,
                              rf.run_id,
                              rf.page_id,
                              rf.line_id,
                              rf.category,
                              rf.span_start,
                              rf.span_end,
                              rf.span_basis_kind,
                              rf.span_basis_ref,
                              rf.confidence,
                              rf.basis_primary,
                              rf.basis_secondary_json,
                              rf.assist_explanation_key,
                              rf.assist_explanation_sha256,
                              rf.bbox_refs,
                              rf.token_refs_json,
                              rf.area_mask_id,
                              rf.decision_status,
                              rf.override_risk_classification,
                              rf.override_risk_reason_codes_json,
                              rf.decision_by,
                              rf.decision_at,
                              rf.decision_reason,
                              rf.decision_etag,
                              rf.updated_at,
                              rf.created_at
                            FROM redaction_findings AS rf
                            INNER JOIN redaction_runs AS rr
                              ON rr.id = rf.run_id
                            WHERE rr.project_id = %(project_id)s
                              AND rr.document_id = %(document_id)s
                              AND rf.run_id = %(run_id)s
                              AND rf.id = %(finding_id)s
                            LIMIT 1
                            FOR UPDATE
                            """,
                            {
                                "project_id": project_id,
                                "document_id": document_id,
                                "run_id": run_id,
                                "finding_id": finding_id.strip(),
                            },
                        )
                        finding_row = cursor.fetchone()
                        if finding_row is None:
                            raise DocumentNotFoundError(
                                "Linked redaction finding was not found."
                            )
                        linked_finding = self._as_redaction_finding_record(finding_row)
                        if (
                            isinstance(expected_finding_decision_etag, str)
                            and expected_finding_decision_etag.strip()
                            and linked_finding.decision_etag
                            != expected_finding_decision_etag.strip()
                        ):
                            raise DocumentRedactionRunConflictError(
                                "Linked redaction finding etag is stale."
                            )
                        next_finding_etag = self._compute_redaction_etag(
                            run_id,
                            linked_finding.id,
                            "AREA_MASK_UPDATED",
                            now.isoformat(),
                        )
                        override_risk_classification, override_risk_reason_codes = (
                            self._derive_redaction_override_risk(
                                to_decision_status="OVERRIDDEN",
                                category=linked_finding.category,
                                area_mask_id=new_mask_id,
                                basis_secondary_json=linked_finding.basis_secondary_json,
                                policy_snapshot_json=policy_snapshot_json,
                            )
                        )
                        cursor.execute(
                            """
                            UPDATE redaction_findings
                            SET
                              area_mask_id = %(area_mask_id)s,
                              decision_status = 'OVERRIDDEN',
                              decision_by = %(decision_by)s,
                              decision_at = %(decision_at)s,
                              decision_reason = %(decision_reason)s,
                              override_risk_classification = %(override_risk_classification)s,
                              override_risk_reason_codes_json = %(override_risk_reason_codes_json)s::jsonb,
                              decision_etag = %(decision_etag)s,
                              updated_at = NOW()
                            WHERE id = %(finding_id)s
                            """,
                            {
                                "finding_id": linked_finding.id,
                                "area_mask_id": new_mask_id,
                                "decision_by": actor_user_id,
                                "decision_at": now,
                                "decision_reason": mask_reason,
                                "override_risk_classification": override_risk_classification,
                                "override_risk_reason_codes_json": (
                                    json.dumps(
                                        override_risk_reason_codes,
                                        ensure_ascii=True,
                                        separators=(",", ":"),
                                        sort_keys=False,
                                    )
                                    if override_risk_reason_codes is not None
                                    else None
                                ),
                                "decision_etag": next_finding_etag,
                            },
                        )
                        cursor.execute(
                            """
                            INSERT INTO redaction_decision_events (
                              id,
                              run_id,
                              page_id,
                              finding_id,
                              from_decision_status,
                              to_decision_status,
                              action_type,
                              area_mask_id,
                              actor_user_id,
                              reason,
                              created_at
                            )
                            VALUES (
                              %(id)s,
                              %(run_id)s,
                              %(page_id)s,
                              %(finding_id)s,
                              %(from_decision_status)s,
                              'OVERRIDDEN',
                              'MASK',
                              %(area_mask_id)s,
                              %(actor_user_id)s,
                              %(reason)s,
                              %(created_at)s
                            )
                            """,
                            {
                                "id": event_id,
                                "run_id": run_id,
                                "page_id": page_id,
                                "finding_id": linked_finding.id,
                                "from_decision_status": linked_finding.decision_status,
                                "area_mask_id": new_mask_id,
                                "actor_user_id": actor_user_id,
                                "reason": mask_reason,
                                "created_at": now,
                            },
                        )

                    cursor.execute(
                        """
                        UPDATE redaction_outputs
                        SET
                          status = 'PENDING',
                          generated_at = NULL,
                          safeguarded_preview_key = NULL,
                          preview_sha256 = NULL,
                          updated_at = NOW()
                        WHERE run_id = %(run_id)s
                          AND page_id = %(page_id)s
                        """,
                        {
                            "run_id": run_id,
                            "page_id": page_id,
                        },
                    )
                    self._refresh_redaction_run_output_status(cursor=cursor, run_id=run_id)
                    self._refresh_redaction_page_second_review_requirement(
                        cursor=cursor,
                        run_id=run_id,
                        page_id=page_id,
                        actor_user_id=actor_user_id,
                    )
                    cursor.execute(
                        """
                        SELECT
                          id,
                          run_id,
                          page_id,
                          geometry_json,
                          mask_reason,
                          version_etag,
                          supersedes_area_mask_id,
                          superseded_by_area_mask_id,
                          created_by,
                          created_at,
                          updated_at
                        FROM redaction_area_masks
                        WHERE id = %(mask_id)s
                        LIMIT 1
                        """,
                        {"mask_id": new_mask_id},
                    )
                    new_mask_row = cursor.fetchone()

                    if linked_finding is not None:
                        cursor.execute(
                            """
                            SELECT
                              rf.id,
                              rf.run_id,
                              rf.page_id,
                              rf.line_id,
                              rf.category,
                              rf.span_start,
                              rf.span_end,
                              rf.span_basis_kind,
                              rf.span_basis_ref,
                              rf.confidence,
                              rf.basis_primary,
                              rf.basis_secondary_json,
                              rf.assist_explanation_key,
                              rf.assist_explanation_sha256,
                              rf.bbox_refs,
                              rf.token_refs_json,
                              rf.area_mask_id,
                              rf.decision_status,
                              rf.override_risk_classification,
                              rf.override_risk_reason_codes_json,
                              rf.decision_by,
                              rf.decision_at,
                              rf.decision_reason,
                              rf.decision_etag,
                              rf.updated_at,
                              rf.created_at
                            FROM redaction_findings AS rf
                            WHERE rf.id = %(finding_id)s
                            LIMIT 1
                            """,
                            {"finding_id": linked_finding.id},
                        )
                        finding_row = cursor.fetchone()
                        linked_finding = (
                            self._as_redaction_finding_record(finding_row)
                            if finding_row is not None
                            else None
                        )
                connection.commit()
        except (DocumentNotFoundError, DocumentRedactionRunConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Redaction area-mask revision failed."
            ) from error
        if new_mask_row is None:
            raise DocumentStoreUnavailableError("Redaction area-mask revision failed.")
        return self._as_redaction_area_mask_record(new_mask_row), linked_finding

    def list_redaction_decision_events(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str | None = None,
    ) -> list[RedactionDecisionEventRecord]:
        self.ensure_schema()
        where_clause = (
            "rr.project_id = %(project_id)s AND rr.document_id = %(document_id)s "
            "AND rde.run_id = %(run_id)s"
        )
        params: dict[str, object] = {
            "project_id": project_id,
            "document_id": document_id,
            "run_id": run_id,
        }
        if isinstance(page_id, str) and page_id.strip():
            where_clause += " AND rde.page_id = %(page_id)s"
            params["page_id"] = page_id.strip()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        f"""
                        SELECT
                          rde.id,
                          rde.run_id,
                          rde.page_id,
                          rde.finding_id,
                          rde.from_decision_status,
                          rde.to_decision_status,
                          rde.action_type,
                          rde.area_mask_id,
                          rde.actor_user_id,
                          rde.reason,
                          rde.created_at
                        FROM redaction_decision_events AS rde
                        INNER JOIN redaction_runs AS rr
                          ON rr.id = rde.run_id
                        WHERE {where_clause}
                        ORDER BY rde.created_at ASC, rde.id ASC
                        """,
                        params,
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Redaction decision event listing failed."
            ) from error
        return [self._as_redaction_decision_event_record(row) for row in rows]

    def list_redaction_page_review_events(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str | None = None,
    ) -> list[RedactionPageReviewEventRecord]:
        self.ensure_schema()
        where_clause = (
            "rr.project_id = %(project_id)s AND rr.document_id = %(document_id)s "
            "AND rpre.run_id = %(run_id)s"
        )
        params: dict[str, object] = {
            "project_id": project_id,
            "document_id": document_id,
            "run_id": run_id,
        }
        if isinstance(page_id, str) and page_id.strip():
            where_clause += " AND rpre.page_id = %(page_id)s"
            params["page_id"] = page_id.strip()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        f"""
                        SELECT
                          rpre.id,
                          rpre.run_id,
                          rpre.page_id,
                          rpre.event_type,
                          rpre.actor_user_id,
                          rpre.reason,
                          rpre.created_at
                        FROM redaction_page_review_events AS rpre
                        INNER JOIN redaction_runs AS rr
                          ON rr.id = rpre.run_id
                        WHERE {where_clause}
                        ORDER BY rpre.created_at ASC, rpre.id ASC
                        """,
                        params,
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Redaction page-review event listing failed."
            ) from error
        return [self._as_redaction_page_review_event_record(row) for row in rows]

    def list_redaction_run_review_events(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> list[RedactionRunReviewEventRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          rrre.id,
                          rrre.run_id,
                          rrre.event_type,
                          rrre.actor_user_id,
                          rrre.reason,
                          rrre.created_at
                        FROM redaction_run_review_events AS rrre
                        INNER JOIN redaction_runs AS rr
                          ON rr.id = rrre.run_id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                          AND rrre.run_id = %(run_id)s
                        ORDER BY rrre.created_at ASC, rrre.id ASC
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Redaction run-review event listing failed."
            ) from error
        return [self._as_redaction_run_review_event_record(row) for row in rows]

    def list_redaction_run_output_events(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> list[RedactionRunOutputEventRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          rroe.id,
                          rroe.run_id,
                          rroe.event_type,
                          rroe.from_status,
                          rroe.to_status,
                          rroe.reason,
                          rroe.actor_user_id,
                          rroe.created_at
                        FROM redaction_run_output_events AS rroe
                        INNER JOIN redaction_runs AS rr
                          ON rr.id = rroe.run_id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                          AND rroe.run_id = %(run_id)s
                        ORDER BY rroe.created_at ASC, rroe.id ASC
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Redaction run-output event listing failed."
            ) from error
        return [self._as_redaction_run_output_event_record(row) for row in rows]

    def reset_redaction_outputs_for_reviewed_generation(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> RedactionRunOutputRecord:
        self.ensure_schema()
        now = datetime.now(timezone.utc)
        run_output_row: dict[str, object] | None = None
        previous_run_output_status: RedactionOutputStatus | None = None
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          rrv.review_status
                        FROM redaction_run_reviews AS rrv
                        INNER JOIN redaction_runs AS rr
                          ON rr.id = rrv.run_id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                          AND rrv.run_id = %(run_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    review_row = cursor.fetchone()
                    if review_row is None:
                        raise DocumentNotFoundError("Redaction run not found.")
                    review_status = self._assert_redaction_run_review_status(
                        str(review_row["review_status"])
                    )
                    if review_status != "APPROVED":
                        raise DocumentRedactionRunConflictError(
                            "Reviewed output regeneration requires APPROVED run review."
                        )
                    cursor.execute(
                        """
                        SELECT status
                        FROM redaction_run_outputs
                        WHERE run_id = %(run_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {"run_id": run_id},
                    )
                    prior_run_output_row = cursor.fetchone()
                    if prior_run_output_row is None:
                        raise DocumentNotFoundError("Redaction run output not found.")
                    previous_run_output_status = self._assert_redaction_output_status(
                        str(prior_run_output_row["status"])
                    )
                    cursor.execute(
                        """
                        UPDATE redaction_outputs
                        SET
                          status = 'PENDING',
                          safeguarded_preview_key = NULL,
                          preview_sha256 = NULL,
                          started_at = %(started_at)s,
                          generated_at = NULL,
                          canceled_by = NULL,
                          canceled_at = NULL,
                          failure_reason = NULL,
                          updated_at = NOW()
                        WHERE run_id = %(run_id)s
                        """,
                        {
                            "run_id": run_id,
                            "started_at": now,
                        },
                    )
                    cursor.execute(
                        """
                        UPDATE redaction_run_outputs
                        SET
                          status = 'PENDING',
                          output_manifest_key = NULL,
                          output_manifest_sha256 = NULL,
                          started_at = %(started_at)s,
                          generated_at = NULL,
                          canceled_by = NULL,
                          canceled_at = NULL,
                          failure_reason = NULL,
                          updated_at = NOW()
                        WHERE run_id = %(run_id)s
                        """,
                        {
                            "run_id": run_id,
                            "started_at": now,
                        },
                    )
                    self._append_redaction_run_output_event(
                        cursor=cursor,
                        run_id=run_id,
                        from_status=previous_run_output_status,
                        to_status="PENDING",
                        reason="Reviewed output generation triggered from approved snapshot.",
                    )
                    self._refresh_redaction_run_output_status(cursor=cursor, run_id=run_id)
                    cursor.execute(
                        """
                        SELECT
                          rro.run_id,
                          rro.status,
                          rro.output_manifest_key,
                          rro.output_manifest_sha256,
                          rro.page_count,
                          rro.started_at,
                          rro.generated_at,
                          rro.canceled_by,
                          rro.canceled_at,
                          rro.failure_reason,
                          rro.created_at,
                          rro.updated_at
                        FROM redaction_run_outputs AS rro
                        WHERE rro.run_id = %(run_id)s
                        LIMIT 1
                        """,
                        {"run_id": run_id},
                    )
                    run_output_row = cursor.fetchone()
                connection.commit()
        except (DocumentNotFoundError, DocumentRedactionRunConflictError):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Redaction reviewed output reset failed."
            ) from error
        if run_output_row is None:
            raise DocumentStoreUnavailableError("Redaction reviewed output reset failed.")
        return self._as_redaction_run_output_record(run_output_row)

    def set_redaction_output_projection(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        status: RedactionOutputStatus,
        safeguarded_preview_key: str | None,
        preview_sha256: str | None,
        failure_reason: str | None = None,
    ) -> RedactionOutputRecord:
        self.ensure_schema()
        output_row: dict[str, object] | None = None
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE redaction_outputs AS ro
                        SET
                          status = %(status)s,
                          safeguarded_preview_key = %(safeguarded_preview_key)s,
                          preview_sha256 = %(preview_sha256)s,
                          generated_at = CASE
                            WHEN %(status)s = 'READY' THEN NOW()
                            ELSE NULL
                          END,
                          failure_reason = %(failure_reason)s,
                          canceled_by = CASE
                            WHEN %(status)s = 'CANCELED' THEN ro.canceled_by
                            ELSE NULL
                          END,
                          canceled_at = CASE
                            WHEN %(status)s = 'CANCELED' THEN ro.canceled_at
                            ELSE NULL
                          END,
                          updated_at = NOW()
                        WHERE ro.run_id = %(run_id)s
                          AND ro.page_id = %(page_id)s
                          AND EXISTS (
                            SELECT 1
                            FROM redaction_runs AS rr
                            WHERE rr.id = ro.run_id
                              AND rr.project_id = %(project_id)s
                              AND rr.document_id = %(document_id)s
                          )
                        RETURNING
                          ro.run_id,
                          ro.page_id,
                          ro.status,
                          ro.safeguarded_preview_key,
                          ro.preview_sha256,
                          ro.started_at,
                          ro.generated_at,
                          ro.canceled_by,
                          ro.canceled_at,
                          ro.failure_reason,
                          ro.created_at,
                          ro.updated_at
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                            "page_id": page_id,
                            "status": status,
                            "safeguarded_preview_key": safeguarded_preview_key,
                            "preview_sha256": preview_sha256,
                            "failure_reason": failure_reason,
                        },
                    )
                    output_row = cursor.fetchone()
                    if output_row is None:
                        raise DocumentNotFoundError("Redaction output was not found.")
                    self._refresh_redaction_run_output_status(cursor=cursor, run_id=run_id)
                connection.commit()
        except (DocumentNotFoundError,):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Redaction output update failed.") from error
        if output_row is None:
            raise DocumentStoreUnavailableError("Redaction output update failed.")
        return self._as_redaction_output_record(output_row)

    def get_redaction_output(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> RedactionOutputRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          ro.run_id,
                          ro.page_id,
                          ro.status,
                          ro.safeguarded_preview_key,
                          ro.preview_sha256,
                          ro.started_at,
                          ro.generated_at,
                          ro.canceled_by,
                          ro.canceled_at,
                          ro.failure_reason,
                          ro.created_at,
                          ro.updated_at
                        FROM redaction_outputs AS ro
                        INNER JOIN redaction_runs AS rr
                          ON rr.id = ro.run_id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                          AND ro.run_id = %(run_id)s
                          AND ro.page_id = %(page_id)s
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
            raise DocumentStoreUnavailableError("Redaction output lookup failed.") from error
        if row is None:
            return None
        return self._as_redaction_output_record(row)

    def list_redaction_outputs(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> list[RedactionOutputRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          ro.run_id,
                          ro.page_id,
                          ro.status,
                          ro.safeguarded_preview_key,
                          ro.preview_sha256,
                          ro.started_at,
                          ro.generated_at,
                          ro.canceled_by,
                          ro.canceled_at,
                          ro.failure_reason,
                          ro.created_at,
                          ro.updated_at
                        FROM redaction_outputs AS ro
                        INNER JOIN redaction_runs AS rr
                          ON rr.id = ro.run_id
                        INNER JOIN pages AS p
                          ON p.id = ro.page_id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                          AND ro.run_id = %(run_id)s
                        ORDER BY p.page_index ASC, ro.page_id ASC
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError("Redaction output listing failed.") from error
        return [self._as_redaction_output_record(row) for row in rows]

    def get_redaction_run_output(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> RedactionRunOutputRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          rro.run_id,
                          rro.status,
                          rro.output_manifest_key,
                          rro.output_manifest_sha256,
                          rro.page_count,
                          rro.started_at,
                          rro.generated_at,
                          rro.canceled_by,
                          rro.canceled_at,
                          rro.failure_reason,
                          rro.created_at,
                          rro.updated_at
                        FROM redaction_run_outputs AS rro
                        INNER JOIN redaction_runs AS rr
                          ON rr.id = rro.run_id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                          AND rro.run_id = %(run_id)s
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
            raise DocumentStoreUnavailableError(
                "Redaction run output lookup failed."
            ) from error
        if row is None:
            return None
        return self._as_redaction_run_output_record(row)

    def set_redaction_run_output_status(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        status: RedactionOutputStatus,
        failure_reason: str | None = None,
        actor_user_id: str | None = None,
    ) -> RedactionRunOutputRecord:
        self.ensure_schema()
        next_row: dict[str, object] | None = None
        now = datetime.now(timezone.utc)
        trimmed_reason = (
            failure_reason.strip()[:600]
            if isinstance(failure_reason, str) and failure_reason.strip()
            else None
        )
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          rro.run_id,
                          rro.status,
                          rro.started_at
                        FROM redaction_run_outputs AS rro
                        INNER JOIN redaction_runs AS rr
                          ON rr.id = rro.run_id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                          AND rro.run_id = %(run_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "document_id": document_id,
                            "run_id": run_id,
                        },
                    )
                    current_row = cursor.fetchone()
                    if current_row is None:
                        raise DocumentNotFoundError("Redaction run output not found.")
                    previous_status = self._assert_redaction_output_status(
                        str(current_row["status"])
                    )
                    previous_started_at = current_row.get("started_at")
                    started_at: datetime | None
                    if status == "PENDING":
                        if (
                            previous_status == "PENDING"
                            and isinstance(previous_started_at, datetime)
                        ):
                            started_at = previous_started_at
                        else:
                            started_at = now
                    elif isinstance(previous_started_at, datetime):
                        started_at = previous_started_at
                    else:
                        started_at = now

                    cursor.execute(
                        """
                        UPDATE redaction_run_outputs
                        SET
                          status = %(status)s,
                          output_manifest_key = CASE
                            WHEN %(status)s = 'READY' THEN output_manifest_key
                            ELSE NULL
                          END,
                          output_manifest_sha256 = CASE
                            WHEN %(status)s = 'READY' THEN output_manifest_sha256
                            ELSE NULL
                          END,
                          started_at = %(started_at)s,
                          generated_at = CASE
                            WHEN %(status)s = 'READY' THEN NOW()
                            ELSE NULL
                          END,
                          canceled_by = CASE
                            WHEN %(status)s = 'CANCELED' THEN %(actor_user_id)s
                            ELSE NULL
                          END,
                          canceled_at = CASE
                            WHEN %(status)s = 'CANCELED' THEN NOW()
                            ELSE NULL
                          END,
                          failure_reason = %(failure_reason)s,
                          updated_at = NOW()
                        WHERE run_id = %(run_id)s
                        RETURNING
                          run_id,
                          status,
                          output_manifest_key,
                          output_manifest_sha256,
                          page_count,
                          started_at,
                          generated_at,
                          canceled_by,
                          canceled_at,
                          failure_reason,
                          created_at,
                          updated_at
                        """,
                        {
                            "run_id": run_id,
                            "status": status,
                            "started_at": started_at,
                            "actor_user_id": actor_user_id,
                            "failure_reason": trimmed_reason,
                        },
                    )
                    next_row = cursor.fetchone()
                    if next_row is None:
                        raise DocumentStoreUnavailableError(
                            "Redaction run output status update failed."
                        )
                    if previous_status != status:
                        self._append_redaction_run_output_event(
                            cursor=cursor,
                            run_id=run_id,
                            from_status=previous_status,
                            to_status=status,
                            reason=trimmed_reason,
                            actor_user_id=actor_user_id,
                            created_at=now,
                        )
                connection.commit()
        except (DocumentNotFoundError,):
            raise
        except psycopg.Error as error:
            raise DocumentStoreUnavailableError(
                "Redaction run output status update failed."
            ) from error
        if next_row is None:
            raise DocumentStoreUnavailableError("Redaction run output status update failed.")
        return self._as_redaction_run_output_record(next_row)
