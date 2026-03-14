import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from app.audit.models import AuditEventRecord, AuditEventType, AuditIntegrityStatus
from app.core.config import Settings

AUDIT_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS audit_events (
      id TEXT PRIMARY KEY,
      chain_index BIGINT NOT NULL UNIQUE,
      timestamp TIMESTAMPTZ NOT NULL,
      actor_user_id TEXT,
      project_id TEXT,
      event_type TEXT NOT NULL,
      object_type TEXT,
      object_id TEXT,
      ip TEXT,
      user_agent TEXT,
      request_id TEXT NOT NULL,
      metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
      prev_hash TEXT NOT NULL,
      row_hash TEXT NOT NULL UNIQUE,
      CHECK (jsonb_typeof(metadata_json) = 'object')
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_audit_events_chain_index
      ON audit_events(chain_index DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_audit_events_timestamp
      ON audit_events(timestamp DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_audit_events_actor_user
      ON audit_events(actor_user_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_audit_events_project_id
      ON audit_events(project_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_audit_events_event_type
      ON audit_events(event_type)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_audit_events_request_id
      ON audit_events(request_id)
    """,
    """
    CREATE OR REPLACE FUNCTION prevent_audit_events_mutation()
    RETURNS trigger AS $$
    BEGIN
      RAISE EXCEPTION 'audit_events is append-only';
    END;
    $$ LANGUAGE plpgsql
    """,
    """
    DROP TRIGGER IF EXISTS trg_audit_events_no_update ON audit_events
    """,
    """
    CREATE TRIGGER trg_audit_events_no_update
    BEFORE UPDATE ON audit_events
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_events_mutation()
    """,
    """
    DROP TRIGGER IF EXISTS trg_audit_events_no_delete ON audit_events
    """,
    """
    CREATE TRIGGER trg_audit_events_no_delete
    BEFORE DELETE ON audit_events
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_events_mutation()
    """,
)


class AuditStoreUnavailableError(RuntimeError):
    """Audit persistence could not be reached."""


class AuditEventNotFoundError(RuntimeError):
    """Audit event was not found."""


class AuditStore:
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
                    for statement in AUDIT_SCHEMA_STATEMENTS:
                        cursor.execute(statement)
                connection.commit()
        except psycopg.Error as error:
            raise AuditStoreUnavailableError("Audit schema could not be initialized.") from error

        self._schema_initialized = True

    @staticmethod
    def _canonical_payload(
        *,
        chain_index: int,
        event_id: str,
        timestamp: datetime,
        actor_user_id: str | None,
        project_id: str | None,
        event_type: AuditEventType,
        object_type: str | None,
        object_id: str | None,
        ip: str | None,
        user_agent: str | None,
        request_id: str,
        metadata_json: dict[str, object],
        prev_hash: str,
    ) -> str:
        payload = {
            "id": event_id,
            "chain_index": chain_index,
            "timestamp": timestamp.astimezone(UTC).isoformat(),
            "actor_user_id": actor_user_id,
            "project_id": project_id,
            "event_type": event_type,
            "object_type": object_type,
            "object_id": object_id,
            "ip": ip,
            "user_agent": user_agent,
            "request_id": request_id,
            "metadata_json": metadata_json,
            "prev_hash": prev_hash,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    @classmethod
    def _row_hash(
        cls,
        *,
        chain_index: int,
        event_id: str,
        timestamp: datetime,
        actor_user_id: str | None,
        project_id: str | None,
        event_type: AuditEventType,
        object_type: str | None,
        object_id: str | None,
        ip: str | None,
        user_agent: str | None,
        request_id: str,
        metadata_json: dict[str, object],
        prev_hash: str,
    ) -> str:
        canonical = cls._canonical_payload(
            chain_index=chain_index,
            event_id=event_id,
            timestamp=timestamp,
            actor_user_id=actor_user_id,
            project_id=project_id,
            event_type=event_type,
            object_type=object_type,
            object_id=object_id,
            ip=ip,
            user_agent=user_agent,
            request_id=request_id,
            metadata_json=metadata_json,
            prev_hash=prev_hash,
        )
        raw = f"{prev_hash}|{canonical}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _as_metadata(value: object) -> dict[str, object]:
        if isinstance(value, dict):
            return value
        return {}

    @staticmethod
    def _as_event_type(value: str) -> AuditEventType:
        return value  # type: ignore[return-value]

    @classmethod
    def _as_event(cls, row: dict[str, object]) -> AuditEventRecord:
        return AuditEventRecord(
            id=str(row["id"]),
            chain_index=int(row["chain_index"]),
            timestamp=row["timestamp"],  # type: ignore[arg-type]
            actor_user_id=row["actor_user_id"],  # type: ignore[arg-type]
            project_id=row["project_id"],  # type: ignore[arg-type]
            event_type=cls._as_event_type(str(row["event_type"])),
            object_type=row["object_type"],  # type: ignore[arg-type]
            object_id=row["object_id"],  # type: ignore[arg-type]
            ip=row["ip"],  # type: ignore[arg-type]
            user_agent=row["user_agent"],  # type: ignore[arg-type]
            request_id=str(row["request_id"]),
            metadata_json=cls._as_metadata(row["metadata_json"]),
            prev_hash=str(row["prev_hash"]),
            row_hash=str(row["row_hash"]),
        )

    def append_event(
        self,
        *,
        actor_user_id: str | None,
        project_id: str | None,
        event_type: AuditEventType,
        object_type: str | None,
        object_id: str | None,
        ip: str | None,
        user_agent: str | None,
        request_id: str,
        metadata_json: dict[str, object],
    ) -> AuditEventRecord:
        self.ensure_schema()

        event_id = str(uuid4())
        timestamp = datetime.now(UTC)

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute("SELECT pg_advisory_xact_lock(27077601)")
                    cursor.execute(
                        """
                        SELECT chain_index, row_hash
                        FROM audit_events
                        ORDER BY chain_index DESC
                        LIMIT 1
                        """
                    )
                    latest = cursor.fetchone()
                    if latest is None:
                        chain_index = 1
                        prev_hash = "GENESIS"
                    else:
                        chain_index = int(latest["chain_index"]) + 1
                        prev_hash = str(latest["row_hash"])

                    row_hash = self._row_hash(
                        chain_index=chain_index,
                        event_id=event_id,
                        timestamp=timestamp,
                        actor_user_id=actor_user_id,
                        project_id=project_id,
                        event_type=event_type,
                        object_type=object_type,
                        object_id=object_id,
                        ip=ip,
                        user_agent=user_agent,
                        request_id=request_id,
                        metadata_json=metadata_json,
                        prev_hash=prev_hash,
                    )

                    cursor.execute(
                        """
                        INSERT INTO audit_events (
                          id,
                          chain_index,
                          timestamp,
                          actor_user_id,
                          project_id,
                          event_type,
                          object_type,
                          object_id,
                          ip,
                          user_agent,
                          request_id,
                          metadata_json,
                          prev_hash,
                          row_hash
                        )
                        VALUES (
                          %(id)s,
                          %(chain_index)s,
                          %(timestamp)s,
                          %(actor_user_id)s,
                          %(project_id)s,
                          %(event_type)s,
                          %(object_type)s,
                          %(object_id)s,
                          %(ip)s,
                          %(user_agent)s,
                          %(request_id)s,
                          %(metadata_json)s::jsonb,
                          %(prev_hash)s,
                          %(row_hash)s
                        )
                        RETURNING
                          id,
                          chain_index,
                          timestamp,
                          actor_user_id,
                          project_id,
                          event_type,
                          object_type,
                          object_id,
                          ip,
                          user_agent,
                          request_id,
                          metadata_json,
                          prev_hash,
                          row_hash
                        """,
                        {
                            "id": event_id,
                            "chain_index": chain_index,
                            "timestamp": timestamp,
                            "actor_user_id": actor_user_id,
                            "project_id": project_id,
                            "event_type": event_type,
                            "object_type": object_type,
                            "object_id": object_id,
                            "ip": ip,
                            "user_agent": user_agent,
                            "request_id": request_id,
                            "metadata_json": json.dumps(
                                metadata_json,
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                            "prev_hash": prev_hash,
                            "row_hash": row_hash,
                        },
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise AuditStoreUnavailableError(
                            "Audit event could not be loaded after append."
                        )
                connection.commit()
        except psycopg.Error as error:
            raise AuditStoreUnavailableError("Audit event append failed.") from error

        return self._as_event(row)

    def list_events(
        self,
        *,
        project_id: str | None,
        actor_user_id: str | None,
        event_type: AuditEventType | None,
        from_timestamp: datetime | None,
        to_timestamp: datetime | None,
        cursor: int,
        page_size: int,
    ) -> tuple[list[AuditEventRecord], int | None]:
        self.ensure_schema()
        clauses = ["1=1"]
        params: dict[str, object] = {
            "cursor": max(cursor, 0),
            "limit": max(1, min(page_size, 200)) + 1,
        }

        if project_id:
            clauses.append("project_id = %(project_id)s")
            params["project_id"] = project_id
        if actor_user_id:
            clauses.append("actor_user_id = %(actor_user_id)s")
            params["actor_user_id"] = actor_user_id
        if event_type:
            clauses.append("event_type = %(event_type)s")
            params["event_type"] = event_type
        if from_timestamp:
            clauses.append("timestamp >= %(from_timestamp)s")
            params["from_timestamp"] = from_timestamp
        if to_timestamp:
            clauses.append("timestamp <= %(to_timestamp)s")
            params["to_timestamp"] = to_timestamp

        where_sql = " AND ".join(clauses)

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor_obj:
                    cursor_obj.execute(
                        f"""
                        SELECT
                          id,
                          chain_index,
                          timestamp,
                          actor_user_id,
                          project_id,
                          event_type,
                          object_type,
                          object_id,
                          ip,
                          user_agent,
                          request_id,
                          metadata_json,
                          prev_hash,
                          row_hash
                        FROM audit_events
                        WHERE {where_sql}
                        ORDER BY chain_index DESC
                        LIMIT %(limit)s
                        OFFSET %(cursor)s
                        """,
                        params,
                    )
                    rows = cursor_obj.fetchall()
        except psycopg.Error as error:
            raise AuditStoreUnavailableError("Audit event list failed.") from error

        has_more = len(rows) > max(1, min(page_size, 200))
        selected = rows[: max(1, min(page_size, 200))]
        next_cursor: int | None = None
        if has_more:
            next_cursor = max(cursor, 0) + max(1, min(page_size, 200))
        return [self._as_event(row) for row in selected], next_cursor

    def get_event(self, *, event_id: str) -> AuditEventRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          chain_index,
                          timestamp,
                          actor_user_id,
                          project_id,
                          event_type,
                          object_type,
                          object_id,
                          ip,
                          user_agent,
                          request_id,
                          metadata_json,
                          prev_hash,
                          row_hash
                        FROM audit_events
                        WHERE id = %(event_id)s
                        """,
                        {"event_id": event_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise AuditStoreUnavailableError("Audit event lookup failed.") from error

        if row is None:
            raise AuditEventNotFoundError("Audit event not found.")
        return self._as_event(row)

    def list_user_activity(
        self,
        *,
        actor_user_id: str,
        limit: int,
    ) -> list[AuditEventRecord]:
        self.ensure_schema()
        page_size = max(1, min(limit, 200))
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          chain_index,
                          timestamp,
                          actor_user_id,
                          project_id,
                          event_type,
                          object_type,
                          object_id,
                          ip,
                          user_agent,
                          request_id,
                          metadata_json,
                          prev_hash,
                          row_hash
                        FROM audit_events
                        WHERE actor_user_id = %(actor_user_id)s
                        ORDER BY chain_index DESC
                        LIMIT %(limit)s
                        """,
                        {"actor_user_id": actor_user_id, "limit": page_size},
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise AuditStoreUnavailableError("User activity lookup failed.") from error

        return [self._as_event(row) for row in rows]

    def verify_integrity(self) -> AuditIntegrityStatus:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          chain_index,
                          timestamp,
                          actor_user_id,
                          project_id,
                          event_type,
                          object_type,
                          object_id,
                          ip,
                          user_agent,
                          request_id,
                          metadata_json,
                          prev_hash,
                          row_hash
                        FROM audit_events
                        ORDER BY chain_index ASC
                        """
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise AuditStoreUnavailableError("Audit integrity verification failed.") from error

        events = [self._as_event(row) for row in rows]
        return self.verify_chain(events)

    @classmethod
    def verify_chain(cls, events: list[AuditEventRecord]) -> AuditIntegrityStatus:
        previous_hash = "GENESIS"
        checked_rows = 0
        chain_head: str | None = None

        for event in events:
            checked_rows += 1
            expected = cls._row_hash(
                chain_index=event.chain_index,
                event_id=event.id,
                timestamp=event.timestamp,
                actor_user_id=event.actor_user_id,
                project_id=event.project_id,
                event_type=event.event_type,
                object_type=event.object_type,
                object_id=event.object_id,
                ip=event.ip,
                user_agent=event.user_agent,
                request_id=event.request_id,
                metadata_json=event.metadata_json,
                prev_hash=event.prev_hash,
            )
            if event.prev_hash != previous_hash or event.row_hash != expected:
                return AuditIntegrityStatus(
                    checked_rows=checked_rows,
                    chain_head=chain_head,
                    is_valid=False,
                    first_invalid_chain_index=event.chain_index,
                    first_invalid_event_id=event.id,
                    detail="Audit hash chain verification failed.",
                )

            previous_hash = event.row_hash
            chain_head = event.row_hash

        return AuditIntegrityStatus(
            checked_rows=checked_rows,
            chain_head=chain_head,
            is_valid=True,
            first_invalid_chain_index=None,
            first_invalid_event_id=None,
            detail="Audit hash chain verified.",
        )
