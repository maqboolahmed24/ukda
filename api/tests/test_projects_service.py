from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

import pytest
from app.auth.models import SessionPrincipal, UserRecord
from app.core.config import get_settings
from app.projects.models import ProjectMember, ProjectSummary
from app.projects.service import (
    ProjectAccessDeniedError,
    ProjectService,
    ProjectUserNotFoundError,
)
from app.projects.store import LastProjectLeadConstraintError


def _principal(
    *,
    user_id: str,
    email: str,
    platform_roles: tuple[Literal["ADMIN", "AUDITOR"], ...] = (),
) -> SessionPrincipal:
    return SessionPrincipal(
        session_id=f"session-{user_id}",
        auth_source="bearer",
        user_id=user_id,
        oidc_sub=f"oidc-{user_id}",
        email=email,
        display_name=email.split("@")[0],
        platform_roles=platform_roles,
        issued_at=datetime.now(UTC) - timedelta(minutes=2),
        expires_at=datetime.now(UTC) + timedelta(minutes=58),
        csrf_token="csrf-token",
    )


class InMemoryProjectStore:
    def __init__(self) -> None:
        self.baseline_id = "baseline-phase0-v1"
        self._projects: dict[str, ProjectSummary] = {}
        self._memberships: dict[
            str, dict[str, Literal["PROJECT_LEAD", "RESEARCHER", "REVIEWER"]]
        ] = {}
        self._users: dict[str, UserRecord] = {}
        self._sequence = 0
        self._seed_users()

    def _seed_users(self) -> None:
        now = datetime.now(UTC)
        seed_users = [
            ("user-lead", "project-lead@local.ukde"),
            ("user-researcher", "researcher@local.ukde"),
            ("user-reviewer", "reviewer@local.ukde"),
            ("user-admin", "admin@local.ukde"),
        ]
        for user_id, email in seed_users:
            self._users[email.lower()] = UserRecord(
                id=user_id,
                oidc_sub=f"oidc-{user_id}",
                email=email,
                display_name=email.split("@")[0],
                last_login_at=now,
                platform_roles=(),
            )

    def list_projects_for_user(self, *, user_id: str) -> list[ProjectSummary]:
        rows: list[ProjectSummary] = []
        for project in self._projects.values():
            role = self._memberships.get(project.id, {}).get(user_id)
            if role is None:
                continue
            rows.append(
                ProjectSummary(
                    **{
                        **project.__dict__,
                        "current_user_role": role,
                    }
                )
            )
        return rows

    def create_project(
        self,
        *,
        name: str,
        purpose: str,
        intended_access_tier: Literal["OPEN", "SAFEGUARDED", "CONTROLLED"],
        created_by_user_id: str,
    ) -> ProjectSummary:
        self._sequence += 1
        project_id = f"project-{self._sequence}"
        now = datetime.now(UTC)
        summary = ProjectSummary(
            id=project_id,
            name=name,
            purpose=purpose,
            status="ACTIVE",
            created_by=created_by_user_id,
            created_at=now,
            intended_access_tier=intended_access_tier,
            baseline_policy_snapshot_id=self.baseline_id,
            current_user_role="PROJECT_LEAD",
        )
        self._projects[project_id] = ProjectSummary(
            **{
                **summary.__dict__,
                "current_user_role": None,
            }
        )
        self._memberships[project_id] = {created_by_user_id: "PROJECT_LEAD"}
        return summary

    def get_project_summary_for_user(
        self, *, project_id: str, user_id: str
    ) -> ProjectSummary | None:
        project = self._projects.get(project_id)
        if project is None:
            return None
        role = self._memberships.get(project_id, {}).get(user_id)
        if role is None:
            return None
        return ProjectSummary(
            **{
                **project.__dict__,
                "current_user_role": role,
            }
        )

    def get_project_summary(self, *, project_id: str) -> ProjectSummary | None:
        return self._projects.get(project_id)

    def lookup_user_by_email(self, *, email: str) -> UserRecord | None:
        return self._users.get(email.strip().lower())

    def list_project_members(self, *, project_id: str) -> list[ProjectMember]:
        now = datetime.now(UTC)
        members: list[ProjectMember] = []
        for user_id, role in self._memberships.get(project_id, {}).items():
            user = next(user for user in self._users.values() if user.id == user_id)
            members.append(
                ProjectMember(
                    project_id=project_id,
                    user_id=user_id,
                    email=user.email,
                    display_name=user.display_name,
                    role=role,
                    created_at=now,
                    updated_at=now,
                )
            )
        return members

    def add_project_member(
        self,
        *,
        project_id: str,
        user_id: str,
        role: Literal["PROJECT_LEAD", "RESEARCHER", "REVIEWER"],
    ) -> ProjectMember:
        members = self._memberships.setdefault(project_id, {})
        if user_id in members:
            raise RuntimeError("duplicate")
        members[user_id] = role
        user = next(user for user in self._users.values() if user.id == user_id)
        now = datetime.now(UTC)
        return ProjectMember(
            project_id=project_id,
            user_id=user_id,
            email=user.email,
            display_name=user.display_name,
            role=role,
            created_at=now,
            updated_at=now,
        )

    def change_project_member_role(
        self,
        *,
        project_id: str,
        user_id: str,
        role: Literal["PROJECT_LEAD", "RESEARCHER", "REVIEWER"],
    ) -> ProjectMember:
        members = self._memberships.get(project_id, {})
        existing = members.get(user_id)
        if existing is None:
            raise RuntimeError("not-found")
        if existing == "PROJECT_LEAD" and role != "PROJECT_LEAD":
            lead_count = sum(
                1 for existing_role in members.values() if existing_role == "PROJECT_LEAD"
            )
            if lead_count <= 1:
                raise LastProjectLeadConstraintError(
                    "Project must retain at least one PROJECT_LEAD."
                )
        members[user_id] = role
        user = next(user for user in self._users.values() if user.id == user_id)
        now = datetime.now(UTC)
        return ProjectMember(
            project_id=project_id,
            user_id=user_id,
            email=user.email,
            display_name=user.display_name,
            role=role,
            created_at=now,
            updated_at=now,
        )

    def remove_project_member(self, *, project_id: str, user_id: str) -> None:
        members = self._memberships.get(project_id, {})
        existing = members.get(user_id)
        if existing is None:
            raise RuntimeError("not-found")
        if existing == "PROJECT_LEAD":
            lead_count = sum(1 for role in members.values() if role == "PROJECT_LEAD")
            if lead_count <= 1:
                raise LastProjectLeadConstraintError(
                    "Project must retain at least one PROJECT_LEAD."
                )
        del members[user_id]


