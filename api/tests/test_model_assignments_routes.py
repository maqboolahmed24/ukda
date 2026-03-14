from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.audit.service import get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.documents.models import (
    ApprovedModelRecord,
    ProjectModelAssignmentRecord,
    TrainingDatasetRecord,
)
from app.documents.service import (
    DocumentModelAssignmentAccessDeniedError,
    DocumentModelAssignmentNotFoundError,
    DocumentModelCatalogAccessDeniedError,
    get_document_service,
)
from app.main import app
from app.projects.store import ProjectNotFoundError

client = TestClient(app)


class SpyAuditService:
    def __init__(self) -> None:
        self.recorded: list[dict[str, object]] = []

    def record_event_best_effort(self, **kwargs):  # type: ignore[no-untyped-def]
        self.recorded.append(kwargs)
        return None


class FakeDocumentService:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.approved_models: list[ApprovedModelRecord] = [
            ApprovedModelRecord(
                id="model-transcription-primary-qwen2.5-vl-3b-instruct",
                model_type="VLM",
                model_role="TRANSCRIPTION_PRIMARY",
                model_family="Qwen2.5-VL",
                model_version="3B-Instruct",
                serving_interface="OPENAI_CHAT",
                engine_family="QWEN_VL",
                deployment_unit="internal-vlm",
                artifact_subpath="internal-vlm/qwen2.5-vl-3b-instruct",
                checksum_sha256="0" * 64,
                runtime_profile="default",
                response_contract_version="v1",
                metadata_json={"phase": "4.0"},
                status="APPROVED",
                approved_by=None,
                approved_at=None,
                created_at=now - timedelta(days=10),
                updated_at=now - timedelta(days=1),
            ),
            ApprovedModelRecord(
                id="model-transcription-fallback-kraken",
                model_type="HTR",
                model_role="TRANSCRIPTION_FALLBACK",
                model_family="Kraken",
                model_version="baseline",
                serving_interface="ENGINE_NATIVE",
                engine_family="KRAKEN",
                deployment_unit="kraken",
                artifact_subpath="kraken/default",
                checksum_sha256="2" * 64,
                runtime_profile="fallback-default",
                response_contract_version="v1",
                metadata_json={"phase": "4.4"},
                status="APPROVED",
                approved_by=None,
                approved_at=None,
                created_at=now - timedelta(days=8),
                updated_at=now - timedelta(days=1),
            ),
        ]
        self.assignments: dict[str, ProjectModelAssignmentRecord] = {
            "assignment-1": ProjectModelAssignmentRecord(
                id="assignment-1",
                project_id="project-1",
                model_role="TRANSCRIPTION_PRIMARY",
                approved_model_id="model-transcription-primary-qwen2.5-vl-3b-instruct",
                status="ACTIVE",
                assignment_reason="Initial assignment",
                created_by="user-lead",
                created_at=now - timedelta(days=7),
                activated_by="user-lead",
                activated_at=now - timedelta(days=7),
                retired_by=None,
                retired_at=None,
            )
        }
        self.datasets: list[TrainingDatasetRecord] = [
            TrainingDatasetRecord(
                id="dataset-1",
                project_id="project-1",
                source_approved_model_id="model-transcription-primary-qwen2.5-vl-3b-instruct",
                project_model_assignment_id="assignment-1",
                dataset_kind="TRANSCRIPTION_TRAINING",
                page_count=128,
                storage_key="controlled/derived/project-1/training/dataset-1.jsonl",
                dataset_sha256="a" * 64,
                created_by="user-reviewer",
                created_at=now - timedelta(days=2),
            )
        ]

    @staticmethod
    def _role_for_user(current_user: SessionPrincipal) -> str:
        if "ADMIN" in set(current_user.platform_roles):
            return "ADMIN"
        if current_user.user_id == "user-lead":
            return "PROJECT_LEAD"
        if current_user.user_id == "user-reviewer":
            return "REVIEWER"
        return "RESEARCHER"

    def _require_catalog_read(self, *, current_user: SessionPrincipal) -> None:
        role = self._role_for_user(current_user)
        if role in {"PROJECT_LEAD", "REVIEWER", "ADMIN"}:
            return
        raise DocumentModelCatalogAccessDeniedError("Current role cannot view approved model catalog routes.")

    def _require_catalog_mutation(self, *, current_user: SessionPrincipal) -> None:
        role = self._role_for_user(current_user)
        if role in {"PROJECT_LEAD", "ADMIN"}:
            return
        raise DocumentModelCatalogAccessDeniedError(
            "Current role cannot create approved model catalog entries."
        )

    def _require_assignment_read(
        self, *, current_user: SessionPrincipal, project_id: str
    ) -> None:
        if project_id != "project-1":
            raise ProjectNotFoundError("Project not found.")
        role = self._role_for_user(current_user)
        if role in {"PROJECT_LEAD", "REVIEWER", "ADMIN"}:
            return
        raise DocumentModelAssignmentAccessDeniedError(
            "Current role cannot view model-assignment routes in this project."
        )

    def _require_assignment_mutation(
        self, *, current_user: SessionPrincipal, project_id: str
    ) -> None:
        if project_id != "project-1":
            raise ProjectNotFoundError("Project not found.")
        role = self._role_for_user(current_user)
        if role in {"PROJECT_LEAD", "ADMIN"}:
            return
        raise DocumentModelAssignmentAccessDeniedError(
            "Current role cannot create, activate, or retire model assignments."
        )

    def list_approved_models(
        self,
        *,
        current_user: SessionPrincipal,
        model_role: str | None = None,
        status: str | None = None,
    ) -> list[ApprovedModelRecord]:
        self._require_catalog_read(current_user=current_user)
        rows = self.approved_models
        if isinstance(model_role, str) and model_role:
            rows = [row for row in rows if row.model_role == model_role]
        if isinstance(status, str) and status:
            rows = [row for row in rows if row.status == status]
        return rows

    def create_approved_model(
        self,
        *,
        current_user: SessionPrincipal,
        model_type: str,
        model_role: str,
        model_family: str,
        model_version: str,
        serving_interface: str,
        engine_family: str,
        deployment_unit: str,
        artifact_subpath: str,
        checksum_sha256: str,
        runtime_profile: str,
        response_contract_version: str,
        metadata_json: dict[str, object] | None = None,
    ) -> ApprovedModelRecord:
        self._require_catalog_mutation(current_user=current_user)
        now = datetime.now(UTC)
        record = ApprovedModelRecord(
            id=f"model-{model_role.lower()}-{model_family.lower()}-{model_version.lower()}",
            model_type=model_type,  # type: ignore[arg-type]
            model_role=model_role,  # type: ignore[arg-type]
            model_family=model_family,
            model_version=model_version,
            serving_interface=serving_interface,  # type: ignore[arg-type]
            engine_family=engine_family,
            deployment_unit=deployment_unit,
            artifact_subpath=artifact_subpath,
            checksum_sha256=checksum_sha256.lower(),
            runtime_profile=runtime_profile,
            response_contract_version=response_contract_version,
            metadata_json=metadata_json or {},
            status="APPROVED",
            approved_by=current_user.user_id,
            approved_at=now,
            created_at=now,
            updated_at=now,
        )
        self.approved_models.append(record)
        return record

    def list_project_model_assignments(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> list[ProjectModelAssignmentRecord]:
        self._require_assignment_read(current_user=current_user, project_id=project_id)
        return list(self.assignments.values())

    def create_project_model_assignment(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        model_role: str,
        approved_model_id: str,
        assignment_reason: str,
    ) -> ProjectModelAssignmentRecord:
        self._require_assignment_mutation(current_user=current_user, project_id=project_id)
        now = datetime.now(UTC)
        assignment = ProjectModelAssignmentRecord(
            id=f"assignment-{len(self.assignments) + 1}",
            project_id=project_id,
            model_role=model_role,  # type: ignore[arg-type]
            approved_model_id=approved_model_id,
            status="DRAFT",
            assignment_reason=assignment_reason,
            created_by=current_user.user_id,
            created_at=now,
            activated_by=None,
            activated_at=None,
            retired_by=None,
            retired_at=None,
        )
        self.assignments[assignment.id] = assignment
        return assignment

    def get_project_model_assignment(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        assignment_id: str,
    ) -> ProjectModelAssignmentRecord:
        self._require_assignment_read(current_user=current_user, project_id=project_id)
        row = self.assignments.get(assignment_id)
        if row is None:
            raise DocumentModelAssignmentNotFoundError("Model assignment not found.")
        return row

    def list_training_datasets_for_assignment(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        assignment_id: str,
    ) -> list[TrainingDatasetRecord]:
        self._require_assignment_read(current_user=current_user, project_id=project_id)
        if assignment_id not in self.assignments:
            raise DocumentModelAssignmentNotFoundError("Model assignment not found.")
        return [
            row
            for row in self.datasets
            if row.project_id == project_id and row.project_model_assignment_id == assignment_id
        ]

    def activate_project_model_assignment(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        assignment_id: str,
    ) -> ProjectModelAssignmentRecord:
        self._require_assignment_mutation(current_user=current_user, project_id=project_id)
        row = self.assignments.get(assignment_id)
        if row is None:
            raise DocumentModelAssignmentNotFoundError("Model assignment not found.")
        activated = replace(
            row,
            status="ACTIVE",
            activated_by=current_user.user_id,
            activated_at=datetime.now(UTC),
            retired_by=None,
            retired_at=None,
        )
        self.assignments[assignment_id] = activated
        return activated

    def retire_project_model_assignment(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        assignment_id: str,
    ) -> ProjectModelAssignmentRecord:
        self._require_assignment_mutation(current_user=current_user, project_id=project_id)
        row = self.assignments.get(assignment_id)
        if row is None:
            raise DocumentModelAssignmentNotFoundError("Model assignment not found.")
        retired = replace(
            row,
            status="RETIRED",
            retired_by=current_user.user_id,
            retired_at=datetime.now(UTC),
        )
        self.assignments[assignment_id] = retired
        return retired


def _principal(*, user_id: str, is_admin: bool = False) -> SessionPrincipal:
    now = datetime.now(UTC)
    return SessionPrincipal(
        session_id="session-1",
        auth_source="cookie",
        user_id=user_id,
        oidc_sub=f"oidc|{user_id}",
        email=f"{user_id}@example.test",
        display_name=user_id,
        platform_roles=("ADMIN",) if is_admin else (),
        issued_at=now - timedelta(minutes=5),
        expires_at=now + timedelta(hours=1),
        csrf_token="csrf-token",
    )


@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_reviewer_can_read_approved_model_catalog_and_assignment_routes() -> None:
    fake_service = FakeDocumentService()
    spy_audit = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="user-reviewer"
    )
    app.dependency_overrides[get_document_service] = lambda: fake_service
    app.dependency_overrides[get_audit_service] = lambda: spy_audit

    models_response = client.get("/approved-models")
    assert models_response.status_code == 200
    assert models_response.json()["items"][0]["modelRole"] == "TRANSCRIPTION_PRIMARY"

    assignments_response = client.get("/projects/project-1/model-assignments")
    assert assignments_response.status_code == 200
    assert assignments_response.json()["items"][0]["id"] == "assignment-1"

    datasets_response = client.get(
        "/projects/project-1/model-assignments/assignment-1/datasets"
    )
    assert datasets_response.status_code == 200
    assert datasets_response.json()["items"][0]["datasetKind"] == "TRANSCRIPTION_TRAINING"

    recorded_types = [str(item.get("event_type")) for item in spy_audit.recorded]
    assert "APPROVED_MODEL_LIST_VIEWED" in recorded_types
    assert "MODEL_ASSIGNMENT_LIST_VIEWED" in recorded_types
    assert "TRAINING_DATASET_VIEWED" in recorded_types


