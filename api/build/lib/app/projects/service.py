from dataclasses import dataclass
from functools import lru_cache

from app.auth.models import SessionPrincipal
from app.core.config import Settings, get_settings
from app.projects.models import AccessTier, ProjectMember, ProjectRole, ProjectSummary
from app.projects.store import (
    ProjectNotFoundError,
    ProjectStore,
)


class ProjectAccessDeniedError(RuntimeError):
    """Current session cannot access this project surface."""


class ProjectValidationError(RuntimeError):
    """Payload validation failed before persistence."""


class ProjectUserNotFoundError(RuntimeError):
    """User could not be resolved by email."""


@dataclass(frozen=True)
class ProjectWorkspaceContext:
    summary: ProjectSummary
    is_member: bool
    can_access_settings: bool
    can_manage_members: bool


class ProjectService:
    def __init__(
        self,
        *,
        settings: Settings,
        store: ProjectStore | None = None,
    ) -> None:
        self._settings = settings
        self._store = store or ProjectStore(settings)

    @staticmethod
    def _is_admin_override(current_user: SessionPrincipal) -> bool:
        return "ADMIN" in set(current_user.platform_roles)

    @staticmethod
    def _validate_name(value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ProjectValidationError("Project name must be at least 2 characters.")
        if len(normalized) > 180:
            raise ProjectValidationError("Project name must be 180 characters or fewer.")
        return normalized

    @staticmethod
    def _validate_purpose(value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 12:
            raise ProjectValidationError("Project purpose must be at least 12 characters.")
        if len(normalized) > 3000:
            raise ProjectValidationError("Project purpose must be 3000 characters or fewer.")
        return normalized

    def list_my_projects(self, *, current_user: SessionPrincipal) -> list[ProjectSummary]:
        return self._store.list_projects_for_user(user_id=current_user.user_id)

    def create_project(
        self,
        *,
        current_user: SessionPrincipal,
        name: str,
        purpose: str,
        intended_access_tier: AccessTier,
    ) -> ProjectSummary:
        normalized_name = self._validate_name(name)
        normalized_purpose = self._validate_purpose(purpose)
        return self._store.create_project(
            name=normalized_name,
            purpose=normalized_purpose,
            intended_access_tier=intended_access_tier,
            created_by_user_id=current_user.user_id,
        )

    def require_member_workspace(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> ProjectWorkspaceContext:
        summary = self._store.get_project_summary_for_user(
            project_id=project_id,
            user_id=current_user.user_id,
        )
        if summary is None:
            raise ProjectAccessDeniedError("Membership is required for this project route.")

        is_admin = self._is_admin_override(current_user)
        can_access_settings = is_admin or summary.current_user_role == "PROJECT_LEAD"
        return ProjectWorkspaceContext(
            summary=summary,
            is_member=True,
            can_access_settings=can_access_settings,
            can_manage_members=can_access_settings,
        )

    def resolve_workspace_context(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> ProjectWorkspaceContext:
        member_summary = self._store.get_project_summary_for_user(
            project_id=project_id,
            user_id=current_user.user_id,
        )
        if member_summary is not None:
            is_admin = self._is_admin_override(current_user)
            can_access_settings = is_admin or member_summary.current_user_role == "PROJECT_LEAD"
            return ProjectWorkspaceContext(
                summary=member_summary,
                is_member=True,
                can_access_settings=can_access_settings,
                can_manage_members=can_access_settings,
            )

        if not self._is_admin_override(current_user):
            raise ProjectAccessDeniedError(
                "Membership is required unless the route declares an admin override."
            )

        project = self._store.get_project_summary(project_id=project_id)
        if project is None:
            raise ProjectNotFoundError("Project not found.")

        return ProjectWorkspaceContext(
            summary=project,
            is_member=False,
            can_access_settings=True,
            can_manage_members=True,
        )

    def require_settings_access(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> ProjectWorkspaceContext:
        context = self.resolve_workspace_context(
            current_user=current_user,
            project_id=project_id,
        )
        if not context.can_access_settings:
            raise ProjectAccessDeniedError("Project settings require elevated access.")
        return context

    def list_project_members(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> tuple[ProjectWorkspaceContext, list[ProjectMember]]:
        context = self.require_settings_access(
            current_user=current_user,
            project_id=project_id,
        )
        members = self._store.list_project_members(project_id=project_id)
        return context, members

    def get_project_member_for_settings(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        member_user_id: str,
    ) -> ProjectMember | None:
        context = self.require_settings_access(
            current_user=current_user,
            project_id=project_id,
        )
        if not context.can_manage_members:
            raise ProjectAccessDeniedError("Current session cannot manage project members.")
        return self._store.get_project_member(project_id=project_id, user_id=member_user_id)

    def add_project_member(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        member_email: str,
        role: ProjectRole,
    ) -> ProjectMember:
        context = self.require_settings_access(
            current_user=current_user,
            project_id=project_id,
        )
        if not context.can_manage_members:
            raise ProjectAccessDeniedError("Current session cannot manage project members.")

        target_user = self._store.lookup_user_by_email(email=member_email)
        if target_user is None:
            raise ProjectUserNotFoundError(
                "User is unknown. Ask them to authenticate once before adding membership."
            )

        return self._store.add_project_member(
            project_id=project_id,
            user_id=target_user.id,
            role=role,
        )

    def change_project_member_role(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        member_user_id: str,
        role: ProjectRole,
    ) -> ProjectMember:
        context = self.require_settings_access(
            current_user=current_user,
            project_id=project_id,
        )
        if not context.can_manage_members:
            raise ProjectAccessDeniedError("Current session cannot manage project members.")

        return self._store.change_project_member_role(
            project_id=project_id,
            user_id=member_user_id,
            role=role,
        )

    def remove_project_member(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        member_user_id: str,
    ) -> ProjectRole:
        context = self.require_settings_access(
            current_user=current_user,
            project_id=project_id,
        )
        if not context.can_manage_members:
            raise ProjectAccessDeniedError("Current session cannot manage project members.")

        return self._store.remove_project_member(
            project_id=project_id,
            user_id=member_user_id,
        )


@lru_cache
def get_project_service() -> ProjectService:
    settings = get_settings()
    return ProjectService(settings=settings)
