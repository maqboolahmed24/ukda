from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Literal

import pytest
from app.audit.service import get_audit_service
from app.auth.dependencies import (
    require_authenticated_user,
    require_internal_export_gateway_service_account,
)
from app.auth.models import SessionPrincipal
from app.exports.deposit_profiles import (
    build_bundle_profile_snapshot,
    bundle_profile_snapshot_sha256,
    get_bundle_profile,
    list_bundle_profiles,
    validate_bundle_artifact_against_profile,
)
from app.exports.models import (
    BundleEventRecord,
    BundleProfileRecord,
    BundleValidationProjectionRecord,
    BundleValidationRunRecord,
    BundleVerificationProjectionRecord,
    BundleVerificationRunRecord,
    DepositBundleRecord,
    ExportCandidateSnapshotRecord,
    ExportReceiptRecord,
    ProvenanceProofRecord,
    ExportRequestEventRecord,
    ExportRequestListPage,
    ExportRequestRecord,
    ExportRequestReviewEventRecord,
    ExportRequestReviewRecord,
    ExportReviewQueueItemRecord,
)
from app.exports.service import (
    ExportAccessDeniedError,
    ExportConflictError,
    ExportNotFoundError,
    get_export_service,
)
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


class SpyAuditService:
    def __init__(self) -> None:
        self.recorded: list[dict[str, object]] = []

    def record_event_best_effort(self, **kwargs):  # type: ignore[no-untyped-def]
        self.recorded.append(kwargs)
        return None


