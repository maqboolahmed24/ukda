from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Literal

import pytest
from app.audit.service import get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.documents.models import (
    DocumentPageRecord,
    DocumentRecord,
    DocumentRedactionProjectionRecord,
    RedactionAreaMaskRecord,
    RedactionDecisionEventRecord,
    RedactionFindingRecord,
    RedactionOutputRecord,
    RedactionPageReviewEventRecord,
    RedactionPageReviewRecord,
    RedactionRunOutputEventRecord,
    RedactionRunOutputRecord,
    RedactionRunRecord,
    RedactionRunReviewEventRecord,
    RedactionRunReviewRecord,
)
from app.documents.service import (
    DocumentNotFoundError,
    DocumentPageAssetNotReadyError,
    DocumentPageNotFoundError,
    DocumentRedactionAccessDeniedError,
    DocumentRedactionComparePageSnapshot,
    DocumentRedactionCompareSnapshot,
    DocumentRedactionPolicyWarningSnapshot,
    DocumentRedactionConflictError,
    DocumentRedactionOverviewSnapshot,
    DocumentRedactionPreviewAsset,
    DocumentRedactionPreviewStatusSnapshot,
    DocumentRedactionRunNotFoundError,
    DocumentRedactionRunOutputSnapshot,
    DocumentRedactionRunPageSnapshot,
    DocumentRedactionRunTimelineEventSnapshot,
    DocumentValidationError,
    get_document_service,
)
from app.main import app
from app.projects.service import ProjectAccessDeniedError
from fastapi.testclient import TestClient

client = TestClient(app)


class SpyAuditService:
    def __init__(self) -> None:
        self.recorded: list[dict[str, object]] = []

    def record_event_best_effort(self, **kwargs):  # type: ignore[no-untyped-def]
        self.recorded.append(kwargs)
        return None