def _service(store: InMemoryProjectStore) -> ProjectService:
    return ProjectService(settings=get_settings(), store=store)  # type: ignore[arg-type]


def test_create_project_attaches_baseline_and_creator_membership() -> None:
    store = InMemoryProjectStore()
    service = _service(store)
    creator = _principal(user_id="user-lead", email="project-lead@local.ukde")

    project = service.create_project(
        current_user=creator,
        name="Northern Diaries",
        purpose="Transcribe and review historical regional diary pages.",
        intended_access_tier="CONTROLLED",
    )

    assert project.baseline_policy_snapshot_id == store.baseline_id
    assert project.current_user_role == "PROJECT_LEAD"
    assert store._memberships[project.id][creator.user_id] == "PROJECT_LEAD"


def test_non_member_cannot_access_member_scoped_workspace_routes() -> None:
    store = InMemoryProjectStore()
    service = _service(store)
    creator = _principal(user_id="user-lead", email="project-lead@local.ukde")
    outsider = _principal(user_id="user-reviewer", email="reviewer@local.ukde")
    project = service.create_project(
        current_user=creator,
        name="Parish Records",
        purpose="Transcribe parish records and resolve uncertain handwriting safely.",
        intended_access_tier="SAFEGUARDED",
    )

    with pytest.raises(ProjectAccessDeniedError):
        service.require_member_workspace(
            current_user=outsider,
            project_id=project.id,
        )