class FakeExportService:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.candidate = ExportCandidateSnapshotRecord(
            id="candidate-1",
            project_id="project-1",
            source_phase="PHASE6",
            source_artifact_kind="REDACTION_RUN_OUTPUT",
            source_run_id="run-1",
            source_artifact_id="run-1",
            governance_run_id="run-1",
            governance_manifest_id="manifest-1",
            governance_ledger_id="ledger-1",
            governance_manifest_sha256="a" * 64,
            governance_ledger_sha256="b" * 64,
            policy_snapshot_hash="c" * 64,
            policy_id="policy-1",
            policy_family_id="family-1",
            policy_version="1",
            candidate_kind="SAFEGUARDED_PREVIEW",
            artefact_manifest_json={
                "fileList": [
                    {
                        "fileName": "output-manifest.json",
                        "sha256": "d" * 64,
                        "fileSizeBytes": 5,
                    }
                ]
            },
            candidate_sha256="e" * 64,
            eligibility_status="ELIGIBLE",
            supersedes_candidate_snapshot_id=None,
            superseded_by_candidate_snapshot_id=None,
            created_by="user-1",
            created_at=now,
        )
        self.requests: dict[str, ExportRequestRecord] = {
            "request-1": ExportRequestRecord(
                id="request-1",
                project_id="project-1",
                candidate_snapshot_id="candidate-1",
                candidate_origin_phase="PHASE6",
                candidate_kind="SAFEGUARDED_PREVIEW",
                bundle_profile=None,
                risk_classification="STANDARD",
                risk_reason_codes_json=(),
                review_path="SINGLE",
                requires_second_review=False,
                supersedes_export_request_id=None,
                superseded_by_export_request_id=None,
                request_revision=1,
                purpose_statement="Request surface tests for export routes.",
                status="SUBMITTED",
                submitted_by="researcher-1",
                submitted_at=now,
                first_review_started_by=None,
                first_review_started_at=None,
                sla_due_at=now + timedelta(hours=72),
                last_queue_activity_at=now,
                retention_until=None,
                final_review_id=None,
                final_decision_by=None,
                final_decision_at=None,
                final_decision_reason=None,
                final_return_comment=None,
                release_pack_key="exports/requests/request-1/release-pack/test.json",
                release_pack_sha256="f" * 64,
                release_pack_json={
                    "schemaVersion": 1,
                    "requestScope": "REQUEST_FROZEN",
                    "candidateSnapshotId": "candidate-1",
                },
                release_pack_created_at=now,
                receipt_id=None,
                receipt_key=None,
                receipt_sha256=None,
                receipt_created_by=None,
                receipt_created_at=None,
                exported_at=None,
                created_at=now,
                updated_at=now,
            )
        }
        self.request_events: dict[str, list[ExportRequestEventRecord]] = {
            "request-1": [
                ExportRequestEventRecord(
                    id="event-1",
                    export_request_id="request-1",
                    event_type="REQUEST_SUBMITTED",
                    from_status=None,
                    to_status="SUBMITTED",
                    actor_user_id="researcher-1",
                    reason=None,
                    created_at=now,
                )
            ]
        }
        self.request_reviews: dict[str, list[ExportRequestReviewRecord]] = {
            "request-1": [
                ExportRequestReviewRecord(
                    id="review-1",
                    export_request_id="request-1",
                    review_stage="PRIMARY",
                    is_required=True,
                    status="PENDING",
                    assigned_reviewer_user_id=None,
                    assigned_at=None,
                    acted_by_user_id=None,
                    acted_at=None,
                    decision_reason=None,
                    return_comment=None,
                    review_etag="review-etag-1",
                    created_at=now,
                    updated_at=now,
                )
            ]
        }
        self.request_review_events: dict[str, list[ExportRequestReviewEventRecord]] = {
            "request-1": [
                ExportRequestReviewEventRecord(
                    id="review-event-1",
                    review_id="review-1",
                    export_request_id="request-1",
                    review_stage="PRIMARY",
                    event_type="REVIEW_CREATED",
                    actor_user_id="researcher-1",
                    assigned_reviewer_user_id=None,
                    decision_reason=None,
                    return_comment=None,
                    created_at=now,
                )
            ]
        }
        self.receipts: dict[str, list[ExportReceiptRecord]] = {}
        self.provenance_proofs: dict[str, list[ProvenanceProofRecord]] = {}
        self.provenance_artifacts: dict[str, dict[str, object]] = {}
        self.deposit_bundles: dict[str, list[DepositBundleRecord]] = {}
        self.bundle_events: dict[str, list[BundleEventRecord]] = {}
        self.bundle_artifacts: dict[str, dict[str, object]] = {}
        self.bundle_verification: dict[str, BundleVerificationProjectionRecord] = {}
        self.bundle_verification_runs: dict[str, list[BundleVerificationRunRecord]] = {}
        self.bundle_validation_projections: dict[
            tuple[str, str], BundleValidationProjectionRecord
        ] = {}
        self.bundle_validation_runs: dict[tuple[str, str], list[BundleValidationRunRecord]] = {}
        self.bundle_profiles: tuple[BundleProfileRecord, ...] = list_bundle_profiles()
        self.raise_access_denied = False

    def _maybe_raise(self) -> None:
        if self.raise_access_denied:
            raise ExportAccessDeniedError("Current role cannot access this export route.")

    @staticmethod
    def _can_mutate_review(kwargs) -> bool:  # type: ignore[no-untyped-def]
        current_user = kwargs.get("current_user")
        if not isinstance(current_user, SessionPrincipal):
            return False
        roles = set(current_user.platform_roles)
        if "ADMIN" in roles:
            return True
        return current_user.user_id.startswith("reviewer-")

    def list_export_candidates(self, **kwargs) -> tuple[ExportCandidateSnapshotRecord, ...]:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        _ = kwargs
        return (self.candidate,)

    def get_export_candidate(self, **kwargs) -> ExportCandidateSnapshotRecord:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        _ = kwargs
        return self.candidate

    def get_candidate_release_pack_preview(self, **kwargs) -> dict[str, object]:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        _ = kwargs
        return {
            "candidate": self.candidate,
            "releasePack": {"schemaVersion": 1, "files": [], "riskClassification": "STANDARD"},
            "releasePackSha256": "g" * 64,
            "releasePackKey": "exports/candidates/candidate-1/release-pack-preview/1/preview.json",
            "riskClassification": "STANDARD",
            "riskReasonCodes": (),
            "reviewPath": "SINGLE",
            "requiresSecondReview": False,
        }

    def create_export_request(self, **kwargs) -> ExportRequestRecord:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        now = datetime.now(UTC)
        _ = kwargs
        record = self.requests["request-1"]
        return replace_request(
            record,
            id="request-2",
            status="SUBMITTED",
            request_revision=1,
            submitted_at=now,
            created_at=now,
            updated_at=now,
        )

    def resubmit_export_request(self, **kwargs) -> ExportRequestRecord:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        now = datetime.now(UTC)
        _ = kwargs
        record = self.requests["request-1"]
        return replace_request(
            record,
            id="request-3",
            status="RESUBMITTED",
            request_revision=2,
            supersedes_export_request_id="request-1",
            submitted_at=now,
            created_at=now,
            updated_at=now,
        )

    def list_export_requests(self, **kwargs) -> ExportRequestListPage:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        _ = kwargs
        return ExportRequestListPage(items=tuple(self.requests.values()), next_cursor=None)

    def get_export_request(self, **kwargs) -> ExportRequestRecord:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        request_id = str(kwargs["export_request_id"])
        return self.requests[request_id]

    def get_export_request_status(self, **kwargs) -> dict[str, object]:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        _ = kwargs
        record = self.requests["request-1"]
        return {
            "id": record.id,
            "status": record.status,
            "riskClassification": record.risk_classification,
            "reviewPath": record.review_path,
            "requiresSecondReview": record.requires_second_review,
            "requestRevision": record.request_revision,
            "submittedAt": record.submitted_at,
            "lastQueueActivityAt": None,
            "slaDueAt": None,
            "retentionUntil": None,
            "finalDecisionAt": None,
            "finalDecisionBy": None,
            "finalDecisionReason": None,
            "finalReturnComment": None,
            "exportedAt": None,
        }

    def get_export_request_release_pack(self, **kwargs) -> dict[str, object]:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        _ = kwargs
        record = self.requests["request-1"]
        return {
            "requestId": record.id,
            "requestRevision": record.request_revision,
            "releasePack": record.release_pack_json,
            "releasePackSha256": record.release_pack_sha256,
            "releasePackKey": record.release_pack_key,
            "releasePackCreatedAt": record.release_pack_created_at,
        }

    def get_export_request_validation_summary(self, **kwargs) -> dict[str, object]:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        _ = kwargs
        record = self.requests["request-1"]
        return {
            "requestId": record.id,
            "projectId": record.project_id,
            "requestStatus": record.status,
            "requestRevision": record.request_revision,
            "generatedAt": datetime.now(UTC).isoformat(),
            "isValid": True,
            "releasePack": {
                "checkId": "release_pack",
                "passed": True,
                "issueCount": 0,
                "issues": [],
                "facts": {
                    "computedPayloadSha256": record.release_pack_sha256,
                    "storedPayloadSha256": record.release_pack_sha256,
                },
            },
            "auditCompleteness": {
                "checkId": "audit_completeness",
                "passed": True,
                "issueCount": 0,
                "issues": [],
                "facts": {
                    "requestEventCount": len(self.request_events["request-1"]),
                    "reviewCount": len(self.request_reviews["request-1"]),
                    "reviewEventCount": len(self.request_review_events["request-1"]),
                    "receiptCount": len(self.receipts.get("request-1", [])),
                },
            },
        }

    def get_export_request_events(self, **kwargs) -> tuple[ExportRequestEventRecord, ...]:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        request_id = str(kwargs["export_request_id"])
        return tuple(self.request_events[request_id])

    def get_export_request_reviews(self, **kwargs) -> tuple[ExportRequestReviewRecord, ...]:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        request_id = str(kwargs["export_request_id"])
        return tuple(self.request_reviews[request_id])

    def get_export_request_review_events(  # type: ignore[no-untyped-def]
        self, **kwargs
    ) -> tuple[ExportRequestReviewEventRecord, ...]:
        self._maybe_raise()
        request_id = str(kwargs["export_request_id"])
        return tuple(self.request_review_events[request_id])

    def get_export_request_receipt(self, **kwargs) -> ExportReceiptRecord:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        request_id = str(kwargs["export_request_id"])
        receipts = self.receipts.get(request_id, [])
        if not receipts:
            raise ExportNotFoundError("Export request has no attached receipt.")
        request = self.requests[request_id]
        if request.receipt_id is None:
            raise ExportNotFoundError("Export request has no attached receipt.")
        match = next((item for item in receipts if item.id == request.receipt_id), None)
        if match is None:
            raise ExportNotFoundError("Export request receipt lineage is unavailable.")
        return match

    def list_export_request_receipts(self, **kwargs) -> tuple[ExportReceiptRecord, ...]:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        request_id = str(kwargs["export_request_id"])
        return tuple(self.receipts.get(request_id, []))

    def _ensure_provenance_proof(self, *, request_id: str, actor_user_id: str) -> ProvenanceProofRecord:
        history = self.provenance_proofs.get(request_id, [])
        current = next((item for item in history if item.superseded_by_proof_id is None), None)
        if current is not None:
            return current
        request = self.requests[request_id]
        now = datetime.now(UTC)
        attempt_number = 1
        proof_id = f"{request_id}-proof-{attempt_number}"
        root_sha = hashlib.sha256(
            f"{request.candidate_snapshot_id}|{request.release_pack_sha256}|{attempt_number}".encode(
                "utf-8"
            )
        ).hexdigest()
        proof = ProvenanceProofRecord(
            id=proof_id,
            project_id=request.project_id,
            export_request_id=request_id,
            candidate_snapshot_id=request.candidate_snapshot_id,
            attempt_number=attempt_number,
            supersedes_proof_id=None,
            superseded_by_proof_id=None,
            root_sha256=root_sha,
            signature_key_ref="ukde-provenance-lamport-v1",
            signature_bytes_key=(
                f"controlled/derived/provenance/{request.project_id}/export-requests/{request_id}/"
                f"proofs/{proof_id}/signature.bin"
            ),
            proof_artifact_key=(
                f"controlled/derived/provenance/{request.project_id}/export-requests/{request_id}/"
                f"proofs/{proof_id}/proof.json"
            ),
            proof_artifact_sha256="f" * 64,
            created_by=actor_user_id,
            created_at=now,
        )
        self.provenance_proofs[request_id] = [proof]
        self.provenance_artifacts[proof_id] = {
            "schemaVersion": 1,
            "proofId": proof_id,
            "projectId": request.project_id,
            "exportRequestId": request_id,
            "candidateSnapshotId": request.candidate_snapshot_id,
            "attemptNumber": attempt_number,
            "leaves": [
                {
                    "artifact_kind": "EXPORT_REQUEST",
                    "stable_identifier": request_id,
                    "immutable_reference": request.release_pack_sha256,
                    "parent_references": [],
                }
            ],
            "merkle": {
                "algorithm": "SHA-256",
                "leafCount": 1,
                "rootSha256": root_sha,
            },
            "signature": {
                "algorithm": "LAMPORT_SHA256_OTS_V1",
                "keyRef": "ukde-provenance-lamport-v1",
                "signatureBase64": "",
            },
            "verificationMaterial": {
                "publicKeyAlgorithm": "LAMPORT_SHA256_OTS_V1",
                "publicKeyBase64": "",
                "publicKeySha256": hashlib.sha256(proof_id.encode("utf-8")).hexdigest(),
                "rootHashAlgorithm": "SHA-256",
            },
        }
        return proof

    def get_export_request_provenance_summary(self, **kwargs) -> dict[str, object]:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        request_id = str(kwargs["export_request_id"])
        current_user = kwargs["current_user"]
        request = self.requests[request_id]
        if request.status not in {"APPROVED", "EXPORTED"}:
            raise ExportAccessDeniedError(
                "Provenance is available only for APPROVED or EXPORTED request lineages."
            )
        proof = self._ensure_provenance_proof(
            request_id=request_id,
            actor_user_id=current_user.user_id,
        )
        artifact = self.provenance_artifacts[proof.id]
        candidate = self.candidate
        return {
            "projectId": request.project_id,
            "requestId": request.id,
            "requestStatus": request.status,
            "candidateSnapshotId": request.candidate_snapshot_id,
            "proofAttemptCount": len(self.provenance_proofs.get(request_id, [])),
            "currentProofId": proof.id,
            "currentAttemptNumber": proof.attempt_number,
            "currentProofGeneratedAt": proof.created_at.isoformat(),
            "rootSha256": proof.root_sha256,
            "signatureKeyRef": proof.signature_key_ref,
            "signatureStatus": "SIGNED",
            "lineageNodes": [
                {
                    "artifactKind": str(row.get("artifact_kind")),
                    "stableIdentifier": str(row.get("stable_identifier")),
                    "immutableReference": str(row.get("immutable_reference")),
                    "parentReferences": list(row.get("parent_references") or []),
                }
                for row in artifact.get("leaves", [])
                if isinstance(row, dict)
            ],
            "references": {
                "manifestId": candidate.governance_manifest_id,
                "ledgerId": candidate.governance_ledger_id,
                "policySnapshotHash": candidate.policy_snapshot_hash,
                "policyId": candidate.policy_id,
                "policyVersion": candidate.policy_version,
                "exportApprovalReviewId": request.final_review_id,
                "exportApprovalActorUserId": request.final_decision_by,
                "exportApprovalAt": (
                    request.final_decision_at.isoformat()
                    if request.final_decision_at is not None
                    else None
                ),
                "modelReferencesByRole": (
                    candidate.artefact_manifest_json.get("approvedModelReferencesByRole")
                    if isinstance(
                        candidate.artefact_manifest_json.get("approvedModelReferencesByRole"),
                        dict,
                    )
                    else {}
                ),
            },
        }

    def list_export_request_provenance_proofs(self, **kwargs) -> tuple[ProvenanceProofRecord, ...]:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        request_id = str(kwargs["export_request_id"])
        current_user = kwargs["current_user"]
        request = self.requests[request_id]
        if request.status not in {"APPROVED", "EXPORTED"}:
            raise ExportAccessDeniedError(
                "Provenance is available only for APPROVED or EXPORTED request lineages."
            )
        self._ensure_provenance_proof(
            request_id=request_id,
            actor_user_id=current_user.user_id,
        )
        return tuple(self.provenance_proofs.get(request_id, []))

    def get_export_request_current_provenance_proof(self, **kwargs) -> dict[str, object]:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        request_id = str(kwargs["export_request_id"])
        current_user = kwargs["current_user"]
        request = self.requests[request_id]
        if request.status not in {"APPROVED", "EXPORTED"}:
            raise ExportAccessDeniedError(
                "Provenance is available only for APPROVED or EXPORTED request lineages."
            )
        proof = self._ensure_provenance_proof(
            request_id=request_id,
            actor_user_id=current_user.user_id,
        )
        return {"proof": proof, "artifact": dict(self.provenance_artifacts[proof.id])}

    def get_export_request_provenance_proof(self, **kwargs) -> dict[str, object]:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        request_id = str(kwargs["export_request_id"])
        proof_id = str(kwargs["proof_id"])
        request = self.requests[request_id]
        if request.status not in {"APPROVED", "EXPORTED"}:
            raise ExportAccessDeniedError(
                "Provenance is available only for APPROVED or EXPORTED request lineages."
            )
        proof = next(
            (
                item
                for item in self.provenance_proofs.get(request_id, [])
                if item.id == proof_id
            ),
            None,
        )
        if proof is None:
            raise ExportNotFoundError("Provenance proof not found.")
        return {"proof": proof, "artifact": dict(self.provenance_artifacts[proof.id])}

    def regenerate_export_request_provenance_proof(self, **kwargs) -> ProvenanceProofRecord:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        request_id = str(kwargs["export_request_id"])
        current_user = kwargs["current_user"]
        if "ADMIN" not in set(current_user.platform_roles):
            raise ExportAccessDeniedError("Only ADMIN can regenerate provenance proofs.")
        request = self.requests[request_id]
        if request.status not in {"APPROVED", "EXPORTED"}:
            raise ExportAccessDeniedError(
                "Provenance is available only for APPROVED or EXPORTED request lineages."
            )
        history = list(self.provenance_proofs.get(request_id, []))
        current = next((item for item in history if item.superseded_by_proof_id is None), None)
        if current is None:
            return self._ensure_provenance_proof(
                request_id=request_id,
                actor_user_id=current_user.user_id,
            )
        attempt_number = current.attempt_number + 1
        now = datetime.now(UTC)
        proof_id = f"{request_id}-proof-{attempt_number}"
        root_sha = hashlib.sha256(
            f"{request.candidate_snapshot_id}|{request.release_pack_sha256}|{attempt_number}".encode(
                "utf-8"
            )
        ).hexdigest()
        regenerated = ProvenanceProofRecord(
            id=proof_id,
            project_id=request.project_id,
            export_request_id=request_id,
            candidate_snapshot_id=request.candidate_snapshot_id,
            attempt_number=attempt_number,
            supersedes_proof_id=current.id,
            superseded_by_proof_id=None,
            root_sha256=root_sha,
            signature_key_ref="ukde-provenance-lamport-v1",
            signature_bytes_key=(
                f"controlled/derived/provenance/{request.project_id}/export-requests/{request_id}/"
                f"proofs/{proof_id}/signature.bin"
            ),
            proof_artifact_key=(
                f"controlled/derived/provenance/{request.project_id}/export-requests/{request_id}/"
                f"proofs/{proof_id}/proof.json"
            ),
            proof_artifact_sha256="f" * 64,
            created_by=current_user.user_id,
            created_at=now,
        )
        history = [
            replace_proof(item, superseded_by_proof_id=proof_id) if item.id == current.id else item
            for item in history
        ]
        history.insert(0, regenerated)
        self.provenance_proofs[request_id] = history
        self.provenance_artifacts[proof_id] = {
            "schemaVersion": 1,
            "proofId": proof_id,
            "projectId": request.project_id,
            "exportRequestId": request_id,
            "candidateSnapshotId": request.candidate_snapshot_id,
            "attemptNumber": attempt_number,
            "leaves": [
                {
                    "artifact_kind": "EXPORT_REQUEST",
                    "stable_identifier": request_id,
                    "immutable_reference": request.release_pack_sha256,
                    "parent_references": [],
                }
            ],
            "merkle": {
                "algorithm": "SHA-256",
                "leafCount": 1,
                "rootSha256": root_sha,
            },
            "signature": {
                "algorithm": "LAMPORT_SHA256_OTS_V1",
                "keyRef": "ukde-provenance-lamport-v1",
                "signatureBase64": "",
            },
            "verificationMaterial": {
                "publicKeyAlgorithm": "LAMPORT_SHA256_OTS_V1",
                "publicKeyBase64": "",
                "publicKeySha256": hashlib.sha256(proof_id.encode("utf-8")).hexdigest(),
                "rootHashAlgorithm": "SHA-256",
            },
        }
        return regenerated

    @staticmethod
    def _bundle_key(*, project_id: str, export_request_id: str, bundle_id: str, kind: str) -> str:
        suffix = (
            "controlled_evidence_bundle.zip"
            if kind == "CONTROLLED_EVIDENCE"
            else "safeguarded_deposit_bundle.zip"
        )
        return (
            f"controlled/derived/provenance/{project_id}/export-requests/{export_request_id}/"
            f"bundles/{bundle_id}/{suffix}"
        )

    def _is_admin(self, current_user: SessionPrincipal) -> bool:
        return "ADMIN" in set(current_user.platform_roles)

    def _is_auditor(self, current_user: SessionPrincipal) -> bool:
        return "AUDITOR" in set(current_user.platform_roles)

    def _is_reviewer_or_lead(self, current_user: SessionPrincipal) -> bool:
        return current_user.user_id.startswith("reviewer-") or current_user.user_id.startswith(
            "project-lead-"
        )

    def list_export_request_bundles(self, **kwargs) -> tuple[DepositBundleRecord, ...]:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        request_id = str(kwargs["export_request_id"])
        current_user = kwargs["current_user"]
        request = self.requests[request_id]
        if request.status not in {"APPROVED", "EXPORTED"}:
            raise ExportAccessDeniedError(
                "Deposit bundles are available only for APPROVED or EXPORTED request lineages."
            )
        items = list(self.deposit_bundles.get(request_id, []))
        if self._is_admin(current_user) or self._is_auditor(current_user):
            return tuple(items)
        return tuple(item for item in items if item.bundle_kind == "SAFEGUARDED_DEPOSIT")

    def create_export_request_bundle(self, **kwargs) -> DepositBundleRecord:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        request_id = str(kwargs["export_request_id"])
        kind = str(kwargs["bundle_kind"]).strip().upper()
        current_user = kwargs["current_user"]
        request = self.requests[request_id]
        if request.status not in {"APPROVED", "EXPORTED"}:
            raise ExportAccessDeniedError(
                "Deposit bundles are available only for APPROVED or EXPORTED request lineages."
            )
        if kind == "CONTROLLED_EVIDENCE":
            if not self._is_admin(current_user):
                raise ExportAccessDeniedError(
                    "Only ADMIN can build controlled evidence deposit bundles."
                )
        elif kind == "SAFEGUARDED_DEPOSIT":
            if not (self._is_admin(current_user) or self._is_reviewer_or_lead(current_user)):
                raise ExportAccessDeniedError(
                    "Only PROJECT_LEAD, REVIEWER, or ADMIN can build safeguarded deposit bundles."
                )
        else:
            raise ExportAccessDeniedError("bundleKind is invalid.")

        history = list(self.deposit_bundles.get(request_id, []))
        current = next(
            (
                item
                for item in history
                if item.bundle_kind == kind
                and item.candidate_snapshot_id == request.candidate_snapshot_id
                and item.superseded_by_bundle_id is None
            ),
            None,
        )
        if current is not None:
            return current

        same_lineage = [
            item
            for item in history
            if item.bundle_kind == kind and item.candidate_snapshot_id == request.candidate_snapshot_id
        ]
        attempt_number = max((item.attempt_number for item in same_lineage), default=0) + 1
        now = datetime.now(UTC)
        bundle_id = f"{request_id}-{kind.lower()}-{attempt_number}"
        proof = self._ensure_provenance_proof(request_id=request_id, actor_user_id=current_user.user_id)
        proof_artifact = self.provenance_artifacts[proof.id]
        artifact = {
            "archiveEntries": [
                "bundle/metadata.json",
                "bundle/provenance-proof.json",
                "bundle/provenance-signature.json",
                "bundle/provenance-verification-material.json",
            ],
            "metadata": {
                "bundleId": bundle_id,
                "bundleKind": kind,
                "bundleAttemptNumber": attempt_number,
                "exportRequest": {
                    "id": request.id,
                    "finalReviewId": request.final_review_id,
                },
                "candidateSnapshot": {
                    "id": request.candidate_snapshot_id,
                },
                "metadata": {"releasePackSha256": request.release_pack_sha256},
                "provenanceProof": {
                    "proofId": proof.id,
                    "rootSha256": proof.root_sha256,
                    "proofArtifactSha256": proof.proof_artifact_sha256,
                },
                "exportReceiptMetadata": (
                    {"receiptId": request.receipt_id, "receiptSha256": request.receipt_sha256}
                    if request.receipt_id is not None
                    else None
                ),
            },
            "provenanceProofArtifact": proof_artifact,
            "provenanceSignature": (
                dict(proof_artifact.get("signature"))
                if isinstance(proof_artifact.get("signature"), dict)
                else {}
            ),
            "provenanceVerificationMaterial": (
                dict(proof_artifact.get("verificationMaterial"))
                if isinstance(proof_artifact.get("verificationMaterial"), dict)
                else {}
            ),
        }
        bundle_sha = hashlib.sha256(str(artifact).encode("utf-8")).hexdigest()
        bundle = DepositBundleRecord(
            id=bundle_id,
            project_id=request.project_id,
            export_request_id=request_id,
            candidate_snapshot_id=request.candidate_snapshot_id,
            provenance_proof_id=proof.id,
            provenance_proof_artifact_sha256=proof.proof_artifact_sha256,
            bundle_kind=kind,  # type: ignore[arg-type]
            status="SUCCEEDED",
            attempt_number=attempt_number,
            supersedes_bundle_id=None,
            superseded_by_bundle_id=None,
            bundle_key=self._bundle_key(
                project_id=request.project_id,
                export_request_id=request_id,
                bundle_id=bundle_id,
                kind=kind,
            ),
            bundle_sha256=bundle_sha,
            failure_reason=None,
            created_by=current_user.user_id,
            created_at=now,
            started_at=now,
            finished_at=now,
            canceled_by=None,
            canceled_at=None,
        )
        history.insert(0, bundle)
        self.deposit_bundles[request_id] = history
        self.bundle_artifacts[bundle.id] = artifact
        self.bundle_verification[bundle.id] = BundleVerificationProjectionRecord(
            bundle_id=bundle.id,
            status="PENDING",
            last_verification_run_id=None,
            verified_at=None,
            updated_at=now,
        )
        self.bundle_events[bundle.id] = [
            BundleEventRecord(
                id=f"{bundle.id}-queued",
                bundle_id=bundle.id,
                event_type="BUNDLE_BUILD_QUEUED",
                verification_run_id=None,
                validation_run_id=None,
                actor_user_id=current_user.user_id,
                reason=None,
                created_at=now,
            ),
            BundleEventRecord(
                id=f"{bundle.id}-started",
                bundle_id=bundle.id,
                event_type="BUNDLE_BUILD_STARTED",
                verification_run_id=None,
                validation_run_id=None,
                actor_user_id=current_user.user_id,
                reason=None,
                created_at=now + timedelta(microseconds=1),
            ),
            BundleEventRecord(
                id=f"{bundle.id}-succeeded",
                bundle_id=bundle.id,
                event_type="BUNDLE_BUILD_SUCCEEDED",
                verification_run_id=None,
                validation_run_id=None,
                actor_user_id=current_user.user_id,
                reason=f"bundle_sha256:{bundle_sha}",
                created_at=now + timedelta(microseconds=2),
            ),
        ]
        return bundle

    def get_export_request_bundle(self, **kwargs) -> dict[str, object]:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        request_id = str(kwargs["export_request_id"])
        bundle_id = str(kwargs["bundle_id"])
        current_user = kwargs["current_user"]
        request = self.requests[request_id]
        bundle = next(
            (item for item in self.deposit_bundles.get(request_id, []) if item.id == bundle_id),
            None,
        )
        if bundle is None:
            raise ExportNotFoundError("Deposit bundle not found.")
        if bundle.bundle_kind == "CONTROLLED_EVIDENCE" and not (
            self._is_admin(current_user) or self._is_auditor(current_user)
        ):
            raise ExportAccessDeniedError(
                "Controlled evidence bundles are limited to ADMIN and AUDITOR."
            )
        if request.status not in {"APPROVED", "EXPORTED"}:
            raise ExportAccessDeniedError(
                "Deposit bundles are available only for APPROVED or EXPORTED request lineages."
            )
        attempts = [
            item
            for item in self.deposit_bundles.get(request_id, [])
            if item.bundle_kind == bundle.bundle_kind
            and item.candidate_snapshot_id == bundle.candidate_snapshot_id
        ]
        return {
            "bundle": bundle,
            "lineageAttempts": tuple(attempts),
            "verificationProjection": self.bundle_verification.get(bundle.id),
            "artifact": dict(self.bundle_artifacts.get(bundle.id, {})),
        }

    def get_export_request_bundle_status(self, **kwargs) -> dict[str, object]:  # type: ignore[no-untyped-def]
        detail = self.get_export_request_bundle(**kwargs)
        return {
            "bundle": detail["bundle"],
            "verificationProjection": detail["verificationProjection"],
        }

    def list_export_request_bundle_events(self, **kwargs) -> tuple[BundleEventRecord, ...]:  # type: ignore[no-untyped-def]
        detail = self.get_export_request_bundle(**kwargs)
        bundle = detail["bundle"]
        if not isinstance(bundle, DepositBundleRecord):
            raise ExportNotFoundError("Deposit bundle not found.")
        events = sorted(
            self.bundle_events.get(bundle.id, []),
            key=lambda item: (item.created_at, item.id),
        )
        return tuple(events)

    def cancel_export_request_bundle(self, **kwargs) -> DepositBundleRecord:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        request_id = str(kwargs["export_request_id"])
        bundle_id = str(kwargs["bundle_id"])
        current_user = kwargs["current_user"]
        bundle = next(
            (item for item in self.deposit_bundles.get(request_id, []) if item.id == bundle_id),
            None,
        )
        if bundle is None:
            raise ExportNotFoundError("Deposit bundle not found.")
        if bundle.bundle_kind == "CONTROLLED_EVIDENCE":
            if not self._is_admin(current_user):
                raise ExportAccessDeniedError(
                    "Only ADMIN can mutate controlled evidence deposit bundles."
                )
        elif not (self._is_admin(current_user) or self._is_reviewer_or_lead(current_user)):
            raise ExportAccessDeniedError(
                "Only PROJECT_LEAD, REVIEWER, or ADMIN can mutate safeguarded deposit bundles."
            )
        if bundle.status not in {"QUEUED", "RUNNING"}:
            raise ExportConflictError(
                "Only QUEUED or RUNNING deposit bundles can be canceled."
            )
        now = datetime.now(UTC)
        canceled = replace_bundle(
            bundle,
            status="CANCELED",
            canceled_by=current_user.user_id,
            canceled_at=now,
            finished_at=now,
        )
        self.deposit_bundles[request_id] = [
            canceled if item.id == bundle.id else item
            for item in self.deposit_bundles.get(request_id, [])
        ]
        self.bundle_events.setdefault(bundle.id, []).append(
            BundleEventRecord(
                id=f"{bundle.id}-canceled",
                bundle_id=bundle.id,
                event_type="BUNDLE_BUILD_CANCELED",
                verification_run_id=None,
                validation_run_id=None,
                actor_user_id=current_user.user_id,
                reason=None,
                created_at=now,
            )
        )
        return canceled

    def rebuild_export_request_bundle(self, **kwargs) -> DepositBundleRecord:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        request_id = str(kwargs["export_request_id"])
        bundle_id = str(kwargs["bundle_id"])
        current_user = kwargs["current_user"]
        target = next(
            (item for item in self.deposit_bundles.get(request_id, []) if item.id == bundle_id),
            None,
        )
        if target is None:
            raise ExportNotFoundError("Deposit bundle not found.")
        if target.bundle_kind == "CONTROLLED_EVIDENCE":
            if not self._is_admin(current_user):
                raise ExportAccessDeniedError(
                    "Only ADMIN can mutate controlled evidence deposit bundles."
                )
        elif not (self._is_admin(current_user) or self._is_reviewer_or_lead(current_user)):
            raise ExportAccessDeniedError(
                "Only PROJECT_LEAD, REVIEWER, or ADMIN can mutate safeguarded deposit bundles."
            )
        history = list(self.deposit_bundles.get(request_id, []))
        current = next(
            (
                item
                for item in history
                if item.bundle_kind == target.bundle_kind
                and item.candidate_snapshot_id == target.candidate_snapshot_id
                and item.superseded_by_bundle_id is None
            ),
            None,
        )
        rebuilt = self.create_export_request_bundle(
            current_user=current_user,
            project_id=target.project_id,
            export_request_id=request_id,
            bundle_kind=target.bundle_kind,
        )
        if rebuilt.id == (current.id if current is not None else None):
            attempt_number = current.attempt_number + 1 if current is not None else 1
            now = datetime.now(UTC)
            proof = self._ensure_provenance_proof(
                request_id=request_id, actor_user_id=current_user.user_id
            )
            artifact = dict(self.bundle_artifacts.get(rebuilt.id, {}))
            new_id = f"{request_id}-{target.bundle_kind.lower()}-{attempt_number}"
            rebuilt = replace_bundle(
                rebuilt,
                id=new_id,
                attempt_number=attempt_number,
                supersedes_bundle_id=current.id if current is not None else None,
                superseded_by_bundle_id=None,
                bundle_key=self._bundle_key(
                    project_id=target.project_id,
                    export_request_id=request_id,
                    bundle_id=new_id,
                    kind=target.bundle_kind,
                ),
                created_at=now,
                started_at=now,
                finished_at=now,
                created_by=current_user.user_id,
                provenance_proof_id=proof.id,
                provenance_proof_artifact_sha256=proof.proof_artifact_sha256,
            )
            if current is not None:
                history = [
                    replace_bundle(item, superseded_by_bundle_id=new_id)
                    if item.id == current.id
                    else item
                    for item in history
                ]
            history.insert(0, rebuilt)
            self.deposit_bundles[request_id] = history
            self.bundle_artifacts[new_id] = artifact
            self.bundle_verification[new_id] = BundleVerificationProjectionRecord(
                bundle_id=new_id,
                status="PENDING",
                last_verification_run_id=None,
                verified_at=None,
                updated_at=now,
            )
            self.bundle_events[new_id] = [
                BundleEventRecord(
                    id=f"{new_id}-rebuild",
                    bundle_id=new_id,
                    event_type="BUNDLE_REBUILD_REQUESTED",
                    verification_run_id=None,
                    validation_run_id=None,
                    actor_user_id=current_user.user_id,
                    reason=f"requested_from:{bundle_id}",
                    created_at=now,
                ),
                BundleEventRecord(
                    id=f"{new_id}-queued",
                    bundle_id=new_id,
                    event_type="BUNDLE_BUILD_QUEUED",
                    verification_run_id=None,
                    validation_run_id=None,
                    actor_user_id=current_user.user_id,
                    reason=None,
                    created_at=now + timedelta(microseconds=1),
                ),
                BundleEventRecord(
                    id=f"{new_id}-started",
                    bundle_id=new_id,
                    event_type="BUNDLE_BUILD_STARTED",
                    verification_run_id=None,
                    validation_run_id=None,
                    actor_user_id=current_user.user_id,
                    reason=None,
                    created_at=now + timedelta(microseconds=2),
                ),
                BundleEventRecord(
                    id=f"{new_id}-succeeded",
                    bundle_id=new_id,
                    event_type="BUNDLE_BUILD_SUCCEEDED",
                    verification_run_id=None,
                    validation_run_id=None,
                    actor_user_id=current_user.user_id,
                    reason=f"bundle_sha256:{rebuilt.bundle_sha256}",
                    created_at=now + timedelta(microseconds=3),
                ),
            ]
        return rebuilt

    def start_export_request_bundle_verification(
        self, **kwargs
    ) -> BundleVerificationRunRecord:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        request_id = str(kwargs["export_request_id"])
        bundle_id = str(kwargs["bundle_id"])
        current_user = kwargs["current_user"]
        if not self._is_admin(current_user):
            raise ExportAccessDeniedError("Only ADMIN can start bundle verification.")
        detail = self.get_export_request_bundle(**kwargs)
        bundle = detail["bundle"]
        if not isinstance(bundle, DepositBundleRecord):
            raise ExportNotFoundError("Deposit bundle not found.")
        if bundle.status != "SUCCEEDED":
            raise ExportConflictError("Bundle verification requires a SUCCEEDED bundle attempt.")
        artifact = self.bundle_artifacts.get(bundle.id)
        if artifact is None:
            raise ExportConflictError(
                "Bundle verification requires an immutable succeeded bundle artifact."
            )
        runs = list(self.bundle_verification_runs.get(bundle.id, []))
        current = next((item for item in runs if item.superseded_by_verification_run_id is None), None)
        attempt_number = max((item.attempt_number for item in runs), default=0) + 1
        now = datetime.now(UTC)
        computed_sha = hashlib.sha256(str(artifact).encode("utf-8")).hexdigest()
        failures: list[str] = []
        if computed_sha != bundle.bundle_sha256:
            failures.append("Bundle archive hash does not match the pinned immutable hash.")
        result = "VALID" if not failures else "INVALID"
        status_value = "SUCCEEDED" if result == "VALID" else "FAILED"
        run = BundleVerificationRunRecord(
            id=f"{bundle.id}-verify-{attempt_number}",
            project_id=bundle.project_id,
            bundle_id=bundle.id,
            attempt_number=attempt_number,
            supersedes_verification_run_id=current.id if current is not None else None,
            superseded_by_verification_run_id=None,
            status=status_value,  # type: ignore[arg-type]
            result_json={
                "verificationResult": result,
                "bundleSha256": bundle.bundle_sha256,
                "rootSha256": "root-placeholder",
                "signatureStatus": "VALID",
                "failures": failures,
            },
            created_by=current_user.user_id,
            created_at=now,
            started_at=now,
            finished_at=now,
            canceled_by=None,
            canceled_at=None,
            failure_reason="; ".join(failures) if failures else None,
        )
        if current is not None:
            runs = [
                run_item
                if run_item.id != current.id
                else replace_verification_run(
                    run_item,
                    superseded_by_verification_run_id=run.id,
                )
                for run_item in runs
            ]
        runs.insert(0, run)
        self.bundle_verification_runs[bundle.id] = runs

        projection = self.bundle_verification.get(bundle.id)
        if projection is None:
            projection = BundleVerificationProjectionRecord(
                bundle_id=bundle.id,
                status="PENDING",
                last_verification_run_id=None,
                verified_at=None,
                updated_at=now,
            )
        if run.status == "SUCCEEDED":
            projection = BundleVerificationProjectionRecord(
                bundle_id=bundle.id,
                status="VERIFIED",
                last_verification_run_id=run.id,
                verified_at=now,
                updated_at=now,
            )
        elif projection.status != "VERIFIED":
            projection = BundleVerificationProjectionRecord(
                bundle_id=bundle.id,
                status="FAILED",
                last_verification_run_id=run.id,
                verified_at=None,
                updated_at=now,
            )
        else:
            projection = BundleVerificationProjectionRecord(
                bundle_id=projection.bundle_id,
                status=projection.status,
                last_verification_run_id=projection.last_verification_run_id,
                verified_at=projection.verified_at,
                updated_at=now,
            )
        self.bundle_verification[bundle.id] = projection
        self.bundle_events.setdefault(bundle.id, []).extend(
            [
                BundleEventRecord(
                    id=f"{run.id}-started",
                    bundle_id=bundle.id,
                    event_type="BUNDLE_VERIFICATION_STARTED",
                    verification_run_id=run.id,
                    validation_run_id=None,
                    actor_user_id=current_user.user_id,
                    reason=None,
                    created_at=now + timedelta(microseconds=1),
                ),
                BundleEventRecord(
                    id=f"{run.id}-terminal",
                    bundle_id=bundle.id,
                    event_type=(
                        "BUNDLE_VERIFICATION_SUCCEEDED"
                        if run.status == "SUCCEEDED"
                        else "BUNDLE_VERIFICATION_FAILED"
                    ),
                    verification_run_id=run.id,
                    validation_run_id=None,
                    actor_user_id=current_user.user_id,
                    reason=run.failure_reason,
                    created_at=now + timedelta(microseconds=2),
                ),
            ]
        )
        return run

    def get_export_request_bundle_verification(self, **kwargs) -> dict[str, object]:  # type: ignore[no-untyped-def]
        detail = self.get_export_request_bundle(**kwargs)
        bundle = detail["bundle"]
        if not isinstance(bundle, DepositBundleRecord):
            raise ExportNotFoundError("Deposit bundle not found.")
        runs = sorted(
            self.bundle_verification_runs.get(bundle.id, []),
            key=lambda item: (item.attempt_number, item.created_at, item.id),
            reverse=True,
        )
        latest_attempt = runs[0] if runs else None
        latest_completed_attempt = next(
            (item for item in runs if item.status in {"SUCCEEDED", "FAILED"}),
            None,
        )
        return {
            "bundle": bundle,
            "projection": self.bundle_verification.get(bundle.id),
            "latestAttempt": latest_attempt,
            "latestCompletedAttempt": latest_completed_attempt,
        }

    def get_export_request_bundle_verification_status(self, **kwargs) -> dict[str, object]:  # type: ignore[no-untyped-def]
        detail = self.get_export_request_bundle_verification(**kwargs)
        return {
            "bundle": detail["bundle"],
            "projection": detail["projection"],
            "latestAttempt": detail["latestAttempt"],
        }

    def list_export_request_bundle_verification_runs(
        self, **kwargs
    ) -> tuple[BundleVerificationRunRecord, ...]:  # type: ignore[no-untyped-def]
        detail = self.get_export_request_bundle(**kwargs)
        bundle = detail["bundle"]
        if not isinstance(bundle, DepositBundleRecord):
            raise ExportNotFoundError("Deposit bundle not found.")
        runs = sorted(
            self.bundle_verification_runs.get(bundle.id, []),
            key=lambda item: (item.attempt_number, item.created_at, item.id),
            reverse=True,
        )
        return tuple(runs)

    def get_export_request_bundle_verification_run(
        self, **kwargs
    ) -> BundleVerificationRunRecord:  # type: ignore[no-untyped-def]
        detail = self.get_export_request_bundle(**kwargs)
        bundle = detail["bundle"]
        if not isinstance(bundle, DepositBundleRecord):
            raise ExportNotFoundError("Deposit bundle not found.")
        verification_run_id = str(kwargs["verification_run_id"])
        run = next(
            (
                item
                for item in self.bundle_verification_runs.get(bundle.id, [])
                if item.id == verification_run_id
            ),
            None,
        )
        if run is None:
            raise ExportNotFoundError("Bundle verification run not found.")
        return run

    def get_export_request_bundle_verification_run_status(
        self, **kwargs
    ) -> dict[str, object]:  # type: ignore[no-untyped-def]
        run = self.get_export_request_bundle_verification_run(**kwargs)
        return {"verificationRun": run}

    def cancel_export_request_bundle_verification_run(
        self, **kwargs
    ) -> BundleVerificationRunRecord:  # type: ignore[no-untyped-def]
        current_user = kwargs["current_user"]
        if not self._is_admin(current_user):
            raise ExportAccessDeniedError("Only ADMIN can cancel bundle verification runs.")
        run = self.get_export_request_bundle_verification_run(**kwargs)
        if run.status not in {"QUEUED", "RUNNING"}:
            raise ExportConflictError(
                "Bundle verification cancel is allowed only for QUEUED or RUNNING runs."
            )
        now = datetime.now(UTC)
        canceled = replace_verification_run(
            run,
            status="CANCELED",
            canceled_by=current_user.user_id,
            canceled_at=now,
            finished_at=now,
            failure_reason="Bundle verification run canceled.",
        )
        bundle_id = run.bundle_id
        self.bundle_verification_runs[bundle_id] = [
            canceled if item.id == run.id else item
            for item in self.bundle_verification_runs.get(bundle_id, [])
        ]
        self.bundle_events.setdefault(bundle_id, []).append(
            BundleEventRecord(
                id=f"{run.id}-canceled",
                bundle_id=bundle_id,
                event_type="BUNDLE_VERIFICATION_CANCELED",
                verification_run_id=run.id,
                validation_run_id=None,
                actor_user_id=current_user.user_id,
                reason="Bundle verification run canceled.",
                created_at=now,
            )
        )
        return canceled

    def list_export_request_bundle_profiles(
        self, **kwargs
    ) -> tuple[BundleProfileRecord, ...]:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        bundle_id = kwargs.get("bundle_id")
        if isinstance(bundle_id, str) and bundle_id.strip():
            _ = self.get_export_request_bundle(
                current_user=kwargs["current_user"],
                project_id=kwargs["project_id"],
                export_request_id=kwargs["export_request_id"],
                bundle_id=bundle_id,
            )
        return self.bundle_profiles

    def start_export_request_bundle_validation(
        self, **kwargs
    ) -> BundleValidationRunRecord:  # type: ignore[no-untyped-def]
        self._maybe_raise()
        current_user = kwargs["current_user"]
        if not self._is_admin(current_user):
            raise ExportAccessDeniedError("Only ADMIN can start bundle validation.")
        profile_id = str(kwargs["profile_id"]).strip().upper()
        try:
            profile = get_bundle_profile(profile_id=profile_id)
        except ValueError as error:
            raise ExportConflictError(str(error)) from error

        detail = self.get_export_request_bundle(**kwargs)
        bundle = detail["bundle"]
        if not isinstance(bundle, DepositBundleRecord):
            raise ExportNotFoundError("Deposit bundle not found.")
        if bundle.status != "SUCCEEDED":
            raise ExportConflictError("Bundle validation requires a SUCCEEDED bundle attempt.")
        artifact = self.bundle_artifacts.get(bundle.id)
        if artifact is None:
            raise ExportConflictError(
                "Bundle validation requires an immutable succeeded bundle artifact."
            )

        key = (bundle.id, profile.id)
        runs = list(self.bundle_validation_runs.get(key, []))
        current = next((item for item in runs if item.superseded_by_validation_run_id is None), None)
        attempt_number = max((item.attempt_number for item in runs), default=0) + 1
        now = datetime.now(UTC)
        projection = self.bundle_verification.get(bundle.id)
        verification_status = projection.status if projection is not None else None
        output = validate_bundle_artifact_against_profile(
            bundle_id=bundle.id,
            bundle_kind=bundle.bundle_kind,
            bundle_sha256=bundle.bundle_sha256 or "",
            bundle_artifact=artifact,
            expected_proof_artifact_sha256=bundle.provenance_proof_artifact_sha256,
            verification_projection_status=verification_status,
            profile=profile,
            checked_at=now,
        )
        snapshot_sha = bundle_profile_snapshot_sha256(profile=profile)
        snapshot_key = (
            "controlled/derived/provenance/"
            f"{bundle.project_id}/export-requests/{bundle.export_request_id}/bundles/{bundle.id}/"
            f"profiles/{profile.id.lower()}/{snapshot_sha}.json"
        )
        result_json = dict(output.payload)
        result_json["profileSnapshotSha256"] = snapshot_sha
        result_json["profileSnapshotKey"] = snapshot_key
        result_json["profileSnapshot"] = build_bundle_profile_snapshot(profile=profile)
        result_json["attemptNumber"] = attempt_number
        status_value = "SUCCEEDED" if output.result == "VALID" else "FAILED"
        failure_reason = (
            "; ".join(
                str(item)
                for item in result_json.get("failures", [])
                if isinstance(item, str) and item.strip()
            )[:5000]
            if status_value == "FAILED"
            else None
        )
        run = BundleValidationRunRecord(
            id=f"{bundle.id}-validate-{profile.id.lower()}-{attempt_number}",
            project_id=bundle.project_id,
            bundle_id=bundle.id,
            profile_id=profile.id,
            profile_snapshot_key=snapshot_key,
            profile_snapshot_sha256=snapshot_sha,
            status=status_value,  # type: ignore[arg-type]
            attempt_number=attempt_number,
            supersedes_validation_run_id=current.id if current is not None else None,
            superseded_by_validation_run_id=None,
            result_json=result_json,
            failure_reason=failure_reason,
            created_by=current_user.user_id,
            created_at=now,
            started_at=now,
            finished_at=now,
            canceled_by=None,
            canceled_at=None,
        )
        if current is not None:
            runs = [
                replace_validation_run(item, superseded_by_validation_run_id=run.id)
                if item.id == current.id
                else item
                for item in runs
            ]
        runs.insert(0, run)
        self.bundle_validation_runs[key] = runs

        prior_projection = self.bundle_validation_projections.get(key)
        if status_value == "SUCCEEDED":
            next_projection = BundleValidationProjectionRecord(
                bundle_id=bundle.id,
                profile_id=profile.id,
                status="READY",
                last_validation_run_id=run.id,
                ready_at=now,
                updated_at=now,
            )
        elif prior_projection is not None and prior_projection.status == "READY":
            next_projection = replace_validation_projection(prior_projection, updated_at=now)
        else:
            next_projection = BundleValidationProjectionRecord(
                bundle_id=bundle.id,
                profile_id=profile.id,
                status="FAILED",
                last_validation_run_id=run.id,
                ready_at=None,
                updated_at=now,
            )
        self.bundle_validation_projections[key] = next_projection
        self.bundle_events.setdefault(bundle.id, []).extend(
            [
                BundleEventRecord(
                    id=f"{run.id}-validation-started",
                    bundle_id=bundle.id,
                    event_type="BUNDLE_VALIDATION_STARTED",
                    verification_run_id=None,
                    validation_run_id=run.id,
                    actor_user_id=current_user.user_id,
                    reason=f"profile:{profile.id}",
                    created_at=now + timedelta(microseconds=1),
                ),
                BundleEventRecord(
                    id=f"{run.id}-validation-terminal",
                    bundle_id=bundle.id,
                    event_type=(
                        "BUNDLE_VALIDATION_SUCCEEDED"
                        if status_value == "SUCCEEDED"
                        else "BUNDLE_VALIDATION_FAILED"
                    ),
                    verification_run_id=None,
                    validation_run_id=run.id,
                    actor_user_id=current_user.user_id,
                    reason=run.failure_reason or f"profile:{profile.id}",
                    created_at=now + timedelta(microseconds=2),
                ),
            ]
        )
        return run

    def get_export_request_bundle_validation_status(self, **kwargs) -> dict[str, object]:  # type: ignore[no-untyped-def]
        detail = self.get_export_request_bundle(**kwargs)
        bundle = detail["bundle"]
        if not isinstance(bundle, DepositBundleRecord):
            raise ExportNotFoundError("Deposit bundle not found.")
        profile_id = str(kwargs["profile_id"]).strip().upper()
        runs = sorted(
            self.bundle_validation_runs.get((bundle.id, profile_id), []),
            key=lambda item: (item.attempt_number, item.created_at, item.id),
            reverse=True,
        )
        return {
            "bundleId": bundle.id,
            "bundleStatus": bundle.status,
            "profileId": profile_id,
            "verificationProjection": self.bundle_verification.get(bundle.id),
            "projection": self.bundle_validation_projections.get((bundle.id, profile_id)),
            "latestAttempt": runs[0] if runs else None,
            "inFlightAttempt": next(
                (item for item in runs if item.status in {"QUEUED", "RUNNING"}),
                None,
            ),
            "lastSuccessfulAttempt": next(
                (item for item in runs if item.status == "SUCCEEDED"),
                None,
            ),
        }

    def list_export_request_bundle_validation_runs(
        self, **kwargs
    ) -> tuple[BundleValidationRunRecord, ...]:  # type: ignore[no-untyped-def]
        detail = self.get_export_request_bundle(**kwargs)
        bundle = detail["bundle"]
        if not isinstance(bundle, DepositBundleRecord):
            raise ExportNotFoundError("Deposit bundle not found.")
        profile_id = str(kwargs["profile_id"]).strip().upper()
        runs = sorted(
            self.bundle_validation_runs.get((bundle.id, profile_id), []),
            key=lambda item: (item.attempt_number, item.created_at, item.id),
            reverse=True,
        )
        return tuple(runs)

    def get_export_request_bundle_validation_run(
        self, **kwargs
    ) -> BundleValidationRunRecord:  # type: ignore[no-untyped-def]
        detail = self.get_export_request_bundle(**kwargs)
        bundle = detail["bundle"]
        if not isinstance(bundle, DepositBundleRecord):
            raise ExportNotFoundError("Deposit bundle not found.")
        validation_run_id = str(kwargs["validation_run_id"])
        profile_id = kwargs.get("profile_id")
        if isinstance(profile_id, str) and profile_id.strip():
            profiles = [profile_id.strip().upper()]
        else:
            profiles = [item.id for item in self.bundle_profiles]
        for item_profile_id in profiles:
            match = next(
                (
                    item
                    for item in self.bundle_validation_runs.get((bundle.id, item_profile_id), [])
                    if item.id == validation_run_id
                ),
                None,
            )
            if match is not None:
                return match
        raise ExportNotFoundError("Bundle validation run not found.")

    def get_export_request_bundle_validation_run_status(
        self, **kwargs
    ) -> dict[str, object]:  # type: ignore[no-untyped-def]
        run = self.get_export_request_bundle_validation_run(**kwargs)
        return {"validationRun": run}

    def cancel_export_request_bundle_validation_run(
        self, **kwargs
    ) -> BundleValidationRunRecord:  # type: ignore[no-untyped-def]
        current_user = kwargs["current_user"]
        if not self._is_admin(current_user):
            raise ExportAccessDeniedError("Only ADMIN can cancel bundle validation runs.")
        run = self.get_export_request_bundle_validation_run(**kwargs)
        if run.status not in {"QUEUED", "RUNNING"}:
            raise ExportConflictError(
                "Bundle validation cancel is allowed only for QUEUED or RUNNING runs."
            )
        now = datetime.now(UTC)
        canceled = replace_validation_run(
            run,
            status="CANCELED",
            canceled_by=current_user.user_id,
            canceled_at=now,
            finished_at=now,
            failure_reason="Bundle validation run canceled.",
        )
        key = (run.bundle_id, run.profile_id)
        self.bundle_validation_runs[key] = [
            canceled if item.id == run.id else item
            for item in self.bundle_validation_runs.get(key, [])
        ]
        self.bundle_events.setdefault(run.bundle_id, []).append(
            BundleEventRecord(
                id=f"{run.id}-validation-canceled",
                bundle_id=run.bundle_id,
                event_type="BUNDLE_VALIDATION_CANCELED",
                verification_run_id=None,
                validation_run_id=run.id,
                actor_user_id=current_user.user_id,
                reason="Bundle validation run canceled.",
                created_at=now,
            )
        )
        return canceled

    def attach_gateway_export_request_receipt(  # type: ignore[no-untyped-def]
        self, **kwargs
    ) -> tuple[ExportRequestRecord, ExportReceiptRecord]:
        self._maybe_raise()
        request_id = str(kwargs["export_request_id"])
        receipt_key = str(kwargs["receipt_key"])
        receipt_sha256 = str(kwargs["receipt_sha256"])
        exported_at = kwargs["exported_at"]
        gateway_user_id = str(kwargs["gateway_user_id"])
        request = self.requests[request_id]
        if request.status not in {"APPROVED", "EXPORTED"}:
            raise ExportAccessDeniedError(
                "Only APPROVED or EXPORTED requests can attach gateway receipts."
            )
        history = list(self.receipts.get(request_id, []))
        now = datetime.now(UTC)
        supersedes = history[0].id if history else None
        attempt_number = len(history) + 1
        receipt = ExportReceiptRecord(
            id=f"receipt-{attempt_number}",
            export_request_id=request_id,
            attempt_number=attempt_number,
            supersedes_receipt_id=supersedes,
            superseded_by_receipt_id=None,
            receipt_key=receipt_key,
            receipt_sha256=receipt_sha256,
            created_by=gateway_user_id,
            created_at=now,
            exported_at=exported_at,
        )
        if history:
            history[0] = replace_receipt(
                history[0],
                superseded_by_receipt_id=receipt.id,
            )
        history.insert(0, receipt)
        self.receipts[request_id] = history
        self.requests[request_id] = replace_request(
            request,
            status="EXPORTED",
            receipt_id=receipt.id,
            receipt_key=receipt_key,
            receipt_sha256=receipt_sha256,
            receipt_created_by=gateway_user_id,
            receipt_created_at=now,
            exported_at=exported_at,
            updated_at=now,
        )
        self.request_events[request_id].append(
            ExportRequestEventRecord(
                id=f"event-{len(self.request_events[request_id]) + 1}",
                export_request_id=request_id,
                event_type="REQUEST_RECEIPT_ATTACHED",
                from_status=request.status,
                to_status=request.status,
                actor_user_id=gateway_user_id,
                reason=f"receipt_attempt:{attempt_number}",
                created_at=now,
            )
        )
        self.request_events[request_id].append(
            ExportRequestEventRecord(
                id=f"event-{len(self.request_events[request_id]) + 1}",
                export_request_id=request_id,
                event_type="REQUEST_EXPORTED",
                from_status=request.status,
                to_status="EXPORTED",
                actor_user_id=gateway_user_id,
                reason=f"receipt_attempt:{attempt_number}",
                created_at=now,
            )
        )
        return self.requests[request_id], receipt

    def list_export_review_queue(  # type: ignore[no-untyped-def]
        self, **kwargs
    ) -> tuple[ExportReviewQueueItemRecord, ...]:
        self._maybe_raise()
        _ = kwargs
        request = self.requests["request-1"]
        reviews = tuple(self.request_reviews["request-1"])
        active = next(
            (
                review
                for review in reviews
                if review.is_required and review.status in {"PENDING", "IN_REVIEW"}
            ),
            None,
        )
        if request.status not in {"SUBMITTED", "RESUBMITTED", "IN_REVIEW"}:
            return ()
        return (
            ExportReviewQueueItemRecord(
                request=request,
                reviews=reviews,
                active_review_id=active.id if active else None,
                active_review_stage=active.review_stage if active else None,
                active_review_status=active.status if active else None,
                active_review_assigned_reviewer_user_id=(
                    active.assigned_reviewer_user_id if active else None
                ),
                aging_bucket="ON_TRACK",
                sla_seconds_remaining=7200,
                is_sla_breached=False,
            ),
        )

    def claim_export_request_review(  # type: ignore[no-untyped-def]
        self, **kwargs
    ) -> tuple[ExportRequestRecord, ExportRequestReviewRecord]:
        self._maybe_raise()
        if not self._can_mutate_review(kwargs):
            raise ExportAccessDeniedError("Current role cannot mutate export review stages.")
        request_id = str(kwargs["export_request_id"])
        review_id = str(kwargs["review_id"])
        review_etag = str(kwargs["review_etag"])
        reviews = self.request_reviews[request_id]
        review = next(item for item in reviews if item.id == review_id)
        if review.review_etag != review_etag:
            raise ExportAccessDeniedError("stale etag")
        now = datetime.now(UTC)
        updated_review = replace_review(
            review,
            assigned_reviewer_user_id="reviewer-1",
            assigned_at=now,
            review_etag=f"{review.id}-claimed-etag",
            updated_at=now,
        )
        self.request_reviews[request_id] = [
            updated_review if item.id == review_id else item for item in reviews
        ]
        self.request_review_events[request_id].append(
            ExportRequestReviewEventRecord(
                id=f"review-event-{len(self.request_review_events[request_id]) + 1}",
                review_id=review_id,
                export_request_id=request_id,
                review_stage=updated_review.review_stage,
                event_type="REVIEW_CLAIMED",
                actor_user_id="reviewer-1",
                assigned_reviewer_user_id="reviewer-1",
                decision_reason=None,
                return_comment=None,
                created_at=now,
            )
        )
        return self.requests[request_id], updated_review

    def release_export_request_review(  # type: ignore[no-untyped-def]
        self, **kwargs
    ) -> tuple[ExportRequestRecord, ExportRequestReviewRecord]:
        self._maybe_raise()
        if not self._can_mutate_review(kwargs):
            raise ExportAccessDeniedError("Current role cannot mutate export review stages.")
        request_id = str(kwargs["export_request_id"])
        review_id = str(kwargs["review_id"])
        review_etag = str(kwargs["review_etag"])
        reviews = self.request_reviews[request_id]
        review = next(item for item in reviews if item.id == review_id)
        if review.review_etag != review_etag:
            raise ExportAccessDeniedError("stale etag")
        now = datetime.now(UTC)
        updated_review = replace_review(
            review,
            status="PENDING",
            assigned_reviewer_user_id=None,
            assigned_at=None,
            review_etag=f"{review.id}-released-etag",
            updated_at=now,
        )
        self.request_reviews[request_id] = [
            updated_review if item.id == review_id else item for item in reviews
        ]
        self.request_review_events[request_id].append(
            ExportRequestReviewEventRecord(
                id=f"review-event-{len(self.request_review_events[request_id]) + 1}",
                review_id=review_id,
                export_request_id=request_id,
                review_stage=updated_review.review_stage,
                event_type="REVIEW_RELEASED",
                actor_user_id="reviewer-1",
                assigned_reviewer_user_id=None,
                decision_reason=None,
                return_comment=None,
                created_at=now,
            )
        )
        return self.requests[request_id], updated_review

    def start_export_request_review(  # type: ignore[no-untyped-def]
        self, **kwargs
    ) -> tuple[ExportRequestRecord, ExportRequestReviewRecord]:
        self._maybe_raise()
        if not self._can_mutate_review(kwargs):
            raise ExportAccessDeniedError("Current role cannot mutate export review stages.")
        request_id = str(kwargs["export_request_id"])
        review_id = str(kwargs["review_id"])
        review_etag = str(kwargs["review_etag"])
        reviews = self.request_reviews[request_id]
        review = next(item for item in reviews if item.id == review_id)
        if review.review_etag != review_etag:
            raise ExportAccessDeniedError("stale etag")
        now = datetime.now(UTC)
        updated_review = replace_review(
            review,
            status="IN_REVIEW",
            assigned_reviewer_user_id="reviewer-1",
            assigned_at=review.assigned_at or now,
            review_etag=f"{review.id}-started-etag",
            updated_at=now,
        )
        self.request_reviews[request_id] = [
            updated_review if item.id == review_id else item for item in reviews
        ]
        self.requests[request_id] = replace_request(
            self.requests[request_id],
            status="IN_REVIEW",
            first_review_started_by="reviewer-1",
            first_review_started_at=now,
            updated_at=now,
        )
        self.request_events[request_id].append(
            ExportRequestEventRecord(
                id=f"event-{len(self.request_events[request_id]) + 1}",
                export_request_id=request_id,
                event_type="REQUEST_REVIEW_STARTED",
                from_status="SUBMITTED",
                to_status="IN_REVIEW",
                actor_user_id="reviewer-1",
                reason=None,
                created_at=now,
            )
        )
        self.request_review_events[request_id].append(
            ExportRequestReviewEventRecord(
                id=f"review-event-{len(self.request_review_events[request_id]) + 1}",
                review_id=review_id,
                export_request_id=request_id,
                review_stage=updated_review.review_stage,
                event_type="REVIEW_STARTED",
                actor_user_id="reviewer-1",
                assigned_reviewer_user_id="reviewer-1",
                decision_reason=None,
                return_comment=None,
                created_at=now,
            )
        )
        return self.requests[request_id], updated_review

    def decide_export_request(  # type: ignore[no-untyped-def]
        self, **kwargs
    ) -> tuple[ExportRequestRecord, ExportRequestReviewRecord]:
        self._maybe_raise()
        if not self._can_mutate_review(kwargs):
            raise ExportAccessDeniedError("Current role cannot mutate export review stages.")
        request_id = str(kwargs["export_request_id"])
        review_id = str(kwargs["review_id"])
        review_etag = str(kwargs["review_etag"])
        decision = str(kwargs["decision"])
        decision_reason = kwargs.get("decision_reason")
        return_comment = kwargs.get("return_comment")
        reviews = self.request_reviews[request_id]
        review = next(item for item in reviews if item.id == review_id)
        if review.review_etag != review_etag:
            raise ExportAccessDeniedError("stale etag")
        now = datetime.now(UTC)
        next_review_status = "APPROVED"
        next_request_status = "APPROVED"
        review_event_type = "REVIEW_APPROVED"
        request_event_type = "REQUEST_APPROVED"
        request_event_reason = decision_reason
        if decision == "REJECT":
            next_review_status = "REJECTED"
            next_request_status = "REJECTED"
            review_event_type = "REVIEW_REJECTED"
            request_event_type = "REQUEST_REJECTED"
            request_event_reason = decision_reason
        elif decision == "RETURN":
            next_review_status = "RETURNED"
            next_request_status = "RETURNED"
            review_event_type = "REVIEW_RETURNED"
            request_event_type = "REQUEST_RETURNED"
            request_event_reason = return_comment
        updated_review = replace_review(
            review,
            status=next_review_status,  # type: ignore[arg-type]
            acted_by_user_id="reviewer-1",
            acted_at=now,
            decision_reason=decision_reason if isinstance(decision_reason, str) else None,
            return_comment=return_comment if isinstance(return_comment, str) else None,
            review_etag=f"{review.id}-decided-etag",
            updated_at=now,
        )
        self.request_reviews[request_id] = [
            updated_review if item.id == review_id else item for item in reviews
        ]
        self.requests[request_id] = replace_request(
            self.requests[request_id],
            status=next_request_status,  # type: ignore[arg-type]
            final_review_id=review_id,
            final_decision_by="reviewer-1",
            final_decision_at=now,
            final_decision_reason=(
                updated_review.decision_reason if decision != "RETURN" else None
            ),
            final_return_comment=updated_review.return_comment,
            updated_at=now,
        )
        self.request_events[request_id].append(
            ExportRequestEventRecord(
                id=f"event-{len(self.request_events[request_id]) + 1}",
                export_request_id=request_id,
                event_type=request_event_type,  # type: ignore[arg-type]
                from_status="IN_REVIEW",
                to_status=next_request_status,  # type: ignore[arg-type]
                actor_user_id="reviewer-1",
                reason=request_event_reason if isinstance(request_event_reason, str) else None,
                created_at=now,
            )
        )
        self.request_review_events[request_id].append(
            ExportRequestReviewEventRecord(
                id=f"review-event-{len(self.request_review_events[request_id]) + 1}",
                review_id=review_id,
                export_request_id=request_id,
                review_stage=updated_review.review_stage,
                event_type=review_event_type,  # type: ignore[arg-type]
                actor_user_id="reviewer-1",
                assigned_reviewer_user_id="reviewer-1",
                decision_reason=updated_review.decision_reason,
                return_comment=updated_review.return_comment,
                created_at=now,
            )
        )
        return self.requests[request_id], updated_review


