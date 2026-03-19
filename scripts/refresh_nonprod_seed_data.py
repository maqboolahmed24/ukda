#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

import psycopg

Environment = Literal["dev", "staging", "prod"]

MANAGED_PROJECT_PREFIX = "seed-nonprod-"
ALLOWED_PLATFORM_ROLES = {"ADMIN", "AUDITOR"}
ALLOWED_PROJECT_ROLES = {"PROJECT_LEAD", "RESEARCHER", "REVIEWER"}
ALLOWED_ACCESS_TIERS = {"OPEN", "SAFEGUARDED", "CONTROLLED"}

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

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS users (
      id TEXT PRIMARY KEY,
      oidc_sub TEXT NOT NULL UNIQUE,
      email TEXT NOT NULL,
      display_name TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      last_login_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_platform_roles (
      user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      role TEXT NOT NULL CHECK (role IN ('ADMIN', 'AUDITOR')),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (user_id, role)
    )
    """,
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
)


@dataclass(frozen=True)
class SeedUser:
    oidc_sub: str
    email: str
    display_name: str
    platform_roles: tuple[str, ...]


@dataclass(frozen=True)
class SeedMember:
    user_oidc_sub: str
    role: str


@dataclass(frozen=True)
class SeedProject:
    id: str
    name: str
    purpose: str
    intended_access_tier: str
    created_by_user_oidc_sub: str
    members: tuple[SeedMember, ...]


@dataclass(frozen=True)
class SeedPack:
    version: str
    classification: str
    allowed_environments: tuple[str, ...]
    users: tuple[SeedUser, ...]
    projects: tuple[SeedProject, ...]


def _baseline_rules_json() -> str:
    return json.dumps(BASELINE_POLICY_RULES, separators=(",", ":"), sort_keys=True)


def _baseline_snapshot_hash() -> str:
    return hashlib.sha256(_baseline_rules_json().encode("utf-8")).hexdigest()


def _sha256_payload(payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _stable_user_id(oidc_sub: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"ukde-nonprod-seed:{oidc_sub}"))


def _load_seed_pack(path: Path) -> tuple[SeedPack, str]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise RuntimeError(f"Could not read seed pack: {error}") from error
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Seed pack JSON is invalid: {error}") from error

    if not isinstance(raw, dict):
        raise RuntimeError("Seed pack root must be a JSON object.")

    version = str(raw.get("version", "")).strip()
    classification = str(raw.get("classification", "")).strip()
    allowed_envs_raw = raw.get("allowedEnvironments")
    users_raw = raw.get("users")
    projects_raw = raw.get("projects")
    if not version:
        raise RuntimeError("Seed pack version is required.")
    if classification != "SYNTHETIC_ONLY":
        raise RuntimeError("Seed pack classification must be SYNTHETIC_ONLY.")
    if not isinstance(allowed_envs_raw, list) or not allowed_envs_raw:
        raise RuntimeError("Seed pack allowedEnvironments must be a non-empty array.")
    allowed_environments = tuple(
        str(item).strip()
        for item in allowed_envs_raw
        if str(item).strip()
    )
    if not set(allowed_environments).issubset({"dev", "staging"}):
        raise RuntimeError("Seed pack allowed environments may only include dev and staging.")
    if not isinstance(users_raw, list) or not users_raw:
        raise RuntimeError("Seed pack users must be a non-empty array.")
    if not isinstance(projects_raw, list) or not projects_raw:
        raise RuntimeError("Seed pack projects must be a non-empty array.")

    users: list[SeedUser] = []
    seen_oidc_subs: set[str] = set()
    for index, entry in enumerate(users_raw):
        if not isinstance(entry, dict):
            raise RuntimeError(f"Seed user at index {index} must be an object.")
        oidc_sub = str(entry.get("oidcSub", "")).strip()
        email = str(entry.get("email", "")).strip()
        display_name = str(entry.get("displayName", "")).strip()
        roles_raw = entry.get("platformRoles", [])
        if not oidc_sub or not oidc_sub.startswith(MANAGED_PROJECT_PREFIX):
            raise RuntimeError(
                f"Seed user oidcSub '{oidc_sub}' must start with '{MANAGED_PROJECT_PREFIX}'."
            )
        if oidc_sub in seen_oidc_subs:
            raise RuntimeError(f"Duplicate seed user oidcSub '{oidc_sub}'.")
        seen_oidc_subs.add(oidc_sub)
        if not email or not email.endswith(".invalid"):
            raise RuntimeError(
                f"Seed user email '{email}' must use '.invalid' synthetic domain."
            )
        if not display_name:
            raise RuntimeError(f"Seed user '{oidc_sub}' requires displayName.")
        if not isinstance(roles_raw, list):
            raise RuntimeError(f"Seed user '{oidc_sub}' platformRoles must be an array.")
        normalized_roles = tuple(
            role
            for role in [str(item).strip().upper() for item in roles_raw]
            if role in ALLOWED_PLATFORM_ROLES
        )
        if len(normalized_roles) != len({str(item).strip().upper() for item in roles_raw}):
            raise RuntimeError(
                f"Seed user '{oidc_sub}' platformRoles may only contain ADMIN/AUDITOR."
            )
        users.append(
            SeedUser(
                oidc_sub=oidc_sub,
                email=email,
                display_name=display_name,
                platform_roles=normalized_roles,
            )
        )

    projects: list[SeedProject] = []
    seen_project_ids: set[str] = set()
    for index, entry in enumerate(projects_raw):
        if not isinstance(entry, dict):
            raise RuntimeError(f"Seed project at index {index} must be an object.")
        project_id = str(entry.get("id", "")).strip()
        name = str(entry.get("name", "")).strip()
        purpose = str(entry.get("purpose", "")).strip()
        access_tier = str(entry.get("intendedAccessTier", "")).strip().upper()
        created_by = str(entry.get("createdByUserOidcSub", "")).strip()
        members_raw = entry.get("members")
        if not project_id or not project_id.startswith(MANAGED_PROJECT_PREFIX):
            raise RuntimeError(
                f"Seed project id '{project_id}' must start with '{MANAGED_PROJECT_PREFIX}'."
            )
        if project_id in seen_project_ids:
            raise RuntimeError(f"Duplicate seed project id '{project_id}'.")
        seen_project_ids.add(project_id)
        if not name:
            raise RuntimeError(f"Seed project '{project_id}' requires name.")
        if len(purpose) < 12:
            raise RuntimeError(
                f"Seed project '{project_id}' purpose must be at least 12 characters."
            )
        if access_tier not in ALLOWED_ACCESS_TIERS:
            raise RuntimeError(
                f"Seed project '{project_id}' intendedAccessTier must be "
                "OPEN/SAFEGUARDED/CONTROLLED."
            )
        if created_by not in seen_oidc_subs:
            raise RuntimeError(
                f"Seed project '{project_id}' createdByUserOidcSub '{created_by}' is unknown."
            )
        if not isinstance(members_raw, list) or not members_raw:
            raise RuntimeError(f"Seed project '{project_id}' members must be a non-empty array.")
        members: list[SeedMember] = []
        lead_count = 0
        seen_member_user_ids: set[str] = set()
        for member_index, member_entry in enumerate(members_raw):
            if not isinstance(member_entry, dict):
                raise RuntimeError(
                    f"Seed project '{project_id}' member {member_index} must be an object."
                )
            user_oidc_sub = str(member_entry.get("userOidcSub", "")).strip()
            role = str(member_entry.get("role", "")).strip().upper()
            if user_oidc_sub not in seen_oidc_subs:
                raise RuntimeError(
                    f"Seed project '{project_id}' member user '{user_oidc_sub}' is unknown."
                )
            if role not in ALLOWED_PROJECT_ROLES:
                raise RuntimeError(
                    f"Seed project '{project_id}' member role '{role}' is invalid."
                )
            if user_oidc_sub in seen_member_user_ids:
                raise RuntimeError(
                    f"Seed project '{project_id}' has duplicate member '{user_oidc_sub}'."
                )
            seen_member_user_ids.add(user_oidc_sub)
            if role == "PROJECT_LEAD":
                lead_count += 1
            members.append(
                SeedMember(
                    user_oidc_sub=user_oidc_sub,
                    role=role,
                )
            )
        if lead_count == 0:
            raise RuntimeError(f"Seed project '{project_id}' must include one PROJECT_LEAD.")
        projects.append(
            SeedProject(
                id=project_id,
                name=name,
                purpose=purpose,
                intended_access_tier=access_tier,
                created_by_user_oidc_sub=created_by,
                members=tuple(members),
            )
        )

    return (
        SeedPack(
            version=version,
            classification=classification,
            allowed_environments=allowed_environments,
            users=tuple(users),
            projects=tuple(projects),
        ),
        _sha256_payload(raw),
    )


def _connect(database_url: str) -> psycopg.Connection:
    conninfo = database_url
    if database_url.startswith("postgresql+psycopg://"):
        conninfo = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    return psycopg.connect(conninfo=conninfo, connect_timeout=3)


def _ensure_schema(cursor: psycopg.Cursor) -> None:
    for statement in SCHEMA_STATEMENTS:
        cursor.execute(statement)


def _ensure_baseline_snapshot(cursor: psycopg.Cursor) -> None:
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
        ON CONFLICT (id) DO UPDATE
        SET
          snapshot_hash = EXCLUDED.snapshot_hash,
          rules_json = EXCLUDED.rules_json,
          seeded_by = EXCLUDED.seeded_by
        """,
        {
            "id": BASELINE_POLICY_SNAPSHOT_ID,
            "snapshot_hash": _baseline_snapshot_hash(),
            "rules_json": _baseline_rules_json(),
            "seeded_by": BASELINE_POLICY_SEEDED_BY,
        },
    )


