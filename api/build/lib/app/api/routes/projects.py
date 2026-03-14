from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.audit.dependencies import get_audit_request_context
from app.audit.models import AuditEventType, AuditRequestContext
from app.audit.service import AuditService, get_audit_service
from app.audit.store import AuditStoreUnavailableError as AuditUnavailableError
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.projects.models import AccessTier, ProjectMember, ProjectRole, ProjectSummary
from app.projects.service import (
    ProjectAccessDeniedError,
    ProjectService,
    ProjectUserNotFoundError,
    ProjectValidationError,
    get_project_service,
)
from app.projects.store import (
    DuplicateProjectMemberError,
    LastProjectLeadConstraintError,
    ProjectMemberNotFoundError,
    ProjectNotFoundError,
    ProjectStoreUnavailableError,
)

router = APIRouter(prefix="/projects", dependencies=[Depends(require_authenticated_user)])


class ProjectSummaryResponse(BaseModel):
    id: str
    name: str
    purpose: str
    status: Literal["ACTIVE", "ARCHIVED"]
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    intended_access_tier: AccessTier = Field(serialization_alias="intendedAccessTier")
    baseline_policy_snapshot_id: str = Field(serialization_alias="baselinePolicySnapshotId")
    current_user_role: ProjectRole | None = Field(
        default=None,
        serialization_alias="currentUserRole",
    )
    is_member: bool = Field(serialization_alias="isMember")
    can_access_settings: bool = Field(serialization_alias="canAccessSettings")
    can_manage_members: bool = Field(serialization_alias="canManageMembers")


class ProjectListResponse(BaseModel):
    items: list[ProjectSummaryResponse]


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    purpose: str = Field(min_length=12, max_length=3000)
    intended_access_tier: AccessTier = Field(
        default="CONTROLLED",
        serialization_alias="intendedAccessTier",
    )


class ProjectMemberResponse(BaseModel):
    project_id: str = Field(serialization_alias="projectId")
    user_id: str = Field(serialization_alias="userId")
    email: str
    display_name: str = Field(serialization_alias="displayName")
    role: ProjectRole
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class ProjectMembersResponse(BaseModel):
    project: ProjectSummaryResponse
    items: list[ProjectMemberResponse]


class AddProjectMemberRequest(BaseModel):
    member_email: str = Field(min_length=3, max_length=320, serialization_alias="memberEmail")
    role: ProjectRole


class ChangeProjectMemberRoleRequest(BaseModel):
    role: ProjectRole


def _as_project_summary_response(
    summary: ProjectSummary,
    *,
    is_member: bool,
    can_access_settings: bool,
    can_manage_members: bool,
) -> ProjectSummaryResponse:
    return ProjectSummaryResponse(
        id=summary.id,
        name=summary.name,
        purpose=summary.purpose,
        status=summary.status,
        created_by=summary.created_by,
        created_at=summary.created_at,
        intended_access_tier=summary.intended_access_tier,
        baseline_policy_snapshot_id=summary.baseline_policy_snapshot_id,
        current_user_role=summary.current_user_role,
        is_member=is_member,
        can_access_settings=can_access_settings,
        can_manage_members=can_manage_members,
    )


def _as_project_member_response(member: ProjectMember) -> ProjectMemberResponse:
    return ProjectMemberResponse(
        project_id=member.project_id,
        user_id=member.user_id,
        email=member.email,
        display_name=member.display_name,
        role=member.role,
        created_at=member.created_at,
        updated_at=member.updated_at,
    )


def _record_required_audit_event(
    *,
    audit_service: AuditService,
    event_type: AuditEventType,
    actor_user_id: str,
    request_context: AuditRequestContext,
    project_id: str | None = None,
    object_type: str | None = None,
    object_id: str | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    try:
        audit_service.record_event(
            event_type=event_type,
            actor_user_id=actor_user_id,
            project_id=project_id,
            object_type=object_type,
            object_id=object_id,
            metadata=metadata,
            request_context=request_context,
        )
    except AuditUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audit store is unavailable.",
        ) from error