def replace_request(record: ExportRequestRecord, **kwargs) -> ExportRequestRecord:  # type: ignore[no-untyped-def]
    values = record.__dict__.copy()
    values.update(kwargs)
    return ExportRequestRecord(**values)


def replace_review(record: ExportRequestReviewRecord, **kwargs) -> ExportRequestReviewRecord:  # type: ignore[no-untyped-def]
    values = record.__dict__.copy()
    values.update(kwargs)
    return ExportRequestReviewRecord(**values)


def replace_receipt(record: ExportReceiptRecord, **kwargs) -> ExportReceiptRecord:  # type: ignore[no-untyped-def]
    values = record.__dict__.copy()
    values.update(kwargs)
    return ExportReceiptRecord(**values)


def replace_proof(record: ProvenanceProofRecord, **kwargs) -> ProvenanceProofRecord:  # type: ignore[no-untyped-def]
    values = record.__dict__.copy()
    values.update(kwargs)
    return ProvenanceProofRecord(**values)


def replace_bundle(record: DepositBundleRecord, **kwargs) -> DepositBundleRecord:  # type: ignore[no-untyped-def]
    values = record.__dict__.copy()
    values.update(kwargs)
    return DepositBundleRecord(**values)


def replace_verification_run(
    record: BundleVerificationRunRecord, **kwargs
) -> BundleVerificationRunRecord:  # type: ignore[no-untyped-def]
    values = record.__dict__.copy()
    values.update(kwargs)
    return BundleVerificationRunRecord(**values)


