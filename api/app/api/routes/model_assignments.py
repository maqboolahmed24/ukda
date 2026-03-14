from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.audit.dependencies import get_audit_request_context
from app.audit.models import AuditRequestContext
from app.audit.service import AuditService, get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.documents.models import (
    ApprovedModelRecord,
    ProjectModelAssignmentRecord,
    TrainingDatasetRecord,
)
from app.documents.service import (
    DocumentModelAssignmentAccessDeniedError,
    DocumentModelAssignmentConflictError,
    DocumentModelAssignmentNotFoundError,
    DocumentModelCatalogAccessDeniedError,
    DocumentModelCatalogConflictError,
    DocumentService,
    DocumentStoreUnavailableError,
    DocumentValidationError,
    get_document_service,
)
from app.projects.service import ProjectAccessDeniedError
from app.projects.store import ProjectNotFoundError

router = APIRouter(dependencies=[Depends(require_authenticated_user)])

ApprovedModelTypeLiteral = Literal["VLM", "LLM", "HTR"]
ApprovedModelRoleLiteral = Literal[
    "TRANSCRIPTION_PRIMARY",
    "TRANSCRIPTION_FALLBACK",
    "ASSIST",
]
ApprovedModelServingInterfaceLiteral = Literal[
    "OPENAI_CHAT",
    "OPENAI_EMBEDDING",
    "ENGINE_NATIVE",
    "RULES_NATIVE",
]
ApprovedModelStatusLiteral = Literal["APPROVED", "DEPRECATED", "ROLLED_BACK"]
ProjectModelAssignmentStatusLiteral = Literal["DRAFT", "ACTIVE", "RETIRED"]
TrainingDatasetKindLiteral = Literal["TRANSCRIPTION_TRAINING"]


class ApprovedModelResponse(BaseModel):
    id: str
    model_type: ApprovedModelTypeLiteral = Field(serialization_alias="modelType")
    model_role: ApprovedModelRoleLiteral = Field(serialization_alias="modelRole")
    model_family: str = Field(serialization_alias="modelFamily")
    model_version: str = Field(serialization_alias="modelVersion")
    serving_interface: ApprovedModelServingInterfaceLiteral = Field(
        serialization_alias="servingInterface"
    )
    engine_family: str = Field(serialization_alias="engineFamily")
    deployment_unit: str = Field(serialization_alias="deploymentUnit")
    artifact_subpath: str = Field(serialization_alias="artifactSubpath")
    checksum_sha256: str = Field(serialization_alias="checksumSha256")
    runtime_profile: str = Field(serialization_alias="runtimeProfile")
    response_contract_version: str = Field(serialization_alias="responseContractVersion")
    metadata_json: dict[str, object] = Field(serialization_alias="metadataJson")
    status: ApprovedModelStatusLiteral
    approved_by: str | None = Field(default=None, serialization_alias="approvedBy")
    approved_at: datetime | None = Field(default=None, serialization_alias="approvedAt")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class ApprovedModelListResponse(BaseModel):
    items: list[ApprovedModelResponse]


class CreateApprovedModelRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    model_type: ApprovedModelTypeLiteral = Field(
        alias="modelType",
        serialization_alias="modelType",
    )
    model_role: ApprovedModelRoleLiteral = Field(
        alias="modelRole",
        serialization_alias="modelRole",
    )
    model_family: str = Field(
        alias="modelFamily",
        serialization_alias="modelFamily",
        min_length=1,
        max_length=120,
    )
    model_version: str = Field(
        alias="modelVersion",
        serialization_alias="modelVersion",
        min_length=1,
        max_length=120,
    )
    serving_interface: ApprovedModelServingInterfaceLiteral = Field(
        alias="servingInterface",
        serialization_alias="servingInterface",
    )
    engine_family: str = Field(
        alias="engineFamily",
        serialization_alias="engineFamily",
        min_length=1,
        max_length=120,
    )
    deployment_unit: str = Field(
        alias="deploymentUnit",
        serialization_alias="deploymentUnit",
        min_length=1,
        max_length=160,
    )
    artifact_subpath: str = Field(
        alias="artifactSubpath",
        serialization_alias="artifactSubpath",
        min_length=1,
        max_length=240,
    )
    checksum_sha256: str = Field(
        alias="checksumSha256",
        serialization_alias="checksumSha256",
        min_length=64,
        max_length=64,
    )
    runtime_profile: str = Field(
        alias="runtimeProfile",
        serialization_alias="runtimeProfile",
        min_length=1,
        max_length=120,
    )
    response_contract_version: str = Field(
        alias="responseContractVersion",
        serialization_alias="responseContractVersion",
        min_length=1,
        max_length=120,
    )
    metadata_json: dict[str, object] | None = Field(
        default=None,
        alias="metadataJson",
        serialization_alias="metadataJson",
    )