def _upsert_seed_user(cursor: psycopg.Cursor, user: SeedUser) -> str:
    now = datetime.now(UTC)
    cursor.execute(
        """
        INSERT INTO users (
          id,
          oidc_sub,
          email,
          display_name,
          created_at,
          last_login_at
        )
        VALUES (
          %(id)s,
          %(oidc_sub)s,
          %(email)s,
          %(display_name)s,
          %(created_at)s,
          %(last_login_at)s
        )
        ON CONFLICT (oidc_sub) DO UPDATE
        SET
          email = EXCLUDED.email,
          display_name = EXCLUDED.display_name,
          last_login_at = EXCLUDED.last_login_at
        RETURNING id
        """,
        {
            "id": _stable_user_id(user.oidc_sub),
            "oidc_sub": user.oidc_sub,
            "email": user.email,
            "display_name": user.display_name,
            "created_at": now,
            "last_login_at": now,
        },
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError(f"Could not upsert seed user '{user.oidc_sub}'.")
    user_id = str(row[0])
    cursor.execute(
        """
        DELETE FROM user_platform_roles
        WHERE user_id = %(user_id)s
        """,
        {"user_id": user_id},
    )
    for role in user.platform_roles:
        cursor.execute(
            """
            INSERT INTO user_platform_roles (user_id, role)
            VALUES (%(user_id)s, %(role)s)
            ON CONFLICT (user_id, role) DO NOTHING
            """,
            {"user_id": user_id, "role": role},
        )
    return user_id


def _sync_seed_projects(
    cursor: psycopg.Cursor,
    *,
    pack: SeedPack,
    user_ids_by_oidc_sub: dict[str, str],
) -> dict[str, int]:
    archived_count = 0
    membership_upserts = 0
    membership_deletes = 0
    project_upserts = 0

    managed_ids = [project.id for project in pack.projects]
    for project in pack.projects:
        created_by_user_id = user_ids_by_oidc_sub[project.created_by_user_oidc_sub]
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
            ON CONFLICT (id) DO UPDATE
            SET
              name = EXCLUDED.name,
              purpose = EXCLUDED.purpose,
              status = 'ACTIVE',
              intended_access_tier = EXCLUDED.intended_access_tier,
              baseline_policy_snapshot_id = EXCLUDED.baseline_policy_snapshot_id
            """,
            {
                "id": project.id,
                "name": project.name,
                "purpose": project.purpose,
                "created_by": created_by_user_id,
                "created_at": datetime.now(UTC),
                "intended_access_tier": project.intended_access_tier,
                "baseline_policy_snapshot_id": BASELINE_POLICY_SNAPSHOT_ID,
            },
        )
        project_upserts += 1

        desired_user_ids = [
            user_ids_by_oidc_sub[member.user_oidc_sub]
            for member in project.members
        ]
        cursor.execute(
            """
            DELETE FROM project_members
            WHERE project_id = %(project_id)s
              AND user_id <> ALL(%(desired_user_ids)s::text[])
            """,
            {"project_id": project.id, "desired_user_ids": desired_user_ids},
        )
        membership_deletes += cursor.rowcount

        for member in project.members:
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
                  %(now)s,
                  %(now)s
                )
                ON CONFLICT (project_id, user_id) DO UPDATE
                SET
                  role = EXCLUDED.role,
                  updated_at = EXCLUDED.updated_at
                """,
                {
                    "project_id": project.id,
                    "user_id": user_ids_by_oidc_sub[member.user_oidc_sub],
                    "role": member.role,
                    "now": datetime.now(UTC),
                },
            )
            membership_upserts += 1

    cursor.execute(
        """
        SELECT id
        FROM projects
        WHERE id LIKE %(prefix)s
        """,
        {"prefix": f"{MANAGED_PROJECT_PREFIX}%"},
    )
    existing_managed_ids = [str(row[0]) for row in cursor.fetchall()]
    stale_ids = [project_id for project_id in existing_managed_ids if project_id not in managed_ids]
    if stale_ids:
        cursor.execute(
            """
            UPDATE projects
            SET status = 'ARCHIVED'
            WHERE id = ANY(%(stale_ids)s::text[])
            """,
            {"stale_ids": stale_ids},
        )
        archived_count += cursor.rowcount
        cursor.execute(
            """
            DELETE FROM project_members
            WHERE project_id = ANY(%(stale_ids)s::text[])
            """,
            {"stale_ids": stale_ids},
        )
        membership_deletes += cursor.rowcount

    return {
        "projectUpserts": project_upserts,
        "membershipUpserts": membership_upserts,
        "membershipDeletes": membership_deletes,
        "archivedStaleManagedProjects": archived_count,
    }


