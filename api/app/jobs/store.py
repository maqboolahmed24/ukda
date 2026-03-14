import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from app.core.config import Settings
from app.jobs.models import JobEventRecord, JobEventType, JobRecord, JobStatus, JobType
from app.projects.store import ProjectStore

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_VALID_STATUSES: set[str] = {"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"}
_VALID_TYPES: set[str] = {
    "NOOP",
    "EXTRACT_PAGES",
    "RENDER_THUMBNAILS",
    "PREPROCESS_DOCUMENT",
    "PREPROCESS_PAGE",
    "FINALIZE_PREPROCESS_RUN",
    "LAYOUT_ANALYZE_DOCUMENT",
    "LAYOUT_ANALYZE_PAGE",
    "FINALIZE_LAYOUT_RUN",
    "TRANSCRIBE_DOCUMENT",
    "TRANSCRIBE_PAGE",
    "FINALIZE_TRANSCRIPTION_RUN",
}
_VALID_EVENT_TYPES: set[str] = {
    "JOB_CREATED",
    "JOB_STARTED",
    "JOB_SUCCEEDED",
    "JOB_FAILED",
    "JOB_CANCELED",
    "JOB_RETRY_APPENDED",
}

JOB_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS jobs (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
      supersedes_job_id TEXT REFERENCES jobs(id),
      superseded_by_job_id TEXT REFERENCES jobs(id),
      type TEXT NOT NULL CHECK (
        type IN (
          'NOOP',
          'EXTRACT_PAGES',
          'RENDER_THUMBNAILS',
          'PREPROCESS_DOCUMENT',
          'PREPROCESS_PAGE',
          'FINALIZE_PREPROCESS_RUN',
          'LAYOUT_ANALYZE_DOCUMENT',
          'LAYOUT_ANALYZE_PAGE',
          'FINALIZE_LAYOUT_RUN',
          'TRANSCRIBE_DOCUMENT',
          'TRANSCRIBE_PAGE',
          'FINALIZE_TRANSCRIPTION_RUN'
        )
      ),
      dedupe_key TEXT NOT NULL,
      status TEXT NOT NULL CHECK (
        status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED')
      ),
      attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
      max_attempts INTEGER NOT NULL CHECK (max_attempts >= 1),
      payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      started_at TIMESTAMPTZ,
      finished_at TIMESTAMPTZ,
      canceled_by TEXT REFERENCES users(id),
      canceled_at TIMESTAMPTZ,
      error_code TEXT,
      error_message TEXT,
      cancel_requested_by TEXT REFERENCES users(id),
      cancel_requested_at TIMESTAMPTZ,
      lease_owner_id TEXT,
      lease_expires_at TIMESTAMPTZ,
      last_heartbeat_at TIMESTAMPTZ,
      CHECK (jsonb_typeof(payload_json) = 'object')
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_jobs_project_created_at
      ON jobs(project_id, created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_jobs_project_status
      ON jobs(project_id, status, created_at DESC)
    """,
    """
    ALTER TABLE jobs
    DROP CONSTRAINT IF EXISTS jobs_type_check
    """,
    """
    ALTER TABLE jobs
    ADD CONSTRAINT jobs_type_check CHECK (
      type IN (
        'NOOP',
        'EXTRACT_PAGES',
        'RENDER_THUMBNAILS',
        'PREPROCESS_DOCUMENT',
        'PREPROCESS_PAGE',
        'FINALIZE_PREPROCESS_RUN',
        'LAYOUT_ANALYZE_DOCUMENT',
        'LAYOUT_ANALYZE_PAGE',
        'FINALIZE_LAYOUT_RUN',
        'TRANSCRIBE_DOCUMENT',
        'TRANSCRIBE_PAGE',
        'FINALIZE_TRANSCRIPTION_RUN'
      )
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_jobs_dedupe_lookup
      ON jobs(project_id, dedupe_key, status, created_at DESC)
      WHERE superseded_by_job_id IS NULL
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_jobs_running_lease
      ON jobs(status, lease_expires_at)
      WHERE status = 'RUNNING'
    """,
    """
    CREATE TABLE IF NOT EXISTS job_events (
      id BIGSERIAL PRIMARY KEY,
      job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      event_type TEXT NOT NULL CHECK (
        event_type IN (
          'JOB_CREATED',
          'JOB_STARTED',
          'JOB_SUCCEEDED',
          'JOB_FAILED',
          'JOB_CANCELED',
          'JOB_RETRY_APPENDED'
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
    CREATE INDEX IF NOT EXISTS idx_job_events_job_id
      ON job_events(job_id, id DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_job_events_project_id
      ON job_events(project_id, id DESC)
    """,
    """
    CREATE OR REPLACE FUNCTION prevent_job_events_mutation()
    RETURNS trigger AS $$
    BEGIN
      RAISE EXCEPTION 'job_events is append-only';
    END;
    $$ LANGUAGE plpgsql
    """,
    """
    DROP TRIGGER IF EXISTS trg_job_events_no_update ON job_events
    """,
    """
    CREATE TRIGGER trg_job_events_no_update
    BEFORE UPDATE ON job_events
    FOR EACH ROW
    EXECUTE FUNCTION prevent_job_events_mutation()
    """,
    """
    DROP TRIGGER IF EXISTS trg_job_events_no_delete ON job_events
    """,
    """
    CREATE TRIGGER trg_job_events_no_delete
    BEFORE DELETE ON job_events
    FOR EACH ROW
    EXECUTE FUNCTION prevent_job_events_mutation()
    """,
)


class JobStoreUnavailableError(RuntimeError):
    """Jobs persistence could not be reached."""


class JobNotFoundError(RuntimeError):
    """Job was not found."""


class JobTransitionError(RuntimeError):
    """Requested transition is invalid for the current job state."""


class JobRetryConflictError(RuntimeError):
    """Retry cannot be applied to the selected job row."""


class JobStore:
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

    def ensure_schema(self) -> None:
        if self._schema_initialized:
            return

        self._project_store.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    for statement in JOB_SCHEMA_STATEMENTS:
                        cursor.execute(statement)
                connection.commit()
        except psycopg.Error as error:
            raise JobStoreUnavailableError("Jobs schema could not be initialized.") from error

        self._schema_initialized = True

    @staticmethod
    def _assert_status(value: str) -> JobStatus:
        if value not in _VALID_STATUSES:
            raise JobStoreUnavailableError("Unexpected job status persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_type(value: str) -> JobType:
        if value not in _VALID_TYPES:
            raise JobStoreUnavailableError("Unexpected job type persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_event_type(value: str) -> JobEventType:
        if value not in _VALID_EVENT_TYPES:
            raise JobStoreUnavailableError("Unexpected job event type persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _as_payload(value: object) -> dict[str, object]:
        if isinstance(value, dict):
            return value
        return {}

    @classmethod
    def _as_job(cls, row: dict[str, object]) -> JobRecord:
        return JobRecord(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            attempt_number=int(row["attempt_number"]),
            supersedes_job_id=row["supersedes_job_id"],  # type: ignore[arg-type]
            superseded_by_job_id=row["superseded_by_job_id"],  # type: ignore[arg-type]
            type=cls._assert_type(str(row["type"])),
            dedupe_key=str(row["dedupe_key"]),
            status=cls._assert_status(str(row["status"])),
            attempts=int(row["attempts"]),
            max_attempts=int(row["max_attempts"]),
            payload_json=cls._as_payload(row["payload_json"]),
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
            started_at=row["started_at"],  # type: ignore[arg-type]
            finished_at=row["finished_at"],  # type: ignore[arg-type]
            canceled_by=row["canceled_by"],  # type: ignore[arg-type]
            canceled_at=row["canceled_at"],  # type: ignore[arg-type]
            error_code=row["error_code"],  # type: ignore[arg-type]
            error_message=row["error_message"],  # type: ignore[arg-type]
            cancel_requested_by=row["cancel_requested_by"],  # type: ignore[arg-type]
            cancel_requested_at=row["cancel_requested_at"],  # type: ignore[arg-type]
            lease_owner_id=row["lease_owner_id"],  # type: ignore[arg-type]
            lease_expires_at=row["lease_expires_at"],  # type: ignore[arg-type]
            last_heartbeat_at=row["last_heartbeat_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_job_event(cls, row: dict[str, object]) -> JobEventRecord:
        from_status_raw = row["from_status"]
        from_status: JobStatus | None = None
        if isinstance(from_status_raw, str):
            from_status = cls._assert_status(from_status_raw)
        return JobEventRecord(
            id=int(row["id"]),
            job_id=str(row["job_id"]),
            project_id=str(row["project_id"]),
            event_type=cls._assert_event_type(str(row["event_type"])),
            from_status=from_status,
            to_status=cls._assert_status(str(row["to_status"])),
            actor_user_id=row["actor_user_id"],  # type: ignore[arg-type]
            details_json=cls._as_payload(row["details_json"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    @staticmethod
    def sanitize_error_message(message: str | None) -> str | None:
        if message is None:
            return None
        collapsed = _CONTROL_CHARS_RE.sub(" ", message)
        collapsed = collapsed.replace("\n", " ").replace("\r", " ").replace("\t", " ")
        collapsed = " ".join(collapsed.split())
        if not collapsed:
            return None
        return collapsed[:500]

    @staticmethod
    def compute_dedupe_key(
        *,
        project_id: str,
        job_type: JobType,
        logical_key: str,
    ) -> str:
        canonical = f"{project_id}|{job_type}|{logical_key.strip()}".encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def _get_job_for_update(
        self,
        *,
        cursor: psycopg.Cursor,
        project_id: str,
        job_id: str,
    ) -> JobRecord:
        cursor.execute(
            """
            SELECT
              id,
              project_id,
              attempt_number,
              supersedes_job_id,
              superseded_by_job_id,
              type,
              dedupe_key,
              status,
              attempts,
              max_attempts,
              payload_json,
              created_by,
              created_at,
              started_at,
              finished_at,
              canceled_by,
              canceled_at,
              error_code,
              error_message,
              cancel_requested_by,
              cancel_requested_at,
              lease_owner_id,
              lease_expires_at,
              last_heartbeat_at
            FROM jobs
            WHERE project_id = %(project_id)s
              AND id = %(job_id)s
            FOR UPDATE
            """,
            {"project_id": project_id, "job_id": job_id},
        )
        row = cursor.fetchone()
        if row is None:
            raise JobNotFoundError("Job not found.")
        return self._as_job(row)

    def _append_job_event(
        self,
        *,
        cursor: psycopg.Cursor,
        job_id: str,
        project_id: str,
        event_type: JobEventType,
        from_status: JobStatus | None,
        to_status: JobStatus,
        actor_user_id: str | None,
        details: dict[str, object] | None = None,
    ) -> None:
        payload = details or {}
        cursor.execute(
            """
            INSERT INTO job_events (
              job_id,
              project_id,
              event_type,
              from_status,
              to_status,
              actor_user_id,
              details_json
            )
            VALUES (
              %(job_id)s,
              %(project_id)s,
              %(event_type)s,
              %(from_status)s,
              %(to_status)s,
              %(actor_user_id)s,
              %(details_json)s::jsonb
            )
            """,
            {
                "job_id": job_id,
                "project_id": project_id,
                "event_type": event_type,
                "from_status": from_status,
                "to_status": to_status,
                "actor_user_id": actor_user_id,
                "details_json": json.dumps(payload, separators=(",", ":"), sort_keys=True),
            },
        )

    def _read_job(
        self,
        *,
        cursor: psycopg.Cursor,
        project_id: str,
        job_id: str,
    ) -> JobRecord:
        cursor.execute(
            """
            SELECT
              id,
              project_id,
              attempt_number,
              supersedes_job_id,
              superseded_by_job_id,
              type,
              dedupe_key,
              status,
              attempts,
              max_attempts,
              payload_json,
              created_by,
              created_at,
              started_at,
              finished_at,
              canceled_by,
              canceled_at,
              error_code,
              error_message,
              cancel_requested_by,
              cancel_requested_at,
              lease_owner_id,
              lease_expires_at,
              last_heartbeat_at
            FROM jobs
            WHERE project_id = %(project_id)s
              AND id = %(job_id)s
            """,
            {"project_id": project_id, "job_id": job_id},
        )
        row = cursor.fetchone()
        if row is None:
            raise JobNotFoundError("Job not found.")
        return self._as_job(row)

    def list_project_jobs(
        self,
        *,
        project_id: str,
        cursor: int,
        page_size: int,
    ) -> tuple[list[JobRecord], int | None]:
        self.ensure_schema()
        safe_cursor = max(0, cursor)
        safe_page_size = max(1, min(page_size, 200))
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_obj:
                    cursor_obj.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          attempt_number,
                          supersedes_job_id,
                          superseded_by_job_id,
                          type,
                          dedupe_key,
                          status,
                          attempts,
                          max_attempts,
                          payload_json,
                          created_by,
                          created_at,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          error_code,
                          error_message,
                          cancel_requested_by,
                          cancel_requested_at,
                          lease_owner_id,
                          lease_expires_at,
                          last_heartbeat_at
                        FROM jobs
                        WHERE project_id = %(project_id)s
                        ORDER BY created_at DESC, id DESC
                        OFFSET %(cursor)s
                        LIMIT %(limit)s
                        """,
                        {
                            "project_id": project_id,
                            "cursor": safe_cursor,
                            "limit": safe_page_size + 1,
                        },
                    )
                    rows = cursor_obj.fetchall()
        except psycopg.Error as error:
            raise JobStoreUnavailableError("Job listing failed.") from error

        items = [self._as_job(row) for row in rows[:safe_page_size]]
        has_more = len(rows) > safe_page_size
        next_cursor = safe_cursor + safe_page_size if has_more else None
        return items, next_cursor

    def list_job_events(
        self,
        *,
        project_id: str,
        job_id: str,
        cursor: int,
        page_size: int,
    ) -> tuple[list[JobEventRecord], int | None]:
        self.ensure_schema()
        safe_cursor = max(0, cursor)
        safe_page_size = max(1, min(page_size, 200))
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_obj:
                    cursor_obj.execute(
                        """
                        SELECT
                          id,
                          job_id,
                          project_id,
                          event_type,
                          from_status,
                          to_status,
                          actor_user_id,
                          details_json,
                          created_at
                        FROM job_events
                        WHERE project_id = %(project_id)s
                          AND job_id = %(job_id)s
                        ORDER BY id ASC
                        OFFSET %(cursor)s
                        LIMIT %(limit)s
                        """,
                        {
                            "project_id": project_id,
                            "job_id": job_id,
                            "cursor": safe_cursor,
                            "limit": safe_page_size + 1,
                        },
                    )
                    rows = cursor_obj.fetchall()
        except psycopg.Error as error:
            raise JobStoreUnavailableError("Job events listing failed.") from error

        items = [self._as_job_event(row) for row in rows[:safe_page_size]]
        has_more = len(rows) > safe_page_size
        next_cursor = safe_cursor + safe_page_size if has_more else None
        return items, next_cursor

    def get_job(self, *, project_id: str, job_id: str) -> JobRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_obj:
                    return self._read_job(
                        cursor=cursor_obj,
                        project_id=project_id,
                        job_id=job_id,
                    )
        except JobNotFoundError:
            raise
        except psycopg.Error as error:
            raise JobStoreUnavailableError("Job lookup failed.") from error

    def get_job_status(self, *, project_id: str, job_id: str) -> JobRecord:
        return self.get_job(project_id=project_id, job_id=job_id)

    def enqueue_job(
        self,
        *,
        project_id: str,
        job_type: JobType,
        dedupe_key: str,
        payload_json: dict[str, object],
        created_by: str,
        max_attempts: int,
        supersedes_job_id: str | None = None,
        event_type: JobEventType = "JOB_CREATED",
    ) -> tuple[JobRecord, bool, str]:
        self.ensure_schema()
        if max_attempts < 1:
            raise JobTransitionError("max_attempts must be at least 1.")

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_obj:
                    lock_key = f"jobs|{project_id}|{dedupe_key}"
                    cursor_obj.execute(
                        "SELECT pg_advisory_xact_lock(hashtext(%(lock_key)s))",
                        {"lock_key": lock_key},
                    )
                    cursor_obj.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          attempt_number,
                          supersedes_job_id,
                          superseded_by_job_id,
                          type,
                          dedupe_key,
                          status,
                          attempts,
                          max_attempts,
                          payload_json,
                          created_by,
                          created_at,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          error_code,
                          error_message,
                          cancel_requested_by,
                          cancel_requested_at,
                          lease_owner_id,
                          lease_expires_at,
                          last_heartbeat_at
                        FROM jobs
                        WHERE project_id = %(project_id)s
                          AND dedupe_key = %(dedupe_key)s
                          AND superseded_by_job_id IS NULL
                          AND status IN ('QUEUED', 'RUNNING')
                        ORDER BY created_at DESC, id DESC
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {"project_id": project_id, "dedupe_key": dedupe_key},
                    )
                    in_flight_row = cursor_obj.fetchone()
                    if in_flight_row is not None:
                        connection.commit()
                        return self._as_job(in_flight_row), False, "IN_FLIGHT"

                    cursor_obj.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          attempt_number,
                          supersedes_job_id,
                          superseded_by_job_id,
                          type,
                          dedupe_key,
                          status,
                          attempts,
                          max_attempts,
                          payload_json,
                          created_by,
                          created_at,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          error_code,
                          error_message,
                          cancel_requested_by,
                          cancel_requested_at,
                          lease_owner_id,
                          lease_expires_at,
                          last_heartbeat_at
                        FROM jobs
                        WHERE project_id = %(project_id)s
                          AND dedupe_key = %(dedupe_key)s
                          AND superseded_by_job_id IS NULL
                          AND status = 'SUCCEEDED'
                        ORDER BY created_at DESC, id DESC
                        LIMIT 1
                        FOR UPDATE
                        """,
                        {"project_id": project_id, "dedupe_key": dedupe_key},
                    )
                    succeeded_row = cursor_obj.fetchone()
                    if succeeded_row is not None:
                        connection.commit()
                        return self._as_job(succeeded_row), False, "SUCCEEDED"

                    attempt_number = 1
                    supersedes: JobRecord | None = None
                    if supersedes_job_id is not None:
                        supersedes = self._get_job_for_update(
                            cursor=cursor_obj,
                            project_id=project_id,
                            job_id=supersedes_job_id,
                        )
                        attempt_number = supersedes.attempt_number + 1

                    job_id = str(uuid4())
                    cursor_obj.execute(
                        """
                        INSERT INTO jobs (
                          id,
                          project_id,
                          attempt_number,
                          supersedes_job_id,
                          type,
                          dedupe_key,
                          status,
                          attempts,
                          max_attempts,
                          payload_json,
                          created_by
                        )
                        VALUES (
                          %(id)s,
                          %(project_id)s,
                          %(attempt_number)s,
                          %(supersedes_job_id)s,
                          %(type)s,
                          %(dedupe_key)s,
                          'QUEUED',
                          0,
                          %(max_attempts)s,
                          %(payload_json)s::jsonb,
                          %(created_by)s
                        )
                        """,
                        {
                            "id": job_id,
                            "project_id": project_id,
                            "attempt_number": attempt_number,
                            "supersedes_job_id": supersedes_job_id,
                            "type": job_type,
                            "dedupe_key": dedupe_key,
                            "max_attempts": max_attempts,
                            "payload_json": json.dumps(
                                payload_json,
                                separators=(",", ":"),
                                sort_keys=True,
                            ),
                            "created_by": created_by,
                        },
                    )

                    if supersedes is not None:
                        if supersedes.superseded_by_job_id is not None:
                            raise JobRetryConflictError(
                                "Retry target is already superseded; retry the latest attempt row."
                            )
                        cursor_obj.execute(
                            """
                            UPDATE jobs
                            SET superseded_by_job_id = %(new_job_id)s
                            WHERE id = %(job_id)s
                            """,
                            {
                                "new_job_id": job_id,
                                "job_id": supersedes.id,
                            },
                        )

                    self._append_job_event(
                        cursor=cursor_obj,
                        job_id=job_id,
                        project_id=project_id,
                        event_type=event_type,
                        from_status=None,
                        to_status="QUEUED",
                        actor_user_id=created_by,
                        details={"attempt_number": attempt_number},
                    )

                    created = self._read_job(
                        cursor=cursor_obj,
                        project_id=project_id,
                        job_id=job_id,
                    )
                connection.commit()
        except (JobNotFoundError, JobRetryConflictError):
            raise
        except psycopg.Error as error:
            raise JobStoreUnavailableError("Job enqueue failed.") from error

        return created, True, "CREATED"

    def append_retry(
        self,
        *,
        project_id: str,
        job_id: str,
        actor_user_id: str,
    ) -> tuple[JobRecord, bool, str]:
        self.ensure_schema()
        current = self.get_job(project_id=project_id, job_id=job_id)
        if current.status not in {"FAILED", "CANCELED"}:
            raise JobTransitionError("Retry is allowed only for FAILED or CANCELED jobs.")
        return self.enqueue_job(
            project_id=project_id,
            job_type=current.type,
            dedupe_key=current.dedupe_key,
            payload_json=current.payload_json,
            created_by=actor_user_id,
            max_attempts=current.max_attempts,
            supersedes_job_id=current.id,
            event_type="JOB_RETRY_APPENDED",
        )

    def cancel_job(
        self,
        *,
        project_id: str,
        job_id: str,
        actor_user_id: str,
    ) -> tuple[JobRecord, bool]:
        self.ensure_schema()
        now = datetime.now(UTC)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_obj:
                    job = self._get_job_for_update(
                        cursor=cursor_obj,
                        project_id=project_id,
                        job_id=job_id,
                    )

                    if job.status == "QUEUED":
                        cursor_obj.execute(
                            """
                            UPDATE jobs
                            SET
                              status = 'CANCELED',
                              canceled_by = %(actor_user_id)s,
                              canceled_at = %(now)s,
                              finished_at = %(now)s,
                              cancel_requested_by = NULL,
                              cancel_requested_at = NULL
                            WHERE id = %(job_id)s
                            """,
                            {
                                "actor_user_id": actor_user_id,
                                "now": now,
                                "job_id": job.id,
                            },
                        )
                        self._append_job_event(
                            cursor=cursor_obj,
                            job_id=job.id,
                            project_id=project_id,
                            event_type="JOB_CANCELED",
                            from_status=job.status,
                            to_status="CANCELED",
                            actor_user_id=actor_user_id,
                            details={"mode": "queued_direct"},
                        )
                        canceled = self._read_job(
                            cursor=cursor_obj,
                            project_id=project_id,
                            job_id=job.id,
                        )
                        connection.commit()
                        return canceled, True

                    if job.status == "RUNNING":
                        cursor_obj.execute(
                            """
                            UPDATE jobs
                            SET
                              cancel_requested_by = COALESCE(
                                cancel_requested_by,
                                %(actor_user_id)s
                              ),
                              cancel_requested_at = COALESCE(
                                cancel_requested_at,
                                %(now)s
                              )
                            WHERE id = %(job_id)s
                            """,
                            {
                                "actor_user_id": actor_user_id,
                                "now": now,
                                "job_id": job.id,
                            },
                        )
                        running = self._read_job(
                            cursor=cursor_obj,
                            project_id=project_id,
                            job_id=job.id,
                        )
                        connection.commit()
                        return running, False

                    raise JobTransitionError(
                        "Cancel is allowed only while the job is QUEUED or RUNNING."
                    )
        except (JobNotFoundError, JobTransitionError):
            raise
        except psycopg.Error as error:
            raise JobStoreUnavailableError("Job cancel failed.") from error

    def _recover_stale_running_jobs(
        self,
        *,
        cursor: psycopg.Cursor,
        now: datetime,
    ) -> None:
        cursor.execute(
            """
            SELECT
              id,
              project_id,
              attempt_number,
              supersedes_job_id,
              superseded_by_job_id,
              type,
              dedupe_key,
              status,
              attempts,
              max_attempts,
              payload_json,
              created_by,
              created_at,
              started_at,
              finished_at,
              canceled_by,
              canceled_at,
              error_code,
              error_message,
              cancel_requested_by,
              cancel_requested_at,
              lease_owner_id,
              lease_expires_at,
              last_heartbeat_at
            FROM jobs
            WHERE status = 'RUNNING'
              AND lease_expires_at IS NOT NULL
              AND lease_expires_at <= %(now)s
              AND superseded_by_job_id IS NULL
            ORDER BY lease_expires_at ASC, id ASC
            LIMIT 50
            FOR UPDATE SKIP LOCKED
            """,
            {"now": now},
        )
        stale_rows = cursor.fetchall()

        for row in stale_rows:
            job = self._as_job(row)
            if job.cancel_requested_at is not None:
                cursor.execute(
                    """
                    UPDATE jobs
                    SET
                      status = 'CANCELED',
                      canceled_by = COALESCE(canceled_by, cancel_requested_by),
                      canceled_at = COALESCE(canceled_at, %(now)s),
                      finished_at = %(now)s,
                      lease_owner_id = NULL,
                      lease_expires_at = NULL,
                      last_heartbeat_at = NULL
                    WHERE id = %(job_id)s
                    """,
                    {"now": now, "job_id": job.id},
                )
                self._append_job_event(
                    cursor=cursor,
                    job_id=job.id,
                    project_id=job.project_id,
                    event_type="JOB_CANCELED",
                    from_status="RUNNING",
                    to_status="CANCELED",
                    actor_user_id=job.cancel_requested_by,
                    details={"reason": "lease_expired_after_cancel_request"},
                )
                continue

            if job.attempts >= job.max_attempts:
                cursor.execute(
                    """
                    UPDATE jobs
                    SET
                      status = 'FAILED',
                      finished_at = %(now)s,
                      error_code = 'WORKER_LEASE_EXPIRED',
                      error_message = %(error_message)s,
                      lease_owner_id = NULL,
                      lease_expires_at = NULL,
                      last_heartbeat_at = NULL
                    WHERE id = %(job_id)s
                    """,
                    {
                        "now": now,
                        "error_message": self.sanitize_error_message(
                            "Worker lease expired before completion."
                        ),
                        "job_id": job.id,
                    },
                )
                self._append_job_event(
                    cursor=cursor,
                    job_id=job.id,
                    project_id=job.project_id,
                    event_type="JOB_FAILED",
                    from_status="RUNNING",
                    to_status="FAILED",
                    actor_user_id=None,
                    details={"reason": "lease_expired_max_attempts_reached"},
                )
                continue

            cursor.execute(
                """
                UPDATE jobs
                SET
                  status = 'QUEUED',
                  lease_owner_id = NULL,
                  lease_expires_at = NULL,
                  last_heartbeat_at = NULL
                WHERE id = %(job_id)s
                """,
                {"job_id": job.id},
            )
            self._append_job_event(
                cursor=cursor,
                job_id=job.id,
                project_id=job.project_id,
                event_type="JOB_FAILED",
                from_status="RUNNING",
                to_status="QUEUED",
                actor_user_id=None,
                details={"reason": "lease_expired_requeued"},
            )

    def claim_next_job(
        self,
        *,
        worker_id: str,
        lease_seconds: int,
    ) -> JobRecord | None:
        self.ensure_schema()
        safe_lease_seconds = max(5, min(lease_seconds, 600))
        now = datetime.now(UTC)
        lease_expires_at = now + timedelta(seconds=safe_lease_seconds)

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_obj:
                    self._recover_stale_running_jobs(cursor=cursor_obj, now=now)

                    while True:
                        cursor_obj.execute(
                            """
                            SELECT
                              id,
                              project_id,
                              attempt_number,
                              supersedes_job_id,
                              superseded_by_job_id,
                              type,
                              dedupe_key,
                              status,
                              attempts,
                              max_attempts,
                              payload_json,
                              created_by,
                              created_at,
                              started_at,
                              finished_at,
                              canceled_by,
                              canceled_at,
                              error_code,
                              error_message,
                              cancel_requested_by,
                              cancel_requested_at,
                              lease_owner_id,
                              lease_expires_at,
                              last_heartbeat_at
                            FROM jobs
                            WHERE status = 'QUEUED'
                              AND superseded_by_job_id IS NULL
                            ORDER BY created_at ASC, id ASC
                            LIMIT 1
                            FOR UPDATE SKIP LOCKED
                            """
                        )
                        candidate_row = cursor_obj.fetchone()
                        if candidate_row is None:
                            connection.commit()
                            return None

                        candidate = self._as_job(candidate_row)
                        cursor_obj.execute(
                            """
                            SELECT id
                            FROM jobs
                            WHERE project_id = %(project_id)s
                              AND dedupe_key = %(dedupe_key)s
                              AND superseded_by_job_id IS NULL
                              AND status = 'SUCCEEDED'
                              AND id <> %(job_id)s
                            LIMIT 1
                            FOR UPDATE
                            """,
                            {
                                "project_id": candidate.project_id,
                                "dedupe_key": candidate.dedupe_key,
                                "job_id": candidate.id,
                            },
                        )
                        succeeded_row = cursor_obj.fetchone()
                        if succeeded_row is not None:
                            cursor_obj.execute(
                                """
                                UPDATE jobs
                                SET
                                  status = 'CANCELED',
                                  canceled_at = %(now)s,
                                  finished_at = %(now)s,
                                  error_code = 'DEDUPE_ALREADY_SUCCEEDED',
                                  error_message = %(error_message)s
                                WHERE id = %(job_id)s
                                """,
                                {
                                    "now": now,
                                    "error_message": self.sanitize_error_message(
                                        (
                                            "Job skipped because the logical work item "
                                            "already succeeded."
                                        )
                                    ),
                                    "job_id": candidate.id,
                                },
                            )
                            self._append_job_event(
                                cursor=cursor_obj,
                                job_id=candidate.id,
                                project_id=candidate.project_id,
                                event_type="JOB_CANCELED",
                                from_status="QUEUED",
                                to_status="CANCELED",
                                actor_user_id=None,
                                details={"reason": "dedupe_already_succeeded"},
                            )
                            continue

                        cursor_obj.execute(
                            """
                            UPDATE jobs
                            SET
                              status = 'RUNNING',
                              attempts = attempts + 1,
                              started_at = COALESCE(started_at, %(now)s),
                              lease_owner_id = %(worker_id)s,
                              lease_expires_at = %(lease_expires_at)s,
                              last_heartbeat_at = %(now)s
                            WHERE id = %(job_id)s
                            """,
                            {
                                "now": now,
                                "worker_id": worker_id,
                                "lease_expires_at": lease_expires_at,
                                "job_id": candidate.id,
                            },
                        )
                        self._append_job_event(
                            cursor=cursor_obj,
                            job_id=candidate.id,
                            project_id=candidate.project_id,
                            event_type="JOB_STARTED",
                            from_status="QUEUED",
                            to_status="RUNNING",
                            actor_user_id=None,
                            details={"worker_id": worker_id},
                        )
                        claimed = self._read_job(
                            cursor=cursor_obj,
                            project_id=candidate.project_id,
                            job_id=candidate.id,
                        )
                        connection.commit()
                        return claimed
        except psycopg.Error as error:
            raise JobStoreUnavailableError("Job claim failed.") from error

    def heartbeat_job(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_seconds: int,
    ) -> bool:
        self.ensure_schema()
        safe_lease_seconds = max(5, min(lease_seconds, 600))
        now = datetime.now(UTC)
        lease_expires_at = now + timedelta(seconds=safe_lease_seconds)
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor_obj:
                    cursor_obj.execute(
                        """
                        UPDATE jobs
                        SET
                          lease_expires_at = %(lease_expires_at)s,
                          last_heartbeat_at = %(now)s
                        WHERE id = %(job_id)s
                          AND status = 'RUNNING'
                          AND lease_owner_id = %(worker_id)s
                        """,
                        {
                            "lease_expires_at": lease_expires_at,
                            "now": now,
                            "job_id": job_id,
                            "worker_id": worker_id,
                        },
                    )
                    updated = cursor_obj.rowcount > 0
                connection.commit()
                return updated
        except psycopg.Error as error:
            raise JobStoreUnavailableError("Job heartbeat failed.") from error

    def finish_running_job(
        self,
        *,
        job_id: str,
        worker_id: str,
        success: bool,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> JobRecord:
        self.ensure_schema()
        now = datetime.now(UTC)
        sanitized_error_message = self.sanitize_error_message(error_message)
        sanitized_error_code = error_code.strip()[:80] if error_code else None

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_obj:
                    cursor_obj.execute(
                        """
                        SELECT
                          id,
                          project_id,
                          attempt_number,
                          supersedes_job_id,
                          superseded_by_job_id,
                          type,
                          dedupe_key,
                          status,
                          attempts,
                          max_attempts,
                          payload_json,
                          created_by,
                          created_at,
                          started_at,
                          finished_at,
                          canceled_by,
                          canceled_at,
                          error_code,
                          error_message,
                          cancel_requested_by,
                          cancel_requested_at,
                          lease_owner_id,
                          lease_expires_at,
                          last_heartbeat_at
                        FROM jobs
                        WHERE id = %(job_id)s
                        FOR UPDATE
                        """,
                        {"job_id": job_id},
                    )
                    row = cursor_obj.fetchone()
                    if row is None:
                        raise JobNotFoundError("Job not found.")
                    job = self._as_job(row)
                    if job.status != "RUNNING":
                        raise JobTransitionError("Only RUNNING jobs may be finalized.")
                    if job.lease_owner_id and job.lease_owner_id != worker_id:
                        raise JobTransitionError("Job is owned by a different worker lease.")

                    if job.cancel_requested_at is not None:
                        cursor_obj.execute(
                            """
                            UPDATE jobs
                            SET
                              status = 'CANCELED',
                              canceled_by = COALESCE(
                                canceled_by,
                                cancel_requested_by
                              ),
                              canceled_at = COALESCE(
                                canceled_at,
                                cancel_requested_at,
                                %(now)s
                              ),
                              finished_at = %(now)s,
                              lease_owner_id = NULL,
                              lease_expires_at = NULL,
                              last_heartbeat_at = NULL
                            WHERE id = %(job_id)s
                            """,
                            {"now": now, "job_id": job.id},
                        )
                        self._append_job_event(
                            cursor=cursor_obj,
                            job_id=job.id,
                            project_id=job.project_id,
                            event_type="JOB_CANCELED",
                            from_status="RUNNING",
                            to_status="CANCELED",
                            actor_user_id=job.cancel_requested_by,
                            details={"worker_id": worker_id},
                        )
                        finalized = self._read_job(
                            cursor=cursor_obj,
                            project_id=job.project_id,
                            job_id=job.id,
                        )
                        connection.commit()
                        return finalized

                    if success:
                        cursor_obj.execute(
                            """
                            UPDATE jobs
                            SET
                              status = 'SUCCEEDED',
                              finished_at = %(now)s,
                              error_code = NULL,
                              error_message = NULL,
                              lease_owner_id = NULL,
                              lease_expires_at = NULL,
                              last_heartbeat_at = NULL
                            WHERE id = %(job_id)s
                            """,
                            {"now": now, "job_id": job.id},
                        )
                        self._append_job_event(
                            cursor=cursor_obj,
                            job_id=job.id,
                            project_id=job.project_id,
                            event_type="JOB_SUCCEEDED",
                            from_status="RUNNING",
                            to_status="SUCCEEDED",
                            actor_user_id=None,
                            details={"worker_id": worker_id},
                        )
                        finalized = self._read_job(
                            cursor=cursor_obj,
                            project_id=job.project_id,
                            job_id=job.id,
                        )
                        connection.commit()
                        return finalized

                    if job.attempts < job.max_attempts:
                        cursor_obj.execute(
                            """
                            UPDATE jobs
                            SET
                              status = 'QUEUED',
                              error_code = %(error_code)s,
                              error_message = %(error_message)s,
                              lease_owner_id = NULL,
                              lease_expires_at = NULL,
                              last_heartbeat_at = NULL
                            WHERE id = %(job_id)s
                            """,
                            {
                                "error_code": sanitized_error_code or "JOB_EXECUTION_FAILED",
                                "error_message": sanitized_error_message,
                                "job_id": job.id,
                            },
                        )
                        self._append_job_event(
                            cursor=cursor_obj,
                            job_id=job.id,
                            project_id=job.project_id,
                            event_type="JOB_FAILED",
                            from_status="RUNNING",
                            to_status="QUEUED",
                            actor_user_id=None,
                            details={
                                "worker_id": worker_id,
                                "reason": "delivery_retry_scheduled",
                                "attempts": job.attempts,
                                "max_attempts": job.max_attempts,
                            },
                        )
                        requeued = self._read_job(
                            cursor=cursor_obj,
                            project_id=job.project_id,
                            job_id=job.id,
                        )
                        connection.commit()
                        return requeued

                    cursor_obj.execute(
                        """
                        UPDATE jobs
                        SET
                          status = 'FAILED',
                          finished_at = %(now)s,
                          error_code = %(error_code)s,
                          error_message = %(error_message)s,
                          lease_owner_id = NULL,
                          lease_expires_at = NULL,
                          last_heartbeat_at = NULL
                        WHERE id = %(job_id)s
                        """,
                        {
                            "now": now,
                            "error_code": sanitized_error_code or "JOB_EXECUTION_FAILED",
                            "error_message": sanitized_error_message,
                            "job_id": job.id,
                        },
                    )
                    self._append_job_event(
                        cursor=cursor_obj,
                        job_id=job.id,
                        project_id=job.project_id,
                        event_type="JOB_FAILED",
                        from_status="RUNNING",
                        to_status="FAILED",
                        actor_user_id=None,
                        details={
                            "worker_id": worker_id,
                            "attempts": job.attempts,
                            "max_attempts": job.max_attempts,
                        },
                    )
                    failed = self._read_job(
                        cursor=cursor_obj,
                        project_id=job.project_id,
                        job_id=job.id,
                    )
                connection.commit()
                return failed
        except (JobNotFoundError, JobTransitionError):
            raise
        except psycopg.Error as error:
            raise JobStoreUnavailableError("Job finalization failed.") from error

    def count_open_jobs(self) -> int:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_obj:
                    cursor_obj.execute(
                        """
                        SELECT COUNT(*)::INT AS total
                        FROM jobs
                        WHERE status = 'QUEUED'
                          AND superseded_by_job_id IS NULL
                        """
                    )
                    row = cursor_obj.fetchone()
        except psycopg.Error as error:
            raise JobStoreUnavailableError("Queue depth query failed.") from error
        if row is None:
            return 0
        return int(row["total"])

    def project_job_activity(
        self,
        *,
        project_id: str,
    ) -> tuple[int, JobStatus | None]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_obj:
                    cursor_obj.execute(
                        """
                        SELECT COUNT(*)::INT AS running_jobs
                        FROM jobs
                        WHERE project_id = %(project_id)s
                          AND status = 'RUNNING'
                          AND superseded_by_job_id IS NULL
                        """,
                        {"project_id": project_id},
                    )
                    running_row = cursor_obj.fetchone()
                    cursor_obj.execute(
                        """
                        SELECT status
                        FROM jobs
                        WHERE project_id = %(project_id)s
                        ORDER BY created_at DESC, id DESC
                        LIMIT 1
                        """,
                        {"project_id": project_id},
                    )
                    last_row = cursor_obj.fetchone()
        except psycopg.Error as error:
            raise JobStoreUnavailableError("Project job activity query failed.") from error

        running_jobs = int(running_row["running_jobs"]) if running_row else 0
        if last_row is None:
            return running_jobs, None
        return running_jobs, self._assert_status(str(last_row["status"]))
