from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
import json
from typing import Literal, Mapping, Sequence
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from app.core.config import Settings, get_settings

GovernanceArtifactStatus = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]
GovernanceReadinessStatus = Literal["PENDING", "READY", "FAILED"]
GovernanceGenerationStatus = Literal["IDLE", "RUNNING", "FAILED", "CANCELED"]
GovernanceLedgerVerificationStatus = Literal["PENDING", "VALID", "INVALID"]
GovernanceRunEventType = Literal[
    "RUN_CREATED",
    "MANIFEST_STARTED",
    "MANIFEST_SUCCEEDED",
    "MANIFEST_FAILED",
    "MANIFEST_CANCELED",
    "LEDGER_STARTED",
    "LEDGER_SUCCEEDED",
    "LEDGER_FAILED",
    "LEDGER_CANCELED",
    "LEDGER_VERIFY_STARTED",
    "LEDGER_VERIFIED_VALID",
    "LEDGER_VERIFIED_INVALID",
    "LEDGER_VERIFY_CANCELED",
    "REGENERATE_REQUESTED",
    "RUN_CANCELED",
    "READY_SET",
    "READY_FAILED",
]
GovernanceLedgerVerificationResult = Literal["VALID", "INVALID"]
ExportCandidateSourcePhase = Literal["PHASE6", "PHASE7", "PHASE9", "PHASE10"]
ExportCandidateSourceArtifactKind = Literal[
    "REDACTION_RUN_OUTPUT",
    "DEPOSIT_BUNDLE",
    "DERIVATIVE_SNAPSHOT",
]
ExportCandidateKind = Literal[
    "SAFEGUARDED_PREVIEW",
    "POLICY_RERUN",
    "DEPOSIT_BUNDLE",
    "SAFEGUARDED_DERIVATIVE",
]
ExportCandidateEligibilityStatus = Literal["ELIGIBLE", "SUPERSEDED"]


@dataclass(frozen=True)
class RedactionManifestRecord:
    id: str
    run_id: str
    project_id: str
    document_id: str
    source_review_snapshot_key: str
    source_review_snapshot_sha256: str
    attempt_number: int
    supersedes_manifest_id: str | None
    superseded_by_manifest_id: str | None
    status: GovernanceArtifactStatus
    manifest_key: str | None
    manifest_sha256: str | None
    format_version: int
    started_at: datetime | None
    finished_at: datetime | None
    canceled_by: str | None
    canceled_at: datetime | None
    failure_reason: str | None
    created_by: str
    created_at: datetime


@dataclass(frozen=True)
class RedactionEvidenceLedgerRecord:
    id: str
    run_id: str
    project_id: str
    document_id: str
    source_review_snapshot_key: str
    source_review_snapshot_sha256: str
    attempt_number: int
    supersedes_ledger_id: str | None
    superseded_by_ledger_id: str | None
    status: GovernanceArtifactStatus
    ledger_key: str | None
    ledger_sha256: str | None
    hash_chain_version: str
    started_at: datetime | None
    finished_at: datetime | None
    canceled_by: str | None
    canceled_at: datetime | None
    failure_reason: str | None
    created_by: str
    created_at: datetime


@dataclass(frozen=True)
class GovernanceReadinessProjectionRecord:
    run_id: str
    project_id: str
    document_id: str
    status: GovernanceReadinessStatus
    generation_status: GovernanceGenerationStatus
    manifest_id: str | None
    ledger_id: str | None
    last_ledger_verification_run_id: str | None
    last_manifest_sha256: str | None
    last_ledger_sha256: str | None
    ledger_verification_status: GovernanceLedgerVerificationStatus
    ledger_verified_at: datetime | None
    ready_at: datetime | None
    last_error_code: str | None
    updated_at: datetime


@dataclass(frozen=True)
class GovernanceRunEventRecord:
    id: str
    run_id: str
    event_type: GovernanceRunEventType
    actor_user_id: str | None
    from_status: str | None
    to_status: str | None
    reason: str | None
    created_at: datetime


@dataclass(frozen=True)
class LedgerVerificationRunRecord:
    id: str
    run_id: str
    attempt_number: int
    supersedes_verification_run_id: str | None
    superseded_by_verification_run_id: str | None
    status: GovernanceArtifactStatus
    verification_result: GovernanceLedgerVerificationResult | None
    result_json: dict[str, object] | None
    started_at: datetime | None
    finished_at: datetime | None
    canceled_by: str | None
    canceled_at: datetime | None
    failure_reason: str | None
    created_by: str
    created_at: datetime


@dataclass(frozen=True)
class GovernanceRunSummaryRecord:
    run_id: str
    project_id: str
    document_id: str
    run_status: str
    review_status: str | None
    approved_snapshot_key: str | None
    approved_snapshot_sha256: str | None
    run_output_status: str | None
    run_output_manifest_sha256: str | None
    run_created_at: datetime
    run_finished_at: datetime | None
    readiness_status: GovernanceReadinessStatus
    generation_status: GovernanceGenerationStatus
    ready_manifest_id: str | None
    ready_ledger_id: str | None
    latest_manifest_sha256: str | None
    latest_ledger_sha256: str | None
    ledger_verification_status: GovernanceLedgerVerificationStatus
    ready_at: datetime | None
    last_error_code: str | None
    updated_at: datetime


@dataclass(frozen=True)
class GovernanceOverviewRecord:
    project_id: str
    document_id: str
    active_run_id: str | None
    total_runs: int
    approved_runs: int
    ready_runs: int
    pending_runs: int
    failed_runs: int
    latest_run_id: str | None
    latest_ready_run_id: str | None


@dataclass(frozen=True)
class ExportCandidateSnapshotContractRecord:
    id: str
    project_id: str
    source_phase: ExportCandidateSourcePhase
    source_artifact_kind: ExportCandidateSourceArtifactKind
    source_run_id: str | None
    source_artifact_id: str
    governance_run_id: str | None
    governance_manifest_id: str | None
    governance_ledger_id: str | None
    governance_manifest_sha256: str | None
    governance_ledger_sha256: str | None
    policy_snapshot_hash: str | None
    policy_id: str | None
    policy_family_id: str | None
    policy_version: str | None
    candidate_kind: ExportCandidateKind
    artefact_manifest_json: dict[str, object]
    candidate_sha256: str
    eligibility_status: ExportCandidateEligibilityStatus
    supersedes_candidate_snapshot_id: str | None
    superseded_by_candidate_snapshot_id: str | None
    created_by: str
    created_at: datetime


@dataclass(frozen=True)
class GovernanceReadyPairResolution:
    ready_manifest: RedactionManifestRecord | None
    ready_ledger: RedactionEvidenceLedgerRecord | None
    ledger_verification_status: GovernanceLedgerVerificationStatus
    ledger_verified_at: datetime | None


def _verification_ledger_sha(verification: LedgerVerificationRunRecord) -> str | None:
    if not isinstance(verification.result_json, Mapping):
        return None
    ledger_sha = verification.result_json.get("ledgerSha256")
    if not isinstance(ledger_sha, str):
        return None
    normalized = ledger_sha.strip()
    return normalized if normalized else None


def _verification_targets_ledger_sha(
    *,
    verification: LedgerVerificationRunRecord,
    ledger_sha256: str,
) -> bool:
    if verification.status != "SUCCEEDED":
        return False
    if verification.verification_result not in {"VALID", "INVALID"}:
        return False
    result_json = verification.result_json
    if not isinstance(result_json, Mapping):
        return False
    row_sha = result_json.get("ledgerSha256")
    return isinstance(row_sha, str) and row_sha.strip() == ledger_sha256


def resolve_governance_ready_pair_from_attempts(
    *,
    manifests: Sequence[RedactionManifestRecord],
    ledgers: Sequence[RedactionEvidenceLedgerRecord],
    successful_verifications: Sequence[LedgerVerificationRunRecord],
    existing_ready_manifest_id: str | None,
    existing_ready_ledger_id: str | None,
) -> GovernanceReadyPairResolution:
    succeeded_manifests = sorted(
        (
            item
            for item in manifests
            if item.status == "SUCCEEDED"
        ),
        key=lambda item: (item.attempt_number, item.created_at, item.id),
        reverse=True,
    )
    succeeded_ledgers = sorted(
        (
            item
            for item in ledgers
            if item.status == "SUCCEEDED"
        ),
        key=lambda item: (item.attempt_number, item.created_at, item.id),
        reverse=True,
    )
    ordered_verifications = sorted(
        (
            item
            for item in successful_verifications
            if item.status == "SUCCEEDED" and item.verification_result in {"VALID", "INVALID"}
        ),
        key=lambda item: (item.attempt_number, item.created_at, item.id),
        reverse=True,
    )

    manifests_by_id = {item.id: item for item in succeeded_manifests}
    ledgers_by_id = {item.id: item for item in succeeded_ledgers}
    ledgers_by_sha: dict[str, RedactionEvidenceLedgerRecord] = {}
    for ledger in succeeded_ledgers:
        if not isinstance(ledger.ledger_sha256, str):
            continue
        ledger_sha = ledger.ledger_sha256.strip()
        if not ledger_sha or ledger_sha in ledgers_by_sha:
            continue
        ledgers_by_sha[ledger_sha] = ledger

    ready_manifest = (
        manifests_by_id.get(existing_ready_manifest_id)
        if isinstance(existing_ready_manifest_id, str)
        else None
    )
    ready_ledger = (
        ledgers_by_id.get(existing_ready_ledger_id)
        if isinstance(existing_ready_ledger_id, str)
        else None
    )

    for verification in ordered_verifications:
        if verification.verification_result != "VALID":
            continue
        ledger_sha = _verification_ledger_sha(verification)
        if ledger_sha is None:
            continue
        promoted_ledger = ledgers_by_sha.get(ledger_sha)
        if promoted_ledger is None:
            continue
        promoted_manifest = next(
            (
                manifest
                for manifest in succeeded_manifests
                if manifest.source_review_snapshot_sha256
                == promoted_ledger.source_review_snapshot_sha256
            ),
            None,
        )
        if promoted_manifest is None:
            continue
        ready_manifest = promoted_manifest
        ready_ledger = promoted_ledger
        break

    if ready_manifest is None or ready_ledger is None:
        return GovernanceReadyPairResolution(
            ready_manifest=None,
            ready_ledger=None,
            ledger_verification_status="PENDING",
            ledger_verified_at=None,
        )

    for verification in ordered_verifications:
        if not _verification_targets_ledger_sha(
            verification=verification,
            ledger_sha256=ready_ledger.ledger_sha256 or "",
        ):
            continue
        if verification.verification_result == "VALID":
            return GovernanceReadyPairResolution(
                ready_manifest=ready_manifest,
                ready_ledger=ready_ledger,
                ledger_verification_status="VALID",
                ledger_verified_at=verification.finished_at,
            )
        return GovernanceReadyPairResolution(
            ready_manifest=ready_manifest,
            ready_ledger=ready_ledger,
            ledger_verification_status="INVALID",
            ledger_verified_at=verification.finished_at,
        )

    return GovernanceReadyPairResolution(
        ready_manifest=ready_manifest,
        ready_ledger=ready_ledger,
        ledger_verification_status="PENDING",
        ledger_verified_at=None,
    )