def replace_validation_projection(
    record: BundleValidationProjectionRecord, **kwargs
) -> BundleValidationProjectionRecord:  # type: ignore[no-untyped-def]
    values = record.__dict__.copy()
    values.update(kwargs)
    return BundleValidationProjectionRecord(**values)


def replace_validation_run(
    record: BundleValidationRunRecord, **kwargs
) -> BundleValidationRunRecord:  # type: ignore[no-untyped-def]
    values = record.__dict__.copy()
    values.update(kwargs)
    return BundleValidationRunRecord(**values)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:
    yield
    app.dependency_overrides.clear()


def test_export_candidates_routes_return_payload_and_emit_audit() -> None:
    service = FakeExportService()
    audit = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="researcher-1"
    )
    app.dependency_overrides[get_export_service] = lambda: service
    app.dependency_overrides[get_audit_service] = lambda: audit

    list_response = client.get("/projects/project-1/export-candidates")
    detail_response = client.get("/projects/project-1/export-candidates/candidate-1")
    preview_response = client.get("/projects/project-1/export-candidates/candidate-1/release-pack")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert preview_response.status_code == 200
    event_types = {str(event.get("event_type")) for event in audit.recorded}
    assert "EXPORT_CANDIDATES_VIEWED" in event_types
    assert "EXPORT_CANDIDATE_VIEWED" in event_types
    assert "EXPORT_RELEASE_PACK_VIEWED" in event_types