class FakeRedactionDocumentService:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self._clock = now
        self._etag_counter = 6
        self._run_sequence = 2
        self._event_sequence = 5

        self._project_roles: dict[str, Literal["PROJECT_LEAD", "RESEARCHER", "REVIEWER"]] = {
            "user-1": "PROJECT_LEAD",
            "user-2": "RESEARCHER",
            "user-3": "REVIEWER",
        }

        self._document = DocumentRecord(
            id="doc-2",
            project_id="project-1",
            original_filename="register-1880.pdf",
            stored_filename="controlled/raw/project-1/doc-2/original.bin",
            content_type_detected="application/pdf",
            bytes=125_000,
            sha256="4a6f95f913f2f7f6f613ebd4f8f1df31a5a4f83017db8e8fbf949f4ba4af0bc9",
            page_count=2,
            status="READY",
            created_by="user-1",
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(hours=6),
        )
        self._pages: list[DocumentPageRecord] = [
            DocumentPageRecord(
                id="page-1",
                document_id="doc-2",
                page_index=0,
                width=1000,
                height=1400,
                dpi=300,
                source_width=1000,
                source_height=1400,
                source_dpi=300,
                source_color_mode="GRAY",
                status="READY",
                derived_image_key="controlled/derived/project-1/doc-2/pages/0.png",
                derived_image_sha256="sha-page-0",
                thumbnail_key="controlled/derived/project-1/doc-2/thumbs/0.jpg",
                thumbnail_sha256="sha-thumb-0",
                failure_reason=None,
                canceled_by=None,
                canceled_at=None,
                viewer_rotation=0,
                created_at=now - timedelta(hours=5),
                updated_at=now - timedelta(hours=4),
            ),
            DocumentPageRecord(
                id="page-2",
                document_id="doc-2",
                page_index=1,
                width=1000,
                height=1400,
                dpi=300,
                source_width=1000,
                source_height=1400,
                source_dpi=300,
                source_color_mode="GRAY",
                status="READY",
                derived_image_key="controlled/derived/project-1/doc-2/pages/1.png",
                derived_image_sha256="sha-page-1",
                thumbnail_key="controlled/derived/project-1/doc-2/thumbs/1.jpg",
                thumbnail_sha256="sha-thumb-1",
                failure_reason=None,
                canceled_by=None,
                canceled_at=None,
                viewer_rotation=0,
                created_at=now - timedelta(hours=5),
                updated_at=now - timedelta(hours=4),
            ),
        ]

        run_1 = RedactionRunRecord(
            id="redaction-run-1",
            project_id="project-1",
            document_id="doc-2",
            input_transcription_run_id="transcription-run-1",
            input_layout_run_id="layout-run-1",
            run_kind="BASELINE",
            supersedes_redaction_run_id=None,
            superseded_by_redaction_run_id="redaction-run-2",
            policy_snapshot_id="policy-snapshot-v1",
            policy_snapshot_json={"directIdentifiersOnly": True},
            policy_snapshot_hash="policy-hash-v1",
            policy_id=None,
            policy_family_id=None,
            policy_version=None,
            detectors_version="phase-5.0-scaffold",
            status="SUCCEEDED",
            created_by="user-1",
            created_at=now - timedelta(hours=3),
            started_at=now - timedelta(hours=3),
            finished_at=now - timedelta(hours=2, minutes=50),
            failure_reason=None,
        )
        run_2 = RedactionRunRecord(
            id="redaction-run-2",
            project_id="project-1",
            document_id="doc-2",
            input_transcription_run_id="transcription-run-2",
            input_layout_run_id="layout-run-2",
            run_kind="POLICY_RERUN",
            supersedes_redaction_run_id="redaction-run-1",
            superseded_by_redaction_run_id=None,
            policy_snapshot_id="policy-snapshot-v2",
            policy_snapshot_json={
                "categories": [
                    {
                        "id": "PERSON_NAME",
                        "action": "ALLOW",
                        "review_required_below": 0.9,
                        "auto_apply_above": 0.7,
                    }
                ]
            },
            policy_snapshot_hash="policy-hash-v2",
            policy_id="policy-active-v2",
            policy_family_id="family-main",
            policy_version="2",
            detectors_version="phase-5.0-scaffold",
            status="SUCCEEDED",
            created_by="user-3",
            created_at=now - timedelta(hours=2),
            started_at=now - timedelta(hours=2),
            finished_at=now - timedelta(hours=1, minutes=45),
            failure_reason=None,
        )
        self._runs: dict[str, RedactionRunRecord] = {
            run_1.id: run_1,
            run_2.id: run_2,
        }
        self._run_order: list[str] = ["redaction-run-2", "redaction-run-1"]
        self._policy_catalog: dict[str, dict[str, object]] = {
            "policy-active-v2": {
                "status": "ACTIVE",
                "policy_family_id": "family-main",
                "version": 2,
                "validation_status": "VALID",
                "validated_rules_sha256": "policy-active-v2-hash",
                "rules_json": {
                    "categories": [{"id": "PERSON_NAME", "action": "MASK"}]
                },
            },
            "policy-draft-v3": {
                "status": "DRAFT",
                "policy_family_id": "family-main",
                "version": 3,
                "validation_status": "VALID",
                "validated_rules_sha256": "policy-draft-v3-hash",
                "rules_json": {
                    "categories": [
                        {
                            "id": "PERSON_NAME",
                            "action": "ALLOW",
                            "review_required_below": 0.9,
                            "auto_apply_above": 0.7,
                        }
                    ]
                },
            },
        }
        self._governance_ready_runs: set[str] = {"redaction-run-1", "redaction-run-2"}

        self._projection = DocumentRedactionProjectionRecord(
            document_id="doc-2",
            project_id="project-1",
            active_redaction_run_id="redaction-run-2",
            active_transcription_run_id="transcription-run-2",
            active_layout_run_id="layout-run-2",
            active_policy_snapshot_id="policy-snapshot-v2",
            updated_at=now - timedelta(hours=1),
        )

        self._run_reviews: dict[str, RedactionRunReviewRecord] = {
            "redaction-run-1": RedactionRunReviewRecord(
                run_id="redaction-run-1",
                review_status="APPROVED",
                review_started_by="user-3",
                review_started_at=now - timedelta(hours=2, minutes=45),
                approved_by="user-1",
                approved_at=now - timedelta(hours=2, minutes=30),
                approved_snapshot_key="controlled/derived/project-1/doc-2/redaction-run-1/review.json",
                approved_snapshot_sha256="approved-sha-1",
                locked_at=now - timedelta(hours=2, minutes=30),
                updated_at=now - timedelta(hours=2, minutes=30),
            ),
            "redaction-run-2": RedactionRunReviewRecord(
                run_id="redaction-run-2",
                review_status="IN_REVIEW",
                review_started_by="user-3",
                review_started_at=now - timedelta(hours=1, minutes=40),
                approved_by=None,
                approved_at=None,
                approved_snapshot_key=None,
                approved_snapshot_sha256=None,
                locked_at=None,
                updated_at=now - timedelta(hours=1, minutes=35),
            ),
        }

        self._findings: dict[str, list[RedactionFindingRecord]] = {
            "redaction-run-1": [
                RedactionFindingRecord(
                    id="finding-1-1",
                    run_id="redaction-run-1",
                    page_id="page-1",
                    line_id="line-1",
                    category="PERSON_NAME",
                    span_start=0,
                    span_end=5,
                    span_basis_kind="LINE_TEXT",
                    span_basis_ref="line-1",
                    confidence=0.92,
                    basis_primary="RULE",
                    basis_secondary_json=None,
                    assist_explanation_key=None,
                    assist_explanation_sha256=None,
                    bbox_refs={"bbox": [10, 10, 90, 30]},
                    token_refs_json=[{"tokenId": "token-1"}],
                    area_mask_id=None,
                    decision_status="APPROVED",
                    override_risk_classification=None,
                    override_risk_reason_codes_json=None,
                    decision_by="user-3",
                    decision_at=now - timedelta(hours=2, minutes=40),
                    decision_reason=None,
                    decision_etag="finding-1-1-v1",
                    updated_at=now - timedelta(hours=2, minutes=40),
                    created_at=now - timedelta(hours=2, minutes=55),
                )
            ],
            "redaction-run-2": [
                RedactionFindingRecord(
                    id="finding-2-1",
                    run_id="redaction-run-2",
                    page_id="page-1",
                    line_id="line-1",
                    category="PERSON_NAME",
                    span_start=0,
                    span_end=5,
                    span_basis_kind="LINE_TEXT",
                    span_basis_ref="line-1",
                    confidence=0.95,
                    basis_primary="RULE",
                    basis_secondary_json=None,
                    assist_explanation_key=None,
                    assist_explanation_sha256=None,
                    bbox_refs={"bbox": [10, 10, 90, 30]},
                    token_refs_json=[{"tokenId": "token-1"}],
                    area_mask_id=None,
                    decision_status="NEEDS_REVIEW",
                    override_risk_classification=None,
                    override_risk_reason_codes_json=None,
                    decision_by=None,
                    decision_at=None,
                    decision_reason=None,
                    decision_etag="finding-2-1-v1",
                    updated_at=now - timedelta(hours=1, minutes=50),
                    created_at=now - timedelta(hours=1, minutes=55),
                ),
                RedactionFindingRecord(
                    id="finding-2-2",
                    run_id="redaction-run-2",
                    page_id="page-2",
                    line_id=None,
                    category="EMAIL",
                    span_start=None,
                    span_end=None,
                    span_basis_kind="NONE",
                    span_basis_ref=None,
                    confidence=0.81,
                    basis_primary="NER",
                    basis_secondary_json={"model": "gliner-small"},
                    assist_explanation_key=None,
                    assist_explanation_sha256=None,
                    bbox_refs={"bbox": [40, 100, 220, 140]},
                    token_refs_json=None,
                    area_mask_id="mask-2-2",
                    decision_status="NEEDS_REVIEW",
                    override_risk_classification=None,
                    override_risk_reason_codes_json=None,
                    decision_by=None,
                    decision_at=None,
                    decision_reason=None,
                    decision_etag="finding-2-2-v1",
                    updated_at=now - timedelta(hours=1, minutes=45),
                    created_at=now - timedelta(hours=1, minutes=48),
                ),
            ],
        }

        self._page_reviews: dict[tuple[str, str], RedactionPageReviewRecord] = {
            ("redaction-run-1", "page-1"): RedactionPageReviewRecord(
                run_id="redaction-run-1",
                page_id="page-1",
                review_status="APPROVED",
                review_etag="review-1-1-v1",
                first_reviewed_by="user-3",
                first_reviewed_at=now - timedelta(hours=2, minutes=42),
                requires_second_review=False,
                second_review_status="NOT_REQUIRED",
                second_reviewed_by=None,
                second_reviewed_at=None,
                updated_at=now - timedelta(hours=2, minutes=42),
            ),
            ("redaction-run-1", "page-2"): RedactionPageReviewRecord(
                run_id="redaction-run-1",
                page_id="page-2",
                review_status="APPROVED",
                review_etag="review-1-2-v1",
                first_reviewed_by="user-3",
                first_reviewed_at=now - timedelta(hours=2, minutes=41),
                requires_second_review=False,
                second_review_status="NOT_REQUIRED",
                second_reviewed_by=None,
                second_reviewed_at=None,
                updated_at=now - timedelta(hours=2, minutes=41),
            ),
            ("redaction-run-2", "page-1"): RedactionPageReviewRecord(
                run_id="redaction-run-2",
                page_id="page-1",
                review_status="IN_REVIEW",
                review_etag="review-2-1-v1",
                first_reviewed_by="user-3",
                first_reviewed_at=now - timedelta(hours=1, minutes=42),
                requires_second_review=False,
                second_review_status="NOT_REQUIRED",
                second_reviewed_by=None,
                second_reviewed_at=None,
                updated_at=now - timedelta(hours=1, minutes=42),
            ),
            ("redaction-run-2", "page-2"): RedactionPageReviewRecord(
                run_id="redaction-run-2",
                page_id="page-2",
                review_status="NOT_STARTED",
                review_etag="review-2-2-v1",
                first_reviewed_by=None,
                first_reviewed_at=None,
                requires_second_review=False,
                second_review_status="NOT_REQUIRED",
                second_reviewed_by=None,
                second_reviewed_at=None,
                updated_at=now - timedelta(hours=1, minutes=41),
            ),
        }

        self._outputs: dict[tuple[str, str], RedactionOutputRecord] = {
            ("redaction-run-1", "page-1"): RedactionOutputRecord(
                run_id="redaction-run-1",
                page_id="page-1",
                status="READY",
                safeguarded_preview_key="controlled/derived/project-1/doc-2/redaction-run-1/page-1.png",
                preview_sha256="preview-1-1",
                started_at=now - timedelta(hours=2, minutes=50),
                generated_at=now - timedelta(hours=2, minutes=49),
                canceled_by=None,
                canceled_at=None,
                failure_reason=None,
                created_at=now - timedelta(hours=2, minutes=51),
                updated_at=now - timedelta(hours=2, minutes=49),
            ),
            ("redaction-run-1", "page-2"): RedactionOutputRecord(
                run_id="redaction-run-1",
                page_id="page-2",
                status="READY",
                safeguarded_preview_key="controlled/derived/project-1/doc-2/redaction-run-1/page-2.png",
                preview_sha256="preview-1-2",
                started_at=now - timedelta(hours=2, minutes=50),
                generated_at=now - timedelta(hours=2, minutes=49),
                canceled_by=None,
                canceled_at=None,
                failure_reason=None,
                created_at=now - timedelta(hours=2, minutes=51),
                updated_at=now - timedelta(hours=2, minutes=49),
            ),
            ("redaction-run-2", "page-1"): RedactionOutputRecord(
                run_id="redaction-run-2",
                page_id="page-1",
                status="READY",
                safeguarded_preview_key="controlled/derived/project-1/doc-2/redaction-run-2/page-1.png",
                preview_sha256="preview-2-1",
                started_at=now - timedelta(hours=1, minutes=50),
                generated_at=now - timedelta(hours=1, minutes=47),
                canceled_by=None,
                canceled_at=None,
                failure_reason=None,
                created_at=now - timedelta(hours=1, minutes=52),
                updated_at=now - timedelta(hours=1, minutes=47),
            ),
            ("redaction-run-2", "page-2"): RedactionOutputRecord(
                run_id="redaction-run-2",
                page_id="page-2",
                status="PENDING",
                safeguarded_preview_key=None,
                preview_sha256=None,
                started_at=now - timedelta(hours=1, minutes=50),
                generated_at=None,
                canceled_by=None,
                canceled_at=None,
                failure_reason=None,
                created_at=now - timedelta(hours=1, minutes=52),
                updated_at=now - timedelta(hours=1, minutes=46),
            ),
        }
        self._run_outputs: dict[str, RedactionRunOutputRecord] = {
            "redaction-run-1": RedactionRunOutputRecord(
                run_id="redaction-run-1",
                status="READY",
                output_manifest_key="controlled/derived/project-1/doc-2/redaction-run-1/manifest.json",
                output_manifest_sha256="manifest-1",
                page_count=2,
                started_at=now - timedelta(hours=2, minutes=50),
                generated_at=now - timedelta(hours=2, minutes=49),
                canceled_by=None,
                canceled_at=None,
                failure_reason=None,
                created_at=now - timedelta(hours=2, minutes=52),
                updated_at=now - timedelta(hours=2, minutes=49),
            ),
            "redaction-run-2": RedactionRunOutputRecord(
                run_id="redaction-run-2",
                status="PENDING",
                output_manifest_key=None,
                output_manifest_sha256=None,
                page_count=2,
                started_at=now - timedelta(hours=1, minutes=52),
                generated_at=None,
                canceled_by=None,
                canceled_at=None,
                failure_reason=None,
                created_at=now - timedelta(hours=1, minutes=52),
                updated_at=now - timedelta(hours=1, minutes=46),
            ),
        }

        self._area_masks: dict[tuple[str, str, str], RedactionAreaMaskRecord] = {
            ("redaction-run-2", "page-2", "mask-2-2"): RedactionAreaMaskRecord(
                id="mask-2-2",
                run_id="redaction-run-2",
                page_id="page-2",
                geometry_json={"bbox": [40, 100, 220, 140]},
                mask_reason="Unreadable direct identifier",
                version_etag="mask-2-2-v1",
                supersedes_area_mask_id=None,
                superseded_by_area_mask_id=None,
                created_by="user-3",
                created_at=now - timedelta(hours=1, minutes=46),
                updated_at=now - timedelta(hours=1, minutes=46),
            )
        }

        self._decision_events: list[RedactionDecisionEventRecord] = [
            RedactionDecisionEventRecord(
                id="decision-event-1",
                run_id="redaction-run-2",
                page_id="page-1",
                finding_id="finding-2-1",
                from_decision_status=None,
                to_decision_status="NEEDS_REVIEW",
                action_type="MASK",
                area_mask_id=None,
                actor_user_id="user-3",
                reason="Initial triage",
                created_at=now - timedelta(hours=1, minutes=50),
            )
        ]
        self._page_review_events: list[RedactionPageReviewEventRecord] = [
            RedactionPageReviewEventRecord(
                id="page-review-event-1",
                run_id="redaction-run-2",
                page_id="page-1",
                event_type="PAGE_REVIEW_STARTED",
                actor_user_id="user-3",
                reason=None,
                created_at=now - timedelta(hours=1, minutes=44),
            )
        ]
        self._run_review_events: list[RedactionRunReviewEventRecord] = [
            RedactionRunReviewEventRecord(
                id="run-review-event-1",
                run_id="redaction-run-2",
                event_type="RUN_REVIEW_OPENED",
                actor_user_id="user-3",
                reason=None,
                created_at=now - timedelta(hours=1, minutes=40),
            )
        ]
        self._run_output_events: list[RedactionRunOutputEventRecord] = [
            RedactionRunOutputEventRecord(
                id="run-output-event-1",
                run_id="redaction-run-1",
                event_type="RUN_OUTPUT_GENERATION_SUCCEEDED",
                from_status="PENDING",
                to_status="READY",
                reason=None,
                actor_user_id="user-1",
                created_at=now - timedelta(hours=2, minutes=49),
            ),
            RedactionRunOutputEventRecord(
                id="run-output-event-2",
                run_id="redaction-run-2",
                event_type="RUN_OUTPUT_GENERATION_STARTED",
                from_status="READY",
                to_status="PENDING",
                reason="Awaiting reviewed output generation.",
                actor_user_id="user-3",
                created_at=now - timedelta(hours=1, minutes=52),
            ),
        ]

    def _next_etag(self, prefix: str) -> str:
        self._etag_counter += 1
        return f"{prefix}-v{self._etag_counter}"

    def _next_event_id(self, prefix: str) -> str:
        self._event_sequence += 1
        return f"{prefix}-{self._event_sequence}"

    def _require_project_access(self, project_id: str) -> None:
        if project_id != "project-1":
            raise ProjectAccessDeniedError("Membership is required for this project route.")

    def _resolve_project_role(self, current_user: SessionPrincipal) -> str | None:
        return self._project_roles.get(current_user.user_id)

    def _require_redaction_view_access(
        self, *, current_user: SessionPrincipal, project_id: str
    ) -> None:
        self._require_project_access(project_id)
        if "ADMIN" in set(current_user.platform_roles):
            return
        role = self._resolve_project_role(current_user)
        if role not in {"PROJECT_LEAD", "RESEARCHER", "REVIEWER"}:
            raise DocumentRedactionAccessDeniedError(
                "Current role cannot access privacy-review routes for this project."
            )

    def _require_redaction_mutation_access(
        self, *, current_user: SessionPrincipal, project_id: str
    ) -> None:
        self._require_project_access(project_id)
        if "ADMIN" in set(current_user.platform_roles):
            return
        role = self._resolve_project_role(current_user)
        if role not in {"PROJECT_LEAD", "REVIEWER"}:
            raise DocumentRedactionAccessDeniedError(
                "Current role cannot mutate privacy-review runs in this project."
            )

    def _require_redaction_compare_access(
        self, *, current_user: SessionPrincipal, project_id: str
    ) -> None:
        self._require_project_access(project_id)
        if "ADMIN" in set(current_user.platform_roles) or "AUDITOR" in set(
            current_user.platform_roles
        ):
            return
        role = self._resolve_project_role(current_user)
        if role not in {"PROJECT_LEAD", "REVIEWER"}:
            raise DocumentRedactionAccessDeniedError(
                "Current role cannot view privacy compare routes in this project."
            )

    def _require_redaction_policy_rerun_access(
        self, *, current_user: SessionPrincipal, project_id: str
    ) -> None:
        self._require_project_access(project_id)
        if "ADMIN" in set(current_user.platform_roles):
            return
        role = self._resolve_project_role(current_user)
        if role != "PROJECT_LEAD":
            raise DocumentRedactionAccessDeniedError(
                "Current role cannot request policy reruns in this project."
            )

    def _require_reviewed_output_read_access(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        run_id: str,
    ) -> None:
        self._require_project_access(project_id)
        review = self._run_reviews.get(run_id)
        if review is None:
            raise DocumentRedactionRunNotFoundError("Redaction run review not found.")
        if "ADMIN" in set(current_user.platform_roles):
            return
        if "AUDITOR" in set(current_user.platform_roles):
            if review.review_status != "APPROVED":
                raise DocumentRedactionAccessDeniedError(
                    "Auditor access to reviewed outputs is available only for APPROVED runs."
                )
            return
        role = self._resolve_project_role(current_user)
        if role not in {"PROJECT_LEAD", "REVIEWER"}:
            raise DocumentRedactionAccessDeniedError(
                "Current role cannot access reviewed output artefacts."
            )

    @staticmethod
    def _derive_run_output_readiness_state(
        *,
        review_status: str,
        run_output: RedactionRunOutputRecord,
    ) -> Literal[
        "APPROVAL_REQUIRED",
        "APPROVED_OUTPUT_PENDING",
        "OUTPUT_GENERATING",
        "OUTPUT_FAILED",
        "OUTPUT_CANCELED",
        "OUTPUT_READY",
    ]:
        if review_status != "APPROVED":
            return "APPROVAL_REQUIRED"
        if run_output.status == "READY":
            return "OUTPUT_READY"
        if run_output.status == "FAILED":
            return "OUTPUT_FAILED"
        if run_output.status == "CANCELED":
            return "OUTPUT_CANCELED"
        if run_output.started_at is not None:
            return "OUTPUT_GENERATING"
        return "APPROVED_OUTPUT_PENDING"

    def _load_document(self, *, project_id: str, document_id: str) -> DocumentRecord:
        self._require_project_access(project_id)
        if document_id != self._document.id:
            raise DocumentNotFoundError("Document not found.")
        return self._document

    def _load_run(self, *, project_id: str, document_id: str, run_id: str) -> RedactionRunRecord:
        _ = self._load_document(project_id=project_id, document_id=document_id)
        run = self._runs.get(run_id)
        if run is None or run.document_id != document_id or run.project_id != project_id:
            raise DocumentRedactionRunNotFoundError("Redaction run was not found in project scope.")
        return run

    def _list_findings(
        self,
        *,
        run_id: str,
        page_id: str | None = None,
        category: str | None = None,
        unresolved_only: bool = False,
        direct_identifiers_only: bool = False,
    ) -> list[RedactionFindingRecord]:
        rows = list(self._findings.get(run_id, []))
        if page_id is not None:
            rows = [row for row in rows if row.page_id == page_id]
        if category:
            rows = [row for row in rows if row.category == category]
        if unresolved_only:
            rows = [
                row
                for row in rows
                if row.decision_status in {"NEEDS_REVIEW", "OVERRIDDEN", "FALSE_POSITIVE"}
            ]
        if direct_identifiers_only:
            rows = [row for row in rows if row.category in {"PERSON_NAME", "EMAIL", "PHONE"}]
        return sorted(rows, key=lambda row: (row.created_at, row.id))

    def _list_outputs_for_run(self, run_id: str) -> list[RedactionOutputRecord]:
        return [
            output
            for (candidate_run_id, _), output in self._outputs.items()
            if candidate_run_id == run_id
        ]

    def _run_review_locked(self, run_id: str) -> bool:
        review = self._run_reviews.get(run_id)
        return review is not None and review.review_status == "APPROVED"

    @staticmethod
    def _has_disagreement_markers(payload: dict[str, object] | None) -> bool:
        if payload is None:
            return False
        queue: list[object] = [payload]
        while queue:
            item = queue.pop(0)
            if isinstance(item, dict):
                for key, nested in item.items():
                    normalized = key.strip().lower()
                    if (
                        "disagreement" in normalized
                        or "ambiguous" in normalized
                        or "overlap" in normalized
                    ) and (
                        nested is True
                        or nested == "true"
                        or nested == 1
                        or nested == "1"
                    ):
                        return True
                    queue.append(nested)
            elif isinstance(item, list):
                queue.extend(item)
        return False

    def _derive_override_risk(
        self,
        *,
        run_id: str,
        finding: RedactionFindingRecord,
        decision_status: str,
        next_area_mask_id: str | None,
    ) -> tuple[str | None, list[str] | None]:
        if decision_status not in {"OVERRIDDEN", "FALSE_POSITIVE"}:
            return None, None
        reason_codes: list[str] = []
        if decision_status == "FALSE_POSITIVE":
            reason_codes.append("FALSE_POSITIVE_OVERRIDE")
        if isinstance(next_area_mask_id, str) and next_area_mask_id.strip():
            reason_codes.append("AREA_MASK_OVERRIDE")
        run = self._runs.get(run_id)
        policy_snapshot = run.policy_snapshot_json if run else {}
        dual_review_categories = set()
        if isinstance(policy_snapshot, dict):
            for key, value in policy_snapshot.items():
                normalized_key = key.strip().lower()
                if "dual" in normalized_key or "second_review" in normalized_key:
                    if isinstance(value, list):
                        dual_review_categories.update(
                            item.strip().upper()
                            for item in value
                            if isinstance(item, str) and item.strip()
                        )
        if finding.category.strip().upper() in dual_review_categories:
            reason_codes.append("POLICY_DUAL_REVIEW_CATEGORY")
        if self._has_disagreement_markers(finding.basis_secondary_json):
            reason_codes.append("DETECTOR_DISAGREEMENT_OR_AMBIGUOUS_OVERLAP")
        if reason_codes:
            return "HIGH", reason_codes
        return "STANDARD", None

    def _refresh_page_second_review_requirement(
        self,
        *,
        run_id: str,
        page_id: str,
        actor_user_id: str,
    ) -> None:
        review = self._page_reviews.get((run_id, page_id))
        if review is None:
            return
        high_risk_findings = [
            finding
            for finding in self._findings.get(run_id, [])
            if finding.page_id == page_id
            and finding.decision_status in {"OVERRIDDEN", "FALSE_POSITIVE"}
            and finding.override_risk_classification == "HIGH"
        ]
        requires_second_review = len(high_risk_findings) > 0
        second_review_status = review.second_review_status
        second_reviewed_by = review.second_reviewed_by
        second_reviewed_at = review.second_reviewed_at
        if requires_second_review:
            valid_second_reviewer = (
                isinstance(review.first_reviewed_by, str)
                and isinstance(review.second_reviewed_by, str)
                and review.first_reviewed_by != review.second_reviewed_by
                and review.second_review_status in {"APPROVED", "CHANGES_REQUESTED"}
            )
            if not valid_second_reviewer:
                second_review_status = "PENDING"
                second_reviewed_by = None
                second_reviewed_at = None
        else:
            second_review_status = "NOT_REQUIRED"
            second_reviewed_by = None
            second_reviewed_at = None

        if (
            review.requires_second_review == requires_second_review
            and review.second_review_status == second_review_status
            and review.second_reviewed_by == second_reviewed_by
            and review.second_reviewed_at == second_reviewed_at
        ):
            return

        now = datetime.now(UTC)
        self._page_reviews[(run_id, page_id)] = replace(
            review,
            requires_second_review=requires_second_review,
            second_review_status=second_review_status,
            second_reviewed_by=second_reviewed_by,
            second_reviewed_at=second_reviewed_at,
            review_etag=self._next_etag(f"review-{run_id}-{page_id}"),
            updated_at=now,
        )
        if requires_second_review and not review.requires_second_review:
            self._page_review_events.append(
                RedactionPageReviewEventRecord(
                    id=self._next_event_id("page-review-event"),
                    run_id=run_id,
                    page_id=page_id,
                    event_type="SECOND_REVIEW_REQUIRED",
                    actor_user_id=actor_user_id,
                    reason="Second review required due to high-risk override conditions.",
                    created_at=now,
                )
            )

    def get_redaction_projection(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
    ) -> DocumentRedactionProjectionRecord | None:
        self._require_redaction_view_access(current_user=current_user, project_id=project_id)
        _ = self._load_document(project_id=project_id, document_id=document_id)
        return self._projection

    def list_redaction_runs(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        cursor: int = 0,
        page_size: int = 50,
    ) -> tuple[list[RedactionRunRecord], int | None]:
        self._require_redaction_view_access(current_user=current_user, project_id=project_id)
        _ = self._load_document(project_id=project_id, document_id=document_id)
        ordered = [self._runs[run_id] for run_id in self._run_order]
        start = max(0, cursor)
        end = start + page_size
        next_cursor = end if end < len(ordered) else None
        return ordered[start:end], next_cursor

    def create_redaction_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        input_transcription_run_id: str | None = None,
        input_layout_run_id: str | None = None,
        run_kind: str | None = None,
        supersedes_redaction_run_id: str | None = None,
        detectors_version: str | None = None,
    ) -> RedactionRunRecord:
        self._require_redaction_mutation_access(current_user=current_user, project_id=project_id)
        _ = self._load_document(project_id=project_id, document_id=document_id)
        del supersedes_redaction_run_id
        self._run_sequence += 1
        run_id = f"redaction-run-{self._run_sequence + 1}"
        created = RedactionRunRecord(
            id=run_id,
            project_id=project_id,
            document_id=document_id,
            input_transcription_run_id=input_transcription_run_id or "transcription-run-2",
            input_layout_run_id=input_layout_run_id or "layout-run-2",
            run_kind="POLICY_RERUN" if run_kind == "POLICY_RERUN" else "BASELINE",
            supersedes_redaction_run_id=self._projection.active_redaction_run_id,
            superseded_by_redaction_run_id=None,
            policy_snapshot_id="policy-snapshot-v3",
            policy_snapshot_json={"directIdentifiersOnly": True, "createdByPrompt": 59},
            policy_snapshot_hash=f"policy-hash-{run_id}",
            policy_id=None,
            policy_family_id=None,
            policy_version=None,
            detectors_version=detectors_version or "phase-5.0-scaffold",
            status="QUEUED",
            created_by=current_user.user_id,
            created_at=datetime.now(UTC),
            started_at=None,
            finished_at=None,
            failure_reason=None,
        )
        self._runs[run_id] = created
        self._run_order.insert(0, run_id)
        self._run_reviews[run_id] = RedactionRunReviewRecord(
            run_id=run_id,
            review_status="NOT_READY",
            review_started_by=None,
            review_started_at=None,
            approved_by=None,
            approved_at=None,
            approved_snapshot_key=None,
            approved_snapshot_sha256=None,
            locked_at=None,
            updated_at=datetime.now(UTC),
        )
        for page in self._pages:
            self._page_reviews[(run_id, page.id)] = RedactionPageReviewRecord(
                run_id=run_id,
                page_id=page.id,
                review_status="NOT_STARTED",
                review_etag=self._next_etag(f"review-{run_id}-{page.id}"),
                first_reviewed_by=None,
                first_reviewed_at=None,
                requires_second_review=False,
                second_review_status="NOT_REQUIRED",
                second_reviewed_by=None,
                second_reviewed_at=None,
                updated_at=datetime.now(UTC),
            )
            self._outputs[(run_id, page.id)] = RedactionOutputRecord(
                run_id=run_id,
                page_id=page.id,
                status="PENDING",
                safeguarded_preview_key=None,
                preview_sha256=None,
                started_at=None,
                generated_at=None,
                canceled_by=None,
                canceled_at=None,
                failure_reason=None,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        self._run_outputs[run_id] = RedactionRunOutputRecord(
            run_id=run_id,
            status="PENDING",
            output_manifest_key=None,
            output_manifest_sha256=None,
            page_count=len(self._pages),
            started_at=None,
            generated_at=None,
            canceled_by=None,
            canceled_at=None,
            failure_reason=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self._findings[run_id] = []
        return created

    def request_policy_rerun(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        source_run_id: str,
        policy_id: str,
    ) -> RedactionRunRecord:
        self._require_redaction_policy_rerun_access(
            current_user=current_user,
            project_id=project_id,
        )
        source_run = self._load_run(
            project_id=project_id,
            document_id=document_id,
            run_id=source_run_id,
        )
        if source_run.status != "SUCCEEDED":
            raise DocumentRedactionConflictError("Policy rerun source run must be SUCCEEDED.")
        source_review = self._run_reviews.get(source_run_id)
        if source_review is None or source_review.review_status != "APPROVED":
            raise DocumentRedactionConflictError(
                "Policy rerun source run must be APPROVED under run review."
            )
        if source_run_id not in self._governance_ready_runs:
            raise DocumentRedactionConflictError(
                "Policy rerun source run must be governance-ready."
            )

        target_policy = self._policy_catalog.get(policy_id)
        if target_policy is None:
            raise DocumentValidationError("policyId was not found in the requested project.")
        if target_policy.get("status") not in {"ACTIVE", "DRAFT"}:
            raise DocumentRedactionConflictError(
                "Policy reruns require an ACTIVE or validated DRAFT target policy revision."
            )
        if target_policy.get("validation_status") != "VALID":
            raise DocumentRedactionConflictError(
                "Policy reruns require target policy validation_status=VALID."
            )
        if target_policy.get("validated_rules_sha256") not in {
            "policy-active-v2-hash",
            "policy-draft-v3-hash",
        }:
            raise DocumentRedactionConflictError(
                "Policy reruns reject stale validated revisions whose rules no longer match validated hash."
            )

        self._run_sequence += 1
        run_id = f"redaction-run-{self._run_sequence + 1}"
        now = datetime.now(UTC)
        created = RedactionRunRecord(
            id=run_id,
            project_id=project_id,
            document_id=document_id,
            input_transcription_run_id=source_run.input_transcription_run_id,
            input_layout_run_id=source_run.input_layout_run_id,
            run_kind="POLICY_RERUN",
            supersedes_redaction_run_id=source_run.id,
            superseded_by_redaction_run_id=None,
            policy_snapshot_id=policy_id,
            policy_snapshot_json=dict(target_policy.get("rules_json") or {}),
            policy_snapshot_hash=str(target_policy.get("validated_rules_sha256") or ""),
            policy_id=policy_id,
            policy_family_id=str(target_policy.get("policy_family_id") or "family-main"),
            policy_version=str(target_policy.get("version") or ""),
            detectors_version=source_run.detectors_version,
            status="SUCCEEDED",
            created_by=current_user.user_id,
            created_at=now,
            started_at=now,
            finished_at=now,
            failure_reason=None,
        )
        self._runs[source_run.id] = replace(
            source_run,
            superseded_by_redaction_run_id=run_id,
        )
        self._runs[run_id] = created
        self._run_order.insert(0, run_id)
        self._run_reviews[run_id] = RedactionRunReviewRecord(
            run_id=run_id,
            review_status="NOT_READY",
            review_started_by=None,
            review_started_at=None,
            approved_by=None,
            approved_at=None,
            approved_snapshot_key=None,
            approved_snapshot_sha256=None,
            locked_at=None,
            updated_at=now,
        )
        for page in self._pages:
            self._page_reviews[(run_id, page.id)] = RedactionPageReviewRecord(
                run_id=run_id,
                page_id=page.id,
                review_status="NOT_STARTED",
                review_etag=self._next_etag(f"review-{run_id}-{page.id}"),
                first_reviewed_by=None,
                first_reviewed_at=None,
                requires_second_review=False,
                second_review_status="NOT_REQUIRED",
                second_reviewed_by=None,
                second_reviewed_at=None,
                updated_at=now,
            )
            self._outputs[(run_id, page.id)] = RedactionOutputRecord(
                run_id=run_id,
                page_id=page.id,
                status="READY",
                safeguarded_preview_key=(
                    f"controlled/derived/project-1/doc-2/{run_id}/{page.id}.png"
                ),
                preview_sha256=f"preview-{run_id}-{page.id}",
                started_at=now,
                generated_at=now,
                canceled_by=None,
                canceled_at=None,
                failure_reason=None,
                created_at=now,
                updated_at=now,
            )
        self._run_outputs[run_id] = RedactionRunOutputRecord(
            run_id=run_id,
            status="READY",
            output_manifest_key=f"controlled/derived/project-1/doc-2/{run_id}/manifest.json",
            output_manifest_sha256=f"manifest-{run_id}",
            page_count=len(self._pages),
            started_at=now,
            generated_at=now,
            canceled_by=None,
            canceled_at=None,
            failure_reason=None,
            created_at=now,
            updated_at=now,
        )
        self._findings[run_id] = [
            replace(
                finding,
                id=f"{finding.id}-{run_id}",
                run_id=run_id,
                decision_etag=self._next_etag(f"{finding.id}-{run_id}"),
                updated_at=now,
                created_at=now,
            )
            for finding in self._findings.get(source_run.id, [])
        ]
        return created

    def get_active_redaction_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
    ) -> tuple[DocumentRedactionProjectionRecord | None, RedactionRunRecord | None]:
        self._require_redaction_view_access(current_user=current_user, project_id=project_id)
        _ = self._load_document(project_id=project_id, document_id=document_id)
        active = (
            self._runs.get(self._projection.active_redaction_run_id)
            if self._projection.active_redaction_run_id
            else None
        )
        return self._projection, active

    def get_redaction_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> RedactionRunRecord:
        self._require_redaction_view_access(current_user=current_user, project_id=project_id)
        return self._load_run(project_id=project_id, document_id=document_id, run_id=run_id)

    def get_redaction_run_status(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> RedactionRunRecord:
        return self.get_redaction_run(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )

    def cancel_redaction_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> RedactionRunRecord:
        self._require_redaction_mutation_access(current_user=current_user, project_id=project_id)
        run = self._load_run(project_id=project_id, document_id=document_id, run_id=run_id)
        if self._run_review_locked(run_id):
            raise DocumentRedactionConflictError("Approved redaction runs cannot be canceled.")
        updated = replace(
            run,
            status="CANCELED",
            finished_at=datetime.now(UTC),
        )
        self._runs[run_id] = updated
        for key, output in list(self._outputs.items()):
            if key[0] == run_id and output.status not in {"READY", "FAILED"}:
                self._outputs[key] = replace(
                    output,
                    status="CANCELED",
                    canceled_by=current_user.user_id,
                    canceled_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
        run_output = self._run_outputs.get(run_id)
        if run_output is not None:
            self._run_outputs[run_id] = replace(
                run_output,
                status="CANCELED",
                canceled_by=current_user.user_id,
                canceled_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        return updated

    def activate_redaction_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentRedactionProjectionRecord:
        self._require_redaction_mutation_access(current_user=current_user, project_id=project_id)
        run = self._load_run(project_id=project_id, document_id=document_id, run_id=run_id)
        review = self._run_reviews.get(run_id)
        if review is None or review.review_status != "APPROVED":
            raise DocumentRedactionConflictError("Run review must be approved before activation.")
        run_outputs = self._list_outputs_for_run(run_id)
        if any(output.status != "READY" for output in run_outputs):
            raise DocumentRedactionConflictError(
                "Safeguarded preview outputs must be READY before activation."
            )
        self._projection = replace(
            self._projection,
            active_redaction_run_id=run_id,
            active_transcription_run_id=run.input_transcription_run_id,
            active_layout_run_id=run.input_layout_run_id,
            active_policy_snapshot_id=run.policy_snapshot_id,
            updated_at=datetime.now(UTC),
        )
        return self._projection

    def get_redaction_run_review(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> RedactionRunReviewRecord:
        self._require_redaction_view_access(current_user=current_user, project_id=project_id)
        _ = self._load_run(project_id=project_id, document_id=document_id, run_id=run_id)
        review = self._run_reviews.get(run_id)
        if review is None:
            raise DocumentRedactionRunNotFoundError("Redaction run review not found.")
        return review

    def start_redaction_run_review(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> RedactionRunReviewRecord:
        self._require_redaction_mutation_access(current_user=current_user, project_id=project_id)
        _ = self._load_run(project_id=project_id, document_id=document_id, run_id=run_id)
        review = self._run_reviews[run_id]
        if review.review_status != "NOT_READY":
            raise DocumentRedactionConflictError(
                "Run review start requires NOT_READY status."
            )
        if any(
            review.review_status == "NOT_STARTED"
            for (candidate_run_id, _), review in self._page_reviews.items()
            if candidate_run_id == run_id
        ):
            raise DocumentRedactionConflictError(
                "Run review start requires every page to be reviewed at least once."
            )
        updated = replace(
            review,
            review_status="IN_REVIEW",
            review_started_by=review.review_started_by or current_user.user_id,
            review_started_at=review.review_started_at or datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self._run_reviews[run_id] = updated
        self._run_review_events.append(
            RedactionRunReviewEventRecord(
                id=self._next_event_id("run-review-event"),
                run_id=run_id,
                event_type="RUN_REVIEW_OPENED",
                actor_user_id=current_user.user_id,
                reason=None,
                created_at=datetime.now(UTC),
            )
        )
        return updated

    def complete_redaction_run_review(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        review_status: str,
        reason: str | None = None,
    ) -> RedactionRunReviewRecord:
        self._require_redaction_mutation_access(current_user=current_user, project_id=project_id)
        _ = self._load_run(project_id=project_id, document_id=document_id, run_id=run_id)
        if review_status not in {"APPROVED", "CHANGES_REQUESTED"}:
            raise DocumentRedactionConflictError("Run review completion requires APPROVED or CHANGES_REQUESTED.")
        review = self._run_reviews[run_id]
        if review.review_status != "IN_REVIEW":
            raise DocumentRedactionConflictError("Run review completion requires IN_REVIEW state.")
        if review_status == "APPROVED":
            for (candidate_run_id, _), page_review in self._page_reviews.items():
                if candidate_run_id != run_id:
                    continue
                if page_review.review_status != "APPROVED":
                    raise DocumentRedactionConflictError(
                        "Run approval requires every page review to be APPROVED."
                    )
                if (
                    page_review.requires_second_review
                    and page_review.second_review_status != "APPROVED"
                ):
                    raise DocumentRedactionConflictError(
                        "Run approval requires required second review to be APPROVED."
                    )
        now = datetime.now(UTC)
        updated = replace(
            review,
            review_status=review_status,
            approved_by=current_user.user_id if review_status == "APPROVED" else None,
            approved_at=now if review_status == "APPROVED" else None,
            approved_snapshot_key=(
                f"controlled/derived/project-1/doc-2/{run_id}/approved-review.json"
                if review_status == "APPROVED"
                else None
            ),
            approved_snapshot_sha256=(
                f"approved-{run_id}-{now.timestamp():.0f}"
                if review_status == "APPROVED"
                else None
            ),
            locked_at=now if review_status == "APPROVED" else None,
            updated_at=now,
        )
        self._run_reviews[run_id] = updated
        self._run_review_events.append(
            RedactionRunReviewEventRecord(
                id=self._next_event_id("run-review-event"),
                run_id=run_id,
                event_type=(
                    "RUN_APPROVED"
                    if review_status == "APPROVED"
                    else "RUN_CHANGES_REQUESTED"
                ),
                actor_user_id=current_user.user_id,
                reason=reason,
                created_at=now,
            )
        )
        return updated

    def list_redaction_run_events(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> list[DocumentRedactionRunTimelineEventSnapshot]:
        self._require_redaction_view_access(current_user=current_user, project_id=project_id)
        _ = self._load_run(project_id=project_id, document_id=document_id, run_id=run_id)
        rows: list[DocumentRedactionRunTimelineEventSnapshot] = []
        for event in self._decision_events:
            if event.run_id != run_id:
                continue
            rows.append(
                DocumentRedactionRunTimelineEventSnapshot(
                    source_table="redaction_decision_events",
                    source_table_precedence=0,
                    event_id=event.id,
                    run_id=event.run_id,
                    page_id=event.page_id,
                    finding_id=event.finding_id,
                    event_type=event.action_type,
                    actor_user_id=event.actor_user_id,
                    reason=event.reason,
                    created_at=event.created_at,
                    details_json={
                        "fromDecisionStatus": event.from_decision_status,
                        "toDecisionStatus": event.to_decision_status,
                        "actionType": event.action_type,
                        "areaMaskId": event.area_mask_id,
                    },
                )
            )
        for event in self._page_review_events:
            if event.run_id != run_id:
                continue
            rows.append(
                DocumentRedactionRunTimelineEventSnapshot(
                    source_table="redaction_page_review_events",
                    source_table_precedence=1,
                    event_id=event.id,
                    run_id=event.run_id,
                    page_id=event.page_id,
                    finding_id=None,
                    event_type=event.event_type,
                    actor_user_id=event.actor_user_id,
                    reason=event.reason,
                    created_at=event.created_at,
                    details_json={},
                )
            )
        for event in self._run_review_events:
            if event.run_id != run_id:
                continue
            rows.append(
                DocumentRedactionRunTimelineEventSnapshot(
                    source_table="redaction_run_review_events",
                    source_table_precedence=2,
                    event_id=event.id,
                    run_id=event.run_id,
                    page_id=None,
                    finding_id=None,
                    event_type=event.event_type,
                    actor_user_id=event.actor_user_id,
                    reason=event.reason,
                    created_at=event.created_at,
                    details_json={},
                )
            )
        for event in self._run_output_events:
            if event.run_id != run_id:
                continue
            rows.append(
                DocumentRedactionRunTimelineEventSnapshot(
                    source_table="redaction_run_output_events",
                    source_table_precedence=3,
                    event_id=event.id,
                    run_id=event.run_id,
                    page_id=None,
                    finding_id=None,
                    event_type=event.event_type,
                    actor_user_id=event.actor_user_id,
                    reason=event.reason,
                    created_at=event.created_at,
                    details_json={
                        "fromStatus": event.from_status,
                        "toStatus": event.to_status,
                    },
                )
            )
        return sorted(rows, key=lambda row: (row.created_at, row.source_table_precedence, row.event_id))

    def list_redaction_run_pages(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        category: str | None = None,
        unresolved_only: bool = False,
        direct_identifiers_only: bool = False,
        cursor: int = 0,
        page_size: int = 200,
    ) -> tuple[list[DocumentRedactionRunPageSnapshot], int | None]:
        self._require_redaction_view_access(current_user=current_user, project_id=project_id)
        _ = self._load_run(project_id=project_id, document_id=document_id, run_id=run_id)
        rows: list[DocumentRedactionRunPageSnapshot] = []
        for page in self._pages:
            page_findings = self._list_findings(
                run_id=run_id,
                page_id=page.id,
                category=category,
                unresolved_only=unresolved_only,
                direct_identifiers_only=direct_identifiers_only,
            )
            unresolved_count = sum(
                1
                for finding in page_findings
                if finding.decision_status in {"NEEDS_REVIEW", "OVERRIDDEN", "FALSE_POSITIVE"}
            )
            if unresolved_only and unresolved_count <= 0:
                continue
            review = self._page_reviews[(run_id, page.id)]
            output = self._outputs[(run_id, page.id)]
            rows.append(
                DocumentRedactionRunPageSnapshot(
                    run_id=run_id,
                    page_id=page.id,
                    page_index=page.page_index,
                    finding_count=len(page_findings),
                    unresolved_count=unresolved_count,
                    review_status=review.review_status,
                    review_etag=review.review_etag,
                    requires_second_review=review.requires_second_review,
                    second_review_status=review.second_review_status,
                    second_reviewed_by=review.second_reviewed_by,
                    second_reviewed_at=review.second_reviewed_at,
                    last_reviewed_by=review.first_reviewed_by,
                    last_reviewed_at=review.first_reviewed_at,
                    preview_status=output.status,
                    top_findings=tuple(page_findings[:3]),
                )
            )
        ordered = sorted(rows, key=lambda row: (row.page_index, row.page_id))
        start = max(0, cursor)
        end = start + page_size
        next_cursor = end if end < len(ordered) else None
        return ordered[start:end], next_cursor

    def list_redaction_run_page_findings(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        category: str | None = None,
        unresolved_only: bool = False,
        direct_identifiers_only: bool = False,
    ) -> list[RedactionFindingRecord]:
        self._require_redaction_view_access(current_user=current_user, project_id=project_id)
        _ = self._load_run(project_id=project_id, document_id=document_id, run_id=run_id)
        return self._list_findings(
            run_id=run_id,
            page_id=page_id,
            category=category,
            unresolved_only=unresolved_only,
            direct_identifiers_only=direct_identifiers_only,
        )

    def get_redaction_run_page_finding(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        finding_id: str,
    ) -> RedactionFindingRecord:
        self._require_redaction_view_access(current_user=current_user, project_id=project_id)
        _ = self._load_run(project_id=project_id, document_id=document_id, run_id=run_id)
        for finding in self._findings.get(run_id, []):
            if finding.id == finding_id and finding.page_id == page_id:
                return finding
        raise DocumentPageNotFoundError("Redaction finding not found.")

    def list_redaction_area_masks(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> list[RedactionAreaMaskRecord]:
        self._require_redaction_view_access(current_user=current_user, project_id=project_id)
        _ = self._load_run(project_id=project_id, document_id=document_id, run_id=run_id)
        return sorted(
            [
                mask
                for (candidate_run_id, candidate_page_id, _), mask in self._area_masks.items()
                if candidate_run_id == run_id and candidate_page_id == page_id
            ],
            key=lambda item: (item.created_at, item.id),
        )

    def get_redaction_area_mask_by_id(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        mask_id: str,
    ) -> RedactionAreaMaskRecord:
        self._require_redaction_view_access(current_user=current_user, project_id=project_id)
        _ = self._load_run(project_id=project_id, document_id=document_id, run_id=run_id)
        for (candidate_run_id, _, candidate_mask_id), mask in self._area_masks.items():
            if candidate_run_id == run_id and candidate_mask_id == mask_id:
                return mask
        raise DocumentPageNotFoundError("Redaction area mask not found.")

    def update_redaction_finding_decision(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        finding_id: str,
        expected_decision_etag: str,
        decision_status: str,
        reason: str | None = None,
        action_type: str | None = None,
    ) -> RedactionFindingRecord:
        self._require_redaction_mutation_access(current_user=current_user, project_id=project_id)
        _ = self._load_run(project_id=project_id, document_id=document_id, run_id=run_id)
        if self._run_review_locked(run_id):
            raise DocumentRedactionConflictError("Approved runs are locked and cannot be mutated.")
        normalized_action_type = "MASK"
        if isinstance(action_type, str) and action_type.strip():
            normalized_action_type = action_type.strip().upper()
        if normalized_action_type not in {"MASK", "PSEUDONYMIZE", "GENERALIZE"}:
            raise DocumentValidationError(
                "actionType must be MASK, PSEUDONYMIZE, or GENERALIZE."
            )
        findings = self._findings.get(run_id, [])
        for index, finding in enumerate(findings):
            if finding.id != finding_id:
                continue
            if finding.decision_etag != expected_decision_etag:
                raise DocumentRedactionConflictError("decisionEtag does not match current finding state.")
            override_risk_classification, override_risk_reason_codes = self._derive_override_risk(
                run_id=run_id,
                finding=finding,
                decision_status=decision_status,
                next_area_mask_id=finding.area_mask_id,
            )
            updated = replace(
                finding,
                decision_status=decision_status,
                action_type=normalized_action_type,
                override_risk_classification=override_risk_classification,
                override_risk_reason_codes_json=override_risk_reason_codes,
                decision_by=current_user.user_id,
                decision_at=datetime.now(UTC),
                decision_reason=reason,
                decision_etag=self._next_etag(finding.id),
                updated_at=datetime.now(UTC),
            )
            findings[index] = updated
            self._decision_events.append(
                RedactionDecisionEventRecord(
                    id=self._next_event_id("decision-event"),
                    run_id=run_id,
                    page_id=updated.page_id,
                    finding_id=updated.id,
                    from_decision_status=finding.decision_status,
                    to_decision_status=updated.decision_status,
                    action_type=normalized_action_type,
                    area_mask_id=updated.area_mask_id,
                    actor_user_id=current_user.user_id,
                    reason=reason,
                    created_at=datetime.now(UTC),
                )
            )
            current_output = self._outputs[(run_id, updated.page_id)]
            self._outputs[(run_id, updated.page_id)] = replace(
                current_output,
                status="PENDING",
                generated_at=None,
                preview_sha256=None,
                updated_at=datetime.now(UTC),
            )
            run_output = self._run_outputs[run_id]
            self._run_outputs[run_id] = replace(run_output, status="PENDING", updated_at=datetime.now(UTC))
            self._refresh_page_second_review_requirement(
                run_id=run_id,
                page_id=updated.page_id,
                actor_user_id=current_user.user_id,
            )
            return updated
        raise DocumentPageNotFoundError("Redaction finding not found.")

    def get_redaction_run_page_review(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> RedactionPageReviewRecord:
        self._require_redaction_view_access(current_user=current_user, project_id=project_id)
        _ = self._load_run(project_id=project_id, document_id=document_id, run_id=run_id)
        review = self._page_reviews.get((run_id, page_id))
        if review is None:
            raise DocumentPageNotFoundError("Redaction page review not found.")
        return review

    def update_redaction_page_review(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        expected_review_etag: str,
        review_status: str,
        reason: str | None = None,
    ) -> RedactionPageReviewRecord:
        self._require_redaction_mutation_access(current_user=current_user, project_id=project_id)
        _ = self._load_run(project_id=project_id, document_id=document_id, run_id=run_id)
        if self._run_review_locked(run_id):
            raise DocumentRedactionConflictError("Approved runs are locked and cannot be mutated.")
        review = self._page_reviews.get((run_id, page_id))
        if review is None:
            raise DocumentPageNotFoundError("Redaction page review not found.")
        if review.review_etag != expected_review_etag:
            raise DocumentRedactionConflictError("reviewEtag does not match current page review state.")
        now = datetime.now(UTC)
        next_first_reviewed_by = review.first_reviewed_by or current_user.user_id
        next_first_reviewed_at = review.first_reviewed_at or now
        next_review_status = review_status
        next_second_review_status = review.second_review_status
        next_second_reviewed_by = review.second_reviewed_by
        next_second_reviewed_at = review.second_reviewed_at
        event_type = (
            "PAGE_APPROVED"
            if review_status == "APPROVED"
            else "CHANGES_REQUESTED"
            if review_status == "CHANGES_REQUESTED"
            else "PAGE_REVIEW_STARTED"
        )
        if review.requires_second_review:
            if (
                review.first_reviewed_by is not None
                and current_user.user_id == review.first_reviewed_by
                and review.review_status == "APPROVED"
                and review_status in {"APPROVED", "CHANGES_REQUESTED"}
            ):
                raise DocumentRedactionConflictError(
                    "Second review must be completed by a different reviewer."
                )
            if (
                review.first_reviewed_by is not None
                and current_user.user_id != review.first_reviewed_by
                and review.review_status == "APPROVED"
                and review_status in {"APPROVED", "CHANGES_REQUESTED"}
            ):
                next_second_review_status = (
                    "APPROVED" if review_status == "APPROVED" else "CHANGES_REQUESTED"
                )
                next_second_reviewed_by = current_user.user_id
                next_second_reviewed_at = now
                event_type = (
                    "SECOND_REVIEW_APPROVED"
                    if review_status == "APPROVED"
                    else "SECOND_REVIEW_CHANGES_REQUESTED"
                )
                next_review_status = review_status
            else:
                next_second_review_status = "PENDING"
                next_second_reviewed_by = None
                next_second_reviewed_at = None
        else:
            next_second_review_status = "NOT_REQUIRED"
            next_second_reviewed_by = None
            next_second_reviewed_at = None

        updated = replace(
            review,
            review_status=next_review_status,
            review_etag=self._next_etag(f"review-{run_id}-{page_id}"),
            first_reviewed_by=next_first_reviewed_by,
            first_reviewed_at=next_first_reviewed_at,
            second_review_status=next_second_review_status,
            second_reviewed_by=next_second_reviewed_by,
            second_reviewed_at=next_second_reviewed_at,
            updated_at=now,
        )
        self._page_reviews[(run_id, page_id)] = updated
        self._page_review_events.append(
            RedactionPageReviewEventRecord(
                id=self._next_event_id("page-review-event"),
                run_id=run_id,
                page_id=page_id,
                event_type=event_type,
                actor_user_id=current_user.user_id,
                reason=reason,
                created_at=now,
            )
        )
        return updated

    def list_redaction_run_page_events(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> list[DocumentRedactionRunTimelineEventSnapshot]:
        self._require_redaction_view_access(current_user=current_user, project_id=project_id)
        _ = self._load_run(project_id=project_id, document_id=document_id, run_id=run_id)
        merged = [
            event
            for event in self.list_redaction_run_events(
                current_user=current_user,
                project_id=project_id,
                document_id=document_id,
                run_id=run_id,
            )
            if event.page_id == page_id
        ]
        return merged

    def get_redaction_page_preview_status(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> DocumentRedactionPreviewStatusSnapshot:
        self._require_reviewed_output_read_access(
            current_user=current_user,
            project_id=project_id,
            run_id=run_id,
        )
        _ = self._load_run(project_id=project_id, document_id=document_id, run_id=run_id)
        output = self._outputs.get((run_id, page_id))
        if output is None:
            raise DocumentPageNotFoundError("Redaction preview status was not found.")
        run_output = self._run_outputs.get(run_id)
        review = self._run_reviews.get(run_id)
        readiness_state = (
            self._derive_run_output_readiness_state(
                review_status=review.review_status,
                run_output=run_output,
            )
            if review is not None and run_output is not None
            else None
        )
        return DocumentRedactionPreviewStatusSnapshot(
            run_id=run_id,
            page_id=page_id,
            status=output.status,
            preview_sha256=output.preview_sha256,
            generated_at=output.generated_at,
            failure_reason=output.failure_reason,
            run_output_status=run_output.status if run_output else None,
            run_output_manifest_sha256=(
                run_output.output_manifest_sha256 if run_output else None
            ),
            run_output_readiness_state=readiness_state,
            downstream_ready=readiness_state == "OUTPUT_READY",
        )

    def read_redaction_page_preview(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> DocumentRedactionPreviewAsset:
        snapshot = self.get_redaction_page_preview_status(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=page_id,
        )
        if snapshot.status != "READY":
            raise DocumentPageAssetNotReadyError("Safeguarded preview is not ready for this page.")
        return DocumentRedactionPreviewAsset(
            payload=b"fixture-redaction-preview",
            media_type="image/png",
            etag_seed=snapshot.preview_sha256,
            cache_control="private, no-cache, max-age=0, must-revalidate",
        )

    def get_redaction_run_output(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentRedactionRunOutputSnapshot:
        self._require_reviewed_output_read_access(
            current_user=current_user,
            project_id=project_id,
            run_id=run_id,
        )
        _ = self._load_run(project_id=project_id, document_id=document_id, run_id=run_id)
        output = self._run_outputs.get(run_id)
        if output is None:
            raise DocumentRedactionRunNotFoundError("Redaction run output not found.")
        review = self._run_reviews.get(run_id)
        if review is None:
            raise DocumentRedactionRunNotFoundError("Redaction run review not found.")
        readiness_state = self._derive_run_output_readiness_state(
            review_status=review.review_status,
            run_output=output,
        )
        return DocumentRedactionRunOutputSnapshot(
            run_output=output,
            review_status=review.review_status,
            readiness_state=readiness_state,
            downstream_ready=readiness_state == "OUTPUT_READY",
        )

    def get_redaction_run_output_status(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> DocumentRedactionRunOutputSnapshot:
        return self.get_redaction_run_output(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )

    def revise_redaction_area_mask(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        mask_id: str,
        expected_version_etag: str,
        geometry_json: dict[str, object],
        mask_reason: str,
        finding_id: str | None = None,
        expected_finding_decision_etag: str | None = None,
    ) -> tuple[RedactionAreaMaskRecord, RedactionFindingRecord | None]:
        self._require_redaction_mutation_access(current_user=current_user, project_id=project_id)
        _ = self._load_run(project_id=project_id, document_id=document_id, run_id=run_id)
        if self._run_review_locked(run_id):
            raise DocumentRedactionConflictError("Approved runs are locked and cannot be mutated.")
        key = (run_id, page_id, mask_id)
        mask = self._area_masks.get(key)
        if mask is None:
            raise DocumentPageNotFoundError("Redaction area mask not found.")
        if mask.version_etag != expected_version_etag:
            raise DocumentRedactionConflictError("versionEtag does not match current area-mask state.")
        now = datetime.now(UTC)
        new_mask_id = self._next_event_id("mask")
        updated_mask = replace(
            mask,
            id=new_mask_id,
            geometry_json=dict(geometry_json),
            mask_reason=mask_reason,
            version_etag=self._next_etag(new_mask_id),
            supersedes_area_mask_id=mask.id,
            superseded_by_area_mask_id=None,
            created_by=current_user.user_id,
            created_at=now,
            updated_at=now,
        )
        self._area_masks[(run_id, page_id, new_mask_id)] = updated_mask
        self._area_masks[key] = replace(
            mask,
            superseded_by_area_mask_id=updated_mask.id,
            updated_at=now,
        )

        updated_finding: RedactionFindingRecord | None = None
        if finding_id:
            findings = self._findings.get(run_id, [])
            for index, finding in enumerate(findings):
                if finding.id != finding_id:
                    continue
                if expected_finding_decision_etag != finding.decision_etag:
                    raise DocumentRedactionConflictError(
                        "findingDecisionEtag does not match current finding state."
                    )
                override_risk_classification, override_risk_reason_codes = self._derive_override_risk(
                    run_id=run_id,
                    finding=finding,
                    decision_status="OVERRIDDEN",
                    next_area_mask_id=updated_mask.id,
                )
                updated_finding = replace(
                    finding,
                    area_mask_id=updated_mask.id,
                    decision_status="OVERRIDDEN",
                    action_type="MASK",
                    override_risk_classification=override_risk_classification,
                    override_risk_reason_codes_json=override_risk_reason_codes,
                    decision_by=current_user.user_id,
                    decision_at=now,
                    decision_reason=mask_reason,
                    decision_etag=self._next_etag(finding.id),
                    updated_at=now,
                )
                findings[index] = updated_finding
                self._decision_events.append(
                    RedactionDecisionEventRecord(
                        id=self._next_event_id("decision-event"),
                        run_id=run_id,
                        page_id=page_id,
                        finding_id=finding_id,
                        from_decision_status=finding.decision_status,
                        to_decision_status=updated_finding.decision_status,
                        action_type="MASK",
                        area_mask_id=updated_mask.id,
                        actor_user_id=current_user.user_id,
                        reason=mask_reason,
                        created_at=now,
                    )
                )
                break

        current_output = self._outputs[(run_id, page_id)]
        self._outputs[(run_id, page_id)] = replace(
            current_output,
            status="PENDING",
            generated_at=None,
            preview_sha256=None,
            updated_at=now,
        )
        self._run_outputs[run_id] = replace(self._run_outputs[run_id], status="PENDING", updated_at=now)
        self._refresh_page_second_review_requirement(
            run_id=run_id,
            page_id=page_id,
            actor_user_id=current_user.user_id,
        )
        return updated_mask, updated_finding

    def create_redaction_area_mask(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        geometry_json: dict[str, object],
        mask_reason: str,
        finding_id: str | None = None,
        expected_finding_decision_etag: str | None = None,
    ) -> tuple[RedactionAreaMaskRecord, RedactionFindingRecord | None]:
        self._require_redaction_mutation_access(current_user=current_user, project_id=project_id)
        _ = self._load_run(project_id=project_id, document_id=document_id, run_id=run_id)
        if self._run_review_locked(run_id):
            raise DocumentRedactionConflictError("Approved runs are locked and cannot be mutated.")
        now = datetime.now(UTC)
        new_mask_id = self._next_event_id("mask")
        created_mask = RedactionAreaMaskRecord(
            id=new_mask_id,
            run_id=run_id,
            page_id=page_id,
            geometry_json=dict(geometry_json),
            mask_reason=mask_reason,
            version_etag=self._next_etag(new_mask_id),
            supersedes_area_mask_id=None,
            superseded_by_area_mask_id=None,
            created_by=current_user.user_id,
            created_at=now,
            updated_at=now,
        )
        self._area_masks[(run_id, page_id, created_mask.id)] = created_mask

        updated_finding: RedactionFindingRecord | None = None
        if finding_id:
            findings = self._findings.get(run_id, [])
            for index, finding in enumerate(findings):
                if finding.id != finding_id:
                    continue
                if finding.page_id != page_id:
                    raise DocumentRedactionConflictError(
                        "Linked redaction finding must belong to the same page."
                    )
                if expected_finding_decision_etag and expected_finding_decision_etag != finding.decision_etag:
                    raise DocumentRedactionConflictError(
                        "findingDecisionEtag does not match current finding state."
                    )
                override_risk_classification, override_risk_reason_codes = self._derive_override_risk(
                    run_id=run_id,
                    finding=finding,
                    decision_status="OVERRIDDEN",
                    next_area_mask_id=created_mask.id,
                )
                updated_finding = replace(
                    finding,
                    area_mask_id=created_mask.id,
                    decision_status="OVERRIDDEN",
                    action_type="MASK",
                    override_risk_classification=override_risk_classification,
                    override_risk_reason_codes_json=override_risk_reason_codes,
                    decision_by=current_user.user_id,
                    decision_at=now,
                    decision_reason=mask_reason,
                    decision_etag=self._next_etag(finding.id),
                    updated_at=now,
                )
                findings[index] = updated_finding
                self._decision_events.append(
                    RedactionDecisionEventRecord(
                        id=self._next_event_id("decision-event"),
                        run_id=run_id,
                        page_id=page_id,
                        finding_id=finding_id,
                        from_decision_status=finding.decision_status,
                        to_decision_status=updated_finding.decision_status,
                        action_type="MASK",
                        area_mask_id=created_mask.id,
                        actor_user_id=current_user.user_id,
                        reason=mask_reason,
                        created_at=now,
                    )
                )
                break

        current_output = self._outputs[(run_id, page_id)]
        self._outputs[(run_id, page_id)] = replace(
            current_output,
            status="PENDING",
            generated_at=None,
            preview_sha256=None,
            updated_at=now,
        )
        self._run_outputs[run_id] = replace(
            self._run_outputs[run_id],
            status="PENDING",
            updated_at=now,
        )
        self._refresh_page_second_review_requirement(
            run_id=run_id,
            page_id=page_id,
            actor_user_id=current_user.user_id,
        )
        return created_mask, updated_finding

    def revise_redaction_area_mask_by_id(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        mask_id: str,
        expected_version_etag: str,
        geometry_json: dict[str, object],
        mask_reason: str,
        finding_id: str | None = None,
        expected_finding_decision_etag: str | None = None,
    ) -> tuple[RedactionAreaMaskRecord, RedactionFindingRecord | None]:
        mask = self.get_redaction_area_mask_by_id(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            mask_id=mask_id,
        )
        return self.revise_redaction_area_mask(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_id=mask.page_id,
            mask_id=mask_id,
            expected_version_etag=expected_version_etag,
            geometry_json=geometry_json,
            mask_reason=mask_reason,
            finding_id=finding_id,
            expected_finding_decision_etag=expected_finding_decision_etag,
        )

    def get_redaction_overview(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
    ) -> DocumentRedactionOverviewSnapshot:
        self._require_redaction_view_access(current_user=current_user, project_id=project_id)
        document = self._load_document(project_id=project_id, document_id=document_id)
        active_run = self._runs.get(self._projection.active_redaction_run_id or "")
        latest_run = self._runs[self._run_order[0]] if self._run_order else None
        findings_by_category: dict[str, int] = {}
        unresolved_findings = 0
        auto_applied_findings = 0
        needs_review_findings = 0
        overridden_findings = 0
        pages_blocked = 0
        preview_ready = 0
        preview_failed = 0
        preview_total = 0

        if active_run:
            findings = self._findings.get(active_run.id, [])
            for finding in findings:
                findings_by_category[finding.category] = findings_by_category.get(finding.category, 0) + 1
                if finding.decision_status == "AUTO_APPLIED":
                    auto_applied_findings += 1
                elif finding.decision_status == "NEEDS_REVIEW":
                    needs_review_findings += 1
                elif finding.decision_status == "OVERRIDDEN":
                    overridden_findings += 1
                if finding.decision_status in {"NEEDS_REVIEW", "OVERRIDDEN", "FALSE_POSITIVE"}:
                    unresolved_findings += 1
            for page in self._pages:
                review = self._page_reviews[(active_run.id, page.id)]
                if review.review_status != "APPROVED" or (
                    review.requires_second_review
                    and review.second_review_status != "APPROVED"
                ):
                    pages_blocked += 1
            outputs = self._list_outputs_for_run(active_run.id)
            preview_total = len(outputs)
            preview_ready = sum(1 for output in outputs if output.status == "READY")
            preview_failed = sum(1 for output in outputs if output.status == "FAILED")

        return DocumentRedactionOverviewSnapshot(
            document=document,
            projection=self._projection,
            active_run=active_run,
            latest_run=latest_run,
            total_runs=len(self._run_order),
            page_count=len(self._pages),
            findings_by_category=findings_by_category,
            unresolved_findings=unresolved_findings,
            auto_applied_findings=auto_applied_findings,
            needs_review_findings=needs_review_findings,
            overridden_findings=overridden_findings,
            pages_blocked_for_review=pages_blocked,
            preview_ready_pages=preview_ready,
            preview_total_pages=preview_total,
            preview_failed_pages=preview_failed,
        )

    def compare_redaction_runs(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        base_run_id: str,
        candidate_run_id: str,
    ) -> DocumentRedactionCompareSnapshot:
        self._require_redaction_compare_access(current_user=current_user, project_id=project_id)
        document = self._load_document(project_id=project_id, document_id=document_id)
        base_run = self._load_run(project_id=project_id, document_id=document_id, run_id=base_run_id)
        candidate_run = self._load_run(project_id=project_id, document_id=document_id, run_id=candidate_run_id)

        pages: list[DocumentRedactionComparePageSnapshot] = []
        changed_pages = 0
        changed_decisions = 0
        changed_actions = 0
        base_action_by_finding = {
            event.finding_id: event.action_type
            for event in sorted(
                [item for item in self._decision_events if item.run_id == base_run.id],
                key=lambda item: (item.created_at, item.id),
            )
        }
        candidate_action_by_finding = {
            event.finding_id: event.action_type
            for event in sorted(
                [item for item in self._decision_events if item.run_id == candidate_run.id],
                key=lambda item: (item.created_at, item.id),
            )
        }
        for page in self._pages:
            base_findings = self._list_findings(run_id=base_run.id, page_id=page.id)
            candidate_findings = self._list_findings(run_id=candidate_run.id, page_id=page.id)
            base_by_key = {
                (row.category, row.line_id, row.span_start, row.span_end): row
                for row in base_findings
            }
            candidate_by_key = {
                (row.category, row.line_id, row.span_start, row.span_end): row
                for row in candidate_findings
            }
            page_decision_changes = 0
            for key in set(base_by_key) | set(candidate_by_key):
                base_finding = base_by_key.get(key)
                candidate_finding = candidate_by_key.get(key)
                if base_finding is None or candidate_finding is None:
                    page_decision_changes += 1
                    continue
                if base_finding.decision_status != candidate_finding.decision_status:
                    page_decision_changes += 1
            base_review = self._page_reviews.get((base_run.id, page.id))
            candidate_review = self._page_reviews.get((candidate_run.id, page.id))
            base_decision_counts: dict[str, int] = {}
            candidate_decision_counts: dict[str, int] = {}
            base_action_counts: dict[str, int] = {}
            candidate_action_counts: dict[str, int] = {}
            for finding in base_findings:
                base_decision_counts[finding.decision_status] = (
                    base_decision_counts.get(finding.decision_status, 0) + 1
                )
                action = base_action_by_finding.get(finding.id, "MASK")
                base_action_counts[action] = base_action_counts.get(action, 0) + 1
            for finding in candidate_findings:
                candidate_decision_counts[finding.decision_status] = (
                    candidate_decision_counts.get(finding.decision_status, 0) + 1
                )
                action = candidate_action_by_finding.get(finding.id, "MASK")
                candidate_action_counts[action] = candidate_action_counts.get(action, 0) + 1
            decision_status_deltas = {
                status: candidate_decision_counts.get(status, 0)
                - base_decision_counts.get(status, 0)
                for status in (
                    "AUTO_APPLIED",
                    "NEEDS_REVIEW",
                    "APPROVED",
                    "OVERRIDDEN",
                    "FALSE_POSITIVE",
                )
            }
            action_type_deltas = {
                action: candidate_action_counts.get(action, 0) - base_action_counts.get(action, 0)
                for action in ("MASK", "PSEUDONYMIZE", "GENERALIZE")
            }
            page_action_changes = sum(abs(delta) for delta in action_type_deltas.values())
            changed_review_status = (
                (base_review.review_status if base_review is not None else None)
                != (candidate_review.review_status if candidate_review is not None else None)
            )
            changed_second_review_status = (
                (base_review.second_review_status if base_review is not None else None)
                != (
                    candidate_review.second_review_status
                    if candidate_review is not None
                    else None
                )
            )
            base_preview_status = self._outputs[(base_run.id, page.id)].status
            candidate_preview_status = self._outputs[(candidate_run.id, page.id)].status
            preview_ready_delta = int(candidate_preview_status == "READY") - int(
                base_preview_status == "READY"
            )
            action_compare_state = (
                "AVAILABLE"
                if base_preview_status == "READY" and candidate_preview_status == "READY"
                else "NOT_YET_AVAILABLE"
            )
            if (
                page_decision_changes > 0
                or page_action_changes > 0
                or changed_review_status
                or changed_second_review_status
                or base_preview_status != candidate_preview_status
            ):
                changed_pages += 1
            changed_decisions += page_decision_changes
            changed_actions += page_action_changes
            pages.append(
                DocumentRedactionComparePageSnapshot(
                    page_id=page.id,
                    page_index=page.page_index,
                    base_finding_count=len(base_findings),
                    candidate_finding_count=len(candidate_findings),
                    changed_decision_count=page_decision_changes,
                    changed_action_count=page_action_changes,
                    base_decision_counts=base_decision_counts,
                    candidate_decision_counts=candidate_decision_counts,
                    decision_status_deltas=decision_status_deltas,
                    base_action_counts=base_action_counts,  # type: ignore[arg-type]
                    candidate_action_counts=candidate_action_counts,  # type: ignore[arg-type]
                    action_type_deltas=action_type_deltas,  # type: ignore[arg-type]
                    action_compare_state=action_compare_state,  # type: ignore[arg-type]
                    changed_review_status=changed_review_status,
                    changed_second_review_status=changed_second_review_status,
                    base_review=base_review,
                    candidate_review=candidate_review,
                    base_preview_status=base_preview_status,
                    candidate_preview_status=candidate_preview_status,
                    preview_ready_delta=preview_ready_delta,
                )
            )

        pre_activation_warnings: tuple[DocumentRedactionPolicyWarningSnapshot, ...] = ()
        if candidate_run.policy_id == "policy-draft-v3":
            pre_activation_warnings = (
                DocumentRedactionPolicyWarningSnapshot(
                    code="BROAD_ALLOW_RULE",
                    severity="WARNING",
                    message="Policy contains broad allow action(s).",
                    affected_categories=("PERSON_NAME",),
                ),
                DocumentRedactionPolicyWarningSnapshot(
                    code="INCONSISTENT_THRESHOLD",
                    severity="WARNING",
                    message="Policy contains inconsistent confidence thresholds.",
                    affected_categories=("PERSON_NAME",),
                ),
            )
        candidate_policy_status: str | None = None
        if candidate_run.policy_id:
            status_value = self._policy_catalog.get(candidate_run.policy_id, {}).get("status")
            if isinstance(status_value, str):
                candidate_policy_status = status_value

        return DocumentRedactionCompareSnapshot(
            document=document,
            base_run=base_run,
            candidate_run=candidate_run,
            pages=tuple(pages),
            changed_page_count=changed_pages,
            changed_decision_count=changed_decisions,
            changed_action_count=changed_actions,
            compare_action_state=(
                "AVAILABLE"
                if all(page.action_compare_state == "AVAILABLE" for page in pages)
                else "NOT_YET_AVAILABLE"
            ),
            candidate_policy_status=candidate_policy_status,
            comparison_only_candidate=candidate_run.policy_id == "policy-draft-v3",
            pre_activation_warnings=pre_activation_warnings,
        )


def _principal(
    *,
    user_id: str = "user-1",
    roles: tuple[Literal["ADMIN", "AUDITOR"], ...] = (),
) -> SessionPrincipal:
    return SessionPrincipal(
        session_id="session-docs-redaction",
        auth_source="bearer",
        user_id=user_id,
        oidc_sub=f"oidc-{user_id}",
        email=f"{user_id}@test.local",
        display_name=user_id.title(),
        platform_roles=roles,
        issued_at=datetime.now(UTC) - timedelta(minutes=5),
        expires_at=datetime.now(UTC) + timedelta(minutes=55),
        csrf_token="csrf-redaction",
    )


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:
    yield
    app.dependency_overrides.clear()


def test_redaction_view_routes_emit_expected_audit_events() -> None:
    spy = SpyAuditService()
    fake = FakeRedactionDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: fake

    overview = client.get("/projects/project-1/documents/doc-2/privacy/overview")
    runs = client.get("/projects/project-1/documents/doc-2/redaction-runs")
    active = client.get("/projects/project-1/documents/doc-2/redaction-runs/active")
    detail = client.get("/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2")
    status_response = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/status"
    )
    review = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/review"
    )
    events = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/events"
    )
    pages = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/pages",
        params={"unresolvedOnly": "true", "directIdentifiersOnly": "true"},
    )
    findings = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/pages/page-1/findings",
        params={
            "workspaceView": "true",
            "findingId": "finding-2-1",
            "lineId": "line-1",
            "tokenId": "token-1",
        },
    )
    finding_detail = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/pages/page-1/findings/finding-2-1"
    )
    page_review = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/pages/page-1/review"
    )
    page_events = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/pages/page-1/events"
    )
    preview_status = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/pages/page-1/preview-status"
    )
    run_output = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/output"
    )
    run_output_status = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/output/status"
    )
    compare = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/compare",
        params={"baseRunId": "redaction-run-1", "candidateRunId": "redaction-run-2"},
    )

    assert overview.status_code == 200
    assert runs.status_code == 200
    assert active.status_code == 200
    assert detail.status_code == 200
    assert status_response.status_code == 200
    assert review.status_code == 200
    assert events.status_code == 200
    assert pages.status_code == 200
    assert findings.status_code == 200
    assert finding_detail.status_code == 200
    assert page_review.status_code == 200
    assert page_events.status_code == 200
    assert preview_status.status_code == 200
    assert run_output.status_code == 200
    assert run_output_status.status_code == 200
    assert compare.status_code == 200

    assert overview.json()["activeRun"]["id"] == "redaction-run-2"
    assert overview.json()["autoAppliedFindings"] == 0
    assert overview.json()["needsReviewFindings"] == 2
    assert overview.json()["overriddenFindings"] == 0
    assert status_response.json()["status"] == "SUCCEEDED"
    assert preview_status.json()["status"] == "READY"
    assert findings.json()["items"][0]["actionType"] == "MASK"
    assert finding_detail.json()["geometry"]["anchorKind"] == "TOKEN_LINKED"
    assert finding_detail.json()["geometry"]["tokenIds"] == ["token-1"]
    assert finding_detail.json()["actionType"] == "MASK"
    assert compare.json()["baseRun"]["id"] == "redaction-run-1"
    assert compare.json()["candidateRun"]["id"] == "redaction-run-2"

    event_types = {entry.get("event_type") for entry in spy.recorded}
    assert "PRIVACY_OVERVIEW_VIEWED" in event_types
    assert "PRIVACY_RUN_VIEWED" in event_types
    assert "PRIVACY_TRIAGE_VIEWED" in event_types
    assert "PRIVACY_WORKSPACE_VIEWED" in event_types
    assert "REDACTION_RUN_STATUS_VIEWED" in event_types
    assert "REDACTION_RUN_EVENTS_VIEWED" in event_types
    assert "POLICY_RUN_COMPARE_VIEWED" in event_types
    assert "SAFEGUARDED_PREVIEW_STATUS_VIEWED" in event_types
    assert "REDACTION_RUN_OUTPUT_VIEWED" in event_types
    assert "REDACTION_RUN_OUTPUT_STATUS_VIEWED" in event_types
    assert "REDACTION_FINDING_VIEWED" in event_types


def test_redaction_run_output_response_exposes_readiness_without_manifest_key() -> None:
    fake = FakeRedactionDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: fake

    response = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/output/status"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["runId"] == "redaction-run-2"
    assert payload["reviewStatus"] == "IN_REVIEW"
    assert payload["readinessState"] == "APPROVAL_REQUIRED"
    assert payload["downstreamReady"] is False
    assert "outputManifestKey" not in payload


def test_reviewed_output_routes_enforce_researcher_and_auditor_rules() -> None:
    fake = FakeRedactionDocumentService()
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: fake

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-2")
    researcher_denied = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-1/output"
    )
    assert researcher_denied.status_code == 403

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="auditor-user",
        roles=("AUDITOR",),
    )
    auditor_approved = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-1/output"
    )
    assert auditor_approved.status_code == 200
    assert auditor_approved.json()["reviewStatus"] == "APPROVED"
    assert auditor_approved.json()["readinessState"] == "OUTPUT_READY"

    auditor_unapproved = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/output"
    )
    assert auditor_unapproved.status_code == 403

