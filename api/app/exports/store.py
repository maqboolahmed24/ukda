from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from app.core.config import Settings
from app.core.storage_boundaries import resolve_storage_boundary
from app.documents.governance import GovernanceStore, GovernanceStoreUnavailableError
from app.exports.models import (
    BundleEventRecord,
    BundleEventType,
    BundleProfileRecord,
    BundleValidationProjectionRecord,
    BundleValidationProjectionStatus,
    BundleValidationRunRecord,
    BundleValidationRunStatus,
    BundleVerificationProjectionRecord,
    BundleVerificationProjectionStatus,
    BundleVerificationRunRecord,
    BundleVerificationRunStatus,
    DepositBundleKind,
    DepositBundleRecord,
    DepositBundleStatus,
    ExportCandidateEligibilityStatus,
    ExportCandidateKind,
    ExportCandidateSnapshotRecord,
    ExportCandidateSourceArtifactKind,
    ExportCandidateSourcePhase,
    ExportOperationsMaintenanceResult,
    ExportOperationsStatusRecord,
    ExportReceiptRecord,
    ExportRequestDecision,
    ExportRequestEventRecord,
    ExportRequestEventType,
    ExportRequestListPage,
    ExportRequestRecord,
    ExportRequestReviewEventRecord,
    ExportRequestReviewEventType,
    ExportRequestReviewPath,
    ExportRequestReviewRecord,
    ExportRequestReviewStage,
    ExportRequestReviewStatus,
    ExportRequestRiskClassification,
    ExportRequestStatus,
    ProvenanceProofRecord,
)
from app.exports.deposit_profiles import (
    BundleProfileValidationOutput,
    build_bundle_profile_snapshot,
    bundle_profile_snapshot_bytes,
    bundle_profile_snapshot_sha256,
    get_bundle_profile,
    list_bundle_profiles,
    validate_bundle_artifact_against_profile,
)
from app.exports.replay import (
    classify_verification_failure,
    run_bundle_replay_drill as run_bundle_replay_drill_payload,
)
from app.exports.provenance import (
    MerkleTreeResult,
    ProvenanceLeaf,
    build_merkle_tree,
    build_proof_artifact_payload,
    canonical_json_bytes,
    normalize_leaf,
    sign_root_sha256,
)
from app.exports.verification import verify_bundle_archive_bytes