@router.get("", response_model=ProjectListResponse)
def list_my_projects(
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectListResponse:
    try:
        summaries = project_service.list_my_projects(current_user=current_user)
    except ProjectStoreUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Project store is unavailable.",
        ) from error

    is_admin = "ADMIN" in set(current_user.platform_roles)
    return ProjectListResponse(
        items=[
            _as_project_summary_response(
                summary,
                is_member=True,
                can_access_settings=is_admin or summary.current_user_role == "PROJECT_LEAD",
                can_manage_members=is_admin or summary.current_user_role == "PROJECT_LEAD",
            )
            for summary in summaries
        ]
    )


@router.post("", response_model=ProjectSummaryResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: CreateProjectRequest,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectSummaryResponse:
    try:
        summary = project_service.create_project(
            current_user=current_user,
            name=payload.name,
            purpose=payload.purpose,
            intended_access_tier=payload.intended_access_tier,
        )
    except ProjectValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except ProjectStoreUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Project creation failed because the project store is unavailable.",
        ) from error

    _record_required_audit_event(
        audit_service=audit_service,
        event_type="PROJECT_CREATED",
        actor_user_id=current_user.user_id,
        project_id=summary.id,
        object_type="project",
        object_id=summary.id,
        metadata={
            "project_name": summary.name,
            "intended_access_tier": summary.intended_access_tier,
            "baseline_policy_snapshot_id": summary.baseline_policy_snapshot_id,
        },
        request_context=request_context,
    )
    _record_required_audit_event(
        audit_service=audit_service,
        event_type="PROJECT_BASELINE_POLICY_ATTACHED",
        actor_user_id=current_user.user_id,
        project_id=summary.id,
        object_type="baseline_policy_snapshot",
        object_id=summary.baseline_policy_snapshot_id,
        metadata={
            "project_id": summary.id,
            "baseline_policy_snapshot_id": summary.baseline_policy_snapshot_id,
        },
        request_context=request_context,
    )

    return _as_project_summary_response(
        summary,
        is_member=True,
        can_access_settings=True,
        can_manage_members=True,
    )


@router.get("/{project_id}", response_model=ProjectSummaryResponse)
def get_project_summary(
    project_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectSummaryResponse:
    try:
        context = project_service.require_member_workspace(
            current_user=current_user,
            project_id=project_id,
        )
    except ProjectAccessDeniedError as error:
        audit_service.record_event_best_effort(
            event_type="ACCESS_DENIED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            metadata={
                "route": request_context.route_template,
                "required_roles": ["PROJECT_MEMBER"],
                "status_code": status.HTTP_403_FORBIDDEN,
            },
            request_context=request_context,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
    except ProjectStoreUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Project store is unavailable.",
        ) from error

    return _as_project_summary_response(
        context.summary,
        is_member=context.is_member,
        can_access_settings=context.can_access_settings,
        can_manage_members=context.can_manage_members,
    )


@router.get("/{project_id}/workspace", response_model=ProjectSummaryResponse)
def get_project_workspace_context(
    project_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectSummaryResponse:
    try:
        context = project_service.resolve_workspace_context(
            current_user=current_user,
            project_id=project_id,
        )
    except ProjectNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ProjectAccessDeniedError as error:
        audit_service.record_event_best_effort(
            event_type="ACCESS_DENIED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            metadata={
                "route": request_context.route_template,
                "required_roles": ["PROJECT_MEMBER", "ADMIN_OVERRIDE"],
                "status_code": status.HTTP_403_FORBIDDEN,
            },
            request_context=request_context,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
    except ProjectStoreUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Project store is unavailable.",
        ) from error

    return _as_project_summary_response(
        context.summary,
        is_member=context.is_member,
        can_access_settings=context.can_access_settings,
        can_manage_members=context.can_manage_members,
    )


@router.get("/{project_id}/members", response_model=ProjectMembersResponse)
def list_project_members(
    project_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectMembersResponse:
    try:
        context, members = project_service.list_project_members(
            current_user=current_user,
            project_id=project_id,
        )
    except ProjectAccessDeniedError as error:
        audit_service.record_event_best_effort(
            event_type="ACCESS_DENIED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            metadata={
                "route": request_context.route_template,
                "required_roles": ["PROJECT_LEAD", "ADMIN"],
                "status_code": status.HTTP_403_FORBIDDEN,
            },
            request_context=request_context,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
    except ProjectStoreUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Project store is unavailable.",
        ) from error

    return ProjectMembersResponse(
        project=_as_project_summary_response(
            context.summary,
            is_member=context.is_member,
            can_access_settings=context.can_access_settings,
            can_manage_members=context.can_manage_members,
        ),
        items=[_as_project_member_response(member) for member in members],
    )


