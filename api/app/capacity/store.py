from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from app.capacity.models import CapacityTestKind, CapacityTestRunPage, CapacityTestRunRecord, CapacityTestStatus
from app.core.config import Settings
from app.projects.store import ProjectStore

_VALID_TEST_KINDS: set[str] = {"LOAD", "SOAK", "BENCHMARK"}
_VALID_STATUSES: set[str] = {"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"}

CAPACITY_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS capacity_test_runs (
      id TEXT PRIMARY KEY,
      test_kind TEXT NOT NULL CHECK (test_kind IN ('LOAD', 'SOAK', 'BENCHMARK')),
      scenario_name TEXT NOT NULL,
      status TEXT NOT NULL CHECK (
        status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED')
      ),
      results_key TEXT,
      results_sha256 TEXT,
      started_by TEXT NOT NULL REFERENCES users(id),
      started_at TIMESTAMPTZ,
      finished_at TIMESTAMPTZ,
      created_at TIMESTAMPTZ NOT NULL,
      scenario_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      results_json JSONB,
      failure_reason TEXT,
      CHECK (jsonb_typeof(scenario_json) = 'object'),
      CHECK (results_json IS NULL OR jsonb_typeof(results_json) = 'object')
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_capacity_test_runs_created
      ON capacity_test_runs(created_at DESC, id DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_capacity_test_runs_status
      ON capacity_test_runs(status, created_at DESC, id DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_capacity_test_runs_scenario
      ON capacity_test_runs(scenario_name, created_at DESC, id DESC)
    """,
)


class CapacityStoreUnavailableError(RuntimeError):
    """Capacity persistence is unavailable."""


class CapacityTestNotFoundError(RuntimeError):
    """Requested capacity test run was not found."""


class CapacityTransitionError(RuntimeError):
    """Requested capacity test run transition is not valid."""


class CapacityStore:
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
                    for statement in CAPACITY_SCHEMA_STATEMENTS:
                        cursor.execute(statement)
                connection.commit()
        except psycopg.Error as error:
            raise CapacityStoreUnavailableError(
                "Capacity schema could not be initialized."
            ) from error

        self._schema_initialized = True

    @staticmethod
    def _assert_kind(value: str) -> CapacityTestKind:
        if value not in _VALID_TEST_KINDS:
            raise CapacityStoreUnavailableError("Unexpected capacity test kind persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_status(value: str) -> CapacityTestStatus:
        if value not in _VALID_STATUSES:
            raise CapacityStoreUnavailableError("Unexpected capacity test status persisted.")
        return value  # type: ignore[return-value]

    @classmethod
    def _as_run_record(cls, row: dict[str, object]) -> CapacityTestRunRecord:
        scenario_raw = row.get("scenario_json")
        results_raw = row.get("results_json")
        return CapacityTestRunRecord(
            id=str(row["id"]),
            test_kind=cls._assert_kind(str(row["test_kind"])),
            scenario_name=str(row["scenario_name"]),
            status=cls._assert_status(str(row["status"])),
            results_key=str(row["results_key"]) if isinstance(row.get("results_key"), str) else None,
            results_sha256=(
                str(row["results_sha256"]) if isinstance(row.get("results_sha256"), str) else None
            ),
            started_by=str(row["started_by"]),
            started_at=row.get("started_at"),  # type: ignore[arg-type]
            finished_at=row.get("finished_at"),  # type: ignore[arg-type]
            created_at=row["created_at"],  # type: ignore[arg-type]
            scenario_json=dict(scenario_raw) if isinstance(scenario_raw, dict) else {},
            results_json=dict(results_raw) if isinstance(results_raw, dict) else None,
            failure_reason=(
                str(row["failure_reason"]) if isinstance(row.get("failure_reason"), str) else None
            ),
        )

    def create_test_run(
        self,
        *,
        test_kind: CapacityTestKind,
        scenario_name: str,
        started_by: str,
        scenario_json: dict[str, object],
    ) -> CapacityTestRunRecord:
        self.ensure_schema()
        now = self.utcnow()
        run_id = f"capacity-{uuid4()}"
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO capacity_test_runs (
                          id,
                          test_kind,
                          scenario_name,
                          status,
                          results_key,
                          results_sha256,
                          started_by,
                          started_at,
                          finished_at,
                          created_at,
                          scenario_json,
                          results_json,
                          failure_reason
                        )
                        VALUES (
                          %(id)s,
                          %(test_kind)s,
                          %(scenario_name)s,
                          'QUEUED',
                          NULL,
                          NULL,
                          %(started_by)s,
                          NULL,
                          NULL,
                          %(created_at)s,
                          %(scenario_json)s::jsonb,
                          NULL,
                          NULL
                        )
                        RETURNING
                          id,
                          test_kind,
                          scenario_name,
                          status,
                          results_key,
                          results_sha256,
                          started_by,
                          started_at,
                          finished_at,
                          created_at,
                          scenario_json,
                          results_json,
                          failure_reason
                        """,
                        {
                            "id": run_id,
                            "test_kind": test_kind,
                            "scenario_name": scenario_name,
                            "started_by": started_by,
                            "created_at": now,
                            "scenario_json": scenario_json,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise CapacityStoreUnavailableError("Capacity test run could not be created.") from error

        if row is None:
            raise CapacityStoreUnavailableError("Capacity test run creation returned no row.")
        return self._as_run_record(row)

    def mark_running(self, *, run_id: str) -> CapacityTestRunRecord:
        self.ensure_schema()
        now = self.utcnow()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE capacity_test_runs
                        SET
                          status = 'RUNNING',
                          started_at = COALESCE(started_at, %(started_at)s),
                          failure_reason = NULL
                        WHERE id = %(run_id)s
                          AND status IN ('QUEUED', 'RUNNING')
                        RETURNING
                          id,
                          test_kind,
                          scenario_name,
                          status,
                          results_key,
                          results_sha256,
                          started_by,
                          started_at,
                          finished_at,
                          created_at,
                          scenario_json,
                          results_json,
                          failure_reason
                        """,
                        {"run_id": run_id, "started_at": now},
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise CapacityStoreUnavailableError("Capacity test run could not be started.") from error

        if row is None:
            existing = self.get_test_run(run_id=run_id)
            if existing.status in {"SUCCEEDED", "FAILED", "CANCELED"}:
                raise CapacityTransitionError(
                    f"Capacity test run {run_id} is already terminal ({existing.status})."
                )
            raise CapacityTransitionError(f"Capacity test run {run_id} cannot enter RUNNING state.")
        return self._as_run_record(row)

    def mark_succeeded(
        self,
        *,
        run_id: str,
        results_key: str,
        results_sha256: str,
        results_json: dict[str, object],
    ) -> CapacityTestRunRecord:
        self.ensure_schema()
        now = self.utcnow()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE capacity_test_runs
                        SET
                          status = 'SUCCEEDED',
                          results_key = %(results_key)s,
                          results_sha256 = %(results_sha256)s,
                          results_json = %(results_json)s::jsonb,
                          finished_at = %(finished_at)s,
                          failure_reason = NULL
                        WHERE id = %(run_id)s
                          AND status IN ('QUEUED', 'RUNNING')
                        RETURNING
                          id,
                          test_kind,
                          scenario_name,
                          status,
                          results_key,
                          results_sha256,
                          started_by,
                          started_at,
                          finished_at,
                          created_at,
                          scenario_json,
                          results_json,
                          failure_reason
                        """,
                        {
                            "run_id": run_id,
                            "results_key": results_key,
                            "results_sha256": results_sha256,
                            "results_json": results_json,
                            "finished_at": now,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise CapacityStoreUnavailableError(
                "Capacity test run success update failed."
            ) from error

        if row is None:
            existing = self.get_test_run(run_id=run_id)
            if existing.status == "SUCCEEDED":
                return existing
            raise CapacityTransitionError(
                f"Capacity test run {run_id} cannot enter SUCCEEDED state."
            )
        return self._as_run_record(row)

    def mark_failed(self, *, run_id: str, failure_reason: str) -> CapacityTestRunRecord:
        self.ensure_schema()
        now = self.utcnow()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        UPDATE capacity_test_runs
                        SET
                          status = 'FAILED',
                          finished_at = %(finished_at)s,
                          failure_reason = %(failure_reason)s
                        WHERE id = %(run_id)s
                          AND status IN ('QUEUED', 'RUNNING')
                        RETURNING
                          id,
                          test_kind,
                          scenario_name,
                          status,
                          results_key,
                          results_sha256,
                          started_by,
                          started_at,
                          finished_at,
                          created_at,
                          scenario_json,
                          results_json,
                          failure_reason
                        """,
                        {
                            "run_id": run_id,
                            "finished_at": now,
                            "failure_reason": failure_reason[:400],
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise CapacityStoreUnavailableError("Capacity test run failure update failed.") from error

        if row is None:
            existing = self.get_test_run(run_id=run_id)
            if existing.status == "FAILED":
                return existing
            raise CapacityTransitionError(
                f"Capacity test run {run_id} cannot enter FAILED state."
            )
        return self._as_run_record(row)

    def get_test_run(self, *, run_id: str) -> CapacityTestRunRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          test_kind,
                          scenario_name,
                          status,
                          results_key,
                          results_sha256,
                          started_by,
                          started_at,
                          finished_at,
                          created_at,
                          scenario_json,
                          results_json,
                          failure_reason
                        FROM capacity_test_runs
                        WHERE id = %(run_id)s
                        """,
                        {"run_id": run_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise CapacityStoreUnavailableError("Capacity test run lookup failed.") from error

        if row is None:
            raise CapacityTestNotFoundError(f"Capacity test run {run_id} was not found.")
        return self._as_run_record(row)

    def list_test_runs(self, *, cursor: int, page_size: int) -> CapacityTestRunPage:
        self.ensure_schema()
        limit = page_size + 1
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_obj:
                    cursor_obj.execute(
                        """
                        SELECT
                          id,
                          test_kind,
                          scenario_name,
                          status,
                          results_key,
                          results_sha256,
                          started_by,
                          started_at,
                          finished_at,
                          created_at,
                          scenario_json,
                          results_json,
                          failure_reason
                        FROM capacity_test_runs
                        ORDER BY created_at DESC, id DESC
                        OFFSET %(cursor)s
                        LIMIT %(limit)s
                        """,
                        {"cursor": cursor, "limit": limit},
                    )
                    rows = cursor_obj.fetchall()
        except psycopg.Error as error:
            raise CapacityStoreUnavailableError("Capacity test run listing failed.") from error

        has_more = len(rows) > page_size
        materialized = rows[:page_size]
        items = [self._as_run_record(row) for row in materialized]
        return CapacityTestRunPage(items=items, next_cursor=(cursor + page_size) if has_more else None)