def test_export_request_submit_and_resubmit_routes_emit_audit_events() -> None:
    service = FakeExportService()
    audit = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="researcher-1"
    )
    app.dependency_overrides[get_export_service] = lambda: service
    app.dependency_overrides[get_audit_service] = lambda: audit

    create_response = client.post(
        "/projects/project-1/export-requests",
        json={
            "candidateSnapshotId": "candidate-1",
            "purposeStatement": "Submit this candidate as a first export request.",
        },
    )
    resubmit_response = client.post(
        "/projects/project-1/export-requests/request-1/resubmit",
        json={
            "candidateSnapshotId": "candidate-1",
            "purposeStatement": "Resubmit as successor revision after return.",
        },
    )

    assert create_response.status_code == 201
    assert resubmit_response.status_code == 201
    event_types = {str(event.get("event_type")) for event in audit.recorded}
    assert "EXPORT_REQUEST_SUBMITTED" in event_types
    assert "EXPORT_REQUEST_RESUBMITTED" in event_types


def test_export_request_read_surfaces_emit_audit_events() -> None:
    service = FakeExportService()
    audit = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="researcher-1"
    )
    app.dependency_overrides[get_export_service] = lambda: service
    app.dependency_overrides[get_audit_service] = lambda: audit

    responses = [
        client.get("/projects/project-1/export-requests"),
        client.get("/projects/project-1/export-requests/request-1"),
        client.get("/projects/project-1/export-requests/request-1/status"),
        client.get("/projects/project-1/export-requests/request-1/release-pack"),
        client.get("/projects/project-1/export-requests/request-1/validation-summary"),
        client.get("/projects/project-1/export-requests/request-1/events"),
        client.get("/projects/project-1/export-requests/request-1/reviews"),
        client.get("/projects/project-1/export-requests/request-1/reviews/events"),
    ]

    assert all(response.status_code == 200 for response in responses)
    event_types = {str(event.get("event_type")) for event in audit.recorded}
    assert "EXPORT_HISTORY_VIEWED" in event_types
    assert "EXPORT_REQUEST_VIEWED" in event_types
    assert "EXPORT_REQUEST_STATUS_VIEWED" in event_types
    assert "EXPORT_REQUEST_EVENTS_VIEWED" in event_types
    assert "EXPORT_REQUEST_REVIEWS_VIEWED" in event_types
    assert "EXPORT_REQUEST_REVIEW_EVENTS_VIEWED" in event_types