def test_reviewer_cannot_mutate_catalog_or_assignments() -> None:
    fake_service = FakeDocumentService()
    spy_audit = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="user-reviewer"
    )
    app.dependency_overrides[get_document_service] = lambda: fake_service
    app.dependency_overrides[get_audit_service] = lambda: spy_audit

    create_catalog_response = client.post(
        "/approved-models",
        json={
            "modelType": "LLM",
            "modelRole": "ASSIST",
            "modelFamily": "Qwen3",
            "modelVersion": "4B",
            "servingInterface": "OPENAI_CHAT",
            "engineFamily": "QWEN",
            "deploymentUnit": "internal-llm",
            "artifactSubpath": "internal-llm/qwen3-4b",
            "checksumSha256": "1" * 64,
            "runtimeProfile": "assist-default",
            "responseContractVersion": "v1",
        },
    )
    assert create_catalog_response.status_code == 403

    activate_assignment_response = client.post(
        "/projects/project-1/model-assignments/assignment-1/activate"
    )
    assert activate_assignment_response.status_code == 403

    denied_events = [
        item
        for item in spy_audit.recorded
        if str(item.get("event_type")) == "ACCESS_DENIED"
    ]
    assert len(denied_events) >= 2


def test_admin_can_create_and_activate_assignments_with_audit_events() -> None:
    fake_service = FakeDocumentService()
    spy_audit = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="user-admin",
        is_admin=True,
    )
    app.dependency_overrides[get_document_service] = lambda: fake_service
    app.dependency_overrides[get_audit_service] = lambda: spy_audit

    create_model_response = client.post(
        "/approved-models",
        json={
            "modelType": "LLM",
            "modelRole": "ASSIST",
            "modelFamily": "Qwen3",
            "modelVersion": "4B",
            "servingInterface": "OPENAI_CHAT",
            "engineFamily": "QWEN",
            "deploymentUnit": "internal-llm",
            "artifactSubpath": "internal-llm/qwen3-4b",
            "checksumSha256": "1" * 64,
            "runtimeProfile": "assist-default",
            "responseContractVersion": "v1",
        },
    )
    assert create_model_response.status_code == 201
    assert create_model_response.json()["modelRole"] == "ASSIST"

    create_assignment_response = client.post(
        "/projects/project-1/model-assignments",
        json={
            "modelRole": "ASSIST",
            "approvedModelId": create_model_response.json()["id"],
            "assignmentReason": "Add reviewer assist model",
        },
    )
    assert create_assignment_response.status_code == 201
    created_assignment_id = create_assignment_response.json()["id"]

    activate_response = client.post(
        f"/projects/project-1/model-assignments/{created_assignment_id}/activate"
    )
    assert activate_response.status_code == 200
    assert activate_response.json()["status"] == "ACTIVE"

    retire_response = client.post(
        f"/projects/project-1/model-assignments/{created_assignment_id}/retire"
    )
    assert retire_response.status_code == 200
    assert retire_response.json()["status"] == "RETIRED"

    recorded_types = [str(item.get("event_type")) for item in spy_audit.recorded]
    assert "APPROVED_MODEL_CREATED" in recorded_types
    assert "PROJECT_MODEL_ASSIGNMENT_CREATED" in recorded_types
    assert "PROJECT_MODEL_ACTIVATED" in recorded_types
    assert "PROJECT_MODEL_RETIRED" in recorded_types