class ProjectModelAssignmentResponse(BaseModel):
    id: str
    project_id: str = Field(serialization_alias="projectId")
    model_role: ApprovedModelRoleLiteral = Field(serialization_alias="modelRole")
    approved_model_id: str = Field(serialization_alias="approvedModelId")
    status: ProjectModelAssignmentStatusLiteral
    assignment_reason: str = Field(serialization_alias="assignmentReason")
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    activated_by: str | None = Field(default=None, serialization_alias="activatedBy")
    activated_at: datetime | None = Field(default=None, serialization_alias="activatedAt")
    retired_by: str | None = Field(default=None, serialization_alias="retiredBy")
    retired_at: datetime | None = Field(default=None, serialization_alias="retiredAt")


class ProjectModelAssignmentListResponse(BaseModel):
    items: list[ProjectModelAssignmentResponse]


class CreateProjectModelAssignmentRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    model_role: ApprovedModelRoleLiteral = Field(
        alias="modelRole",
        serialization_alias="modelRole",
    )
    approved_model_id: str = Field(
        alias="approvedModelId",
        serialization_alias="approvedModelId",
        min_length=1,
        max_length=160,
    )
    assignment_reason: str = Field(
        alias="assignmentReason",
        serialization_alias="assignmentReason",
        min_length=1,
        max_length=800,
    )


class TrainingDatasetResponse(BaseModel):
    id: str
    project_id: str = Field(serialization_alias="projectId")
    source_approved_model_id: str | None = Field(
        default=None,
        serialization_alias="sourceApprovedModelId",
    )
    project_model_assignment_id: str | None = Field(
        default=None,
        serialization_alias="projectModelAssignmentId",
    )
    dataset_kind: TrainingDatasetKindLiteral = Field(serialization_alias="datasetKind")
    page_count: int = Field(serialization_alias="pageCount")
    storage_key: str = Field(serialization_alias="storageKey")
    dataset_sha256: str = Field(serialization_alias="datasetSha256")
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")


class TrainingDatasetListResponse(BaseModel):
    items: list[TrainingDatasetResponse]