def test_redaction_mutation_routes_enforce_rbac_and_locking() -> None:
    spy = SpyAuditService()
    fake = FakeRedactionDocumentService()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: fake

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-2")
    denied_create = client.post("/projects/project-1/documents/doc-2/redaction-runs")
    assert denied_create.status_code == 403

    denied_patch = client.patch(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/findings/finding-2-1",
        json={"decisionStatus": "APPROVED", "decisionEtag": "finding-2-1-v1"},
    )
    assert denied_patch.status_code == 403

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")
    create = client.post(
        "/projects/project-1/documents/doc-2/redaction-runs",
        json={"runKind": "POLICY_RERUN"},
    )
    assert create.status_code == 201

    finding_update = client.patch(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/findings/finding-2-1",
        json={"decisionStatus": "APPROVED", "decisionEtag": "finding-2-1-v1"},
    )
    assert finding_update.status_code == 200
    updated_finding = finding_update.json()
    assert updated_finding["decisionStatus"] == "APPROVED"

    now = datetime.now(UTC)
    fake._page_reviews[("redaction-run-2", "page-1")] = replace(
        fake._page_reviews[("redaction-run-2", "page-1")],
        review_status="APPROVED",
        review_etag=fake._next_etag("review-2-1"),
        updated_at=now,
    )
    fake._page_reviews[("redaction-run-2", "page-2")] = replace(
        fake._page_reviews[("redaction-run-2", "page-2")],
        review_status="APPROVED",
        review_etag=fake._next_etag("review-2-2"),
        first_reviewed_by="user-3",
        first_reviewed_at=now,
        updated_at=now,
    )
    fake._outputs[("redaction-run-2", "page-1")] = replace(
        fake._outputs[("redaction-run-2", "page-1")],
        status="READY",
        preview_sha256="preview-2-1-ready",
        generated_at=now,
        updated_at=now,
    )
    fake._outputs[("redaction-run-2", "page-2")] = replace(
        fake._outputs[("redaction-run-2", "page-2")],
        status="READY",
        preview_sha256="preview-2-2-ready",
        generated_at=now,
        updated_at=now,
    )
    fake._run_outputs["redaction-run-2"] = replace(
        fake._run_outputs["redaction-run-2"],
        status="READY",
        output_manifest_key="controlled/derived/project-1/doc-2/redaction-run-2/manifest.json",
        output_manifest_sha256="manifest-2",
        generated_at=now,
        updated_at=now,
    )

    complete_review = client.post(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/complete-review",
        json={"reviewStatus": "APPROVED"},
    )
    assert complete_review.status_code == 200

    locked_update = client.patch(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/findings/finding-2-1",
        json={
            "decisionStatus": "OVERRIDDEN",
            "decisionEtag": updated_finding["decisionEtag"],
            "reason": "post-lock change",
        },
    )
    assert locked_update.status_code == 409