def test_admin_override_is_explicit_and_limited() -> None:
    store = InMemoryProjectStore()
    service = _service(store)
    creator = _principal(user_id="user-lead", email="project-lead@local.ukde")
    admin = _principal(
        user_id="user-admin",
        email="admin@local.ukde",
        platform_roles=("ADMIN",),
    )
    project = service.create_project(
        current_user=creator,
        name="Local Census",
        purpose="Review and transcribe local census pages with governance checks.",
        intended_access_tier="CONTROLLED",
    )

    context = service.resolve_workspace_context(
        current_user=admin,
        project_id=project.id,
    )
    assert context.is_member is False
    assert context.can_access_settings is True

    with pytest.raises(ProjectAccessDeniedError):
        service.require_member_workspace(
            current_user=admin,
            project_id=project.id,
        )


def test_auditor_has_no_implicit_project_workspace_access() -> None:
    store = InMemoryProjectStore()
    service = _service(store)
    lead = _principal(user_id="user-lead", email="project-lead@local.ukde")
    auditor = _principal(
        user_id="user-reviewer",
        email="reviewer@local.ukde",
        platform_roles=("AUDITOR",),
    )
    project = service.create_project(
        current_user=lead,
        name="Tax Rolls",
        purpose="Review tax-roll transcripts with explicit governance boundaries.",
        intended_access_tier="SAFEGUARDED",
    )

    with pytest.raises(ProjectAccessDeniedError):
        service.resolve_workspace_context(
            current_user=auditor,
            project_id=project.id,
        )


def test_researcher_cannot_manage_members() -> None:
    store = InMemoryProjectStore()
    service = _service(store)
    lead = _principal(user_id="user-lead", email="project-lead@local.ukde")
    researcher = _principal(user_id="user-researcher", email="researcher@local.ukde")
    project = service.create_project(
        current_user=lead,
        name="Shipping Logs",
        purpose="Transcribe shipping logs and prepare reviewed text outputs.",
        intended_access_tier="CONTROLLED",
    )
    store._memberships[project.id][researcher.user_id] = "RESEARCHER"

    with pytest.raises(ProjectAccessDeniedError):
        service.add_project_member(
            current_user=researcher,
            project_id=project.id,
            member_email="reviewer@local.ukde",
            role="REVIEWER",
        )


def test_project_lead_can_add_change_and_remove_members() -> None:
    store = InMemoryProjectStore()
    service = _service(store)
    lead = _principal(user_id="user-lead", email="project-lead@local.ukde")
    project = service.create_project(
        current_user=lead,
        name="Court Notes",
        purpose="Transcribe and quality-check handwritten court-note pages.",
        intended_access_tier="SAFEGUARDED",
    )

    added = service.add_project_member(
        current_user=lead,
        project_id=project.id,
        member_email="reviewer@local.ukde",
        role="REVIEWER",
    )
    assert added.role == "REVIEWER"

    updated = service.change_project_member_role(
        current_user=lead,
        project_id=project.id,
        member_user_id=added.user_id,
        role="RESEARCHER",
    )
    assert updated.role == "RESEARCHER"

    service.remove_project_member(
        current_user=lead,
        project_id=project.id,
        member_user_id=added.user_id,
    )
    assert added.user_id not in store._memberships[project.id]


def test_add_member_requires_known_user_identity() -> None:
    store = InMemoryProjectStore()
    service = _service(store)
    lead = _principal(user_id="user-lead", email="project-lead@local.ukde")
    project = service.create_project(
        current_user=lead,
        name="Estate Rolls",
        purpose="Transcribe estate-roll pages with confidence-linked review.",
        intended_access_tier="CONTROLLED",
    )

    with pytest.raises(ProjectUserNotFoundError):
        service.add_project_member(
            current_user=lead,
            project_id=project.id,
            member_email="unknown@local.ukde",
            role="RESEARCHER",
        )