def _as_approved_model_response(record: ApprovedModelRecord) -> ApprovedModelResponse:
    return ApprovedModelResponse(
        id=record.id,
        model_type=record.model_type,
        model_role=record.model_role,
        model_family=record.model_family,
        model_version=record.model_version,
        serving_interface=record.serving_interface,
        engine_family=record.engine_family,
        deployment_unit=record.deployment_unit,
        artifact_subpath=record.artifact_subpath,
        checksum_sha256=record.checksum_sha256,
        runtime_profile=record.runtime_profile,
        response_contract_version=record.response_contract_version,
        metadata_json=record.metadata_json,
        status=record.status,
        approved_by=record.approved_by,
        approved_at=record.approved_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _as_project_model_assignment_response(
    record: ProjectModelAssignmentRecord,
) -> ProjectModelAssignmentResponse:
    return ProjectModelAssignmentResponse(
        id=record.id,
        project_id=record.project_id,
        model_role=record.model_role,
        approved_model_id=record.approved_model_id,
        status=record.status,
        assignment_reason=record.assignment_reason,
        created_by=record.created_by,
        created_at=record.created_at,
        activated_by=record.activated_by,
        activated_at=record.activated_at,
        retired_by=record.retired_by,
        retired_at=record.retired_at,
    )


def _as_training_dataset_response(record: TrainingDatasetRecord) -> TrainingDatasetResponse:
    return TrainingDatasetResponse(
        id=record.id,
        project_id=record.project_id,
        source_approved_model_id=record.source_approved_model_id,
        project_model_assignment_id=record.project_model_assignment_id,
        dataset_kind=record.dataset_kind,
        page_count=record.page_count,
        storage_key=record.storage_key,
        dataset_sha256=record.dataset_sha256,
        created_by=record.created_by,
        created_at=record.created_at,
    )


def _record_audit_event(
    *,
    audit_service: AuditService,
    request_context: AuditRequestContext,
    event_type: str,
    actor_user_id: str,
    project_id: str | None = None,
    object_type: str | None = None,
    object_id: str | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    audit_service.record_event_best_effort(
        event_type=event_type,
        actor_user_id=actor_user_id,
        project_id=project_id,
        object_type=object_type,
        object_id=object_id,
        metadata=metadata,
        request_context=request_context,
    )


@router.get("/approved-models", response_model=ApprovedModelListResponse)
def list_approved_models(
    model_role: str | None = Query(default=None, alias="modelRole"),
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> ApprovedModelListResponse:
    try:
        rows = document_service.list_approved_models(
            current_user=current_user,
            model_role=model_role,
            status=status_filter,
        )
    except DocumentModelCatalogAccessDeniedError as error:
        _record_audit_event(
            audit_service=audit_service,
            request_context=request_context,
            event_type="ACCESS_DENIED",
            actor_user_id=current_user.user_id,
            metadata={
                "route": request_context.route_template,
                "required_roles": ["PROJECT_LEAD", "REVIEWER", "ADMIN"],
                "status_code": status.HTTP_403_FORBIDDEN,
            },
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except DocumentValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except DocumentStoreUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Approved-model catalog is unavailable.",
        ) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="APPROVED_MODEL_LIST_VIEWED",
        actor_user_id=current_user.user_id,
        metadata={
            "route": request_context.route_template,
            "model_role": model_role or "",
            "status": status_filter or "",
            "returned_count": len(rows),
        },
    )
    return ApprovedModelListResponse(
        items=[_as_approved_model_response(row) for row in rows]
    )


@router.post(
    "/approved-models",
    response_model=ApprovedModelResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_approved_model(
    payload: CreateApprovedModelRequest,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> ApprovedModelResponse:
    try:
        row = document_service.create_approved_model(
            current_user=current_user,
            model_type=payload.model_type,
            model_role=payload.model_role,
            model_family=payload.model_family,
            model_version=payload.model_version,
            serving_interface=payload.serving_interface,
            engine_family=payload.engine_family,
            deployment_unit=payload.deployment_unit,
            artifact_subpath=payload.artifact_subpath,
            checksum_sha256=payload.checksum_sha256,
            runtime_profile=payload.runtime_profile,
            response_contract_version=payload.response_contract_version,
            metadata_json=payload.metadata_json,
        )
    except DocumentModelCatalogAccessDeniedError as error:
        _record_audit_event(
            audit_service=audit_service,
            request_context=request_context,
            event_type="ACCESS_DENIED",
            actor_user_id=current_user.user_id,
            metadata={
                "route": request_context.route_template,
                "required_roles": ["PROJECT_LEAD", "ADMIN"],
                "status_code": status.HTTP_403_FORBIDDEN,
            },
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except DocumentValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except DocumentModelCatalogConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except DocumentStoreUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Approved-model catalog is unavailable.",
        ) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="APPROVED_MODEL_CREATED",
        actor_user_id=current_user.user_id,
        object_type="approved_model",
        object_id=row.id,
        metadata={
            "route": request_context.route_template,
            "approved_model_id": row.id,
            "model_type": row.model_type,
            "model_role": row.model_role,
            "model_family": row.model_family,
            "model_version": row.model_version,
        },
    )
    return _as_approved_model_response(row)


@router.get(
    "/projects/{project_id}/model-assignments",
    response_model=ProjectModelAssignmentListResponse,
)
def list_project_model_assignments(
    project_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> ProjectModelAssignmentListResponse:
    try:
        rows = document_service.list_project_model_assignments(
            current_user=current_user,
            project_id=project_id,
        )
    except (ProjectNotFoundError, DocumentModelAssignmentNotFoundError) as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (ProjectAccessDeniedError, DocumentModelAssignmentAccessDeniedError) as error:
        _record_audit_event(
            audit_service=audit_service,
            request_context=request_context,
            event_type="ACCESS_DENIED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            metadata={
                "route": request_context.route_template,
                "required_roles": ["PROJECT_LEAD", "REVIEWER", "ADMIN"],
                "status_code": status.HTTP_403_FORBIDDEN,
            },
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except DocumentValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except DocumentStoreUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Project model assignments are unavailable.",
        ) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="MODEL_ASSIGNMENT_LIST_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        metadata={
            "route": request_context.route_template,
            "returned_count": len(rows),
        },
    )
    return ProjectModelAssignmentListResponse(
        items=[_as_project_model_assignment_response(row) for row in rows]
    )


@router.post(
    "/projects/{project_id}/model-assignments",
    response_model=ProjectModelAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_model_assignment(
    project_id: str,
    payload: CreateProjectModelAssignmentRequest,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> ProjectModelAssignmentResponse:
    try:
        row = document_service.create_project_model_assignment(
            current_user=current_user,
            project_id=project_id,
            model_role=payload.model_role,
            approved_model_id=payload.approved_model_id,
            assignment_reason=payload.assignment_reason,
        )
    except ProjectNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (ProjectAccessDeniedError, DocumentModelAssignmentAccessDeniedError) as error:
        _record_audit_event(
            audit_service=audit_service,
            request_context=request_context,
            event_type="ACCESS_DENIED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            metadata={
                "route": request_context.route_template,
                "required_roles": ["PROJECT_LEAD", "ADMIN"],
                "status_code": status.HTTP_403_FORBIDDEN,
            },
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except DocumentValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except DocumentModelAssignmentConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except DocumentStoreUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Project model assignments are unavailable.",
        ) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="PROJECT_MODEL_ASSIGNMENT_CREATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="project_model_assignment",
        object_id=row.id,
        metadata={
            "route": request_context.route_template,
            "assignment_id": row.id,
            "model_role": row.model_role,
            "approved_model_id": row.approved_model_id,
            "status": row.status,
        },
    )
    return _as_project_model_assignment_response(row)


@router.get(
    "/projects/{project_id}/model-assignments/{assignment_id}",
    response_model=ProjectModelAssignmentResponse,
)
def get_project_model_assignment(
    project_id: str,
    assignment_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> ProjectModelAssignmentResponse:
    try:
        row = document_service.get_project_model_assignment(
            current_user=current_user,
            project_id=project_id,
            assignment_id=assignment_id,
        )
    except (ProjectNotFoundError, DocumentModelAssignmentNotFoundError) as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (ProjectAccessDeniedError, DocumentModelAssignmentAccessDeniedError) as error:
        _record_audit_event(
            audit_service=audit_service,
            request_context=request_context,
            event_type="ACCESS_DENIED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            metadata={
                "route": request_context.route_template,
                "required_roles": ["PROJECT_LEAD", "REVIEWER", "ADMIN"],
                "status_code": status.HTTP_403_FORBIDDEN,
            },
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except DocumentValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except DocumentStoreUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Project model assignment read is unavailable.",
        ) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="MODEL_ASSIGNMENT_DETAIL_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="project_model_assignment",
        object_id=row.id,
        metadata={
            "route": request_context.route_template,
            "assignment_id": row.id,
        },
    )
    return _as_project_model_assignment_response(row)