GOVERNANCE_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS redaction_manifests (
      id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL REFERENCES redaction_runs(id) ON DELETE CASCADE,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      source_review_snapshot_key TEXT NOT NULL,
      source_review_snapshot_sha256 TEXT NOT NULL,
      attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
      supersedes_manifest_id TEXT REFERENCES redaction_manifests(id),
      superseded_by_manifest_id TEXT REFERENCES redaction_manifests(id),
      status TEXT NOT NULL CHECK (
        status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED')
      ),
      manifest_key TEXT,
      manifest_sha256 TEXT,
      format_version INTEGER NOT NULL DEFAULT 1 CHECK (format_version >= 1),
      started_at TIMESTAMPTZ,
      finished_at TIMESTAMPTZ,
      canceled_by TEXT REFERENCES users(id),
      canceled_at TIMESTAMPTZ,
      failure_reason TEXT,
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE (run_id, attempt_number)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_redaction_manifests_scope
      ON redaction_manifests(project_id, document_id, run_id, attempt_number DESC, created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS redaction_evidence_ledgers (
      id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL REFERENCES redaction_runs(id) ON DELETE CASCADE,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      source_review_snapshot_key TEXT NOT NULL,
      source_review_snapshot_sha256 TEXT NOT NULL,
      attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
      supersedes_ledger_id TEXT REFERENCES redaction_evidence_ledgers(id),
      superseded_by_ledger_id TEXT REFERENCES redaction_evidence_ledgers(id),
      status TEXT NOT NULL CHECK (
        status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED')
      ),
      ledger_key TEXT,
      ledger_sha256 TEXT,
      hash_chain_version TEXT NOT NULL DEFAULT 'v1',
      started_at TIMESTAMPTZ,
      finished_at TIMESTAMPTZ,
      canceled_by TEXT REFERENCES users(id),
      canceled_at TIMESTAMPTZ,
      failure_reason TEXT,
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE (run_id, attempt_number)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_redaction_evidence_ledgers_scope
      ON redaction_evidence_ledgers(project_id, document_id, run_id, attempt_number DESC, created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS ledger_verification_runs (
      id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL REFERENCES redaction_runs(id) ON DELETE CASCADE,
      attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
      supersedes_verification_run_id TEXT REFERENCES ledger_verification_runs(id),
      superseded_by_verification_run_id TEXT REFERENCES ledger_verification_runs(id),
      status TEXT NOT NULL CHECK (
        status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED')
      ),
      verification_result TEXT CHECK (
        verification_result IS NULL OR verification_result IN ('VALID', 'INVALID')
      ),
      result_json JSONB,
      started_at TIMESTAMPTZ,
      finished_at TIMESTAMPTZ,
      canceled_by TEXT REFERENCES users(id),
      canceled_at TIMESTAMPTZ,
      failure_reason TEXT,
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE (run_id, attempt_number)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_ledger_verification_runs_scope
      ON ledger_verification_runs(run_id, attempt_number DESC, created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS governance_readiness_projections (
      run_id TEXT PRIMARY KEY REFERENCES redaction_runs(id) ON DELETE CASCADE,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      status TEXT NOT NULL CHECK (status IN ('PENDING', 'READY', 'FAILED')),
      generation_status TEXT NOT NULL CHECK (
        generation_status IN ('IDLE', 'RUNNING', 'FAILED', 'CANCELED')
      ),
      manifest_id TEXT REFERENCES redaction_manifests(id),
      ledger_id TEXT REFERENCES redaction_evidence_ledgers(id),
      last_ledger_verification_run_id TEXT REFERENCES ledger_verification_runs(id),
      last_manifest_sha256 TEXT,
      last_ledger_sha256 TEXT,
      ledger_verification_status TEXT NOT NULL CHECK (
        ledger_verification_status IN ('PENDING', 'VALID', 'INVALID')
      ),
      ledger_verified_at TIMESTAMPTZ,
      ready_at TIMESTAMPTZ,
      last_error_code TEXT,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_governance_readiness_scope
      ON governance_readiness_projections(project_id, document_id, status, updated_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS governance_run_events (
      id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL REFERENCES redaction_runs(id) ON DELETE CASCADE,
      event_type TEXT NOT NULL CHECK (
        event_type IN (
          'RUN_CREATED',
          'MANIFEST_STARTED',
          'MANIFEST_SUCCEEDED',
          'MANIFEST_FAILED',
          'MANIFEST_CANCELED',
          'LEDGER_STARTED',
          'LEDGER_SUCCEEDED',
          'LEDGER_FAILED',
          'LEDGER_CANCELED',
          'LEDGER_VERIFY_STARTED',
          'LEDGER_VERIFIED_VALID',
          'LEDGER_VERIFIED_INVALID',
          'LEDGER_VERIFY_CANCELED',
          'REGENERATE_REQUESTED',
          'RUN_CANCELED',
          'READY_SET',
          'READY_FAILED'
        )
      ),
      actor_user_id TEXT REFERENCES users(id),
      from_status TEXT,
      to_status TEXT,
      reason TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_governance_run_events_scope
      ON governance_run_events(run_id, created_at ASC, id ASC)
    """,
    """
    CREATE TABLE IF NOT EXISTS export_candidate_snapshots (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      source_phase TEXT NOT NULL CHECK (source_phase IN ('PHASE6', 'PHASE7', 'PHASE9', 'PHASE10')),
      source_artifact_kind TEXT NOT NULL CHECK (
        source_artifact_kind IN ('REDACTION_RUN_OUTPUT', 'DEPOSIT_BUNDLE', 'DERIVATIVE_SNAPSHOT')
      ),
      source_run_id TEXT REFERENCES redaction_runs(id),
      source_artifact_id TEXT NOT NULL,
      governance_run_id TEXT REFERENCES redaction_runs(id),
      governance_manifest_id TEXT REFERENCES redaction_manifests(id),
      governance_ledger_id TEXT REFERENCES redaction_evidence_ledgers(id),
      governance_manifest_sha256 TEXT,
      governance_ledger_sha256 TEXT,
      policy_snapshot_hash TEXT,
      policy_id TEXT,
      policy_family_id TEXT,
      policy_version TEXT,
      candidate_kind TEXT NOT NULL CHECK (
        candidate_kind IN ('SAFEGUARDED_PREVIEW', 'POLICY_RERUN', 'DEPOSIT_BUNDLE', 'SAFEGUARDED_DERIVATIVE')
      ),
      artefact_manifest_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      candidate_sha256 TEXT NOT NULL,
      eligibility_status TEXT NOT NULL CHECK (
        eligibility_status IN ('ELIGIBLE', 'SUPERSEDED')
      ),
      supersedes_candidate_snapshot_id TEXT REFERENCES export_candidate_snapshots(id),
      superseded_by_candidate_snapshot_id TEXT REFERENCES export_candidate_snapshots(id),
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_export_candidate_snapshots_scope
      ON export_candidate_snapshots(project_id, created_at DESC, id DESC)
    """,
)


class GovernanceStoreUnavailableError(RuntimeError):
    """Governance persistence could not be reached."""


class GovernanceRunNotFoundError(RuntimeError):
    """Governance run was not found in project scope."""


class GovernanceRunConflictError(RuntimeError):
    """Governance run mutation violated a lifecycle constraint."""


class GovernanceStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._schema_initialized = False

    @staticmethod
    def _as_conninfo(database_url: str) -> str:
        if database_url.startswith("postgresql+psycopg://"):
            return database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        return database_url

    def _connect(self) -> psycopg.Connection:
        conninfo = self._as_conninfo(self._settings.database_url)
        return psycopg.connect(conninfo=conninfo, connect_timeout=2)

    def ensure_schema(self) -> None:
        if self._schema_initialized:
            return

        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    for statement in GOVERNANCE_SCHEMA_STATEMENTS:
                        cursor.execute(statement)
                connection.commit()
        except psycopg.Error as error:
            raise GovernanceStoreUnavailableError(
                "Governance schema could not be initialized."
            ) from error

        self._schema_initialized = True

    @staticmethod
    def _assert_artifact_status(value: str) -> GovernanceArtifactStatus:
        if value not in {"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"}:
            raise GovernanceStoreUnavailableError("Unexpected governance artifact status persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_readiness_status(value: str) -> GovernanceReadinessStatus:
        if value not in {"PENDING", "READY", "FAILED"}:
            raise GovernanceStoreUnavailableError("Unexpected governance readiness status persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_generation_status(value: str) -> GovernanceGenerationStatus:
        if value not in {"IDLE", "RUNNING", "FAILED", "CANCELED"}:
            raise GovernanceStoreUnavailableError("Unexpected governance generation status persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_ledger_verification_status(
        value: str,
    ) -> GovernanceLedgerVerificationStatus:
        if value not in {"PENDING", "VALID", "INVALID"}:
            raise GovernanceStoreUnavailableError(
                "Unexpected governance ledger verification status persisted."
            )
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_event_type(value: str) -> GovernanceRunEventType:
        if value not in {
            "RUN_CREATED",
            "MANIFEST_STARTED",
            "MANIFEST_SUCCEEDED",
            "MANIFEST_FAILED",
            "MANIFEST_CANCELED",
            "LEDGER_STARTED",
            "LEDGER_SUCCEEDED",
            "LEDGER_FAILED",
            "LEDGER_CANCELED",
            "LEDGER_VERIFY_STARTED",
            "LEDGER_VERIFIED_VALID",
            "LEDGER_VERIFIED_INVALID",
            "LEDGER_VERIFY_CANCELED",
            "REGENERATE_REQUESTED",
            "RUN_CANCELED",
            "READY_SET",
            "READY_FAILED",
        }:
            raise GovernanceStoreUnavailableError("Unexpected governance event type persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_candidate_source_phase(value: str) -> ExportCandidateSourcePhase:
        if value not in {"PHASE6", "PHASE7", "PHASE9", "PHASE10"}:
            raise GovernanceStoreUnavailableError("Unexpected candidate source phase persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_candidate_source_artifact_kind(
        value: str,
    ) -> ExportCandidateSourceArtifactKind:
        if value not in {"REDACTION_RUN_OUTPUT", "DEPOSIT_BUNDLE", "DERIVATIVE_SNAPSHOT"}:
            raise GovernanceStoreUnavailableError(
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
            raise GovernanceStoreUnavailableError("Unexpected candidate kind persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_candidate_eligibility_status(value: str) -> ExportCandidateEligibilityStatus:
        if value not in {"ELIGIBLE", "SUPERSEDED"}:
            raise GovernanceStoreUnavailableError("Unexpected candidate eligibility status persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_verification_result(
        value: str | None,
    ) -> GovernanceLedgerVerificationResult | None:
        if value is None:
            return None
        if value not in {"VALID", "INVALID"}:
            raise GovernanceStoreUnavailableError(
                "Unexpected ledger verification result persisted."
            )
        return value  # type: ignore[return-value]

    @classmethod
    def _as_manifest_record(cls, row: dict[str, object]) -> RedactionManifestRecord:
        return RedactionManifestRecord(
            id=str(row["id"]),
            run_id=str(row["run_id"]),
            project_id=str(row["project_id"]),
            document_id=str(row["document_id"]),
            source_review_snapshot_key=str(row["source_review_snapshot_key"]),
            source_review_snapshot_sha256=str(row["source_review_snapshot_sha256"]),
            attempt_number=int(row["attempt_number"]),
            supersedes_manifest_id=(
                str(row["supersedes_manifest_id"])
                if isinstance(row.get("supersedes_manifest_id"), str)
                else None
            ),
            superseded_by_manifest_id=(
                str(row["superseded_by_manifest_id"])
                if isinstance(row.get("superseded_by_manifest_id"), str)
                else None
            ),
            status=cls._assert_artifact_status(str(row["status"])),
            manifest_key=(
                str(row["manifest_key"]) if isinstance(row.get("manifest_key"), str) else None
            ),
            manifest_sha256=(
                str(row["manifest_sha256"])
                if isinstance(row.get("manifest_sha256"), str)
                else None
            ),
            format_version=int(row.get("format_version") or 1),
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
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_ledger_record(cls, row: dict[str, object]) -> RedactionEvidenceLedgerRecord:
        return RedactionEvidenceLedgerRecord(
            id=str(row["id"]),
            run_id=str(row["run_id"]),
            project_id=str(row["project_id"]),
            document_id=str(row["document_id"]),
            source_review_snapshot_key=str(row["source_review_snapshot_key"]),
            source_review_snapshot_sha256=str(row["source_review_snapshot_sha256"]),
            attempt_number=int(row["attempt_number"]),
            supersedes_ledger_id=(
                str(row["supersedes_ledger_id"])
                if isinstance(row.get("supersedes_ledger_id"), str)
                else None
            ),
            superseded_by_ledger_id=(
                str(row["superseded_by_ledger_id"])
                if isinstance(row.get("superseded_by_ledger_id"), str)
                else None
            ),
            status=cls._assert_artifact_status(str(row["status"])),
            ledger_key=(
                str(row["ledger_key"]) if isinstance(row.get("ledger_key"), str) else None
            ),
            ledger_sha256=(
                str(row["ledger_sha256"])
                if isinstance(row.get("ledger_sha256"), str)
                else None
            ),
            hash_chain_version=str(row.get("hash_chain_version") or "v1"),
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
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_readiness_record(
        cls,
        row: dict[str, object],
    ) -> GovernanceReadinessProjectionRecord:
        return GovernanceReadinessProjectionRecord(
            run_id=str(row["run_id"]),
            project_id=str(row["project_id"]),
            document_id=str(row["document_id"]),
            status=cls._assert_readiness_status(str(row["status"])),
            generation_status=cls._assert_generation_status(str(row["generation_status"])),
            manifest_id=(
                str(row["manifest_id"]) if isinstance(row.get("manifest_id"), str) else None
            ),
            ledger_id=(str(row["ledger_id"]) if isinstance(row.get("ledger_id"), str) else None),
            last_ledger_verification_run_id=(
                str(row["last_ledger_verification_run_id"])
                if isinstance(row.get("last_ledger_verification_run_id"), str)
                else None
            ),
            last_manifest_sha256=(
                str(row["last_manifest_sha256"])
                if isinstance(row.get("last_manifest_sha256"), str)
                else None
            ),
            last_ledger_sha256=(
                str(row["last_ledger_sha256"])
                if isinstance(row.get("last_ledger_sha256"), str)
                else None
            ),
            ledger_verification_status=cls._assert_ledger_verification_status(
                str(row["ledger_verification_status"])
            ),
            ledger_verified_at=row.get("ledger_verified_at"),  # type: ignore[arg-type]
            ready_at=row.get("ready_at"),  # type: ignore[arg-type]
            last_error_code=(
                str(row["last_error_code"])
                if isinstance(row.get("last_error_code"), str)
                else None
            ),
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_run_event_record(cls, row: dict[str, object]) -> GovernanceRunEventRecord:
        return GovernanceRunEventRecord(
            id=str(row["id"]),
            run_id=str(row["run_id"]),
            event_type=cls._assert_event_type(str(row["event_type"])),
            actor_user_id=(
                str(row["actor_user_id"])
                if isinstance(row.get("actor_user_id"), str)
                else None
            ),
            from_status=(
                str(row["from_status"]) if isinstance(row.get("from_status"), str) else None
            ),
            to_status=(str(row["to_status"]) if isinstance(row.get("to_status"), str) else None),
            reason=str(row["reason"]) if isinstance(row.get("reason"), str) else None,
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_verification_record(cls, row: dict[str, object]) -> LedgerVerificationRunRecord:
        return LedgerVerificationRunRecord(
            id=str(row["id"]),
            run_id=str(row["run_id"]),
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
            status=cls._assert_artifact_status(str(row["status"])),
            verification_result=cls._assert_verification_result(
                str(row["verification_result"])
                if isinstance(row.get("verification_result"), str)
                else None
            ),
            result_json=(
                dict(row["result_json"]) if isinstance(row.get("result_json"), dict) else None
            ),
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
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_run_summary_record(cls, row: dict[str, object]) -> GovernanceRunSummaryRecord:
        return GovernanceRunSummaryRecord(
            run_id=str(row["run_id"]),
            project_id=str(row["project_id"]),
            document_id=str(row["document_id"]),
            run_status=str(row["run_status"]),
            review_status=(
                str(row["review_status"]) if isinstance(row.get("review_status"), str) else None
            ),
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
            run_output_status=(
                str(row["run_output_status"])
                if isinstance(row.get("run_output_status"), str)
                else None
            ),
            run_output_manifest_sha256=(
                str(row["run_output_manifest_sha256"])
                if isinstance(row.get("run_output_manifest_sha256"), str)
                else None
            ),
            run_created_at=row["run_created_at"],  # type: ignore[arg-type]
            run_finished_at=row.get("run_finished_at"),  # type: ignore[arg-type]
            readiness_status=cls._assert_readiness_status(
                str(row.get("readiness_status") or "PENDING")
            ),
            generation_status=cls._assert_generation_status(
                str(row.get("generation_status") or "IDLE")
            ),
            ready_manifest_id=(
                str(row["ready_manifest_id"])
                if isinstance(row.get("ready_manifest_id"), str)
                else None
            ),
            ready_ledger_id=(
                str(row["ready_ledger_id"])
                if isinstance(row.get("ready_ledger_id"), str)
                else None
            ),
            latest_manifest_sha256=(
                str(row["latest_manifest_sha256"])
                if isinstance(row.get("latest_manifest_sha256"), str)
                else None
            ),
            latest_ledger_sha256=(
                str(row["latest_ledger_sha256"])
                if isinstance(row.get("latest_ledger_sha256"), str)
                else None
            ),
            ledger_verification_status=cls._assert_ledger_verification_status(
                str(row.get("ledger_verification_status") or "PENDING")
            ),
            ready_at=row.get("ready_at"),  # type: ignore[arg-type]
            last_error_code=(
                str(row["last_error_code"])
                if isinstance(row.get("last_error_code"), str)
                else None
            ),
            updated_at=row.get("updated_at")  # type: ignore[arg-type]
            if isinstance(row.get("updated_at"), datetime)
            else datetime.now(timezone.utc),
        )

    @classmethod
    def _as_candidate_contract_record(
        cls,
        row: dict[str, object],
    ) -> ExportCandidateSnapshotContractRecord:
        return ExportCandidateSnapshotContractRecord(
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

    @staticmethod
    def _compute_generation_status(
        *,
        latest_manifest: RedactionManifestRecord | None,
        latest_ledger: RedactionEvidenceLedgerRecord | None,
    ) -> GovernanceGenerationStatus:
        latest_statuses: list[GovernanceArtifactStatus] = []
        if latest_manifest is not None:
            latest_statuses.append(latest_manifest.status)
        if latest_ledger is not None:
            latest_statuses.append(latest_ledger.status)
        if any(status in {"QUEUED", "RUNNING"} for status in latest_statuses):
            return "RUNNING"
        if any(status == "FAILED" for status in latest_statuses):
            return "FAILED"
        if any(status == "CANCELED" for status in latest_statuses):
            return "CANCELED"
        return "IDLE"

    @staticmethod
    def _compute_failure_code(
        *,
        latest_manifest: RedactionManifestRecord | None,
        latest_ledger: RedactionEvidenceLedgerRecord | None,
        generation_status: GovernanceGenerationStatus,
    ) -> str | None:
        if generation_status != "FAILED":
            return None
        if latest_ledger is not None and latest_ledger.status == "FAILED":
            return "LEDGER_FAILED"
        if latest_manifest is not None and latest_manifest.status == "FAILED":
            return "MANIFEST_FAILED"
        return "GENERATION_FAILED"

    @staticmethod
    def _compute_readiness_status(
        *,
        ready_manifest: RedactionManifestRecord | None,
        ready_ledger: RedactionEvidenceLedgerRecord | None,
        ledger_verification_status: GovernanceLedgerVerificationStatus,
        generation_status: GovernanceGenerationStatus,
    ) -> GovernanceReadinessStatus:
        if (
            ready_manifest is not None
            and ready_ledger is not None
            and ledger_verification_status == "VALID"
        ):
            return "READY"
        if generation_status == "FAILED":
            return "FAILED"
        return "PENDING"

    def _append_event_if_missing(
        self,
        *,
        cursor: psycopg.Cursor,
        run_id: str,
        event_type: GovernanceRunEventType,
        actor_user_id: str | None,
        from_status: str | None = None,
        to_status: str | None = None,
        reason: str | None = None,
    ) -> None:
        cursor.execute(
            """
            SELECT id
            FROM governance_run_events
            WHERE run_id = %(run_id)s
              AND event_type = %(event_type)s
            LIMIT 1
            """,
            {"run_id": run_id, "event_type": event_type},
        )
        if cursor.fetchone() is not None:
            return
        cursor.execute(
            """
            INSERT INTO governance_run_events (
              id,
              run_id,
              event_type,
              actor_user_id,
              from_status,
              to_status,
              reason,
              created_at
            )
            VALUES (
              %(id)s,
              %(run_id)s,
              %(event_type)s,
              %(actor_user_id)s,
              %(from_status)s,
              %(to_status)s,
              %(reason)s,
              NOW()
            )
            """,
            {
                "id": str(uuid4()),
                "run_id": run_id,
                "event_type": event_type,
                "actor_user_id": actor_user_id,
                "from_status": from_status,
                "to_status": to_status,
                "reason": reason,
            },
        )

    def _append_event(
        self,
        *,
        cursor: psycopg.Cursor,
        run_id: str,
        event_type: GovernanceRunEventType,
        actor_user_id: str | None,
        from_status: str | None = None,
        to_status: str | None = None,
        reason: str | None = None,
    ) -> None:
        cursor.execute(
            """
            INSERT INTO governance_run_events (
              id,
              run_id,
              event_type,
              actor_user_id,
              from_status,
              to_status,
              reason,
              created_at
            )
            VALUES (
              %(id)s,
              %(run_id)s,
              %(event_type)s,
              %(actor_user_id)s,
              %(from_status)s,
              %(to_status)s,
              %(reason)s,
              NOW()
            )
            """,
            {
                "id": str(uuid4()),
                "run_id": run_id,
                "event_type": event_type,
                "actor_user_id": actor_user_id,
                "from_status": from_status,
                "to_status": to_status,
                "reason": reason,
            },
        )

    def _load_latest_manifest(
        self, *, cursor: psycopg.Cursor, run_id: str
    ) -> RedactionManifestRecord | None:
        cursor.execute(
            """
            SELECT
              id,
              run_id,
              project_id,
              document_id,
              source_review_snapshot_key,
              source_review_snapshot_sha256,
              attempt_number,
              supersedes_manifest_id,
              superseded_by_manifest_id,
              status,
              manifest_key,
              manifest_sha256,
              format_version,
              started_at,
              finished_at,
              canceled_by,
              canceled_at,
              failure_reason,
              created_by,
              created_at
            FROM redaction_manifests
            WHERE run_id = %(run_id)s
            ORDER BY attempt_number DESC, created_at DESC, id DESC
            LIMIT 1
            """,
            {"run_id": run_id},
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._as_manifest_record(row)

    def _load_latest_ledger(
        self, *, cursor: psycopg.Cursor, run_id: str
    ) -> RedactionEvidenceLedgerRecord | None:
        cursor.execute(
            """
            SELECT
              id,
              run_id,
              project_id,
              document_id,
              source_review_snapshot_key,
              source_review_snapshot_sha256,
              attempt_number,
              supersedes_ledger_id,
              superseded_by_ledger_id,
              status,
              ledger_key,
              ledger_sha256,
              hash_chain_version,
              started_at,
              finished_at,
              canceled_by,
              canceled_at,
              failure_reason,
              created_by,
              created_at
            FROM redaction_evidence_ledgers
            WHERE run_id = %(run_id)s
            ORDER BY attempt_number DESC, created_at DESC, id DESC
            LIMIT 1
            """,
            {"run_id": run_id},
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._as_ledger_record(row)

    def _load_latest_ready_manifest(
        self, *, cursor: psycopg.Cursor, run_id: str
    ) -> RedactionManifestRecord | None:
        cursor.execute(
            """
            SELECT
              id,
              run_id,
              project_id,
              document_id,
              source_review_snapshot_key,
              source_review_snapshot_sha256,
              attempt_number,
              supersedes_manifest_id,
              superseded_by_manifest_id,
              status,
              manifest_key,
              manifest_sha256,
              format_version,
              started_at,
              finished_at,
              canceled_by,
              canceled_at,
              failure_reason,
              created_by,
              created_at
            FROM redaction_manifests
            WHERE run_id = %(run_id)s
              AND status = 'SUCCEEDED'
            ORDER BY attempt_number DESC, created_at DESC, id DESC
            LIMIT 1
            """,
            {"run_id": run_id},
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._as_manifest_record(row)

    def _load_latest_ready_ledger(
        self, *, cursor: psycopg.Cursor, run_id: str
    ) -> RedactionEvidenceLedgerRecord | None:
        cursor.execute(
            """
            SELECT
              id,
              run_id,
              project_id,
              document_id,
              source_review_snapshot_key,
              source_review_snapshot_sha256,
              attempt_number,
              supersedes_ledger_id,
              superseded_by_ledger_id,
              status,
              ledger_key,
              ledger_sha256,
              hash_chain_version,
              started_at,
              finished_at,
              canceled_by,
              canceled_at,
              failure_reason,
              created_by,
              created_at
            FROM redaction_evidence_ledgers
            WHERE run_id = %(run_id)s
              AND status = 'SUCCEEDED'
            ORDER BY attempt_number DESC, created_at DESC, id DESC
            LIMIT 1
            """,
            {"run_id": run_id},
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._as_ledger_record(row)

    def _load_manifest_by_id(
        self, *, cursor: psycopg.Cursor, run_id: str, manifest_id: str
    ) -> RedactionManifestRecord | None:
        cursor.execute(
            """
            SELECT
              id,
              run_id,
              project_id,
              document_id,
              source_review_snapshot_key,
              source_review_snapshot_sha256,
              attempt_number,
              supersedes_manifest_id,
              superseded_by_manifest_id,
              status,
              manifest_key,
              manifest_sha256,
              format_version,
              started_at,
              finished_at,
              canceled_by,
              canceled_at,
              failure_reason,
              created_by,
              created_at
            FROM redaction_manifests
            WHERE run_id = %(run_id)s
              AND id = %(manifest_id)s
            LIMIT 1
            """,
            {"run_id": run_id, "manifest_id": manifest_id},
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._as_manifest_record(row)

    def _load_ledger_by_id(
        self, *, cursor: psycopg.Cursor, run_id: str, ledger_id: str
    ) -> RedactionEvidenceLedgerRecord | None:
        cursor.execute(
            """
            SELECT
              id,
              run_id,
              project_id,
              document_id,
              source_review_snapshot_key,
              source_review_snapshot_sha256,
              attempt_number,
              supersedes_ledger_id,
              superseded_by_ledger_id,
              status,
              ledger_key,
              ledger_sha256,
              hash_chain_version,
              started_at,
              finished_at,
              canceled_by,
              canceled_at,
              failure_reason,
              created_by,
              created_at
            FROM redaction_evidence_ledgers
            WHERE run_id = %(run_id)s
              AND id = %(ledger_id)s
            LIMIT 1
            """,
            {"run_id": run_id, "ledger_id": ledger_id},
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._as_ledger_record(row)

    def _load_succeeded_ledger_by_sha(
        self, *, cursor: psycopg.Cursor, run_id: str, ledger_sha256: str
    ) -> RedactionEvidenceLedgerRecord | None:
        cursor.execute(
            """
            SELECT
              id,
              run_id,
              project_id,
              document_id,
              source_review_snapshot_key,
              source_review_snapshot_sha256,
              attempt_number,
              supersedes_ledger_id,
              superseded_by_ledger_id,
              status,
              ledger_key,
              ledger_sha256,
              hash_chain_version,
              started_at,
              finished_at,
              canceled_by,
              canceled_at,
              failure_reason,
              created_by,
              created_at
            FROM redaction_evidence_ledgers
            WHERE run_id = %(run_id)s
              AND status = 'SUCCEEDED'
              AND ledger_sha256 = %(ledger_sha256)s
            ORDER BY attempt_number DESC, created_at DESC, id DESC
            LIMIT 1
            """,
            {"run_id": run_id, "ledger_sha256": ledger_sha256},
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._as_ledger_record(row)

    def _load_latest_succeeded_manifest_for_snapshot(
        self, *, cursor: psycopg.Cursor, run_id: str, snapshot_sha256: str
    ) -> RedactionManifestRecord | None:
        cursor.execute(
            """
            SELECT
              id,
              run_id,
              project_id,
              document_id,
              source_review_snapshot_key,
              source_review_snapshot_sha256,
              attempt_number,
              supersedes_manifest_id,
              superseded_by_manifest_id,
              status,
              manifest_key,
              manifest_sha256,
              format_version,
              started_at,
              finished_at,
              canceled_by,
              canceled_at,
              failure_reason,
              created_by,
              created_at
            FROM redaction_manifests
            WHERE run_id = %(run_id)s
              AND status = 'SUCCEEDED'
              AND source_review_snapshot_sha256 = %(snapshot_sha256)s
            ORDER BY attempt_number DESC, created_at DESC, id DESC
            LIMIT 1
            """,
            {"run_id": run_id, "snapshot_sha256": snapshot_sha256},
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._as_manifest_record(row)

    def _load_latest_successful_verification_for_ledger(
        self, *, cursor: psycopg.Cursor, run_id: str, ledger_sha256: str
    ) -> LedgerVerificationRunRecord | None:
        cursor.execute(
            """
            SELECT
              id,
              run_id,
              attempt_number,
              supersedes_verification_run_id,
              superseded_by_verification_run_id,
              status,
              verification_result,
              result_json,
              started_at,
              finished_at,
              canceled_by,
              canceled_at,
              failure_reason,
              created_by,
              created_at
            FROM ledger_verification_runs
            WHERE run_id = %(run_id)s
              AND status = 'SUCCEEDED'
              AND result_json ->> 'ledgerSha256' = %(ledger_sha256)s
            ORDER BY attempt_number DESC, created_at DESC, id DESC
            LIMIT 1
            """,
            {"run_id": run_id, "ledger_sha256": ledger_sha256},
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._as_verification_record(row)

    def _load_succeeded_manifests(
        self, *, cursor: psycopg.Cursor, run_id: str
    ) -> list[RedactionManifestRecord]:
        cursor.execute(
            """
            SELECT
              id,
              run_id,
              project_id,
              document_id,
              source_review_snapshot_key,
              source_review_snapshot_sha256,
              attempt_number,
              supersedes_manifest_id,
              superseded_by_manifest_id,
              status,
              manifest_key,
              manifest_sha256,
              format_version,
              started_at,
              finished_at,
              canceled_by,
              canceled_at,
              failure_reason,
              created_by,
              created_at
            FROM redaction_manifests
            WHERE run_id = %(run_id)s
              AND status = 'SUCCEEDED'
            ORDER BY attempt_number DESC, created_at DESC, id DESC
            """,
            {"run_id": run_id},
        )
        rows = cursor.fetchall()
        return [self._as_manifest_record(row) for row in rows]

    def _load_succeeded_ledgers(
        self, *, cursor: psycopg.Cursor, run_id: str
    ) -> list[RedactionEvidenceLedgerRecord]:
        cursor.execute(
            """
            SELECT
              id,
              run_id,
              project_id,
              document_id,
              source_review_snapshot_key,
              source_review_snapshot_sha256,
              attempt_number,
              supersedes_ledger_id,
              superseded_by_ledger_id,
              status,
              ledger_key,
              ledger_sha256,
              hash_chain_version,
              started_at,
              finished_at,
              canceled_by,
              canceled_at,
              failure_reason,
              created_by,
              created_at
            FROM redaction_evidence_ledgers
            WHERE run_id = %(run_id)s
              AND status = 'SUCCEEDED'
            ORDER BY attempt_number DESC, created_at DESC, id DESC
            """,
            {"run_id": run_id},
        )
        rows = cursor.fetchall()
        return [self._as_ledger_record(row) for row in rows]

    def _load_successful_verification_runs(
        self, *, cursor: psycopg.Cursor, run_id: str
    ) -> list[LedgerVerificationRunRecord]:
        cursor.execute(
            """
            SELECT
              id,
              run_id,
              attempt_number,
              supersedes_verification_run_id,
              superseded_by_verification_run_id,
              status,
              verification_result,
              result_json,
              started_at,
              finished_at,
              canceled_by,
              canceled_at,
              failure_reason,
              created_by,
              created_at
            FROM ledger_verification_runs
            WHERE run_id = %(run_id)s
              AND status = 'SUCCEEDED'
            ORDER BY attempt_number DESC, created_at DESC, id DESC
            """,
            {"run_id": run_id},
        )
        rows = cursor.fetchall()
        return [self._as_verification_record(row) for row in rows]

    def _resolve_ready_pair(
        self,
        *,
        cursor: psycopg.Cursor,
        run_id: str,
        existing_ready_manifest_id: str | None,
        existing_ready_ledger_id: str | None,
        latest_successful_verification: LedgerVerificationRunRecord | None,
    ) -> GovernanceReadyPairResolution:
        manifests = self._load_succeeded_manifests(cursor=cursor, run_id=run_id)
        ledgers = self._load_succeeded_ledgers(cursor=cursor, run_id=run_id)
        successful_verifications = self._load_successful_verification_runs(
            cursor=cursor,
            run_id=run_id,
        )
        if latest_successful_verification is not None and not any(
            item.id == latest_successful_verification.id for item in successful_verifications
        ):
            successful_verifications.insert(0, latest_successful_verification)
        return resolve_governance_ready_pair_from_attempts(
            manifests=manifests,
            ledgers=ledgers,
            successful_verifications=successful_verifications,
            existing_ready_manifest_id=existing_ready_manifest_id,
            existing_ready_ledger_id=existing_ready_ledger_id,
        )

    def _load_latest_verification(
        self, *, cursor: psycopg.Cursor, run_id: str
    ) -> LedgerVerificationRunRecord | None:
        cursor.execute(
            """
            SELECT
              id,
              run_id,
              attempt_number,
              supersedes_verification_run_id,
              superseded_by_verification_run_id,
              status,
              verification_result,
              result_json,
              started_at,
              finished_at,
              canceled_by,
              canceled_at,
              failure_reason,
              created_by,
              created_at
            FROM ledger_verification_runs
            WHERE run_id = %(run_id)s
            ORDER BY attempt_number DESC, created_at DESC, id DESC
            LIMIT 1
            """,
            {"run_id": run_id},
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._as_verification_record(row)

    def _load_latest_successful_verification(
        self, *, cursor: psycopg.Cursor, run_id: str
    ) -> LedgerVerificationRunRecord | None:
        cursor.execute(
            """
            SELECT
              id,
              run_id,
              attempt_number,
              supersedes_verification_run_id,
              superseded_by_verification_run_id,
              status,
              verification_result,
              result_json,
              started_at,
              finished_at,
              canceled_by,
              canceled_at,
              failure_reason,
              created_by,
              created_at
            FROM ledger_verification_runs
            WHERE run_id = %(run_id)s
              AND status = 'SUCCEEDED'
            ORDER BY attempt_number DESC, created_at DESC, id DESC
            LIMIT 1
            """,
            {"run_id": run_id},
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._as_verification_record(row)

    def _sync_governance_scaffold(
        self,
        *,
        cursor: psycopg.Cursor,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> None:
        cursor.execute(
            """
            SELECT
              rr.id AS run_id,
              rr.project_id,
              rr.document_id,
              rr.created_by AS run_created_by,
              rr.status AS run_status,
              rrv.review_status,
              rrv.approved_by,
              rrv.approved_snapshot_key,
              rrv.approved_snapshot_sha256,
              rro.status AS run_output_status,
              rro.output_manifest_key,
              rro.output_manifest_sha256,
              rro.started_at AS run_output_started_at,
              rro.generated_at AS run_output_generated_at
            FROM redaction_runs AS rr
            LEFT JOIN redaction_run_reviews AS rrv
              ON rrv.run_id = rr.id
            LEFT JOIN redaction_run_outputs AS rro
              ON rro.run_id = rr.id
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
            raise GovernanceRunNotFoundError("Governance run not found.")

        review_status = (
            str(run_row["review_status"])
            if isinstance(run_row.get("review_status"), str)
            else None
        )
        approved_snapshot_key = (
            str(run_row["approved_snapshot_key"])
            if isinstance(run_row.get("approved_snapshot_key"), str)
            and str(run_row["approved_snapshot_key"]).strip()
            else None
        )
        approved_snapshot_sha256 = (
            str(run_row["approved_snapshot_sha256"])
            if isinstance(run_row.get("approved_snapshot_sha256"), str)
            and str(run_row["approved_snapshot_sha256"]).strip()
            else None
        )
        run_output_status = (
            str(run_row["run_output_status"])
            if isinstance(run_row.get("run_output_status"), str)
            else None
        )
        run_output_manifest_key = (
            str(run_row["output_manifest_key"])
            if isinstance(run_row.get("output_manifest_key"), str)
            and str(run_row["output_manifest_key"]).strip()
            else None
        )
        run_output_manifest_sha256 = (
            str(run_row["output_manifest_sha256"])
            if isinstance(run_row.get("output_manifest_sha256"), str)
            and str(run_row["output_manifest_sha256"]).strip()
            else None
        )
        actor_user_id = (
            str(run_row["approved_by"])
            if isinstance(run_row.get("approved_by"), str)
            and str(run_row["approved_by"]).strip()
            else str(run_row["run_created_by"])
        )

        self._append_event_if_missing(
            cursor=cursor,
            run_id=run_id,
            event_type="RUN_CREATED",
            actor_user_id=actor_user_id,
            reason="Governance scaffold initialized.",
        )

        latest_manifest = self._load_latest_manifest(cursor=cursor, run_id=run_id)
        if (
            review_status == "APPROVED"
            and approved_snapshot_key is not None
            and approved_snapshot_sha256 is not None
            and run_output_status == "READY"
            and run_output_manifest_key is not None
            and run_output_manifest_sha256 is not None
        ):
            needs_manifest_seed = (
                latest_manifest is None
                or latest_manifest.status != "SUCCEEDED"
                or latest_manifest.manifest_sha256 != run_output_manifest_sha256
            )
            if needs_manifest_seed:
                cursor.execute(
                    """
                    SELECT
                      id,
                      attempt_number
                    FROM redaction_manifests
                    WHERE run_id = %(run_id)s
                    ORDER BY attempt_number DESC, created_at DESC, id DESC
                    LIMIT 1
                    """,
                    {"run_id": run_id},
                )
                previous_manifest = cursor.fetchone()
                previous_manifest_id = (
                    str(previous_manifest["id"])
                    if previous_manifest is not None and isinstance(previous_manifest.get("id"), str)
                    else None
                )
                next_attempt_number = (
                    int(previous_manifest["attempt_number"]) + 1
                    if previous_manifest is not None
                    and isinstance(previous_manifest.get("attempt_number"), int)
                    else 1
                )
                manifest_id = str(uuid4())
                cursor.execute(
                    """
                    INSERT INTO redaction_manifests (
                      id,
                      run_id,
                      project_id,
                      document_id,
                      source_review_snapshot_key,
                      source_review_snapshot_sha256,
                      attempt_number,
                      supersedes_manifest_id,
                      superseded_by_manifest_id,
                      status,
                      manifest_key,
                      manifest_sha256,
                      format_version,
                      started_at,
                      finished_at,
                      canceled_by,
                      canceled_at,
                      failure_reason,
                      created_by,
                      created_at
                    )
                    VALUES (
                      %(id)s,
                      %(run_id)s,
                      %(project_id)s,
                      %(document_id)s,
                      %(source_review_snapshot_key)s,
                      %(source_review_snapshot_sha256)s,
                      %(attempt_number)s,
                      %(supersedes_manifest_id)s,
                      NULL,
                      'SUCCEEDED',
                      %(manifest_key)s,
                      %(manifest_sha256)s,
                      1,
                      %(started_at)s,
                      %(finished_at)s,
                      NULL,
                      NULL,
                      NULL,
                      %(created_by)s,
                      NOW()
                    )
                    """,
                    {
                        "id": manifest_id,
                        "run_id": run_id,
                        "project_id": project_id,
                        "document_id": document_id,
                        "source_review_snapshot_key": approved_snapshot_key,
                        "source_review_snapshot_sha256": approved_snapshot_sha256,
                        "attempt_number": next_attempt_number,
                        "supersedes_manifest_id": previous_manifest_id,
                        "manifest_key": run_output_manifest_key,
                        "manifest_sha256": run_output_manifest_sha256,
                        "started_at": run_row.get("run_output_started_at"),
                        "finished_at": run_row.get("run_output_generated_at"),
                        "created_by": actor_user_id,
                    },
                )
                if previous_manifest_id is not None:
                    cursor.execute(
                        """
                        UPDATE redaction_manifests
                        SET superseded_by_manifest_id = %(new_manifest_id)s
                        WHERE id = %(manifest_id)s
                          AND superseded_by_manifest_id IS NULL
                        """,
                        {
                            "new_manifest_id": manifest_id,
                            "manifest_id": previous_manifest_id,
                        },
                    )
                self._append_event_if_missing(
                    cursor=cursor,
                    run_id=run_id,
                    event_type="MANIFEST_SUCCEEDED",
                    actor_user_id=actor_user_id,
                    from_status="RUNNING",
                    to_status="SUCCEEDED",
                    reason="Manifest attempt seeded from reviewed Phase 5 run output.",
                )
                latest_manifest = self._load_latest_manifest(cursor=cursor, run_id=run_id)

        latest_ledger = self._load_latest_ledger(cursor=cursor, run_id=run_id)
        if (
            review_status == "APPROVED"
            and approved_snapshot_key is not None
            and approved_snapshot_sha256 is not None
            and latest_ledger is None
        ):
            ledger_id = str(uuid4())
            cursor.execute(
                """
                INSERT INTO redaction_evidence_ledgers (
                  id,
                  run_id,
                  project_id,
                  document_id,
                  source_review_snapshot_key,
                  source_review_snapshot_sha256,
                  attempt_number,
                  supersedes_ledger_id,
                  superseded_by_ledger_id,
                  status,
                  ledger_key,
                  ledger_sha256,
                  hash_chain_version,
                  started_at,
                  finished_at,
                  canceled_by,
                  canceled_at,
                  failure_reason,
                  created_by,
                  created_at
                )
                VALUES (
                  %(id)s,
                  %(run_id)s,
                  %(project_id)s,
                  %(document_id)s,
                  %(source_review_snapshot_key)s,
                  %(source_review_snapshot_sha256)s,
                  1,
                  NULL,
                  NULL,
                  'QUEUED',
                  NULL,
                  NULL,
                  'v1',
                  NULL,
                  NULL,
                  NULL,
                  NULL,
                  NULL,
                  %(created_by)s,
                  NOW()
                )
                """,
                {
                    "id": ledger_id,
                    "run_id": run_id,
                    "project_id": project_id,
                    "document_id": document_id,
                    "source_review_snapshot_key": approved_snapshot_key,
                    "source_review_snapshot_sha256": approved_snapshot_sha256,
                    "created_by": actor_user_id,
                },
            )
            self._append_event_if_missing(
                cursor=cursor,
                run_id=run_id,
                event_type="LEDGER_STARTED",
                actor_user_id=actor_user_id,
                from_status="IDLE",
                to_status="QUEUED",
                reason="Ledger attempt scaffolded; content generation remains pending.",
            )
            latest_ledger = self._load_latest_ledger(cursor=cursor, run_id=run_id)

        latest_verification = self._load_latest_verification(cursor=cursor, run_id=run_id)
        latest_successful_verification = self._load_latest_successful_verification(
            cursor=cursor, run_id=run_id
        )

        cursor.execute(
            """
            SELECT
              manifest_id,
              ledger_id,
              status,
              ready_at
            FROM governance_readiness_projections
            WHERE run_id = %(run_id)s
            LIMIT 1
            FOR UPDATE
            """,
            {"run_id": run_id},
        )
        existing_projection = cursor.fetchone()
        existing_ready_manifest_id = (
            str(existing_projection["manifest_id"])
            if existing_projection is not None
            and isinstance(existing_projection.get("manifest_id"), str)
            and str(existing_projection["manifest_id"]).strip()
            else None
        )
        existing_ready_ledger_id = (
            str(existing_projection["ledger_id"])
            if existing_projection is not None
            and isinstance(existing_projection.get("ledger_id"), str)
            and str(existing_projection["ledger_id"]).strip()
            else None
        )
        ready_resolution = self._resolve_ready_pair(
            cursor=cursor,
            run_id=run_id,
            existing_ready_manifest_id=existing_ready_manifest_id,
            existing_ready_ledger_id=existing_ready_ledger_id,
            latest_successful_verification=latest_successful_verification,
        )
        ready_manifest = ready_resolution.ready_manifest
        ready_ledger = ready_resolution.ready_ledger
        ledger_verification_status = ready_resolution.ledger_verification_status
        ledger_verified_at = ready_resolution.ledger_verified_at
        last_ledger_verification_run_id = latest_verification.id if latest_verification is not None else None

        generation_status = self._compute_generation_status(
            latest_manifest=latest_manifest,
            latest_ledger=latest_ledger,
        )
        readiness_status = self._compute_readiness_status(
            ready_manifest=ready_manifest,
            ready_ledger=ready_ledger,
            ledger_verification_status=ledger_verification_status,
            generation_status=generation_status,
        )
        last_error_code = self._compute_failure_code(
            latest_manifest=latest_manifest,
            latest_ledger=latest_ledger,
            generation_status=generation_status,
        )

        previous_status = (
            str(existing_projection["status"])
            if existing_projection is not None and isinstance(existing_projection.get("status"), str)
            else None
        )
        preserved_ready_at = (
            existing_projection.get("ready_at")  # type: ignore[assignment]
            if existing_projection is not None
            else None
        )
        ready_at = (
            preserved_ready_at
            if readiness_status == "READY" and isinstance(preserved_ready_at, datetime)
            else datetime.now(timezone.utc)
            if readiness_status == "READY"
            else None
        )

        cursor.execute(
            """
            INSERT INTO governance_readiness_projections (
              run_id,
              project_id,
              document_id,
              status,
              generation_status,
              manifest_id,
              ledger_id,
              last_ledger_verification_run_id,
              last_manifest_sha256,
              last_ledger_sha256,
              ledger_verification_status,
              ledger_verified_at,
              ready_at,
              last_error_code,
              updated_at
            )
            VALUES (
              %(run_id)s,
              %(project_id)s,
              %(document_id)s,
              %(status)s,
              %(generation_status)s,
              %(manifest_id)s,
              %(ledger_id)s,
              %(last_ledger_verification_run_id)s,
              %(last_manifest_sha256)s,
              %(last_ledger_sha256)s,
              %(ledger_verification_status)s,
              %(ledger_verified_at)s,
              %(ready_at)s,
              %(last_error_code)s,
              NOW()
            )
            ON CONFLICT (run_id) DO UPDATE
            SET
              project_id = EXCLUDED.project_id,
              document_id = EXCLUDED.document_id,
              status = EXCLUDED.status,
              generation_status = EXCLUDED.generation_status,
              manifest_id = EXCLUDED.manifest_id,
              ledger_id = EXCLUDED.ledger_id,
              last_ledger_verification_run_id = EXCLUDED.last_ledger_verification_run_id,
              last_manifest_sha256 = EXCLUDED.last_manifest_sha256,
              last_ledger_sha256 = EXCLUDED.last_ledger_sha256,
              ledger_verification_status = EXCLUDED.ledger_verification_status,
              ledger_verified_at = EXCLUDED.ledger_verified_at,
              ready_at = EXCLUDED.ready_at,
              last_error_code = EXCLUDED.last_error_code,
              updated_at = NOW()
            """,
            {
                "run_id": run_id,
                "project_id": project_id,
                "document_id": document_id,
                "status": readiness_status,
                "generation_status": generation_status,
                "manifest_id": ready_manifest.id if ready_manifest is not None else None,
                "ledger_id": ready_ledger.id if ready_ledger is not None else None,
                "last_ledger_verification_run_id": last_ledger_verification_run_id,
                "last_manifest_sha256": (
                    ready_manifest.manifest_sha256 if ready_manifest is not None else None
                ),
                "last_ledger_sha256": (
                    ready_ledger.ledger_sha256 if ready_ledger is not None else None
                ),
                "ledger_verification_status": ledger_verification_status,
                "ledger_verified_at": ledger_verified_at,
                "ready_at": ready_at,
                "last_error_code": last_error_code,
            },
        )

        if previous_status != readiness_status and readiness_status == "READY":
            self._append_event_if_missing(
                cursor=cursor,
                run_id=run_id,
                event_type="READY_SET",
                actor_user_id=actor_user_id,
                from_status=previous_status,
                to_status="READY",
                reason="Governance readiness pointer advanced to READY.",
            )
        if previous_status != readiness_status and readiness_status == "FAILED":
            self._append_event_if_missing(
                cursor=cursor,
                run_id=run_id,
                event_type="READY_FAILED",
                actor_user_id=actor_user_id,
                from_status=previous_status,
                to_status="FAILED",
                reason=last_error_code or "Governance generation failed.",
            )

    def _assert_document_exists(
        self,
        *,
        cursor: psycopg.Cursor,
        project_id: str,
        document_id: str,
    ) -> None:
        cursor.execute(
            """
            SELECT id
            FROM documents
            WHERE project_id = %(project_id)s
              AND id = %(document_id)s
            LIMIT 1
            """,
            {"project_id": project_id, "document_id": document_id},
        )
        if cursor.fetchone() is None:
            raise GovernanceRunNotFoundError("Document not found.")

    def _list_document_run_ids(
        self,
        *,
        cursor: psycopg.Cursor,
        project_id: str,
        document_id: str,
    ) -> list[str]:
        cursor.execute(
            """
            SELECT id
            FROM redaction_runs
            WHERE project_id = %(project_id)s
              AND document_id = %(document_id)s
            ORDER BY created_at DESC, id DESC
            """,
            {"project_id": project_id, "document_id": document_id},
        )
        return [str(row["id"]) for row in cursor.fetchall()]

    def list_governance_runs(
        self,
        *,
        project_id: str,
        document_id: str,
    ) -> list[GovernanceRunSummaryRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    self._assert_document_exists(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                    )
                    run_ids = self._list_document_run_ids(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                    )
                    for run_id in run_ids:
                        self._sync_governance_scaffold(
                            cursor=cursor,
                            project_id=project_id,
                            document_id=document_id,
                            run_id=run_id,
                        )
                    cursor.execute(
                        """
                        SELECT
                          rr.id AS run_id,
                          rr.project_id,
                          rr.document_id,
                          rr.status AS run_status,
                          rrv.review_status,
                          rrv.approved_snapshot_key,
                          rrv.approved_snapshot_sha256,
                          rro.status AS run_output_status,
                          rro.output_manifest_sha256 AS run_output_manifest_sha256,
                          rr.created_at AS run_created_at,
                          rr.finished_at AS run_finished_at,
                          COALESCE(grp.status, 'PENDING') AS readiness_status,
                          COALESCE(grp.generation_status, 'IDLE') AS generation_status,
                          grp.manifest_id AS ready_manifest_id,
                          grp.ledger_id AS ready_ledger_id,
                          grp.last_manifest_sha256 AS latest_manifest_sha256,
                          grp.last_ledger_sha256 AS latest_ledger_sha256,
                          COALESCE(grp.ledger_verification_status, 'PENDING') AS ledger_verification_status,
                          grp.ready_at,
                          grp.last_error_code,
                          grp.updated_at
                        FROM redaction_runs AS rr
                        LEFT JOIN redaction_run_reviews AS rrv
                          ON rrv.run_id = rr.id
                        LEFT JOIN redaction_run_outputs AS rro
                          ON rro.run_id = rr.id
                        LEFT JOIN governance_readiness_projections AS grp
                          ON grp.run_id = rr.id
                        WHERE rr.project_id = %(project_id)s
                          AND rr.document_id = %(document_id)s
                        ORDER BY rr.created_at DESC, rr.id DESC
                        """,
                        {"project_id": project_id, "document_id": document_id},
                    )
                    rows = cursor.fetchall()
                connection.commit()
        except GovernanceRunNotFoundError:
            raise
        except psycopg.Error as error:
            raise GovernanceStoreUnavailableError("Governance run listing failed.") from error
        return [self._as_run_summary_record(row) for row in rows]

    def get_governance_run_overview(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> GovernanceRunSummaryRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    self._assert_document_exists(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                    )
                    self._sync_governance_scaffold(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                    )
                    cursor.execute(
                        """
                        SELECT
                          rr.id AS run_id,
                          rr.project_id,
                          rr.document_id,
                          rr.status AS run_status,
                          rrv.review_status,
                          rrv.approved_snapshot_key,
                          rrv.approved_snapshot_sha256,
                          rro.status AS run_output_status,
                          rro.output_manifest_sha256 AS run_output_manifest_sha256,
                          rr.created_at AS run_created_at,
                          rr.finished_at AS run_finished_at,
                          COALESCE(grp.status, 'PENDING') AS readiness_status,
                          COALESCE(grp.generation_status, 'IDLE') AS generation_status,
                          grp.manifest_id AS ready_manifest_id,
                          grp.ledger_id AS ready_ledger_id,
                          grp.last_manifest_sha256 AS latest_manifest_sha256,
                          grp.last_ledger_sha256 AS latest_ledger_sha256,
                          COALESCE(grp.ledger_verification_status, 'PENDING') AS ledger_verification_status,
                          grp.ready_at,
                          grp.last_error_code,
                          grp.updated_at
                        FROM redaction_runs AS rr
                        LEFT JOIN redaction_run_reviews AS rrv
                          ON rrv.run_id = rr.id
                        LEFT JOIN redaction_run_outputs AS rro
                          ON rro.run_id = rr.id
                        LEFT JOIN governance_readiness_projections AS grp
                          ON grp.run_id = rr.id
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
                connection.commit()
        except GovernanceRunNotFoundError:
            raise
        except psycopg.Error as error:
            raise GovernanceStoreUnavailableError("Governance run lookup failed.") from error
        if row is None:
            raise GovernanceRunNotFoundError("Governance run not found.")
        return self._as_run_summary_record(row)

    def get_governance_overview(
        self,
        *,
        project_id: str,
        document_id: str,
    ) -> GovernanceOverviewRecord:
        run_summaries = self.list_governance_runs(project_id=project_id, document_id=document_id)
        total_runs = len(run_summaries)
        approved_runs = sum(1 for item in run_summaries if item.review_status == "APPROVED")
        ready_runs = sum(1 for item in run_summaries if item.readiness_status == "READY")
        failed_runs = sum(1 for item in run_summaries if item.readiness_status == "FAILED")
        pending_runs = max(0, total_runs - ready_runs - failed_runs)
        latest_run_id = run_summaries[0].run_id if run_summaries else None
        latest_ready_run_id = next(
            (item.run_id for item in run_summaries if item.readiness_status == "READY"),
            None,
        )

        active_run_id: str | None = None
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT active_redaction_run_id
                        FROM document_redaction_projections
                        WHERE project_id = %(project_id)s
                          AND document_id = %(document_id)s
                        LIMIT 1
                        """,
                        {"project_id": project_id, "document_id": document_id},
                    )
                    projection_row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise GovernanceStoreUnavailableError("Governance overview lookup failed.") from error
        if (
            projection_row is not None
            and isinstance(projection_row.get("active_redaction_run_id"), str)
        ):
            active_run_id = str(projection_row["active_redaction_run_id"])

        return GovernanceOverviewRecord(
            project_id=project_id,
            document_id=document_id,
            active_run_id=active_run_id,
            total_runs=total_runs,
            approved_runs=approved_runs,
            ready_runs=ready_runs,
            pending_runs=pending_runs,
            failed_runs=failed_runs,
            latest_run_id=latest_run_id,
            latest_ready_run_id=latest_ready_run_id,
        )

    def list_governance_run_events(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> list[GovernanceRunEventRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    self._assert_document_exists(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                    )
                    self._sync_governance_scaffold(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                    )
                    cursor.execute(
                        """
                        SELECT
                          id,
                          run_id,
                          event_type,
                          actor_user_id,
                          from_status,
                          to_status,
                          reason,
                          created_at
                        FROM governance_run_events
                        WHERE run_id = %(run_id)s
                        ORDER BY created_at ASC, id ASC
                        """,
                        {"run_id": run_id},
                    )
                    rows = cursor.fetchall()
                connection.commit()
        except GovernanceRunNotFoundError:
            raise
        except psycopg.Error as error:
            raise GovernanceStoreUnavailableError("Governance event listing failed.") from error
        return [self._as_run_event_record(row) for row in rows]

    def list_manifest_attempts(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> list[RedactionManifestRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    self._assert_document_exists(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                    )
                    self._sync_governance_scaffold(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                    )
                    cursor.execute(
                        """
                        SELECT
                          id,
                          run_id,
                          project_id,
                          document_id,
                          source_review_snapshot_key,
                          source_review_snapshot_sha256,
                          attempt_number,
                          supersedes_manifest_id,
                          superseded_by_manifest_id,
                          status,
                          manifest_key,
                          manifest_sha256,
                          format_version,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          failure_reason,
                          created_by,
                          created_at
                        FROM redaction_manifests
                        WHERE run_id = %(run_id)s
                        ORDER BY attempt_number DESC, created_at DESC, id DESC
                        """,
                        {"run_id": run_id},
                    )
                    rows = cursor.fetchall()
                connection.commit()
        except GovernanceRunNotFoundError:
            raise
        except psycopg.Error as error:
            raise GovernanceStoreUnavailableError("Manifest attempt listing failed.") from error
        return [self._as_manifest_record(row) for row in rows]

    def list_ledger_attempts(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> list[RedactionEvidenceLedgerRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    self._assert_document_exists(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                    )
                    self._sync_governance_scaffold(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                    )
                    cursor.execute(
                        """
                        SELECT
                          id,
                          run_id,
                          project_id,
                          document_id,
                          source_review_snapshot_key,
                          source_review_snapshot_sha256,
                          attempt_number,
                          supersedes_ledger_id,
                          superseded_by_ledger_id,
                          status,
                          ledger_key,
                          ledger_sha256,
                          hash_chain_version,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          failure_reason,
                          created_by,
                          created_at
                        FROM redaction_evidence_ledgers
                        WHERE run_id = %(run_id)s
                        ORDER BY attempt_number DESC, created_at DESC, id DESC
                        """,
                        {"run_id": run_id},
                    )
                    rows = cursor.fetchall()
                connection.commit()
        except GovernanceRunNotFoundError:
            raise
        except psycopg.Error as error:
            raise GovernanceStoreUnavailableError("Ledger attempt listing failed.") from error
        return [self._as_ledger_record(row) for row in rows]

    def get_readiness_projection(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> GovernanceReadinessProjectionRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    self._assert_document_exists(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                    )
                    self._sync_governance_scaffold(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                    )
                    cursor.execute(
                        """
                        SELECT
                          run_id,
                          project_id,
                          document_id,
                          status,
                          generation_status,
                          manifest_id,
                          ledger_id,
                          last_ledger_verification_run_id,
                          last_manifest_sha256,
                          last_ledger_sha256,
                          ledger_verification_status,
                          ledger_verified_at,
                          ready_at,
                          last_error_code,
                          updated_at
                        FROM governance_readiness_projections
                        WHERE run_id = %(run_id)s
                        LIMIT 1
                        """,
                        {"run_id": run_id},
                    )
                    row = cursor.fetchone()
                connection.commit()
        except GovernanceRunNotFoundError:
            raise
        except psycopg.Error as error:
            raise GovernanceStoreUnavailableError(
                "Governance readiness projection lookup failed."
            ) from error
        if row is None:
            raise GovernanceStoreUnavailableError("Governance readiness projection missing.")
        return self._as_readiness_record(row)

    def sync_governance_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    self._assert_document_exists(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                    )
                    self._sync_governance_scaffold(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                    )
                connection.commit()
        except GovernanceRunNotFoundError:
            raise
        except psycopg.Error as error:
            raise GovernanceStoreUnavailableError("Governance run synchronization failed.") from error

    def begin_ledger_attempt(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        source_review_snapshot_key: str,
        source_review_snapshot_sha256: str,
        actor_user_id: str,
        force_new_attempt: bool = False,
    ) -> RedactionEvidenceLedgerRecord:
        self.ensure_schema()
        normalized_key = source_review_snapshot_key.strip()
        normalized_sha256 = source_review_snapshot_sha256.strip()
        if not normalized_key or not normalized_sha256:
            raise GovernanceRunConflictError("Ledger generation requires pinned snapshot key and hash.")
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    self._assert_document_exists(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                    )
                    self._sync_governance_scaffold(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                    )
                    latest = self._load_latest_ledger(cursor=cursor, run_id=run_id)
                    if latest is not None:
                        snapshot_matches = (
                            latest.source_review_snapshot_key == normalized_key
                            and latest.source_review_snapshot_sha256 == normalized_sha256
                        )
                        if (
                            not force_new_attempt
                            and snapshot_matches
                            and latest.status in {"QUEUED", "RUNNING"}
                        ):
                            cursor.execute(
                                """
                                UPDATE redaction_evidence_ledgers
                                SET
                                  status = 'RUNNING',
                                  started_at = COALESCE(started_at, NOW()),
                                  finished_at = NULL,
                                  canceled_by = NULL,
                                  canceled_at = NULL,
                                  failure_reason = NULL
                                WHERE id = %(id)s
                                """,
                                {"id": latest.id},
                            )
                            self._append_event(
                                cursor=cursor,
                                run_id=run_id,
                                event_type="LEDGER_STARTED",
                                actor_user_id=actor_user_id,
                                from_status=latest.status,
                                to_status="RUNNING",
                                reason="Ledger generation started.",
                            )
                            self._sync_governance_scaffold(
                                cursor=cursor,
                                project_id=project_id,
                                document_id=document_id,
                                run_id=run_id,
                            )
                            updated = self._load_latest_ledger(cursor=cursor, run_id=run_id)
                            if updated is None:
                                raise GovernanceStoreUnavailableError(
                                    "Ledger attempt could not be started."
                                )
                            connection.commit()
                            return updated
                        if (
                            not force_new_attempt
                            and snapshot_matches
                            and latest.status == "SUCCEEDED"
                            and isinstance(latest.ledger_key, str)
                            and latest.ledger_key.strip()
                            and isinstance(latest.ledger_sha256, str)
                            and latest.ledger_sha256.strip()
                        ):
                            self._sync_governance_scaffold(
                                cursor=cursor,
                                project_id=project_id,
                                document_id=document_id,
                                run_id=run_id,
                            )
                            connection.commit()
                            return latest

                    supersedes_ledger_id = latest.id if latest is not None else None
                    next_attempt_number = (
                        latest.attempt_number + 1 if latest is not None else 1
                    )
                    ledger_id = str(uuid4())
                    cursor.execute(
                        """
                        INSERT INTO redaction_evidence_ledgers (
                          id,
                          run_id,
                          project_id,
                          document_id,
                          source_review_snapshot_key,
                          source_review_snapshot_sha256,
                          attempt_number,
                          supersedes_ledger_id,
                          superseded_by_ledger_id,
                          status,
                          ledger_key,
                          ledger_sha256,
                          hash_chain_version,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          failure_reason,
                          created_by,
                          created_at
                        )
                        VALUES (
                          %(id)s,
                          %(run_id)s,
                          %(project_id)s,
                          %(document_id)s,
                          %(source_review_snapshot_key)s,
                          %(source_review_snapshot_sha256)s,
                          %(attempt_number)s,
                          %(supersedes_ledger_id)s,
                          NULL,
                          'RUNNING',
                          NULL,
                          NULL,
                          'v1',
                          NOW(),
                          NULL,
                          NULL,
                          NULL,
                          NULL,
                          %(created_by)s,
                          NOW()
                        )
                        """,
                        {
                            "id": ledger_id,
                            "run_id": run_id,
                            "project_id": project_id,
                            "document_id": document_id,
                            "source_review_snapshot_key": normalized_key,
                            "source_review_snapshot_sha256": normalized_sha256,
                            "attempt_number": next_attempt_number,
                            "supersedes_ledger_id": supersedes_ledger_id,
                            "created_by": actor_user_id,
                        },
                    )
                    if supersedes_ledger_id is not None:
                        cursor.execute(
                            """
                            UPDATE redaction_evidence_ledgers
                            SET superseded_by_ledger_id = %(new_ledger_id)s
                            WHERE id = %(ledger_id)s
                              AND superseded_by_ledger_id IS NULL
                            """,
                            {
                                "new_ledger_id": ledger_id,
                                "ledger_id": supersedes_ledger_id,
                            },
                        )
                    self._append_event(
                        cursor=cursor,
                        run_id=run_id,
                        event_type="LEDGER_STARTED",
                        actor_user_id=actor_user_id,
                        from_status=latest.status if latest is not None else "IDLE",
                        to_status="RUNNING",
                        reason="Ledger attempt appended.",
                    )
                    self._sync_governance_scaffold(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                    )
                    inserted = self._load_latest_ledger(cursor=cursor, run_id=run_id)
                    if inserted is None:
                        raise GovernanceStoreUnavailableError("Ledger attempt could not be created.")
                connection.commit()
        except GovernanceRunNotFoundError:
            raise
        except GovernanceRunConflictError:
            raise
        except psycopg.Error as error:
            raise GovernanceStoreUnavailableError("Ledger attempt could not be started.") from error
        return inserted

    def complete_ledger_attempt(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        ledger_id: str,
        ledger_key: str,
        ledger_sha256: str,
        actor_user_id: str,
    ) -> RedactionEvidenceLedgerRecord:
        self.ensure_schema()
        normalized_key = ledger_key.strip()
        normalized_sha256 = ledger_sha256.strip()
        if not normalized_key or not normalized_sha256:
            raise GovernanceRunConflictError("Completed ledger attempt requires immutable key and hash.")
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    self._assert_document_exists(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                    )
                    cursor.execute(
                        """
                        SELECT
                          id,
                          run_id,
                          project_id,
                          document_id,
                          source_review_snapshot_key,
                          source_review_snapshot_sha256,
                          attempt_number,
                          supersedes_ledger_id,
                          superseded_by_ledger_id,
                          status,
                          ledger_key,
                          ledger_sha256,
                          hash_chain_version,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          failure_reason,
                          created_by,
                          created_at
                        FROM redaction_evidence_ledgers
                        WHERE run_id = %(run_id)s
                          AND id = %(ledger_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {"run_id": run_id, "ledger_id": ledger_id},
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise GovernanceRunNotFoundError("Ledger attempt not found.")
                    record = self._as_ledger_record(row)
                    if record.status not in {"QUEUED", "RUNNING", "SUCCEEDED"}:
                        raise GovernanceRunConflictError(
                            "Only queued or running ledger attempts can complete."
                        )
                    cursor.execute(
                        """
                        UPDATE redaction_evidence_ledgers
                        SET
                          status = 'SUCCEEDED',
                          ledger_key = %(ledger_key)s,
                          ledger_sha256 = %(ledger_sha256)s,
                          finished_at = NOW(),
                          canceled_by = NULL,
                          canceled_at = NULL,
                          failure_reason = NULL
                        WHERE id = %(ledger_id)s
                        """,
                        {
                            "ledger_key": normalized_key,
                            "ledger_sha256": normalized_sha256,
                            "ledger_id": ledger_id,
                        },
                    )
                    self._append_event(
                        cursor=cursor,
                        run_id=run_id,
                        event_type="LEDGER_SUCCEEDED",
                        actor_user_id=actor_user_id,
                        from_status=record.status,
                        to_status="SUCCEEDED",
                        reason="Ledger attempt finished successfully.",
                    )
                    self._sync_governance_scaffold(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                    )
                    cursor.execute(
                        """
                        SELECT
                          id,
                          run_id,
                          project_id,
                          document_id,
                          source_review_snapshot_key,
                          source_review_snapshot_sha256,
                          attempt_number,
                          supersedes_ledger_id,
                          superseded_by_ledger_id,
                          status,
                          ledger_key,
                          ledger_sha256,
                          hash_chain_version,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          failure_reason,
                          created_by,
                          created_at
                        FROM redaction_evidence_ledgers
                        WHERE id = %(ledger_id)s
                        LIMIT 1
                        """,
                        {"ledger_id": ledger_id},
                    )
                    updated = cursor.fetchone()
                    if updated is None:
                        raise GovernanceStoreUnavailableError("Ledger completion row reload failed.")
                connection.commit()
        except GovernanceRunNotFoundError:
            raise
        except GovernanceRunConflictError:
            raise
        except psycopg.Error as error:
            raise GovernanceStoreUnavailableError("Ledger attempt completion failed.") from error
        return self._as_ledger_record(updated)

    def fail_ledger_attempt(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        ledger_id: str,
        failure_reason: str,
        actor_user_id: str,
    ) -> RedactionEvidenceLedgerRecord:
        self.ensure_schema()
        message = failure_reason.strip() or "Ledger generation failed."
        if len(message) > 600:
            message = message[:600]
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    self._assert_document_exists(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                    )
                    cursor.execute(
                        """
                        SELECT
                          id,
                          run_id,
                          project_id,
                          document_id,
                          source_review_snapshot_key,
                          source_review_snapshot_sha256,
                          attempt_number,
                          supersedes_ledger_id,
                          superseded_by_ledger_id,
                          status,
                          ledger_key,
                          ledger_sha256,
                          hash_chain_version,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          failure_reason,
                          created_by,
                          created_at
                        FROM redaction_evidence_ledgers
                        WHERE run_id = %(run_id)s
                          AND id = %(ledger_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {"run_id": run_id, "ledger_id": ledger_id},
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise GovernanceRunNotFoundError("Ledger attempt not found.")
                    record = self._as_ledger_record(row)
                    if record.status not in {"QUEUED", "RUNNING", "FAILED"}:
                        raise GovernanceRunConflictError(
                            "Only queued or running ledger attempts can fail."
                        )
                    cursor.execute(
                        """
                        UPDATE redaction_evidence_ledgers
                        SET
                          status = 'FAILED',
                          finished_at = NOW(),
                          canceled_by = NULL,
                          canceled_at = NULL,
                          failure_reason = %(failure_reason)s
                        WHERE id = %(ledger_id)s
                        """,
                        {"failure_reason": message, "ledger_id": ledger_id},
                    )
                    self._append_event(
                        cursor=cursor,
                        run_id=run_id,
                        event_type="LEDGER_FAILED",
                        actor_user_id=actor_user_id,
                        from_status=record.status,
                        to_status="FAILED",
                        reason=message,
                    )
                    self._sync_governance_scaffold(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                    )
                    cursor.execute(
                        """
                        SELECT
                          id,
                          run_id,
                          project_id,
                          document_id,
                          source_review_snapshot_key,
                          source_review_snapshot_sha256,
                          attempt_number,
                          supersedes_ledger_id,
                          superseded_by_ledger_id,
                          status,
                          ledger_key,
                          ledger_sha256,
                          hash_chain_version,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          failure_reason,
                          created_by,
                          created_at
                        FROM redaction_evidence_ledgers
                        WHERE id = %(ledger_id)s
                        LIMIT 1
                        """,
                        {"ledger_id": ledger_id},
                    )
                    updated = cursor.fetchone()
                    if updated is None:
                        raise GovernanceStoreUnavailableError("Ledger failure row reload failed.")
                connection.commit()
        except GovernanceRunNotFoundError:
            raise
        except GovernanceRunConflictError:
            raise
        except psycopg.Error as error:
            raise GovernanceStoreUnavailableError("Ledger failure transition failed.") from error
        return self._as_ledger_record(updated)

    def create_ledger_verification_attempt(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        actor_user_id: str,
    ) -> LedgerVerificationRunRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    self._assert_document_exists(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                    )
                    self._sync_governance_scaffold(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                    )
                    latest = self._load_latest_verification(cursor=cursor, run_id=run_id)
                    supersedes_verification_run_id = latest.id if latest is not None else None
                    next_attempt_number = (
                        latest.attempt_number + 1 if latest is not None else 1
                    )
                    verification_id = str(uuid4())
                    cursor.execute(
                        """
                        INSERT INTO ledger_verification_runs (
                          id,
                          run_id,
                          attempt_number,
                          supersedes_verification_run_id,
                          superseded_by_verification_run_id,
                          status,
                          verification_result,
                          result_json,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          failure_reason,
                          created_by,
                          created_at
                        )
                        VALUES (
                          %(id)s,
                          %(run_id)s,
                          %(attempt_number)s,
                          %(supersedes_verification_run_id)s,
                          NULL,
                          'QUEUED',
                          NULL,
                          NULL,
                          NULL,
                          NULL,
                          NULL,
                          NULL,
                          NULL,
                          %(created_by)s,
                          NOW()
                        )
                        """,
                        {
                            "id": verification_id,
                            "run_id": run_id,
                            "attempt_number": next_attempt_number,
                            "supersedes_verification_run_id": supersedes_verification_run_id,
                            "created_by": actor_user_id,
                        },
                    )
                    if supersedes_verification_run_id is not None:
                        cursor.execute(
                            """
                            UPDATE ledger_verification_runs
                            SET superseded_by_verification_run_id = %(new_verification_run_id)s
                            WHERE id = %(verification_run_id)s
                              AND superseded_by_verification_run_id IS NULL
                            """,
                            {
                                "new_verification_run_id": verification_id,
                                "verification_run_id": supersedes_verification_run_id,
                            },
                        )
                    self._append_event(
                        cursor=cursor,
                        run_id=run_id,
                        event_type="LEDGER_VERIFY_STARTED",
                        actor_user_id=actor_user_id,
                        from_status=latest.status if latest is not None else "IDLE",
                        to_status="QUEUED",
                        reason="Ledger verification attempt queued.",
                    )
                    self._sync_governance_scaffold(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                    )
                    cursor.execute(
                        """
                        SELECT
                          id,
                          run_id,
                          attempt_number,
                          supersedes_verification_run_id,
                          superseded_by_verification_run_id,
                          status,
                          verification_result,
                          result_json,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          failure_reason,
                          created_by,
                          created_at
                        FROM ledger_verification_runs
                        WHERE id = %(verification_run_id)s
                        LIMIT 1
                        """,
                        {"verification_run_id": verification_id},
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise GovernanceStoreUnavailableError(
                            "Ledger verification attempt could not be loaded."
                        )
                connection.commit()
        except GovernanceRunNotFoundError:
            raise
        except psycopg.Error as error:
            raise GovernanceStoreUnavailableError(
                "Ledger verification attempt creation failed."
            ) from error
        return self._as_verification_record(row)

    def start_ledger_verification_attempt(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        verification_run_id: str,
    ) -> LedgerVerificationRunRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    self._assert_document_exists(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                    )
                    cursor.execute(
                        """
                        SELECT
                          id,
                          run_id,
                          attempt_number,
                          supersedes_verification_run_id,
                          superseded_by_verification_run_id,
                          status,
                          verification_result,
                          result_json,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          failure_reason,
                          created_by,
                          created_at
                        FROM ledger_verification_runs
                        WHERE run_id = %(run_id)s
                          AND id = %(verification_run_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {"run_id": run_id, "verification_run_id": verification_run_id},
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise GovernanceRunNotFoundError("Ledger verification attempt not found.")
                    record = self._as_verification_record(row)
                    if record.status not in {"QUEUED", "RUNNING"}:
                        raise GovernanceRunConflictError(
                            "Only queued verification attempts can start."
                        )
                    cursor.execute(
                        """
                        UPDATE ledger_verification_runs
                        SET
                          status = 'RUNNING',
                          started_at = COALESCE(started_at, NOW()),
                          finished_at = NULL,
                          canceled_by = NULL,
                          canceled_at = NULL,
                          failure_reason = NULL
                        WHERE id = %(verification_run_id)s
                        """,
                        {"verification_run_id": verification_run_id},
                    )
                    self._sync_governance_scaffold(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                    )
                    cursor.execute(
                        """
                        SELECT
                          id,
                          run_id,
                          attempt_number,
                          supersedes_verification_run_id,
                          superseded_by_verification_run_id,
                          status,
                          verification_result,
                          result_json,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          failure_reason,
                          created_by,
                          created_at
                        FROM ledger_verification_runs
                        WHERE id = %(verification_run_id)s
                        LIMIT 1
                        """,
                        {"verification_run_id": verification_run_id},
                    )
                    updated = cursor.fetchone()
                    if updated is None:
                        raise GovernanceStoreUnavailableError(
                            "Ledger verification start row reload failed."
                        )
                connection.commit()
        except GovernanceRunNotFoundError:
            raise
        except GovernanceRunConflictError:
            raise
        except psycopg.Error as error:
            raise GovernanceStoreUnavailableError(
                "Ledger verification start failed."
            ) from error
        return self._as_verification_record(updated)

    def complete_ledger_verification_attempt(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        verification_run_id: str,
        verification_result: GovernanceLedgerVerificationResult,
        result_json: dict[str, object],
    ) -> LedgerVerificationRunRecord:
        self.ensure_schema()
        if verification_result not in {"VALID", "INVALID"}:
            raise GovernanceRunConflictError("Verification result must be VALID or INVALID.")
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    self._assert_document_exists(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                    )
                    cursor.execute(
                        """
                        SELECT
                          id,
                          run_id,
                          attempt_number,
                          supersedes_verification_run_id,
                          superseded_by_verification_run_id,
                          status,
                          verification_result,
                          result_json,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          failure_reason,
                          created_by,
                          created_at
                        FROM ledger_verification_runs
                        WHERE run_id = %(run_id)s
                          AND id = %(verification_run_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {"run_id": run_id, "verification_run_id": verification_run_id},
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise GovernanceRunNotFoundError("Ledger verification attempt not found.")
                    record = self._as_verification_record(row)
                    if record.status not in {"QUEUED", "RUNNING", "SUCCEEDED"}:
                        raise GovernanceRunConflictError(
                            "Only queued or running verification attempts can complete."
                        )
                    cursor.execute(
                        """
                        UPDATE ledger_verification_runs
                        SET
                          status = 'SUCCEEDED',
                          verification_result = %(verification_result)s,
                          result_json = %(result_json)s::jsonb,
                          started_at = COALESCE(started_at, NOW()),
                          finished_at = NOW(),
                          canceled_by = NULL,
                          canceled_at = NULL,
                          failure_reason = NULL
                        WHERE id = %(verification_run_id)s
                        """,
                        {
                            "verification_result": verification_result,
                            "result_json": json.dumps(result_json, ensure_ascii=True),
                            "verification_run_id": verification_run_id,
                        },
                    )
                    self._append_event(
                        cursor=cursor,
                        run_id=run_id,
                        event_type=(
                            "LEDGER_VERIFIED_VALID"
                            if verification_result == "VALID"
                            else "LEDGER_VERIFIED_INVALID"
                        ),
                        actor_user_id=record.created_by,
                        from_status=record.status,
                        to_status="SUCCEEDED",
                        reason=f"Ledger verification completed with {verification_result}.",
                    )
                    self._sync_governance_scaffold(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                    )
                    cursor.execute(
                        """
                        SELECT
                          id,
                          run_id,
                          attempt_number,
                          supersedes_verification_run_id,
                          superseded_by_verification_run_id,
                          status,
                          verification_result,
                          result_json,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          failure_reason,
                          created_by,
                          created_at
                        FROM ledger_verification_runs
                        WHERE id = %(verification_run_id)s
                        LIMIT 1
                        """,
                        {"verification_run_id": verification_run_id},
                    )
                    updated = cursor.fetchone()
                    if updated is None:
                        raise GovernanceStoreUnavailableError(
                            "Ledger verification completion row reload failed."
                        )
                connection.commit()
        except GovernanceRunNotFoundError:
            raise
        except GovernanceRunConflictError:
            raise
        except psycopg.Error as error:
            raise GovernanceStoreUnavailableError(
                "Ledger verification completion failed."
            ) from error
        return self._as_verification_record(updated)

    def fail_ledger_verification_attempt(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        verification_run_id: str,
        failure_reason: str,
    ) -> LedgerVerificationRunRecord:
        self.ensure_schema()
        message = failure_reason.strip() or "Ledger verification failed."
        if len(message) > 600:
            message = message[:600]
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    self._assert_document_exists(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                    )
                    cursor.execute(
                        """
                        SELECT
                          id,
                          run_id,
                          attempt_number,
                          supersedes_verification_run_id,
                          superseded_by_verification_run_id,
                          status,
                          verification_result,
                          result_json,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          failure_reason,
                          created_by,
                          created_at
                        FROM ledger_verification_runs
                        WHERE run_id = %(run_id)s
                          AND id = %(verification_run_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {"run_id": run_id, "verification_run_id": verification_run_id},
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise GovernanceRunNotFoundError("Ledger verification attempt not found.")
                    record = self._as_verification_record(row)
                    if record.status not in {"QUEUED", "RUNNING", "FAILED"}:
                        raise GovernanceRunConflictError(
                            "Only queued or running verification attempts can fail."
                        )
                    cursor.execute(
                        """
                        UPDATE ledger_verification_runs
                        SET
                          status = 'FAILED',
                          started_at = COALESCE(started_at, NOW()),
                          finished_at = NOW(),
                          canceled_by = NULL,
                          canceled_at = NULL,
                          failure_reason = %(failure_reason)s
                        WHERE id = %(verification_run_id)s
                        """,
                        {
                            "failure_reason": message,
                            "verification_run_id": verification_run_id,
                        },
                    )
                    self._sync_governance_scaffold(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                    )
                    cursor.execute(
                        """
                        SELECT
                          id,
                          run_id,
                          attempt_number,
                          supersedes_verification_run_id,
                          superseded_by_verification_run_id,
                          status,
                          verification_result,
                          result_json,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          failure_reason,
                          created_by,
                          created_at
                        FROM ledger_verification_runs
                        WHERE id = %(verification_run_id)s
                        LIMIT 1
                        """,
                        {"verification_run_id": verification_run_id},
                    )
                    updated = cursor.fetchone()
                    if updated is None:
                        raise GovernanceStoreUnavailableError(
                            "Ledger verification failure row reload failed."
                        )
                connection.commit()
        except GovernanceRunNotFoundError:
            raise
        except GovernanceRunConflictError:
            raise
        except psycopg.Error as error:
            raise GovernanceStoreUnavailableError(
                "Ledger verification failure transition failed."
            ) from error
        return self._as_verification_record(updated)

    def cancel_ledger_verification_attempt(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        verification_run_id: str,
        actor_user_id: str,
    ) -> LedgerVerificationRunRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    self._assert_document_exists(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                    )
                    cursor.execute(
                        """
                        SELECT
                          id,
                          run_id,
                          attempt_number,
                          supersedes_verification_run_id,
                          superseded_by_verification_run_id,
                          status,
                          verification_result,
                          result_json,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          failure_reason,
                          created_by,
                          created_at
                        FROM ledger_verification_runs
                        WHERE run_id = %(run_id)s
                          AND id = %(verification_run_id)s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {"run_id": run_id, "verification_run_id": verification_run_id},
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise GovernanceRunNotFoundError("Ledger verification attempt not found.")
                    record = self._as_verification_record(row)
                    if record.status not in {"QUEUED", "RUNNING"}:
                        raise GovernanceRunConflictError(
                            "Ledger verification cancel is allowed only for queued or running attempts."
                        )
                    cursor.execute(
                        """
                        UPDATE ledger_verification_runs
                        SET
                          status = 'CANCELED',
                          finished_at = NOW(),
                          canceled_by = %(actor_user_id)s,
                          canceled_at = NOW(),
                          failure_reason = NULL
                        WHERE id = %(verification_run_id)s
                        """,
                        {
                            "actor_user_id": actor_user_id,
                            "verification_run_id": verification_run_id,
                        },
                    )
                    self._append_event(
                        cursor=cursor,
                        run_id=run_id,
                        event_type="LEDGER_VERIFY_CANCELED",
                        actor_user_id=actor_user_id,
                        from_status=record.status,
                        to_status="CANCELED",
                        reason="Ledger verification attempt canceled.",
                    )
                    self._sync_governance_scaffold(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                    )
                    cursor.execute(
                        """
                        SELECT
                          id,
                          run_id,
                          attempt_number,
                          supersedes_verification_run_id,
                          superseded_by_verification_run_id,
                          status,
                          verification_result,
                          result_json,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          failure_reason,
                          created_by,
                          created_at
                        FROM ledger_verification_runs
                        WHERE id = %(verification_run_id)s
                        LIMIT 1
                        """,
                        {"verification_run_id": verification_run_id},
                    )
                    updated = cursor.fetchone()
                    if updated is None:
                        raise GovernanceStoreUnavailableError(
                            "Ledger verification cancel row reload failed."
                        )
                connection.commit()
        except GovernanceRunNotFoundError:
            raise
        except GovernanceRunConflictError:
            raise
        except psycopg.Error as error:
            raise GovernanceStoreUnavailableError(
                "Ledger verification cancel failed."
            ) from error
        return self._as_verification_record(updated)

    def list_ledger_verification_runs(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> list[LedgerVerificationRunRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    self._assert_document_exists(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                    )
                    self._sync_governance_scaffold(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                    )
                    cursor.execute(
                        """
                        SELECT
                          id,
                          run_id,
                          attempt_number,
                          supersedes_verification_run_id,
                          superseded_by_verification_run_id,
                          status,
                          verification_result,
                          result_json,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          failure_reason,
                          created_by,
                          created_at
                        FROM ledger_verification_runs
                        WHERE run_id = %(run_id)s
                        ORDER BY attempt_number DESC, created_at DESC, id DESC
                        """,
                        {"run_id": run_id},
                    )
                    rows = cursor.fetchall()
                connection.commit()
        except GovernanceRunNotFoundError:
            raise
        except psycopg.Error as error:
            raise GovernanceStoreUnavailableError(
                "Ledger verification attempt listing failed."
            ) from error
        return [self._as_verification_record(row) for row in rows]

    def get_ledger_verification_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        verification_run_id: str,
    ) -> LedgerVerificationRunRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    self._assert_document_exists(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                    )
                    self._sync_governance_scaffold(
                        cursor=cursor,
                        project_id=project_id,
                        document_id=document_id,
                        run_id=run_id,
                    )
                    cursor.execute(
                        """
                        SELECT
                          id,
                          run_id,
                          attempt_number,
                          supersedes_verification_run_id,
                          superseded_by_verification_run_id,
                          status,
                          verification_result,
                          result_json,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          failure_reason,
                          created_by,
                          created_at
                        FROM ledger_verification_runs
                        WHERE run_id = %(run_id)s
                          AND id = %(verification_run_id)s
                        LIMIT 1
                        """,
                        {"run_id": run_id, "verification_run_id": verification_run_id},
                    )
                    row = cursor.fetchone()
                connection.commit()
        except GovernanceRunNotFoundError:
            raise
        except psycopg.Error as error:
            raise GovernanceStoreUnavailableError(
                "Ledger verification attempt lookup failed."
            ) from error
        if row is None:
            raise GovernanceRunNotFoundError("Ledger verification attempt not found.")
        return self._as_verification_record(row)

    def list_candidate_snapshot_contracts(
        self,
        *,
        project_id: str,
    ) -> list[ExportCandidateSnapshotContractRecord]:
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
                        ORDER BY created_at DESC, id DESC
                        """,
                        {"project_id": project_id},
                    )
                    rows = cursor.fetchall()
                connection.commit()
        except psycopg.Error as error:
            raise GovernanceStoreUnavailableError(
                "Candidate snapshot contract listing failed."
            ) from error
        return [self._as_candidate_contract_record(row) for row in rows]


@lru_cache
def get_governance_store() -> GovernanceStore:
    settings = get_settings()
    return GovernanceStore(settings=settings)


__all__ = [
    "ExportCandidateSnapshotContractRecord",
    "GovernanceReadyPairResolution",
    "GovernanceReadinessProjectionRecord",
    "GovernanceRunConflictError",
    "GovernanceRunEventRecord",
    "GovernanceRunNotFoundError",
    "GovernanceRunSummaryRecord",
    "GovernanceStore",
    "GovernanceStoreUnavailableError",
    "LedgerVerificationRunRecord",
    "RedactionEvidenceLedgerRecord",
    "RedactionManifestRecord",
    "get_governance_store",
    "resolve_governance_ready_pair_from_attempts",
]
