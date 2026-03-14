from __future__ import annotations

from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from app.core.config import Settings
from app.exports.models import ExportStubEventRecord

EXPORT_STUB_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS export_stub_events (
      id TEXT PRIMARY KEY,
      project_id TEXT,
      route TEXT NOT NULL,
      method TEXT NOT NULL,
      actor_user_id TEXT,
      request_id TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_export_stub_events_project_created_at
      ON export_stub_events(project_id, created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_export_stub_events_request_id
      ON export_stub_events(request_id)
    """,
)


class ExportStubStoreUnavailableError(RuntimeError):
    """Export stub persistence is unavailable."""


class ExportStubStore:
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
                    for statement in EXPORT_STUB_SCHEMA_STATEMENTS:
                        cursor.execute(statement)
                connection.commit()
        except psycopg.Error as error:
            raise ExportStubStoreUnavailableError(
                "Export stub schema could not be initialized."
            ) from error

        self._schema_initialized = True

    @staticmethod
    def _as_record(row: dict[str, object]) -> ExportStubEventRecord:
        return ExportStubEventRecord(
            id=str(row["id"]),
            project_id=row["project_id"],  # type: ignore[arg-type]
            route=str(row["route"]),
            method=str(row["method"]),
            actor_user_id=row["actor_user_id"],  # type: ignore[arg-type]
            request_id=str(row["request_id"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    def append_stub_event(
        self,
        *,
        project_id: str | None,
        route: str,
        method: str,
        actor_user_id: str | None,
        request_id: str,
    ) -> ExportStubEventRecord:
        self.ensure_schema()
        event_id = str(uuid4())

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO export_stub_events (
                          id,
                          project_id,
                          route,
                          method,
                          actor_user_id,
                          request_id
                        )
                        VALUES (
                          %(id)s,
                          %(project_id)s,
                          %(route)s,
                          %(method)s,
                          %(actor_user_id)s,
                          %(request_id)s
                        )
                        RETURNING
                          id,
                          project_id,
                          route,
                          method,
                          actor_user_id,
                          request_id,
                          created_at
                        """,
                        {
                            "id": event_id,
                            "project_id": project_id,
                            "route": route,
                            "method": method.upper(),
                            "actor_user_id": actor_user_id,
                            "request_id": request_id,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise ExportStubStoreUnavailableError(
                "Export stub event could not be persisted."
            ) from error

        if row is None:
            raise ExportStubStoreUnavailableError("Export stub event insert returned no row.")
        return self._as_record(row)