@router.get(
    "/projects/{project_id}/model-assignments/{assignment_id}/datasets",
    response_model=TrainingDatasetListResponse,
)
def list_training_datasets_for_assignment(
    project_id: str,
    assignment_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> TrainingDatasetListResponse:
    try:
        rows = document_service.list_training_datasets_for_assignment(
            current_user=current_user,
            project_id=project_id,
            assignment_id=assignment_id,
        )
    except (ProjectNotFoundError, DocumentModelAssignmentNotFoundError) as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (ProjectAccessDeniedError, DocumentModelAssignmentAccessDeniedError) as error:
        _record_audit_event(
            audit_service=audit_service,
            request_context=request_context,
            event_type="ACCESS_DENIED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            metadata={
                "route": request_context.route_template,
                "required_roles": ["PROJECT_LEAD", "REVIEWER", "ADMIN"],
                "status_code": status.HTTP_403_FORBIDDEN,
            },
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except DocumentValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except DocumentStoreUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Training dataset lineage is unavailable.",
        ) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="TRAINING_DATASET_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="project_model_assignment",
        object_id=assignment_id,
        metadata={
            "route": request_context.route_template,
            "assignment_id": assignment_id,
            "returned_count": len(rows),
        },
    )
    return TrainingDatasetListResponse(
        items=[_as_training_dataset_response(row) for row in rows]
    )


