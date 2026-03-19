from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from app.core.config import Settings
from app.projects.store import ProjectStore
from app.recovery.models import (
    RecoveryDrillEventRecord,
    RecoveryDrillEventType,
    RecoveryDrillPage,
    RecoveryDrillRecord,
    RecoveryDrillScope,
    RecoveryDrillStatus,
)

_VALID_SCOPES: set[str] = {
    "QUEUE_REPLAY",
    "STORAGE_INTERRUPT",
    "RESTORE_CLEAN_ENV",
    "FULL_RECOVERY",
}
_VALID_STATUSES: set[str] = {"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"}
_VALID_EVENT_TYPES: set[str] = {
    "DRILL_CREATED",
    "DRILL_STARTED",
    "DRILL_FINISHED",
    "DRILL_FAILED",
    "DRILL_CANCELED",
}

RECOVERY_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS recovery_drills (
      id TEXT PRIMARY KEY,
      scope TEXT NOT NULL CHECK (
        scope IN ('QUEUE_REPLAY', 'STORAGE_INTERRUPT', 'RESTORE_CLEAN_ENV', 'FULL_RECOVERY')
      ),
      status TEXT NOT NULL CHECK (
        status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED')
      ),
      started_by TEXT NOT NULL REFERENCES users(id),
      started_at TIMESTAMPTZ,
      finished_at TIMESTAMPTZ,
      canceled_by TEXT REFERENCES users(id),
      canceled_at TIMESTAMPTZ,
      evidence_summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      failure_reason TEXT,
      evidence_storage_key TEXT,
      evidence_storage_sha256 TEXT,
      created_at TIMESTAMPTZ NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL,
      CHECK (jsonb_typeof(evidence_summary_json) = 'object')
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_recovery_drills_created
      ON recovery_drills(created_at DESC, id DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_recovery_drills_status
      ON recovery_drills(status, created_at DESC, id DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS recovery_drill_events (
      id BIGSERIAL PRIMARY KEY,
      drill_id TEXT NOT NULL REFERENCES recovery_drills(id) ON DELETE CASCADE,
      event_type TEXT NOT NULL CHECK (
        event_type IN (
          'DRILL_CREATED',
          'DRILL_STARTED',
          'DRILL_FINISHED',
          'DRILL_FAILED',
          'DRILL_CANCELED'
        )
      ),
      from_status TEXT CHECK (
        from_status IS NULL
        OR from_status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED')
      ),
      to_status TEXT NOT NULL CHECK (
        to_status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED')
      ),
      actor_user_id TEXT REFERENCES users(id),
      details_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      CHECK (jsonb_typeof(details_json) = 'object')
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_recovery_drill_events_drill_created
      ON recovery_drill_events(drill_id, id DESC)
    """,
    """
    CREATE OR REPLACE FUNCTION prevent_recovery_drill_events_mutation()
    RETURNS trigger AS $$
    BEGIN
      RAISE EXCEPTION 'recovery_drill_events is append-only';
    END;
    $$ LANGUAGE plpgsql
    """,
    """
    DROP TRIGGER IF EXISTS trg_recovery_drill_events_no_update ON recovery_drill_events
    """,
    """
    CREATE TRIGGER trg_recovery_drill_events_no_update
    BEFORE UPDATE ON recovery_drill_events
    FOR EACH ROW
    EXECUTE FUNCTION prevent_recovery_drill_events_mutation()
    """,
    """
    DROP TRIGGER IF EXISTS trg_recovery_drill_events_no_delete ON recovery_drill_events
    """,
    """
    CREATE TRIGGER trg_recovery_drill_events_no_delete
    BEFORE DELETE ON recovery_drill_events
    FOR EACH ROW
    EXECUTE FUNCTION prevent_recovery_drill_events_mutation()
    """,
)


class RecoveryStoreUnavailableError(RuntimeError):
    """Recovery persistence is unavailable."""


class RecoveryDrillNotFoundError(RuntimeError):
    """Requested recovery drill was not found."""


class RecoveryDrillTransitionError(RuntimeError):
    """Requested recovery drill transition is invalid."""


class RecoveryStore:
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

    def ensure_schema(self) -> None:
        if self._schema_initialized:
            return
        self._project_store.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    for statement in RECOVERY_SCHEMA_STATEMENTS:
                        cursor.execute(statement)
                connection.commit()
        except psycopg.Error as error:
            raise RecoveryStoreUnavailableError("Recovery schema could not be initialized.") from error
        self._schema_initialized = True

    @staticmethod
    def _assert_scope(value: str) -> RecoveryDrillScope:
        if value not in _VALID_SCOPES:
            raise RecoveryStoreUnavailableError("Unexpected recovery drill scope persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_status(value: str) -> RecoveryDrillStatus:
        if value not in _VALID_STATUSES:
            raise RecoveryStoreUnavailableError("Unexpected recovery drill status persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_event_type(value: str) -> RecoveryDrillEventType:
        if value not in _VALID_EVENT_TYPES:
            raise RecoveryStoreUnavailableError("Unexpected recovery drill event type persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _as_payload(value: object) -> dict[str, object]:
        if isinstance(value, dict):
            return dict(value)
        return {}

    @classmethod
    def _as_drill(cls, row: dict[str, object]) -> RecoveryDrillRecord:
        return RecoveryDrillRecord(
            id=str(row["id"]),
            scope=cls._assert_scope(str(row["scope"])),
            status=cls._assert_status(str(row["status"])),
            started_by=str(row["started_by"]),
            started_at=row.get("started_at"),  # type: ignore[arg-type]
            finished_at=row.get("finished_at"),  # type: ignore[arg-type]
            canceled_by=(str(row["canceled_by"]) if isinstance(row.get("canceled_by"), str) else None),
            canceled_at=row.get("canceled_at"),  # type: ignore[arg-type]
            evidence_summary_json=cls._as_payload(row.get("evidence_summary_json")),
            failure_reason=(str(row["failure_reason"]) if isinstance(row.get("failure_reason"), str) else None),
            evidence_storage_key=(
                str(row["evidence_storage_key"])
                if isinstance(row.get("evidence_storage_key"), str)
                else None
            ),
            evidence_storage_sha256=(
                str(row["evidence_storage_sha256"])
                if isinstance(row.get("evidence_storage_sha256"), str)
                else None
            ),
            created_at=row["created_at"],  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_event(cls, row: dict[str, object]) -> RecoveryDrillEventRecord:
        from_status: RecoveryDrillStatus | None = None
        from_status_raw = row.get("from_status")
        if isinstance(from_status_raw, str):
            from_status = cls._assert_status(from_status_raw)
        return RecoveryDrillEventRecord(
            id=int(row["id"]),
            drill_id=str(row["drill_id"]),
            event_type=cls._assert_event_type(str(row["event_type"])),
            from_status=from_status,
            to_status=cls._assert_status(str(row["to_status"])),
            actor_user_id=(str(row["actor_user_id"]) if isinstance(row.get("actor_user_id"), str) else None),
            details_json=cls._as_payload(row.get("details_json")),
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    def _append_event(
        self,
        *,
        cursor: psycopg.Cursor,
        drill_id: str,
        event_type: RecoveryDrillEventType,
        from_status: RecoveryDrillStatus | None,
        to_status: RecoveryDrillStatus,
        actor_user_id: str | None,
        details: dict[str, object] | None = None,
    ) -> None:
        cursor.execute(
            """
            INSERT INTO recovery_drill_events (
              drill_id,
              event_type,
              from_status,
              to_status,
              actor_user_id,
              details_json
            )
            VALUES (
              %(drill_id)s,
              %(event_type)s,
              %(from_status)s,
              %(to_status)s,
              %(actor_user_id)s,
              %(details_json)s::jsonb
            )
            """,
            {
                "drill_id": drill_id,
                "event_type": event_type,
                "from_status": from_status,
                "to_status": to_status,
                "actor_user_id": actor_user_id,
                "details_json": json.dumps(details or {}, separators=(",", ":"), sort_keys=True),
            },
        )

    def create_drill(self, *, scope: RecoveryDrillScope, started_by: str) -> RecoveryDrillRecord:
        self.ensure_schema()
        now = self.utcnow()
        drill_id = f"recovery-{uuid4()}"
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO recovery_drills (
                          id,
                          scope,
                          status,
                          started_by,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          evidence_summary_json,
                          failure_reason,
                          evidence_storage_key,
                          evidence_storage_sha256,
                          created_at,
                          updated_at
                        )
                        VALUES (
                          %(id)s,
                          %(scope)s,
                          'QUEUED',
                          %(started_by)s,
                          NULL,
                          NULL,
                          NULL,
                          NULL,
                          '{}'::jsonb,
                          NULL,
                          NULL,
                          NULL,
                          %(created_at)s,
                          %(updated_at)s
                        )
                        RETURNING
                          id,
                          scope,
                          status,
                          started_by,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          evidence_summary_json,
                          failure_reason,
                          evidence_storage_key,
                          evidence_storage_sha256,
                          created_at,
                          updated_at
                        """,
                        {
                            "id": drill_id,
                            "scope": scope,
                            "started_by": started_by,
                            "created_at": now,
                            "updated_at": now,
                        },
                    )
                    row = cursor.fetchone()
                    self._append_event(
                        cursor=cursor,
                        drill_id=drill_id,
                        event_type="DRILL_CREATED",
                        from_status=None,
                        to_status="QUEUED",
                        actor_user_id=started_by,
                        details={"scope": scope},
                    )
                connection.commit()
        except psycopg.Error as error:
            raise RecoveryStoreUnavailableError("Recovery drill could not be created.") from error

        if row is None:
            raise RecoveryStoreUnavailableError("Recovery drill creation returned no row.")
        return self._as_drill(row)

    def mark_running(self, *, drill_id: str) -> RecoveryDrillRecord:
        self.ensure_schema()
        now = self.utcnow()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE recovery_drills
                        SET
                          status = 'RUNNING',
                          started_at = COALESCE(started_at, %(started_at)s),
                          failure_reason = NULL,
                          updated_at = %(updated_at)s
                        WHERE id = %(drill_id)s
                          AND status = 'QUEUED'
                        RETURNING
                          id,
                          scope,
                          status,
                          started_by,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          evidence_summary_json,
                          failure_reason,
                          evidence_storage_key,
                          evidence_storage_sha256,
                          created_at,
                          updated_at
                        """,
                        {
                            "drill_id": drill_id,
                            "started_at": now,
                            "updated_at": now,
                        },
                    )
                    row = cursor.fetchone()
                    if row is not None:
                        self._append_event(
                            cursor=cursor,
                            drill_id=drill_id,
                            event_type="DRILL_STARTED",
                            from_status="QUEUED",
                            to_status="RUNNING",
                            actor_user_id=None,
                            details={"started_at": row.get("started_at").isoformat() if row.get("started_at") else None},
                        )
                connection.commit()
        except psycopg.Error as error:
            raise RecoveryStoreUnavailableError("Recovery drill could not enter RUNNING.") from error

        if row is None:
            existing = self.get_drill(drill_id=drill_id)
            if existing.status == "RUNNING":
                return existing
            raise RecoveryDrillTransitionError(
                f"Recovery drill {drill_id} cannot enter RUNNING from {existing.status}."
            )
        return self._as_drill(row)

    def mark_succeeded(
        self,
        *,
        drill_id: str,
        evidence_summary_json: dict[str, object],
        evidence_storage_key: str,
        evidence_storage_sha256: str,
    ) -> RecoveryDrillRecord:
        self.ensure_schema()
        now = self.utcnow()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE recovery_drills
                        SET
                          status = 'SUCCEEDED',
                          finished_at = %(finished_at)s,
                          evidence_summary_json = %(evidence_summary_json)s::jsonb,
                          evidence_storage_key = %(evidence_storage_key)s,
                          evidence_storage_sha256 = %(evidence_storage_sha256)s,
                          failure_reason = NULL,
                          updated_at = %(updated_at)s
                        WHERE id = %(drill_id)s
                          AND status = 'RUNNING'
                        RETURNING
                          id,
                          scope,
                          status,
                          started_by,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          evidence_summary_json,
                          failure_reason,
                          evidence_storage_key,
                          evidence_storage_sha256,
                          created_at,
                          updated_at
                        """,
                        {
                            "drill_id": drill_id,
                            "finished_at": now,
                            "evidence_summary_json": json.dumps(
                                evidence_summary_json,
                                separators=(",", ":"),
                                sort_keys=True,
                            ),
                            "evidence_storage_key": evidence_storage_key,
                            "evidence_storage_sha256": evidence_storage_sha256,
                            "updated_at": now,
                        },
                    )
                    row = cursor.fetchone()
                    if row is not None:
                        self._append_event(
                            cursor=cursor,
                            drill_id=drill_id,
                            event_type="DRILL_FINISHED",
                            from_status="RUNNING",
                            to_status="SUCCEEDED",
                            actor_user_id=None,
                            details={
                                "evidence_storage_key": evidence_storage_key,
                                "evidence_storage_sha256": evidence_storage_sha256,
                            },
                        )
                connection.commit()
        except psycopg.Error as error:
            raise RecoveryStoreUnavailableError("Recovery drill success update failed.") from error

        if row is None:
            existing = self.get_drill(drill_id=drill_id)
            if existing.status == "SUCCEEDED":
                return existing
            raise RecoveryDrillTransitionError(
                f"Recovery drill {drill_id} cannot enter SUCCEEDED from {existing.status}."
            )
        return self._as_drill(row)

    def mark_failed(
        self,
        *,
        drill_id: str,
        failure_reason: str,
        evidence_summary_json: dict[str, object],
        evidence_storage_key: str | None = None,
        evidence_storage_sha256: str | None = None,
    ) -> RecoveryDrillRecord:
        self.ensure_schema()
        now = self.utcnow()
        safe_reason = failure_reason.strip()[:500] if failure_reason.strip() else "Recovery drill failed."
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        WITH prior AS (
                          SELECT status
                          FROM recovery_drills
                          WHERE id = %(drill_id)s
                          FOR UPDATE
                        ),
                        updated AS (
                          UPDATE recovery_drills
                          SET
                            status = 'FAILED',
                            finished_at = %(finished_at)s,
                            evidence_summary_json = %(evidence_summary_json)s::jsonb,
                            evidence_storage_key = %(evidence_storage_key)s,
                            evidence_storage_sha256 = %(evidence_storage_sha256)s,
                            failure_reason = %(failure_reason)s,
                            updated_at = %(updated_at)s
                          WHERE id = %(drill_id)s
                            AND EXISTS (
                              SELECT 1
                              FROM prior
                              WHERE prior.status IN ('QUEUED', 'RUNNING')
                            )
                          RETURNING
                            id,
                            scope,
                            status,
                            started_by,
                            started_at,
                            finished_at,
                            canceled_by,
                            canceled_at,
                            evidence_summary_json,
                            failure_reason,
                            evidence_storage_key,
                            evidence_storage_sha256,
                            created_at,
                            updated_at
                        )
                        SELECT
                          updated.*,
                          prior.status AS previous_status
                        FROM updated, prior
                        """,
                        {
                            "drill_id": drill_id,
                            "finished_at": now,
                            "evidence_summary_json": json.dumps(
                                evidence_summary_json,
                                separators=(",", ":"),
                                sort_keys=True,
                            ),
                            "evidence_storage_key": evidence_storage_key,
                            "evidence_storage_sha256": evidence_storage_sha256,
                            "failure_reason": safe_reason,
                            "updated_at": now,
                        },
                    )
                    row = cursor.fetchone()
                    if row is not None:
                        previous_status_raw = row.get("previous_status")
                        from_status: RecoveryDrillStatus = "RUNNING"
                        if isinstance(previous_status_raw, str) and previous_status_raw in _VALID_STATUSES:
                            from_status = self._assert_status(previous_status_raw)
                        self._append_event(
                            cursor=cursor,
                            drill_id=drill_id,
                            event_type="DRILL_FAILED",
                            from_status=from_status,
                            to_status="FAILED",
                            actor_user_id=None,
                            details={
                                "failure_reason": safe_reason,
                                "evidence_storage_key": evidence_storage_key,
                                "evidence_storage_sha256": evidence_storage_sha256,
                            },
                        )
                connection.commit()
        except psycopg.Error as error:
            raise RecoveryStoreUnavailableError("Recovery drill failure update failed.") from error

        if row is None:
            existing = self.get_drill(drill_id=drill_id)
            if existing.status == "FAILED":
                return existing
            raise RecoveryDrillTransitionError(
                f"Recovery drill {drill_id} cannot enter FAILED from {existing.status}."
            )
        return self._as_drill(row)

    def cancel_drill(self, *, drill_id: str, canceled_by: str) -> RecoveryDrillRecord:
        self.ensure_schema()
        now = self.utcnow()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        WITH prior AS (
                          SELECT status
                          FROM recovery_drills
                          WHERE id = %(drill_id)s
                          FOR UPDATE
                        ),
                        updated AS (
                          UPDATE recovery_drills
                          SET
                            status = 'CANCELED',
                            canceled_by = %(canceled_by)s,
                            canceled_at = %(canceled_at)s,
                            finished_at = COALESCE(finished_at, %(finished_at)s),
                            updated_at = %(updated_at)s
                          WHERE id = %(drill_id)s
                            AND EXISTS (
                              SELECT 1
                              FROM prior
                              WHERE prior.status IN ('QUEUED', 'RUNNING')
                            )
                          RETURNING
                            id,
                            scope,
                            status,
                            started_by,
                            started_at,
                            finished_at,
                            canceled_by,
                            canceled_at,
                            evidence_summary_json,
                            failure_reason,
                            evidence_storage_key,
                            evidence_storage_sha256,
                            created_at,
                            updated_at
                        )
                        SELECT
                          updated.*,
                          prior.status AS previous_status
                        FROM updated, prior
                        """,
                        {
                            "drill_id": drill_id,
                            "canceled_by": canceled_by,
                            "canceled_at": now,
                            "finished_at": now,
                            "updated_at": now,
                        },
                    )
                    row = cursor.fetchone()
                    if row is not None:
                        previous_status_raw = row.get("previous_status")
                        from_status: RecoveryDrillStatus = "RUNNING"
                        if isinstance(previous_status_raw, str) and previous_status_raw in _VALID_STATUSES:
                            from_status = self._assert_status(previous_status_raw)
                        self._append_event(
                            cursor=cursor,
                            drill_id=drill_id,
                            event_type="DRILL_CANCELED",
                            from_status=from_status,
                            to_status="CANCELED",
                            actor_user_id=canceled_by,
                            details={"reason": "manual_cancel"},
                        )
                connection.commit()
        except psycopg.Error as error:
            raise RecoveryStoreUnavailableError("Recovery drill cancellation failed.") from error

        if row is None:
            existing = self.get_drill(drill_id=drill_id)
            if existing.status == "CANCELED":
                return existing
            raise RecoveryDrillTransitionError(
                f"Recovery drill {drill_id} cannot be canceled from {existing.status}."
            )
        return self._as_drill(row)

    def get_drill(self, *, drill_id: str) -> RecoveryDrillRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          scope,
                          status,
                          started_by,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          evidence_summary_json,
                          failure_reason,
                          evidence_storage_key,
                          evidence_storage_sha256,
                          created_at,
                          updated_at
                        FROM recovery_drills
                        WHERE id = %(drill_id)s
                        """,
                        {"drill_id": drill_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise RecoveryStoreUnavailableError("Recovery drill lookup failed.") from error

        if row is None:
            raise RecoveryDrillNotFoundError(f"Recovery drill {drill_id} was not found.")
        return self._as_drill(row)

    def list_drills(self, *, cursor: int, page_size: int) -> RecoveryDrillPage:
        self.ensure_schema()
        limit = page_size + 1
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_obj:
                    cursor_obj.execute(
                        """
                        SELECT
                          id,
                          scope,
                          status,
                          started_by,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          evidence_summary_json,
                          failure_reason,
                          evidence_storage_key,
                          evidence_storage_sha256,
                          created_at,
                          updated_at
                        FROM recovery_drills
                        ORDER BY created_at DESC, id DESC
                        OFFSET %(cursor)s
                        LIMIT %(limit)s
                        """,
                        {"cursor": cursor, "limit": limit},
                    )
                    rows = cursor_obj.fetchall()
        except psycopg.Error as error:
            raise RecoveryStoreUnavailableError("Recovery drill listing failed.") from error

        has_more = len(rows) > page_size
        materialized = rows[:page_size]
        items = [self._as_drill(row) for row in materialized]
        return RecoveryDrillPage(items=items, next_cursor=(cursor + page_size) if has_more else None)

    def list_drill_events(
        self,
        *,
        drill_id: str,
        cursor: int,
        page_size: int,
    ) -> tuple[list[RecoveryDrillEventRecord], int | None]:
        self.ensure_schema()
        limit = page_size + 1
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_obj:
                    cursor_obj.execute(
                        """
                        SELECT
                          id,
                          drill_id,
                          event_type,
                          from_status,
                          to_status,
                          actor_user_id,
                          details_json,
                          created_at
                        FROM recovery_drill_events
                        WHERE drill_id = %(drill_id)s
                        ORDER BY id DESC
                        OFFSET %(cursor)s
                        LIMIT %(limit)s
                        """,
                        {
                            "drill_id": drill_id,
                            "cursor": cursor,
                            "limit": limit,
                        },
                    )
                    rows = cursor_obj.fetchall()
        except psycopg.Error as error:
            raise RecoveryStoreUnavailableError("Recovery drill event listing failed.") from error

        has_more = len(rows) > page_size
        materialized = rows[:page_size]
        items = [self._as_event(row) for row in materialized]
        return items, (cursor + page_size) if has_more else None

    def count_active_drills(self) -> int:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_obj:
                    cursor_obj.execute(
                        """
                        SELECT COUNT(*)::INT AS total
                        FROM recovery_drills
                        WHERE status IN ('QUEUED', 'RUNNING')
                        """
                    )
                    row = cursor_obj.fetchone()
        except psycopg.Error as error:
            raise RecoveryStoreUnavailableError("Recovery active-drill query failed.") from error
        if row is None:
            return 0
        return int(row["total"])