def test_export_request_provenance_routes_return_distinct_payloads_and_emit_audit() -> None:
    service = FakeExportService()
    service.requests["request-1"] = replace_request(
        service.requests["request-1"],
        status="APPROVED",
        final_review_id="review-1",
        final_decision_by="reviewer-1",
        final_decision_at=datetime.now(UTC),
    )
    audit = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="reviewer-1"
    )
    app.dependency_overrides[get_export_service] = lambda: service
    app.dependency_overrides[get_audit_service] = lambda: audit

    summary_response = client.get("/projects/project-1/export-requests/request-1/provenance")
    list_response = client.get("/projects/project-1/export-requests/request-1/provenance/proofs")
    current_response = client.get("/projects/project-1/export-requests/request-1/provenance/proof")

    assert summary_response.status_code == 200
    assert list_response.status_code == 200
    assert current_response.status_code == 200
    summary_payload = summary_response.json()
    list_payload = list_response.json()
    current_payload = current_response.json()

    assert summary_payload["proofAttemptCount"] == len(list_payload["items"])
    assert summary_payload["currentProofId"] == current_payload["proof"]["id"]
    assert summary_payload["signatureStatus"] == "SIGNED"
    assert current_payload["proof"]["supersededByProofId"] is None

    specific_response = client.get(
        f"/projects/project-1/export-requests/request-1/provenance/proofs/{current_payload['proof']['id']}"
    )
    assert specific_response.status_code == 200
    assert specific_response.json()["proof"]["id"] == current_payload["proof"]["id"]

    event_types = {str(event.get("event_type")) for event in audit.recorded}
    assert "EXPORT_PROVENANCE_VIEWED" in event_types
    assert "EXPORT_PROVENANCE_PROOFS_VIEWED" in event_types
    assert "EXPORT_PROVENANCE_PROOF_VIEWED" in event_types