def test_redaction_finding_patch_accepts_phase7_action_types() -> None:
    fake = FakeRedactionDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: fake

    accepted = client.patch(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/findings/finding-2-1",
        json={
            "decisionStatus": "APPROVED",
            "decisionEtag": "finding-2-1-v1",
            "actionType": "PSEUDONYMIZE",
        },
    )
    assert accepted.status_code == 200
    assert accepted.json()["decisionStatus"] == "APPROVED"
    assert accepted.json()["actionType"] == "PSEUDONYMIZE"


def test_redaction_finding_patch_requires_reason_for_override_statuses() -> None:
    fake = FakeRedactionDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: fake

    missing_override_reason = client.patch(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/findings/finding-2-1",
        json={
            "decisionStatus": "OVERRIDDEN",
            "decisionEtag": "finding-2-1-v1",
        },
    )
    assert missing_override_reason.status_code == 422
    missing_override_detail = str(missing_override_reason.json().get("detail"))
    assert "reason is required" in missing_override_detail

    missing_false_positive_reason = client.patch(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/findings/finding-2-1",
        json={
            "decisionStatus": "FALSE_POSITIVE",
            "decisionEtag": "finding-2-1-v1",
        },
    )
    assert missing_false_positive_reason.status_code == 422
    missing_false_positive_detail = str(missing_false_positive_reason.json().get("detail"))
    assert "reason is required" in missing_false_positive_detail


