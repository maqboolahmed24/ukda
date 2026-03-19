from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from app.core.config import Settings
from app.projects.store import ProjectStore
from app.security.findings.models import (
    RiskAcceptanceEventRecord,
    RiskAcceptanceEventType,
    RiskAcceptanceRecord,
    RiskAcceptanceStatus,
    SecurityFindingRecord,
    SecurityFindingSeverity,
    SecurityFindingStatus,
)

_VALID_FINDING_STATUSES: set[str] = {"OPEN", "IN_PROGRESS", "RESOLVED"}
_VALID_FINDING_SEVERITIES: set[str] = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
_VALID_RISK_ACCEPTANCE_STATUSES: set[str] = {"ACTIVE", "EXPIRED", "REVOKED"}
_VALID_RISK_ACCEPTANCE_EVENT_TYPES: set[str] = {
    "ACCEPTANCE_CREATED",
    "ACCEPTANCE_REVIEW_SCHEDULED",
    "ACCEPTANCE_RENEWED",
    "ACCEPTANCE_EXPIRED",
    "ACCEPTANCE_REVOKED",
}

SECURITY_FINDINGS_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS security_findings (
      id TEXT PRIMARY KEY,
      status TEXT NOT NULL CHECK (status IN ('OPEN', 'IN_PROGRESS', 'RESOLVED')),
      severity TEXT NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
      owner_user_id TEXT NOT NULL,
      source TEXT NOT NULL,
      opened_at TIMESTAMPTZ NOT NULL,
      resolved_at TIMESTAMPTZ,
      resolution_summary TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_security_findings_status_opened
      ON security_findings(status, opened_at DESC, id DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_security_findings_severity_opened
      ON security_findings(severity, opened_at DESC, id DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS risk_acceptances (
      id TEXT PRIMARY KEY,
      finding_id TEXT NOT NULL REFERENCES security_findings(id) ON DELETE CASCADE,
      status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'EXPIRED', 'REVOKED')),
      justification TEXT NOT NULL,
      approved_by TEXT NOT NULL,
      accepted_at TIMESTAMPTZ NOT NULL,
      expires_at TIMESTAMPTZ,
      review_date TIMESTAMPTZ,
      revoked_by TEXT,
      revoked_at TIMESTAMPTZ,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      CHECK (expires_at IS NOT NULL OR review_date IS NOT NULL)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_risk_acceptances_status_updated
      ON risk_acceptances(status, updated_at DESC, id DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_risk_acceptances_finding_updated
      ON risk_acceptances(finding_id, updated_at DESC, id DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS risk_acceptance_events (
      id BIGSERIAL PRIMARY KEY,
      risk_acceptance_id TEXT NOT NULL REFERENCES risk_acceptances(id) ON DELETE CASCADE,
      event_type TEXT NOT NULL CHECK (
        event_type IN (
          'ACCEPTANCE_CREATED',
          'ACCEPTANCE_REVIEW_SCHEDULED',
          'ACCEPTANCE_RENEWED',
          'ACCEPTANCE_EXPIRED',
          'ACCEPTANCE_REVOKED'
        )
      ),
      actor_user_id TEXT,
      expires_at TIMESTAMPTZ,
      review_date TIMESTAMPTZ,
      reason TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_risk_acceptance_events_acceptance_id
      ON risk_acceptance_events(risk_acceptance_id, id DESC)
    """,
    """
    CREATE OR REPLACE FUNCTION prevent_risk_acceptance_events_mutation()
    RETURNS trigger AS $$
    BEGIN
      RAISE EXCEPTION 'risk_acceptance_events is append-only';
    END;
    $$ LANGUAGE plpgsql
    """,
    """
    DROP TRIGGER IF EXISTS trg_risk_acceptance_events_no_update
      ON risk_acceptance_events
    """,
    """
    CREATE TRIGGER trg_risk_acceptance_events_no_update
    BEFORE UPDATE ON risk_acceptance_events
    FOR EACH ROW
    EXECUTE FUNCTION prevent_risk_acceptance_events_mutation()
    """,
    """
    DROP TRIGGER IF EXISTS trg_risk_acceptance_events_no_delete
      ON risk_acceptance_events
    """,
    """
    CREATE TRIGGER trg_risk_acceptance_events_no_delete
    BEFORE DELETE ON risk_acceptance_events
    FOR EACH ROW
    EXECUTE FUNCTION prevent_risk_acceptance_events_mutation()
    """,
)


class SecurityStoreUnavailableError(RuntimeError):
    """Security findings persistence is unavailable."""


class SecurityFindingNotFoundError(RuntimeError):
    """Requested security finding was not found."""


class RiskAcceptanceNotFoundError(RuntimeError):
    """Requested risk acceptance was not found."""


class RiskAcceptanceConflictError(RuntimeError):
    """Risk acceptance transition or payload is invalid."""


class SecurityFindingsStore:
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
                    for statement in SECURITY_FINDINGS_SCHEMA_STATEMENTS:
                        cursor.execute(statement)
                connection.commit()
        except psycopg.Error as error:
            raise SecurityStoreUnavailableError(
                "Security findings schema could not be initialized."
            ) from error
        self._schema_initialized = True

    @staticmethod
    def _assert_finding_status(value: str) -> SecurityFindingStatus:
        if value not in _VALID_FINDING_STATUSES:
            raise SecurityStoreUnavailableError("Unexpected security finding status persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_finding_severity(value: str) -> SecurityFindingSeverity:
        if value not in _VALID_FINDING_SEVERITIES:
            raise SecurityStoreUnavailableError("Unexpected security finding severity persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_risk_acceptance_status(value: str) -> RiskAcceptanceStatus:
        if value not in _VALID_RISK_ACCEPTANCE_STATUSES:
            raise SecurityStoreUnavailableError("Unexpected risk acceptance status persisted.")
        return value  # type: ignore[return-value]

    @staticmethod
    def _assert_risk_acceptance_event_type(value: str) -> RiskAcceptanceEventType:
        if value not in _VALID_RISK_ACCEPTANCE_EVENT_TYPES:
            raise SecurityStoreUnavailableError(
                "Unexpected risk acceptance event type persisted."
            )
        return value  # type: ignore[return-value]

    @classmethod
    def _as_finding(cls, row: dict[str, object]) -> SecurityFindingRecord:
        return SecurityFindingRecord(
            id=str(row["id"]),
            status=cls._assert_finding_status(str(row["status"])),
            severity=cls._assert_finding_severity(str(row["severity"])),
            owner_user_id=str(row["owner_user_id"]),
            source=str(row["source"]),
            opened_at=row["opened_at"],  # type: ignore[arg-type]
            resolved_at=row.get("resolved_at"),  # type: ignore[arg-type]
            resolution_summary=(
                str(row["resolution_summary"])
                if isinstance(row.get("resolution_summary"), str)
                else None
            ),
            created_at=row["created_at"],  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_risk_acceptance(cls, row: dict[str, object]) -> RiskAcceptanceRecord:
        return RiskAcceptanceRecord(
            id=str(row["id"]),
            finding_id=str(row["finding_id"]),
            status=cls._assert_risk_acceptance_status(str(row["status"])),
            justification=str(row["justification"]),
            approved_by=str(row["approved_by"]),
            accepted_at=row["accepted_at"],  # type: ignore[arg-type]
            expires_at=row.get("expires_at"),  # type: ignore[arg-type]
            review_date=row.get("review_date"),  # type: ignore[arg-type]
            revoked_by=(str(row["revoked_by"]) if isinstance(row.get("revoked_by"), str) else None),
            revoked_at=row.get("revoked_at"),  # type: ignore[arg-type]
            created_at=row["created_at"],  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    @classmethod
    def _as_risk_acceptance_event(
        cls, row: dict[str, object]
    ) -> RiskAcceptanceEventRecord:
        return RiskAcceptanceEventRecord(
            id=int(row["id"]),
            risk_acceptance_id=str(row["risk_acceptance_id"]),
            event_type=cls._assert_risk_acceptance_event_type(str(row["event_type"])),
            actor_user_id=(
                str(row["actor_user_id"]) if isinstance(row.get("actor_user_id"), str) else None
            ),
            expires_at=row.get("expires_at"),  # type: ignore[arg-type]
            review_date=row.get("review_date"),  # type: ignore[arg-type]
            reason=str(row["reason"]) if isinstance(row.get("reason"), str) else None,
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    def upsert_finding(
        self,
        *,
        finding_id: str,
        status: SecurityFindingStatus,
        severity: SecurityFindingSeverity,
        owner_user_id: str,
        source: str,
        opened_at: datetime,
        resolved_at: datetime | None,
        resolution_summary: str | None,
    ) -> SecurityFindingRecord:
        self.ensure_schema()
        now = self.utcnow()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO security_findings (
                          id,
                          status,
                          severity,
                          owner_user_id,
                          source,
                          opened_at,
                          resolved_at,
                          resolution_summary,
                          created_at,
                          updated_at
                        )
                        VALUES (
                          %(id)s,
                          %(status)s,
                          %(severity)s,
                          %(owner_user_id)s,
                          %(source)s,
                          %(opened_at)s,
                          %(resolved_at)s,
                          %(resolution_summary)s,
                          %(created_at)s,
                          %(updated_at)s
                        )
                        ON CONFLICT (id) DO UPDATE
                        SET
                          status = EXCLUDED.status,
                          severity = EXCLUDED.severity,
                          owner_user_id = EXCLUDED.owner_user_id,
                          source = EXCLUDED.source,
                          opened_at = LEAST(security_findings.opened_at, EXCLUDED.opened_at),
                          resolved_at = EXCLUDED.resolved_at,
                          resolution_summary = EXCLUDED.resolution_summary,
                          updated_at = EXCLUDED.updated_at
                        RETURNING
                          id,
                          status,
                          severity,
                          owner_user_id,
                          source,
                          opened_at,
                          resolved_at,
                          resolution_summary,
                          created_at,
                          updated_at
                        """,
                        {
                            "id": finding_id.strip(),
                            "status": status,
                            "severity": severity,
                            "owner_user_id": owner_user_id.strip(),
                            "source": source.strip(),
                            "opened_at": opened_at,
                            "resolved_at": resolved_at,
                            "resolution_summary": resolution_summary,
                            "created_at": now,
                            "updated_at": now,
                        },
                    )
                    row = cursor.fetchone()
                connection.commit()
        except psycopg.Error as error:
            raise SecurityStoreUnavailableError("Security finding upsert failed.") from error
        if row is None:
            raise SecurityStoreUnavailableError("Security finding upsert failed.")
        return self._as_finding(row)

    def list_findings(
        self,
        *,
        statuses: set[SecurityFindingStatus] | None = None,
        severities: set[SecurityFindingSeverity] | None = None,
    ) -> list[SecurityFindingRecord]:
        self.ensure_schema()
        where_clauses = []
        params: dict[str, object] = {}
        if statuses:
            where_clauses.append("status = ANY(%(statuses)s)")
            params["statuses"] = list(statuses)
        if severities:
            where_clauses.append("severity = ANY(%(severities)s)")
            params["severities"] = list(severities)
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        f"""
                        SELECT
                          id,
                          status,
                          severity,
                          owner_user_id,
                          source,
                          opened_at,
                          resolved_at,
                          resolution_summary,
                          created_at,
                          updated_at
                        FROM security_findings
                        {where_sql}
                        ORDER BY
                          CASE severity
                            WHEN 'CRITICAL' THEN 0
                            WHEN 'HIGH' THEN 1
                            WHEN 'MEDIUM' THEN 2
                            ELSE 3
                          END ASC,
                          opened_at DESC,
                          id DESC
                        """,
                        params,
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise SecurityStoreUnavailableError("Security findings list failed.") from error
        return [self._as_finding(row) for row in rows]

    def get_finding(self, *, finding_id: str) -> SecurityFindingRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          status,
                          severity,
                          owner_user_id,
                          source,
                          opened_at,
                          resolved_at,
                          resolution_summary,
                          created_at,
                          updated_at
                        FROM security_findings
                        WHERE id = %(finding_id)s
                        LIMIT 1
                        """,
                        {"finding_id": finding_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise SecurityStoreUnavailableError("Security finding lookup failed.") from error
        if row is None:
            raise SecurityFindingNotFoundError(f"Security finding {finding_id} was not found.")
        return self._as_finding(row)

    def _append_risk_acceptance_event(
        self,
        *,
        cursor: psycopg.Cursor,
        risk_acceptance_id: str,
        event_type: RiskAcceptanceEventType,
        actor_user_id: str | None,
        expires_at: datetime | None,
        review_date: datetime | None,
        reason: str | None,
    ) -> RiskAcceptanceEventRecord:
        cursor.execute(
            """
            INSERT INTO risk_acceptance_events (
              risk_acceptance_id,
              event_type,
              actor_user_id,
              expires_at,
              review_date,
              reason
            )
            VALUES (
              %(risk_acceptance_id)s,
              %(event_type)s,
              %(actor_user_id)s,
              %(expires_at)s,
              %(review_date)s,
              %(reason)s
            )
            RETURNING
              id,
              risk_acceptance_id,
              event_type,
              actor_user_id,
              expires_at,
              review_date,
              reason,
              created_at
            """,
            {
                "risk_acceptance_id": risk_acceptance_id,
                "event_type": event_type,
                "actor_user_id": actor_user_id,
                "expires_at": expires_at,
                "review_date": review_date,
                "reason": reason,
            },
        )
        row = cursor.fetchone()
        if row is None:
            raise SecurityStoreUnavailableError("Risk acceptance event append failed.")
        return self._as_risk_acceptance_event(row)

    def _recompute_projection_locked(
        self, *, cursor: psycopg.Cursor, risk_acceptance_id: str
    ) -> RiskAcceptanceRecord:
        cursor.execute(
            """
            SELECT
              id,
              finding_id,
              status,
              justification,
              approved_by,
              accepted_at,
              expires_at,
              review_date,
              revoked_by,
              revoked_at,
              created_at,
              updated_at
            FROM risk_acceptances
            WHERE id = %(risk_acceptance_id)s
            LIMIT 1
            FOR UPDATE
            """,
            {"risk_acceptance_id": risk_acceptance_id},
        )
        base_row = cursor.fetchone()
        if base_row is None:
            raise RiskAcceptanceNotFoundError(
                f"Risk acceptance {risk_acceptance_id} was not found."
            )
        base_record = self._as_risk_acceptance(base_row)

        cursor.execute(
            """
            SELECT
              id,
              risk_acceptance_id,
              event_type,
              actor_user_id,
              expires_at,
              review_date,
              reason,
              created_at
            FROM risk_acceptance_events
            WHERE risk_acceptance_id = %(risk_acceptance_id)s
            ORDER BY id ASC
            """,
            {"risk_acceptance_id": risk_acceptance_id},
        )
        event_rows = cursor.fetchall()
        events = [self._as_risk_acceptance_event(row) for row in event_rows]

        projection_status = base_record.status
        projection_justification = base_record.justification
        projection_approved_by = base_record.approved_by
        projection_accepted_at = base_record.accepted_at
        projection_expires_at = base_record.expires_at
        projection_review_date = base_record.review_date
        projection_revoked_by = base_record.revoked_by
        projection_revoked_at = base_record.revoked_at
        projection_updated_at = base_record.updated_at

        for event in events:
            projection_updated_at = event.created_at
            if event.event_type in {"ACCEPTANCE_CREATED", "ACCEPTANCE_RENEWED"}:
                projection_status = "ACTIVE"
                if event.reason:
                    projection_justification = event.reason
                if event.actor_user_id:
                    projection_approved_by = event.actor_user_id
                projection_accepted_at = event.created_at
                if event.expires_at is not None or event.review_date is not None:
                    projection_expires_at = event.expires_at
                    projection_review_date = event.review_date
                projection_revoked_by = None
                projection_revoked_at = None
                continue
            if event.event_type == "ACCEPTANCE_REVIEW_SCHEDULED":
                if event.reason:
                    projection_justification = event.reason
                if event.review_date is not None:
                    projection_review_date = event.review_date
                continue
            if event.event_type == "ACCEPTANCE_EXPIRED":
                projection_status = "EXPIRED"
                projection_revoked_by = None
                projection_revoked_at = None
                continue
            if event.event_type == "ACCEPTANCE_REVOKED":
                projection_status = "REVOKED"
                if event.reason:
                    projection_justification = event.reason
                projection_revoked_by = event.actor_user_id
                projection_revoked_at = event.created_at
                continue

        cursor.execute(
            """
            UPDATE risk_acceptances
            SET
              status = %(status)s,
              justification = %(justification)s,
              approved_by = %(approved_by)s,
              accepted_at = %(accepted_at)s,
              expires_at = %(expires_at)s,
              review_date = %(review_date)s,
              revoked_by = %(revoked_by)s,
              revoked_at = %(revoked_at)s,
              updated_at = %(updated_at)s
            WHERE id = %(risk_acceptance_id)s
            RETURNING
              id,
              finding_id,
              status,
              justification,
              approved_by,
              accepted_at,
              expires_at,
              review_date,
              revoked_by,
              revoked_at,
              created_at,
              updated_at
            """,
            {
                "risk_acceptance_id": risk_acceptance_id,
                "status": projection_status,
                "justification": projection_justification,
                "approved_by": projection_approved_by,
                "accepted_at": projection_accepted_at,
                "expires_at": projection_expires_at,
                "review_date": projection_review_date,
                "revoked_by": projection_revoked_by,
                "revoked_at": projection_revoked_at,
                "updated_at": projection_updated_at,
            },
        )
        row = cursor.fetchone()
        if row is None:
            raise SecurityStoreUnavailableError("Risk acceptance projection update failed.")
        return self._as_risk_acceptance(row)

    def create_risk_acceptance(
        self,
        *,
        finding_id: str,
        justification: str,
        approved_by: str,
        expires_at: datetime | None,
        review_date: datetime | None,
    ) -> RiskAcceptanceRecord:
        self.ensure_schema()
        now = self.utcnow()
        risk_acceptance_id = f"risk-acceptance-{uuid4()}"
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT id
                        FROM security_findings
                        WHERE id = %(finding_id)s
                        LIMIT 1
                        """,
                        {"finding_id": finding_id},
                    )
                    if cursor.fetchone() is None:
                        raise SecurityFindingNotFoundError(
                            f"Security finding {finding_id} was not found."
                        )

                    cursor.execute(
                        """
                        SELECT id
                        FROM risk_acceptances
                        WHERE finding_id = %(finding_id)s
                          AND status = 'ACTIVE'
                        LIMIT 1
                        """,
                        {"finding_id": finding_id},
                    )
                    existing_active = cursor.fetchone()
                    if existing_active is not None:
                        raise RiskAcceptanceConflictError(
                            "An ACTIVE risk acceptance already exists for this finding."
                        )

                    cursor.execute(
                        """
                        INSERT INTO risk_acceptances (
                          id,
                          finding_id,
                          status,
                          justification,
                          approved_by,
                          accepted_at,
                          expires_at,
                          review_date,
                          revoked_by,
                          revoked_at,
                          created_at,
                          updated_at
                        )
                        VALUES (
                          %(id)s,
                          %(finding_id)s,
                          'ACTIVE',
                          %(justification)s,
                          %(approved_by)s,
                          %(accepted_at)s,
                          %(expires_at)s,
                          %(review_date)s,
                          NULL,
                          NULL,
                          %(created_at)s,
                          %(updated_at)s
                        )
                        """,
                        {
                            "id": risk_acceptance_id,
                            "finding_id": finding_id,
                            "justification": justification,
                            "approved_by": approved_by,
                            "accepted_at": now,
                            "expires_at": expires_at,
                            "review_date": review_date,
                            "created_at": now,
                            "updated_at": now,
                        },
                    )

                    self._append_risk_acceptance_event(
                        cursor=cursor,
                        risk_acceptance_id=risk_acceptance_id,
                        event_type="ACCEPTANCE_CREATED",
                        actor_user_id=approved_by,
                        expires_at=expires_at,
                        review_date=review_date,
                        reason=justification,
                    )
                    projected = self._recompute_projection_locked(
                        cursor=cursor,
                        risk_acceptance_id=risk_acceptance_id,
                    )
                connection.commit()
        except (
            SecurityFindingNotFoundError,
            RiskAcceptanceConflictError,
        ):
            raise
        except psycopg.Error as error:
            raise SecurityStoreUnavailableError("Risk acceptance create failed.") from error
        return projected

    def list_risk_acceptances(
        self,
        *,
        status: RiskAcceptanceStatus | None = None,
        finding_id: str | None = None,
    ) -> list[RiskAcceptanceRecord]:
        self.ensure_schema()
        where_clauses = []
        params: dict[str, object] = {}
        if status is not None:
            where_clauses.append("status = %(status)s")
            params["status"] = status
        if finding_id is not None:
            where_clauses.append("finding_id = %(finding_id)s")
            params["finding_id"] = finding_id
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        f"""
                        SELECT
                          id,
                          finding_id,
                          status,
                          justification,
                          approved_by,
                          accepted_at,
                          expires_at,
                          review_date,
                          revoked_by,
                          revoked_at,
                          created_at,
                          updated_at
                        FROM risk_acceptances
                        {where_sql}
                        ORDER BY updated_at DESC, id DESC
                        """,
                        params,
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise SecurityStoreUnavailableError("Risk acceptances list failed.") from error
        return [self._as_risk_acceptance(row) for row in rows]

    def get_risk_acceptance(self, *, risk_acceptance_id: str) -> RiskAcceptanceRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          finding_id,
                          status,
                          justification,
                          approved_by,
                          accepted_at,
                          expires_at,
                          review_date,
                          revoked_by,
                          revoked_at,
                          created_at,
                          updated_at
                        FROM risk_acceptances
                        WHERE id = %(risk_acceptance_id)s
                        LIMIT 1
                        """,
                        {"risk_acceptance_id": risk_acceptance_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise SecurityStoreUnavailableError("Risk acceptance lookup failed.") from error
        if row is None:
            raise RiskAcceptanceNotFoundError(
                f"Risk acceptance {risk_acceptance_id} was not found."
            )
        return self._as_risk_acceptance(row)

    def list_risk_acceptance_events(
        self, *, risk_acceptance_id: str
    ) -> list[RiskAcceptanceEventRecord]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          id,
                          risk_acceptance_id,
                          event_type,
                          actor_user_id,
                          expires_at,
                          review_date,
                          reason,
                          created_at
                        FROM risk_acceptance_events
                        WHERE risk_acceptance_id = %(risk_acceptance_id)s
                        ORDER BY id DESC
                        """,
                        {"risk_acceptance_id": risk_acceptance_id},
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise SecurityStoreUnavailableError("Risk acceptance events lookup failed.") from error
        return [self._as_risk_acceptance_event(row) for row in rows]

    def renew_risk_acceptance(
        self,
        *,
        risk_acceptance_id: str,
        actor_user_id: str,
        expires_at: datetime | None,
        review_date: datetime | None,
        reason: str,
    ) -> RiskAcceptanceRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    current = self._recompute_projection_locked(
                        cursor=cursor,
                        risk_acceptance_id=risk_acceptance_id,
                    )
                    if current.status == "REVOKED":
                        raise RiskAcceptanceConflictError(
                            "REVOKED risk acceptances cannot be renewed."
                        )
                    self._append_risk_acceptance_event(
                        cursor=cursor,
                        risk_acceptance_id=risk_acceptance_id,
                        event_type="ACCEPTANCE_RENEWED",
                        actor_user_id=actor_user_id,
                        expires_at=expires_at,
                        review_date=review_date,
                        reason=reason,
                    )
                    projected = self._recompute_projection_locked(
                        cursor=cursor,
                        risk_acceptance_id=risk_acceptance_id,
                    )
                connection.commit()
        except (
            RiskAcceptanceNotFoundError,
            RiskAcceptanceConflictError,
        ):
            raise
        except psycopg.Error as error:
            raise SecurityStoreUnavailableError("Risk acceptance renew failed.") from error
        return projected

    def schedule_risk_acceptance_review(
        self,
        *,
        risk_acceptance_id: str,
        actor_user_id: str,
        review_date: datetime,
        reason: str | None,
    ) -> RiskAcceptanceRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    current = self._recompute_projection_locked(
                        cursor=cursor,
                        risk_acceptance_id=risk_acceptance_id,
                    )
                    if current.status != "ACTIVE":
                        raise RiskAcceptanceConflictError(
                            "Only ACTIVE risk acceptances can schedule reviews."
                        )
                    self._append_risk_acceptance_event(
                        cursor=cursor,
                        risk_acceptance_id=risk_acceptance_id,
                        event_type="ACCEPTANCE_REVIEW_SCHEDULED",
                        actor_user_id=actor_user_id,
                        expires_at=current.expires_at,
                        review_date=review_date,
                        reason=reason,
                    )
                    projected = self._recompute_projection_locked(
                        cursor=cursor,
                        risk_acceptance_id=risk_acceptance_id,
                    )
                connection.commit()
        except (
            RiskAcceptanceNotFoundError,
            RiskAcceptanceConflictError,
        ):
            raise
        except psycopg.Error as error:
            raise SecurityStoreUnavailableError(
                "Risk acceptance review schedule failed."
            ) from error
        return projected

    def revoke_risk_acceptance(
        self,
        *,
        risk_acceptance_id: str,
        actor_user_id: str,
        reason: str,
    ) -> RiskAcceptanceRecord:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    current = self._recompute_projection_locked(
                        cursor=cursor,
                        risk_acceptance_id=risk_acceptance_id,
                    )
                    if current.status == "REVOKED":
                        return current
                    self._append_risk_acceptance_event(
                        cursor=cursor,
                        risk_acceptance_id=risk_acceptance_id,
                        event_type="ACCEPTANCE_REVOKED",
                        actor_user_id=actor_user_id,
                        expires_at=current.expires_at,
                        review_date=current.review_date,
                        reason=reason,
                    )
                    projected = self._recompute_projection_locked(
                        cursor=cursor,
                        risk_acceptance_id=risk_acceptance_id,
                    )
                connection.commit()
        except RiskAcceptanceNotFoundError:
            raise
        except psycopg.Error as error:
            raise SecurityStoreUnavailableError("Risk acceptance revoke failed.") from error
        return projected

    def expire_due_risk_acceptances(
        self,
        *,
        now: datetime | None = None,
        actor_user_id: str | None = "system-risk-expiry-evaluator",
    ) -> list[RiskAcceptanceRecord]:
        self.ensure_schema()
        effective_now = now or self.utcnow()
        expired: list[RiskAcceptanceRecord] = []
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT id
                        FROM risk_acceptances
                        WHERE status = 'ACTIVE'
                          AND expires_at IS NOT NULL
                          AND expires_at <= %(effective_now)s
                        ORDER BY expires_at ASC, id ASC
                        FOR UPDATE
                        """,
                        {"effective_now": effective_now},
                    )
                    rows = cursor.fetchall()
                    for row in rows:
                        risk_acceptance_id = str(row["id"])
                        current = self._recompute_projection_locked(
                            cursor=cursor,
                            risk_acceptance_id=risk_acceptance_id,
                        )
                        if current.status != "ACTIVE":
                            continue
                        if current.expires_at is None or current.expires_at > effective_now:
                            continue
                        self._append_risk_acceptance_event(
                            cursor=cursor,
                            risk_acceptance_id=risk_acceptance_id,
                            event_type="ACCEPTANCE_EXPIRED",
                            actor_user_id=actor_user_id,
                            expires_at=current.expires_at,
                            review_date=current.review_date,
                            reason="Risk acceptance expired at scheduled expires_at timestamp.",
                        )
                        projected = self._recompute_projection_locked(
                            cursor=cursor,
                            risk_acceptance_id=risk_acceptance_id,
                        )
                        expired.append(projected)
                connection.commit()
        except psycopg.Error as error:
            raise SecurityStoreUnavailableError(
                "Risk acceptance expiry evaluation failed."
            ) from error
        return expired