def test_export_request_provenance_regeneration_is_admin_only() -> None:
    service = FakeExportService()
    service.requests["request-1"] = replace_request(
        service.requests["request-1"],
        status="APPROVED",
        final_review_id="review-1",
        final_decision_by="reviewer-1",
        final_decision_at=datetime.now(UTC),
    )
    audit = SpyAuditService()
    app.dependency_overrides[get_export_service] = lambda: service
    app.dependency_overrides[get_audit_service] = lambda: audit

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="reviewer-1"
    )
    denied_response = client.post(
        "/projects/project-1/export-requests/request-1/provenance/proofs/regenerate"
    )
    assert denied_response.status_code == 403

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="admin-1",
        platform_roles=("ADMIN",),
    )
    first_admin_response = client.post(
        "/projects/project-1/export-requests/request-1/provenance/proofs/regenerate"
    )
    second_admin_response = client.post(
        "/projects/project-1/export-requests/request-1/provenance/proofs/regenerate"
    )
    assert first_admin_response.status_code == 200
    assert second_admin_response.status_code == 200
    first_payload = first_admin_response.json()["proof"]
    second_payload = second_admin_response.json()["proof"]
    assert first_payload["attemptNumber"] == 1
    assert second_payload["attemptNumber"] == 2
    assert second_payload["supersedesProofId"] == first_payload["id"]

    event_types = {str(event.get("event_type")) for event in audit.recorded}
    assert "EXPORT_PROVENANCE_PROOF_REGENERATED" in event_types


def test_export_request_bundle_routes_return_payload_and_emit_audit() -> None:
    service = FakeExportService()
    service.requests["request-1"] = replace_request(
        service.requests["request-1"],
        status="APPROVED",
        final_review_id="review-1",
        final_decision_by="reviewer-1",
        final_decision_at=datetime.now(UTC),
    )
    audit = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="reviewer-1"
    )
    app.dependency_overrides[get_export_service] = lambda: service
    app.dependency_overrides[get_audit_service] = lambda: audit

    create_response = client.post(
        "/projects/project-1/export-requests/request-1/bundles?kind=SAFEGUARDED_DEPOSIT"
    )
    assert create_response.status_code == 200
    created_bundle = create_response.json()["bundle"]

    list_response = client.get("/projects/project-1/export-requests/request-1/bundles")
    detail_response = client.get(
        f"/projects/project-1/export-requests/request-1/bundles/{created_bundle['id']}"
    )
    status_response = client.get(
        f"/projects/project-1/export-requests/request-1/bundles/{created_bundle['id']}/status"
    )
    events_response = client.get(
        f"/projects/project-1/export-requests/request-1/bundles/{created_bundle['id']}/events"
    )
    rebuild_response = client.post(
        f"/projects/project-1/export-requests/request-1/bundles/{created_bundle['id']}/rebuild"
    )

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert status_response.status_code == 200
    assert events_response.status_code == 200
    assert rebuild_response.status_code == 200
    assert len(list_response.json()["items"]) >= 1
    assert len(events_response.json()["items"]) >= 3
    assert rebuild_response.json()["bundle"]["attemptNumber"] == 2

    event_types = {str(event.get("event_type")) for event in audit.recorded}
    assert "BUNDLE_LIST_VIEWED" in event_types
    assert "BUNDLE_BUILD_RUN_CREATED" in event_types
    assert "BUNDLE_DETAIL_VIEWED" in event_types
    assert "BUNDLE_STATUS_VIEWED" in event_types
    assert "BUNDLE_EVENTS_VIEWED" in event_types


def test_controlled_evidence_bundle_route_rbac() -> None:
    service = FakeExportService()
    service.requests["request-1"] = replace_request(
        service.requests["request-1"],
        status="APPROVED",
        final_review_id="review-1",
        final_decision_by="reviewer-1",
        final_decision_at=datetime.now(UTC),
    )
    app.dependency_overrides[get_export_service] = lambda: service
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="reviewer-1"
    )
    denied_create = client.post(
        "/projects/project-1/export-requests/request-1/bundles?kind=CONTROLLED_EVIDENCE"
    )
    assert denied_create.status_code == 403

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="admin-1",
        platform_roles=("ADMIN",),
    )
    created = client.post(
        "/projects/project-1/export-requests/request-1/bundles?kind=CONTROLLED_EVIDENCE"
    )
    assert created.status_code == 200
    bundle_id = created.json()["bundle"]["id"]

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="researcher-1"
    )
    denied_read = client.get(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}"
    )
    assert denied_read.status_code == 403

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="auditor-1",
        platform_roles=("AUDITOR",),
    )
    allowed_read = client.get(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}"
    )
    assert allowed_read.status_code == 200


def test_bundle_cancel_rejects_terminal_attempts() -> None:
    service = FakeExportService()
    service.requests["request-1"] = replace_request(
        service.requests["request-1"],
        status="APPROVED",
        final_review_id="review-1",
        final_decision_by="reviewer-1",
        final_decision_at=datetime.now(UTC),
    )
    app.dependency_overrides[get_export_service] = lambda: service
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="reviewer-1"
    )

    create = client.post(
        "/projects/project-1/export-requests/request-1/bundles?kind=SAFEGUARDED_DEPOSIT"
    )
    assert create.status_code == 200
    bundle_id = create.json()["bundle"]["id"]
    cancel = client.post(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/cancel"
    )
    assert cancel.status_code == 409


def test_bundle_verification_routes_return_payload_and_emit_audit() -> None:
    service = FakeExportService()
    service.requests["request-1"] = replace_request(
        service.requests["request-1"],
        status="APPROVED",
        final_review_id="review-1",
        final_decision_by="reviewer-1",
        final_decision_at=datetime.now(UTC),
    )
    audit = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="admin-1",
        platform_roles=("ADMIN",),
    )
    app.dependency_overrides[get_export_service] = lambda: service
    app.dependency_overrides[get_audit_service] = lambda: audit

    create = client.post(
        "/projects/project-1/export-requests/request-1/bundles?kind=SAFEGUARDED_DEPOSIT"
    )
    assert create.status_code == 200
    bundle_id = create.json()["bundle"]["id"]

    verify = client.post(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/verify"
    )
    assert verify.status_code == 200
    verification_run_id = verify.json()["verificationRun"]["id"]

    summary = client.get(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/verification"
    )
    status_response = client.get(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/verification/status"
    )
    runs = client.get(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/verification-runs"
    )
    detail = client.get(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/verification/{verification_run_id}"
    )
    run_status = client.get(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/verification/{verification_run_id}/status"
    )

    assert summary.status_code == 200
    assert status_response.status_code == 200
    assert runs.status_code == 200
    assert detail.status_code == 200
    assert run_status.status_code == 200
    assert len(runs.json()["items"]) >= 1

    event_types = {str(event.get("event_type")) for event in audit.recorded}
    assert "BUNDLE_VERIFICATION_RUN_CREATED" in event_types
    assert "BUNDLE_VERIFICATION_RUN_STARTED" in event_types
    assert "BUNDLE_VERIFICATION_VIEWED" in event_types
    assert "BUNDLE_VERIFICATION_STATUS_VIEWED" in event_types


def test_bundle_verification_route_rbac_and_cancel_rules() -> None:
    service = FakeExportService()
    service.requests["request-1"] = replace_request(
        service.requests["request-1"],
        status="APPROVED",
        final_review_id="review-1",
        final_decision_by="reviewer-1",
        final_decision_at=datetime.now(UTC),
    )
    app.dependency_overrides[get_export_service] = lambda: service
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="admin-1",
        platform_roles=("ADMIN",),
    )
    created = client.post(
        "/projects/project-1/export-requests/request-1/bundles?kind=CONTROLLED_EVIDENCE"
    )
    assert created.status_code == 200
    bundle_id = created.json()["bundle"]["id"]

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="reviewer-1"
    )
    denied_read = client.get(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/verification"
    )
    denied_start = client.post(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/verify"
    )
    assert denied_read.status_code == 403
    assert denied_start.status_code == 403

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="auditor-1",
        platform_roles=("AUDITOR",),
    )
    auditor_read = client.get(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/verification"
    )
    assert auditor_read.status_code == 200

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="admin-1",
        platform_roles=("ADMIN",),
    )
    run_response = client.post(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/verify"
    )
    assert run_response.status_code == 200
    run_id = run_response.json()["verificationRun"]["id"]

    terminal_cancel = client.post(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/verification/{run_id}/cancel"
    )
    assert terminal_cancel.status_code == 409

    now = datetime.now(UTC)
    running_run = BundleVerificationRunRecord(
        id=f"{bundle_id}-verify-running",
        project_id="project-1",
        bundle_id=bundle_id,
        attempt_number=99,
        supersedes_verification_run_id=run_id,
        superseded_by_verification_run_id=None,
        status="RUNNING",
        result_json={},
        created_by="admin-1",
        created_at=now,
        started_at=now,
        finished_at=None,
        canceled_by=None,
        canceled_at=None,
        failure_reason=None,
    )
    service.bundle_verification_runs[bundle_id] = [
        running_run,
        replace_verification_run(
            service.bundle_verification_runs[bundle_id][0],
            superseded_by_verification_run_id=running_run.id,
        ),
        *service.bundle_verification_runs[bundle_id][1:],
    ]
    running_cancel = client.post(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/verification/{running_run.id}/cancel"
    )
    assert running_cancel.status_code == 200
    assert running_cancel.json()["verificationRun"]["status"] == "CANCELED"