EXPORT_SCHEMA_STATEMENTS = (
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_export_candidate_snapshot_source
      ON export_candidate_snapshots(project_id, source_artifact_kind, source_artifact_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_export_candidate_snapshots_supersedes
      ON export_candidate_snapshots(project_id, supersedes_candidate_snapshot_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS export_requests (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      candidate_snapshot_id TEXT NOT NULL REFERENCES export_candidate_snapshots(id),
      candidate_origin_phase TEXT NOT NULL CHECK (
        candidate_origin_phase IN ('PHASE6', 'PHASE7', 'PHASE9', 'PHASE10')
      ),
      candidate_kind TEXT NOT NULL CHECK (
        candidate_kind IN (
          'SAFEGUARDED_PREVIEW',
          'POLICY_RERUN',
          'DEPOSIT_BUNDLE',
          'SAFEGUARDED_DERIVATIVE'
        )
      ),
      bundle_profile TEXT,
      risk_classification TEXT NOT NULL CHECK (risk_classification IN ('STANDARD', 'HIGH')),
      risk_reason_codes_json JSONB NOT NULL DEFAULT '[]'::jsonb,
      review_path TEXT NOT NULL CHECK (review_path IN ('SINGLE', 'DUAL')),
      requires_second_review BOOLEAN NOT NULL DEFAULT FALSE,
      supersedes_export_request_id TEXT REFERENCES export_requests(id),
      superseded_by_export_request_id TEXT REFERENCES export_requests(id),
      request_revision INTEGER NOT NULL CHECK (request_revision >= 1),
      purpose_statement TEXT NOT NULL,
      status TEXT NOT NULL CHECK (
        status IN (
          'SUBMITTED',
          'RESUBMITTED',
          'IN_REVIEW',
          'APPROVED',
          'EXPORTED',
          'REJECTED',
          'RETURNED'
        )
      ),
      submitted_by TEXT NOT NULL REFERENCES users(id),
      submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      first_review_started_by TEXT REFERENCES users(id),
      first_review_started_at TIMESTAMPTZ,
      sla_due_at TIMESTAMPTZ,
      last_queue_activity_at TIMESTAMPTZ,
      retention_until TIMESTAMPTZ,
      final_review_id TEXT,
      final_decision_by TEXT REFERENCES users(id),
      final_decision_at TIMESTAMPTZ,
      final_decision_reason TEXT,
      final_return_comment TEXT,
      release_pack_key TEXT NOT NULL,
      release_pack_sha256 TEXT NOT NULL,
      release_pack_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      release_pack_created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      receipt_id TEXT,
      receipt_key TEXT,
      receipt_sha256 TEXT,
      receipt_created_by TEXT REFERENCES users(id),
      receipt_created_at TIMESTAMPTZ,
      exported_at TIMESTAMPTZ,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_export_requests_scope_submitted
      ON export_requests(project_id, submitted_at DESC, id DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_export_requests_scope_requester
      ON export_requests(project_id, submitted_by, submitted_at DESC, id DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_export_requests_scope_status
      ON export_requests(project_id, status, submitted_at DESC, id DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS export_request_events (
      id TEXT PRIMARY KEY,
      export_request_id TEXT NOT NULL REFERENCES export_requests(id) ON DELETE CASCADE,
      event_type TEXT NOT NULL CHECK (
        event_type IN (
          'REQUEST_SUBMITTED',
          'REQUEST_REVIEW_STARTED',
          'REQUEST_RESUBMITTED',
          'REQUEST_APPROVED',
          'REQUEST_EXPORTED',
          'REQUEST_REJECTED',
          'REQUEST_RETURNED',
          'REQUEST_RECEIPT_ATTACHED',
          'REQUEST_REMINDER_SENT',
          'REQUEST_ESCALATED'
        )
      ),
      from_status TEXT,
      to_status TEXT NOT NULL,
      actor_user_id TEXT REFERENCES users(id),
      reason TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_export_request_events_scope
      ON export_request_events(export_request_id, created_at DESC, id DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS export_receipts (
      id TEXT PRIMARY KEY,
      export_request_id TEXT NOT NULL REFERENCES export_requests(id) ON DELETE CASCADE,
      attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
      supersedes_receipt_id TEXT REFERENCES export_receipts(id),
      superseded_by_receipt_id TEXT REFERENCES export_receipts(id),
      receipt_key TEXT NOT NULL,
      receipt_sha256 TEXT NOT NULL,
      created_by TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      exported_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_export_receipts_attempt
      ON export_receipts(export_request_id, attempt_number)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_export_receipts_scope
      ON export_receipts(export_request_id, created_at DESC, id DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS provenance_proofs (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      export_request_id TEXT NOT NULL REFERENCES export_requests(id) ON DELETE CASCADE,
      candidate_snapshot_id TEXT NOT NULL REFERENCES export_candidate_snapshots(id),
      attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
      supersedes_proof_id TEXT REFERENCES provenance_proofs(id),
      superseded_by_proof_id TEXT REFERENCES provenance_proofs(id),
      root_sha256 TEXT NOT NULL,
      signature_key_ref TEXT NOT NULL,
      signature_bytes_key TEXT NOT NULL,
      proof_artifact_key TEXT NOT NULL,
      proof_artifact_sha256 TEXT NOT NULL,
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE (export_request_id, attempt_number)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_provenance_proofs_scope
      ON provenance_proofs(project_id, export_request_id, created_at DESC, id DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_provenance_proofs_current
      ON provenance_proofs(export_request_id)
      WHERE superseded_by_proof_id IS NULL
    """,
    """
    CREATE TABLE IF NOT EXISTS deposit_bundles (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      export_request_id TEXT NOT NULL REFERENCES export_requests(id) ON DELETE CASCADE,
      candidate_snapshot_id TEXT NOT NULL REFERENCES export_candidate_snapshots(id),
      provenance_proof_id TEXT NOT NULL REFERENCES provenance_proofs(id),
      provenance_proof_artifact_sha256 TEXT NOT NULL,
      bundle_kind TEXT NOT NULL CHECK (
        bundle_kind IN ('CONTROLLED_EVIDENCE', 'SAFEGUARDED_DEPOSIT')
      ),
      status TEXT NOT NULL CHECK (
        status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED')
      ),
      attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
      supersedes_bundle_id TEXT REFERENCES deposit_bundles(id),
      superseded_by_bundle_id TEXT REFERENCES deposit_bundles(id),
      bundle_key TEXT,
      bundle_sha256 TEXT,
      failure_reason TEXT,
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      started_at TIMESTAMPTZ,
      finished_at TIMESTAMPTZ,
      canceled_by TEXT REFERENCES users(id),
      canceled_at TIMESTAMPTZ,
      UNIQUE (export_request_id, candidate_snapshot_id, bundle_kind, attempt_number)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_deposit_bundles_scope
      ON deposit_bundles(project_id, export_request_id, candidate_snapshot_id, bundle_kind, created_at DESC, id DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_deposit_bundles_current
      ON deposit_bundles(export_request_id, candidate_snapshot_id, bundle_kind)
      WHERE superseded_by_bundle_id IS NULL
    """,
    """
    CREATE TABLE IF NOT EXISTS bundle_verification_projections (
      bundle_id TEXT PRIMARY KEY REFERENCES deposit_bundles(id) ON DELETE CASCADE,
      status TEXT NOT NULL CHECK (status IN ('PENDING', 'VERIFIED', 'FAILED')),
      last_verification_run_id TEXT,
      verified_at TIMESTAMPTZ,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS bundle_verification_runs (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      bundle_id TEXT NOT NULL REFERENCES deposit_bundles(id) ON DELETE CASCADE,
      attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
      supersedes_verification_run_id TEXT REFERENCES bundle_verification_runs(id),
      superseded_by_verification_run_id TEXT REFERENCES bundle_verification_runs(id),
      status TEXT NOT NULL CHECK (
        status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED')
      ),
      result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      started_at TIMESTAMPTZ,
      finished_at TIMESTAMPTZ,
      canceled_by TEXT REFERENCES users(id),
      canceled_at TIMESTAMPTZ,
      failure_reason TEXT,
      UNIQUE (bundle_id, attempt_number)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_bundle_verification_runs_scope
      ON bundle_verification_runs(bundle_id, attempt_number DESC, created_at DESC, id DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_bundle_verification_runs_current
      ON bundle_verification_runs(bundle_id)
      WHERE superseded_by_verification_run_id IS NULL
    """,
    """
    CREATE TABLE IF NOT EXISTS bundle_validation_runs (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      bundle_id TEXT NOT NULL REFERENCES deposit_bundles(id) ON DELETE CASCADE,
      profile_id TEXT NOT NULL,
      profile_snapshot_key TEXT NOT NULL,
      profile_snapshot_sha256 TEXT NOT NULL,
      status TEXT NOT NULL CHECK (
        status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED')
      ),
      attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
      supersedes_validation_run_id TEXT REFERENCES bundle_validation_runs(id),
      superseded_by_validation_run_id TEXT REFERENCES bundle_validation_runs(id),
      result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      failure_reason TEXT,
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      started_at TIMESTAMPTZ,
      finished_at TIMESTAMPTZ,
      canceled_by TEXT REFERENCES users(id),
      canceled_at TIMESTAMPTZ,
      UNIQUE (bundle_id, profile_id, attempt_number)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_bundle_validation_runs_scope
      ON bundle_validation_runs(bundle_id, profile_id, attempt_number DESC, created_at DESC, id DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_bundle_validation_runs_current
      ON bundle_validation_runs(bundle_id, profile_id)
      WHERE superseded_by_validation_run_id IS NULL
    """,
    """
    CREATE TABLE IF NOT EXISTS bundle_validation_projections (
      bundle_id TEXT NOT NULL REFERENCES deposit_bundles(id) ON DELETE CASCADE,
      profile_id TEXT NOT NULL,
      status TEXT NOT NULL CHECK (status IN ('PENDING', 'READY', 'FAILED')),
      last_validation_run_id TEXT,
      ready_at TIMESTAMPTZ,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (bundle_id, profile_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS bundle_events (
      id TEXT PRIMARY KEY,
      bundle_id TEXT NOT NULL REFERENCES deposit_bundles(id) ON DELETE CASCADE,
      event_type TEXT NOT NULL CHECK (
        event_type IN (
          'BUNDLE_BUILD_QUEUED',
          'BUNDLE_REBUILD_REQUESTED',
          'BUNDLE_BUILD_STARTED',
          'BUNDLE_BUILD_SUCCEEDED',
          'BUNDLE_BUILD_FAILED',
          'BUNDLE_BUILD_CANCELED',
          'BUNDLE_VERIFICATION_STARTED',
          'BUNDLE_VERIFICATION_SUCCEEDED',
          'BUNDLE_VERIFICATION_FAILED',
          'BUNDLE_VERIFICATION_CANCELED',
          'BUNDLE_VALIDATION_STARTED',
          'BUNDLE_VALIDATION_SUCCEEDED',
          'BUNDLE_VALIDATION_FAILED',
          'BUNDLE_VALIDATION_CANCELED'
        )
      ),
      verification_run_id TEXT,
      validation_run_id TEXT,
      actor_user_id TEXT REFERENCES users(id),
      reason TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_bundle_events_scope
      ON bundle_events(bundle_id, created_at ASC, id ASC)
    """,
    """
    CREATE TABLE IF NOT EXISTS export_request_reviews (
      id TEXT PRIMARY KEY,
      export_request_id TEXT NOT NULL REFERENCES export_requests(id) ON DELETE CASCADE,
      review_stage TEXT NOT NULL CHECK (review_stage IN ('PRIMARY', 'SECONDARY')),
      is_required BOOLEAN NOT NULL,
      status TEXT NOT NULL CHECK (
        status IN ('PENDING', 'IN_REVIEW', 'APPROVED', 'RETURNED', 'REJECTED')
      ),
      assigned_reviewer_user_id TEXT REFERENCES users(id),
      assigned_at TIMESTAMPTZ,
      acted_by_user_id TEXT REFERENCES users(id),
      acted_at TIMESTAMPTZ,
      decision_reason TEXT,
      return_comment TEXT,
      review_etag TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_export_request_reviews_stage
      ON export_request_reviews(export_request_id, review_stage)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_export_request_reviews_scope
      ON export_request_reviews(export_request_id, review_stage, created_at ASC, id ASC)
    """,
    """
    CREATE TABLE IF NOT EXISTS export_request_review_events (
      id TEXT PRIMARY KEY,
      review_id TEXT NOT NULL REFERENCES export_request_reviews(id) ON DELETE CASCADE,
      export_request_id TEXT NOT NULL REFERENCES export_requests(id) ON DELETE CASCADE,
      review_stage TEXT NOT NULL CHECK (review_stage IN ('PRIMARY', 'SECONDARY')),
      event_type TEXT NOT NULL CHECK (
        event_type IN (
          'REVIEW_CREATED',
          'REVIEW_CLAIMED',
          'REVIEW_STARTED',
          'REVIEW_APPROVED',
          'REVIEW_REJECTED',
          'REVIEW_RETURNED',
          'REVIEW_RELEASED'
        )
      ),
      actor_user_id TEXT REFERENCES users(id),
      assigned_reviewer_user_id TEXT REFERENCES users(id),
      decision_reason TEXT,
      return_comment TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_export_request_review_events_scope
      ON export_request_review_events(export_request_id, review_id, created_at DESC, id DESC)
    """,
)


class ExportStoreUnavailableError(RuntimeError):
    """Export persistence is unavailable."""


class ExportStoreNotFoundError(RuntimeError):
    """Export record was not found."""


class ExportStoreConflictError(RuntimeError):
    """Export mutation violated request lineage constraints."""


class ExportStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._boundary = resolve_storage_boundary(settings)
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
    def _canonical_json_bytes(payload: dict[str, object]) -> bytes:
        return json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    @staticmethod
    def _sha256_hex(payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    def _resolve_storage_path(self, object_key: str) -> Path:
        return self._settings.storage_controlled_root / object_key.lstrip("/")

    def _assert_app_writable_key(self, *, object_key: str) -> None:
        if not self._boundary.can_write(writer="app", object_key=object_key):
            raise ExportStoreUnavailableError(
                "Object key violates controlled storage boundaries."
            )

    def _write_storage_object_idempotent(self, *, object_key: str, payload: bytes) -> None:
        self._assert_app_writable_key(object_key=object_key)
        destination = self._resolve_storage_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            try:
                existing_payload = destination.read_bytes()
            except OSError as error:
                raise ExportStoreUnavailableError(
                    "Existing provenance object bytes could not be read."
                ) from error
            if existing_payload != payload:
                raise ExportStoreUnavailableError(
                    "Existing provenance object bytes differ from deterministic payload."
                )
            return
        try:
            with destination.open("xb") as handle:
                handle.write(payload)
            destination.chmod(0o600)
        except OSError as error:
            raise ExportStoreUnavailableError("Provenance object bytes could not be persisted.") from error

    def _read_storage_object_bytes(self, *, object_key: str) -> bytes:
        path = self._resolve_storage_path(object_key)
        try:
            return path.read_bytes()
        except OSError as error:
            raise ExportStoreUnavailableError("Provenance object bytes could not be read.") from error

    def _build_provenance_signature_key(
        self,
        *,
        project_id: str,
        export_request_id: str,
        proof_id: str,
    ) -> str:
        prefix = self._settings.storage_controlled_derived_prefix.strip("/ ")
        object_key = (
            f"{prefix}/provenance/{project_id}/export-requests/{export_request_id}/"
            f"proofs/{proof_id}/signature.bin"
        )
        self._assert_app_writable_key(object_key=object_key)
        return object_key

    def _build_provenance_artifact_key(
        self,
        *,
        project_id: str,
        export_request_id: str,
        proof_id: str,
    ) -> str:
        prefix = self._settings.storage_controlled_derived_prefix.strip("/ ")
        object_key = (
            f"{prefix}/provenance/{project_id}/export-requests/{export_request_id}/"
            f"proofs/{proof_id}/proof.json"
        )
        self._assert_app_writable_key(object_key=object_key)
        return object_key

    @staticmethod
    def _bundle_archive_name(*, bundle_kind: DepositBundleKind) -> str:
        if bundle_kind == "CONTROLLED_EVIDENCE":
            return "controlled_evidence_bundle.zip"
        return "safeguarded_deposit_bundle.zip"

    def _build_bundle_object_key(
        self,
        *,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        bundle_kind: DepositBundleKind,
    ) -> str:
        prefix = self._settings.storage_controlled_derived_prefix.strip("/ ")
        object_key = (
            f"{prefix}/provenance/{project_id}/export-requests/{export_request_id}/"
            f"bundles/{bundle_id}/{self._bundle_archive_name(bundle_kind=bundle_kind)}"
        )
        self._assert_app_writable_key(object_key=object_key)
        return object_key

    def _build_bundle_profile_snapshot_key(
        self,
        *,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        profile_id: str,
        profile_snapshot_sha256: str,
    ) -> str:
        prefix = self._settings.storage_controlled_derived_prefix.strip("/ ")
        object_key = (
            f"{prefix}/provenance/{project_id}/export-requests/{export_request_id}/"
            f"bundles/{bundle_id}/profiles/{profile_id.strip().lower()}/"
            f"{profile_snapshot_sha256.strip().lower()}.json"
        )
        self._assert_app_writable_key(object_key=object_key)
        return object_key

    @staticmethod
    def _zipinfo(name: str) -> zipfile.ZipInfo:
        # Fixed timestamp + permissions keeps archive bytes deterministic.
        info = zipfile.ZipInfo(filename=name, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o600 << 16
        return info

    def _build_bundle_payload(
        self,
        *,
        bundle_id: str,
        bundle_kind: DepositBundleKind,
        bundle_attempt_number: int,
        request: ExportRequestRecord,
        candidate: ExportCandidateSnapshotRecord,
        proof: ProvenanceProofRecord,
        proof_artifact: dict[str, object],
        built_at: datetime,
    ) -> dict[str, object]:
        proof_signature = proof_artifact.get("signature")
        proof_verification = proof_artifact.get("verificationMaterial")
        manifest_entries = (
            list(candidate.artefact_manifest_json.get("entries"))
            if isinstance(candidate.artefact_manifest_json.get("entries"), list)
            else []
        )
        file_list = (
            list(candidate.artefact_manifest_json.get("fileList"))
            if isinstance(candidate.artefact_manifest_json.get("fileList"), list)
            else []
        )
        outputs = (
            list(candidate.artefact_manifest_json.get("outputs"))
            if isinstance(candidate.artefact_manifest_json.get("outputs"), list)
            else []
        )
        receipt_metadata: dict[str, object] | None = None
        if (
            request.receipt_id is not None
            or request.receipt_sha256 is not None
            or request.receipt_created_at is not None
        ):
            receipt_metadata = {
                "receiptId": request.receipt_id,
                "receiptSha256": request.receipt_sha256,
                "exportedAt": request.exported_at.isoformat() if request.exported_at else None,
                "receiptCreatedAt": (
                    request.receipt_created_at.isoformat() if request.receipt_created_at else None
                ),
                "receiptRef": self._sanitize_reference(request.receipt_key),
            }

        return {
            "schemaVersion": 1,
            "bundleId": bundle_id,
            "bundleKind": bundle_kind,
            "bundleAttemptNumber": bundle_attempt_number,
            "builtAt": built_at.isoformat(),
            "projectId": request.project_id,
            "exportRequest": {
                "id": request.id,
                "status": request.status,
                "requestRevision": request.request_revision,
                "riskClassification": request.risk_classification,
                "reviewPath": request.review_path,
                "finalReviewId": request.final_review_id,
                "finalDecisionBy": request.final_decision_by,
                "finalDecisionAt": (
                    request.final_decision_at.isoformat() if request.final_decision_at else None
                ),
            },
            "candidateSnapshot": {
                "id": candidate.id,
                "candidateSha256": candidate.candidate_sha256,
                "sourcePhase": candidate.source_phase,
                "sourceArtifactKind": candidate.source_artifact_kind,
                "sourceArtifactId": candidate.source_artifact_id,
                "sourceRunId": candidate.source_run_id,
            },
            "governanceReferences": {
                "governanceRunId": candidate.governance_run_id,
                "manifestId": candidate.governance_manifest_id,
                "manifestSha256": candidate.governance_manifest_sha256,
                "ledgerId": candidate.governance_ledger_id,
                "ledgerSha256": candidate.governance_ledger_sha256,
                "ledgerVerificationRunId": next(
                    (
                        str(leaf.get("stable_identifier"))
                        for leaf in proof_artifact.get("leaves", [])
                        if isinstance(leaf, dict)
                        and str(leaf.get("artifact_kind")) == "LEDGER_VERIFICATION"
                    ),
                    None,
                ),
                "readinessReference": next(
                    (
                        str(leaf.get("stable_identifier"))
                        for leaf in proof_artifact.get("leaves", [])
                        if isinstance(leaf, dict)
                        and str(leaf.get("artifact_kind")) == "GOVERNANCE_READINESS_REFERENCE"
                    ),
                    None,
                ),
            },
            "policyLineage": {
                "policySnapshotHash": candidate.policy_snapshot_hash,
                "policyId": candidate.policy_id,
                "policyFamilyId": candidate.policy_family_id,
                "policyVersion": candidate.policy_version,
            },
            "toolVersions": {
                "detectorsVersion": candidate.artefact_manifest_json.get("detectorsVersion"),
                "pipelineVersion": candidate.artefact_manifest_json.get("pipelineVersion"),
                "modelReferencesByRole": (
                    dict(candidate.artefact_manifest_json.get("approvedModelReferencesByRole"))
                    if isinstance(
                        candidate.artefact_manifest_json.get("approvedModelReferencesByRole"),
                        dict,
                    )
                    else {}
                ),
            },
            "transcriptOrDerivativeOutput": {
                "files": file_list,
                "outputs": outputs,
            },
            "manifest": {
                "entryCount": len(manifest_entries),
                "entries": manifest_entries,
                "candidateManifest": dict(candidate.artefact_manifest_json),
            },
            "metadata": {
                "releasePackSha256": request.release_pack_sha256,
                "releasePackRef": self._sanitize_reference(request.release_pack_key),
                "bundleProfile": request.bundle_profile,
            },
            "provenanceProof": {
                "proofId": proof.id,
                "attemptNumber": proof.attempt_number,
                "rootSha256": proof.root_sha256,
                "proofArtifactSha256": proof.proof_artifact_sha256,
                "signatureKeyRef": proof.signature_key_ref,
                "signature": (
                    dict(proof_signature) if isinstance(proof_signature, dict) else {}
                ),
                "verificationMaterial": (
                    dict(proof_verification) if isinstance(proof_verification, dict) else {}
                ),
            },
            "exportReceiptMetadata": receipt_metadata,
        }

    def _build_bundle_archive_bytes(
        self,
        *,
        metadata_payload: dict[str, object],
        proof_artifact: dict[str, object],
    ) -> bytes:
        metadata_bytes = self._canonical_json_bytes(metadata_payload)
        proof_bytes = self._canonical_json_bytes(proof_artifact)
        signature = proof_artifact.get("signature")
        verification_material = proof_artifact.get("verificationMaterial")
        signature_bytes = self._canonical_json_bytes(
            dict(signature) if isinstance(signature, dict) else {}
        )
        verification_bytes = self._canonical_json_bytes(
            dict(verification_material) if isinstance(verification_material, dict) else {}
        )

        output = io.BytesIO()
        with zipfile.ZipFile(output, mode="w") as archive:
            archive.writestr(self._zipinfo("bundle/metadata.json"), metadata_bytes)
            archive.writestr(self._zipinfo("bundle/provenance-proof.json"), proof_bytes)
            archive.writestr(
                self._zipinfo("bundle/provenance-signature.json"),
                signature_bytes,
            )
            archive.writestr(
                self._zipinfo("bundle/provenance-verification-material.json"),
                verification_bytes,
            )
        return output.getvalue()

    @staticmethod
    def _is_undefined_table_error(error: psycopg.Error) -> bool:
        return getattr(error, "sqlstate", None) == "42P01"

    @staticmethod
    def _sanitize_reference(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.startswith("/"):
            return normalized.split("/")[-1] or None
        if ".ukde-storage" in normalized:
            return normalized.split("/")[-1] or None
        return normalized

    @staticmethod
    def _as_reason_codes(value: object) -> tuple[str, ...]:
        if not isinstance(value, list):
            return ()
        codes: list[str] = []
        for entry in value:
            if not isinstance(entry, str):
                continue
            code = entry.strip()
            if not code or code in codes:
                continue
            codes.append(code)
        return tuple(codes)

    @staticmethod
    def _assert_candidate_source_phase(value: str) -> ExportCandidateSourcePhase:
        if value not in {"PHASE6", "PHASE7", "PHASE9", "PHASE10"}:
            raise ExportStoreUnavailableError("Unexpected candidate source phase persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_candidate_source_artifact_kind(value: str) -> ExportCandidateSourceArtifactKind:
        if value not in {"REDACTION_RUN_OUTPUT", "DEPOSIT_BUNDLE", "DERIVATIVE_SNAPSHOT"}:
            raise ExportStoreUnavailableError(
                "Unexpected candidate source artifact kind persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_candidate_kind(value: str) -> ExportCandidateKind:
        if value not in {
            "SAFEGUARDED_PREVIEW",
            "POLICY_RERUN",
            "DEPOSIT_BUNDLE",
            "SAFEGUARDED_DERIVATIVE",
        }:
            raise ExportStoreUnavailableError("Unexpected candidate kind persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_candidate_eligibility_status(value: str) -> ExportCandidateEligibilityStatus:
        if value not in {"ELIGIBLE", "SUPERSEDED"}:
            raise ExportStoreUnavailableError("Unexpected candidate eligibility status persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_request_status(value: str) -> ExportRequestStatus:
        if value not in {
            "SUBMITTED",
            "RESUBMITTED",
            "IN_REVIEW",
            "APPROVED",
            "EXPORTED",
            "REJECTED",
            "RETURNED",
        }:
            raise ExportStoreUnavailableError("Unexpected export request status persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_risk_classification(value: str) -> ExportRequestRiskClassification:
        if value not in {"STANDARD", "HIGH"}:
            raise ExportStoreUnavailableError("Unexpected export request risk classification.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_review_path(value: str) -> ExportRequestReviewPath:
        if value not in {"SINGLE", "DUAL"}:
            raise ExportStoreUnavailableError("Unexpected export request review path.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_event_type(value: str) -> ExportRequestEventType:
        if value not in {
            "REQUEST_SUBMITTED",
            "REQUEST_REVIEW_STARTED",
            "REQUEST_RESUBMITTED",
            "REQUEST_APPROVED",
            "REQUEST_EXPORTED",
            "REQUEST_REJECTED",
            "REQUEST_RETURNED",
            "REQUEST_RECEIPT_ATTACHED",
            "REQUEST_REMINDER_SENT",
            "REQUEST_ESCALATED",
        }:
            raise ExportStoreUnavailableError("Unexpected export request event type persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_review_stage(value: str) -> ExportRequestReviewStage:
        if value not in {"PRIMARY", "SECONDARY"}:
            raise ExportStoreUnavailableError("Unexpected export review stage persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_review_status(value: str) -> ExportRequestReviewStatus:
        if value not in {"PENDING", "IN_REVIEW", "APPROVED", "RETURNED", "REJECTED"}:
            raise ExportStoreUnavailableError("Unexpected export review status persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_review_event_type(value: str) -> ExportRequestReviewEventType:
        if value not in {
            "REVIEW_CREATED",
            "REVIEW_CLAIMED",
            "REVIEW_STARTED",
            "REVIEW_APPROVED",
            "REVIEW_REJECTED",
            "REVIEW_RETURNED",
            "REVIEW_RELEASED",
        }:
            raise ExportStoreUnavailableError("Unexpected export review event type persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_bundle_kind(value: str) -> DepositBundleKind:
        if value not in {"CONTROLLED_EVIDENCE", "SAFEGUARDED_DEPOSIT"}:
            raise ExportStoreUnavailableError("Unexpected deposit bundle kind persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_bundle_status(value: str) -> DepositBundleStatus:
        if value not in {"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"}:
            raise ExportStoreUnavailableError("Unexpected deposit bundle status persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_bundle_verification_projection_status(value: str) -> BundleVerificationProjectionStatus:
        if value not in {"PENDING", "VERIFIED", "FAILED"}:
            raise ExportStoreUnavailableError(
                "Unexpected bundle verification projection status persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_bundle_verification_run_status(value: str) -> BundleVerificationRunStatus:
        if value not in {"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"}:
            raise ExportStoreUnavailableError("Unexpected bundle verification run status persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_bundle_validation_projection_status(value: str) -> BundleValidationProjectionStatus:
        if value not in {"PENDING", "READY", "FAILED"}:
            raise ExportStoreUnavailableError(
                "Unexpected bundle validation projection status persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_bundle_validation_run_status(value: str) -> BundleValidationRunStatus:
        if value not in {"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"}:
            raise ExportStoreUnavailableError("Unexpected bundle validation run status persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_bundle_event_type(value: str) -> BundleEventType:
        if value not in {
            "BUNDLE_BUILD_QUEUED",
            "BUNDLE_REBUILD_REQUESTED",
            "BUNDLE_BUILD_STARTED",
            "BUNDLE_BUILD_SUCCEEDED",
            "BUNDLE_BUILD_FAILED",
            "BUNDLE_BUILD_CANCELED",
            "BUNDLE_VERIFICATION_STARTED",
            "BUNDLE_VERIFICATION_SUCCEEDED",
            "BUNDLE_VERIFICATION_FAILED",
            "BUNDLE_VERIFICATION_CANCELED",
            "BUNDLE_VALIDATION_STARTED",
            "BUNDLE_VALIDATION_SUCCEEDED",
            "BUNDLE_VALIDATION_FAILED",
            "BUNDLE_VALIDATION_CANCELED",
        }:
            raise ExportStoreUnavailableError("Unexpected bundle event type persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _next_review_etag(*, review_id: str, actor_user_id: str, now: datetime, action: str) -> str:
        material = f"{review_id}|{actor_user_id}|{action}|{now.isoformat()}".encode("utf-8")
        return hashlib.sha256(material).hexdigest()

    @classmethod
    def _as_candidate_record(cls, row: dict[str, object]) -> ExportCandidateSnapshotRecord:
        return ExportCandidateSnapshotRecord(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            source_phase=cls._assert_candidate_source_phase(str(row["source_phase"])),
            source_artifact_kind=cls._assert_candidate_source_artifact_kind(
                str(row["source_artifact_kind"])
            ),
            source_run_id=(
                str(row["source_run_id"]) if isinstance(row.get("source_run_id"), str) else None
            ),
            source_artifact_id=str(row["source_artifact_id"]),
            governance_run_id=(
                str(row["governance_run_id"])
                if isinstance(row.get("governance_run_id"), str)
                else None
            ),
            governance_manifest_id=(
                str(row["governance_manifest_id"])
                if isinstance(row.get("governance_manifest_id"), str)
                else None
            ),
            governance_ledger_id=(
                str(row["governance_ledger_id"])
                if isinstance(row.get("governance_ledger_id"), str)
                else None
            ),
            governance_manifest_sha256=(
                str(row["governance_manifest_sha256"])
                if isinstance(row.get("governance_manifest_sha256"), str)
                else None
            ),
            governance_ledger_sha256=(
                str(row["governance_ledger_sha256"])
                if isinstance(row.get("governance_ledger_sha256"), str)
                else None
            ),
            policy_snapshot_hash=(
                str(row["policy_snapshot_hash"])
                if isinstance(row.get("policy_snapshot_hash"), str)
                else None
            ),
            policy_id=str(row["policy_id"]) if isinstance(row.get("policy_id"), str) else None,
            policy_family_id=(
                str(row["policy_family_id"])
                if isinstance(row.get("policy_family_id"), str)
                else None
            ),
            policy_version=(
                str(row["policy_version"]) if isinstance(row.get("policy_version"), str) else None
            ),
            candidate_kind=cls._assert_candidate_kind(str(row["candidate_kind"])),
            artefact_manifest_json=(
                dict(row["artefact_manifest_json"])
                if isinstance(row.get("artefact_manifest_json"), dict)
                else {}
            ),
            candidate_sha256=str(row["candidate_sha256"]),
            eligibility_status=cls._assert_candidate_eligibility_status(
                str(row["eligibility_status"])
            ),
            supersedes_candidate_snapshot_id=(
                str(row["supersedes_candidate_snapshot_id"])
                if isinstance(row.get("supersedes_candidate_snapshot_id"), str)
                else None
            ),
            superseded_by_candidate_snapshot_id=(
                str(row["superseded_by_candidate_snapshot_id"])
                if isinstance(row.get("superseded_by_candidate_snapshot_id"), str)
                else None
            ),
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_request_record(cls, row: dict[str, object]) -> ExportRequestRecord:
        return ExportRequestRecord(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            candidate_snapshot_id=str(row["candidate_snapshot_id"]),
            candidate_origin_phase=cls._assert_candidate_source_phase(
                str(row["candidate_origin_phase"])
            ),
            candidate_kind=cls._assert_candidate_kind(str(row["candidate_kind"])),
            bundle_profile=(
                str(row["bundle_profile"]) if isinstance(row.get("bundle_profile"), str) else None
            ),
            risk_classification=cls._assert_risk_classification(str(row["risk_classification"])),
            risk_reason_codes_json=cls._as_reason_codes(row.get("risk_reason_codes_json")),
            review_path=cls._assert_review_path(str(row["review_path"])),
            requires_second_review=bool(row.get("requires_second_review", False)),
            supersedes_export_request_id=(
                str(row["supersedes_export_request_id"])
                if isinstance(row.get("supersedes_export_request_id"), str)
                else None
            ),
            superseded_by_export_request_id=(
                str(row["superseded_by_export_request_id"])
                if isinstance(row.get("superseded_by_export_request_id"), str)
                else None
            ),
            request_revision=int(row["request_revision"]),
            purpose_statement=str(row["purpose_statement"]),
            status=cls._assert_request_status(str(row["status"])),
            submitted_by=str(row["submitted_by"]),
            submitted_at=row["submitted_at"],  # type: ignore[arg-type]
            first_review_started_by=(
                str(row["first_review_started_by"])
                if isinstance(row.get("first_review_started_by"), str)
                else None
            ),
            first_review_started_at=row.get("first_review_started_at"),  # type: ignore[arg-type]
            sla_due_at=row.get("sla_due_at"),  # type: ignore[arg-type]
            last_queue_activity_at=row.get("last_queue_activity_at"),  # type: ignore[arg-type]
            retention_until=row.get("retention_until"),  # type: ignore[arg-type]
            final_review_id=(
                str(row["final_review_id"]) if isinstance(row.get("final_review_id"), str) else None
            ),
            final_decision_by=(
                str(row["final_decision_by"])
                if isinstance(row.get("final_decision_by"), str)
                else None
            ),
            final_decision_at=row.get("final_decision_at"),  # type: ignore[arg-type]
            final_decision_reason=(
                str(row["final_decision_reason"])
                if isinstance(row.get("final_decision_reason"), str)
                else None
            ),
            final_return_comment=(
                str(row["final_return_comment"])
                if isinstance(row.get("final_return_comment"), str)
                else None
            ),
            release_pack_key=str(row["release_pack_key"]),
            release_pack_sha256=str(row["release_pack_sha256"]),
            release_pack_json=(
                dict(row["release_pack_json"])
                if isinstance(row.get("release_pack_json"), dict)
                else {}
            ),
            release_pack_created_at=row["release_pack_created_at"],  # type: ignore[arg-type]
            receipt_id=str(row["receipt_id"]) if isinstance(row.get("receipt_id"), str) else None,
            receipt_key=(
                str(row["receipt_key"]) if isinstance(row.get("receipt_key"), str) else None
            ),
            receipt_sha256=(
                str(row["receipt_sha256"]) if isinstance(row.get("receipt_sha256"), str) else None
            ),
            receipt_created_by=(
                str(row["receipt_created_by"])
                if isinstance(row.get("receipt_created_by"), str)
                else None
            ),
            receipt_created_at=row.get("receipt_created_at"),  # type: ignore[arg-type]
            exported_at=row.get("exported_at"),  # type: ignore[arg-type]
            created_at=row["created_at"],  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_event_record(cls, row: dict[str, object]) -> ExportRequestEventRecord:
        return ExportRequestEventRecord(
            id=str(row["id"]),
            export_request_id=str(row["export_request_id"]),
            event_type=cls._assert_event_type(str(row["event_type"])),
            from_status=(
                cls._assert_request_status(str(row["from_status"]))
                if isinstance(row.get("from_status"), str)
                else None
            ),
            to_status=cls._assert_request_status(str(row["to_status"])),
            actor_user_id=(
                str(row["actor_user_id"]) if isinstance(row.get("actor_user_id"), str) else None
            ),
            reason=str(row["reason"]) if isinstance(row.get("reason"), str) else None,
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_review_record(cls, row: dict[str, object]) -> ExportRequestReviewRecord:
        return ExportRequestReviewRecord(
            id=str(row["id"]),
            export_request_id=str(row["export_request_id"]),
            review_stage=cls._assert_review_stage(str(row["review_stage"])),
            is_required=bool(row.get("is_required", False)),
            status=cls._assert_review_status(str(row["status"])),
            assigned_reviewer_user_id=(
                str(row["assigned_reviewer_user_id"])
                if isinstance(row.get("assigned_reviewer_user_id"), str)
                else None
            ),
            assigned_at=row.get("assigned_at"),  # type: ignore[arg-type]
            acted_by_user_id=(
                str(row["acted_by_user_id"])
                if isinstance(row.get("acted_by_user_id"), str)
                else None
            ),
            acted_at=row.get("acted_at"),  # type: ignore[arg-type]
            decision_reason=(
                str(row["decision_reason"])
                if isinstance(row.get("decision_reason"), str)
                else None
            ),
            return_comment=(
                str(row["return_comment"]) if isinstance(row.get("return_comment"), str) else None
            ),
            review_etag=str(row["review_etag"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_review_event_record(cls, row: dict[str, object]) -> ExportRequestReviewEventRecord:
        return ExportRequestReviewEventRecord(
            id=str(row["id"]),
            review_id=str(row["review_id"]),
            export_request_id=str(row["export_request_id"]),
            review_stage=cls._assert_review_stage(str(row["review_stage"])),
            event_type=cls._assert_review_event_type(str(row["event_type"])),
            actor_user_id=(
                str(row["actor_user_id"]) if isinstance(row.get("actor_user_id"), str) else None
            ),
            assigned_reviewer_user_id=(
                str(row["assigned_reviewer_user_id"])
                if isinstance(row.get("assigned_reviewer_user_id"), str)
                else None
            ),
            decision_reason=(
                str(row["decision_reason"])
                if isinstance(row.get("decision_reason"), str)
                else None
            ),
            return_comment=(
                str(row["return_comment"]) if isinstance(row.get("return_comment"), str) else None
            ),
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_receipt_record(cls, row: dict[str, object]) -> ExportReceiptRecord:
        return ExportReceiptRecord(
            id=str(row["id"]),
            export_request_id=str(row["export_request_id"]),
            attempt_number=int(row["attempt_number"]),
            supersedes_receipt_id=(
                str(row["supersedes_receipt_id"])
                if isinstance(row.get("supersedes_receipt_id"), str)
                else None
            ),
            superseded_by_receipt_id=(
                str(row["superseded_by_receipt_id"])
                if isinstance(row.get("superseded_by_receipt_id"), str)
                else None
            ),
            receipt_key=str(row["receipt_key"]),
            receipt_sha256=str(row["receipt_sha256"]),
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
            exported_at=row["exported_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_provenance_proof_record(cls, row: dict[str, object]) -> ProvenanceProofRecord:
        return ProvenanceProofRecord(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            export_request_id=str(row["export_request_id"]),
            candidate_snapshot_id=str(row["candidate_snapshot_id"]),
            attempt_number=int(row["attempt_number"]),
            supersedes_proof_id=(
                str(row["supersedes_proof_id"])
                if isinstance(row.get("supersedes_proof_id"), str)
                else None
            ),
            superseded_by_proof_id=(
                str(row["superseded_by_proof_id"])
                if isinstance(row.get("superseded_by_proof_id"), str)
                else None
            ),
            root_sha256=str(row["root_sha256"]),
            signature_key_ref=str(row["signature_key_ref"]),
            signature_bytes_key=str(row["signature_bytes_key"]),
            proof_artifact_key=str(row["proof_artifact_key"]),
            proof_artifact_sha256=str(row["proof_artifact_sha256"]),
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_deposit_bundle_record(cls, row: dict[str, object]) -> DepositBundleRecord:
        return DepositBundleRecord(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            export_request_id=str(row["export_request_id"]),
            candidate_snapshot_id=str(row["candidate_snapshot_id"]),
            provenance_proof_id=str(row["provenance_proof_id"]),
            provenance_proof_artifact_sha256=str(row["provenance_proof_artifact_sha256"]),
            bundle_kind=cls._assert_bundle_kind(str(row["bundle_kind"])),
            status=cls._assert_bundle_status(str(row["status"])),
            attempt_number=int(row["attempt_number"]),
            supersedes_bundle_id=(
                str(row["supersedes_bundle_id"])
                if isinstance(row.get("supersedes_bundle_id"), str)
                else None
            ),
            superseded_by_bundle_id=(
                str(row["superseded_by_bundle_id"])
                if isinstance(row.get("superseded_by_bundle_id"), str)
                else None
            ),
            bundle_key=str(row["bundle_key"]) if isinstance(row.get("bundle_key"), str) else None,
            bundle_sha256=(
                str(row["bundle_sha256"]) if isinstance(row.get("bundle_sha256"), str) else None
            ),
            failure_reason=(
                str(row["failure_reason"]) if isinstance(row.get("failure_reason"), str) else None
            ),
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
            started_at=row.get("started_at"),  # type: ignore[arg-type]
            finished_at=row.get("finished_at"),  # type: ignore[arg-type]
            canceled_by=(
                str(row["canceled_by"]) if isinstance(row.get("canceled_by"), str) else None
            ),
            canceled_at=row.get("canceled_at"),  # type: ignore[arg-type]
        )

    @classmethod
    def _as_bundle_verification_projection_record(
        cls,
        row: dict[str, object],
    ) -> BundleVerificationProjectionRecord:
        return BundleVerificationProjectionRecord(
            bundle_id=str(row["bundle_id"]),
            status=cls._assert_bundle_verification_projection_status(str(row["status"])),
            last_verification_run_id=(
                str(row["last_verification_run_id"])
                if isinstance(row.get("last_verification_run_id"), str)
                else None
            ),
            verified_at=row.get("verified_at"),  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_bundle_verification_run_record(
        cls,
        row: dict[str, object],
    ) -> BundleVerificationRunRecord:
        return BundleVerificationRunRecord(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            bundle_id=str(row["bundle_id"]),
            attempt_number=int(row["attempt_number"]),
            supersedes_verification_run_id=(
                str(row["supersedes_verification_run_id"])
                if isinstance(row.get("supersedes_verification_run_id"), str)
                else None
            ),
            superseded_by_verification_run_id=(
                str(row["superseded_by_verification_run_id"])
                if isinstance(row.get("superseded_by_verification_run_id"), str)
                else None
            ),
            status=cls._assert_bundle_verification_run_status(str(row["status"])),
            result_json=(
                dict(row["result_json"]) if isinstance(row.get("result_json"), dict) else {}
            ),
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
            started_at=row.get("started_at"),  # type: ignore[arg-type]
            finished_at=row.get("finished_at"),  # type: ignore[arg-type]
            canceled_by=(
                str(row["canceled_by"]) if isinstance(row.get("canceled_by"), str) else None
            ),
            canceled_at=row.get("canceled_at"),  # type: ignore[arg-type]
            failure_reason=(
                str(row["failure_reason"]) if isinstance(row.get("failure_reason"), str) else None
            ),
        )

    @classmethod
    def _as_bundle_validation_projection_record(
        cls,
        row: dict[str, object],
    ) -> BundleValidationProjectionRecord:
        return BundleValidationProjectionRecord(
            bundle_id=str(row["bundle_id"]),
            profile_id=str(row["profile_id"]),
            status=cls._assert_bundle_validation_projection_status(str(row["status"])),
            last_validation_run_id=(
                str(row["last_validation_run_id"])
                if isinstance(row.get("last_validation_run_id"), str)
                else None
            ),
            ready_at=row.get("ready_at"),  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_bundle_validation_run_record(
        cls,
        row: dict[str, object],
    ) -> BundleValidationRunRecord:
        return BundleValidationRunRecord(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            bundle_id=str(row["bundle_id"]),
            profile_id=str(row["profile_id"]),
            profile_snapshot_key=str(row["profile_snapshot_key"]),
            profile_snapshot_sha256=str(row["profile_snapshot_sha256"]),
            status=cls._assert_bundle_validation_run_status(str(row["status"])),
            attempt_number=int(row["attempt_number"]),
            supersedes_validation_run_id=(
                str(row["supersedes_validation_run_id"])
                if isinstance(row.get("supersedes_validation_run_id"), str)
                else None
            ),
            superseded_by_validation_run_id=(
                str(row["superseded_by_validation_run_id"])
                if isinstance(row.get("superseded_by_validation_run_id"), str)
                else None
            ),
            result_json=(
                dict(row["result_json"]) if isinstance(row.get("result_json"), dict) else {}
            ),
            failure_reason=(
                str(row["failure_reason"]) if isinstance(row.get("failure_reason"), str) else None
            ),
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
            started_at=row.get("started_at"),  # type: ignore[arg-type]
            finished_at=row.get("finished_at"),  # type: ignore[arg-type]
            canceled_by=(
                str(row["canceled_by"]) if isinstance(row.get("canceled_by"), str) else None
            ),
            canceled_at=row.get("canceled_at"),  # type: ignore[arg-type]
        )

    @classmethod
    def _as_bundle_event_record(cls, row: dict[str, object]) -> BundleEventRecord:
        return BundleEventRecord(
            id=str(row["id"]),
            bundle_id=str(row["bundle_id"]),
            event_type=cls._assert_bundle_event_type(str(row["event_type"])),
            verification_run_id=(
                str(row["verification_run_id"])
                if isinstance(row.get("verification_run_id"), str)
                else None
            ),
            validation_run_id=(
                str(row["validation_run_id"])
                if isinstance(row.get("validation_run_id"), str)
                else None
            ),
            actor_user_id=(
                str(row["actor_user_id"]) if isinstance(row.get("actor_user_id"), str) else None
            ),
            reason=str(row["reason"]) if isinstance(row.get("reason"), str) else None,
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    def ensure_schema(self) -> None:
        if self._schema_initialized:
            return

        try:
            GovernanceStore(self._settings).ensure_schema()
        except GovernanceStoreUnavailableError as error:
            raise ExportStoreUnavailableError(
                "Governance schema is unavailable for export candidate snapshots."
            ) from error

        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    for statement in EXPORT_SCHEMA_STATEMENTS:
                        cursor.execute(statement)
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Export schema could not be initialized.") from error

        self._schema_initialized = True

    def sync_phase6_candidate_snapshots(
        self,
        *,
        project_id: str,
        actor_user_id: str,
    ) -> int:
        self.ensure_schema()
        inserted_count = 0
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          rr.id AS run_id,
                          rr.run_kind,
                          rr.supersedes_redaction_run_id AS supersedes_run_id,
                          rr.superseded_by_redaction_run_id AS superseded_by_run_id,
                          rr.policy_snapshot_hash,
                          rr.policy_id,
                          rr.policy_family_id,
                          rr.policy_version,
                          rro.output_manifest_key,
                          rro.output_manifest_sha256,
                          rro.page_count,
                          grp.manifest_id AS governance_manifest_id,
                          grp.ledger_id AS governance_ledger_id,
                          grp.last_manifest_sha256 AS governance_manifest_sha256,
                          grp.last_ledger_sha256 AS governance_ledger_sha256
                        FROM redaction_runs AS rr
                        INNER JOIN redaction_run_reviews AS rrv
                          ON rrv.run_id = rr.id
                        INNER JOIN redaction_run_outputs AS rro
                          ON rro.run_id = rr.id
                        INNER JOIN governance_readiness_projections AS grp
                          ON grp.run_id = rr.id
                        WHERE rr.project_id = %(project_id)s
                          AND rrv.review_status = 'APPROVED'
                          AND rro.status = 'READY'
                          AND grp.status = 'READY'
                          AND grp.ledger_verification_status = 'VALID'
                        ORDER BY rr.created_at ASC, rr.id ASC
                        """,
                        {"project_id": project_id},
                    )
                    run_rows = cursor.fetchall()

                    cursor.execute(
                        """
                        SELECT
                          pma.model_role,
                          am.id AS model_id,
                          am.model_family,
                          am.model_version,
                          am.checksum_sha256
                        FROM project_model_assignments AS pma
                        INNER JOIN approved_models AS am
                          ON am.id = pma.approved_model_id
                        WHERE pma.project_id = %(project_id)s
                          AND pma.status = 'ACTIVE'
                        ORDER BY pma.model_role ASC, pma.created_at DESC, pma.id DESC
                        """,
                        {"project_id": project_id},
                    )
                    model_rows = cursor.fetchall()
                    model_refs_by_role: dict[str, dict[str, str]] = {}
                    for row in model_rows:
                        role = str(row["model_role"])
                        if role in model_refs_by_role:
                            continue
                        model_refs_by_role[role] = {
                            "modelId": str(row["model_id"]),
                            "modelFamily": str(row["model_family"]),
                            "modelVersion": str(row["model_version"]),
                            "checksumSha256": str(row["checksum_sha256"]),
                        }

                    for run_row in run_rows:
                        run_id = str(run_row["run_id"])
                        run_kind = str(run_row["run_kind"])
                        source_phase: ExportCandidateSourcePhase = (
                            "PHASE7" if run_kind == "POLICY_RERUN" else "PHASE6"
                        )
                        candidate_kind: ExportCandidateKind = (
                            "POLICY_RERUN" if run_kind == "POLICY_RERUN" else "SAFEGUARDED_PREVIEW"
                        )

                        cursor.execute(
                            """
                            SELECT
                              p.page_index,
                              ro.page_id,
                              ro.safeguarded_preview_key,
                              ro.preview_sha256
                            FROM redaction_outputs AS ro
                            INNER JOIN pages AS p
                              ON p.id = ro.page_id
                            WHERE ro.run_id = %(run_id)s
                              AND ro.status = 'READY'
                            ORDER BY p.page_index ASC, ro.page_id ASC
                            """,
                            {"run_id": run_id},
                        )
                        output_rows = cursor.fetchall()

                        cursor.execute(
                            """
                            SELECT category, COUNT(*)::INT AS count
                            FROM redaction_findings
                            WHERE run_id = %(run_id)s
                              AND decision_status IN ('AUTO_APPLIED', 'APPROVED', 'OVERRIDDEN')
                            GROUP BY category
                            ORDER BY category ASC
                            """,
                            {"run_id": run_id},
                        )
                        category_rows = cursor.fetchall()
                        category_counts = {
                            str(row["category"]): int(row["count"]) for row in category_rows
                        }

                        cursor.execute(
                            """
                            SELECT
                              SUM(
                                CASE WHEN decision_status = 'OVERRIDDEN' THEN 1 ELSE 0 END
                              )::INT AS override_count,
                              SUM(
                                CASE
                                  WHEN area_mask_id IS NOT NULL AND btrim(area_mask_id) <> '' THEN 1
                                  ELSE 0
                                END
                              )::INT AS area_mask_count
                            FROM redaction_findings
                            WHERE run_id = %(run_id)s
                              AND decision_status IN ('AUTO_APPLIED', 'APPROVED', 'OVERRIDDEN')
                            """,
                            {"run_id": run_id},
                        )
                        count_row = cursor.fetchone() or {}
                        reviewer_override_count = int(count_row.get("override_count") or 0)
                        conservative_area_mask_count = int(count_row.get("area_mask_count") or 0)

                        risk_flags: list[str] = []
                        if reviewer_override_count > 0:
                            risk_flags.append("manual_review_override_present")
                        if conservative_area_mask_count > 0:
                            risk_flags.append("conservative_area_mask_present")
                        if any("INDIRECT" in key.upper() for key in category_counts):
                            risk_flags.append("indirect_risk_present")
                        if run_kind == "POLICY_RERUN":
                            risk_flags.append("policy_escalation_present")

                        files: list[dict[str, object]] = []
                        output_manifest_sha256 = (
                            str(run_row["output_manifest_sha256"])
                            if isinstance(run_row.get("output_manifest_sha256"), str)
                            else None
                        )
                        output_manifest_key = self._sanitize_reference(
                            run_row.get("output_manifest_key")
                        )
                        if output_manifest_sha256 is not None:
                            files.append(
                                {
                                    "fileName": "output-manifest.json",
                                    "fileSizeBytes": 0,
                                    "sha256": output_manifest_sha256,
                                    "sourceRef": output_manifest_key,
                                    "sourceKind": "RUN_OUTPUT_MANIFEST",
                                }
                            )
                        for output_row in output_rows:
                            page_index = int(output_row.get("page_index") or 0)
                            preview_sha = (
                                str(output_row["preview_sha256"])
                                if isinstance(output_row.get("preview_sha256"), str)
                                else None
                            )
                            if preview_sha is None:
                                continue
                            files.append(
                                {
                                    "fileName": f"page-{page_index + 1:04d}.png",
                                    "fileSizeBytes": 0,
                                    "sha256": preview_sha,
                                    "sourceRef": self._sanitize_reference(
                                        output_row.get("safeguarded_preview_key")
                                    ),
                                    "sourceKind": "SAFEGUARDED_PREVIEW_PAGE",
                                }
                            )

                        artefact_manifest_json: dict[str, object] = {
                            "schemaVersion": 1,
                            "fileList": files,
                            "sourceArtefactReferences": [
                                {
                                    "sourceArtifactKind": "REDACTION_RUN_OUTPUT",
                                    "sourceArtifactId": run_id,
                                    "sourceRunId": run_id,
                                    "manifestRef": output_manifest_key,
                                    "manifestSha256": output_manifest_sha256,
                                }
                            ],
                            "redactionCountsByCategory": category_counts,
                            "reviewerOverrideCount": reviewer_override_count,
                            "conservativeAreaMaskCount": conservative_area_mask_count,
                            "riskFlags": risk_flags,
                            "approvedModelReferencesByRole": model_refs_by_role,
                            "releaseReviewChecklist": [
                                "candidate_snapshot_pinned",
                                "governance_pins_present",
                                "policy_lineage_pinned",
                                "classifier_reasons_pinned",
                            ],
                        }

                        candidate_material = {
                            "runId": run_id,
                            "sourcePhase": source_phase,
                            "candidateKind": candidate_kind,
                            "governanceManifestSha256": run_row.get("governance_manifest_sha256"),
                            "governanceLedgerSha256": run_row.get("governance_ledger_sha256"),
                            "policySnapshotHash": run_row.get("policy_snapshot_hash"),
                            "manifest": artefact_manifest_json,
                        }
                        candidate_sha256 = self._sha256_hex(
                            self._canonical_json_bytes(candidate_material)
                        )
                        candidate_id = (
                            "candidate-"
                            + self._sha256_hex(
                                f"{project_id}|{run_id}|{candidate_sha256}".encode("utf-8")
                            )[:24]
                        )

                        supersedes_candidate_snapshot_id: str | None = None
                        supersedes_run_id = (
                            str(run_row["supersedes_run_id"])
                            if isinstance(run_row.get("supersedes_run_id"), str)
                            else None
                        )
                        if supersedes_run_id is not None:
                            cursor.execute(
                                """
                                SELECT id
                                FROM export_candidate_snapshots
                                WHERE project_id = %(project_id)s
                                  AND source_artifact_kind = 'REDACTION_RUN_OUTPUT'
                                  AND source_artifact_id = %(source_artifact_id)s
                                ORDER BY created_at DESC, id DESC
                                LIMIT 1
                                """,
                                {
                                    "project_id": project_id,
                                    "source_artifact_id": supersedes_run_id,
                                },
                            )
                            predecessor_row = cursor.fetchone()
                            if predecessor_row is not None:
                                supersedes_candidate_snapshot_id = str(predecessor_row["id"])

                        eligibility_status: ExportCandidateEligibilityStatus = "ELIGIBLE"
                        if isinstance(run_row.get("superseded_by_run_id"), str):
                            eligibility_status = "SUPERSEDED"

                        cursor.execute(
                            """
                            INSERT INTO export_candidate_snapshots (
                              id,
                              project_id,
                              source_phase,
                              source_artifact_kind,
                              source_run_id,
                              source_artifact_id,
                              governance_run_id,
                              governance_manifest_id,
                              governance_ledger_id,
                              governance_manifest_sha256,
                              governance_ledger_sha256,
                              policy_snapshot_hash,
                              policy_id,
                              policy_family_id,
                              policy_version,
                              candidate_kind,
                              artefact_manifest_json,
                              candidate_sha256,
                              eligibility_status,
                              supersedes_candidate_snapshot_id,
                              superseded_by_candidate_snapshot_id,
                              created_by
                            )
                            VALUES (
                              %(id)s,
                              %(project_id)s,
                              %(source_phase)s,
                              'REDACTION_RUN_OUTPUT',
                              %(source_run_id)s,
                              %(source_artifact_id)s,
                              %(governance_run_id)s,
                              %(governance_manifest_id)s,
                              %(governance_ledger_id)s,
                              %(governance_manifest_sha256)s,
                              %(governance_ledger_sha256)s,
                              %(policy_snapshot_hash)s,
                              %(policy_id)s,
                              %(policy_family_id)s,
                              %(policy_version)s,
                              %(candidate_kind)s,
                              %(artefact_manifest_json)s,
                              %(candidate_sha256)s,
                              %(eligibility_status)s,
                              %(supersedes_candidate_snapshot_id)s,
                              NULL,
                              %(created_by)s
                            )
                            ON CONFLICT (project_id, source_artifact_kind, source_artifact_id)
                            DO NOTHING
                            """,
                            {
                                "id": candidate_id,
                                "project_id": project_id,
                                "source_phase": source_phase,
                                "source_run_id": run_id,
                                "source_artifact_id": run_id,
                                "governance_run_id": run_id,
                                "governance_manifest_id": run_row.get("governance_manifest_id"),
                                "governance_ledger_id": run_row.get("governance_ledger_id"),
                                "governance_manifest_sha256": run_row.get(
                                    "governance_manifest_sha256"
                                ),
                                "governance_ledger_sha256": run_row.get(
                                    "governance_ledger_sha256"
                                ),
                                "policy_snapshot_hash": run_row.get("policy_snapshot_hash"),
                                "policy_id": run_row.get("policy_id"),
                                "policy_family_id": run_row.get("policy_family_id"),
                                "policy_version": run_row.get("policy_version"),
                                "candidate_kind": candidate_kind,
                                "artefact_manifest_json": artefact_manifest_json,
                                "candidate_sha256": candidate_sha256,
                                "eligibility_status": eligibility_status,
                                "supersedes_candidate_snapshot_id": (
                                    supersedes_candidate_snapshot_id
                                ),
                                "created_by": actor_user_id,
                            },
                        )
                        inserted_count += int(cursor.rowcount or 0)
                connection.commit()
        except psycopg.Error as error:
            if self._is_undefined_table_error(error):
                return 0
            raise ExportStoreUnavailableError(
                "Candidate snapshot synchronization failed."
            ) from error
        return inserted_count

    def list_candidates(
        self,
        *,
        project_id: str,
        include_superseded: bool = False,
    ) -> tuple[ExportCandidateSnapshotRecord, ...]:
        self.ensure_schema()
        conditions = ["ecs.project_id = %(project_id)s"]
        if not include_superseded:
            conditions.append("ecs.eligibility_status = 'ELIGIBLE'")
            conditions.append(
                """
                NOT EXISTS (
                  SELECT 1
                  FROM export_candidate_snapshots AS successor
                  WHERE successor.project_id = ecs.project_id
                    AND successor.supersedes_candidate_snapshot_id = ecs.id
                )
                """
            )

        where_sql = " AND ".join(conditions)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        f"""
                        SELECT
                          ecs.id,
                          ecs.project_id,
                          ecs.source_phase,
                          ecs.source_artifact_kind,
                          ecs.source_run_id,
                          ecs.source_artifact_id,
                          ecs.governance_run_id,
                          ecs.governance_manifest_id,
                          ecs.governance_ledger_id,
                          ecs.governance_manifest_sha256,
                          ecs.governance_ledger_sha256,
                          ecs.policy_snapshot_hash,
                          ecs.policy_id,
                          ecs.policy_family_id,
                          ecs.policy_version,
                          ecs.candidate_kind,
                          ecs.artefact_manifest_json,
                          ecs.candidate_sha256,
                          ecs.eligibility_status,
                          ecs.supersedes_candidate_snapshot_id,
                          ecs.superseded_by_candidate_snapshot_id,
                          ecs.created_by,
                          ecs.created_at
                        FROM export_candidate_snapshots AS ecs
                        WHERE {where_sql}
                        ORDER BY ecs.created_at DESC, ecs.id DESC
                        """,
                        {"project_id": project_id},
                    )
                    rows = cursor.fetchall()
                connection.commit()
        except psycopg.Error as error:
            if self._is_undefined_table_error(error):
                return ()
            raise ExportStoreUnavailableError("Export candidate listing failed.") from error
        return tuple(self._as_candidate_record(row) for row in rows)

    def get_candidate(
        self,
        *,
        project_id: str,
        candidate_id: str,
    ) -> ExportCandidateSnapshotRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          source_phase,
                          source_artifact_kind,
                          source_run_id,
                          source_artifact_id,
                          governance_run_id,
                          governance_manifest_id,
                          governance_ledger_id,
                          governance_manifest_sha256,
                          governance_ledger_sha256,
                          policy_snapshot_hash,
                          policy_id,
                          policy_family_id,
                          policy_version,
                          candidate_kind,
                          artefact_manifest_json,
                          candidate_sha256,
                          eligibility_status,
                          supersedes_candidate_snapshot_id,
                          superseded_by_candidate_snapshot_id,
                          created_by,
                          created_at
                        FROM export_candidate_snapshots
                        WHERE project_id = %(project_id)s
                          AND id = %(candidate_id)s
                        LIMIT 1
                        """,
                        {"project_id": project_id, "candidate_id": candidate_id},
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            if self._is_undefined_table_error(error):
                raise ExportStoreNotFoundError("Export candidate snapshot not found.") from error
            raise ExportStoreUnavailableError("Export candidate lookup failed.") from error
        if row is None:
            raise ExportStoreNotFoundError("Export candidate snapshot not found.")
        return self._as_candidate_record(row)

    def create_request(
        self,
        *,
        request_id: str,
        project_id: str,
        candidate_snapshot_id: str,
        candidate_origin_phase: ExportCandidateSourcePhase,
        candidate_kind: ExportCandidateKind,
        bundle_profile: str | None,
        risk_classification: ExportRequestRiskClassification,
        risk_reason_codes_json: tuple[str, ...],
        review_path: ExportRequestReviewPath,
        requires_second_review: bool,
        supersedes_export_request_id: str | None,
        request_revision: int,
        purpose_statement: str,
        status: ExportRequestStatus,
        submitted_by: str,
        release_pack_key: str,
        release_pack_sha256: str,
        release_pack_json: dict[str, object],
    ) -> ExportRequestRecord:
        self.ensure_schema()
        if status not in {"SUBMITTED", "RESUBMITTED"}:
            raise ExportStoreConflictError("Submission status must be SUBMITTED or RESUBMITTED.")

        request_event_type: ExportRequestEventType = (
            "REQUEST_RESUBMITTED" if status == "RESUBMITTED" else "REQUEST_SUBMITTED"
        )

        now = datetime.now(UTC)
        review_rows: list[dict[str, object]] = [
            {
                "id": str(uuid4()),
                "review_stage": "PRIMARY",
                "is_required": True,
                "review_etag": self._sha256_hex(f"{request_id}|PRIMARY|{now.isoformat()}".encode()),
            }
        ]
        if requires_second_review:
            review_rows.append(
                {
                    "id": str(uuid4()),
                    "review_stage": "SECONDARY",
                    "is_required": True,
                    "review_etag": self._sha256_hex(
                        f"{request_id}|SECONDARY|{now.isoformat()}".encode()
                    ),
                }
            )

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    if supersedes_export_request_id is not None:
                        cursor.execute(
                            """
                            UPDATE export_requests
                            SET
                              superseded_by_export_request_id = %(successor_id)s,
                              updated_at = NOW()
                            WHERE id = %(predecessor_id)s
                              AND project_id = %(project_id)s
                              AND status = 'RETURNED'
                              AND superseded_by_export_request_id IS NULL
                            RETURNING id
                            """,
                            {
                                "successor_id": request_id,
                                "predecessor_id": supersedes_export_request_id,
                                "project_id": project_id,
                            },
                        )
                        predecessor_row = cursor.fetchone()
                        if predecessor_row is None:
                            raise ExportStoreConflictError(
                                "Only unsuperseded RETURNED requests can be resubmitted."
                            )

                    cursor.execute(
                        """
                        INSERT INTO export_requests (
                          id,
                          project_id,
                          candidate_snapshot_id,
                          candidate_origin_phase,
                          candidate_kind,
                          bundle_profile,
                          risk_classification,
                          risk_reason_codes_json,
                          review_path,
                          requires_second_review,
                          supersedes_export_request_id,
                          request_revision,
                          purpose_statement,
                          status,
                          submitted_by,
                          submitted_at,
                          sla_due_at,
                          last_queue_activity_at,
                          release_pack_key,
                          release_pack_sha256,
                          release_pack_json,
                          release_pack_created_at
                        )
                        VALUES (
                          %(id)s,
                          %(project_id)s,
                          %(candidate_snapshot_id)s,
                          %(candidate_origin_phase)s,
                          %(candidate_kind)s,
                          %(bundle_profile)s,
                          %(risk_classification)s,
                          %(risk_reason_codes_json)s,
                          %(review_path)s,
                          %(requires_second_review)s,
                          %(supersedes_export_request_id)s,
                          %(request_revision)s,
                          %(purpose_statement)s,
                          %(status)s,
                          %(submitted_by)s,
                          NOW(),
                          (NOW() + make_interval(hours => %(sla_hours)s)),
                          NOW(),
                          %(release_pack_key)s,
                          %(release_pack_sha256)s,
                          %(release_pack_json)s,
                          NOW()
                        )
                        RETURNING
                          id,
                          project_id,
                          candidate_snapshot_id,
                          candidate_origin_phase,
                          candidate_kind,
                          bundle_profile,
                          risk_classification,
                          risk_reason_codes_json,
                          review_path,
                          requires_second_review,
                          supersedes_export_request_id,
                          superseded_by_export_request_id,
                          request_revision,
                          purpose_statement,
                          status,
                          submitted_by,
                          submitted_at,
                          first_review_started_by,
                          first_review_started_at,
                          sla_due_at,
                          last_queue_activity_at,
                          retention_until,
                          final_review_id,
                          final_decision_by,
                          final_decision_at,
                          final_decision_reason,
                          final_return_comment,
                          release_pack_key,
                          release_pack_sha256,
                          release_pack_json,
                          release_pack_created_at,
                          receipt_id,
                          receipt_key,
                          receipt_sha256,
                          receipt_created_by,
                          receipt_created_at,
                          exported_at,
                          created_at,
                          updated_at
                        """,
                        {
                            "id": request_id,
                            "project_id": project_id,
                            "candidate_snapshot_id": candidate_snapshot_id,
                            "candidate_origin_phase": candidate_origin_phase,
                            "candidate_kind": candidate_kind,
                            "bundle_profile": bundle_profile,
                            "risk_classification": risk_classification,
                            "risk_reason_codes_json": list(risk_reason_codes_json),
                            "review_path": review_path,
                            "requires_second_review": requires_second_review,
                            "supersedes_export_request_id": supersedes_export_request_id,
                            "request_revision": request_revision,
                            "purpose_statement": purpose_statement,
                            "status": status,
                            "submitted_by": submitted_by,
                            "sla_hours": self._sla_hours(),
                            "release_pack_key": release_pack_key,
                            "release_pack_sha256": release_pack_sha256,
                            "release_pack_json": release_pack_json,
                        },
                    )
                    request_row = cursor.fetchone()

                    cursor.execute(
                        """
                        INSERT INTO export_request_events (
                          id,
                          export_request_id,
                          event_type,
                          from_status,
                          to_status,
                          actor_user_id,
                          reason
                        )
                        VALUES (
                          %(id)s,
                          %(export_request_id)s,
                          %(event_type)s,
                          NULL,
                          %(to_status)s,
                          %(actor_user_id)s,
                          NULL
                        )
                        """,
                        {
                            "id": str(uuid4()),
                            "export_request_id": request_id,
                            "event_type": request_event_type,
                            "to_status": status,
                            "actor_user_id": submitted_by,
                        },
                    )

                    for row in review_rows:
                        cursor.execute(
                            """
                            INSERT INTO export_request_reviews (
                              id,
                              export_request_id,
                              review_stage,
                              is_required,
                              status,
                              assigned_reviewer_user_id,
                              assigned_at,
                              acted_by_user_id,
                              acted_at,
                              decision_reason,
                              return_comment,
                              review_etag
                            )
                            VALUES (
                              %(id)s,
                              %(export_request_id)s,
                              %(review_stage)s,
                              %(is_required)s,
                              'PENDING',
                              NULL,
                              NULL,
                              NULL,
                              NULL,
                              NULL,
                              NULL,
                              %(review_etag)s
                            )
                            """,
                            {
                                "id": row["id"],
                                "export_request_id": request_id,
                                "review_stage": row["review_stage"],
                                "is_required": row["is_required"],
                                "review_etag": row["review_etag"],
                            },
                        )
                        cursor.execute(
                            """
                            INSERT INTO export_request_review_events (
                              id,
                              review_id,
                              export_request_id,
                              review_stage,
                              event_type,
                              actor_user_id,
                              assigned_reviewer_user_id,
                              decision_reason,
                              return_comment
                            )
                            VALUES (
                              %(id)s,
                              %(review_id)s,
                              %(export_request_id)s,
                              %(review_stage)s,
                              'REVIEW_CREATED',
                              %(actor_user_id)s,
                              NULL,
                              NULL,
                              NULL
                            )
                            """,
                            {
                                "id": str(uuid4()),
                                "review_id": row["id"],
                                "export_request_id": request_id,
                                "review_stage": row["review_stage"],
                                "actor_user_id": submitted_by,
                            },
                        )
                connection.commit()
        except ExportStoreConflictError:
            raise
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Export request creation failed.") from error

        if request_row is None:
            raise ExportStoreUnavailableError("Export request insert returned no row.")
        return self._as_request_record(request_row)

    def list_requests(
        self,
        *,
        project_id: str,
        status: ExportRequestStatus | None,
        requester_id: str | None,
        candidate_kind: ExportCandidateKind | None,
        cursor: int,
        limit: int,
    ) -> ExportRequestListPage:
        self.ensure_schema()
        page_limit = max(1, min(limit, 100))
        offset = max(cursor, 0)
        conditions = ["project_id = %(project_id)s"]
        params: dict[str, object] = {
            "project_id": project_id,
            "limit": page_limit + 1,
            "offset": offset,
        }
        if status is not None:
            conditions.append("status = %(status)s")
            params["status"] = status
        if requester_id is not None:
            conditions.append("submitted_by = %(requester_id)s")
            params["requester_id"] = requester_id
        if candidate_kind is not None:
            conditions.append("candidate_kind = %(candidate_kind)s")
            params["candidate_kind"] = candidate_kind
        where_sql = " AND ".join(conditions)

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_obj:
                    cursor_obj.execute(
                        f"""
                        SELECT
                          id,
                          project_id,
                          candidate_snapshot_id,
                          candidate_origin_phase,
                          candidate_kind,
                          bundle_profile,
                          risk_classification,
                          risk_reason_codes_json,
                          review_path,
                          requires_second_review,
                          supersedes_export_request_id,
                          superseded_by_export_request_id,
                          request_revision,
                          purpose_statement,
                          status,
                          submitted_by,
                          submitted_at,
                          first_review_started_by,
                          first_review_started_at,
                          sla_due_at,
                          last_queue_activity_at,
                          retention_until,
                          final_review_id,
                          final_decision_by,
                          final_decision_at,
                          final_decision_reason,
                          final_return_comment,
                          release_pack_key,
                          release_pack_sha256,
                          release_pack_json,
                          release_pack_created_at,
                          receipt_id,
                          receipt_key,
                          receipt_sha256,
                          receipt_created_by,
                          receipt_created_at,
                          exported_at,
                          created_at,
                          updated_at
                        FROM export_requests
                        WHERE {where_sql}
                        ORDER BY submitted_at DESC, id DESC
                        LIMIT %(limit)s
                        OFFSET %(offset)s
                        """,
                        params,
                    )
                    rows = cursor_obj.fetchall()
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Export request listing failed.") from error

        has_more = len(rows) > page_limit
        visible_rows = rows[:page_limit]
        next_cursor = offset + page_limit if has_more else None
        return ExportRequestListPage(
            items=tuple(self._as_request_record(row) for row in visible_rows),
            next_cursor=next_cursor,
        )

    def get_request(
        self,
        *,
        project_id: str,
        export_request_id: str,
    ) -> ExportRequestRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          candidate_snapshot_id,
                          candidate_origin_phase,
                          candidate_kind,
                          bundle_profile,
                          risk_classification,
                          risk_reason_codes_json,
                          review_path,
                          requires_second_review,
                          supersedes_export_request_id,
                          superseded_by_export_request_id,
                          request_revision,
                          purpose_statement,
                          status,
                          submitted_by,
                          submitted_at,
                          first_review_started_by,
                          first_review_started_at,
                          sla_due_at,
                          last_queue_activity_at,
                          retention_until,
                          final_review_id,
                          final_decision_by,
                          final_decision_at,
                          final_decision_reason,
                          final_return_comment,
                          release_pack_key,
                          release_pack_sha256,
                          release_pack_json,
                          release_pack_created_at,
                          receipt_id,
                          receipt_key,
                          receipt_sha256,
                          receipt_created_by,
                          receipt_created_at,
                          exported_at,
                          created_at,
                          updated_at
                        FROM export_requests
                        WHERE project_id = %(project_id)s
                          AND id = %(export_request_id)s
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "export_request_id": export_request_id,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Export request lookup failed.") from error
        if row is None:
            raise ExportStoreNotFoundError("Export request not found.")
        return self._as_request_record(row)

    def list_request_events(
        self,
        *,
        export_request_id: str,
    ) -> tuple[ExportRequestEventRecord, ...]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          export_request_id,
                          event_type,
                          from_status,
                          to_status,
                          actor_user_id,
                          reason,
                          created_at
                        FROM export_request_events
                        WHERE export_request_id = %(export_request_id)s
                        ORDER BY created_at ASC, id ASC
                        """,
                        {"export_request_id": export_request_id},
                    )
                    rows = cursor.fetchall()
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Export request event listing failed.") from error
        return tuple(self._as_event_record(row) for row in rows)

    def list_request_reviews(
        self,
        *,
        export_request_id: str,
    ) -> tuple[ExportRequestReviewRecord, ...]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          export_request_id,
                          review_stage,
                          is_required,
                          status,
                          assigned_reviewer_user_id,
                          assigned_at,
                          acted_by_user_id,
                          acted_at,
                          decision_reason,
                          return_comment,
                          review_etag,
                          created_at,
                          updated_at
                        FROM export_request_reviews
                        WHERE export_request_id = %(export_request_id)s
                        ORDER BY
                          CASE review_stage
                            WHEN 'PRIMARY' THEN 1
                            WHEN 'SECONDARY' THEN 2
                            ELSE 3
                          END ASC,
                          created_at ASC,
                          id ASC
                        """,
                        {"export_request_id": export_request_id},
                    )
                    rows = cursor.fetchall()
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Export request review listing failed.") from error
        return tuple(self._as_review_record(row) for row in rows)

    def list_request_review_events(
        self,
        *,
        export_request_id: str,
    ) -> tuple[ExportRequestReviewEventRecord, ...]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          review_id,
                          export_request_id,
                          review_stage,
                          event_type,
                          actor_user_id,
                          assigned_reviewer_user_id,
                          decision_reason,
                          return_comment,
                          created_at
                        FROM export_request_review_events
                        WHERE export_request_id = %(export_request_id)s
                        ORDER BY created_at ASC, id ASC
                        """,
                        {"export_request_id": export_request_id},
                    )
                    rows = cursor.fetchall()
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Export review event listing failed.") from error
        return tuple(self._as_review_event_record(row) for row in rows)

    def list_request_receipts(
        self,
        *,
        project_id: str,
        export_request_id: str,
    ) -> tuple[ExportReceiptRecord, ...]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          er.id,
                          er.export_request_id,
                          er.attempt_number,
                          er.supersedes_receipt_id,
                          er.superseded_by_receipt_id,
                          er.receipt_key,
                          er.receipt_sha256,
                          er.created_by,
                          er.created_at,
                          er.exported_at
                        FROM export_receipts AS er
                        INNER JOIN export_requests AS req
                          ON req.id = er.export_request_id
                        WHERE req.project_id = %(project_id)s
                          AND req.id = %(export_request_id)s
                        ORDER BY er.attempt_number DESC, er.created_at DESC, er.id DESC
                        """,
                        {
                            "project_id": project_id,
                            "export_request_id": export_request_id,
                        },
                    )
                    rows = cursor.fetchall()
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Export receipt listing failed.") from error
        return tuple(self._as_receipt_record(row) for row in rows)

    @staticmethod
    def _node_ref(*, artifact_kind: str, stable_identifier: str) -> str:
        return f"{artifact_kind}:{stable_identifier}"

    def _build_provenance_leaves(
        self,
        *,
        cursor: psycopg.Cursor,
        request_row: dict[str, object],
        candidate_row: dict[str, object],
    ) -> tuple[ProvenanceLeaf, ...]:
        request_id = str(request_row["id"])
        candidate_id = str(candidate_row["id"])
        candidate_sha256 = str(candidate_row["candidate_sha256"])
        release_pack_sha256 = str(request_row["release_pack_sha256"])
        if not candidate_sha256.strip():
            raise ExportStoreConflictError("Candidate snapshot is missing immutable candidate_sha256.")
        if not release_pack_sha256.strip():
            raise ExportStoreConflictError("Export request is missing release-pack hash.")

        redaction_run_id: str | None = (
            str(candidate_row["source_artifact_id"])
            if isinstance(candidate_row.get("source_artifact_id"), str)
            and str(candidate_row["source_artifact_id"]).strip()
            else None
        )
        if redaction_run_id is None:
            redaction_run_id = (
                str(candidate_row["governance_run_id"])
                if isinstance(candidate_row.get("governance_run_id"), str)
                and str(candidate_row["governance_run_id"]).strip()
                else None
            )
        if redaction_run_id is None:
            raise ExportStoreConflictError("Candidate snapshot is missing pinned redaction lineage.")

        cursor.execute(
            """
            SELECT
              rr.id,
              rr.input_transcription_run_id,
              rr.policy_snapshot_hash,
              rr.policy_id,
              rr.policy_version,
              rr.detectors_version
            FROM redaction_runs AS rr
            WHERE rr.id = %(run_id)s
            LIMIT 1
            """,
            {"run_id": redaction_run_id},
        )
        redaction_row = cursor.fetchone()
        if redaction_row is None:
            raise ExportStoreConflictError("Pinned redaction lineage is unavailable for candidate snapshot.")

        transcription_run_id = (
            str(redaction_row["input_transcription_run_id"])
            if isinstance(redaction_row.get("input_transcription_run_id"), str)
            and str(redaction_row["input_transcription_run_id"]).strip()
            else None
        )
        if transcription_run_id is None:
            raise ExportStoreConflictError("Pinned redaction lineage is missing transcription run reference.")

        cursor.execute(
            """
            SELECT
              tr.id,
              tr.model_id,
              tr.project_model_assignment_id,
              tr.pipeline_version,
              tr.container_digest,
              tr.prompt_template_sha256,
              tr.status
            FROM transcription_runs AS tr
            WHERE tr.id = %(run_id)s
            LIMIT 1
            """,
            {"run_id": transcription_run_id},
        )
        transcription_row = cursor.fetchone()
        if transcription_row is None:
            raise ExportStoreConflictError("Pinned transcription lineage is unavailable for candidate snapshot.")

        project_model_assignment_id = (
            str(transcription_row["project_model_assignment_id"])
            if isinstance(transcription_row.get("project_model_assignment_id"), str)
            and str(transcription_row["project_model_assignment_id"]).strip()
            else None
        )
        model_leaf_identifier: str
        model_leaf_reference: str
        model_leaf_kind: str

        if project_model_assignment_id is not None:
            cursor.execute(
                """
                SELECT
                  pma.id AS assignment_id,
                  pma.approved_model_id,
                  pma.model_role,
                  pma.status AS assignment_status,
                  am.id AS model_id,
                  am.model_family,
                  am.model_version,
                  am.checksum_sha256
                FROM project_model_assignments AS pma
                INNER JOIN approved_models AS am
                  ON am.id = pma.approved_model_id
                WHERE pma.id = %(assignment_id)s
                LIMIT 1
                """,
                {"assignment_id": project_model_assignment_id},
            )
            model_row = cursor.fetchone()
            if model_row is None:
                raise ExportStoreConflictError(
                    "Pinned project model assignment lineage is unavailable for transcription run."
                )
            model_leaf_kind = "PROJECT_MODEL_ASSIGNMENT"
            model_leaf_identifier = str(model_row["assignment_id"])
            model_leaf_reference = self._sha256_hex(
                canonical_json_bytes(
                    {
                        "approvedModelId": str(model_row["approved_model_id"]),
                        "assignmentStatus": str(model_row["assignment_status"]),
                        "checksumSha256": str(model_row["checksum_sha256"]),
                        "modelFamily": str(model_row["model_family"]),
                        "modelRole": str(model_row["model_role"]),
                        "modelVersion": str(model_row["model_version"]),
                    }
                )
            )
        else:
            model_id = str(transcription_row["model_id"])
            cursor.execute(
                """
                SELECT
                  id,
                  model_role,
                  model_family,
                  model_version,
                  checksum_sha256
                FROM approved_models
                WHERE id = %(model_id)s
                LIMIT 1
                """,
                {"model_id": model_id},
            )
            model_row = cursor.fetchone()
            if model_row is None:
                raise ExportStoreConflictError("Pinned transcription approved-model lineage is unavailable.")
            model_leaf_kind = "APPROVED_MODEL_REFERENCE"
            model_leaf_identifier = str(model_row["id"])
            model_leaf_reference = self._sha256_hex(
                canonical_json_bytes(
                    {
                        "checksumSha256": str(model_row["checksum_sha256"]),
                        "modelFamily": str(model_row["model_family"]),
                        "modelRole": str(model_row["model_role"]),
                        "modelVersion": str(model_row["model_version"]),
                    }
                )
            )

        cursor.execute(
            """
            SELECT
              COALESCE(
                BOOL_OR(
                  basis_primary = 'NER'
                  OR COALESCE(UPPER(basis_secondary_json::text), '') LIKE '%%NER%%'
                ),
                FALSE
              ) AS ner_contributed,
              COALESCE(
                BOOL_OR(
                  assist_explanation_sha256 IS NOT NULL
                  AND btrim(assist_explanation_sha256) <> ''
                ),
                FALSE
              ) AS assist_contributed,
              ARRAY_REMOVE(ARRAY_AGG(DISTINCT NULLIF(btrim(assist_explanation_sha256), '')), NULL)
                AS assist_hashes
            FROM redaction_findings
            WHERE run_id = %(run_id)s
            """,
            {"run_id": redaction_run_id},
        )
        detector_row = cursor.fetchone() or {}
        assist_hashes_raw = detector_row.get("assist_hashes")
        assist_hashes: list[str] = []
        if isinstance(assist_hashes_raw, list):
            for value in assist_hashes_raw:
                if not isinstance(value, str):
                    continue
                normalized = value.strip()
                if not normalized or normalized in assist_hashes:
                    continue
                assist_hashes.append(normalized)
        assist_hashes.sort()

        governance_run_id = (
            str(candidate_row["governance_run_id"])
            if isinstance(candidate_row.get("governance_run_id"), str)
            and str(candidate_row["governance_run_id"]).strip()
            else redaction_run_id
        )
        cursor.execute(
            """
            SELECT
              run_id,
              manifest_id,
              ledger_id,
              last_manifest_sha256,
              last_ledger_sha256,
              ledger_verification_status,
              last_ledger_verification_run_id,
              updated_at
            FROM governance_readiness_projections
            WHERE run_id = %(run_id)s
            LIMIT 1
            """,
            {"run_id": governance_run_id},
        )
        readiness_row = cursor.fetchone() or {}
        manifest_id = (
            str(candidate_row["governance_manifest_id"])
            if isinstance(candidate_row.get("governance_manifest_id"), str)
            and str(candidate_row["governance_manifest_id"]).strip()
            else (
                str(readiness_row["manifest_id"])
                if isinstance(readiness_row.get("manifest_id"), str)
                and str(readiness_row["manifest_id"]).strip()
                else None
            )
        )
        manifest_sha256 = (
            str(candidate_row["governance_manifest_sha256"])
            if isinstance(candidate_row.get("governance_manifest_sha256"), str)
            and str(candidate_row["governance_manifest_sha256"]).strip()
            else (
                str(readiness_row["last_manifest_sha256"])
                if isinstance(readiness_row.get("last_manifest_sha256"), str)
                and str(readiness_row["last_manifest_sha256"]).strip()
                else None
            )
        )
        ledger_id = (
            str(candidate_row["governance_ledger_id"])
            if isinstance(candidate_row.get("governance_ledger_id"), str)
            and str(candidate_row["governance_ledger_id"]).strip()
            else (
                str(readiness_row["ledger_id"])
                if isinstance(readiness_row.get("ledger_id"), str)
                and str(readiness_row["ledger_id"]).strip()
                else None
            )
        )
        ledger_sha256 = (
            str(candidate_row["governance_ledger_sha256"])
            if isinstance(candidate_row.get("governance_ledger_sha256"), str)
            and str(candidate_row["governance_ledger_sha256"]).strip()
            else (
                str(readiness_row["last_ledger_sha256"])
                if isinstance(readiness_row.get("last_ledger_sha256"), str)
                and str(readiness_row["last_ledger_sha256"]).strip()
                else None
            )
        )
        if manifest_id is None or manifest_sha256 is None or ledger_id is None or ledger_sha256 is None:
            raise ExportStoreConflictError(
                "Candidate snapshot is missing pinned governance manifest/ledger lineage."
            )

        verification_run_id = (
            str(readiness_row["last_ledger_verification_run_id"])
            if isinstance(readiness_row.get("last_ledger_verification_run_id"), str)
            and str(readiness_row["last_ledger_verification_run_id"]).strip()
            else None
        )
        verification_row: dict[str, object] | None = None
        if verification_run_id is not None:
            cursor.execute(
                """
                SELECT
                  id,
                  attempt_number,
                  status,
                  verification_result,
                  result_json,
                  created_at
                FROM ledger_verification_runs
                WHERE id = %(verification_run_id)s
                  AND run_id = %(run_id)s
                LIMIT 1
                """,
                {
                    "verification_run_id": verification_run_id,
                    "run_id": governance_run_id,
                },
            )
            verification_row = cursor.fetchone()
        if verification_row is None:
            cursor.execute(
                """
                SELECT
                  id,
                  attempt_number,
                  status,
                  verification_result,
                  result_json,
                  created_at
                FROM ledger_verification_runs
                WHERE run_id = %(run_id)s
                  AND status = 'SUCCEEDED'
                  AND verification_result = 'VALID'
                  AND COALESCE(result_json->>'ledgerSha256', '') = %(ledger_sha256)s
                ORDER BY attempt_number DESC, created_at DESC, id DESC
                LIMIT 1
                """,
                {
                    "run_id": governance_run_id,
                    "ledger_sha256": ledger_sha256,
                },
            )
            verification_row = cursor.fetchone()
        if verification_row is None:
            raise ExportStoreConflictError(
                "Candidate snapshot is missing pinned successful ledger verification lineage."
            )

        policy_reference = (
            str(candidate_row["policy_snapshot_hash"])
            if isinstance(candidate_row.get("policy_snapshot_hash"), str)
            and str(candidate_row["policy_snapshot_hash"]).strip()
            else (
                str(redaction_row["policy_snapshot_hash"])
                if isinstance(redaction_row.get("policy_snapshot_hash"), str)
                and str(redaction_row["policy_snapshot_hash"]).strip()
                else None
            )
        )
        policy_version = (
            str(candidate_row["policy_version"])
            if isinstance(candidate_row.get("policy_version"), str)
            and str(candidate_row["policy_version"]).strip()
            else (
                str(redaction_row["policy_version"])
                if isinstance(redaction_row.get("policy_version"), str)
                and str(redaction_row["policy_version"]).strip()
                else None
            )
        )
        if policy_reference is None and policy_version is None:
            raise ExportStoreConflictError(
                "Candidate snapshot is missing policy lineage required for provenance proof."
            )
        policy_identifier = (
            str(candidate_row["policy_id"])
            if isinstance(candidate_row.get("policy_id"), str)
            and str(candidate_row["policy_id"]).strip()
            else "baseline-policy"
        )
        policy_immutable_reference = policy_reference or f"policy-version:{policy_version}"

        cursor.execute(
            """
            SELECT
              id,
              receipt_sha256
            FROM export_receipts
            WHERE export_request_id = %(export_request_id)s
              AND superseded_by_receipt_id IS NULL
            ORDER BY attempt_number DESC, created_at DESC, id DESC
            LIMIT 1
            """,
            {"export_request_id": request_id},
        )
        receipt_row = cursor.fetchone()

        model_ref = self._node_ref(
            artifact_kind=model_leaf_kind,
            stable_identifier=model_leaf_identifier,
        )
        transcription_ref = self._node_ref(
            artifact_kind="TRANSCRIPTION_RUN",
            stable_identifier=transcription_run_id,
        )
        policy_ref = self._node_ref(
            artifact_kind="POLICY_BASELINE_OR_VERSION",
            stable_identifier=policy_identifier,
        )
        redaction_ref = self._node_ref(
            artifact_kind="REDACTION_RUN",
            stable_identifier=redaction_run_id,
        )
        detector_ref = self._node_ref(
            artifact_kind="DETECTOR_LINEAGE",
            stable_identifier=f"{redaction_run_id}:detectors",
        )
        manifest_ref = self._node_ref(
            artifact_kind="GOVERNANCE_MANIFEST",
            stable_identifier=manifest_id,
        )
        ledger_ref = self._node_ref(
            artifact_kind="GOVERNANCE_LEDGER",
            stable_identifier=ledger_id,
        )
        verification_ref = self._node_ref(
            artifact_kind="LEDGER_VERIFICATION",
            stable_identifier=str(verification_row["id"]),
        )
        readiness_ref = self._node_ref(
            artifact_kind="GOVERNANCE_READINESS_REFERENCE",
            stable_identifier=f"{governance_run_id}:{candidate_id}",
        )
        candidate_ref = self._node_ref(
            artifact_kind="APPROVED_CANDIDATE_SNAPSHOT",
            stable_identifier=candidate_id,
        )
        request_ref = self._node_ref(
            artifact_kind="EXPORT_REQUEST",
            stable_identifier=request_id,
        )

        leaves: list[ProvenanceLeaf] = [
            normalize_leaf(
                artifact_kind=model_leaf_kind,
                stable_identifier=model_leaf_identifier,
                immutable_reference=model_leaf_reference,
                parent_references=(),
            ),
            normalize_leaf(
                artifact_kind="TRANSCRIPTION_RUN",
                stable_identifier=transcription_run_id,
                immutable_reference=self._sha256_hex(
                    canonical_json_bytes(
                        {
                            "containerDigest": str(transcription_row["container_digest"]),
                            "modelId": str(transcription_row["model_id"]),
                            "pipelineVersion": str(transcription_row["pipeline_version"]),
                            "promptTemplateSha256": (
                                str(transcription_row["prompt_template_sha256"])
                                if isinstance(transcription_row.get("prompt_template_sha256"), str)
                                else None
                            ),
                            "status": str(transcription_row["status"]),
                        }
                    )
                ),
                parent_references=(model_ref,),
            ),
            normalize_leaf(
                artifact_kind="POLICY_BASELINE_OR_VERSION",
                stable_identifier=policy_identifier,
                immutable_reference=policy_immutable_reference,
                parent_references=(),
            ),
            normalize_leaf(
                artifact_kind="REDACTION_RUN",
                stable_identifier=redaction_run_id,
                immutable_reference=self._sha256_hex(
                    canonical_json_bytes(
                        {
                            "detectorsVersion": str(redaction_row["detectors_version"]),
                            "policySnapshotHash": (
                                str(redaction_row["policy_snapshot_hash"])
                                if isinstance(redaction_row.get("policy_snapshot_hash"), str)
                                else None
                            ),
                            "policyVersion": (
                                str(redaction_row["policy_version"])
                                if isinstance(redaction_row.get("policy_version"), str)
                                else None
                            ),
                            "transcriptionRunId": transcription_run_id,
                        }
                    )
                ),
                parent_references=(transcription_ref, policy_ref),
            ),
            normalize_leaf(
                artifact_kind="DETECTOR_LINEAGE",
                stable_identifier=f"{redaction_run_id}:detectors",
                immutable_reference=self._sha256_hex(
                    canonical_json_bytes(
                        {
                            "assistContributed": bool(detector_row.get("assist_contributed", False)),
                            "assistLineageHashes": assist_hashes,
                            "detectorsVersion": str(redaction_row["detectors_version"]),
                            "nerContributed": bool(detector_row.get("ner_contributed", False)),
                            "policySnapshotHash": (
                                str(redaction_row["policy_snapshot_hash"])
                                if isinstance(redaction_row.get("policy_snapshot_hash"), str)
                                else None
                            ),
                        }
                    )
                ),
                parent_references=(redaction_ref, policy_ref),
            ),
            normalize_leaf(
                artifact_kind="GOVERNANCE_MANIFEST",
                stable_identifier=manifest_id,
                immutable_reference=manifest_sha256,
                parent_references=(redaction_ref,),
            ),
            normalize_leaf(
                artifact_kind="GOVERNANCE_LEDGER",
                stable_identifier=ledger_id,
                immutable_reference=ledger_sha256,
                parent_references=(redaction_ref,),
            ),
            normalize_leaf(
                artifact_kind="LEDGER_VERIFICATION",
                stable_identifier=str(verification_row["id"]),
                immutable_reference=self._sha256_hex(
                    canonical_json_bytes(
                        {
                            "attemptNumber": int(verification_row["attempt_number"]),
                            "result": str(verification_row["verification_result"]),
                            "resultJson": (
                                dict(verification_row["result_json"])
                                if isinstance(verification_row.get("result_json"), dict)
                                else {}
                            ),
                            "status": str(verification_row["status"]),
                        }
                    )
                ),
                parent_references=(ledger_ref,),
            ),
            normalize_leaf(
                artifact_kind="GOVERNANCE_READINESS_REFERENCE",
                stable_identifier=f"{governance_run_id}:{candidate_id}",
                immutable_reference=self._sha256_hex(
                    canonical_json_bytes(
                        {
                            "ledgerId": ledger_id,
                            "ledgerSha256": ledger_sha256,
                            "manifestId": manifest_id,
                            "manifestSha256": manifest_sha256,
                            "verificationRunId": str(verification_row["id"]),
                        }
                    )
                ),
                parent_references=(manifest_ref, ledger_ref, verification_ref),
            ),
            normalize_leaf(
                artifact_kind="APPROVED_CANDIDATE_SNAPSHOT",
                stable_identifier=candidate_id,
                immutable_reference=candidate_sha256,
                parent_references=(redaction_ref, manifest_ref, ledger_ref, policy_ref),
            ),
            normalize_leaf(
                artifact_kind="EXPORT_REQUEST",
                stable_identifier=request_id,
                immutable_reference=self._sha256_hex(
                    canonical_json_bytes(
                        {
                            "releasePackSha256": release_pack_sha256,
                            "requestRevision": int(request_row["request_revision"]),
                            "status": str(request_row["status"]),
                        }
                    )
                ),
                parent_references=(candidate_ref, readiness_ref),
            ),
        ]

        if isinstance(receipt_row, dict):
            receipt_id = str(receipt_row["id"])
            receipt_sha256 = str(receipt_row["receipt_sha256"])
            leaves.append(
                normalize_leaf(
                    artifact_kind="EXPORT_RECEIPT",
                    stable_identifier=receipt_id,
                    immutable_reference=receipt_sha256,
                    parent_references=(request_ref,),
                )
            )

        return tuple(leaves)

    def _load_proof_artifact_payload(self, *, proof_artifact_key: str) -> dict[str, object]:
        payload_bytes = self._read_storage_object_bytes(object_key=proof_artifact_key)
        try:
            loaded = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ExportStoreUnavailableError("Provenance proof artifact is not valid canonical JSON.") from error
        if not isinstance(loaded, dict):
            raise ExportStoreUnavailableError("Provenance proof artifact payload must be a JSON object.")
        return dict(loaded)

    def generate_provenance_proof(
        self,
        *,
        project_id: str,
        export_request_id: str,
        actor_user_id: str,
        force_regenerate: bool = False,
    ) -> ProvenanceProofRecord:
        self.ensure_schema()
        now = datetime.now(UTC)
        created_row: dict[str, object] | None = None
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          candidate_snapshot_id,
                          status,
                          request_revision,
                          release_pack_sha256
                        FROM export_requests
                        WHERE project_id = %(project_id)s
                          AND id = %(export_request_id)s
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "export_request_id": export_request_id,
                        },
                    )
                    request_row = cursor.fetchone()
                    if request_row is None:
                        raise ExportStoreNotFoundError("Export request not found.")
                    request_status = str(request_row.get("status") or "")
                    if request_status not in {"APPROVED", "EXPORTED"}:
                        raise ExportStoreConflictError(
                            "Provenance proofs require an APPROVED or EXPORTED export request."
                        )

                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          source_phase,
                          source_artifact_kind,
                          source_run_id,
                          source_artifact_id,
                          governance_run_id,
                          governance_manifest_id,
                          governance_ledger_id,
                          governance_manifest_sha256,
                          governance_ledger_sha256,
                          policy_snapshot_hash,
                          policy_id,
                          policy_family_id,
                          policy_version,
                          candidate_kind,
                          artefact_manifest_json,
                          candidate_sha256,
                          eligibility_status,
                          supersedes_candidate_snapshot_id,
                          superseded_by_candidate_snapshot_id,
                          created_by,
                          created_at
                        FROM export_candidate_snapshots
                        WHERE project_id = %(project_id)s
                          AND id = %(candidate_snapshot_id)s
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "candidate_snapshot_id": str(request_row["candidate_snapshot_id"]),
                        },
                    )
                    candidate_row = cursor.fetchone()
                    if candidate_row is None:
                        raise ExportStoreConflictError("Pinned candidate snapshot is unavailable.")

                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          export_request_id,
                          candidate_snapshot_id,
                          attempt_number,
                          supersedes_proof_id,
                          superseded_by_proof_id,
                          root_sha256,
                          signature_key_ref,
                          signature_bytes_key,
                          proof_artifact_key,
                          proof_artifact_sha256,
                          created_by,
                          created_at
                        FROM provenance_proofs
                        WHERE export_request_id = %(export_request_id)s
                          AND superseded_by_proof_id IS NULL
                        ORDER BY attempt_number DESC, created_at DESC, id DESC
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {"export_request_id": export_request_id},
                    )
                    current_row = cursor.fetchone()
                    if current_row is not None and not force_regenerate:
                        connection.commit()
                        return self._as_provenance_proof_record(current_row)

                    leaves = self._build_provenance_leaves(
                        cursor=cursor,
                        request_row=request_row,
                        candidate_row=candidate_row,
                    )
                    merkle: MerkleTreeResult = build_merkle_tree(leaves)
                    signature = sign_root_sha256(
                        root_sha256=merkle.root_sha256,
                        key_ref=self._settings.provenance_signing_key_ref,
                        secret=self._settings.provenance_signing_secret,
                    )
                    proof_id = str(uuid4())
                    signature_key = self._build_provenance_signature_key(
                        project_id=project_id,
                        export_request_id=export_request_id,
                        proof_id=proof_id,
                    )
                    proof_artifact_key = self._build_provenance_artifact_key(
                        project_id=project_id,
                        export_request_id=export_request_id,
                        proof_id=proof_id,
                    )
                    cursor.execute(
                        """
                        SELECT COALESCE(MAX(attempt_number), 0)::INT AS last_attempt
                        FROM provenance_proofs
                        WHERE export_request_id = %(export_request_id)s
                        """,
                        {"export_request_id": export_request_id},
                    )
                    attempt_row = cursor.fetchone() or {}
                    attempt_number = int(attempt_row.get("last_attempt") or 0) + 1

                    proof_artifact = build_proof_artifact_payload(
                        proof_id=proof_id,
                        project_id=project_id,
                        export_request_id=export_request_id,
                        candidate_snapshot_id=str(request_row["candidate_snapshot_id"]),
                        attempt_number=attempt_number,
                        created_at=now,
                        merkle=merkle,
                        signature=signature,
                    )
                    proof_artifact_bytes = canonical_json_bytes(proof_artifact)
                    proof_artifact_sha256 = self._sha256_hex(proof_artifact_bytes)
                    self._write_storage_object_idempotent(
                        object_key=signature_key,
                        payload=signature.signature_bytes,
                    )
                    self._write_storage_object_idempotent(
                        object_key=proof_artifact_key,
                        payload=proof_artifact_bytes,
                    )

                    supersedes_proof_id = (
                        str(current_row["id"]) if isinstance(current_row.get("id"), str) else None
                    )
                    cursor.execute(
                        """
                        INSERT INTO provenance_proofs (
                          id,
                          project_id,
                          export_request_id,
                          candidate_snapshot_id,
                          attempt_number,
                          supersedes_proof_id,
                          superseded_by_proof_id,
                          root_sha256,
                          signature_key_ref,
                          signature_bytes_key,
                          proof_artifact_key,
                          proof_artifact_sha256,
                          created_by,
                          created_at
                        )
                        VALUES (
                          %(id)s,
                          %(project_id)s,
                          %(export_request_id)s,
                          %(candidate_snapshot_id)s,
                          %(attempt_number)s,
                          %(supersedes_proof_id)s,
                          NULL,
                          %(root_sha256)s,
                          %(signature_key_ref)s,
                          %(signature_bytes_key)s,
                          %(proof_artifact_key)s,
                          %(proof_artifact_sha256)s,
                          %(created_by)s,
                          %(created_at)s
                        )
                        """,
                        {
                            "id": proof_id,
                            "project_id": project_id,
                            "export_request_id": export_request_id,
                            "candidate_snapshot_id": str(request_row["candidate_snapshot_id"]),
                            "attempt_number": attempt_number,
                            "supersedes_proof_id": supersedes_proof_id,
                            "root_sha256": merkle.root_sha256,
                            "signature_key_ref": signature.key_ref,
                            "signature_bytes_key": signature_key,
                            "proof_artifact_key": proof_artifact_key,
                            "proof_artifact_sha256": proof_artifact_sha256,
                            "created_by": actor_user_id,
                            "created_at": now,
                        },
                    )
                    if supersedes_proof_id is not None:
                        cursor.execute(
                            """
                            UPDATE provenance_proofs
                            SET superseded_by_proof_id = %(new_proof_id)s
                            WHERE id = %(superseded_id)s
                              AND superseded_by_proof_id IS NULL
                            """,
                            {
                                "new_proof_id": proof_id,
                                "superseded_id": supersedes_proof_id,
                            },
                        )
                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          export_request_id,
                          candidate_snapshot_id,
                          attempt_number,
                          supersedes_proof_id,
                          superseded_by_proof_id,
                          root_sha256,
                          signature_key_ref,
                          signature_bytes_key,
                          proof_artifact_key,
                          proof_artifact_sha256,
                          created_by,
                          created_at
                        FROM provenance_proofs
                        WHERE id = %(proof_id)s
                        LIMIT 1
                        """,
                        {"proof_id": proof_id},
                    )
                    created_row = cursor.fetchone()
                connection.commit()
        except ExportStoreConflictError:
            raise
        except ExportStoreNotFoundError:
            raise
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Provenance proof generation failed.") from error
        if created_row is None:
            raise ExportStoreUnavailableError("Provenance proof row could not be read after insert.")
        return self._as_provenance_proof_record(created_row)

    def list_provenance_proofs(
        self,
        *,
        project_id: str,
        export_request_id: str,
    ) -> tuple[ProvenanceProofRecord, ...]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          pp.id,
                          pp.project_id,
                          pp.export_request_id,
                          pp.candidate_snapshot_id,
                          pp.attempt_number,
                          pp.supersedes_proof_id,
                          pp.superseded_by_proof_id,
                          pp.root_sha256,
                          pp.signature_key_ref,
                          pp.signature_bytes_key,
                          pp.proof_artifact_key,
                          pp.proof_artifact_sha256,
                          pp.created_by,
                          pp.created_at
                        FROM provenance_proofs AS pp
                        INNER JOIN export_requests AS req
                          ON req.id = pp.export_request_id
                        WHERE req.project_id = %(project_id)s
                          AND req.id = %(export_request_id)s
                        ORDER BY pp.attempt_number DESC, pp.created_at DESC, pp.id DESC
                        """,
                        {
                            "project_id": project_id,
                            "export_request_id": export_request_id,
                        },
                    )
                    rows = cursor.fetchall()
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Provenance proof listing failed.") from error
        return tuple(self._as_provenance_proof_record(row) for row in rows)

    def get_current_provenance_proof(
        self,
        *,
        project_id: str,
        export_request_id: str,
    ) -> ProvenanceProofRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          pp.id,
                          pp.project_id,
                          pp.export_request_id,
                          pp.candidate_snapshot_id,
                          pp.attempt_number,
                          pp.supersedes_proof_id,
                          pp.superseded_by_proof_id,
                          pp.root_sha256,
                          pp.signature_key_ref,
                          pp.signature_bytes_key,
                          pp.proof_artifact_key,
                          pp.proof_artifact_sha256,
                          pp.created_by,
                          pp.created_at
                        FROM provenance_proofs AS pp
                        INNER JOIN export_requests AS req
                          ON req.id = pp.export_request_id
                        WHERE req.project_id = %(project_id)s
                          AND req.id = %(export_request_id)s
                          AND pp.superseded_by_proof_id IS NULL
                        ORDER BY pp.attempt_number DESC, pp.created_at DESC, pp.id DESC
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "export_request_id": export_request_id,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Current provenance proof lookup failed.") from error
        if row is None:
            raise ExportStoreNotFoundError("Current provenance proof not found.")
        return self._as_provenance_proof_record(row)

    def get_provenance_proof(
        self,
        *,
        project_id: str,
        export_request_id: str,
        proof_id: str,
    ) -> ProvenanceProofRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          pp.id,
                          pp.project_id,
                          pp.export_request_id,
                          pp.candidate_snapshot_id,
                          pp.attempt_number,
                          pp.supersedes_proof_id,
                          pp.superseded_by_proof_id,
                          pp.root_sha256,
                          pp.signature_key_ref,
                          pp.signature_bytes_key,
                          pp.proof_artifact_key,
                          pp.proof_artifact_sha256,
                          pp.created_by,
                          pp.created_at
                        FROM provenance_proofs AS pp
                        INNER JOIN export_requests AS req
                          ON req.id = pp.export_request_id
                        WHERE req.project_id = %(project_id)s
                          AND req.id = %(export_request_id)s
                          AND pp.id = %(proof_id)s
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "export_request_id": export_request_id,
                            "proof_id": proof_id,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Provenance proof lookup failed.") from error
        if row is None:
            raise ExportStoreNotFoundError("Provenance proof not found.")
        return self._as_provenance_proof_record(row)

    def read_provenance_proof_artifact(
        self,
        *,
        proof: ProvenanceProofRecord,
    ) -> dict[str, object]:
        payload = self._load_proof_artifact_payload(proof_artifact_key=proof.proof_artifact_key)
        computed_sha256 = self._sha256_hex(canonical_json_bytes(payload))
        if computed_sha256 != proof.proof_artifact_sha256:
            raise ExportStoreUnavailableError(
                "Provenance proof artifact hash does not match the stored immutable hash."
            )
        return payload

    def _append_bundle_event(
        self,
        *,
        cursor: psycopg.Cursor,
        bundle_id: str,
        event_type: BundleEventType,
        actor_user_id: str | None,
        created_at: datetime,
        reason: str | None = None,
        verification_run_id: str | None = None,
        validation_run_id: str | None = None,
    ) -> None:
        cursor.execute(
            """
            INSERT INTO bundle_events (
              id,
              bundle_id,
              event_type,
              verification_run_id,
              validation_run_id,
              actor_user_id,
              reason,
              created_at
            )
            VALUES (
              %(id)s,
              %(bundle_id)s,
              %(event_type)s,
              %(verification_run_id)s,
              %(validation_run_id)s,
              %(actor_user_id)s,
              %(reason)s,
              %(created_at)s
            )
            """,
            {
                "id": str(uuid4()),
                "bundle_id": bundle_id,
                "event_type": event_type,
                "verification_run_id": verification_run_id,
                "validation_run_id": validation_run_id,
                "actor_user_id": actor_user_id,
                "reason": reason,
                "created_at": created_at,
            },
        )

    def _build_bundle_attempt(
        self,
        *,
        project_id: str,
        export_request_id: str,
        bundle_kind: DepositBundleKind,
        actor_user_id: str,
        force_rebuild: bool,
        rebuild_requested_bundle_id: str | None = None,
    ) -> DepositBundleRecord:
        self.ensure_schema()
        base_now = datetime.now(UTC)
        created_row: dict[str, object] | None = None
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          candidate_snapshot_id,
                          candidate_origin_phase,
                          candidate_kind,
                          bundle_profile,
                          risk_classification,
                          risk_reason_codes_json,
                          review_path,
                          requires_second_review,
                          supersedes_export_request_id,
                          superseded_by_export_request_id,
                          request_revision,
                          purpose_statement,
                          status,
                          submitted_by,
                          submitted_at,
                          first_review_started_by,
                          first_review_started_at,
                          sla_due_at,
                          last_queue_activity_at,
                          retention_until,
                          final_review_id,
                          final_decision_by,
                          final_decision_at,
                          final_decision_reason,
                          final_return_comment,
                          release_pack_key,
                          release_pack_sha256,
                          release_pack_json,
                          release_pack_created_at,
                          receipt_id,
                          receipt_key,
                          receipt_sha256,
                          receipt_created_by,
                          receipt_created_at,
                          exported_at,
                          created_at,
                          updated_at
                        FROM export_requests
                        WHERE project_id = %(project_id)s
                          AND id = %(export_request_id)s
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "export_request_id": export_request_id,
                        },
                    )
                    request_row = cursor.fetchone()
                    if request_row is None:
                        raise ExportStoreNotFoundError("Export request not found.")
                    request_status = str(request_row["status"])
                    if request_status not in {"APPROVED", "EXPORTED"}:
                        raise ExportStoreConflictError(
                            "Deposit bundles require an APPROVED or EXPORTED export request."
                        )

                    if rebuild_requested_bundle_id is not None:
                        cursor.execute(
                            """
                            SELECT
                              id,
                              bundle_kind
                            FROM deposit_bundles
                            WHERE export_request_id = %(export_request_id)s
                              AND id = %(bundle_id)s
                            LIMIT 1
                            FOR UPDATE
                            """,
                            {
                                "export_request_id": export_request_id,
                                "bundle_id": rebuild_requested_bundle_id,
                            },
                        )
                        rebuild_row = cursor.fetchone()
                        if rebuild_row is None:
                            raise ExportStoreNotFoundError("Deposit bundle not found.")
                        if str(rebuild_row["bundle_kind"]) != bundle_kind:
                            raise ExportStoreConflictError(
                                "Rebuild target bundle kind does not match requested lineage."
                            )

                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          source_phase,
                          source_artifact_kind,
                          source_run_id,
                          source_artifact_id,
                          governance_run_id,
                          governance_manifest_id,
                          governance_ledger_id,
                          governance_manifest_sha256,
                          governance_ledger_sha256,
                          policy_snapshot_hash,
                          policy_id,
                          policy_family_id,
                          policy_version,
                          candidate_kind,
                          artefact_manifest_json,
                          candidate_sha256,
                          eligibility_status,
                          supersedes_candidate_snapshot_id,
                          superseded_by_candidate_snapshot_id,
                          created_by,
                          created_at
                        FROM export_candidate_snapshots
                        WHERE project_id = %(project_id)s
                          AND id = %(candidate_snapshot_id)s
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "candidate_snapshot_id": str(request_row["candidate_snapshot_id"]),
                        },
                    )
                    candidate_row = cursor.fetchone()
                    if candidate_row is None:
                        raise ExportStoreConflictError("Pinned candidate snapshot is unavailable.")

                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          export_request_id,
                          candidate_snapshot_id,
                          attempt_number,
                          supersedes_proof_id,
                          superseded_by_proof_id,
                          root_sha256,
                          signature_key_ref,
                          signature_bytes_key,
                          proof_artifact_key,
                          proof_artifact_sha256,
                          created_by,
                          created_at
                        FROM provenance_proofs
                        WHERE export_request_id = %(export_request_id)s
                          AND superseded_by_proof_id IS NULL
                        ORDER BY attempt_number DESC, created_at DESC, id DESC
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {"export_request_id": export_request_id},
                    )
                    proof_row = cursor.fetchone()
                    if proof_row is None:
                        raise ExportStoreConflictError(
                            "Provenance proof is required before deposit bundle creation."
                        )
                    proof = self._as_provenance_proof_record(proof_row)

                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          export_request_id,
                          candidate_snapshot_id,
                          provenance_proof_id,
                          provenance_proof_artifact_sha256,
                          bundle_kind,
                          status,
                          attempt_number,
                          supersedes_bundle_id,
                          superseded_by_bundle_id,
                          bundle_key,
                          bundle_sha256,
                          failure_reason,
                          created_by,
                          created_at,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at
                        FROM deposit_bundles
                        WHERE export_request_id = %(export_request_id)s
                          AND candidate_snapshot_id = %(candidate_snapshot_id)s
                          AND bundle_kind = %(bundle_kind)s
                          AND superseded_by_bundle_id IS NULL
                        ORDER BY attempt_number DESC, created_at DESC, id DESC
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "export_request_id": export_request_id,
                            "candidate_snapshot_id": str(request_row["candidate_snapshot_id"]),
                            "bundle_kind": bundle_kind,
                        },
                    )
                    current_bundle_row = cursor.fetchone()
                    if current_bundle_row is not None and not force_rebuild:
                        connection.commit()
                        return self._as_deposit_bundle_record(current_bundle_row)

                    cursor.execute(
                        """
                        SELECT COALESCE(MAX(attempt_number), 0)::INT AS last_attempt
                        FROM deposit_bundles
                        WHERE export_request_id = %(export_request_id)s
                          AND candidate_snapshot_id = %(candidate_snapshot_id)s
                          AND bundle_kind = %(bundle_kind)s
                        """,
                        {
                            "export_request_id": export_request_id,
                            "candidate_snapshot_id": str(request_row["candidate_snapshot_id"]),
                            "bundle_kind": bundle_kind,
                        },
                    )
                    attempt_row = cursor.fetchone() or {}
                    attempt_number = int(attempt_row.get("last_attempt") or 0) + 1
                    bundle_id = str(uuid4())
                    supersedes_bundle_id = (
                        str(current_bundle_row["id"])
                        if isinstance(current_bundle_row.get("id"), str)
                        else None
                    )

                    queued_at = base_now
                    started_at = base_now + timedelta(microseconds=1)
                    finished_at = base_now + timedelta(microseconds=2)

                    cursor.execute(
                        """
                        INSERT INTO deposit_bundles (
                          id,
                          project_id,
                          export_request_id,
                          candidate_snapshot_id,
                          provenance_proof_id,
                          provenance_proof_artifact_sha256,
                          bundle_kind,
                          status,
                          attempt_number,
                          supersedes_bundle_id,
                          superseded_by_bundle_id,
                          bundle_key,
                          bundle_sha256,
                          failure_reason,
                          created_by,
                          created_at,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at
                        )
                        VALUES (
                          %(id)s,
                          %(project_id)s,
                          %(export_request_id)s,
                          %(candidate_snapshot_id)s,
                          %(provenance_proof_id)s,
                          %(provenance_proof_artifact_sha256)s,
                          %(bundle_kind)s,
                          'QUEUED',
                          %(attempt_number)s,
                          %(supersedes_bundle_id)s,
                          NULL,
                          NULL,
                          NULL,
                          NULL,
                          %(created_by)s,
                          %(created_at)s,
                          NULL,
                          NULL,
                          NULL,
                          NULL
                        )
                        """,
                        {
                            "id": bundle_id,
                            "project_id": project_id,
                            "export_request_id": export_request_id,
                            "candidate_snapshot_id": str(request_row["candidate_snapshot_id"]),
                            "provenance_proof_id": proof.id,
                            "provenance_proof_artifact_sha256": proof.proof_artifact_sha256,
                            "bundle_kind": bundle_kind,
                            "attempt_number": attempt_number,
                            "supersedes_bundle_id": supersedes_bundle_id,
                            "created_by": actor_user_id,
                            "created_at": queued_at,
                        },
                    )

                    if supersedes_bundle_id is not None:
                        cursor.execute(
                            """
                            UPDATE deposit_bundles
                            SET superseded_by_bundle_id = %(bundle_id)s
                            WHERE id = %(superseded_bundle_id)s
                              AND superseded_by_bundle_id IS NULL
                            """,
                            {
                                "bundle_id": bundle_id,
                                "superseded_bundle_id": supersedes_bundle_id,
                            },
                        )

                    cursor.execute(
                        """
                        INSERT INTO bundle_verification_projections (
                          bundle_id,
                          status,
                          last_verification_run_id,
                          verified_at,
                          updated_at
                        )
                        VALUES (
                          %(bundle_id)s,
                          'PENDING',
                          NULL,
                          NULL,
                          %(updated_at)s
                        )
                        ON CONFLICT (bundle_id) DO UPDATE
                        SET
                          status = EXCLUDED.status,
                          last_verification_run_id = EXCLUDED.last_verification_run_id,
                          verified_at = EXCLUDED.verified_at,
                          updated_at = EXCLUDED.updated_at
                        """,
                        {
                            "bundle_id": bundle_id,
                            "updated_at": queued_at,
                        },
                    )

                    if force_rebuild:
                        self._append_bundle_event(
                            cursor=cursor,
                            bundle_id=bundle_id,
                            event_type="BUNDLE_REBUILD_REQUESTED",
                            actor_user_id=actor_user_id,
                            created_at=queued_at,
                            reason=(
                                f"requested_from:{rebuild_requested_bundle_id}"
                                if rebuild_requested_bundle_id is not None
                                else None
                            ),
                        )
                    self._append_bundle_event(
                        cursor=cursor,
                        bundle_id=bundle_id,
                        event_type="BUNDLE_BUILD_QUEUED",
                        actor_user_id=actor_user_id,
                        created_at=queued_at,
                    )

                    cursor.execute(
                        """
                        UPDATE deposit_bundles
                        SET
                          status = 'RUNNING',
                          started_at = %(started_at)s,
                          failure_reason = NULL,
                          canceled_by = NULL,
                          canceled_at = NULL
                        WHERE id = %(bundle_id)s
                        """,
                        {
                            "bundle_id": bundle_id,
                            "started_at": started_at,
                        },
                    )
                    self._append_bundle_event(
                        cursor=cursor,
                        bundle_id=bundle_id,
                        event_type="BUNDLE_BUILD_STARTED",
                        actor_user_id=actor_user_id,
                        created_at=started_at,
                    )

                    request = self._as_request_record(request_row)
                    candidate = self._as_candidate_record(candidate_row)
                    build_failed_reason: str | None = None
                    bundle_key: str | None = None
                    bundle_sha256: str | None = None
                    try:
                        proof_artifact = self.read_provenance_proof_artifact(proof=proof)
                        bundle_metadata = self._build_bundle_payload(
                            bundle_id=bundle_id,
                            bundle_kind=bundle_kind,
                            bundle_attempt_number=attempt_number,
                            request=request,
                            candidate=candidate,
                            proof=proof,
                            proof_artifact=proof_artifact,
                            built_at=started_at,
                        )
                        archive_bytes = self._build_bundle_archive_bytes(
                            metadata_payload=bundle_metadata,
                            proof_artifact=proof_artifact,
                        )
                        bundle_sha256 = self._sha256_hex(archive_bytes)
                        bundle_key = self._build_bundle_object_key(
                            project_id=project_id,
                            export_request_id=export_request_id,
                            bundle_id=bundle_id,
                            bundle_kind=bundle_kind,
                        )
                        self._write_storage_object_idempotent(
                            object_key=bundle_key,
                            payload=archive_bytes,
                        )
                    except Exception as error:  # pragma: no cover - failure path guard
                        build_failed_reason = str(error).strip()[:5000] or "Bundle build failed."

                    if build_failed_reason is None:
                        cursor.execute(
                            """
                            UPDATE deposit_bundles
                            SET
                              status = 'SUCCEEDED',
                              bundle_key = %(bundle_key)s,
                              bundle_sha256 = %(bundle_sha256)s,
                              failure_reason = NULL,
                              finished_at = %(finished_at)s
                            WHERE id = %(bundle_id)s
                            """,
                            {
                                "bundle_id": bundle_id,
                                "bundle_key": bundle_key,
                                "bundle_sha256": bundle_sha256,
                                "finished_at": finished_at,
                            },
                        )
                        self._append_bundle_event(
                            cursor=cursor,
                            bundle_id=bundle_id,
                            event_type="BUNDLE_BUILD_SUCCEEDED",
                            actor_user_id=actor_user_id,
                            created_at=finished_at,
                            reason=(
                                f"bundle_sha256:{bundle_sha256}"
                                if isinstance(bundle_sha256, str)
                                else None
                            ),
                        )
                    else:
                        cursor.execute(
                            """
                            UPDATE deposit_bundles
                            SET
                              status = 'FAILED',
                              bundle_key = NULL,
                              bundle_sha256 = NULL,
                              failure_reason = %(failure_reason)s,
                              finished_at = %(finished_at)s
                            WHERE id = %(bundle_id)s
                            """,
                            {
                                "bundle_id": bundle_id,
                                "failure_reason": build_failed_reason,
                                "finished_at": finished_at,
                            },
                        )
                        self._append_bundle_event(
                            cursor=cursor,
                            bundle_id=bundle_id,
                            event_type="BUNDLE_BUILD_FAILED",
                            actor_user_id=actor_user_id,
                            created_at=finished_at,
                            reason=build_failed_reason,
                        )

                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          export_request_id,
                          candidate_snapshot_id,
                          provenance_proof_id,
                          provenance_proof_artifact_sha256,
                          bundle_kind,
                          status,
                          attempt_number,
                          supersedes_bundle_id,
                          superseded_by_bundle_id,
                          bundle_key,
                          bundle_sha256,
                          failure_reason,
                          created_by,
                          created_at,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at
                        FROM deposit_bundles
                        WHERE id = %(bundle_id)s
                        LIMIT 1
                        """,
                        {"bundle_id": bundle_id},
                    )
                    created_row = cursor.fetchone()
                connection.commit()
        except ExportStoreConflictError:
            raise
        except ExportStoreNotFoundError:
            raise
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Deposit bundle build failed.") from error
        if created_row is None:
            raise ExportStoreUnavailableError("Deposit bundle row could not be read after build.")
        return self._as_deposit_bundle_record(created_row)

    def create_or_get_deposit_bundle(
        self,
        *,
        project_id: str,
        export_request_id: str,
        bundle_kind: DepositBundleKind,
        actor_user_id: str,
    ) -> DepositBundleRecord:
        return self._build_bundle_attempt(
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_kind=bundle_kind,
            actor_user_id=actor_user_id,
            force_rebuild=False,
        )

    def rebuild_deposit_bundle(
        self,
        *,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        actor_user_id: str,
    ) -> DepositBundleRecord:
        target = self.get_deposit_bundle(
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
        )
        return self._build_bundle_attempt(
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_kind=target.bundle_kind,
            actor_user_id=actor_user_id,
            force_rebuild=True,
            rebuild_requested_bundle_id=bundle_id,
        )

    def list_deposit_bundles(
        self,
        *,
        project_id: str,
        export_request_id: str,
    ) -> tuple[DepositBundleRecord, ...]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          b.id,
                          b.project_id,
                          b.export_request_id,
                          b.candidate_snapshot_id,
                          b.provenance_proof_id,
                          b.provenance_proof_artifact_sha256,
                          b.bundle_kind,
                          b.status,
                          b.attempt_number,
                          b.supersedes_bundle_id,
                          b.superseded_by_bundle_id,
                          b.bundle_key,
                          b.bundle_sha256,
                          b.failure_reason,
                          b.created_by,
                          b.created_at,
                          b.started_at,
                          b.finished_at,
                          b.canceled_by,
                          b.canceled_at
                        FROM deposit_bundles AS b
                        INNER JOIN export_requests AS req
                          ON req.id = b.export_request_id
                        WHERE req.project_id = %(project_id)s
                          AND req.id = %(export_request_id)s
                        ORDER BY
                          CASE b.bundle_kind
                            WHEN 'SAFEGUARDED_DEPOSIT' THEN 1
                            WHEN 'CONTROLLED_EVIDENCE' THEN 2
                            ELSE 3
                          END ASC,
                          b.attempt_number DESC,
                          b.created_at DESC,
                          b.id DESC
                        """,
                        {
                            "project_id": project_id,
                            "export_request_id": export_request_id,
                        },
                    )
                    rows = cursor.fetchall()
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Deposit bundle listing failed.") from error
        return tuple(self._as_deposit_bundle_record(row) for row in rows)

    def get_deposit_bundle(
        self,
        *,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
    ) -> DepositBundleRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          b.id,
                          b.project_id,
                          b.export_request_id,
                          b.candidate_snapshot_id,
                          b.provenance_proof_id,
                          b.provenance_proof_artifact_sha256,
                          b.bundle_kind,
                          b.status,
                          b.attempt_number,
                          b.supersedes_bundle_id,
                          b.superseded_by_bundle_id,
                          b.bundle_key,
                          b.bundle_sha256,
                          b.failure_reason,
                          b.created_by,
                          b.created_at,
                          b.started_at,
                          b.finished_at,
                          b.canceled_by,
                          b.canceled_at
                        FROM deposit_bundles AS b
                        INNER JOIN export_requests AS req
                          ON req.id = b.export_request_id
                        WHERE req.project_id = %(project_id)s
                          AND req.id = %(export_request_id)s
                          AND b.id = %(bundle_id)s
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "export_request_id": export_request_id,
                            "bundle_id": bundle_id,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Deposit bundle lookup failed.") from error
        if row is None:
            raise ExportStoreNotFoundError("Deposit bundle not found.")
        return self._as_deposit_bundle_record(row)

    def get_deposit_bundle_status(
        self,
        *,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
    ) -> DepositBundleRecord:
        return self.get_deposit_bundle(
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
        )

    def list_deposit_bundle_events(
        self,
        *,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
    ) -> tuple[BundleEventRecord, ...]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          ev.id,
                          ev.bundle_id,
                          ev.event_type,
                          ev.verification_run_id,
                          ev.validation_run_id,
                          ev.actor_user_id,
                          ev.reason,
                          ev.created_at
                        FROM bundle_events AS ev
                        INNER JOIN deposit_bundles AS b
                          ON b.id = ev.bundle_id
                        INNER JOIN export_requests AS req
                          ON req.id = b.export_request_id
                        WHERE req.project_id = %(project_id)s
                          AND req.id = %(export_request_id)s
                          AND b.id = %(bundle_id)s
                        ORDER BY ev.created_at ASC, ev.id ASC
                        """,
                        {
                            "project_id": project_id,
                            "export_request_id": export_request_id,
                            "bundle_id": bundle_id,
                        },
                    )
                    rows = cursor.fetchall()
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Deposit bundle events listing failed.") from error
        return tuple(self._as_bundle_event_record(row) for row in rows)

    def get_bundle_verification_projection(
        self,
        *,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
    ) -> BundleVerificationProjectionRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          p.bundle_id,
                          p.status,
                          p.last_verification_run_id,
                          p.verified_at,
                          p.updated_at
                        FROM bundle_verification_projections AS p
                        INNER JOIN deposit_bundles AS b
                          ON b.id = p.bundle_id
                        INNER JOIN export_requests AS req
                          ON req.id = b.export_request_id
                        WHERE req.project_id = %(project_id)s
                          AND req.id = %(export_request_id)s
                          AND b.id = %(bundle_id)s
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "export_request_id": export_request_id,
                            "bundle_id": bundle_id,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError(
                "Bundle verification projection lookup failed."
            ) from error
        if row is None:
            return None
        return self._as_bundle_verification_projection_record(row)

    def _select_bundle_verification_run(
        self,
        *,
        cursor: psycopg.Cursor,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        verification_run_id: str,
        for_update: bool = False,
    ) -> dict[str, object] | None:
        query = """
            SELECT
              vr.id,
              vr.project_id,
              vr.bundle_id,
              vr.attempt_number,
              vr.supersedes_verification_run_id,
              vr.superseded_by_verification_run_id,
              vr.status,
              vr.result_json,
              vr.created_by,
              vr.created_at,
              vr.started_at,
              vr.finished_at,
              vr.canceled_by,
              vr.canceled_at,
              vr.failure_reason
            FROM bundle_verification_runs AS vr
            INNER JOIN deposit_bundles AS b
              ON b.id = vr.bundle_id
            INNER JOIN export_requests AS req
              ON req.id = b.export_request_id
            WHERE req.project_id = %(project_id)s
              AND req.id = %(export_request_id)s
              AND b.id = %(bundle_id)s
              AND vr.id = %(verification_run_id)s
            LIMIT 1
        """
        if for_update:
            query = f"{query}\nFOR UPDATE"
        cursor.execute(
            query,
            {
                "project_id": project_id,
                "export_request_id": export_request_id,
                "bundle_id": bundle_id,
                "verification_run_id": verification_run_id,
            },
        )
        return cursor.fetchone()

    def list_bundle_verification_runs(
        self,
        *,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
    ) -> tuple[BundleVerificationRunRecord, ...]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          vr.id,
                          vr.project_id,
                          vr.bundle_id,
                          vr.attempt_number,
                          vr.supersedes_verification_run_id,
                          vr.superseded_by_verification_run_id,
                          vr.status,
                          vr.result_json,
                          vr.created_by,
                          vr.created_at,
                          vr.started_at,
                          vr.finished_at,
                          vr.canceled_by,
                          vr.canceled_at,
                          vr.failure_reason
                        FROM bundle_verification_runs AS vr
                        INNER JOIN deposit_bundles AS b
                          ON b.id = vr.bundle_id
                        INNER JOIN export_requests AS req
                          ON req.id = b.export_request_id
                        WHERE req.project_id = %(project_id)s
                          AND req.id = %(export_request_id)s
                          AND b.id = %(bundle_id)s
                        ORDER BY vr.attempt_number DESC, vr.created_at DESC, vr.id DESC
                        """,
                        {
                            "project_id": project_id,
                            "export_request_id": export_request_id,
                            "bundle_id": bundle_id,
                        },
                    )
                    rows = cursor.fetchall()
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError(
                "Bundle verification run listing failed."
            ) from error
        return tuple(self._as_bundle_verification_run_record(row) for row in rows)

    def get_bundle_verification_run(
        self,
        *,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        verification_run_id: str,
    ) -> BundleVerificationRunRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    row = self._select_bundle_verification_run(
                        cursor=cursor,
                        project_id=project_id,
                        export_request_id=export_request_id,
                        bundle_id=bundle_id,
                        verification_run_id=verification_run_id,
                    )
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError(
                "Bundle verification run lookup failed."
            ) from error
        if row is None:
            raise ExportStoreNotFoundError("Bundle verification run not found.")
        return self._as_bundle_verification_run_record(row)

    def get_current_bundle_verification_run(
        self,
        *,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
    ) -> BundleVerificationRunRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          vr.id,
                          vr.project_id,
                          vr.bundle_id,
                          vr.attempt_number,
                          vr.supersedes_verification_run_id,
                          vr.superseded_by_verification_run_id,
                          vr.status,
                          vr.result_json,
                          vr.created_by,
                          vr.created_at,
                          vr.started_at,
                          vr.finished_at,
                          vr.canceled_by,
                          vr.canceled_at,
                          vr.failure_reason
                        FROM bundle_verification_runs AS vr
                        INNER JOIN deposit_bundles AS b
                          ON b.id = vr.bundle_id
                        INNER JOIN export_requests AS req
                          ON req.id = b.export_request_id
                        WHERE req.project_id = %(project_id)s
                          AND req.id = %(export_request_id)s
                          AND b.id = %(bundle_id)s
                          AND vr.superseded_by_verification_run_id IS NULL
                        ORDER BY vr.attempt_number DESC, vr.created_at DESC, vr.id DESC
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "export_request_id": export_request_id,
                            "bundle_id": bundle_id,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError(
                "Current bundle verification run lookup failed."
            ) from error
        if row is None:
            return None
        return self._as_bundle_verification_run_record(row)

    def create_bundle_verification_run(
        self,
        *,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        actor_user_id: str,
    ) -> BundleVerificationRunRecord:
        self.ensure_schema()
        now = datetime.now(UTC)
        created_row: dict[str, object] | None = None
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          b.id,
                          b.project_id,
                          b.export_request_id,
                          b.candidate_snapshot_id,
                          b.provenance_proof_id,
                          b.provenance_proof_artifact_sha256,
                          b.bundle_kind,
                          b.status,
                          b.attempt_number,
                          b.supersedes_bundle_id,
                          b.superseded_by_bundle_id,
                          b.bundle_key,
                          b.bundle_sha256,
                          b.failure_reason,
                          b.created_by,
                          b.created_at,
                          b.started_at,
                          b.finished_at,
                          b.canceled_by,
                          b.canceled_at
                        FROM deposit_bundles AS b
                        INNER JOIN export_requests AS req
                          ON req.id = b.export_request_id
                        WHERE req.project_id = %(project_id)s
                          AND req.id = %(export_request_id)s
                          AND b.id = %(bundle_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "export_request_id": export_request_id,
                            "bundle_id": bundle_id,
                        },
                    )
                    bundle_row = cursor.fetchone()
                    if bundle_row is None:
                        raise ExportStoreNotFoundError("Deposit bundle not found.")
                    bundle = self._as_deposit_bundle_record(bundle_row)
                    if bundle.status != "SUCCEEDED":
                        raise ExportStoreConflictError(
                            "Bundle verification requires a SUCCEEDED bundle attempt."
                        )
                    if bundle.bundle_key is None or bundle.bundle_sha256 is None:
                        raise ExportStoreConflictError(
                            "Bundle verification requires an immutable succeeded bundle artifact."
                        )

                    cursor.execute(
                        """
                        SELECT
                          id,
                          attempt_number
                        FROM bundle_verification_runs
                        WHERE bundle_id = %(bundle_id)s
                          AND superseded_by_verification_run_id IS NULL
                        ORDER BY attempt_number DESC, created_at DESC, id DESC
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {"bundle_id": bundle.id},
                    )
                    current_run_row = cursor.fetchone()
                    supersedes_verification_run_id = (
                        str(current_run_row["id"])
                        if isinstance(current_run_row.get("id"), str)
                        else None
                    )

                    cursor.execute(
                        """
                        SELECT COALESCE(MAX(attempt_number), 0)::INT AS last_attempt
                        FROM bundle_verification_runs
                        WHERE bundle_id = %(bundle_id)s
                        """,
                        {"bundle_id": bundle.id},
                    )
                    last_attempt_row = cursor.fetchone() or {}
                    attempt_number = int(last_attempt_row.get("last_attempt") or 0) + 1

                    run_id = str(uuid4())
                    queued_at = now
                    started_at = now + timedelta(microseconds=1)
                    finished_at = now + timedelta(microseconds=2)

                    cursor.execute(
                        """
                        INSERT INTO bundle_verification_runs (
                          id,
                          project_id,
                          bundle_id,
                          attempt_number,
                          supersedes_verification_run_id,
                          superseded_by_verification_run_id,
                          status,
                          result_json,
                          created_by,
                          created_at,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          failure_reason
                        )
                        VALUES (
                          %(id)s,
                          %(project_id)s,
                          %(bundle_id)s,
                          %(attempt_number)s,
                          %(supersedes_verification_run_id)s,
                          NULL,
                          'QUEUED',
                          '{}'::jsonb,
                          %(created_by)s,
                          %(created_at)s,
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
                            "bundle_id": bundle.id,
                            "attempt_number": attempt_number,
                            "supersedes_verification_run_id": supersedes_verification_run_id,
                            "created_by": actor_user_id,
                            "created_at": queued_at,
                        },
                    )

                    if supersedes_verification_run_id is not None:
                        cursor.execute(
                            """
                            UPDATE bundle_verification_runs
                            SET superseded_by_verification_run_id = %(run_id)s
                            WHERE id = %(superseded_run_id)s
                              AND superseded_by_verification_run_id IS NULL
                            """,
                            {
                                "run_id": run_id,
                                "superseded_run_id": supersedes_verification_run_id,
                            },
                        )

                    cursor.execute(
                        """
                        UPDATE bundle_verification_runs
                        SET
                          status = 'RUNNING',
                          started_at = %(started_at)s,
                          canceled_by = NULL,
                          canceled_at = NULL,
                          failure_reason = NULL
                        WHERE id = %(verification_run_id)s
                        """,
                        {
                            "verification_run_id": run_id,
                            "started_at": started_at,
                        },
                    )
                    self._append_bundle_event(
                        cursor=cursor,
                        bundle_id=bundle.id,
                        event_type="BUNDLE_VERIFICATION_STARTED",
                        actor_user_id=actor_user_id,
                        created_at=started_at,
                        verification_run_id=run_id,
                    )

                    try:
                        verification_output = verify_bundle_archive_bytes(
                            self._read_storage_object_bytes(object_key=bundle.bundle_key),
                            expected_bundle_sha256=bundle.bundle_sha256,
                        )
                        verification_result = verification_output.result
                        verification_payload = verification_output.payload
                    except Exception as error:
                        verification_result = "INVALID"
                        verification_payload = {
                            "verificationResult": "INVALID",
                            "bundleSha256": bundle.bundle_sha256,
                            "checkedAt": datetime.now(UTC).isoformat(),
                            "failures": [str(error).strip() or "Bundle verification execution failed."],
                        }
                    verification_failures = tuple(
                        item
                        for item in verification_payload.get("failures", [])
                        if isinstance(item, str) and item.strip()
                    )
                    if verification_result == "INVALID":
                        verification_payload = {
                            **verification_payload,
                            "failureClass": classify_verification_failure(
                                failures=verification_failures
                            ),
                        }
                    else:
                        verification_payload = {
                            **verification_payload,
                            "failureClass": None,
                        }
                    failure_reason = (
                        "; ".join(
                            str(item) for item in verification_failures
                        )[:5000]
                        if verification_result == "INVALID"
                        else None
                    )

                    if verification_result == "VALID":
                        cursor.execute(
                            """
                            UPDATE bundle_verification_runs
                            SET
                              status = 'SUCCEEDED',
                              result_json = %(result_json)s,
                              finished_at = %(finished_at)s,
                              failure_reason = NULL
                            WHERE id = %(verification_run_id)s
                            """,
                            {
                                "verification_run_id": run_id,
                                "result_json": verification_payload,
                                "finished_at": finished_at,
                            },
                        )
                        cursor.execute(
                            """
                            INSERT INTO bundle_verification_projections (
                              bundle_id,
                              status,
                              last_verification_run_id,
                              verified_at,
                              updated_at
                            )
                            VALUES (
                              %(bundle_id)s,
                              'VERIFIED',
                              %(verification_run_id)s,
                              %(verified_at)s,
                              %(updated_at)s
                            )
                            ON CONFLICT (bundle_id) DO UPDATE
                            SET
                              status = EXCLUDED.status,
                              last_verification_run_id = EXCLUDED.last_verification_run_id,
                              verified_at = EXCLUDED.verified_at,
                              updated_at = EXCLUDED.updated_at
                            """,
                            {
                                "bundle_id": bundle.id,
                                "verification_run_id": run_id,
                                "verified_at": finished_at,
                                "updated_at": finished_at,
                            },
                        )
                        self._append_bundle_event(
                            cursor=cursor,
                            bundle_id=bundle.id,
                            event_type="BUNDLE_VERIFICATION_SUCCEEDED",
                            actor_user_id=actor_user_id,
                            created_at=finished_at,
                            verification_run_id=run_id,
                            reason=f"bundle_sha256:{bundle.bundle_sha256}",
                        )
                    else:
                        cursor.execute(
                            """
                            UPDATE bundle_verification_runs
                            SET
                              status = 'FAILED',
                              result_json = %(result_json)s,
                              finished_at = %(finished_at)s,
                              failure_reason = %(failure_reason)s
                            WHERE id = %(verification_run_id)s
                            """,
                            {
                                "verification_run_id": run_id,
                                "result_json": verification_payload,
                                "finished_at": finished_at,
                                "failure_reason": failure_reason or "Bundle verification failed.",
                            },
                        )
                        cursor.execute(
                            """
                            INSERT INTO bundle_verification_projections (
                              bundle_id,
                              status,
                              last_verification_run_id,
                              verified_at,
                              updated_at
                            )
                            VALUES (
                              %(bundle_id)s,
                              'FAILED',
                              %(verification_run_id)s,
                              NULL,
                              %(updated_at)s
                            )
                            ON CONFLICT (bundle_id) DO UPDATE
                            SET
                              status = CASE
                                WHEN bundle_verification_projections.status = 'VERIFIED'
                                  THEN bundle_verification_projections.status
                                ELSE EXCLUDED.status
                              END,
                              last_verification_run_id = CASE
                                WHEN bundle_verification_projections.status = 'VERIFIED'
                                  THEN bundle_verification_projections.last_verification_run_id
                                ELSE EXCLUDED.last_verification_run_id
                              END,
                              verified_at = CASE
                                WHEN bundle_verification_projections.status = 'VERIFIED'
                                  THEN bundle_verification_projections.verified_at
                                ELSE EXCLUDED.verified_at
                              END,
                              updated_at = EXCLUDED.updated_at
                            """,
                            {
                                "bundle_id": bundle.id,
                                "verification_run_id": run_id,
                                "updated_at": finished_at,
                            },
                        )
                        self._append_bundle_event(
                            cursor=cursor,
                            bundle_id=bundle.id,
                            event_type="BUNDLE_VERIFICATION_FAILED",
                            actor_user_id=actor_user_id,
                            created_at=finished_at,
                            verification_run_id=run_id,
                            reason=failure_reason or "Bundle verification failed.",
                        )

                    created_row = self._select_bundle_verification_run(
                        cursor=cursor,
                        project_id=project_id,
                        export_request_id=export_request_id,
                        bundle_id=bundle_id,
                        verification_run_id=run_id,
                    )
                connection.commit()
        except ExportStoreConflictError:
            raise
        except ExportStoreNotFoundError:
            raise
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Bundle verification run creation failed.") from error

        if created_row is None:
            raise ExportStoreUnavailableError(
                "Bundle verification run row could not be read after creation."
            )
        return self._as_bundle_verification_run_record(created_row)

    def cancel_bundle_verification_run(
        self,
        *,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        verification_run_id: str,
        actor_user_id: str,
        reason: str | None = None,
    ) -> BundleVerificationRunRecord:
        self.ensure_schema()
        canceled_row: dict[str, object] | None = None
        now = datetime.now(UTC)
        cancel_reason = reason.strip() if isinstance(reason, str) else ""
        if not cancel_reason:
            cancel_reason = "Bundle verification run canceled."
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    row = self._select_bundle_verification_run(
                        cursor=cursor,
                        project_id=project_id,
                        export_request_id=export_request_id,
                        bundle_id=bundle_id,
                        verification_run_id=verification_run_id,
                        for_update=True,
                    )
                    if row is None:
                        raise ExportStoreNotFoundError("Bundle verification run not found.")
                    run = self._as_bundle_verification_run_record(row)
                    if run.status not in {"QUEUED", "RUNNING"}:
                        raise ExportStoreConflictError(
                            "Bundle verification cancel is allowed only for QUEUED or RUNNING runs."
                        )
                    cursor.execute(
                        """
                        UPDATE bundle_verification_runs
                        SET
                          status = 'CANCELED',
                          canceled_by = %(canceled_by)s,
                          canceled_at = %(canceled_at)s,
                          finished_at = %(finished_at)s,
                          failure_reason = %(failure_reason)s
                        WHERE id = %(verification_run_id)s
                        """,
                        {
                            "verification_run_id": verification_run_id,
                            "canceled_by": actor_user_id,
                            "canceled_at": now,
                            "finished_at": now,
                            "failure_reason": cancel_reason,
                        },
                    )
                    self._append_bundle_event(
                        cursor=cursor,
                        bundle_id=bundle_id,
                        event_type="BUNDLE_VERIFICATION_CANCELED",
                        actor_user_id=actor_user_id,
                        created_at=now,
                        verification_run_id=verification_run_id,
                        reason=cancel_reason,
                    )
                    canceled_row = self._select_bundle_verification_run(
                        cursor=cursor,
                        project_id=project_id,
                        export_request_id=export_request_id,
                        bundle_id=bundle_id,
                        verification_run_id=verification_run_id,
                    )
                connection.commit()
        except ExportStoreConflictError:
            raise
        except ExportStoreNotFoundError:
            raise
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Bundle verification cancel failed.") from error
        if canceled_row is None:
            raise ExportStoreUnavailableError(
                "Bundle verification cancel row could not be read."
            )
        return self._as_bundle_verification_run_record(canceled_row)

    def list_bundle_profiles(self) -> tuple[BundleProfileRecord, ...]:
        return list_bundle_profiles()

    def get_bundle_validation_projection(
        self,
        *,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        profile_id: str,
    ) -> BundleValidationProjectionRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          vp.bundle_id,
                          vp.profile_id,
                          vp.status,
                          vp.last_validation_run_id,
                          vp.ready_at,
                          vp.updated_at
                        FROM bundle_validation_projections AS vp
                        INNER JOIN deposit_bundles AS b
                          ON b.id = vp.bundle_id
                        INNER JOIN export_requests AS req
                          ON req.id = b.export_request_id
                        WHERE req.project_id = %(project_id)s
                          AND req.id = %(export_request_id)s
                          AND b.id = %(bundle_id)s
                          AND vp.profile_id = %(profile_id)s
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "export_request_id": export_request_id,
                            "bundle_id": bundle_id,
                            "profile_id": profile_id,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError(
                "Bundle validation projection lookup failed."
            ) from error
        if row is None:
            return None
        return self._as_bundle_validation_projection_record(row)

    def _select_bundle_validation_run(
        self,
        *,
        cursor: psycopg.Cursor,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        profile_id: str,
        validation_run_id: str,
        for_update: bool = False,
    ) -> dict[str, object] | None:
        query = """
            SELECT
              vr.id,
              vr.project_id,
              vr.bundle_id,
              vr.profile_id,
              vr.profile_snapshot_key,
              vr.profile_snapshot_sha256,
              vr.status,
              vr.attempt_number,
              vr.supersedes_validation_run_id,
              vr.superseded_by_validation_run_id,
              vr.result_json,
              vr.failure_reason,
              vr.created_by,
              vr.created_at,
              vr.started_at,
              vr.finished_at,
              vr.canceled_by,
              vr.canceled_at
            FROM bundle_validation_runs AS vr
            INNER JOIN deposit_bundles AS b
              ON b.id = vr.bundle_id
            INNER JOIN export_requests AS req
              ON req.id = b.export_request_id
            WHERE req.project_id = %(project_id)s
              AND req.id = %(export_request_id)s
              AND b.id = %(bundle_id)s
              AND vr.profile_id = %(profile_id)s
              AND vr.id = %(validation_run_id)s
            LIMIT 1
        """
        if for_update:
            query = f"{query}\nFOR UPDATE"
        cursor.execute(
            query,
            {
                "project_id": project_id,
                "export_request_id": export_request_id,
                "bundle_id": bundle_id,
                "profile_id": profile_id,
                "validation_run_id": validation_run_id,
            },
        )
        return cursor.fetchone()

    def list_bundle_validation_runs(
        self,
        *,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        profile_id: str,
    ) -> tuple[BundleValidationRunRecord, ...]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          vr.id,
                          vr.project_id,
                          vr.bundle_id,
                          vr.profile_id,
                          vr.profile_snapshot_key,
                          vr.profile_snapshot_sha256,
                          vr.status,
                          vr.attempt_number,
                          vr.supersedes_validation_run_id,
                          vr.superseded_by_validation_run_id,
                          vr.result_json,
                          vr.failure_reason,
                          vr.created_by,
                          vr.created_at,
                          vr.started_at,
                          vr.finished_at,
                          vr.canceled_by,
                          vr.canceled_at
                        FROM bundle_validation_runs AS vr
                        INNER JOIN deposit_bundles AS b
                          ON b.id = vr.bundle_id
                        INNER JOIN export_requests AS req
                          ON req.id = b.export_request_id
                        WHERE req.project_id = %(project_id)s
                          AND req.id = %(export_request_id)s
                          AND b.id = %(bundle_id)s
                          AND vr.profile_id = %(profile_id)s
                        ORDER BY vr.attempt_number DESC, vr.created_at DESC, vr.id DESC
                        """,
                        {
                            "project_id": project_id,
                            "export_request_id": export_request_id,
                            "bundle_id": bundle_id,
                            "profile_id": profile_id,
                        },
                    )
                    rows = cursor.fetchall()
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Bundle validation run listing failed.") from error
        return tuple(self._as_bundle_validation_run_record(row) for row in rows)

    def get_bundle_validation_run(
        self,
        *,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        profile_id: str,
        validation_run_id: str,
    ) -> BundleValidationRunRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    row = self._select_bundle_validation_run(
                        cursor=cursor,
                        project_id=project_id,
                        export_request_id=export_request_id,
                        bundle_id=bundle_id,
                        profile_id=profile_id,
                        validation_run_id=validation_run_id,
                    )
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Bundle validation run lookup failed.") from error
        if row is None:
            raise ExportStoreNotFoundError("Bundle validation run not found.")
        return self._as_bundle_validation_run_record(row)

    def get_current_bundle_validation_run(
        self,
        *,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        profile_id: str,
    ) -> BundleValidationRunRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          vr.id,
                          vr.project_id,
                          vr.bundle_id,
                          vr.profile_id,
                          vr.profile_snapshot_key,
                          vr.profile_snapshot_sha256,
                          vr.status,
                          vr.attempt_number,
                          vr.supersedes_validation_run_id,
                          vr.superseded_by_validation_run_id,
                          vr.result_json,
                          vr.failure_reason,
                          vr.created_by,
                          vr.created_at,
                          vr.started_at,
                          vr.finished_at,
                          vr.canceled_by,
                          vr.canceled_at
                        FROM bundle_validation_runs AS vr
                        INNER JOIN deposit_bundles AS b
                          ON b.id = vr.bundle_id
                        INNER JOIN export_requests AS req
                          ON req.id = b.export_request_id
                        WHERE req.project_id = %(project_id)s
                          AND req.id = %(export_request_id)s
                          AND b.id = %(bundle_id)s
                          AND vr.profile_id = %(profile_id)s
                          AND vr.superseded_by_validation_run_id IS NULL
                        ORDER BY vr.attempt_number DESC, vr.created_at DESC, vr.id DESC
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "export_request_id": export_request_id,
                            "bundle_id": bundle_id,
                            "profile_id": profile_id,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError(
                "Current bundle validation run lookup failed."
            ) from error
        if row is None:
            return None
        return self._as_bundle_validation_run_record(row)

    def create_bundle_validation_run(
        self,
        *,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        profile_id: str,
        actor_user_id: str,
    ) -> BundleValidationRunRecord:
        self.ensure_schema()
        now = datetime.now(UTC)
        created_row: dict[str, object] | None = None
        normalized_profile_id = profile_id.strip().upper()
        try:
            profile = get_bundle_profile(profile_id=normalized_profile_id)
        except ValueError as error:
            raise ExportStoreConflictError(str(error)) from error
        profile_snapshot_payload = build_bundle_profile_snapshot(profile=profile)
        profile_snapshot_bytes = bundle_profile_snapshot_bytes(profile=profile)
        profile_snapshot_sha256 = bundle_profile_snapshot_sha256(profile=profile)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          b.id,
                          b.project_id,
                          b.export_request_id,
                          b.candidate_snapshot_id,
                          b.provenance_proof_id,
                          b.provenance_proof_artifact_sha256,
                          b.bundle_kind,
                          b.status,
                          b.attempt_number,
                          b.supersedes_bundle_id,
                          b.superseded_by_bundle_id,
                          b.bundle_key,
                          b.bundle_sha256,
                          b.failure_reason,
                          b.created_by,
                          b.created_at,
                          b.started_at,
                          b.finished_at,
                          b.canceled_by,
                          b.canceled_at
                        FROM deposit_bundles AS b
                        INNER JOIN export_requests AS req
                          ON req.id = b.export_request_id
                        WHERE req.project_id = %(project_id)s
                          AND req.id = %(export_request_id)s
                          AND b.id = %(bundle_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "export_request_id": export_request_id,
                            "bundle_id": bundle_id,
                        },
                    )
                    bundle_row = cursor.fetchone()
                    if bundle_row is None:
                        raise ExportStoreNotFoundError("Deposit bundle not found.")
                    bundle = self._as_deposit_bundle_record(bundle_row)
                    if bundle.status != "SUCCEEDED":
                        raise ExportStoreConflictError(
                            "Bundle validation requires a SUCCEEDED bundle attempt."
                        )
                    if bundle.bundle_key is None or bundle.bundle_sha256 is None:
                        raise ExportStoreConflictError(
                            "Bundle validation requires an immutable succeeded bundle artifact."
                        )

                    profile_snapshot_key = self._build_bundle_profile_snapshot_key(
                        project_id=project_id,
                        export_request_id=export_request_id,
                        bundle_id=bundle.id,
                        profile_id=profile.id,
                        profile_snapshot_sha256=profile_snapshot_sha256,
                    )
                    self._write_storage_object_idempotent(
                        object_key=profile_snapshot_key,
                        payload=profile_snapshot_bytes,
                    )

                    cursor.execute(
                        """
                        SELECT
                          id,
                          attempt_number
                        FROM bundle_validation_runs
                        WHERE bundle_id = %(bundle_id)s
                          AND profile_id = %(profile_id)s
                          AND superseded_by_validation_run_id IS NULL
                        ORDER BY attempt_number DESC, created_at DESC, id DESC
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "bundle_id": bundle.id,
                            "profile_id": profile.id,
                        },
                    )
                    current_run_row = cursor.fetchone()
                    supersedes_validation_run_id = (
                        str(current_run_row["id"])
                        if isinstance(current_run_row.get("id"), str)
                        else None
                    )

                    cursor.execute(
                        """
                        SELECT COALESCE(MAX(attempt_number), 0)::INT AS last_attempt
                        FROM bundle_validation_runs
                        WHERE bundle_id = %(bundle_id)s
                          AND profile_id = %(profile_id)s
                        """,
                        {
                            "bundle_id": bundle.id,
                            "profile_id": profile.id,
                        },
                    )
                    last_attempt_row = cursor.fetchone() or {}
                    attempt_number = int(last_attempt_row.get("last_attempt") or 0) + 1

                    cursor.execute(
                        """
                        SELECT
                          status,
                          last_verification_run_id,
                          verified_at,
                          updated_at
                        FROM bundle_verification_projections
                        WHERE bundle_id = %(bundle_id)s
                        LIMIT 1
                        """,
                        {"bundle_id": bundle.id},
                    )
                    verification_projection_row = cursor.fetchone()
                    verification_projection_status = (
                        str(verification_projection_row["status"])
                        if verification_projection_row is not None
                        and isinstance(verification_projection_row.get("status"), str)
                        else None
                    )

                    run_id = str(uuid4())
                    queued_at = now
                    started_at = now + timedelta(microseconds=1)
                    finished_at = now + timedelta(microseconds=2)
                    cursor.execute(
                        """
                        INSERT INTO bundle_validation_runs (
                          id,
                          project_id,
                          bundle_id,
                          profile_id,
                          profile_snapshot_key,
                          profile_snapshot_sha256,
                          status,
                          attempt_number,
                          supersedes_validation_run_id,
                          superseded_by_validation_run_id,
                          result_json,
                          failure_reason,
                          created_by,
                          created_at,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at
                        )
                        VALUES (
                          %(id)s,
                          %(project_id)s,
                          %(bundle_id)s,
                          %(profile_id)s,
                          %(profile_snapshot_key)s,
                          %(profile_snapshot_sha256)s,
                          'QUEUED',
                          %(attempt_number)s,
                          %(supersedes_validation_run_id)s,
                          NULL,
                          '{}'::jsonb,
                          NULL,
                          %(created_by)s,
                          %(created_at)s,
                          NULL,
                          NULL,
                          NULL,
                          NULL
                        )
                        """,
                        {
                            "id": run_id,
                            "project_id": project_id,
                            "bundle_id": bundle.id,
                            "profile_id": profile.id,
                            "profile_snapshot_key": profile_snapshot_key,
                            "profile_snapshot_sha256": profile_snapshot_sha256,
                            "attempt_number": attempt_number,
                            "supersedes_validation_run_id": supersedes_validation_run_id,
                            "created_by": actor_user_id,
                            "created_at": queued_at,
                        },
                    )
                    if supersedes_validation_run_id is not None:
                        cursor.execute(
                            """
                            UPDATE bundle_validation_runs
                            SET superseded_by_validation_run_id = %(run_id)s
                            WHERE id = %(superseded_run_id)s
                              AND superseded_by_validation_run_id IS NULL
                            """,
                            {
                                "run_id": run_id,
                                "superseded_run_id": supersedes_validation_run_id,
                            },
                        )
                    cursor.execute(
                        """
                        UPDATE bundle_validation_runs
                        SET
                          status = 'RUNNING',
                          started_at = %(started_at)s,
                          canceled_by = NULL,
                          canceled_at = NULL,
                          failure_reason = NULL
                        WHERE id = %(validation_run_id)s
                        """,
                        {
                            "validation_run_id": run_id,
                            "started_at": started_at,
                        },
                    )
                    self._append_bundle_event(
                        cursor=cursor,
                        bundle_id=bundle.id,
                        event_type="BUNDLE_VALIDATION_STARTED",
                        actor_user_id=actor_user_id,
                        created_at=started_at,
                        validation_run_id=run_id,
                        reason=f"profile:{profile.id}",
                    )
                    try:
                        artifact = self.read_deposit_bundle_artifact(bundle=bundle)
                        validation_output = validate_bundle_artifact_against_profile(
                            bundle_id=bundle.id,
                            bundle_kind=bundle.bundle_kind,
                            bundle_sha256=bundle.bundle_sha256,
                            bundle_artifact=artifact,
                            expected_proof_artifact_sha256=bundle.provenance_proof_artifact_sha256,
                            verification_projection_status=verification_projection_status,
                            profile=profile,
                            checked_at=finished_at,
                        )
                    except Exception as error:
                        validation_output = BundleProfileValidationOutput(
                            result="INVALID",
                            payload={
                                "validationResult": "INVALID",
                                "profileId": profile.id,
                                "checkedAt": datetime.now(UTC).isoformat(),
                                "failures": [
                                    str(error).strip()
                                    or "Bundle validation execution failed."
                                ],
                                "failureClass": "ENVIRONMENTAL_RUNTIME",
                            },
                        )
                    result_json = dict(validation_output.payload)
                    result_json["profileSnapshotKey"] = profile_snapshot_key
                    result_json["profileSnapshotSha256"] = profile_snapshot_sha256
                    result_json["profileSnapshot"] = profile_snapshot_payload
                    result_json["profileId"] = profile.id
                    result_json["attemptNumber"] = attempt_number
                    failure_reason = (
                        "; ".join(
                            str(item)
                            for item in result_json.get("failures", [])
                            if isinstance(item, str) and item.strip()
                        )[:5000]
                        if validation_output.result == "INVALID"
                        else None
                    )
                    if validation_output.result == "VALID":
                        cursor.execute(
                            """
                            UPDATE bundle_validation_runs
                            SET
                              status = 'SUCCEEDED',
                              result_json = %(result_json)s,
                              finished_at = %(finished_at)s,
                              failure_reason = NULL
                            WHERE id = %(validation_run_id)s
                            """,
                            {
                                "validation_run_id": run_id,
                                "result_json": result_json,
                                "finished_at": finished_at,
                            },
                        )
                        cursor.execute(
                            """
                            INSERT INTO bundle_validation_projections (
                              bundle_id,
                              profile_id,
                              status,
                              last_validation_run_id,
                              ready_at,
                              updated_at
                            )
                            VALUES (
                              %(bundle_id)s,
                              %(profile_id)s,
                              'READY',
                              %(validation_run_id)s,
                              %(ready_at)s,
                              %(updated_at)s
                            )
                            ON CONFLICT (bundle_id, profile_id) DO UPDATE
                            SET
                              status = EXCLUDED.status,
                              last_validation_run_id = EXCLUDED.last_validation_run_id,
                              ready_at = EXCLUDED.ready_at,
                              updated_at = EXCLUDED.updated_at
                            """,
                            {
                                "bundle_id": bundle.id,
                                "profile_id": profile.id,
                                "validation_run_id": run_id,
                                "ready_at": finished_at,
                                "updated_at": finished_at,
                            },
                        )
                        self._append_bundle_event(
                            cursor=cursor,
                            bundle_id=bundle.id,
                            event_type="BUNDLE_VALIDATION_SUCCEEDED",
                            actor_user_id=actor_user_id,
                            created_at=finished_at,
                            validation_run_id=run_id,
                            reason=f"profile:{profile.id}",
                        )
                    else:
                        cursor.execute(
                            """
                            UPDATE bundle_validation_runs
                            SET
                              status = 'FAILED',
                              result_json = %(result_json)s,
                              finished_at = %(finished_at)s,
                              failure_reason = %(failure_reason)s
                            WHERE id = %(validation_run_id)s
                            """,
                            {
                                "validation_run_id": run_id,
                                "result_json": result_json,
                                "finished_at": finished_at,
                                "failure_reason": (
                                    failure_reason or "Bundle validation failed."
                                ),
                            },
                        )
                        cursor.execute(
                            """
                            INSERT INTO bundle_validation_projections (
                              bundle_id,
                              profile_id,
                              status,
                              last_validation_run_id,
                              ready_at,
                              updated_at
                            )
                            VALUES (
                              %(bundle_id)s,
                              %(profile_id)s,
                              'FAILED',
                              %(validation_run_id)s,
                              NULL,
                              %(updated_at)s
                            )
                            ON CONFLICT (bundle_id, profile_id) DO UPDATE
                            SET
                              status = CASE
                                WHEN bundle_validation_projections.status = 'READY'
                                  THEN bundle_validation_projections.status
                                ELSE EXCLUDED.status
                              END,
                              last_validation_run_id = CASE
                                WHEN bundle_validation_projections.status = 'READY'
                                  THEN bundle_validation_projections.last_validation_run_id
                                ELSE EXCLUDED.last_validation_run_id
                              END,
                              ready_at = CASE
                                WHEN bundle_validation_projections.status = 'READY'
                                  THEN bundle_validation_projections.ready_at
                                ELSE EXCLUDED.ready_at
                              END,
                              updated_at = EXCLUDED.updated_at
                            """,
                            {
                                "bundle_id": bundle.id,
                                "profile_id": profile.id,
                                "validation_run_id": run_id,
                                "updated_at": finished_at,
                            },
                        )
                        self._append_bundle_event(
                            cursor=cursor,
                            bundle_id=bundle.id,
                            event_type="BUNDLE_VALIDATION_FAILED",
                            actor_user_id=actor_user_id,
                            created_at=finished_at,
                            validation_run_id=run_id,
                            reason=(failure_reason or "Bundle validation failed."),
                        )
                    created_row = self._select_bundle_validation_run(
                        cursor=cursor,
                        project_id=project_id,
                        export_request_id=export_request_id,
                        bundle_id=bundle_id,
                        profile_id=profile.id,
                        validation_run_id=run_id,
                    )
                connection.commit()
        except ExportStoreConflictError:
            raise
        except ExportStoreNotFoundError:
            raise
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Bundle validation run creation failed.") from error
        if created_row is None:
            raise ExportStoreUnavailableError(
                "Bundle validation run row could not be read after creation."
            )
        return self._as_bundle_validation_run_record(created_row)

    def cancel_bundle_validation_run(
        self,
        *,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        profile_id: str,
        validation_run_id: str,
        actor_user_id: str,
        reason: str | None = None,
    ) -> BundleValidationRunRecord:
        self.ensure_schema()
        canceled_row: dict[str, object] | None = None
        now = datetime.now(UTC)
        cancel_reason = reason.strip() if isinstance(reason, str) else ""
        if not cancel_reason:
            cancel_reason = "Bundle validation run canceled."
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    row = self._select_bundle_validation_run(
                        cursor=cursor,
                        project_id=project_id,
                        export_request_id=export_request_id,
                        bundle_id=bundle_id,
                        profile_id=profile_id,
                        validation_run_id=validation_run_id,
                        for_update=True,
                    )
                    if row is None:
                        raise ExportStoreNotFoundError("Bundle validation run not found.")
                    run = self._as_bundle_validation_run_record(row)
                    if run.status not in {"QUEUED", "RUNNING"}:
                        raise ExportStoreConflictError(
                            "Bundle validation cancel is allowed only for QUEUED or RUNNING runs."
                        )
                    cursor.execute(
                        """
                        UPDATE bundle_validation_runs
                        SET
                          status = 'CANCELED',
                          canceled_by = %(canceled_by)s,
                          canceled_at = %(canceled_at)s,
                          finished_at = %(finished_at)s,
                          failure_reason = %(failure_reason)s
                        WHERE id = %(validation_run_id)s
                        """,
                        {
                            "validation_run_id": validation_run_id,
                            "canceled_by": actor_user_id,
                            "canceled_at": now,
                            "finished_at": now,
                            "failure_reason": cancel_reason,
                        },
                    )
                    self._append_bundle_event(
                        cursor=cursor,
                        bundle_id=bundle_id,
                        event_type="BUNDLE_VALIDATION_CANCELED",
                        actor_user_id=actor_user_id,
                        created_at=now,
                        validation_run_id=validation_run_id,
                        reason=cancel_reason,
                    )
                    canceled_row = self._select_bundle_validation_run(
                        cursor=cursor,
                        project_id=project_id,
                        export_request_id=export_request_id,
                        bundle_id=bundle_id,
                        profile_id=profile_id,
                        validation_run_id=validation_run_id,
                    )
                connection.commit()
        except ExportStoreConflictError:
            raise
        except ExportStoreNotFoundError:
            raise
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Bundle validation cancel failed.") from error
        if canceled_row is None:
            raise ExportStoreUnavailableError(
                "Bundle validation cancel row could not be read."
            )
        return self._as_bundle_validation_run_record(canceled_row)

    def run_bundle_replay_drill(
        self,
        *,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        profile_id: str | None,
    ) -> dict[str, object]:
        request = self.get_request(project_id=project_id, export_request_id=export_request_id)
        if request.status not in {"APPROVED", "EXPORTED"}:
            raise ExportStoreConflictError(
                "Replay drill is available only for APPROVED or EXPORTED request lineages."
            )
        bundle = self.get_deposit_bundle(
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
        )
        if bundle.status != "SUCCEEDED":
            raise ExportStoreConflictError(
                "Replay drill requires a SUCCEEDED bundle attempt."
            )
        if bundle.bundle_key is None or bundle.bundle_sha256 is None:
            raise ExportStoreConflictError(
                "Replay drill requires immutable bundle bytes and hash."
            )
        candidate = self.get_candidate(
            project_id=project_id,
            candidate_id=request.candidate_snapshot_id,
        )
        proof = self.get_provenance_proof(
            project_id=project_id,
            export_request_id=export_request_id,
            proof_id=bundle.provenance_proof_id,
        )
        selected_profile: BundleProfileRecord | None = None
        profile_snapshot_key: str | None = None
        profile_snapshot_sha256: str | None = None
        if isinstance(profile_id, str) and profile_id.strip():
            try:
                selected_profile = get_bundle_profile(profile_id=profile_id)
            except ValueError as error:
                raise ExportStoreConflictError(str(error)) from error
            profile_snapshot_sha256 = bundle_profile_snapshot_sha256(profile=selected_profile)
            profile_snapshot_key = self._build_bundle_profile_snapshot_key(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle.id,
                profile_id=selected_profile.id,
                profile_snapshot_sha256=profile_snapshot_sha256,
            )

        replay_payload = run_bundle_replay_drill_payload(
            bundle_id=bundle.id,
            bundle_kind=bundle.bundle_kind,
            bundle_sha256=bundle.bundle_sha256,
            bundle_bytes=self._read_storage_object_bytes(object_key=bundle.bundle_key),
            expected_candidate_snapshot_id=candidate.id,
            expected_provenance_proof_id=proof.id,
            expected_provenance_proof_artifact_sha256=proof.proof_artifact_sha256,
            selected_profile=selected_profile,
        )
        return {
            "projectId": project_id,
            "exportRequestId": export_request_id,
            "bundleId": bundle.id,
            "candidateSnapshotId": candidate.id,
            "provenanceProofId": proof.id,
            "profileId": selected_profile.id if selected_profile is not None else None,
            "profileSnapshotKey": profile_snapshot_key,
            "profileSnapshotSha256": profile_snapshot_sha256,
            **replay_payload,
        }

    def read_deposit_bundle_artifact(
        self,
        *,
        bundle: DepositBundleRecord,
    ) -> dict[str, object]:
        if bundle.bundle_key is None or bundle.bundle_sha256 is None:
            raise ExportStoreConflictError(
                "Deposit bundle bytes are unavailable until build succeeds."
            )
        payload_bytes = self._read_storage_object_bytes(object_key=bundle.bundle_key)
        computed_sha256 = self._sha256_hex(payload_bytes)
        if computed_sha256 != bundle.bundle_sha256:
            raise ExportStoreUnavailableError(
                "Deposit bundle archive hash does not match stored immutable hash."
            )
        try:
            archive = zipfile.ZipFile(io.BytesIO(payload_bytes), mode="r")
        except zipfile.BadZipFile as error:
            raise ExportStoreUnavailableError("Deposit bundle archive is not a valid zip file.") from error
        with archive:
            entry_names = sorted(archive.namelist())

            def _read_json_entry(name: str) -> dict[str, object]:
                if name not in entry_names:
                    return {}
                try:
                    decoded = archive.read(name).decode("utf-8")
                    parsed = json.loads(decoded)
                except (UnicodeDecodeError, json.JSONDecodeError, KeyError) as error:
                    raise ExportStoreUnavailableError(
                        f"Deposit bundle entry {name} is not valid canonical JSON."
                    ) from error
                return dict(parsed) if isinstance(parsed, dict) else {}

            metadata = _read_json_entry("bundle/metadata.json")
            proof_artifact = _read_json_entry("bundle/provenance-proof.json")
            proof_signature = _read_json_entry("bundle/provenance-signature.json")
            proof_verification_material = _read_json_entry(
                "bundle/provenance-verification-material.json"
            )

        return {
            "archiveEntries": entry_names,
            "metadata": metadata,
            "provenanceProofArtifact": proof_artifact,
            "provenanceSignature": proof_signature,
            "provenanceVerificationMaterial": proof_verification_material,
        }

    def cancel_deposit_bundle(
        self,
        *,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        actor_user_id: str,
        reason: str | None = None,
    ) -> DepositBundleRecord:
        self.ensure_schema()
        canceled_row: dict[str, object] | None = None
        now = datetime.now(UTC)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          b.id,
                          b.project_id,
                          b.export_request_id,
                          b.candidate_snapshot_id,
                          b.provenance_proof_id,
                          b.provenance_proof_artifact_sha256,
                          b.bundle_kind,
                          b.status,
                          b.attempt_number,
                          b.supersedes_bundle_id,
                          b.superseded_by_bundle_id,
                          b.bundle_key,
                          b.bundle_sha256,
                          b.failure_reason,
                          b.created_by,
                          b.created_at,
                          b.started_at,
                          b.finished_at,
                          b.canceled_by,
                          b.canceled_at
                        FROM deposit_bundles AS b
                        INNER JOIN export_requests AS req
                          ON req.id = b.export_request_id
                        WHERE req.project_id = %(project_id)s
                          AND req.id = %(export_request_id)s
                          AND b.id = %(bundle_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "export_request_id": export_request_id,
                            "bundle_id": bundle_id,
                        },
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise ExportStoreNotFoundError("Deposit bundle not found.")
                    status_value = str(row["status"])
                    if status_value not in {"QUEUED", "RUNNING"}:
                        raise ExportStoreConflictError(
                            "Only QUEUED or RUNNING deposit bundles can be canceled."
                        )
                    cursor.execute(
                        """
                        UPDATE deposit_bundles
                        SET
                          status = 'CANCELED',
                          failure_reason = %(reason)s,
                          canceled_by = %(canceled_by)s,
                          canceled_at = %(canceled_at)s,
                          finished_at = %(finished_at)s
                        WHERE id = %(bundle_id)s
                        """,
                        {
                            "bundle_id": bundle_id,
                            "reason": reason,
                            "canceled_by": actor_user_id,
                            "canceled_at": now,
                            "finished_at": now,
                        },
                    )
                    self._append_bundle_event(
                        cursor=cursor,
                        bundle_id=bundle_id,
                        event_type="BUNDLE_BUILD_CANCELED",
                        actor_user_id=actor_user_id,
                        created_at=now,
                        reason=reason,
                    )
                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          export_request_id,
                          candidate_snapshot_id,
                          provenance_proof_id,
                          provenance_proof_artifact_sha256,
                          bundle_kind,
                          status,
                          attempt_number,
                          supersedes_bundle_id,
                          superseded_by_bundle_id,
                          bundle_key,
                          bundle_sha256,
                          failure_reason,
                          created_by,
                          created_at,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at
                        FROM deposit_bundles
                        WHERE id = %(bundle_id)s
                        LIMIT 1
                        """,
                        {"bundle_id": bundle_id},
                    )
                    canceled_row = cursor.fetchone()
                connection.commit()
        except ExportStoreConflictError:
            raise
        except ExportStoreNotFoundError:
            raise
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Deposit bundle cancellation failed.") from error
        if canceled_row is None:
            raise ExportStoreUnavailableError("Deposit bundle cancellation row could not be read.")
        return self._as_deposit_bundle_record(canceled_row)

    def ensure_service_account_user(
        self,
        *,
        user_id: str,
        oidc_sub: str,
        email: str,
        display_name: str,
    ) -> None:
        self.ensure_schema()
        now = datetime.now(UTC)
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO users (
                          id,
                          oidc_sub,
                          email,
                          display_name,
                          created_at,
                          last_login_at
                        )
                        VALUES (
                          %(id)s,
                          %(oidc_sub)s,
                          %(email)s,
                          %(display_name)s,
                          %(created_at)s,
                          %(last_login_at)s
                        )
                        ON CONFLICT (id) DO UPDATE
                        SET
                          oidc_sub = EXCLUDED.oidc_sub,
                          email = EXCLUDED.email,
                          display_name = EXCLUDED.display_name,
                          last_login_at = EXCLUDED.last_login_at
                        """,
                        {
                            "id": user_id,
                            "oidc_sub": oidc_sub,
                            "email": email,
                            "display_name": display_name,
                            "created_at": now,
                            "last_login_at": now,
                        },
                    )
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError(
                "Gateway service account could not be ensured."
            ) from error

    @staticmethod
    def _review_stage_order(stage: str) -> int:
        if stage == "PRIMARY":
            return 1
        if stage == "SECONDARY":
            return 2
        return 9

    @staticmethod
    def _is_terminal_request_status(status: str) -> bool:
        return status in {"APPROVED", "EXPORTED", "REJECTED", "RETURNED"}

    @staticmethod
    def _is_terminal_review_status(status: str) -> bool:
        return status in {"APPROVED", "RETURNED", "REJECTED"}

    def _coerce_positive_int_setting(self, *, name: str, default: int) -> int:
        raw = getattr(self._settings, name, default)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return default
        return value if value > 0 else default

    def _sla_hours(self) -> int:
        return self._coerce_positive_int_setting(name="export_request_sla_hours", default=72)

    def _reminder_after_hours(self) -> int:
        return self._coerce_positive_int_setting(
            name="export_request_reminder_after_hours",
            default=24,
        )

    def _reminder_cooldown_hours(self) -> int:
        return self._coerce_positive_int_setting(
            name="export_request_reminder_cooldown_hours",
            default=12,
        )

    def _escalation_after_sla_hours(self) -> int:
        return self._coerce_positive_int_setting(
            name="export_request_escalation_after_sla_hours",
            default=24,
        )

    def _escalation_cooldown_hours(self) -> int:
        return self._coerce_positive_int_setting(
            name="export_request_escalation_cooldown_hours",
            default=24,
        )

    def _stale_open_after_days(self) -> int:
        return self._coerce_positive_int_setting(
            name="export_request_stale_open_after_days",
            default=30,
        )

    def _retention_stale_open_days(self) -> int:
        return self._coerce_positive_int_setting(
            name="export_request_retention_stale_open_days",
            default=60,
        )

    def _retention_terminal_approved_days(self) -> int:
        return self._coerce_positive_int_setting(
            name="export_request_retention_terminal_approved_days",
            default=180,
        )

    def _retention_terminal_other_days(self) -> int:
        return self._coerce_positive_int_setting(
            name="export_request_retention_terminal_other_days",
            default=90,
        )

    def _retention_pending_window_days(self) -> int:
        return self._coerce_positive_int_setting(
            name="export_request_retention_pending_window_days",
            default=14,
        )

    def _terminal_retention_until(
        self,
        *,
        status: str,
        now: datetime,
    ) -> datetime | None:
        if status in {"APPROVED", "EXPORTED"}:
            return now + timedelta(days=self._retention_terminal_approved_days())
        if status in {"RETURNED", "REJECTED"}:
            return now + timedelta(days=self._retention_terminal_other_days())
        return None

    @staticmethod
    def _is_open_request_status(status: str) -> bool:
        return status in {"SUBMITTED", "RESUBMITTED", "IN_REVIEW"}

    def _resolve_active_required_review(
        self,
        *,
        review_rows: list[dict[str, object]],
    ) -> dict[str, object] | None:
        required_rows = [row for row in review_rows if bool(row.get("is_required", False))]
        required_rows.sort(
            key=lambda row: (
                self._review_stage_order(str(row.get("review_stage") or "")),
                str(row.get("id") or ""),
            )
        )
        for row in required_rows:
            status = str(row.get("status") or "")
            if status == "APPROVED":
                continue
            if status in {"RETURNED", "REJECTED"}:
                return None
            return row
        return None

    def _lock_request_and_reviews(
        self,
        *,
        cursor: psycopg.Cursor,
        project_id: str,
        export_request_id: str,
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        cursor.execute(
            """
            SELECT
              id,
              project_id,
              submitted_by,
              status,
              requires_second_review
            FROM export_requests
            WHERE project_id = %(project_id)s
              AND id = %(export_request_id)s
            FOR UPDATE
            """,
            {
                "project_id": project_id,
                "export_request_id": export_request_id,
            },
        )
        request_row = cursor.fetchone()
        if request_row is None:
            raise ExportStoreNotFoundError("Export request not found.")

        cursor.execute(
            """
            SELECT
              id,
              export_request_id,
              review_stage,
              is_required,
              status,
              assigned_reviewer_user_id,
              assigned_at,
              acted_by_user_id,
              acted_at,
              decision_reason,
              return_comment,
              review_etag,
              created_at,
              updated_at
            FROM export_request_reviews
            WHERE export_request_id = %(export_request_id)s
            ORDER BY
              CASE review_stage
                WHEN 'PRIMARY' THEN 1
                WHEN 'SECONDARY' THEN 2
                ELSE 3
              END ASC,
              created_at ASC,
              id ASC
            FOR UPDATE
            """,
            {"export_request_id": export_request_id},
        )
        review_rows = cursor.fetchall()
        if not review_rows:
            raise ExportStoreConflictError("Export request has no review stages.")
        return request_row, list(review_rows)

    def attach_request_receipt(
        self,
        *,
        export_request_id: str,
        actor_user_id: str,
        receipt_key: str,
        receipt_sha256: str,
        exported_at: datetime,
    ) -> tuple[ExportRequestRecord, ExportReceiptRecord]:
        self.ensure_schema()
        now = datetime.now(UTC)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          status,
                          receipt_id
                        FROM export_requests
                        WHERE id = %(export_request_id)s
                        FOR UPDATE
                        """,
                        {"export_request_id": export_request_id},
                    )
                    request_row = cursor.fetchone()
                    if request_row is None:
                        raise ExportStoreNotFoundError("Export request not found.")

                    request_status = str(request_row.get("status") or "")
                    if request_status not in {"APPROVED", "EXPORTED"}:
                        raise ExportStoreConflictError(
                            "Only APPROVED or EXPORTED requests can attach gateway receipts."
                        )
                    project_id = str(request_row["project_id"])
                    supersedes_receipt_id = (
                        str(request_row["receipt_id"])
                        if isinstance(request_row.get("receipt_id"), str)
                        else None
                    )

                    cursor.execute(
                        """
                        SELECT COALESCE(MAX(attempt_number), 0)::INT AS last_attempt
                        FROM export_receipts
                        WHERE export_request_id = %(export_request_id)s
                        """,
                        {"export_request_id": export_request_id},
                    )
                    attempt_row = cursor.fetchone() or {}
                    attempt_number = int(attempt_row.get("last_attempt") or 0) + 1
                    receipt_id = str(uuid4())

                    cursor.execute(
                        """
                        INSERT INTO export_receipts (
                          id,
                          export_request_id,
                          attempt_number,
                          supersedes_receipt_id,
                          superseded_by_receipt_id,
                          receipt_key,
                          receipt_sha256,
                          created_by,
                          created_at,
                          exported_at
                        )
                        VALUES (
                          %(id)s,
                          %(export_request_id)s,
                          %(attempt_number)s,
                          %(supersedes_receipt_id)s,
                          NULL,
                          %(receipt_key)s,
                          %(receipt_sha256)s,
                          %(created_by)s,
                          %(created_at)s,
                          %(exported_at)s
                        )
                        """,
                        {
                            "id": receipt_id,
                            "export_request_id": export_request_id,
                            "attempt_number": attempt_number,
                            "supersedes_receipt_id": supersedes_receipt_id,
                            "receipt_key": receipt_key,
                            "receipt_sha256": receipt_sha256,
                            "created_by": actor_user_id,
                            "created_at": now,
                            "exported_at": exported_at,
                        },
                    )
                    if cursor.rowcount != 1:
                        raise ExportStoreConflictError("Gateway receipt append failed.")

                    if supersedes_receipt_id is not None:
                        cursor.execute(
                            """
                            UPDATE export_receipts
                            SET superseded_by_receipt_id = %(superseded_by_receipt_id)s
                            WHERE id = %(supersedes_receipt_id)s
                              AND superseded_by_receipt_id IS NULL
                            """,
                            {
                                "superseded_by_receipt_id": receipt_id,
                                "supersedes_receipt_id": supersedes_receipt_id,
                            },
                        )
                        if cursor.rowcount != 1:
                            raise ExportStoreConflictError(
                                "Previous receipt lineage could not be superseded."
                            )

                    cursor.execute(
                        """
                        UPDATE export_requests
                        SET
                          status = 'EXPORTED',
                          receipt_id = %(receipt_id)s,
                          receipt_key = %(receipt_key)s,
                          receipt_sha256 = %(receipt_sha256)s,
                          receipt_created_by = %(receipt_created_by)s,
                          receipt_created_at = %(receipt_created_at)s,
                          exported_at = %(exported_at)s,
                          last_queue_activity_at = %(last_queue_activity_at)s,
                          retention_until = COALESCE(
                            retention_until,
                            %(default_retention_until)s
                          ),
                          updated_at = NOW()
                        WHERE id = %(export_request_id)s
                        """,
                        {
                            "receipt_id": receipt_id,
                            "receipt_key": receipt_key,
                            "receipt_sha256": receipt_sha256,
                            "receipt_created_by": actor_user_id,
                            "receipt_created_at": now,
                            "exported_at": exported_at,
                            "last_queue_activity_at": now,
                            "default_retention_until": self._terminal_retention_until(
                                status="EXPORTED",
                                now=now,
                            ),
                            "export_request_id": export_request_id,
                        },
                    )
                    if cursor.rowcount != 1:
                        raise ExportStoreConflictError("Receipt projection update failed.")

                    cursor.execute(
                        """
                        INSERT INTO export_request_events (
                          id,
                          export_request_id,
                          event_type,
                          from_status,
                          to_status,
                          actor_user_id,
                          reason,
                          created_at
                        )
                        VALUES (
                          %(id)s,
                          %(export_request_id)s,
                          'REQUEST_RECEIPT_ATTACHED',
                          %(from_status)s,
                          %(to_status)s,
                          %(actor_user_id)s,
                          %(reason)s,
                          %(created_at)s
                        )
                        """,
                        {
                            "id": str(uuid4()),
                            "export_request_id": export_request_id,
                            "from_status": request_status,
                            "to_status": request_status,
                            "actor_user_id": actor_user_id,
                            "reason": f"receipt_attempt:{attempt_number}",
                            "created_at": now,
                        },
                    )
                    cursor.execute(
                        """
                        INSERT INTO export_request_events (
                          id,
                          export_request_id,
                          event_type,
                          from_status,
                          to_status,
                          actor_user_id,
                          reason,
                          created_at
                        )
                        VALUES (
                          %(id)s,
                          %(export_request_id)s,
                          'REQUEST_EXPORTED',
                          %(from_status)s,
                          'EXPORTED',
                          %(actor_user_id)s,
                          %(reason)s,
                          %(created_at)s
                        )
                        """,
                        {
                            "id": str(uuid4()),
                            "export_request_id": export_request_id,
                            "from_status": request_status,
                            "actor_user_id": actor_user_id,
                            "reason": f"receipt_attempt:{attempt_number}",
                            "created_at": now,
                        },
                    )
                connection.commit()
        except ExportStoreConflictError:
            raise
        except ExportStoreNotFoundError:
            raise
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Gateway receipt attachment failed.") from error

        request_record = self.get_request(
            project_id=project_id,
            export_request_id=export_request_id,
        )
        receipts = self.list_request_receipts(
            project_id=project_id,
            export_request_id=export_request_id,
        )
        attached_receipt = next((receipt for receipt in receipts if receipt.id == receipt_id), None)
        if attached_receipt is None:
            raise ExportStoreUnavailableError("Attached gateway receipt could not be read back.")
        return request_record, attached_receipt

    def claim_request_review(
        self,
        *,
        project_id: str,
        export_request_id: str,
        review_id: str,
        expected_review_etag: str,
        actor_user_id: str,
    ) -> tuple[ExportRequestRecord, ExportRequestReviewRecord]:
        self.ensure_schema()
        normalized_etag = expected_review_etag.strip()
        if not normalized_etag:
            raise ExportStoreConflictError("reviewEtag is required.")
        now = datetime.now(UTC)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    request_row, review_rows = self._lock_request_and_reviews(
                        cursor=cursor,
                        project_id=project_id,
                        export_request_id=export_request_id,
                    )
                    request_status = str(request_row.get("status") or "")
                    if self._is_terminal_request_status(request_status):
                        raise ExportStoreConflictError(
                            "Terminal export requests cannot be claimed."
                        )
                    active_row = self._resolve_active_required_review(review_rows=review_rows)
                    if active_row is None or str(active_row.get("id") or "") != review_id:
                        raise ExportStoreConflictError(
                            "Claim action must target the active required review stage."
                        )
                    target_row = active_row
                    target_status = str(target_row.get("status") or "")
                    if self._is_terminal_review_status(target_status):
                        raise ExportStoreConflictError("Terminal review stages cannot be claimed.")
                    current_etag = str(target_row.get("review_etag") or "")
                    if current_etag != normalized_etag:
                        raise ExportStoreConflictError(
                            "Review stage changed; refresh to use the latest reviewEtag."
                        )
                    assigned_reviewer = (
                        str(target_row["assigned_reviewer_user_id"])
                        if isinstance(target_row.get("assigned_reviewer_user_id"), str)
                        else None
                    )
                    if assigned_reviewer is not None and assigned_reviewer != actor_user_id:
                        raise ExportStoreConflictError(
                            "Review stage is already claimed by another reviewer."
                        )
                    if (
                        bool(request_row.get("requires_second_review", False))
                        and str(target_row.get("review_stage") or "") == "SECONDARY"
                    ):
                        primary_row = next(
                            (
                                row
                                for row in review_rows
                                if str(row.get("review_stage") or "") == "PRIMARY"
                            ),
                            None,
                        )
                        if (
                            primary_row is None
                            or str(primary_row.get("status") or "") != "APPROVED"
                        ):
                            raise ExportStoreConflictError(
                                "Secondary review requires an approved primary stage."
                            )
                        primary_actor = (
                            str(primary_row["acted_by_user_id"])
                            if isinstance(primary_row.get("acted_by_user_id"), str)
                            else None
                        )
                        if primary_actor == actor_user_id:
                            raise ExportStoreConflictError(
                                "Primary and secondary reviews must be by distinct reviewers."
                            )

                    next_etag = self._next_review_etag(
                        review_id=review_id,
                        actor_user_id=actor_user_id,
                        now=now,
                        action="claim",
                    )
                    cursor.execute(
                        """
                        UPDATE export_request_reviews
                        SET
                          assigned_reviewer_user_id = %(actor_user_id)s,
                          assigned_at = COALESCE(assigned_at, NOW()),
                          review_etag = %(next_review_etag)s,
                          updated_at = NOW()
                        WHERE id = %(review_id)s
                        """,
                        {
                            "actor_user_id": actor_user_id,
                            "next_review_etag": next_etag,
                            "review_id": review_id,
                        },
                    )
                    if cursor.rowcount != 1:
                        raise ExportStoreConflictError("Review stage could not be claimed.")
                    cursor.execute(
                        """
                        INSERT INTO export_request_review_events (
                          id,
                          review_id,
                          export_request_id,
                          review_stage,
                          event_type,
                          actor_user_id,
                          assigned_reviewer_user_id,
                          decision_reason,
                          return_comment,
                          created_at
                        )
                        VALUES (
                          %(id)s,
                          %(review_id)s,
                          %(export_request_id)s,
                          %(review_stage)s,
                          'REVIEW_CLAIMED',
                          %(actor_user_id)s,
                          %(assigned_reviewer_user_id)s,
                          NULL,
                          NULL,
                          %(created_at)s
                        )
                        """,
                        {
                            "id": str(uuid4()),
                            "review_id": review_id,
                            "export_request_id": export_request_id,
                            "review_stage": target_row.get("review_stage"),
                            "actor_user_id": actor_user_id,
                            "assigned_reviewer_user_id": actor_user_id,
                            "created_at": now,
                        },
                    )
                    cursor.execute(
                        """
                        UPDATE export_requests
                        SET
                          sla_due_at = COALESCE(
                            sla_due_at,
                            submitted_at + make_interval(hours => %(sla_hours)s)
                          ),
                          last_queue_activity_at = %(last_queue_activity_at)s,
                          updated_at = NOW()
                        WHERE id = %(export_request_id)s
                        """,
                        {
                            "sla_hours": self._sla_hours(),
                            "last_queue_activity_at": now,
                            "export_request_id": export_request_id,
                        },
                    )
                connection.commit()
        except ExportStoreConflictError:
            raise
        except ExportStoreNotFoundError:
            raise
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Export review claim failed.") from error

        request_record = self.get_request(
            project_id=project_id,
            export_request_id=export_request_id,
        )
        review_record = next(
            (
                row
                for row in self.list_request_reviews(export_request_id=export_request_id)
                if row.id == review_id
            ),
            None,
        )
        if review_record is None:
            raise ExportStoreUnavailableError("Claimed review stage could not be read back.")
        return request_record, review_record

    def release_request_review(
        self,
        *,
        project_id: str,
        export_request_id: str,
        review_id: str,
        expected_review_etag: str,
        actor_user_id: str,
        allow_admin_release: bool,
    ) -> tuple[ExportRequestRecord, ExportRequestReviewRecord]:
        self.ensure_schema()
        normalized_etag = expected_review_etag.strip()
        if not normalized_etag:
            raise ExportStoreConflictError("reviewEtag is required.")
        now = datetime.now(UTC)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    request_row, review_rows = self._lock_request_and_reviews(
                        cursor=cursor,
                        project_id=project_id,
                        export_request_id=export_request_id,
                    )
                    request_status = str(request_row.get("status") or "")
                    if self._is_terminal_request_status(request_status):
                        raise ExportStoreConflictError(
                            "Terminal export requests cannot release review stages."
                        )
                    active_row = self._resolve_active_required_review(review_rows=review_rows)
                    if active_row is None or str(active_row.get("id") or "") != review_id:
                        raise ExportStoreConflictError(
                            "Release action must target the active required review stage."
                        )
                    target_status = str(active_row.get("status") or "")
                    if self._is_terminal_review_status(target_status):
                        raise ExportStoreConflictError("Terminal review stages cannot be released.")
                    current_etag = str(active_row.get("review_etag") or "")
                    if current_etag != normalized_etag:
                        raise ExportStoreConflictError(
                            "Review stage changed; refresh to use the latest reviewEtag."
                        )
                    assigned_reviewer = (
                        str(active_row["assigned_reviewer_user_id"])
                        if isinstance(active_row.get("assigned_reviewer_user_id"), str)
                        else None
                    )
                    if assigned_reviewer is None:
                        raise ExportStoreConflictError("Review stage is not currently assigned.")
                    if not allow_admin_release and assigned_reviewer != actor_user_id:
                        raise ExportStoreConflictError(
                            "Only the assigned reviewer can release this stage."
                        )

                    next_etag = self._next_review_etag(
                        review_id=review_id,
                        actor_user_id=actor_user_id,
                        now=now,
                        action="release",
                    )
                    cursor.execute(
                        """
                        UPDATE export_request_reviews
                        SET
                          status = CASE WHEN status = 'IN_REVIEW' THEN 'PENDING' ELSE status END,
                          assigned_reviewer_user_id = NULL,
                          assigned_at = NULL,
                          review_etag = %(next_review_etag)s,
                          updated_at = NOW()
                        WHERE id = %(review_id)s
                        """,
                        {
                            "next_review_etag": next_etag,
                            "review_id": review_id,
                        },
                    )
                    if cursor.rowcount != 1:
                        raise ExportStoreConflictError("Review stage could not be released.")
                    cursor.execute(
                        """
                        INSERT INTO export_request_review_events (
                          id,
                          review_id,
                          export_request_id,
                          review_stage,
                          event_type,
                          actor_user_id,
                          assigned_reviewer_user_id,
                          decision_reason,
                          return_comment,
                          created_at
                        )
                        VALUES (
                          %(id)s,
                          %(review_id)s,
                          %(export_request_id)s,
                          %(review_stage)s,
                          'REVIEW_RELEASED',
                          %(actor_user_id)s,
                          NULL,
                          NULL,
                          NULL,
                          %(created_at)s
                        )
                        """,
                        {
                            "id": str(uuid4()),
                            "review_id": review_id,
                            "export_request_id": export_request_id,
                            "review_stage": active_row.get("review_stage"),
                            "actor_user_id": actor_user_id,
                            "created_at": now,
                        },
                    )
                    cursor.execute(
                        """
                        UPDATE export_requests
                        SET
                          sla_due_at = COALESCE(
                            sla_due_at,
                            submitted_at + make_interval(hours => %(sla_hours)s)
                          ),
                          last_queue_activity_at = %(last_queue_activity_at)s,
                          updated_at = NOW()
                        WHERE id = %(export_request_id)s
                        """,
                        {
                            "sla_hours": self._sla_hours(),
                            "last_queue_activity_at": now,
                            "export_request_id": export_request_id,
                        },
                    )
                connection.commit()
        except ExportStoreConflictError:
            raise
        except ExportStoreNotFoundError:
            raise
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Export review release failed.") from error

        request_record = self.get_request(
            project_id=project_id,
            export_request_id=export_request_id,
        )
        review_record = next(
            (
                row
                for row in self.list_request_reviews(export_request_id=export_request_id)
                if row.id == review_id
            ),
            None,
        )
        if review_record is None:
            raise ExportStoreUnavailableError("Released review stage could not be read back.")
        return request_record, review_record

    def start_request_review(
        self,
        *,
        project_id: str,
        export_request_id: str,
        review_id: str,
        expected_review_etag: str,
        actor_user_id: str,
    ) -> tuple[ExportRequestRecord, ExportRequestReviewRecord]:
        self.ensure_schema()
        normalized_etag = expected_review_etag.strip()
        if not normalized_etag:
            raise ExportStoreConflictError("reviewEtag is required.")
        now = datetime.now(UTC)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    request_row, review_rows = self._lock_request_and_reviews(
                        cursor=cursor,
                        project_id=project_id,
                        export_request_id=export_request_id,
                    )
                    request_status = str(request_row.get("status") or "")
                    if self._is_terminal_request_status(request_status):
                        raise ExportStoreConflictError(
                            "Terminal export requests cannot start review."
                        )
                    active_row = self._resolve_active_required_review(review_rows=review_rows)
                    if active_row is None or str(active_row.get("id") or "") != review_id:
                        raise ExportStoreConflictError(
                            "start-review must target the active required review stage."
                        )
                    target_status = str(active_row.get("status") or "")
                    if self._is_terminal_review_status(target_status):
                        raise ExportStoreConflictError("Terminal review stages cannot be started.")
                    current_etag = str(active_row.get("review_etag") or "")
                    if current_etag != normalized_etag:
                        raise ExportStoreConflictError(
                            "Review stage changed; refresh to use the latest reviewEtag."
                        )
                    assigned_reviewer = (
                        str(active_row["assigned_reviewer_user_id"])
                        if isinstance(active_row.get("assigned_reviewer_user_id"), str)
                        else None
                    )
                    if assigned_reviewer is not None and assigned_reviewer != actor_user_id:
                        raise ExportStoreConflictError(
                            "Review stage is assigned to another reviewer."
                        )
                    if (
                        bool(request_row.get("requires_second_review", False))
                        and str(active_row.get("review_stage") or "") == "SECONDARY"
                    ):
                        primary_row = next(
                            (
                                row
                                for row in review_rows
                                if str(row.get("review_stage") or "") == "PRIMARY"
                            ),
                            None,
                        )
                        if (
                            primary_row is None
                            or str(primary_row.get("status") or "") != "APPROVED"
                        ):
                            raise ExportStoreConflictError(
                                "Secondary review requires an approved primary stage."
                            )
                        primary_actor = (
                            str(primary_row["acted_by_user_id"])
                            if isinstance(primary_row.get("acted_by_user_id"), str)
                            else None
                        )
                        if primary_actor == actor_user_id:
                            raise ExportStoreConflictError(
                                "Primary and secondary reviews must be by distinct reviewers."
                            )

                    next_etag = self._next_review_etag(
                        review_id=review_id,
                        actor_user_id=actor_user_id,
                        now=now,
                        action="start",
                    )
                    cursor.execute(
                        """
                        UPDATE export_request_reviews
                        SET
                          status = 'IN_REVIEW',
                          assigned_reviewer_user_id = %(actor_user_id)s,
                          assigned_at = COALESCE(assigned_at, NOW()),
                          review_etag = %(next_review_etag)s,
                          updated_at = NOW()
                        WHERE id = %(review_id)s
                        """,
                        {
                            "actor_user_id": actor_user_id,
                            "next_review_etag": next_etag,
                            "review_id": review_id,
                        },
                    )
                    if cursor.rowcount != 1:
                        raise ExportStoreConflictError("Review stage could not be started.")
                    cursor.execute(
                        """
                        INSERT INTO export_request_review_events (
                          id,
                          review_id,
                          export_request_id,
                          review_stage,
                          event_type,
                          actor_user_id,
                          assigned_reviewer_user_id,
                          decision_reason,
                          return_comment,
                          created_at
                        )
                        VALUES (
                          %(id)s,
                          %(review_id)s,
                          %(export_request_id)s,
                          %(review_stage)s,
                          'REVIEW_STARTED',
                          %(actor_user_id)s,
                          %(assigned_reviewer_user_id)s,
                          NULL,
                          NULL,
                          %(created_at)s
                        )
                        """,
                        {
                            "id": str(uuid4()),
                            "review_id": review_id,
                            "export_request_id": export_request_id,
                            "review_stage": active_row.get("review_stage"),
                            "actor_user_id": actor_user_id,
                            "assigned_reviewer_user_id": actor_user_id,
                            "created_at": now,
                        },
                    )
                    cursor.execute(
                        """
                        UPDATE export_requests
                        SET
                          status = 'IN_REVIEW',
                          first_review_started_by = COALESCE(
                            first_review_started_by,
                            %(actor_user_id)s
                          ),
                          first_review_started_at = COALESCE(
                            first_review_started_at,
                            %(review_started_at)s
                          ),
                          sla_due_at = COALESCE(
                            sla_due_at,
                            submitted_at + make_interval(hours => %(sla_hours)s)
                          ),
                          last_queue_activity_at = %(last_queue_activity_at)s,
                          updated_at = NOW()
                        WHERE id = %(export_request_id)s
                        """,
                        {
                            "actor_user_id": actor_user_id,
                            "review_started_at": now,
                            "sla_hours": self._sla_hours(),
                            "last_queue_activity_at": now,
                            "export_request_id": export_request_id,
                        },
                    )
                    if request_status != "IN_REVIEW":
                        cursor.execute(
                            """
                            INSERT INTO export_request_events (
                              id,
                              export_request_id,
                              event_type,
                              from_status,
                              to_status,
                              actor_user_id,
                              reason,
                              created_at
                            )
                            VALUES (
                              %(id)s,
                              %(export_request_id)s,
                              'REQUEST_REVIEW_STARTED',
                              %(from_status)s,
                              'IN_REVIEW',
                              %(actor_user_id)s,
                              NULL,
                              %(created_at)s
                            )
                            """,
                            {
                                "id": str(uuid4()),
                                "export_request_id": export_request_id,
                                "from_status": request_status,
                                "actor_user_id": actor_user_id,
                                "created_at": now,
                            },
                        )
                connection.commit()
        except ExportStoreConflictError:
            raise
        except ExportStoreNotFoundError:
            raise
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Export review start failed.") from error

        request_record = self.get_request(
            project_id=project_id,
            export_request_id=export_request_id,
        )
        review_record = next(
            (
                row
                for row in self.list_request_reviews(export_request_id=export_request_id)
                if row.id == review_id
            ),
            None,
        )
        if review_record is None:
            raise ExportStoreUnavailableError("Started review stage could not be read back.")
        return request_record, review_record

    def decide_request_review(
        self,
        *,
        project_id: str,
        export_request_id: str,
        review_id: str,
        expected_review_etag: str,
        actor_user_id: str,
        decision: ExportRequestDecision,
        decision_reason: str | None,
        return_comment: str | None,
    ) -> tuple[ExportRequestRecord, ExportRequestReviewRecord]:
        self.ensure_schema()
        normalized_etag = expected_review_etag.strip()
        if not normalized_etag:
            raise ExportStoreConflictError("reviewEtag is required.")
        if decision == "REJECT" and not isinstance(decision_reason, str):
            raise ExportStoreConflictError("decisionReason is required for REJECT.")
        if decision == "RETURN" and not isinstance(return_comment, str):
            raise ExportStoreConflictError("returnComment is required for RETURN.")

        now = datetime.now(UTC)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    request_row, review_rows = self._lock_request_and_reviews(
                        cursor=cursor,
                        project_id=project_id,
                        export_request_id=export_request_id,
                    )
                    request_status = str(request_row.get("status") or "")
                    if self._is_terminal_request_status(request_status):
                        raise ExportStoreConflictError(
                            "Terminal export requests cannot accept review decisions."
                        )
                    active_row = self._resolve_active_required_review(review_rows=review_rows)
                    if active_row is None or str(active_row.get("id") or "") != review_id:
                        raise ExportStoreConflictError(
                            "Decision action must target the active required review stage."
                        )
                    target_status = str(active_row.get("status") or "")
                    if target_status != "IN_REVIEW":
                        raise ExportStoreConflictError(
                            "Review stage must be IN_REVIEW before a decision is recorded."
                        )
                    current_etag = str(active_row.get("review_etag") or "")
                    if current_etag != normalized_etag:
                        raise ExportStoreConflictError(
                            "Review stage changed; refresh to use the latest reviewEtag."
                        )
                    assigned_reviewer = (
                        str(active_row["assigned_reviewer_user_id"])
                        if isinstance(active_row.get("assigned_reviewer_user_id"), str)
                        else None
                    )
                    if assigned_reviewer != actor_user_id:
                        raise ExportStoreConflictError(
                            "Only the assigned reviewer can record a decision."
                        )

                    review_stage = str(active_row.get("review_stage") or "")
                    requires_second_review = bool(request_row.get("requires_second_review", False))
                    primary_row = next(
                        (
                            row
                            for row in review_rows
                            if str(row.get("review_stage") or "") == "PRIMARY"
                        ),
                        None,
                    )
                    if requires_second_review and review_stage == "SECONDARY":
                        if (
                            primary_row is None
                            or str(primary_row.get("status") or "") != "APPROVED"
                        ):
                            raise ExportStoreConflictError(
                                "Secondary review requires an approved primary stage."
                            )
                        primary_actor = (
                            str(primary_row["acted_by_user_id"])
                            if isinstance(primary_row.get("acted_by_user_id"), str)
                            else None
                        )
                        if primary_actor == actor_user_id:
                            raise ExportStoreConflictError(
                                "Primary and secondary reviews must be by distinct reviewers."
                            )
                    if (
                        decision == "APPROVE"
                        and requires_second_review
                        and review_stage == "PRIMARY"
                    ):
                        secondary_required = any(
                            str(row.get("review_stage") or "") == "SECONDARY"
                            and bool(row.get("is_required", False))
                            for row in review_rows
                        )
                        if not secondary_required:
                            raise ExportStoreConflictError(
                                "Dual-review request is missing a required secondary stage."
                            )

                    next_review_status: ExportRequestReviewStatus
                    next_review_event_type: ExportRequestReviewEventType
                    next_request_status: ExportRequestStatus
                    next_request_event_type: ExportRequestEventType | None = None
                    request_event_reason: str | None = None
                    request_is_terminal = False
                    if decision == "APPROVE":
                        next_review_status = "APPROVED"
                        next_review_event_type = "REVIEW_APPROVED"
                        if requires_second_review and review_stage == "PRIMARY":
                            next_request_status = "IN_REVIEW"
                        else:
                            next_request_status = "APPROVED"
                            next_request_event_type = "REQUEST_APPROVED"
                            request_event_reason = decision_reason
                            request_is_terminal = True
                    elif decision == "REJECT":
                        next_review_status = "REJECTED"
                        next_review_event_type = "REVIEW_REJECTED"
                        next_request_status = "REJECTED"
                        next_request_event_type = "REQUEST_REJECTED"
                        request_event_reason = decision_reason
                        request_is_terminal = True
                    else:
                        next_review_status = "RETURNED"
                        next_review_event_type = "REVIEW_RETURNED"
                        next_request_status = "RETURNED"
                        next_request_event_type = "REQUEST_RETURNED"
                        request_event_reason = return_comment
                        request_is_terminal = True

                    next_etag = self._next_review_etag(
                        review_id=review_id,
                        actor_user_id=actor_user_id,
                        now=now,
                        action=f"decision:{decision}",
                    )
                    cursor.execute(
                        """
                        UPDATE export_request_reviews
                        SET
                          status = %(status)s,
                          acted_by_user_id = %(acted_by_user_id)s,
                          acted_at = %(acted_at)s,
                          decision_reason = %(decision_reason)s,
                          return_comment = %(return_comment)s,
                          review_etag = %(next_review_etag)s,
                          updated_at = NOW()
                        WHERE id = %(review_id)s
                        """,
                        {
                            "status": next_review_status,
                            "acted_by_user_id": actor_user_id,
                            "acted_at": now,
                            "decision_reason": decision_reason,
                            "return_comment": return_comment,
                            "next_review_etag": next_etag,
                            "review_id": review_id,
                        },
                    )
                    if cursor.rowcount != 1:
                        raise ExportStoreConflictError("Review decision update failed.")

                    cursor.execute(
                        """
                        INSERT INTO export_request_review_events (
                          id,
                          review_id,
                          export_request_id,
                          review_stage,
                          event_type,
                          actor_user_id,
                          assigned_reviewer_user_id,
                          decision_reason,
                          return_comment,
                          created_at
                        )
                        VALUES (
                          %(id)s,
                          %(review_id)s,
                          %(export_request_id)s,
                          %(review_stage)s,
                          %(event_type)s,
                          %(actor_user_id)s,
                          %(assigned_reviewer_user_id)s,
                          %(decision_reason)s,
                          %(return_comment)s,
                          %(created_at)s
                        )
                        """,
                        {
                            "id": str(uuid4()),
                            "review_id": review_id,
                            "export_request_id": export_request_id,
                            "review_stage": review_stage,
                            "event_type": next_review_event_type,
                            "actor_user_id": actor_user_id,
                            "assigned_reviewer_user_id": actor_user_id,
                            "decision_reason": decision_reason,
                            "return_comment": return_comment,
                            "created_at": now,
                        },
                    )

                    cursor.execute(
                        """
                        UPDATE export_requests
                        SET
                          status = %(status)s,
                          last_queue_activity_at = %(last_queue_activity_at)s,
                          retention_until = CASE
                            WHEN %(request_is_terminal)s THEN COALESCE(
                              retention_until,
                              CASE
                                WHEN %(status)s = 'APPROVED' THEN %(terminal_retention_approved)s
                                ELSE %(terminal_retention_other)s
                              END
                            )
                            ELSE retention_until
                          END,
                          final_review_id = CASE
                            WHEN %(request_is_terminal)s THEN %(final_review_id)s
                            ELSE final_review_id
                          END,
                          final_decision_by = CASE
                            WHEN %(request_is_terminal)s THEN %(final_decision_by)s
                            ELSE final_decision_by
                          END,
                          final_decision_at = CASE
                            WHEN %(request_is_terminal)s THEN %(final_decision_at)s
                            ELSE final_decision_at
                          END,
                          final_decision_reason = CASE
                            WHEN %(request_is_terminal)s THEN %(final_decision_reason)s
                            ELSE final_decision_reason
                          END,
                          final_return_comment = CASE
                            WHEN %(request_is_terminal)s THEN %(final_return_comment)s
                            ELSE final_return_comment
                          END,
                          updated_at = NOW()
                        WHERE id = %(export_request_id)s
                        """,
                        {
                            "status": next_request_status,
                            "last_queue_activity_at": now,
                            "request_is_terminal": request_is_terminal,
                            "terminal_retention_approved": self._terminal_retention_until(
                                status="APPROVED",
                                now=now,
                            ),
                            "terminal_retention_other": self._terminal_retention_until(
                                status="RETURNED",
                                now=now,
                            ),
                            "final_review_id": review_id if request_is_terminal else None,
                            "final_decision_by": actor_user_id if request_is_terminal else None,
                            "final_decision_at": now if request_is_terminal else None,
                            "final_decision_reason": decision_reason
                            if request_is_terminal
                            else None,
                            "final_return_comment": return_comment
                            if request_is_terminal
                            else None,
                            "export_request_id": export_request_id,
                        },
                    )
                    if cursor.rowcount != 1:
                        raise ExportStoreConflictError("Request projection update failed.")

                    if next_request_event_type is not None:
                        cursor.execute(
                            """
                            INSERT INTO export_request_events (
                              id,
                              export_request_id,
                              event_type,
                              from_status,
                              to_status,
                              actor_user_id,
                              reason,
                              created_at
                            )
                            VALUES (
                              %(id)s,
                              %(export_request_id)s,
                              %(event_type)s,
                              %(from_status)s,
                              %(to_status)s,
                              %(actor_user_id)s,
                              %(reason)s,
                              %(created_at)s
                            )
                            """,
                            {
                                "id": str(uuid4()),
                                "export_request_id": export_request_id,
                                "event_type": next_request_event_type,
                                "from_status": request_status,
                                "to_status": next_request_status,
                                "actor_user_id": actor_user_id,
                                "reason": request_event_reason,
                                "created_at": now,
                            },
                        )
                connection.commit()
        except ExportStoreConflictError:
            raise
        except ExportStoreNotFoundError:
            raise
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Export review decision failed.") from error

        request_record = self.get_request(
            project_id=project_id,
            export_request_id=export_request_id,
        )
        review_record = next(
            (
                row
                for row in self.list_request_reviews(export_request_id=export_request_id)
                if row.id == review_id
            ),
            None,
        )
        if review_record is None:
            raise ExportStoreUnavailableError("Decided review stage could not be read back.")
        return request_record, review_record

    def _list_due_reminder_candidates(self, *, limit: int) -> tuple[tuple[str, str], ...]:
        self.ensure_schema()
        normalized_limit = max(1, min(limit, 500))
        now = datetime.now(UTC)
        reminder_cutoff = now - timedelta(hours=self._reminder_after_hours())
        reminder_cooldown_cutoff = now - timedelta(hours=self._reminder_cooldown_hours())
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          req.project_id,
                          req.id
                        FROM export_requests AS req
                        WHERE req.status IN ('SUBMITTED', 'RESUBMITTED', 'IN_REVIEW')
                          AND COALESCE(req.last_queue_activity_at, req.submitted_at) <= %(cutoff)s
                          AND NOT EXISTS (
                            SELECT 1
                            FROM export_request_events AS evt
                            WHERE evt.export_request_id = req.id
                              AND evt.event_type = 'REQUEST_REMINDER_SENT'
                              AND evt.created_at > %(cooldown_cutoff)s
                          )
                        ORDER BY
                          COALESCE(req.last_queue_activity_at, req.submitted_at) ASC,
                          req.id ASC
                        LIMIT %(limit)s
                        """,
                        {
                            "cutoff": reminder_cutoff,
                            "cooldown_cutoff": reminder_cooldown_cutoff,
                            "limit": normalized_limit,
                        },
                    )
                    rows = cursor.fetchall()
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Reminder eligibility listing failed.") from error
        return tuple(
            (str(row.get("project_id") or ""), str(row.get("id") or ""))
            for row in rows
            if isinstance(row.get("project_id"), str) and isinstance(row.get("id"), str)
        )

    def _list_due_escalation_candidates(self, *, limit: int) -> tuple[tuple[str, str], ...]:
        self.ensure_schema()
        normalized_limit = max(1, min(limit, 500))
        now = datetime.now(UTC)
        escalation_cutoff = now - timedelta(hours=self._escalation_after_sla_hours())
        escalation_cooldown_cutoff = now - timedelta(hours=self._escalation_cooldown_hours())
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          req.project_id,
                          req.id
                        FROM export_requests AS req
                        WHERE req.status IN ('SUBMITTED', 'RESUBMITTED', 'IN_REVIEW')
                          AND req.sla_due_at IS NOT NULL
                          AND req.sla_due_at <= %(escalation_cutoff)s
                          AND NOT EXISTS (
                            SELECT 1
                            FROM export_request_events AS evt
                            WHERE evt.export_request_id = req.id
                              AND evt.event_type = 'REQUEST_ESCALATED'
                              AND evt.created_at > %(cooldown_cutoff)s
                          )
                        ORDER BY req.sla_due_at ASC, req.id ASC
                        LIMIT %(limit)s
                        """,
                        {
                            "escalation_cutoff": escalation_cutoff,
                            "cooldown_cutoff": escalation_cooldown_cutoff,
                            "limit": normalized_limit,
                        },
                    )
                    rows = cursor.fetchall()
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Escalation eligibility listing failed.") from error
        return tuple(
            (str(row.get("project_id") or ""), str(row.get("id") or ""))
            for row in rows
            if isinstance(row.get("project_id"), str) and isinstance(row.get("id"), str)
        )

    def _append_request_operational_event(
        self,
        *,
        project_id: str,
        export_request_id: str,
        actor_user_id: str,
        event_type: ExportRequestEventType,
        reason: str | None,
        cooldown_hours: int,
        require_escalation_condition: bool = False,
    ) -> ExportRequestRecord:
        self.ensure_schema()
        now = datetime.now(UTC)
        normalized_reason = reason.strip() if isinstance(reason, str) and reason.strip() else None
        cooldown_floor = now - timedelta(hours=max(1, cooldown_hours))
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          submitted_at,
                          status,
                          sla_due_at
                        FROM export_requests
                        WHERE project_id = %(project_id)s
                          AND id = %(export_request_id)s
                        FOR UPDATE
                        """,
                        {
                            "project_id": project_id,
                            "export_request_id": export_request_id,
                        },
                    )
                    request_row = cursor.fetchone()
                    if request_row is None:
                        raise ExportStoreNotFoundError("Export request not found.")
                    request_status = str(request_row.get("status") or "")
                    if not self._is_open_request_status(request_status):
                        raise ExportStoreConflictError(
                            "Only open export requests can accept reminder/escalation events."
                        )

                    cursor.execute(
                        """
                        SELECT created_at
                        FROM export_request_events
                        WHERE export_request_id = %(export_request_id)s
                          AND event_type = %(event_type)s
                        ORDER BY created_at DESC, id DESC
                        LIMIT 1
                        """,
                        {
                            "export_request_id": export_request_id,
                            "event_type": event_type,
                        },
                    )
                    latest_same_event = cursor.fetchone()
                    latest_created_at = (
                        latest_same_event.get("created_at")
                        if isinstance(latest_same_event, dict)
                        else None
                    )
                    if isinstance(latest_created_at, datetime) and latest_created_at > cooldown_floor:
                        raise ExportStoreConflictError(
                            "Reminder/escalation cooldown is still active for this request."
                        )

                    if require_escalation_condition:
                        sla_due_at = request_row.get("sla_due_at")
                        if not isinstance(sla_due_at, datetime):
                            raise ExportStoreConflictError(
                                "Escalation requires a persisted SLA due timestamp."
                            )
                        escalation_cutoff = now - timedelta(hours=self._escalation_after_sla_hours())
                        if sla_due_at > escalation_cutoff:
                            raise ExportStoreConflictError(
                                "Escalation threshold has not been met for this request."
                            )

                    cursor.execute(
                        """
                        INSERT INTO export_request_events (
                          id,
                          export_request_id,
                          event_type,
                          from_status,
                          to_status,
                          actor_user_id,
                          reason,
                          created_at
                        )
                        VALUES (
                          %(id)s,
                          %(export_request_id)s,
                          %(event_type)s,
                          %(from_status)s,
                          %(to_status)s,
                          %(actor_user_id)s,
                          %(reason)s,
                          %(created_at)s
                        )
                        """,
                        {
                            "id": str(uuid4()),
                            "export_request_id": export_request_id,
                            "event_type": event_type,
                            "from_status": request_status,
                            "to_status": request_status,
                            "actor_user_id": actor_user_id,
                            "reason": normalized_reason,
                            "created_at": now,
                        },
                    )

                    cursor.execute(
                        """
                        UPDATE export_requests
                        SET
                          sla_due_at = COALESCE(
                            sla_due_at,
                            submitted_at + make_interval(hours => %(sla_hours)s)
                          ),
                          last_queue_activity_at = %(last_queue_activity_at)s,
                          updated_at = NOW()
                        WHERE id = %(export_request_id)s
                        """,
                        {
                            "sla_hours": self._sla_hours(),
                            "last_queue_activity_at": now,
                            "export_request_id": export_request_id,
                        },
                    )
                    if cursor.rowcount != 1:
                        raise ExportStoreConflictError(
                            "Reminder/escalation request projection update failed."
                        )
                connection.commit()
        except ExportStoreConflictError:
            raise
        except ExportStoreNotFoundError:
            raise
        except psycopg.Error as error:
            raise ExportStoreUnavailableError(
                "Reminder/escalation event append failed."
            ) from error
        return self.get_request(project_id=project_id, export_request_id=export_request_id)

    def record_request_reminder(
        self,
        *,
        project_id: str,
        export_request_id: str,
        actor_user_id: str,
        reason: str | None = None,
    ) -> ExportRequestRecord:
        return self._append_request_operational_event(
            project_id=project_id,
            export_request_id=export_request_id,
            actor_user_id=actor_user_id,
            event_type="REQUEST_REMINDER_SENT",
            reason=reason,
            cooldown_hours=self._reminder_cooldown_hours(),
            require_escalation_condition=False,
        )

    def record_request_escalation(
        self,
        *,
        project_id: str,
        export_request_id: str,
        actor_user_id: str,
        reason: str | None = None,
    ) -> ExportRequestRecord:
        return self._append_request_operational_event(
            project_id=project_id,
            export_request_id=export_request_id,
            actor_user_id=actor_user_id,
            event_type="REQUEST_ESCALATED",
            reason=reason,
            cooldown_hours=self._escalation_cooldown_hours(),
            require_escalation_condition=True,
        )

    def apply_retention_policies(self, *, limit: int = 500) -> int:
        self.ensure_schema()
        normalized_limit = max(1, min(limit, 5_000))
        now = datetime.now(UTC)
        stale_cutoff = now - timedelta(days=self._stale_open_after_days())
        stale_open_retention_until = now + timedelta(days=self._retention_stale_open_days())
        terminal_approved_retention_until = now + timedelta(
            days=self._retention_terminal_approved_days()
        )
        terminal_other_retention_until = now + timedelta(days=self._retention_terminal_other_days())
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        WITH candidates AS (
                          SELECT id
                          FROM export_requests
                          WHERE
                            (
                              status IN ('SUBMITTED', 'RESUBMITTED', 'IN_REVIEW')
                              AND retention_until IS NULL
                              AND COALESCE(last_queue_activity_at, submitted_at) <= %(stale_cutoff)s
                            )
                            OR (
                              status IN ('APPROVED', 'EXPORTED', 'REJECTED', 'RETURNED')
                              AND retention_until IS NULL
                            )
                          ORDER BY updated_at ASC, id ASC
                          LIMIT %(limit)s
                          FOR UPDATE SKIP LOCKED
                        )
                        UPDATE export_requests AS req
                        SET
                          retention_until = CASE
                            WHEN req.status IN ('SUBMITTED', 'RESUBMITTED', 'IN_REVIEW')
                              THEN %(stale_open_retention_until)s
                            WHEN req.status IN ('APPROVED', 'EXPORTED')
                              THEN %(terminal_approved_retention_until)s
                            ELSE %(terminal_other_retention_until)s
                          END,
                          last_queue_activity_at = COALESCE(req.last_queue_activity_at, %(now)s),
                          updated_at = NOW()
                        FROM candidates
                        WHERE req.id = candidates.id
                        RETURNING req.id
                        """,
                        {
                            "stale_cutoff": stale_cutoff,
                            "limit": normalized_limit,
                            "stale_open_retention_until": stale_open_retention_until,
                            "terminal_approved_retention_until": terminal_approved_retention_until,
                            "terminal_other_retention_until": terminal_other_retention_until,
                            "now": now,
                        },
                    )
                    rows = cursor.fetchall()
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Retention policy application failed.") from error
        return len(rows)

    def run_operations_maintenance(
        self,
        *,
        actor_user_id: str,
        batch_limit: int = 200,
    ) -> ExportOperationsMaintenanceResult:
        normalized_batch_limit = max(1, min(batch_limit, 500))
        run_at = datetime.now(UTC)
        reminders_appended = 0
        escalations_appended = 0

        for project_id, request_id in self._list_due_reminder_candidates(limit=normalized_batch_limit):
            try:
                self.record_request_reminder(
                    project_id=project_id,
                    export_request_id=request_id,
                    actor_user_id=actor_user_id,
                    reason="SLA reminder threshold reached.",
                )
                reminders_appended += 1
            except ExportStoreConflictError:
                continue

        for project_id, request_id in self._list_due_escalation_candidates(limit=normalized_batch_limit):
            try:
                self.record_request_escalation(
                    project_id=project_id,
                    export_request_id=request_id,
                    actor_user_id=actor_user_id,
                    reason="SLA escalation threshold reached.",
                )
                escalations_appended += 1
            except ExportStoreConflictError:
                continue

        retention_updates_applied = self.apply_retention_policies(limit=normalized_batch_limit * 3)
        return ExportOperationsMaintenanceResult(
            run_at=run_at,
            reminders_appended=reminders_appended,
            escalations_appended=escalations_appended,
            retention_updates_applied=retention_updates_applied,
            retention_audit_safe=True,
        )

    def get_operations_export_status(self) -> ExportOperationsStatusRecord:
        self.ensure_schema()
        now = datetime.now(UTC)
        stale_cutoff = now - timedelta(days=self._stale_open_after_days())
        reminder_due_cutoff = now - timedelta(hours=self._reminder_after_hours())
        reminder_cooldown_cutoff = now - timedelta(hours=self._reminder_cooldown_hours())
        escalation_due_cutoff = now - timedelta(hours=self._escalation_after_sla_hours())
        escalation_cooldown_cutoff = now - timedelta(hours=self._escalation_cooldown_hours())
        retention_pending_cutoff = now + timedelta(days=self._retention_pending_window_days())
        last_day_cutoff = now - timedelta(hours=24)

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          status,
                          submitted_at,
                          first_review_started_at,
                          sla_due_at,
                          last_queue_activity_at,
                          retention_until
                        FROM export_requests
                        """
                    )
                    request_rows = cursor.fetchall()

                    cursor.execute(
                        """
                        SELECT
                          export_request_id,
                          event_type,
                          MAX(created_at) AS latest_created_at
                        FROM export_request_events
                        WHERE event_type IN ('REQUEST_REMINDER_SENT', 'REQUEST_ESCALATED')
                        GROUP BY export_request_id, event_type
                        """
                    )
                    latest_event_rows = cursor.fetchall()

                    cursor.execute(
                        """
                        SELECT
                          COUNT(*) FILTER (
                            WHERE event_type = 'REQUEST_REMINDER_SENT'
                          )::INT AS reminders_total,
                          COUNT(*) FILTER (
                            WHERE event_type = 'REQUEST_REMINDER_SENT'
                              AND created_at >= %(last_day_cutoff)s
                          )::INT AS reminders_last_24h,
                          COUNT(*) FILTER (
                            WHERE event_type = 'REQUEST_ESCALATED'
                          )::INT AS escalations_total
                        FROM export_request_events
                        """,
                        {"last_day_cutoff": last_day_cutoff},
                    )
                    event_totals_row = cursor.fetchone() or {}
                connection.commit()
        except psycopg.Error as error:
            raise ExportStoreUnavailableError("Export operations status summary failed.") from error

        latest_events: dict[tuple[str, str], datetime] = {}
        for row in latest_event_rows:
            request_id = row.get("export_request_id")
            event_type = row.get("event_type")
            created_at = row.get("latest_created_at")
            if (
                isinstance(request_id, str)
                and isinstance(event_type, str)
                and isinstance(created_at, datetime)
            ):
                latest_events[(request_id, event_type)] = created_at

        open_request_count = 0
        aging_unstarted_count = 0
        aging_no_sla_count = 0
        aging_on_track_count = 0
        aging_due_soon_count = 0
        aging_overdue_count = 0
        stale_open_count = 0
        reminder_due_count = 0
        escalation_due_count = 0
        escalated_open_count = 0
        retention_pending_count = 0
        terminal_approved_count = 0
        terminal_exported_count = 0
        terminal_rejected_count = 0
        terminal_returned_count = 0

        for row in request_rows:
            request_id = str(row.get("id") or "")
            status = str(row.get("status") or "")
            submitted_at = row.get("submitted_at")
            first_review_started_at = row.get("first_review_started_at")
            sla_due_at = row.get("sla_due_at")
            last_queue_activity_at = row.get("last_queue_activity_at")
            retention_until = row.get("retention_until")

            if isinstance(retention_until, datetime) and retention_until <= retention_pending_cutoff:
                retention_pending_count += 1

            if status == "APPROVED":
                terminal_approved_count += 1
            elif status == "EXPORTED":
                terminal_exported_count += 1
            elif status == "REJECTED":
                terminal_rejected_count += 1
            elif status == "RETURNED":
                terminal_returned_count += 1

            if not self._is_open_request_status(status):
                continue

            open_request_count += 1
            reference_activity_at = (
                last_queue_activity_at
                if isinstance(last_queue_activity_at, datetime)
                else submitted_at
            )
            if isinstance(reference_activity_at, datetime) and reference_activity_at <= stale_cutoff:
                stale_open_count += 1

            if (
                isinstance(reference_activity_at, datetime)
                and reference_activity_at <= reminder_due_cutoff
            ):
                latest_reminder = latest_events.get((request_id, "REQUEST_REMINDER_SENT"))
                if latest_reminder is None or latest_reminder <= reminder_cooldown_cutoff:
                    reminder_due_count += 1

            if isinstance(sla_due_at, datetime):
                remaining_seconds = int((sla_due_at - now).total_seconds())
                if remaining_seconds < 0:
                    aging_overdue_count += 1
                elif not isinstance(first_review_started_at, datetime):
                    aging_unstarted_count += 1
                elif remaining_seconds <= 24 * 60 * 60:
                    aging_due_soon_count += 1
                else:
                    aging_on_track_count += 1

                if sla_due_at <= escalation_due_cutoff:
                    latest_escalation = latest_events.get((request_id, "REQUEST_ESCALATED"))
                    if latest_escalation is None or latest_escalation <= escalation_cooldown_cutoff:
                        escalation_due_count += 1
            else:
                if isinstance(first_review_started_at, datetime):
                    aging_no_sla_count += 1
                else:
                    aging_unstarted_count += 1

            if (request_id, "REQUEST_ESCALATED") in latest_events:
                escalated_open_count += 1

        return ExportOperationsStatusRecord(
            generated_at=now,
            open_request_count=open_request_count,
            aging_unstarted_count=aging_unstarted_count,
            aging_no_sla_count=aging_no_sla_count,
            aging_on_track_count=aging_on_track_count,
            aging_due_soon_count=aging_due_soon_count,
            aging_overdue_count=aging_overdue_count,
            stale_open_count=stale_open_count,
            reminder_due_count=reminder_due_count,
            reminders_sent_last_24h=int(event_totals_row.get("reminders_last_24h") or 0),
            reminders_sent_total=int(event_totals_row.get("reminders_total") or 0),
            escalation_due_count=escalation_due_count,
            escalated_open_count=escalated_open_count,
            escalations_total=int(event_totals_row.get("escalations_total") or 0),
            retention_pending_count=retention_pending_count,
            retention_pending_window_days=self._retention_pending_window_days(),
            terminal_approved_count=terminal_approved_count,
            terminal_exported_count=terminal_exported_count,
            terminal_rejected_count=terminal_rejected_count,
            terminal_returned_count=terminal_returned_count,
            policy_sla_hours=self._sla_hours(),
            policy_reminder_after_hours=self._reminder_after_hours(),
            policy_reminder_cooldown_hours=self._reminder_cooldown_hours(),
            policy_escalation_after_sla_hours=self._escalation_after_sla_hours(),
            policy_escalation_cooldown_hours=self._escalation_cooldown_hours(),
            policy_stale_open_after_days=self._stale_open_after_days(),
            policy_retention_stale_open_days=self._retention_stale_open_days(),
            policy_retention_terminal_approved_days=self._retention_terminal_approved_days(),
            policy_retention_terminal_other_days=self._retention_terminal_other_days(),
        )


__all__ = [
    "ExportStore",
    "ExportStoreConflictError",
    "ExportStoreNotFoundError",
    "ExportStoreUnavailableError",
]
