from __future__ import annotations

import json
from datetime import UTC, datetime

import psycopg
from psycopg.rows import dict_row

from app.core.config import Settings
from app.policies.models import (
    BaselinePolicySnapshotRecord,
    PolicyEventRecord,
    PolicyRuleSnapshotRecord,
    PolicyUsageLedgerRecord,
    PolicyUsageManifestRecord,
    PolicyUsagePseudonymSummary,
    PolicyUsageRunRecord,
    ProjectPolicyProjectionRecord,
    RedactionPolicyRecord,
)
from app.projects.store import ProjectStore

POLICY_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS redaction_policies (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      policy_family_id TEXT NOT NULL,
      name TEXT NOT NULL,
      version INTEGER NOT NULL,
      seeded_from_baseline_snapshot_id TEXT REFERENCES baseline_policy_snapshots(id),
      supersedes_policy_id TEXT REFERENCES redaction_policies(id),
      superseded_by_policy_id TEXT REFERENCES redaction_policies(id),
      rules_json JSONB NOT NULL,
      version_etag TEXT NOT NULL,
      status TEXT NOT NULL CHECK (status IN ('DRAFT', 'ACTIVE', 'RETIRED')),
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL,
      activated_by TEXT REFERENCES users(id),
      activated_at TIMESTAMPTZ,
      retired_by TEXT REFERENCES users(id),
      retired_at TIMESTAMPTZ,
      validation_status TEXT NOT NULL CHECK (
        validation_status IN ('NOT_VALIDATED', 'VALID', 'INVALID')
      ),
      validated_rules_sha256 TEXT,
      last_validated_by TEXT REFERENCES users(id),
      last_validated_at TIMESTAMPTZ,
      UNIQUE (project_id, policy_family_id, version)
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_redaction_policies_project_active_unique
      ON redaction_policies(project_id)
      WHERE status = 'ACTIVE'
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_redaction_policies_project_family_version
      ON redaction_policies(project_id, policy_family_id, version DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_redaction_policies_project_created_at
      ON redaction_policies(project_id, created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS project_policy_projections (
      project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
      active_policy_id TEXT REFERENCES redaction_policies(id),
      active_policy_family_id TEXT,
      updated_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS policy_events (
      id TEXT PRIMARY KEY,
      policy_id TEXT NOT NULL REFERENCES redaction_policies(id) ON DELETE CASCADE,
      event_type TEXT NOT NULL CHECK (
        event_type IN (
          'POLICY_CREATED',
          'POLICY_EDITED',
          'POLICY_VALIDATED_VALID',
          'POLICY_VALIDATED_INVALID',
          'POLICY_ACTIVATED',
          'POLICY_RETIRED'
        )
      ),
      actor_user_id TEXT REFERENCES users(id),
      reason TEXT,
      rules_sha256 TEXT NOT NULL,
      rules_snapshot_key TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_policy_events_policy_id_created_at
      ON policy_events(policy_id, created_at ASC, id ASC)
    """,
    """
    CREATE TABLE IF NOT EXISTS policy_rule_snapshots (
      policy_id TEXT NOT NULL REFERENCES redaction_policies(id) ON DELETE CASCADE,
      rules_sha256 TEXT NOT NULL,
      rules_snapshot_key TEXT NOT NULL UNIQUE,
      rules_json JSONB NOT NULL,
      created_at TIMESTAMPTZ NOT NULL,
      PRIMARY KEY (policy_id, rules_sha256, rules_snapshot_key)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_policy_rule_snapshots_policy_sha_created
      ON policy_rule_snapshots(policy_id, rules_sha256, created_at DESC, rules_snapshot_key DESC)
    """,
)


class PolicyStoreUnavailableError(RuntimeError):
    """Policy persistence could not be reached."""


class PolicyStore:
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
    def _coerce_rules_json(value: object) -> dict[str, object]:
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str):
            try:
                payload = json.loads(value)
            except json.JSONDecodeError:
                return {}
            if isinstance(payload, dict):
                return dict(payload)
        return {}

    @staticmethod
    def _as_policy(row: dict[str, object]) -> RedactionPolicyRecord:
        return RedactionPolicyRecord(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            policy_family_id=str(row["policy_family_id"]),
            name=str(row["name"]),
            version=int(row["version"]),
            seeded_from_baseline_snapshot_id=(
                str(row["seeded_from_baseline_snapshot_id"])
                if isinstance(row.get("seeded_from_baseline_snapshot_id"), str)
                else None
            ),
            supersedes_policy_id=(
                str(row["supersedes_policy_id"])
                if isinstance(row.get("supersedes_policy_id"), str)
                else None
            ),
            superseded_by_policy_id=(
                str(row["superseded_by_policy_id"])
                if isinstance(row.get("superseded_by_policy_id"), str)
                else None
            ),
            rules_json=PolicyStore._coerce_rules_json(row.get("rules_json")),
            version_etag=str(row["version_etag"]),
            status=str(row["status"]),  # type: ignore[arg-type]
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
            activated_by=(
                str(row["activated_by"]) if isinstance(row.get("activated_by"), str) else None
            ),
            activated_at=row.get("activated_at"),  # type: ignore[arg-type]
            retired_by=(
                str(row["retired_by"]) if isinstance(row.get("retired_by"), str) else None
            ),
            retired_at=row.get("retired_at"),  # type: ignore[arg-type]
            validation_status=str(row["validation_status"]),  # type: ignore[arg-type]
            validated_rules_sha256=(
                str(row["validated_rules_sha256"])
                if isinstance(row.get("validated_rules_sha256"), str)
                else None
            ),
            last_validated_by=(
                str(row["last_validated_by"])
                if isinstance(row.get("last_validated_by"), str)
                else None
            ),
            last_validated_at=row.get("last_validated_at"),  # type: ignore[arg-type]
        )

    @staticmethod
    def _as_projection(row: dict[str, object]) -> ProjectPolicyProjectionRecord:
        return ProjectPolicyProjectionRecord(
            project_id=str(row["project_id"]),
            active_policy_id=(
                str(row["active_policy_id"])
                if isinstance(row.get("active_policy_id"), str)
                else None
            ),
            active_policy_family_id=(
                str(row["active_policy_family_id"])
                if isinstance(row.get("active_policy_family_id"), str)
                else None
            ),
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @staticmethod
    def _as_policy_event(row: dict[str, object]) -> PolicyEventRecord:
        return PolicyEventRecord(
            id=str(row["id"]),
            policy_id=str(row["policy_id"]),
            event_type=str(row["event_type"]),  # type: ignore[arg-type]
            actor_user_id=(
                str(row["actor_user_id"])
                if isinstance(row.get("actor_user_id"), str)
                else None
            ),
            reason=str(row["reason"]) if isinstance(row.get("reason"), str) else None,
            rules_sha256=str(row["rules_sha256"]),
            rules_snapshot_key=str(row["rules_snapshot_key"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @staticmethod
    def _as_baseline_snapshot(row: dict[str, object]) -> BaselinePolicySnapshotRecord:
        return BaselinePolicySnapshotRecord(
            id=str(row["id"]),
            snapshot_hash=str(row["snapshot_hash"]),
            rules_json=PolicyStore._coerce_rules_json(row.get("rules_json")),
            created_at=row["created_at"],  # type: ignore[arg-type]
            seeded_by=str(row["seeded_by"]),
        )

    @staticmethod
    def _as_policy_rule_snapshot(row: dict[str, object]) -> PolicyRuleSnapshotRecord:
        return PolicyRuleSnapshotRecord(
            policy_id=str(row["policy_id"]),
            rules_sha256=str(row["rules_sha256"]),
            rules_snapshot_key=str(row["rules_snapshot_key"]),
            rules_json=PolicyStore._coerce_rules_json(row.get("rules_json")),
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @staticmethod
    def _as_policy_usage_run(row: dict[str, object]) -> PolicyUsageRunRecord:
        return PolicyUsageRunRecord(
            run_id=str(row["run_id"]),
            project_id=str(row["project_id"]),
            document_id=str(row["document_id"]),
            run_kind=str(row["run_kind"]),
            run_status=str(row["run_status"]),
            supersedes_redaction_run_id=(
                str(row["supersedes_redaction_run_id"])
                if isinstance(row.get("supersedes_redaction_run_id"), str)
                else None
            ),
            policy_family_id=(
                str(row["policy_family_id"])
                if isinstance(row.get("policy_family_id"), str)
                else None
            ),
            policy_version=(
                str(row["policy_version"])
                if isinstance(row.get("policy_version"), str)
                else None
            ),
            run_created_at=row["run_created_at"],  # type: ignore[arg-type]
            run_finished_at=row.get("run_finished_at"),  # type: ignore[arg-type]
            governance_readiness_status=(
                str(row["governance_readiness_status"])
                if isinstance(row.get("governance_readiness_status"), str)
                else None
            ),
            governance_generation_status=(
                str(row["governance_generation_status"])
                if isinstance(row.get("governance_generation_status"), str)
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
            governance_ledger_verification_status=(
                str(row["governance_ledger_verification_status"])
                if isinstance(row.get("governance_ledger_verification_status"), str)
                else None
            ),
        )

    @staticmethod
    def _as_policy_usage_manifest(row: dict[str, object]) -> PolicyUsageManifestRecord:
        return PolicyUsageManifestRecord(
            id=str(row["id"]),
            run_id=str(row["run_id"]),
            project_id=str(row["project_id"]),
            document_id=str(row["document_id"]),
            status=str(row["status"]),
            attempt_number=int(row["attempt_number"]),
            manifest_sha256=(
                str(row["manifest_sha256"])
                if isinstance(row.get("manifest_sha256"), str)
                else None
            ),
            source_review_snapshot_sha256=str(row["source_review_snapshot_sha256"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @staticmethod
    def _as_policy_usage_ledger(row: dict[str, object]) -> PolicyUsageLedgerRecord:
        return PolicyUsageLedgerRecord(
            id=str(row["id"]),
            run_id=str(row["run_id"]),
            project_id=str(row["project_id"]),
            document_id=str(row["document_id"]),
            status=str(row["status"]),
            attempt_number=int(row["attempt_number"]),
            ledger_sha256=(
                str(row["ledger_sha256"])
                if isinstance(row.get("ledger_sha256"), str)
                else None
            ),
            source_review_snapshot_sha256=str(row["source_review_snapshot_sha256"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    def ensure_schema(self) -> None:
        if self._schema_initialized:
            return

        try:
            self._project_store.ensure_schema()
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    for statement in POLICY_SCHEMA_STATEMENTS:
                        cursor.execute(statement)
                connection.commit()
        except psycopg.Error as error:
            raise PolicyStoreUnavailableError(
                "Policy schema could not be initialized."
            ) from error

        self._schema_initialized = True

    def list_policies(self, *, project_id: str) -> list[RedactionPolicyRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          policy_family_id,
                          name,
                          version,
                          seeded_from_baseline_snapshot_id,
                          supersedes_policy_id,
                          superseded_by_policy_id,
                          rules_json,
                          version_etag,
                          status,
                          created_by,
                          created_at,
                          activated_by,
                          activated_at,
                          retired_by,
                          retired_at,
                          validation_status,
                          validated_rules_sha256,
                          last_validated_by,
                          last_validated_at
                        FROM redaction_policies
                        WHERE project_id = %(project_id)s
                        ORDER BY version DESC, created_at DESC, id DESC
                        """,
                        {"project_id": project_id},
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise PolicyStoreUnavailableError("Policy listing failed.") from error

        return [self._as_policy(row) for row in rows]

    def get_policy(
        self,
        *,
        project_id: str,
        policy_id: str,
    ) -> RedactionPolicyRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          policy_family_id,
                          name,
                          version,
                          seeded_from_baseline_snapshot_id,
                          supersedes_policy_id,
                          superseded_by_policy_id,
                          rules_json,
                          version_etag,
                          status,
                          created_by,
                          created_at,
                          activated_by,
                          activated_at,
                          retired_by,
                          retired_at,
                          validation_status,
                          validated_rules_sha256,
                          last_validated_by,
                          last_validated_at
                        FROM redaction_policies
                        WHERE project_id = %(project_id)s
                          AND id = %(policy_id)s
                        """,
                        {"project_id": project_id, "policy_id": policy_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise PolicyStoreUnavailableError("Policy lookup failed.") from error

        if row is None:
            return None
        return self._as_policy(row)

    def get_policy_by_id(self, *, policy_id: str) -> RedactionPolicyRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          policy_family_id,
                          name,
                          version,
                          seeded_from_baseline_snapshot_id,
                          supersedes_policy_id,
                          superseded_by_policy_id,
                          rules_json,
                          version_etag,
                          status,
                          created_by,
                          created_at,
                          activated_by,
                          activated_at,
                          retired_by,
                          retired_at,
                          validation_status,
                          validated_rules_sha256,
                          last_validated_by,
                          last_validated_at
                        FROM redaction_policies
                        WHERE id = %(policy_id)s
                        """,
                        {"policy_id": policy_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise PolicyStoreUnavailableError("Policy lookup failed.") from error

        if row is None:
            return None
        return self._as_policy(row)

    def create_policy(self, *, record: RedactionPolicyRecord) -> None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO redaction_policies (
                          id,
                          project_id,
                          policy_family_id,
                          name,
                          version,
                          seeded_from_baseline_snapshot_id,
                          supersedes_policy_id,
                          superseded_by_policy_id,
                          rules_json,
                          version_etag,
                          status,
                          created_by,
                          created_at,
                          activated_by,
                          activated_at,
                          retired_by,
                          retired_at,
                          validation_status,
                          validated_rules_sha256,
                          last_validated_by,
                          last_validated_at
                        )
                        VALUES (
                          %(id)s,
                          %(project_id)s,
                          %(policy_family_id)s,
                          %(name)s,
                          %(version)s,
                          %(seeded_from_baseline_snapshot_id)s,
                          %(supersedes_policy_id)s,
                          %(superseded_by_policy_id)s,
                          %(rules_json)s::jsonb,
                          %(version_etag)s,
                          %(status)s,
                          %(created_by)s,
                          %(created_at)s,
                          %(activated_by)s,
                          %(activated_at)s,
                          %(retired_by)s,
                          %(retired_at)s,
                          %(validation_status)s,
                          %(validated_rules_sha256)s,
                          %(last_validated_by)s,
                          %(last_validated_at)s
                        )
                        """,
                        {
                            "id": record.id,
                            "project_id": record.project_id,
                            "policy_family_id": record.policy_family_id,
                            "name": record.name,
                            "version": record.version,
                            "seeded_from_baseline_snapshot_id": (
                                record.seeded_from_baseline_snapshot_id
                            ),
                            "supersedes_policy_id": record.supersedes_policy_id,
                            "superseded_by_policy_id": record.superseded_by_policy_id,
                            "rules_json": json.dumps(
                                record.rules_json,
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                            "version_etag": record.version_etag,
                            "status": record.status,
                            "created_by": record.created_by,
                            "created_at": record.created_at,
                            "activated_by": record.activated_by,
                            "activated_at": record.activated_at,
                            "retired_by": record.retired_by,
                            "retired_at": record.retired_at,
                            "validation_status": record.validation_status,
                            "validated_rules_sha256": record.validated_rules_sha256,
                            "last_validated_by": record.last_validated_by,
                            "last_validated_at": record.last_validated_at,
                        },
                    )
                connection.commit()
        except psycopg.Error as error:
            raise PolicyStoreUnavailableError("Policy create failed.") from error

    def set_superseded_by(
        self,
        *,
        policy_id: str,
        superseded_by_policy_id: str,
    ) -> None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE redaction_policies
                        SET superseded_by_policy_id = %(superseded_by_policy_id)s
                        WHERE id = %(policy_id)s
                          AND superseded_by_policy_id IS NULL
                        """,
                        {
                            "policy_id": policy_id,
                            "superseded_by_policy_id": superseded_by_policy_id,
                        },
                    )
                connection.commit()
        except psycopg.Error as error:
            raise PolicyStoreUnavailableError("Policy supersession update failed.") from error

    def update_draft_policy(
        self,
        *,
        project_id: str,
        policy_id: str,
        expected_version_etag: str,
        name: str,
        rules_json: dict[str, object],
        new_version_etag: str,
    ) -> RedactionPolicyRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE redaction_policies
                        SET
                          name = %(name)s,
                          rules_json = %(rules_json)s::jsonb,
                          version_etag = %(new_version_etag)s,
                          validation_status = 'NOT_VALIDATED',
                          validated_rules_sha256 = NULL,
                          last_validated_by = NULL,
                          last_validated_at = NULL
                        WHERE project_id = %(project_id)s
                          AND id = %(policy_id)s
                          AND status = 'DRAFT'
                          AND version_etag = %(expected_version_etag)s
                        RETURNING
                          id,
                          project_id,
                          policy_family_id,
                          name,
                          version,
                          seeded_from_baseline_snapshot_id,
                          supersedes_policy_id,
                          superseded_by_policy_id,
                          rules_json,
                          version_etag,
                          status,
                          created_by,
                          created_at,
                          activated_by,
                          activated_at,
                          retired_by,
                          retired_at,
                          validation_status,
                          validated_rules_sha256,
                          last_validated_by,
                          last_validated_at
                        """,
                        {
                            "project_id": project_id,
                            "policy_id": policy_id,
                            "expected_version_etag": expected_version_etag,
                            "name": name,
                            "rules_json": json.dumps(
                                rules_json,
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                            "new_version_etag": new_version_etag,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise PolicyStoreUnavailableError("Policy update failed.") from error

        if row is None:
            return None
        return self._as_policy(row)

    def update_validation(
        self,
        *,
        project_id: str,
        policy_id: str,
        validation_status: str,
        validated_rules_sha256: str | None,
        last_validated_by: str,
        last_validated_at: datetime,
    ) -> RedactionPolicyRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE redaction_policies
                        SET
                          validation_status = %(validation_status)s,
                          validated_rules_sha256 = %(validated_rules_sha256)s,
                          last_validated_by = %(last_validated_by)s,
                          last_validated_at = %(last_validated_at)s
                        WHERE project_id = %(project_id)s
                          AND id = %(policy_id)s
                        RETURNING
                          id,
                          project_id,
                          policy_family_id,
                          name,
                          version,
                          seeded_from_baseline_snapshot_id,
                          supersedes_policy_id,
                          superseded_by_policy_id,
                          rules_json,
                          version_etag,
                          status,
                          created_by,
                          created_at,
                          activated_by,
                          activated_at,
                          retired_by,
                          retired_at,
                          validation_status,
                          validated_rules_sha256,
                          last_validated_by,
                          last_validated_at
                        """,
                        {
                            "project_id": project_id,
                            "policy_id": policy_id,
                            "validation_status": validation_status,
                            "validated_rules_sha256": validated_rules_sha256,
                            "last_validated_by": last_validated_by,
                            "last_validated_at": last_validated_at,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise PolicyStoreUnavailableError("Policy validation persistence failed.") from error

        if row is None:
            return None
        return self._as_policy(row)

    def activate_policy(
        self,
        *,
        project_id: str,
        policy_id: str,
        activated_by: str,
        activated_at: datetime,
    ) -> RedactionPolicyRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE redaction_policies
                        SET
                          status = 'ACTIVE',
                          activated_by = %(activated_by)s,
                          activated_at = %(activated_at)s,
                          retired_by = NULL,
                          retired_at = NULL
                        WHERE project_id = %(project_id)s
                          AND id = %(policy_id)s
                          AND status = 'DRAFT'
                        RETURNING
                          id,
                          project_id,
                          policy_family_id,
                          name,
                          version,
                          seeded_from_baseline_snapshot_id,
                          supersedes_policy_id,
                          superseded_by_policy_id,
                          rules_json,
                          version_etag,
                          status,
                          created_by,
                          created_at,
                          activated_by,
                          activated_at,
                          retired_by,
                          retired_at,
                          validation_status,
                          validated_rules_sha256,
                          last_validated_by,
                          last_validated_at
                        """,
                        {
                            "project_id": project_id,
                            "policy_id": policy_id,
                            "activated_by": activated_by,
                            "activated_at": activated_at,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise PolicyStoreUnavailableError("Policy activation failed.") from error

        if row is None:
            return None
        return self._as_policy(row)

    def retire_policy(
        self,
        *,
        project_id: str,
        policy_id: str,
        retired_by: str,
        retired_at: datetime,
    ) -> RedactionPolicyRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE redaction_policies
                        SET
                          status = 'RETIRED',
                          retired_by = %(retired_by)s,
                          retired_at = %(retired_at)s
                        WHERE project_id = %(project_id)s
                          AND id = %(policy_id)s
                          AND status = 'ACTIVE'
                        RETURNING
                          id,
                          project_id,
                          policy_family_id,
                          name,
                          version,
                          seeded_from_baseline_snapshot_id,
                          supersedes_policy_id,
                          superseded_by_policy_id,
                          rules_json,
                          version_etag,
                          status,
                          created_by,
                          created_at,
                          activated_by,
                          activated_at,
                          retired_by,
                          retired_at,
                          validation_status,
                          validated_rules_sha256,
                          last_validated_by,
                          last_validated_at
                        """,
                        {
                            "project_id": project_id,
                            "policy_id": policy_id,
                            "retired_by": retired_by,
                            "retired_at": retired_at,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise PolicyStoreUnavailableError("Policy retirement failed.") from error

        if row is None:
            return None
        return self._as_policy(row)

    def retire_active_policies(
        self,
        *,
        project_id: str,
        except_policy_id: str,
        retired_by: str,
        retired_at: datetime,
    ) -> list[RedactionPolicyRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE redaction_policies
                        SET
                          status = 'RETIRED',
                          retired_by = %(retired_by)s,
                          retired_at = %(retired_at)s
                        WHERE project_id = %(project_id)s
                          AND status = 'ACTIVE'
                          AND id <> %(except_policy_id)s
                        RETURNING
                          id,
                          project_id,
                          policy_family_id,
                          name,
                          version,
                          seeded_from_baseline_snapshot_id,
                          supersedes_policy_id,
                          superseded_by_policy_id,
                          rules_json,
                          version_etag,
                          status,
                          created_by,
                          created_at,
                          activated_by,
                          activated_at,
                          retired_by,
                          retired_at,
                          validation_status,
                          validated_rules_sha256,
                          last_validated_by,
                          last_validated_at
                        """,
                        {
                            "project_id": project_id,
                            "except_policy_id": except_policy_id,
                            "retired_by": retired_by,
                            "retired_at": retired_at,
                        },
                    )
                    rows = cursor.fetchall()
                connection.commit()
        except psycopg.Error as error:
            raise PolicyStoreUnavailableError("Policy retirement failed.") from error

        return [self._as_policy(row) for row in rows]

    def get_projection(
        self,
        *,
        project_id: str,
    ) -> ProjectPolicyProjectionRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT project_id, active_policy_id, active_policy_family_id, updated_at
                        FROM project_policy_projections
                        WHERE project_id = %(project_id)s
                        """,
                        {"project_id": project_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise PolicyStoreUnavailableError("Policy projection lookup failed.") from error

        if row is None:
            return None
        return self._as_projection(row)

    def upsert_projection(
        self,
        *,
        project_id: str,
        active_policy_id: str | None,
        active_policy_family_id: str | None,
        updated_at: datetime,
    ) -> ProjectPolicyProjectionRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO project_policy_projections (
                          project_id,
                          active_policy_id,
                          active_policy_family_id,
                          updated_at
                        )
                        VALUES (
                          %(project_id)s,
                          %(active_policy_id)s,
                          %(active_policy_family_id)s,
                          %(updated_at)s
                        )
                        ON CONFLICT (project_id) DO UPDATE
                        SET
                          active_policy_id = EXCLUDED.active_policy_id,
                          active_policy_family_id = EXCLUDED.active_policy_family_id,
                          updated_at = EXCLUDED.updated_at
                        RETURNING project_id, active_policy_id, active_policy_family_id, updated_at
                        """,
                        {
                            "project_id": project_id,
                            "active_policy_id": active_policy_id,
                            "active_policy_family_id": active_policy_family_id,
                            "updated_at": updated_at,
                        },
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise PolicyStoreUnavailableError(
                            "Policy projection could not be loaded after upsert."
                        )
                connection.commit()
        except psycopg.Error as error:
            raise PolicyStoreUnavailableError("Policy projection update failed.") from error

        return self._as_projection(row)

    def append_event(
        self,
        *,
        event: PolicyEventRecord,
        rules_json: dict[str, object],
    ) -> None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO policy_events (
                          id,
                          policy_id,
                          event_type,
                          actor_user_id,
                          reason,
                          rules_sha256,
                          rules_snapshot_key,
                          created_at
                        )
                        VALUES (
                          %(id)s,
                          %(policy_id)s,
                          %(event_type)s,
                          %(actor_user_id)s,
                          %(reason)s,
                          %(rules_sha256)s,
                          %(rules_snapshot_key)s,
                          %(created_at)s
                        )
                        """,
                        {
                            "id": event.id,
                            "policy_id": event.policy_id,
                            "event_type": event.event_type,
                            "actor_user_id": event.actor_user_id,
                            "reason": event.reason,
                            "rules_sha256": event.rules_sha256,
                            "rules_snapshot_key": event.rules_snapshot_key,
                            "created_at": event.created_at,
                        },
                    )
                    cursor.execute(
                        """
                        INSERT INTO policy_rule_snapshots (
                          policy_id,
                          rules_sha256,
                          rules_snapshot_key,
                          rules_json,
                          created_at
                        )
                        VALUES (
                          %(policy_id)s,
                          %(rules_sha256)s,
                          %(rules_snapshot_key)s,
                          %(rules_json)s::jsonb,
                          %(created_at)s
                        )
                        ON CONFLICT (rules_snapshot_key) DO NOTHING
                        """,
                        {
                            "policy_id": event.policy_id,
                            "rules_sha256": event.rules_sha256,
                            "rules_snapshot_key": event.rules_snapshot_key,
                            "rules_json": json.dumps(
                                rules_json,
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                            "created_at": event.created_at,
                        },
                    )
                connection.commit()
        except psycopg.Error as error:
            raise PolicyStoreUnavailableError("Policy event append failed.") from error

    def list_policy_events(
        self,
        *,
        project_id: str,
        policy_id: str,
    ) -> list[PolicyEventRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          e.id,
                          e.policy_id,
                          e.event_type,
                          e.actor_user_id,
                          e.reason,
                          e.rules_sha256,
                          e.rules_snapshot_key,
                          e.created_at
                        FROM policy_events AS e
                        INNER JOIN redaction_policies AS p
                          ON p.id = e.policy_id
                        WHERE e.policy_id = %(policy_id)s
                          AND p.project_id = %(project_id)s
                        ORDER BY e.created_at ASC, e.id ASC
                        """,
                        {"project_id": project_id, "policy_id": policy_id},
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise PolicyStoreUnavailableError("Policy event listing failed.") from error

        return [self._as_policy_event(row) for row in rows]

    def list_lineage_policies(
        self,
        *,
        project_id: str,
        policy_family_id: str,
    ) -> list[RedactionPolicyRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          policy_family_id,
                          name,
                          version,
                          seeded_from_baseline_snapshot_id,
                          supersedes_policy_id,
                          superseded_by_policy_id,
                          rules_json,
                          version_etag,
                          status,
                          created_by,
                          created_at,
                          activated_by,
                          activated_at,
                          retired_by,
                          retired_at,
                          validation_status,
                          validated_rules_sha256,
                          last_validated_by,
                          last_validated_at
                        FROM redaction_policies
                        WHERE project_id = %(project_id)s
                          AND policy_family_id = %(policy_family_id)s
                        ORDER BY version ASC, created_at ASC, id ASC
                        """,
                        {
                            "project_id": project_id,
                            "policy_family_id": policy_family_id,
                        },
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise PolicyStoreUnavailableError("Policy lineage lookup failed.") from error

        return [self._as_policy(row) for row in rows]

    def get_policy_rule_snapshot(
        self,
        *,
        project_id: str,
        policy_id: str,
        rules_sha256: str,
    ) -> PolicyRuleSnapshotRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          s.policy_id,
                          s.rules_sha256,
                          s.rules_snapshot_key,
                          s.rules_json,
                          s.created_at
                        FROM policy_rule_snapshots AS s
                        INNER JOIN redaction_policies AS p
                          ON p.id = s.policy_id
                        WHERE s.policy_id = %(policy_id)s
                          AND s.rules_sha256 = %(rules_sha256)s
                          AND p.project_id = %(project_id)s
                        ORDER BY s.created_at DESC, s.rules_snapshot_key DESC
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "policy_id": policy_id,
                            "rules_sha256": rules_sha256,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise PolicyStoreUnavailableError("Policy snapshot lookup failed.") from error

        if row is None:
            return None
        return self._as_policy_rule_snapshot(row)

    def list_policy_usage_runs(
        self,
        *,
        project_id: str,
        policy_id: str,
    ) -> list[PolicyUsageRunRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          r.id AS run_id,
                          r.project_id,
                          r.document_id,
                          r.run_kind,
                          r.status AS run_status,
                          r.supersedes_redaction_run_id,
                          r.policy_family_id,
                          r.policy_version,
                          r.created_at AS run_created_at,
                          r.finished_at AS run_finished_at,
                          g.status AS governance_readiness_status,
                          g.generation_status AS governance_generation_status,
                          g.manifest_id AS governance_manifest_id,
                          g.ledger_id AS governance_ledger_id,
                          g.last_manifest_sha256 AS governance_manifest_sha256,
                          g.last_ledger_sha256 AS governance_ledger_sha256,
                          g.ledger_verification_status AS governance_ledger_verification_status
                        FROM redaction_runs AS r
                        LEFT JOIN governance_readiness_projections AS g
                          ON g.run_id = r.id
                         AND g.project_id = r.project_id
                         AND g.document_id = r.document_id
                        WHERE r.project_id = %(project_id)s
                          AND r.policy_id = %(policy_id)s
                        ORDER BY r.created_at DESC, r.id DESC
                        """,
                        {"project_id": project_id, "policy_id": policy_id},
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            if getattr(error, "sqlstate", None) == "42P01":
                return []
            raise PolicyStoreUnavailableError("Policy usage run lookup failed.") from error

        return [self._as_policy_usage_run(row) for row in rows]

    def list_policy_usage_manifests(
        self,
        *,
        project_id: str,
        policy_id: str,
    ) -> list[PolicyUsageManifestRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          m.id,
                          m.run_id,
                          m.project_id,
                          m.document_id,
                          m.status,
                          m.attempt_number,
                          m.manifest_sha256,
                          m.source_review_snapshot_sha256,
                          m.created_at
                        FROM redaction_manifests AS m
                        INNER JOIN redaction_runs AS r
                          ON r.id = m.run_id
                        WHERE m.project_id = %(project_id)s
                          AND r.policy_id = %(policy_id)s
                        ORDER BY m.created_at DESC, m.id DESC
                        """,
                        {"project_id": project_id, "policy_id": policy_id},
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            if getattr(error, "sqlstate", None) == "42P01":
                return []
            raise PolicyStoreUnavailableError("Policy usage manifest lookup failed.") from error

        return [self._as_policy_usage_manifest(row) for row in rows]

    def list_policy_usage_ledgers(
        self,
        *,
        project_id: str,
        policy_id: str,
    ) -> list[PolicyUsageLedgerRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          l.id,
                          l.run_id,
                          l.project_id,
                          l.document_id,
                          l.status,
                          l.attempt_number,
                          l.ledger_sha256,
                          l.source_review_snapshot_sha256,
                          l.created_at
                        FROM redaction_evidence_ledgers AS l
                        INNER JOIN redaction_runs AS r
                          ON r.id = l.run_id
                        WHERE l.project_id = %(project_id)s
                          AND r.policy_id = %(policy_id)s
                        ORDER BY l.created_at DESC, l.id DESC
                        """,
                        {"project_id": project_id, "policy_id": policy_id},
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            if getattr(error, "sqlstate", None) == "42P01":
                return []
            raise PolicyStoreUnavailableError("Policy usage ledger lookup failed.") from error

        return [self._as_policy_usage_ledger(row) for row in rows]

    def get_policy_pseudonym_summary(
        self,
        *,
        project_id: str,
        policy_id: str,
    ) -> PolicyUsagePseudonymSummary:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          COUNT(*)::INT AS total_entries,
                          COUNT(*) FILTER (WHERE status = 'ACTIVE')::INT AS active_entries,
                          COUNT(*) FILTER (WHERE status = 'RETIRED')::INT AS retired_entries,
                          COALESCE(
                            ARRAY_AGG(DISTINCT alias_strategy_version)
                              FILTER (WHERE alias_strategy_version IS NOT NULL),
                            ARRAY[]::TEXT[]
                          ) AS alias_strategy_versions,
                          COALESCE(
                            ARRAY_AGG(DISTINCT salt_version_ref)
                              FILTER (WHERE salt_version_ref IS NOT NULL),
                            ARRAY[]::TEXT[]
                          ) AS salt_version_refs
                        FROM pseudonym_registry_entries
                        WHERE project_id = %(project_id)s
                          AND policy_id = %(policy_id)s
                        """,
                        {"project_id": project_id, "policy_id": policy_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            if getattr(error, "sqlstate", None) == "42P01":
                return PolicyUsagePseudonymSummary(
                    total_entries=0,
                    active_entries=0,
                    retired_entries=0,
                    alias_strategy_versions=tuple(),
                    salt_version_refs=tuple(),
                )
            raise PolicyStoreUnavailableError("Policy pseudonym summary lookup failed.") from error

        if row is None:
            return PolicyUsagePseudonymSummary(
                total_entries=0,
                active_entries=0,
                retired_entries=0,
                alias_strategy_versions=tuple(),
                salt_version_refs=tuple(),
            )
        alias_versions_raw = row.get("alias_strategy_versions")
        salt_refs_raw = row.get("salt_version_refs")
        alias_versions = tuple(
            sorted(
                {
                    str(value).strip()
                    for value in (alias_versions_raw or [])
                    if isinstance(value, str) and value.strip()
                }
            )
        )
        salt_refs = tuple(
            sorted(
                {
                    str(value).strip()
                    for value in (salt_refs_raw or [])
                    if isinstance(value, str) and value.strip()
                }
            )
        )
        return PolicyUsagePseudonymSummary(
            total_entries=int(row.get("total_entries") or 0),
            active_entries=int(row.get("active_entries") or 0),
            retired_entries=int(row.get("retired_entries") or 0),
            alias_strategy_versions=alias_versions,
            salt_version_refs=salt_refs,
        )

    def get_baseline_snapshot(
        self,
        *,
        snapshot_id: str,
    ) -> BaselinePolicySnapshotRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          snapshot_hash,
                          rules_json,
                          created_at,
                          seeded_by
                        FROM baseline_policy_snapshots
                        WHERE id = %(snapshot_id)s
                        """,
                        {"snapshot_id": snapshot_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise PolicyStoreUnavailableError("Baseline policy snapshot lookup failed.") from error

        if row is None:
            return None
        return self._as_baseline_snapshot(row)

    def utcnow(self) -> datetime:
        return datetime.now(UTC)