def _validate_environment(environment: str, allowed_environments: tuple[str, ...]) -> None:
    if environment == "prod":
        raise RuntimeError("Non-production seed refresh is blocked in prod.")
    if environment not in set(allowed_environments):
        raise RuntimeError(
            f"Seed pack is not allowed for environment '{environment}'. "
            f"Allowed: {', '.join(allowed_environments)}."
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate or apply deterministic synthetic seed data for dev/staging.",
    )
    parser.add_argument(
        "--pack",
        default="infra/seeds/nonprod/seed-pack.v1.json",
        help="Path to the non-production seed pack JSON file.",
    )
    parser.add_argument(
        "--environment",
        required=True,
        choices=("dev", "staging", "prod"),
        help="Target environment label.",
    )
    parser.add_argument(
        "--output",
        default="output/seeds/latest",
        help="Directory where the seed refresh report is written.",
    )
    parser.add_argument(
        "--database-url",
        default="",
        help="Database URL used only when --apply is set. Falls back to DATABASE_URL env.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the seed pack to the target non-production database.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when validation or apply checks fail.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    output_dir = (repo_root / args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "nonprod-seed-refresh-report.json"

    report: dict[str, object] = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "environment": args.environment,
        "mode": "apply" if args.apply else "validate",
        "overallStatus": "FAIL",
        "detail": "",
        "managedProjectPrefix": MANAGED_PROJECT_PREFIX,
        "applied": False,
    }

    try:
        pack, pack_sha256 = _load_seed_pack((repo_root / args.pack).resolve())
        _validate_environment(args.environment, pack.allowed_environments)
        report["packVersion"] = pack.version
        report["packSha256"] = pack_sha256
        report["classification"] = pack.classification
        report["seedUserCount"] = len(pack.users)
        report["seedProjectCount"] = len(pack.projects)

        if not args.apply:
            report["overallStatus"] = "PASS"
            report["detail"] = "Seed pack validated successfully (no database changes applied)."
            report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
            print(f"nonprod-seed: report written to {report_path}")
            print("nonprod-seed: overall=PASS mode=validate")
            return 0

        database_url = args.database_url.strip() or os.environ.get("DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError(
                "DATABASE_URL is required when --apply is set (via --database-url or env)."
            )

        user_ids_by_oidc_sub: dict[str, str] = {}
        with _connect(database_url) as connection:
            with connection.cursor() as cursor:
                _ensure_schema(cursor)
                _ensure_baseline_snapshot(cursor)
                for user in pack.users:
                    user_ids_by_oidc_sub[user.oidc_sub] = _upsert_seed_user(cursor, user)
                sync_counts = _sync_seed_projects(
                    cursor,
                    pack=pack,
                    user_ids_by_oidc_sub=user_ids_by_oidc_sub,
                )
            connection.commit()

        report["overallStatus"] = "PASS"
        report["detail"] = "Seed pack applied successfully."
        report["applied"] = True
        report.update(sync_counts)
    except Exception as error:  # pragma: no cover - CLI-level failure mapping
        report["overallStatus"] = "FAIL"
        report["detail"] = str(error)
        if args.strict:
            report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
            print(f"nonprod-seed: report written to {report_path}")
            print(f"nonprod-seed: overall=FAIL detail={error}", file=sys.stderr)
            return 1
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"nonprod-seed: report written to {report_path}")
    print(
        "nonprod-seed: "
        f"overall={report['overallStatus']} mode={report['mode']} applied={report['applied']}"
    )
    if report["overallStatus"] != "PASS" and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