def test_bundle_validation_routes_return_payload_and_emit_audit() -> None:
    service = FakeExportService()
    service.requests["request-1"] = replace_request(
        service.requests["request-1"],
        status="APPROVED",
        final_review_id="review-1",
        final_decision_by="reviewer-1",
        final_decision_at=datetime.now(UTC),
    )
    audit = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="admin-1",
        platform_roles=("ADMIN",),
    )
    app.dependency_overrides[get_export_service] = lambda: service
    app.dependency_overrides[get_audit_service] = lambda: audit

    create = client.post(
        "/projects/project-1/export-requests/request-1/bundles?kind=SAFEGUARDED_DEPOSIT"
    )
    assert create.status_code == 200
    bundle_id = create.json()["bundle"]["id"]
    verify = client.post(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/verify"
    )
    assert verify.status_code == 200

    profiles = client.get(
        f"/projects/project-1/export-requests/request-1/bundle-profiles?bundleId={bundle_id}"
    )
    assert profiles.status_code == 200
    profile_id = "SAFEGUARDED_DEPOSIT_CORE_V1"
    validate = client.post(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/validate-profile?profile={profile_id}"
    )
    assert validate.status_code == 200
    validation_run_id = validate.json()["validationRun"]["id"]

    status_response = client.get(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/validation-status?profile={profile_id}"
    )
    runs = client.get(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/validation-runs?profile={profile_id}"
    )
    detail = client.get(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/validation-runs/{validation_run_id}?profile={profile_id}"
    )
    run_status = client.get(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/validation-runs/{validation_run_id}/status?profile={profile_id}"
    )

    assert status_response.status_code == 200
    assert runs.status_code == 200
    assert detail.status_code == 200
    assert run_status.status_code == 200
    assert len(runs.json()["items"]) >= 1

    event_types = {str(event.get("event_type")) for event in audit.recorded}
    assert "BUNDLE_PROFILES_VIEWED" in event_types
    assert "BUNDLE_VALIDATION_RUN_CREATED" in event_types
    assert "BUNDLE_VALIDATION_RUN_STARTED" in event_types
    assert "BUNDLE_VALIDATION_VIEWED" in event_types
    assert "BUNDLE_VALIDATION_STATUS_VIEWED" in event_types


def test_bundle_validation_route_rbac_and_cancel_rules() -> None:
    service = FakeExportService()
    service.requests["request-1"] = replace_request(
        service.requests["request-1"],
        status="APPROVED",
        final_review_id="review-1",
        final_decision_by="reviewer-1",
        final_decision_at=datetime.now(UTC),
    )
    app.dependency_overrides[get_export_service] = lambda: service
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="admin-1",
        platform_roles=("ADMIN",),
    )
    created = client.post(
        "/projects/project-1/export-requests/request-1/bundles?kind=CONTROLLED_EVIDENCE"
    )
    assert created.status_code == 200
    bundle_id = created.json()["bundle"]["id"]
    verify = client.post(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/verify"
    )
    assert verify.status_code == 200

    profile_id = "CONTROLLED_EVIDENCE_CORE_V1"
    run_response = client.post(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/validate-profile?profile={profile_id}"
    )
    assert run_response.status_code == 200
    run_id = run_response.json()["validationRun"]["id"]

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="reviewer-1"
    )
    denied_read = client.get(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/validation-status?profile={profile_id}"
    )
    denied_start = client.post(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/validate-profile?profile={profile_id}"
    )
    assert denied_read.status_code == 403
    assert denied_start.status_code == 403

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="auditor-1",
        platform_roles=("AUDITOR",),
    )
    auditor_read = client.get(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/validation-status?profile={profile_id}"
    )
    assert auditor_read.status_code == 200

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="admin-1",
        platform_roles=("ADMIN",),
    )
    terminal_cancel = client.post(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/validation-runs/{run_id}/cancel?profile={profile_id}"
    )
    assert terminal_cancel.status_code == 409

    now = datetime.now(UTC)
    running_run = BundleValidationRunRecord(
        id=f"{bundle_id}-validate-running",
        project_id="project-1",
        bundle_id=bundle_id,
        profile_id=profile_id,
        profile_snapshot_key=f"profiles/{profile_id.lower()}/snapshot.json",
        profile_snapshot_sha256="a" * 64,
        status="RUNNING",
        attempt_number=99,
        supersedes_validation_run_id=run_id,
        superseded_by_validation_run_id=None,
        result_json={},
        failure_reason=None,
        created_by="admin-1",
        created_at=now,
        started_at=now,
        finished_at=None,
        canceled_by=None,
        canceled_at=None,
    )
    key = (bundle_id, profile_id)
    service.bundle_validation_runs[key] = [
        running_run,
        replace_validation_run(
            service.bundle_validation_runs[key][0],
            superseded_by_validation_run_id=running_run.id,
        ),
        *service.bundle_validation_runs[key][1:],
    ]
    running_cancel = client.post(
        f"/projects/project-1/export-requests/request-1/bundles/{bundle_id}/validation-runs/{running_run.id}/cancel?profile={profile_id}"
    )
    assert running_cancel.status_code == 200
    assert running_cancel.json()["validationRun"]["status"] == "CANCELED"


def test_export_receipt_routes_and_internal_gateway_attach_flow() -> None:
    service = FakeExportService()
    service.requests["request-1"] = replace_request(
        service.requests["request-1"],
        status="APPROVED",
    )
    audit = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="researcher-1"
    )
    app.dependency_overrides[get_export_service] = lambda: service
    app.dependency_overrides[get_audit_service] = lambda: audit
    app.dependency_overrides[require_internal_export_gateway_service_account] = (
        lambda: "service-export-gateway"
    )

    attach_response = client.post(
        "/internal/export-requests/request-1/receipt",
        json={
            "receiptKey": "safeguarded/exports/project-1/request-1/receipt-1.json",
            "receiptSha256": "1" * 64,
            "exportedAt": datetime.now(UTC).isoformat(),
        },
    )
    assert attach_response.status_code == 200
    attach_payload = attach_response.json()
    assert attach_payload["request"]["status"] == "EXPORTED"
    assert attach_payload["receipt"]["attemptNumber"] == 1
    assert attach_payload["receipt"]["receiptKey"] == "receipt-1.json"

    current_receipt_response = client.get(
        "/projects/project-1/export-requests/request-1/receipt"
    )
    history_response = client.get(
        "/projects/project-1/export-requests/request-1/receipts"
    )
    assert current_receipt_response.status_code == 200
    assert history_response.status_code == 200
    assert len(history_response.json()["items"]) == 1

    event_types = {str(event.get("event_type")) for event in audit.recorded}
    assert "EXPORT_REQUEST_EXPORTED" in event_types
    assert "EXPORT_REQUEST_RECEIPT_VIEWED" in event_types
    assert "EXPORT_REQUEST_RECEIPTS_VIEWED" in event_types


def test_internal_receipt_attach_denies_without_gateway_auth_and_public_attach_is_blocked() -> None:
    service = FakeExportService()
    audit = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="researcher-1"
    )
    app.dependency_overrides[get_export_service] = lambda: service
    app.dependency_overrides[get_audit_service] = lambda: audit

    denied_internal = client.post(
        "/internal/export-requests/request-1/receipt",
        json={
            "receiptKey": "safeguarded/exports/project-1/request-1/receipt-1.json",
            "receiptSha256": "1" * 64,
            "exportedAt": datetime.now(UTC).isoformat(),
        },
    )
    assert denied_internal.status_code == 403

    public_attach = client.post(
        "/projects/project-1/export-requests/request-1/receipt",
        json={
            "receiptKey": "safeguarded/exports/project-1/request-1/receipt-1.json",
            "receiptSha256": "1" * 64,
            "exportedAt": datetime.now(UTC).isoformat(),
        },
    )
    assert public_attach.status_code in {404, 405}
    denied_events = [
        entry
        for entry in audit.recorded
        if entry.get("event_type") == "ACCESS_DENIED"
    ]
    assert len(denied_events) >= 1


def test_non_gateway_download_bypass_routes_are_absent() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="researcher-1"
    )
    app.dependency_overrides[get_export_service] = lambda: FakeExportService()
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()

    candidate_download = client.get(
        "/projects/project-1/export-candidates/candidate-1/download"
    )
    request_download = client.get(
        "/projects/project-1/export-requests/request-1/download"
    )
    bundle_download = client.get("/projects/project-1/export-bundles/request-1/download")
    assert candidate_download.status_code == 404
    assert request_download.status_code == 404
    assert bundle_download.status_code == 404


def test_export_review_queue_and_mutation_routes_emit_audit_events() -> None:
    service = FakeExportService()
    audit = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="reviewer-1"
    )
    app.dependency_overrides[get_export_service] = lambda: service
    app.dependency_overrides[get_audit_service] = lambda: audit

    queue_response = client.get("/projects/project-1/export-review")
    assert queue_response.status_code == 200
    queue_payload = queue_response.json()
    assert queue_payload["readOnly"] is False
    assert len(queue_payload["items"]) == 1

    claim_response = client.post(
        "/projects/project-1/export-requests/request-1/reviews/review-1/claim",
        json={"reviewEtag": "review-etag-1"},
    )
    assert claim_response.status_code == 200
    claim_payload = claim_response.json()
    claimed_etag = claim_payload["review"]["reviewEtag"]

    start_response = client.post(
        "/projects/project-1/export-requests/request-1/start-review",
        json={"reviewId": "review-1", "reviewEtag": claimed_etag},
    )
    assert start_response.status_code == 200
    start_payload = start_response.json()
    started_etag = start_payload["review"]["reviewEtag"]

    decision_response = client.post(
        "/projects/project-1/export-requests/request-1/decision",
        json={
            "reviewId": "review-1",
            "reviewEtag": started_etag,
            "decision": "APPROVE",
            "decisionReason": "Approved in route surface test.",
        },
    )
    assert decision_response.status_code == 200
    assert decision_response.json()["request"]["status"] == "APPROVED"

    event_types = {str(event.get("event_type")) for event in audit.recorded}
    assert "EXPORT_REVIEW_QUEUE_VIEWED" in event_types
    assert "EXPORT_REQUEST_REVIEW_CLAIMED" in event_types
    assert "EXPORT_REQUEST_REVIEW_STARTED" in event_types
    assert "EXPORT_REQUEST_APPROVED" in event_types


def test_export_review_auditor_queue_is_read_only() -> None:
    service = FakeExportService()
    audit = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="auditor-1",
        platform_roles=("AUDITOR",),
    )
    app.dependency_overrides[get_export_service] = lambda: service
    app.dependency_overrides[get_audit_service] = lambda: audit

    queue_response = client.get("/projects/project-1/export-review")
    assert queue_response.status_code == 200
    assert queue_response.json()["readOnly"] is True

    claim_response = client.post(
        "/projects/project-1/export-requests/request-1/reviews/review-1/claim",
        json={"reviewEtag": "review-etag-1"},
    )
    assert claim_response.status_code == 403


@pytest.mark.parametrize("actor_user_id", ["researcher-1", "lead-1"])
def test_export_review_mutation_routes_reject_non_reviewer_roles(actor_user_id: str) -> None:
    service = FakeExportService()
    audit = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id=actor_user_id
    )
    app.dependency_overrides[get_export_service] = lambda: service
    app.dependency_overrides[get_audit_service] = lambda: audit

    claim_response = client.post(
        "/projects/project-1/export-requests/request-1/reviews/review-1/claim",
        json={"reviewEtag": "review-etag-1"},
    )
    assert claim_response.status_code == 403


def test_export_route_maps_access_denied_to_403() -> None:
    service = FakeExportService()
    service.raise_access_denied = True
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="researcher-1"
    )
    app.dependency_overrides[get_export_service] = lambda: service
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()

    response = client.get("/projects/project-1/export-candidates")

    assert response.status_code == 403


def _principal(
    *,
    user_id: str,
    platform_roles: tuple[Literal["ADMIN", "AUDITOR"], ...] = (),
) -> SessionPrincipal:
    return SessionPrincipal(
        session_id=f"session-{user_id}",
        auth_source="bearer",
        user_id=user_id,
        oidc_sub=f"oidc-{user_id}",
        email=f"{user_id}@test.local",
        display_name=user_id,
        platform_roles=platform_roles,
        issued_at=datetime.now(UTC) - timedelta(minutes=5),
        expires_at=datetime.now(UTC) + timedelta(minutes=55),
        csrf_token=f"csrf-{user_id}",
    )