def test_redaction_dual_control_rejects_same_user_second_review() -> None:
    fake = FakeRedactionDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: fake

    finding_update = client.patch(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/findings/finding-2-1",
        json={
            "decisionStatus": "FALSE_POSITIVE",
            "decisionEtag": "finding-2-1-v1",
            "reason": "Detector disagreement resolved as false positive.",
        },
    )
    assert finding_update.status_code == 200

    review_snapshot = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/pages/page-1/review"
    )
    assert review_snapshot.status_code == 200
    assert review_snapshot.json()["requiresSecondReview"] is True
    assert review_snapshot.json()["secondReviewStatus"] == "PENDING"

    first_review = client.patch(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/pages/page-1/review",
        json={
            "reviewStatus": "APPROVED",
            "reviewEtag": review_snapshot.json()["reviewEtag"],
        },
    )
    assert first_review.status_code == 200

    same_user_second_attempt = client.patch(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/pages/page-1/review",
        json={
            "reviewStatus": "APPROVED",
            "reviewEtag": first_review.json()["reviewEtag"],
        },
    )
    assert same_user_second_attempt.status_code == 409
    assert "different reviewer" in same_user_second_attempt.json()["detail"].lower()

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-1")
    second_review = client.patch(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/pages/page-1/review",
        json={
            "reviewStatus": "APPROVED",
            "reviewEtag": first_review.json()["reviewEtag"],
        },
    )
    assert second_review.status_code == 200
    assert second_review.json()["secondReviewStatus"] == "APPROVED"
    assert second_review.json()["secondReviewedBy"] == "user-1"