@router.post(
    "/projects/{project_id}/model-assignments/{assignment_id}/activate",
    response_model=ProjectModelAssignmentResponse,
)
def activate_project_model_assignment(
    project_id: str,
    assignment_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> ProjectModelAssignmentResponse:
    try:
        row = document_service.activate_project_model_assignment(
            current_user=current_user,
            project_id=project_id,
            assignment_id=assignment_id,
        )
    except (ProjectNotFoundError, DocumentModelAssignmentNotFoundError) as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (ProjectAccessDeniedError, DocumentModelAssignmentAccessDeniedError) as error:
        _record_audit_event(
            audit_service=audit_service,
            request_context=request_context,
            event_type="ACCESS_DENIED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            metadata={
                "route": request_context.route_template,
                "required_roles": ["PROJECT_LEAD", "ADMIN"],
                "status_code": status.HTTP_403_FORBIDDEN,
            },
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except DocumentValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except DocumentModelAssignmentConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except DocumentStoreUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Project model-assignment activation is unavailable.",
        ) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="PROJECT_MODEL_ACTIVATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="project_model_assignment",
        object_id=row.id,
        metadata={
            "route": request_context.route_template,
            "assignment_id": row.id,
            "model_role": row.model_role,
            "approved_model_id": row.approved_model_id,
            "status": row.status,
        },
    )
    return _as_project_model_assignment_response(row)


@router.post(
    "/projects/{project_id}/model-assignments/{assignment_id}/retire",
    response_model=ProjectModelAssignmentResponse,
)
def retire_project_model_assignment(
    project_id: str,
    assignment_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    document_service: DocumentService = Depends(get_document_service),
) -> ProjectModelAssignmentResponse:
    try:
        row = document_service.retire_project_model_assignment(
            current_user=current_user,
            project_id=project_id,
            assignment_id=assignment_id,
        )
    except (ProjectNotFoundError, DocumentModelAssignmentNotFoundError) as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (ProjectAccessDeniedError, DocumentModelAssignmentAccessDeniedError) as error:
        _record_audit_event(
            audit_service=audit_service,
            request_context=request_context,
            event_type="ACCESS_DENIED",
            actor_user_id=current_user.user_id,
            project_id=project_id,
            metadata={
                "route": request_context.route_template,
                "required_roles": ["PROJECT_LEAD", "ADMIN"],
                "status_code": status.HTTP_403_FORBIDDEN,
            },
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except DocumentValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except DocumentModelAssignmentConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except DocumentStoreUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Project model-assignment retirement is unavailable.",
        ) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="PROJECT_MODEL_RETIRED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="project_model_assignment",
        object_id=row.id,
        metadata={
            "route": request_context.route_template,
            "assignment_id": row.id,
            "model_role": row.model_role,
            "approved_model_id": row.approved_model_id,
            "status": row.status,
        },
    )
    return _as_project_model_assignment_response(row)
