import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from app.auth.models import UserRecord
from app.auth.store import AuthStore
from app.core.config import Settings
from app.projects.models import (
    AccessTier,
    BaselinePolicySnapshot,
    ProjectMember,
    ProjectRole,
    ProjectStatus,
    ProjectSummary,
)

BASELINE_POLICY_SNAPSHOT_ID = "baseline-phase0-v1"
BASELINE_POLICY_SEEDED_BY = "SYSTEM_PHASE_0"
BASELINE_POLICY_RULES = {
    "name": "Phase 0 Baseline Privacy Policy",
    "version": 1,
    "categories": [
        {"id": "PERSON_NAME", "action": "MASK", "review_required_below": 0.9},
        {"id": "ADDRESS", "action": "MASK", "review_required_below": 0.9},
        {"id": "EMAIL", "action": "MASK", "review_required_below": 0.85},
        {"id": "PHONE", "action": "MASK", "review_required_below": 0.85},
        {"id": "GOVERNMENT_ID", "action": "MASK", "review_required_below": 0.95},
    ],
    "defaults": {
        "action": "MASK",
        "auto_apply_confidence_threshold": 0.92,
        "require_manual_review_for_uncertain": True,
    },
    "indirect_identifier_handling": "DEFERRED_TO_PHASE_7",
}