def test_redaction_run_completion_gates_second_review_and_preview_readiness() -> None:
    fake = FakeRedactionDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: fake

    finding_update = client.patch(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/findings/finding-2-1",
        json={
            "decisionStatus": "FALSE_POSITIVE",
            "decisionEtag": "finding-2-1-v1",
            "reason": "Detector disagreement resolved as false positive.",
        },
    )
    assert finding_update.status_code == 200

    page1_review = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/pages/page-1/review"
    ).json()
    first_page1_approval = client.patch(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/pages/page-1/review",
        json={"reviewStatus": "APPROVED", "reviewEtag": page1_review["reviewEtag"]},
    )
    assert first_page1_approval.status_code == 200

    page2_review = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/pages/page-2/review"
    ).json()
    page2_approval = client.patch(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/pages/page-2/review",
        json={"reviewStatus": "APPROVED", "reviewEtag": page2_review["reviewEtag"]},
    )
    assert page2_approval.status_code == 200

    now = datetime.now(UTC)
    fake._outputs[("redaction-run-2", "page-1")] = replace(
        fake._outputs[("redaction-run-2", "page-1")],
        status="READY",
        preview_sha256="preview-2-1-ready",
        generated_at=now,
        updated_at=now,
    )
    fake._outputs[("redaction-run-2", "page-2")] = replace(
        fake._outputs[("redaction-run-2", "page-2")],
        status="READY",
        preview_sha256="preview-2-2-ready",
        generated_at=now,
        updated_at=now,
    )
    fake._run_outputs["redaction-run-2"] = replace(
        fake._run_outputs["redaction-run-2"],
        status="READY",
        output_manifest_key="controlled/derived/project-1/doc-2/redaction-run-2/manifest.json",
        output_manifest_sha256="manifest-2",
        generated_at=now,
        updated_at=now,
    )

    blocked_complete = client.post(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/complete-review",
        json={"reviewStatus": "APPROVED"},
    )
    assert blocked_complete.status_code == 409
    assert "second review" in blocked_complete.json()["detail"].lower()

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-1")
    latest_page1_review = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/pages/page-1/review"
    )
    assert latest_page1_review.status_code == 200
    second_review = client.patch(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/pages/page-1/review",
        json={
            "reviewStatus": "APPROVED",
            "reviewEtag": latest_page1_review.json()["reviewEtag"],
        },
    )
    assert second_review.status_code == 200

    complete_after_second_review = client.post(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/complete-review",
        json={"reviewStatus": "APPROVED"},
    )
    assert complete_after_second_review.status_code == 200
    assert complete_after_second_review.json()["reviewStatus"] == "APPROVED"
    assert complete_after_second_review.json()["approvedSnapshotSha256"] is not None
    assert complete_after_second_review.json()["lockedAt"] is not None