@router.post(
    "/{project_id}/members",
    response_model=ProjectMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_project_member(
    project_id: str,
    payload: AddProjectMemberRequest,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectMemberResponse:
    try:
        member = project_service.add_project_member(
            current_user=current_user,
            project_id=project_id,
            member_email=payload.member_email,
            role=payload.role,
        )
    except ProjectUserNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ProjectAccessDeniedError as error:
        audit_service.record_event_best_effort(
            event_type="ACCESS_DENIED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            metadata={
                "route": request_context.route_template,
                "required_roles": ["PROJECT_LEAD", "ADMIN"],
                "status_code": status.HTTP_403_FORBIDDEN,
            },
            request_context=request_context,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
    except DuplicateProjectMemberError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except ProjectStoreUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Project member add failed because the project store is unavailable.",
        ) from error

    _record_required_audit_event(
        audit_service=audit_service,
        event_type="PROJECT_MEMBER_ADDED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="project_member",
        object_id=member.user_id,
        metadata={
            "member_user_id": member.user_id,
            "member_role": member.role,
        },
        request_context=request_context,
    )

    return _as_project_member_response(member)


@router.patch("/{project_id}/members/{member_user_id}", response_model=ProjectMemberResponse)
def change_project_member_role(
    project_id: str,
    member_user_id: str,
    payload: ChangeProjectMemberRoleRequest,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectMemberResponse:
    previous_role: ProjectRole | None = None

    try:
        existing_member = project_service.get_project_member_for_settings(
            current_user=current_user,
            project_id=project_id,
            member_user_id=member_user_id,
        )
        previous_role = existing_member.role if existing_member else None
        member = project_service.change_project_member_role(
            current_user=current_user,
            project_id=project_id,
            member_user_id=member_user_id,
            role=payload.role,
        )
    except ProjectAccessDeniedError as error:
        audit_service.record_event_best_effort(
            event_type="ACCESS_DENIED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            metadata={
                "route": request_context.route_template,
                "required_roles": ["PROJECT_LEAD", "ADMIN"],
                "status_code": status.HTTP_403_FORBIDDEN,
            },
            request_context=request_context,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
    except ProjectMemberNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except LastProjectLeadConstraintError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except ProjectStoreUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Project member update failed because the project store is unavailable.",
        ) from error

    _record_required_audit_event(
        audit_service=audit_service,
        event_type="PROJECT_MEMBER_ROLE_CHANGED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="project_member",
        object_id=member.user_id,
        metadata={
            "member_user_id": member.user_id,
            "previous_role": previous_role,
            "new_role": member.role,
        },
        request_context=request_context,
    )

    return _as_project_member_response(member)


@router.delete(
    "/{project_id}/members/{member_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_project_member(
    project_id: str,
    member_user_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    project_service: ProjectService = Depends(get_project_service),
) -> None:
    member_role: ProjectRole | None = None

    try:
        existing_member = project_service.get_project_member_for_settings(
            current_user=current_user,
            project_id=project_id,
            member_user_id=member_user_id,
        )
        member_role = existing_member.role if existing_member else None
        removed_role = project_service.remove_project_member(
            current_user=current_user,
            project_id=project_id,
            member_user_id=member_user_id,
        )
        member_role = removed_role
    except ProjectAccessDeniedError as error:
        audit_service.record_event_best_effort(
            event_type="ACCESS_DENIED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            metadata={
                "route": request_context.route_template,
                "required_roles": ["PROJECT_LEAD", "ADMIN"],
                "status_code": status.HTTP_403_FORBIDDEN,
            },
            request_context=request_context,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
    except ProjectMemberNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except LastProjectLeadConstraintError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except ProjectStoreUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Project member removal failed because the project store is unavailable.",
        ) from error

    _record_required_audit_event(
        audit_service=audit_service,
        event_type="PROJECT_MEMBER_REMOVED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="project_member",
        object_id=member_user_id,
        metadata={
            "member_user_id": member_user_id,
            "member_role": member_role,
        },
        request_context=request_context,
    )
