from __future__ import annotations

from datetime import UTC, datetime

import psycopg
from psycopg.rows import dict_row

from app.core.config import Settings
from app.policies.store import PolicyStore
from app.projects.store import ProjectStore
from app.pseudonyms.models import (
    PseudonymRegistryEntryEventRecord,
    PseudonymRegistryEntryRecord,
)

PSEUDONYM_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS pseudonym_registry_entries (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      source_run_id TEXT NOT NULL,
      source_fingerprint_hmac_sha256 TEXT NOT NULL,
      lineage_source_fingerprint_hmac_sha256 TEXT NOT NULL,
      alias_value TEXT NOT NULL,
      policy_id TEXT NOT NULL REFERENCES redaction_policies(id),
      salt_version_ref TEXT NOT NULL,
      alias_strategy_version TEXT NOT NULL,
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL,
      last_used_run_id TEXT,
      updated_at TIMESTAMPTZ NOT NULL,
      status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'RETIRED')),
      retired_at TIMESTAMPTZ,
      retired_by TEXT REFERENCES users(id),
      supersedes_entry_id TEXT REFERENCES pseudonym_registry_entries(id),
      superseded_by_entry_id TEXT REFERENCES pseudonym_registry_entries(id)
    )
    """,
    """
    ALTER TABLE pseudonym_registry_entries
    ADD COLUMN IF NOT EXISTS lineage_source_fingerprint_hmac_sha256 TEXT
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_pseudonym_registry_active_scope_unique
      ON pseudonym_registry_entries(
        project_id,
        source_fingerprint_hmac_sha256,
        policy_id,
        salt_version_ref,
        alias_strategy_version
      )
      WHERE status = 'ACTIVE'
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_pseudonym_registry_alias_active_scope_unique
      ON pseudonym_registry_entries(
        project_id,
        salt_version_ref,
        alias_strategy_version,
        alias_value
      )
      WHERE status = 'ACTIVE'
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_pseudonym_registry_project_created
      ON pseudonym_registry_entries(project_id, created_at DESC, id DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_pseudonym_registry_fingerprint_policy
      ON pseudonym_registry_entries(
        project_id,
        source_fingerprint_hmac_sha256,
        policy_id,
        updated_at DESC,
        id DESC
      )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_pseudonym_registry_lineage_fingerprint_policy
      ON pseudonym_registry_entries(
        project_id,
        lineage_source_fingerprint_hmac_sha256,
        policy_id,
        updated_at DESC,
        id DESC
      )
    """,
    """
    CREATE TABLE IF NOT EXISTS pseudonym_registry_entry_events (
      id TEXT PRIMARY KEY,
      entry_id TEXT NOT NULL REFERENCES pseudonym_registry_entries(id) ON DELETE CASCADE,
      event_type TEXT NOT NULL CHECK (
        event_type IN (
          'ENTRY_CREATED',
          'ENTRY_REUSED',
          'ENTRY_RETIRED'
        )
      ),
      run_id TEXT NOT NULL,
      actor_user_id TEXT REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_pseudonym_registry_events_entry_created
      ON pseudonym_registry_entry_events(entry_id, created_at ASC, id ASC)
    """,
)


class PseudonymRegistryStoreUnavailableError(RuntimeError):
    """Pseudonym registry persistence could not be reached."""


class PseudonymRegistryStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._project_store = ProjectStore(settings)
        self._policy_store = PolicyStore(settings)
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
    def _as_entry(row: dict[str, object]) -> PseudonymRegistryEntryRecord:
        return PseudonymRegistryEntryRecord(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            source_run_id=str(row["source_run_id"]),
            source_fingerprint_hmac_sha256=str(row["source_fingerprint_hmac_sha256"]),
            alias_value=str(row["alias_value"]),
            policy_id=str(row["policy_id"]),
            salt_version_ref=str(row["salt_version_ref"]),
            alias_strategy_version=str(row["alias_strategy_version"]),
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
            last_used_run_id=(
                str(row["last_used_run_id"])
                if isinstance(row.get("last_used_run_id"), str)
                else None
            ),
            updated_at=row["updated_at"],  # type: ignore[arg-type]
            status=str(row["status"]),  # type: ignore[arg-type]
            retired_at=row.get("retired_at"),  # type: ignore[arg-type]
            retired_by=(
                str(row["retired_by"]) if isinstance(row.get("retired_by"), str) else None
            ),
            supersedes_entry_id=(
                str(row["supersedes_entry_id"])
                if isinstance(row.get("supersedes_entry_id"), str)
                else None
            ),
            superseded_by_entry_id=(
                str(row["superseded_by_entry_id"])
                if isinstance(row.get("superseded_by_entry_id"), str)
                else None
            ),
        )

    @staticmethod
    def _as_event(row: dict[str, object]) -> PseudonymRegistryEntryEventRecord:
        return PseudonymRegistryEntryEventRecord(
            id=str(row["id"]),
            entry_id=str(row["entry_id"]),
            event_type=str(row["event_type"]),  # type: ignore[arg-type]
            run_id=str(row["run_id"]),
            actor_user_id=(
                str(row["actor_user_id"])
                if isinstance(row.get("actor_user_id"), str)
                else None
            ),
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    def ensure_schema(self) -> None:
        if self._schema_initialized:
            return

        try:
            self._project_store.ensure_schema()
            self._policy_store.ensure_schema()
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    for statement in PSEUDONYM_SCHEMA_STATEMENTS:
                        cursor.execute(statement)
                connection.commit()
        except psycopg.Error as error:
            raise PseudonymRegistryStoreUnavailableError(
                "Pseudonym registry schema could not be initialized."
            ) from error

        self._schema_initialized = True

    def list_entries(
        self,
        *,
        project_id: str,
    ) -> list[PseudonymRegistryEntryRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          source_run_id,
                          source_fingerprint_hmac_sha256,
                          alias_value,
                          policy_id,
                          salt_version_ref,
                          alias_strategy_version,
                          created_by,
                          created_at,
                          last_used_run_id,
                          updated_at,
                          status,
                          retired_at,
                          retired_by,
                          supersedes_entry_id,
                          superseded_by_entry_id
                        FROM pseudonym_registry_entries
                        WHERE project_id = %(project_id)s
                        ORDER BY created_at DESC, id DESC
                        """,
                        {"project_id": project_id},
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise PseudonymRegistryStoreUnavailableError(
                "Pseudonym registry listing failed."
            ) from error

        return [self._as_entry(row) for row in rows]

    def get_entry(
        self,
        *,
        project_id: str,
        entry_id: str,
    ) -> PseudonymRegistryEntryRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          source_run_id,
                          source_fingerprint_hmac_sha256,
                          alias_value,
                          policy_id,
                          salt_version_ref,
                          alias_strategy_version,
                          created_by,
                          created_at,
                          last_used_run_id,
                          updated_at,
                          status,
                          retired_at,
                          retired_by,
                          supersedes_entry_id,
                          superseded_by_entry_id
                        FROM pseudonym_registry_entries
                        WHERE project_id = %(project_id)s
                          AND id = %(entry_id)s
                        """,
                        {"project_id": project_id, "entry_id": entry_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise PseudonymRegistryStoreUnavailableError(
                "Pseudonym registry lookup failed."
            ) from error

        if row is None:
            return None
        return self._as_entry(row)

    def find_active_entry_by_tuple(
        self,
        *,
        project_id: str,
        source_fingerprint_hmac_sha256: str,
        policy_id: str,
        salt_version_ref: str,
        alias_strategy_version: str,
    ) -> PseudonymRegistryEntryRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          source_run_id,
                          source_fingerprint_hmac_sha256,
                          alias_value,
                          policy_id,
                          salt_version_ref,
                          alias_strategy_version,
                          created_by,
                          created_at,
                          last_used_run_id,
                          updated_at,
                          status,
                          retired_at,
                          retired_by,
                          supersedes_entry_id,
                          superseded_by_entry_id
                        FROM pseudonym_registry_entries
                        WHERE project_id = %(project_id)s
                          AND source_fingerprint_hmac_sha256 = %(source_fingerprint_hmac_sha256)s
                          AND policy_id = %(policy_id)s
                          AND salt_version_ref = %(salt_version_ref)s
                          AND alias_strategy_version = %(alias_strategy_version)s
                          AND status = 'ACTIVE'
                        ORDER BY created_at DESC, id DESC
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "source_fingerprint_hmac_sha256": source_fingerprint_hmac_sha256,
                            "policy_id": policy_id,
                            "salt_version_ref": salt_version_ref,
                            "alias_strategy_version": alias_strategy_version,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise PseudonymRegistryStoreUnavailableError(
                "Pseudonym registry tuple lookup failed."
            ) from error

        if row is None:
            return None
        return self._as_entry(row)

    def find_active_entry_by_alias_scope(
        self,
        *,
        project_id: str,
        salt_version_ref: str,
        alias_strategy_version: str,
        alias_value: str,
    ) -> PseudonymRegistryEntryRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          source_run_id,
                          source_fingerprint_hmac_sha256,
                          alias_value,
                          policy_id,
                          salt_version_ref,
                          alias_strategy_version,
                          created_by,
                          created_at,
                          last_used_run_id,
                          updated_at,
                          status,
                          retired_at,
                          retired_by,
                          supersedes_entry_id,
                          superseded_by_entry_id
                        FROM pseudonym_registry_entries
                        WHERE project_id = %(project_id)s
                          AND salt_version_ref = %(salt_version_ref)s
                          AND alias_strategy_version = %(alias_strategy_version)s
                          AND alias_value = %(alias_value)s
                          AND status = 'ACTIVE'
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "salt_version_ref": salt_version_ref,
                            "alias_strategy_version": alias_strategy_version,
                            "alias_value": alias_value,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise PseudonymRegistryStoreUnavailableError(
                "Pseudonym registry alias lookup failed."
            ) from error

        if row is None:
            return None
        return self._as_entry(row)

    def find_latest_lineage_predecessor(
        self,
        *,
        project_id: str,
        lineage_source_fingerprint_hmac_sha256: str,
        policy_id: str,
        salt_version_ref: str,
        alias_strategy_version: str,
    ) -> PseudonymRegistryEntryRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          source_run_id,
                          source_fingerprint_hmac_sha256,
                          alias_value,
                          policy_id,
                          salt_version_ref,
                          alias_strategy_version,
                          created_by,
                          created_at,
                          last_used_run_id,
                          updated_at,
                          status,
                          retired_at,
                          retired_by,
                          supersedes_entry_id,
                          superseded_by_entry_id
                        FROM pseudonym_registry_entries
                        WHERE project_id = %(project_id)s
                          AND lineage_source_fingerprint_hmac_sha256 = %(
                            lineage_source_fingerprint_hmac_sha256
                          )s
                          AND policy_id = %(policy_id)s
                          AND (
                            salt_version_ref <> %(salt_version_ref)s
                            OR alias_strategy_version <> %(alias_strategy_version)s
                          )
                        ORDER BY updated_at DESC, created_at DESC, id DESC
                        LIMIT 1
                        """,
                        {
                            "project_id": project_id,
                            "lineage_source_fingerprint_hmac_sha256": (
                                lineage_source_fingerprint_hmac_sha256
                            ),
                            "policy_id": policy_id,
                            "salt_version_ref": salt_version_ref,
                            "alias_strategy_version": alias_strategy_version,
                        },
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise PseudonymRegistryStoreUnavailableError(
                "Pseudonym lineage lookup failed."
            ) from error

        if row is None:
            return None
        return self._as_entry(row)

    def create_entry(
        self,
        *,
        record: PseudonymRegistryEntryRecord,
        lineage_source_fingerprint_hmac_sha256: str,
    ) -> None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO pseudonym_registry_entries (
                          id,
                          project_id,
                          source_run_id,
                          source_fingerprint_hmac_sha256,
                          lineage_source_fingerprint_hmac_sha256,
                          alias_value,
                          policy_id,
                          salt_version_ref,
                          alias_strategy_version,
                          created_by,
                          created_at,
                          last_used_run_id,
                          updated_at,
                          status,
                          retired_at,
                          retired_by,
                          supersedes_entry_id,
                          superseded_by_entry_id
                        )
                        VALUES (
                          %(id)s,
                          %(project_id)s,
                          %(source_run_id)s,
                          %(source_fingerprint_hmac_sha256)s,
                          %(lineage_source_fingerprint_hmac_sha256)s,
                          %(alias_value)s,
                          %(policy_id)s,
                          %(salt_version_ref)s,
                          %(alias_strategy_version)s,
                          %(created_by)s,
                          %(created_at)s,
                          %(last_used_run_id)s,
                          %(updated_at)s,
                          %(status)s,
                          %(retired_at)s,
                          %(retired_by)s,
                          %(supersedes_entry_id)s,
                          %(superseded_by_entry_id)s
                        )
                        """,
                        {
                            "id": record.id,
                            "project_id": record.project_id,
                            "source_run_id": record.source_run_id,
                            "source_fingerprint_hmac_sha256": record.source_fingerprint_hmac_sha256,
                            "lineage_source_fingerprint_hmac_sha256": (
                                lineage_source_fingerprint_hmac_sha256
                            ),
                            "alias_value": record.alias_value,
                            "policy_id": record.policy_id,
                            "salt_version_ref": record.salt_version_ref,
                            "alias_strategy_version": record.alias_strategy_version,
                            "created_by": record.created_by,
                            "created_at": record.created_at,
                            "last_used_run_id": record.last_used_run_id,
                            "updated_at": record.updated_at,
                            "status": record.status,
                            "retired_at": record.retired_at,
                            "retired_by": record.retired_by,
                            "supersedes_entry_id": record.supersedes_entry_id,
                            "superseded_by_entry_id": record.superseded_by_entry_id,
                        },
                    )
                connection.commit()
        except psycopg.Error as error:
            raise PseudonymRegistryStoreUnavailableError(
                "Pseudonym entry create failed."
            ) from error

    def touch_entry_usage(
        self,
        *,
        project_id: str,
        entry_id: str,
        last_used_run_id: str,
        updated_at: datetime,
    ) -> PseudonymRegistryEntryRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE pseudonym_registry_entries
                        SET
                          last_used_run_id = %(last_used_run_id)s,
                          updated_at = %(updated_at)s
                        WHERE project_id = %(project_id)s
                          AND id = %(entry_id)s
                          AND status = 'ACTIVE'
                        RETURNING
                          id,
                          project_id,
                          source_run_id,
                          source_fingerprint_hmac_sha256,
                          alias_value,
                          policy_id,
                          salt_version_ref,
                          alias_strategy_version,
                          created_by,
                          created_at,
                          last_used_run_id,
                          updated_at,
                          status,
                          retired_at,
                          retired_by,
                          supersedes_entry_id,
                          superseded_by_entry_id
                        """,
                        {
                            "project_id": project_id,
                            "entry_id": entry_id,
                            "last_used_run_id": last_used_run_id,
                            "updated_at": updated_at,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise PseudonymRegistryStoreUnavailableError(
                "Pseudonym entry usage update failed."
            ) from error

        if row is None:
            return None
        return self._as_entry(row)

    def set_superseded_by(
        self,
        *,
        project_id: str,
        entry_id: str,
        superseded_by_entry_id: str,
    ) -> None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE pseudonym_registry_entries
                        SET superseded_by_entry_id = %(superseded_by_entry_id)s
                        WHERE project_id = %(project_id)s
                          AND id = %(entry_id)s
                          AND superseded_by_entry_id IS NULL
                        """,
                        {
                            "project_id": project_id,
                            "entry_id": entry_id,
                            "superseded_by_entry_id": superseded_by_entry_id,
                        },
                    )
                connection.commit()
        except psycopg.Error as error:
            raise PseudonymRegistryStoreUnavailableError(
                "Pseudonym lineage update failed."
            ) from error

    def retire_entry(
        self,
        *,
        project_id: str,
        entry_id: str,
        retired_by: str,
        retired_at: datetime,
    ) -> PseudonymRegistryEntryRecord | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE pseudonym_registry_entries
                        SET
                          status = 'RETIRED',
                          retired_by = %(retired_by)s,
                          retired_at = %(retired_at)s,
                          updated_at = %(retired_at)s
                        WHERE project_id = %(project_id)s
                          AND id = %(entry_id)s
                          AND status = 'ACTIVE'
                        RETURNING
                          id,
                          project_id,
                          source_run_id,
                          source_fingerprint_hmac_sha256,
                          alias_value,
                          policy_id,
                          salt_version_ref,
                          alias_strategy_version,
                          created_by,
                          created_at,
                          last_used_run_id,
                          updated_at,
                          status,
                          retired_at,
                          retired_by,
                          supersedes_entry_id,
                          superseded_by_entry_id
                        """,
                        {
                            "project_id": project_id,
                            "entry_id": entry_id,
                            "retired_by": retired_by,
                            "retired_at": retired_at,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise PseudonymRegistryStoreUnavailableError(
                "Pseudonym entry retirement failed."
            ) from error

        if row is None:
            return None
        return self._as_entry(row)

    def append_event(self, *, event: PseudonymRegistryEntryEventRecord) -> None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO pseudonym_registry_entry_events (
                          id,
                          entry_id,
                          event_type,
                          run_id,
                          actor_user_id,
                          created_at
                        )
                        VALUES (
                          %(id)s,
                          %(entry_id)s,
                          %(event_type)s,
                          %(run_id)s,
                          %(actor_user_id)s,
                          %(created_at)s
                        )
                        """,
                        {
                            "id": event.id,
                            "entry_id": event.entry_id,
                            "event_type": event.event_type,
                            "run_id": event.run_id,
                            "actor_user_id": event.actor_user_id,
                            "created_at": event.created_at,
                        },
                    )
                connection.commit()
        except psycopg.Error as error:
            raise PseudonymRegistryStoreUnavailableError(
                "Pseudonym registry event append failed."
            ) from error

    def list_entry_events(
        self,
        *,
        project_id: str,
        entry_id: str,
    ) -> list[PseudonymRegistryEntryEventRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          e.id,
                          e.entry_id,
                          e.event_type,
                          e.run_id,
                          e.actor_user_id,
                          e.created_at
                        FROM pseudonym_registry_entry_events AS e
                        INNER JOIN pseudonym_registry_entries AS p
                          ON p.id = e.entry_id
                        WHERE p.project_id = %(project_id)s
                          AND e.entry_id = %(entry_id)s
                        ORDER BY e.created_at ASC, e.id ASC
                        """,
                        {"project_id": project_id, "entry_id": entry_id},
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise PseudonymRegistryStoreUnavailableError(
                "Pseudonym registry event listing failed."
            ) from error

        return [self._as_event(row) for row in rows]

    def utcnow(self) -> datetime:
        return datetime.now(UTC)