def test_redaction_compare_response_includes_decision_and_preview_deltas() -> None:
    fake = FakeRedactionDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: fake

    compare = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/compare",
        params={"baseRunId": "redaction-run-1", "candidateRunId": "redaction-run-2"},
    )
    assert compare.status_code == 200
    payload = compare.json()
    assert payload["items"]
    first_item = payload["items"][0]
    assert "baseDecisionCounts" in first_item
    assert "candidateDecisionCounts" in first_item
    assert "decisionStatusDeltas" in first_item
    assert "baseActionCounts" in first_item
    assert "candidateActionCounts" in first_item
    assert "actionTypeDeltas" in first_item
    assert "actionCompareState" in first_item
    assert "changedSecondReviewStatus" in first_item
    assert "previewReadyDelta" in first_item
    assert "changedActionCount" in payload
    assert "compareActionState" in payload
    assert "candidatePolicyStatus" in payload
    assert "comparisonOnlyCandidate" in payload
    assert "preActivationWarnings" in payload


def test_redaction_compare_enforces_read_only_role_matrix() -> None:
    fake = FakeRedactionDocumentService()
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: fake

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-2")
    researcher_denied = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/compare",
        params={"baseRunId": "redaction-run-1", "candidateRunId": "redaction-run-2"},
    )
    assert researcher_denied.status_code == 403

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="auditor-user",
        roles=("AUDITOR",),
    )
    auditor_allowed = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/compare",
        params={"baseRunId": "redaction-run-1", "candidateRunId": "redaction-run-2"},
    )
    assert auditor_allowed.status_code == 200