PROJECT_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS baseline_policy_snapshots (
      id TEXT PRIMARY KEY,
      snapshot_hash TEXT NOT NULL UNIQUE,
      rules_json JSONB NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      seeded_by TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS projects (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      purpose TEXT NOT NULL,
      status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'ARCHIVED')),
      created_by TEXT NOT NULL REFERENCES users(id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      intended_access_tier TEXT NOT NULL CHECK (
        intended_access_tier IN ('OPEN', 'SAFEGUARDED', 'CONTROLLED')
      ),
      baseline_policy_snapshot_id TEXT NOT NULL
        REFERENCES baseline_policy_snapshots(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS project_members (
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      role TEXT NOT NULL CHECK (role IN ('PROJECT_LEAD', 'RESEARCHER', 'REVIEWER')),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (project_id, user_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_project_members_user_id
      ON project_members(user_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_projects_created_at
      ON projects(created_at DESC)
    """,
)


class ProjectStoreUnavailableError(RuntimeError):
    """Project persistence could not be reached."""


class ProjectNotFoundError(RuntimeError):
    """Project was not found."""


class ProjectMemberNotFoundError(RuntimeError):
    """Project membership was not found."""


class DuplicateProjectMemberError(RuntimeError):
    """Project membership already exists."""


class BaselinePolicySnapshotSeedError(RuntimeError):
    """Seeded baseline policy snapshot is missing or inconsistent."""


class LastProjectLeadConstraintError(RuntimeError):
    """Project must retain at least one PROJECT_LEAD membership."""


class UserLookupError(RuntimeError):
    """User lookup failed."""


class ProjectStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._auth_store = AuthStore(settings)
        self._schema_initialized = False
        self._baseline_seed_inserted = False

    @staticmethod
    def _as_conninfo(database_url: str) -> str:
        if database_url.startswith("postgresql+psycopg://"):
            return database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        return database_url

    def _connect(self) -> psycopg.Connection:
        conninfo = self._as_conninfo(self._settings.database_url)
        return psycopg.connect(conninfo=conninfo, connect_timeout=2)

    @staticmethod
    def _baseline_rules_json() -> str:
        return json.dumps(BASELINE_POLICY_RULES, separators=(",", ":"), sort_keys=True)

    @classmethod
    def _baseline_snapshot_hash(cls) -> str:
        return hashlib.sha256(cls._baseline_rules_json().encode("utf-8")).hexdigest()

    @staticmethod
    def _assert_project_role(role: str) -> ProjectRole:
        if role not in {"PROJECT_LEAD", "RESEARCHER", "REVIEWER"}:
            raise ProjectStoreUnavailableError("Unexpected project role persisted.")
        return role  # type: ignore[return-value]

    @staticmethod
    def _assert_access_tier(tier: str) -> AccessTier:
        if tier not in {"OPEN", "SAFEGUARDED", "CONTROLLED"}:
            raise ProjectStoreUnavailableError("Unexpected project access tier persisted.")
        return tier  # type: ignore[return-value]

    @staticmethod
    def _assert_status(status: str) -> ProjectStatus:
        if status not in {"ACTIVE", "ARCHIVED"}:
            raise ProjectStoreUnavailableError("Unexpected project status persisted.")
        return status  # type: ignore[return-value]

    def _read_seeded_baseline_snapshot(
        self,
        *,
        cursor: psycopg.Cursor,
    ) -> BaselinePolicySnapshot:
        cursor.execute(
            """
            SELECT
              id,
              snapshot_hash,
              rules_json::TEXT AS rules_json,
              seeded_by,
              created_at
            FROM baseline_policy_snapshots
            WHERE id = %(baseline_id)s
            """,
            {"baseline_id": BASELINE_POLICY_SNAPSHOT_ID},
        )
        row = cursor.fetchone()
        if row is None:
            raise BaselinePolicySnapshotSeedError(
                "Seeded baseline policy snapshot could not be loaded."
            )
        expected_hash = self._baseline_snapshot_hash()
        if row["snapshot_hash"] != expected_hash:
            raise BaselinePolicySnapshotSeedError(
                "Seeded baseline policy snapshot hash does not match expected rules."
            )
        return BaselinePolicySnapshot(
            id=row["id"],
            snapshot_hash=row["snapshot_hash"],
            rules_json=row["rules_json"],
            seeded_by=row["seeded_by"],
            created_at=row["created_at"],
        )

    def _ensure_seeded_baseline_snapshot(
        self,
        *,
        cursor: psycopg.Cursor,
    ) -> BaselinePolicySnapshot:
        rules_json = self._baseline_rules_json()
        snapshot_hash = self._baseline_snapshot_hash()
        cursor.execute(
            """
            INSERT INTO baseline_policy_snapshots (
              id,
              snapshot_hash,
              rules_json,
              seeded_by
            )
            VALUES (
              %(id)s,
              %(snapshot_hash)s,
              %(rules_json)s::jsonb,
              %(seeded_by)s
            )
            ON CONFLICT (id) DO NOTHING
            RETURNING id
            """,
            {
                "id": BASELINE_POLICY_SNAPSHOT_ID,
                "snapshot_hash": snapshot_hash,
                "rules_json": rules_json,
                "seeded_by": BASELINE_POLICY_SEEDED_BY,
            },
        )
        self._baseline_seed_inserted = cursor.fetchone() is not None
        return self._read_seeded_baseline_snapshot(cursor=cursor)

    def consume_baseline_seed_inserted(self) -> bool:
        inserted = self._baseline_seed_inserted
        self._baseline_seed_inserted = False
        return inserted

    @staticmethod
    def _as_project_summary(row: dict[str, object]) -> ProjectSummary:
        current_user_role_raw = row.get("current_user_role")
        current_user_role: ProjectRole | None = None
        if isinstance(current_user_role_raw, str):
            current_user_role = ProjectStore._assert_project_role(current_user_role_raw)
        return ProjectSummary(
            id=str(row["id"]),
            name=str(row["name"]),
            purpose=str(row["purpose"]),
            status=ProjectStore._assert_status(str(row["status"])),
            created_by=str(row["created_by"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
            intended_access_tier=ProjectStore._assert_access_tier(str(row["intended_access_tier"])),
            baseline_policy_snapshot_id=str(row["baseline_policy_snapshot_id"]),
            current_user_role=current_user_role,
        )

    @staticmethod
    def _as_project_member(row: dict[str, object]) -> ProjectMember:
        return ProjectMember(
            project_id=str(row["project_id"]),
            user_id=str(row["user_id"]),
            email=str(row["email"]),
            display_name=str(row["display_name"]),
            role=ProjectStore._assert_project_role(str(row["role"])),
            created_at=row["created_at"],  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
        )

    def ensure_schema(self) -> None:
        if self._schema_initialized:
            return

        try:
            self._auth_store.ensure_schema()
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    for statement in PROJECT_SCHEMA_STATEMENTS:
                        cursor.execute(statement)
                    self._ensure_seeded_baseline_snapshot(cursor=cursor)
                connection.commit()
        except (
            psycopg.Error,
            BaselinePolicySnapshotSeedError,
            ProjectStoreUnavailableError,
        ) as error:
            raise ProjectStoreUnavailableError(
                "Project schema could not be initialized."
            ) from error

        self._schema_initialized = True

    def get_seeded_baseline_snapshot(self) -> BaselinePolicySnapshot:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    return self._read_seeded_baseline_snapshot(cursor=cursor)
        except (psycopg.Error, BaselinePolicySnapshotSeedError) as error:
            raise ProjectStoreUnavailableError(
                "Baseline policy snapshot could not be loaded."
            ) from error

    def list_projects_for_user(self, *, user_id: str) -> list[ProjectSummary]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          p.id,
                          p.name,
                          p.purpose,
                          p.status,
                          p.created_by,
                          p.created_at,
                          p.intended_access_tier,
                          p.baseline_policy_snapshot_id,
                          pm.role AS current_user_role
                        FROM projects AS p
                        INNER JOIN project_members AS pm
                          ON pm.project_id = p.id
                        WHERE pm.user_id = %(user_id)s
                        ORDER BY p.created_at DESC, p.name ASC
                        """,
                        {"user_id": user_id},
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise ProjectStoreUnavailableError("Project listing failed.") from error

        return [self._as_project_summary(row) for row in rows]

    def create_project(
        self,
        *,
        name: str,
        purpose: str,
        intended_access_tier: AccessTier,
        created_by_user_id: str,
    ) -> ProjectSummary:
        self.ensure_schema()
        now = datetime.now(UTC)
        project_id = str(uuid4())

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    baseline = self._read_seeded_baseline_snapshot(cursor=cursor)
                    cursor.execute(
                        """
                        INSERT INTO projects (
                          id,
                          name,
                          purpose,
                          status,
                          created_by,
                          created_at,
                          intended_access_tier,
                          baseline_policy_snapshot_id
                        )
                        VALUES (
                          %(id)s,
                          %(name)s,
                          %(purpose)s,
                          'ACTIVE',
                          %(created_by)s,
                          %(created_at)s,
                          %(intended_access_tier)s,
                          %(baseline_policy_snapshot_id)s
                        )
                        """,
                        {
                            "id": project_id,
                            "name": name,
                            "purpose": purpose,
                            "created_by": created_by_user_id,
                            "created_at": now,
                            "intended_access_tier": intended_access_tier,
                            "baseline_policy_snapshot_id": baseline.id,
                        },
                    )
                    cursor.execute(
                        """
                        INSERT INTO project_members (
                          project_id,
                          user_id,
                          role,
                          created_at,
                          updated_at
                        )
                        VALUES (
                          %(project_id)s,
                          %(user_id)s,
                          'PROJECT_LEAD',
                          %(created_at)s,
                          %(updated_at)s
                        )
                        """,
                        {
                            "project_id": project_id,
                            "user_id": created_by_user_id,
                            "created_at": now,
                            "updated_at": now,
                        },
                    )
                    cursor.execute(
                        """
                        SELECT
                          p.id,
                          p.name,
                          p.purpose,
                          p.status,
                          p.created_by,
                          p.created_at,
                          p.intended_access_tier,
                          p.baseline_policy_snapshot_id,
                          pm.role AS current_user_role
                        FROM projects AS p
                        INNER JOIN project_members AS pm
                          ON pm.project_id = p.id
                        WHERE p.id = %(project_id)s
                          AND pm.user_id = %(user_id)s
                        """,
                        {"project_id": project_id, "user_id": created_by_user_id},
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise ProjectStoreUnavailableError(
                            "Project could not be loaded after create."
                        )
                connection.commit()
        except psycopg.Error as error:
            raise ProjectStoreUnavailableError("Project creation failed.") from error

        return self._as_project_summary(row)

    def get_project_summary_for_user(
        self,
        *,
        project_id: str,
        user_id: str,
    ) -> ProjectSummary | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          p.id,
                          p.name,
                          p.purpose,
                          p.status,
                          p.created_by,
                          p.created_at,
                          p.intended_access_tier,
                          p.baseline_policy_snapshot_id,
                          pm.role AS current_user_role
                        FROM projects AS p
                        INNER JOIN project_members AS pm
                          ON pm.project_id = p.id
                        WHERE p.id = %(project_id)s
                          AND pm.user_id = %(user_id)s
                        """,
                        {"project_id": project_id, "user_id": user_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise ProjectStoreUnavailableError("Project summary lookup failed.") from error

        if row is None:
            return None
        return self._as_project_summary(row)

    def get_project_summary(
        self,
        *,
        project_id: str,
    ) -> ProjectSummary | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          p.id,
                          p.name,
                          p.purpose,
                          p.status,
                          p.created_by,
                          p.created_at,
                          p.intended_access_tier,
                          p.baseline_policy_snapshot_id,
                          NULL::TEXT AS current_user_role
                        FROM projects AS p
                        WHERE p.id = %(project_id)s
                        """,
                        {"project_id": project_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise ProjectStoreUnavailableError("Project lookup failed.") from error

        if row is None:
            return None
        return self._as_project_summary(row)

    def lookup_user_by_email(self, *, email: str) -> UserRecord | None:
        self.ensure_schema()
        normalized = email.strip().lower()
        if not normalized:
            raise UserLookupError("User email cannot be empty.")

        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          u.id,
                          u.oidc_sub,
                          u.email,
                          u.display_name,
                          u.last_login_at,
                          COALESCE(
                            ARRAY_AGG(r.role) FILTER (WHERE r.role IS NOT NULL),
                            ARRAY[]::TEXT[]
                          ) AS platform_roles
                        FROM users AS u
                        LEFT JOIN user_platform_roles AS r
                          ON r.user_id = u.id
                        WHERE LOWER(u.email) = %(email)s
                        GROUP BY u.id, u.oidc_sub, u.email, u.display_name, u.last_login_at
                        """,
                        {"email": normalized},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise ProjectStoreUnavailableError("User lookup failed.") from error

        if row is None:
            return None

        roles = tuple(role for role in row["platform_roles"] if role in {"ADMIN", "AUDITOR"})
        return UserRecord(
            id=row["id"],
            oidc_sub=row["oidc_sub"],
            email=row["email"],
            display_name=row["display_name"],
            last_login_at=row["last_login_at"],
            platform_roles=roles,  # type: ignore[arg-type]
        )

    def list_project_members(
        self,
        *,
        project_id: str,
    ) -> list[ProjectMember]:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          pm.project_id,
                          pm.user_id,
                          u.email,
                          u.display_name,
                          pm.role,
                          pm.created_at,
                          pm.updated_at
                        FROM project_members AS pm
                        INNER JOIN users AS u
                          ON u.id = pm.user_id
                        WHERE pm.project_id = %(project_id)s
                        ORDER BY
                          CASE pm.role
                            WHEN 'PROJECT_LEAD' THEN 0
                            WHEN 'RESEARCHER' THEN 1
                            ELSE 2
                          END,
                          u.display_name ASC,
                          u.email ASC
                        """,
                        {"project_id": project_id},
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as error:
            raise ProjectStoreUnavailableError("Project member listing failed.") from error

        return [self._as_project_member(row) for row in rows]

    def get_project_member(
        self,
        *,
        project_id: str,
        user_id: str,
    ) -> ProjectMember | None:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT
                          pm.project_id,
                          pm.user_id,
                          u.email,
                          u.display_name,
                          pm.role,
                          pm.created_at,
                          pm.updated_at
                        FROM project_members AS pm
                        INNER JOIN users AS u
                          ON u.id = pm.user_id
                        WHERE pm.project_id = %(project_id)s
                          AND pm.user_id = %(user_id)s
                        """,
                        {"project_id": project_id, "user_id": user_id},
                    )
                    row = cursor.fetchone()
        except psycopg.Error as error:
            raise ProjectStoreUnavailableError("Project member lookup failed.") from error

        if row is None:
            return None
        return self._as_project_member(row)

    def add_project_member(
        self,
        *,
        project_id: str,
        user_id: str,
        role: ProjectRole,
    ) -> ProjectMember:
        self.ensure_schema()
        now = datetime.now(UTC)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO project_members (
                          project_id,
                          user_id,
                          role,
                          created_at,
                          updated_at
                        )
                        VALUES (
                          %(project_id)s,
                          %(user_id)s,
                          %(role)s,
                          %(created_at)s,
                          %(updated_at)s
                        )
                        ON CONFLICT (project_id, user_id) DO NOTHING
                        """,
                        {
                            "project_id": project_id,
                            "user_id": user_id,
                            "role": role,
                            "created_at": now,
                            "updated_at": now,
                        },
                    )
                    if cursor.rowcount == 0:
                        raise DuplicateProjectMemberError("Project member already exists.")
                    cursor.execute(
                        """
                        SELECT
                          pm.project_id,
                          pm.user_id,
                          u.email,
                          u.display_name,
                          pm.role,
                          pm.created_at,
                          pm.updated_at
                        FROM project_members AS pm
                        INNER JOIN users AS u
                          ON u.id = pm.user_id
                        WHERE pm.project_id = %(project_id)s
                          AND pm.user_id = %(user_id)s
                        """,
                        {"project_id": project_id, "user_id": user_id},
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise ProjectStoreUnavailableError(
                            "Project member could not be loaded after add."
                        )
                connection.commit()
        except DuplicateProjectMemberError:
            raise
        except psycopg.Error as error:
            raise ProjectStoreUnavailableError("Project member add failed.") from error

        return self._as_project_member(row)

    def _count_project_role(
        self,
        *,
        cursor: psycopg.Cursor,
        project_id: str,
        role: ProjectRole,
    ) -> int:
        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM project_members
            WHERE project_id = %(project_id)s
              AND role = %(role)s
            """,
            {"project_id": project_id, "role": role},
        )
        row = cursor.fetchone()
        return int(row["count"]) if row else 0

    def change_project_member_role(
        self,
        *,
        project_id: str,
        user_id: str,
        role: ProjectRole,
    ) -> ProjectMember:
        self.ensure_schema()
        now = datetime.now(UTC)
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT role
                        FROM project_members
                        WHERE project_id = %(project_id)s
                          AND user_id = %(user_id)s
                        """,
                        {"project_id": project_id, "user_id": user_id},
                    )
                    existing = cursor.fetchone()
                    if existing is None:
                        raise ProjectMemberNotFoundError("Project member not found.")

                    existing_role = self._assert_project_role(str(existing["role"]))
                    if existing_role == "PROJECT_LEAD" and role != "PROJECT_LEAD":
                        lead_count = self._count_project_role(
                            cursor=cursor,
                            project_id=project_id,
                            role="PROJECT_LEAD",
                        )
                        if lead_count <= 1:
                            raise LastProjectLeadConstraintError(
                                "Project must retain at least one PROJECT_LEAD."
                            )

                    cursor.execute(
                        """
                        UPDATE project_members
                        SET
                          role = %(role)s,
                          updated_at = %(updated_at)s
                        WHERE project_id = %(project_id)s
                          AND user_id = %(user_id)s
                        """,
                        {
                            "role": role,
                            "updated_at": now,
                            "project_id": project_id,
                            "user_id": user_id,
                        },
                    )
                    cursor.execute(
                        """
                        SELECT
                          pm.project_id,
                          pm.user_id,
                          u.email,
                          u.display_name,
                          pm.role,
                          pm.created_at,
                          pm.updated_at
                        FROM project_members AS pm
                        INNER JOIN users AS u
                          ON u.id = pm.user_id
                        WHERE pm.project_id = %(project_id)s
                          AND pm.user_id = %(user_id)s
                        """,
                        {"project_id": project_id, "user_id": user_id},
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise ProjectStoreUnavailableError(
                            "Project member could not be loaded after role update."
                        )
                connection.commit()
        except (ProjectMemberNotFoundError, LastProjectLeadConstraintError):
            raise
        except psycopg.Error as error:
            raise ProjectStoreUnavailableError("Project member role change failed.") from error

        return self._as_project_member(row)

    def remove_project_member(
        self,
        *,
        project_id: str,
        user_id: str,
    ) -> ProjectRole:
        self.ensure_schema()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT role
                        FROM project_members
                        WHERE project_id = %(project_id)s
                          AND user_id = %(user_id)s
                        """,
                        {"project_id": project_id, "user_id": user_id},
                    )
                    existing = cursor.fetchone()
                    if existing is None:
                        raise ProjectMemberNotFoundError("Project member not found.")

                    existing_role = self._assert_project_role(str(existing["role"]))
                    if existing_role == "PROJECT_LEAD":
                        lead_count = self._count_project_role(
                            cursor=cursor,
                            project_id=project_id,
                            role="PROJECT_LEAD",
                        )
                        if lead_count <= 1:
                            raise LastProjectLeadConstraintError(
                                "Project must retain at least one PROJECT_LEAD."
                            )

                    cursor.execute(
                        """
                        DELETE FROM project_members
                        WHERE project_id = %(project_id)s
                          AND user_id = %(user_id)s
                        """,
                        {"project_id": project_id, "user_id": user_id},
                    )
                connection.commit()
        except (ProjectMemberNotFoundError, LastProjectLeadConstraintError):
            raise
        except psycopg.Error as error:
            raise ProjectStoreUnavailableError("Project member removal failed.") from error

        return existing_role