def test_policy_rerun_route_requires_project_lead_or_admin_and_records_audit_event() -> None:
    spy = SpyAuditService()
    fake = FakeRedactionDocumentService()
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: fake

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")
    reviewer_denied = client.post(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-1/rerun",
        params={"policyId": "policy-draft-v3"},
    )
    assert reviewer_denied.status_code == 403

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-1")
    lead_allowed = client.post(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-1/rerun",
        params={"policyId": "policy-draft-v3"},
    )
    assert lead_allowed.status_code == 201
    payload = lead_allowed.json()
    assert payload["runKind"] == "POLICY_RERUN"
    assert payload["supersedesRedactionRunId"] == "redaction-run-1"
    assert payload["policyId"] == "policy-draft-v3"

    event_types = [str(item.get("event_type")) for item in spy.recorded]
    assert "POLICY_RERUN_REQUESTED" in event_types


def test_compare_surfaces_comparison_only_candidate_and_pre_activation_warnings() -> None:
    fake = FakeRedactionDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-1")
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: fake

    rerun = client.post(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-1/rerun",
        params={"policyId": "policy-draft-v3"},
    )
    assert rerun.status_code == 201
    candidate_run_id = rerun.json()["id"]

    compare = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/compare",
        params={"baseRunId": "redaction-run-1", "candidateRunId": candidate_run_id},
    )
    assert compare.status_code == 200
    payload = compare.json()
    assert payload["comparisonOnlyCandidate"] is True
    assert payload["candidatePolicyStatus"] == "DRAFT"
    warning_codes = {warning["code"] for warning in payload["preActivationWarnings"]}
    assert "BROAD_ALLOW_RULE" in warning_codes
    assert "INCONSISTENT_THRESHOLD" in warning_codes


def test_policy_rerun_route_enforces_source_review_and_policy_validation_gates() -> None:
    fake = FakeRedactionDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-1")
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: fake

    fake._run_reviews["redaction-run-1"] = replace(
        fake._run_reviews["redaction-run-1"],
        review_status="IN_REVIEW",
    )
    blocked_review = client.post(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-1/rerun",
        params={"policyId": "policy-draft-v3"},
    )
    assert blocked_review.status_code == 409

    fake._run_reviews["redaction-run-1"] = replace(
        fake._run_reviews["redaction-run-1"],
        review_status="APPROVED",
    )
    fake._policy_catalog["policy-draft-v3"]["validation_status"] = "INVALID"
    blocked_policy = client.post(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-1/rerun",
        params={"policyId": "policy-draft-v3"},
    )
    assert blocked_policy.status_code == 409

    fake._policy_catalog["policy-draft-v3"]["validation_status"] = "VALID"
    fake._governance_ready_runs.discard("redaction-run-1")
    blocked_governance = client.post(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-1/rerun",
        params={"policyId": "policy-draft-v3"},
    )
    assert blocked_governance.status_code == 409
    assert "governance-ready" in blocked_governance.json()["detail"]


def test_approved_run_rejects_page_review_and_area_mask_mutations() -> None:
    fake = FakeRedactionDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: fake

    page_review_patch = client.patch(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-1/pages/page-1/review",
        json={"reviewStatus": "APPROVED", "reviewEtag": "review-1-1-v1"},
    )
    assert page_review_patch.status_code == 409

    mask_create = client.post(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-1/pages/page-1/area-masks",
        json={
            "geometryJson": {"bbox": [10, 10, 40, 40]},
            "maskReason": "Should fail because run is approved.",
        },
    )
    assert mask_create.status_code == 409


def test_redaction_preview_route_supports_etag_revalidation() -> None:
    spy = SpyAuditService()
    fake = FakeRedactionDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-1")
    app.dependency_overrides[get_audit_service] = lambda: spy
    app.dependency_overrides[get_document_service] = lambda: fake

    preview = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-1/pages/page-1/preview"
    )
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"
    assert preview.headers["cache-control"] == "private, no-cache, max-age=0, must-revalidate"
    assert preview.headers["etag"] == '"preview-1-1"'
    assert preview.content == b"fixture-redaction-preview"

    revalidated = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-1/pages/page-1/preview",
        headers={"If-None-Match": preview.headers["etag"]},
    )
    assert revalidated.status_code == 304
    assert revalidated.content == b""

    pending_preview = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/pages/page-2/preview"
    )
    assert pending_preview.status_code == 409

    event_types = {entry.get("event_type") for entry in spy.recorded}
    assert "SAFEGUARDED_PREVIEW_ACCESSED" in event_types
    assert "SAFEGUARDED_PREVIEW_VIEWED" in event_types


def test_redaction_activation_and_area_mask_revision_routes() -> None:
    fake = FakeRedactionDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-3")
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[get_document_service] = lambda: fake

    blocked_activation = client.post(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/activate"
    )
    assert blocked_activation.status_code == 409

    allowed_activation = client.post(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-1/activate"
    )
    assert allowed_activation.status_code == 200
    assert allowed_activation.json()["projection"]["activeRedactionRunId"] == "redaction-run-1"

    mask_create = client.post(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/pages/page-2/area-masks",
        json={
            "geometryJson": {"bbox": [38, 98, 232, 150]},
            "maskReason": "Unreadable surname near margin",
            "findingId": "finding-2-2",
            "findingDecisionEtag": "finding-2-2-v1",
        },
    )
    assert mask_create.status_code == 201
    created_payload = mask_create.json()
    created_mask_id = created_payload["areaMask"]["id"]
    created_mask_etag = created_payload["areaMask"]["versionEtag"]
    assert created_payload["finding"]["decisionStatus"] == "OVERRIDDEN"
    assert created_payload["finding"]["areaMaskId"] == created_mask_id

    mask_patch = client.patch(
        f"/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/area-masks/{created_mask_id}",
        json={
            "versionEtag": created_mask_etag,
            "geometryJson": {"bbox": [42, 102, 222, 142]},
            "maskReason": "Adjusted mask extent",
            "findingId": "finding-2-2",
            "findingDecisionEtag": created_payload["finding"]["decisionEtag"],
        },
    )
    assert mask_patch.status_code == 200
    payload = mask_patch.json()
    assert payload["areaMask"]["id"] != created_mask_id
    assert payload["areaMask"]["supersedesAreaMaskId"] == created_mask_id
    assert payload["finding"]["decisionStatus"] == "OVERRIDDEN"
    assert payload["finding"]["activeAreaMask"]["id"] == payload["areaMask"]["id"]

    events = client.get(
        "/projects/project-1/documents/doc-2/redaction-runs/redaction-run-2/pages/page-2/events"
    )
    assert events.status_code == 200
    decision_entries = [
        entry for entry in events.json()["items"] if entry["sourceTable"] == "redaction_decision_events"
    ]
    assert decision_entries
    assert all(entry["detailsJson"].get("actionType") == "MASK" for entry in decision_entries)
    assert any(entry["detailsJson"].get("areaMaskId") for entry in decision_entries)
