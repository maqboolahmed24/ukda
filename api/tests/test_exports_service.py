from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
import hashlib
from types import SimpleNamespace
from typing import Literal

import pytest
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
    ExportOperationsMaintenanceResult,
    ExportOperationsStatusRecord,
    ExportReceiptRecord,
    ProvenanceProofRecord,
    ExportRequestEventRecord,
    ExportRequestListPage,
    ExportRequestRecord,
    ExportRequestReviewEventRecord,
    ExportRequestReviewRecord,
)
from app.exports.service import (
    ExportAccessDeniedError,
    ExportConflictError,
    ExportNotFoundError,
    ExportService,
    ExportValidationError,
)
from app.exports.store import ExportStoreConflictError, ExportStoreNotFoundError
from app.projects.models import ProjectSummary
from app.projects.service import (
    ProjectAccessDeniedError,
    ProjectWorkspaceContext,
)
from app.projects.store import ProjectNotFoundError


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


class FakeProjectService:
    def __init__(self, role_map: dict[str, Literal["PROJECT_LEAD", "RESEARCHER", "REVIEWER"]]):
        self._role_map = dict(role_map)

    def resolve_workspace_context(  # type: ignore[no-untyped-def]
        self, *, current_user: SessionPrincipal, project_id: str
    ) -> ProjectWorkspaceContext:
        if project_id != "project-1":
            raise ProjectNotFoundError("Project not found.")

        if "ADMIN" in set(current_user.platform_roles):
            summary = ProjectSummary(
                id=project_id,
                name="Project",
                purpose="Export request service tests.",
                status="ACTIVE",
                created_by="owner-1",
                created_at=datetime.now(UTC),
                intended_access_tier="SAFEGUARDED",
                baseline_policy_snapshot_id="baseline-v1",
                current_user_role=None,
            )
            return ProjectWorkspaceContext(
                summary=summary,
                is_member=False,
                can_access_settings=True,
                can_manage_members=True,
            )

        role = self._role_map.get(current_user.user_id)
        if role is None:
            raise ProjectAccessDeniedError("Membership is required for this project route.")
        summary = ProjectSummary(
            id=project_id,
            name="Project",
            purpose="Export request service tests.",
            status="ACTIVE",
            created_by="owner-1",
            created_at=datetime.now(UTC),
            intended_access_tier="SAFEGUARDED",
            baseline_policy_snapshot_id="baseline-v1",
            current_user_role=role,
        )
        return ProjectWorkspaceContext(
            summary=summary,
            is_member=True,
            can_access_settings=role == "PROJECT_LEAD",
            can_manage_members=role == "PROJECT_LEAD",
        )


class InMemoryExportStore:
    def __init__(self, candidates: tuple[ExportCandidateSnapshotRecord, ...]) -> None:
        self._candidates: dict[str, ExportCandidateSnapshotRecord] = {
            item.id: item for item in candidates
        }
        self._requests: dict[str, ExportRequestRecord] = {}
        self._request_events: dict[str, list[ExportRequestEventRecord]] = {}
        self._request_reviews: dict[str, list[ExportRequestReviewRecord]] = {}
        self._request_review_events: dict[str, list[ExportRequestReviewEventRecord]] = {}
        self._request_receipts: dict[str, list[ExportReceiptRecord]] = {}
        self._provenance_proofs: dict[str, list[ProvenanceProofRecord]] = {}
        self._provenance_artifacts: dict[str, dict[str, object]] = {}
        self._deposit_bundles: dict[str, list[DepositBundleRecord]] = {}
        self._bundle_events: dict[str, list[BundleEventRecord]] = {}
        self._bundle_artifacts: dict[str, dict[str, object]] = {}
        self._bundle_verification_projections: dict[str, BundleVerificationProjectionRecord] = {}
        self._bundle_verification_runs: dict[str, list[BundleVerificationRunRecord]] = {}
        self._bundle_validation_projections: dict[
            tuple[str, str], BundleValidationProjectionRecord
        ] = {}
        self._bundle_validation_runs: dict[
            tuple[str, str], list[BundleValidationRunRecord]
        ] = {}

    @staticmethod
    def _active_review(
        reviews: list[ExportRequestReviewRecord],
    ) -> ExportRequestReviewRecord | None:
        ordered = sorted(
            reviews,
            key=lambda item: (1 if item.review_stage == "PRIMARY" else 2, item.id),
        )
        for review in ordered:
            if not review.is_required:
                continue
            if review.status == "APPROVED":
                continue
            if review.status in {"RETURNED", "REJECTED"}:
                return None
            return review
        return None

    def sync_phase6_candidate_snapshots(self, *, project_id: str, actor_user_id: str) -> int:
        _ = (project_id, actor_user_id)
        return 0

    def list_candidates(
        self,
        *,
        project_id: str,
        include_superseded: bool = False,
    ) -> tuple[ExportCandidateSnapshotRecord, ...]:
        candidates = [
            item for item in self._candidates.values() if item.project_id == project_id
        ]
        if not include_superseded:
            superseded_ids = {
                item.supersedes_candidate_snapshot_id
                for item in candidates
                if item.supersedes_candidate_snapshot_id is not None
            }
            candidates = [
                item
                for item in candidates
                if item.eligibility_status == "ELIGIBLE" and item.id not in superseded_ids
            ]
        candidates.sort(key=lambda item: (item.created_at, item.id), reverse=True)
        return tuple(candidates)

    def get_candidate(self, *, project_id: str, candidate_id: str) -> ExportCandidateSnapshotRecord:
        candidate = self._candidates.get(candidate_id)
        if candidate is None or candidate.project_id != project_id:
            raise ExportStoreNotFoundError("Export candidate snapshot not found.")
        return candidate

    def create_request(self, **kwargs) -> ExportRequestRecord:  # type: ignore[no-untyped-def]
        request_id = str(kwargs["request_id"])
        project_id = str(kwargs["project_id"])
        supersedes_export_request_id = kwargs.get("supersedes_export_request_id")
        now = datetime.now(UTC)

        predecessor = None
        if isinstance(supersedes_export_request_id, str):
            predecessor = self._requests.get(supersedes_export_request_id)
            if predecessor is None:
                raise ExportStoreConflictError(
                    "Only unsuperseded RETURNED requests can be resubmitted."
                )
            if (
                predecessor.status != "RETURNED"
                or predecessor.superseded_by_export_request_id is not None
            ):
                raise ExportStoreConflictError(
                    "Only unsuperseded RETURNED requests can be resubmitted."
                )

        record = ExportRequestRecord(
            id=request_id,
            project_id=project_id,
            candidate_snapshot_id=str(kwargs["candidate_snapshot_id"]),
            candidate_origin_phase=kwargs["candidate_origin_phase"],
            candidate_kind=kwargs["candidate_kind"],
            bundle_profile=kwargs.get("bundle_profile"),
            risk_classification=kwargs["risk_classification"],
            risk_reason_codes_json=tuple(kwargs["risk_reason_codes_json"]),
            review_path=kwargs["review_path"],
            requires_second_review=bool(kwargs["requires_second_review"]),
            supersedes_export_request_id=(
                str(supersedes_export_request_id)
                if isinstance(supersedes_export_request_id, str)
                else None
            ),
            superseded_by_export_request_id=None,
            request_revision=int(kwargs["request_revision"]),
            purpose_statement=str(kwargs["purpose_statement"]),
            status=kwargs["status"],
            submitted_by=str(kwargs["submitted_by"]),
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
            release_pack_key=str(kwargs["release_pack_key"]),
            release_pack_sha256=str(kwargs["release_pack_sha256"]),
            release_pack_json=dict(kwargs["release_pack_json"]),
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
        self._requests[request_id] = record
        if predecessor is not None:
            self._requests[predecessor.id] = replace(
                predecessor,
                superseded_by_export_request_id=request_id,
                updated_at=now,
            )

        event_type = (
            "REQUEST_RESUBMITTED"
            if record.status == "RESUBMITTED"
            else "REQUEST_SUBMITTED"
        )
        self._request_events[request_id] = [
            ExportRequestEventRecord(
                id=f"{request_id}-event-1",
                export_request_id=request_id,
                event_type=event_type,
                from_status=None,
                to_status=record.status,
                actor_user_id=record.submitted_by,
                reason=None,
                created_at=now,
            )
        ]

        review_rows: list[ExportRequestReviewRecord] = [
            ExportRequestReviewRecord(
                id=f"{request_id}-review-primary",
                export_request_id=request_id,
                review_stage="PRIMARY",
                is_required=True,
                status="PENDING",
                assigned_reviewer_user_id=None,
                assigned_at=None,
                acted_by_user_id=None,
                acted_at=None,
                decision_reason=None,
                return_comment=None,
                review_etag=f"{request_id}-etag-primary",
                created_at=now,
                updated_at=now,
            )
        ]
        if record.requires_second_review:
            review_rows.append(
                ExportRequestReviewRecord(
                    id=f"{request_id}-review-secondary",
                    export_request_id=request_id,
                    review_stage="SECONDARY",
                    is_required=True,
                    status="PENDING",
                    assigned_reviewer_user_id=None,
                    assigned_at=None,
                    acted_by_user_id=None,
                    acted_at=None,
                    decision_reason=None,
                    return_comment=None,
                    review_etag=f"{request_id}-etag-secondary",
                    created_at=now,
                    updated_at=now,
                )
            )
        self._request_reviews[request_id] = review_rows
        self._request_review_events[request_id] = [
            ExportRequestReviewEventRecord(
                id=f"{review.id}-created",
                review_id=review.id,
                export_request_id=request_id,
                review_stage=review.review_stage,
                event_type="REVIEW_CREATED",
                actor_user_id=record.submitted_by,
                assigned_reviewer_user_id=None,
                decision_reason=None,
                return_comment=None,
                created_at=now,
            )
            for review in review_rows
        ]
        return record

    def list_requests(self, **kwargs) -> ExportRequestListPage:  # type: ignore[no-untyped-def]
        project_id = str(kwargs["project_id"])
        status = kwargs.get("status")
        requester_id = kwargs.get("requester_id")
        candidate_kind = kwargs.get("candidate_kind")
        cursor = int(kwargs.get("cursor", 0))
        limit = int(kwargs.get("limit", 50))

        rows = [item for item in self._requests.values() if item.project_id == project_id]
        if isinstance(status, str):
            rows = [item for item in rows if item.status == status]
        if isinstance(requester_id, str):
            rows = [item for item in rows if item.submitted_by == requester_id]
        if isinstance(candidate_kind, str):
            rows = [item for item in rows if item.candidate_kind == candidate_kind]
        rows.sort(key=lambda item: (item.submitted_at, item.id), reverse=True)
        page_rows = rows[cursor : cursor + limit]
        next_cursor = cursor + limit if cursor + limit < len(rows) else None
        return ExportRequestListPage(items=tuple(page_rows), next_cursor=next_cursor)

    def get_request(self, *, project_id: str, export_request_id: str) -> ExportRequestRecord:
        request = self._requests.get(export_request_id)
        if request is None or request.project_id != project_id:
            raise ExportStoreNotFoundError("Export request not found.")
        return request

    def list_request_events(
        self, *, export_request_id: str
    ) -> tuple[ExportRequestEventRecord, ...]:
        return tuple(self._request_events.get(export_request_id, []))

    def list_request_reviews(
        self, *, export_request_id: str
    ) -> tuple[ExportRequestReviewRecord, ...]:
        return tuple(self._request_reviews.get(export_request_id, []))

    def list_request_review_events(
        self, *, export_request_id: str
    ) -> tuple[ExportRequestReviewEventRecord, ...]:
        return tuple(self._request_review_events.get(export_request_id, []))

    def list_request_receipts(
        self,
        *,
        project_id: str,
        export_request_id: str,
    ) -> tuple[ExportReceiptRecord, ...]:
        request = self._requests.get(export_request_id)
        if request is None or request.project_id != project_id:
            raise ExportStoreNotFoundError("Export request not found.")
        return tuple(self._request_receipts.get(export_request_id, []))

    def generate_provenance_proof(self, **kwargs) -> ProvenanceProofRecord:  # type: ignore[no-untyped-def]
        project_id = str(kwargs["project_id"])
        export_request_id = str(kwargs["export_request_id"])
        actor_user_id = str(kwargs["actor_user_id"])
        force_regenerate = bool(kwargs.get("force_regenerate", False))
        request = self._requests.get(export_request_id)
        if request is None or request.project_id != project_id:
            raise ExportStoreNotFoundError("Export request not found.")
        if request.status not in {"APPROVED", "EXPORTED"}:
            raise ExportStoreConflictError(
                "Provenance proofs require an APPROVED or EXPORTED export request."
            )
        history = list(self._provenance_proofs.get(export_request_id, []))
        current = next((item for item in history if item.superseded_by_proof_id is None), None)
        if current is not None and not force_regenerate:
            return current

        now = datetime.now(UTC)
        attempt_number = (history[0].attempt_number + 1) if history else 1
        supersedes_id = current.id if current is not None else None
        proof_id = f"{export_request_id}-proof-{attempt_number}"
        root_sha = hashlib.sha256(
            f"{request.candidate_snapshot_id}|{request.release_pack_sha256}|{attempt_number}".encode(
                "utf-8"
            )
        ).hexdigest()
        signature_key_ref = "ukde-provenance-lamport-v1"
        signature_bytes_key = (
            f"controlled/derived/provenance/{project_id}/export-requests/{export_request_id}/"
            f"proofs/{proof_id}/signature.bin"
        )
        proof_artifact_key = (
            f"controlled/derived/provenance/{project_id}/export-requests/{export_request_id}/"
            f"proofs/{proof_id}/proof.json"
        )
        artifact = {
            "schemaVersion": 1,
            "proofId": proof_id,
            "projectId": project_id,
            "exportRequestId": export_request_id,
            "candidateSnapshotId": request.candidate_snapshot_id,
            "attemptNumber": attempt_number,
            "merkle": {
                "algorithm": "SHA-256",
                "leafCount": 1,
                "rootSha256": root_sha,
            },
            "leaves": [
                {
                    "artifact_kind": "EXPORT_REQUEST",
                    "stable_identifier": export_request_id,
                    "immutable_reference": request.release_pack_sha256,
                    "parent_references": [],
                }
            ],
            "signature": {
                "algorithm": "LAMPORT_SHA256_OTS_V1",
                "keyRef": signature_key_ref,
                "signatureBase64": "",
            },
            "verificationMaterial": {
                "publicKeyAlgorithm": "LAMPORT_SHA256_OTS_V1",
                "publicKeyBase64": "",
                "publicKeySha256": hashlib.sha256(proof_id.encode("utf-8")).hexdigest(),
                "rootHashAlgorithm": "SHA-256",
            },
        }
        artifact_sha = hashlib.sha256(
            str(artifact).encode("utf-8")
        ).hexdigest()
        proof = ProvenanceProofRecord(
            id=proof_id,
            project_id=project_id,
            export_request_id=export_request_id,
            candidate_snapshot_id=request.candidate_snapshot_id,
            attempt_number=attempt_number,
            supersedes_proof_id=supersedes_id,
            superseded_by_proof_id=None,
            root_sha256=root_sha,
            signature_key_ref=signature_key_ref,
            signature_bytes_key=signature_bytes_key,
            proof_artifact_key=proof_artifact_key,
            proof_artifact_sha256=artifact_sha,
            created_by=actor_user_id,
            created_at=now,
        )
        if current is not None:
            history = [
                replace(
                    item,
                    superseded_by_proof_id=proof_id,
                )
                if item.id == current.id
                else item
                for item in history
            ]
        history.insert(0, proof)
        self._provenance_proofs[export_request_id] = history
        self._provenance_artifacts[proof.id] = artifact
        return proof

    def list_provenance_proofs(self, **kwargs) -> tuple[ProvenanceProofRecord, ...]:  # type: ignore[no-untyped-def]
        project_id = str(kwargs["project_id"])
        export_request_id = str(kwargs["export_request_id"])
        request = self._requests.get(export_request_id)
        if request is None or request.project_id != project_id:
            raise ExportStoreNotFoundError("Export request not found.")
        return tuple(self._provenance_proofs.get(export_request_id, ()))

    def get_current_provenance_proof(self, **kwargs) -> ProvenanceProofRecord:  # type: ignore[no-untyped-def]
        project_id = str(kwargs["project_id"])
        export_request_id = str(kwargs["export_request_id"])
        request = self._requests.get(export_request_id)
        if request is None or request.project_id != project_id:
            raise ExportStoreNotFoundError("Export request not found.")
        current = next(
            (
                item
                for item in self._provenance_proofs.get(export_request_id, [])
                if item.superseded_by_proof_id is None
            ),
            None,
        )
        if current is None:
            raise ExportStoreNotFoundError("Current provenance proof not found.")
        return current

    def get_provenance_proof(self, **kwargs) -> ProvenanceProofRecord:  # type: ignore[no-untyped-def]
        project_id = str(kwargs["project_id"])
        export_request_id = str(kwargs["export_request_id"])
        proof_id = str(kwargs["proof_id"])
        request = self._requests.get(export_request_id)
        if request is None or request.project_id != project_id:
            raise ExportStoreNotFoundError("Export request not found.")
        match = next(
            (
                item
                for item in self._provenance_proofs.get(export_request_id, [])
                if item.id == proof_id
            ),
            None,
        )
        if match is None:
            raise ExportStoreNotFoundError("Provenance proof not found.")
        return match

    def read_provenance_proof_artifact(self, **kwargs) -> dict[str, object]:  # type: ignore[no-untyped-def]
        proof = kwargs["proof"]
        if not isinstance(proof, ProvenanceProofRecord):
            raise ExportStoreNotFoundError("Provenance proof not found.")
        artifact = self._provenance_artifacts.get(proof.id)
        if artifact is None:
            raise ExportStoreNotFoundError("Provenance proof not found.")
        return dict(artifact)

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

    def _build_bundle_attempt(
        self,
        *,
        project_id: str,
        export_request_id: str,
        bundle_kind: str,
        actor_user_id: str,
        force_rebuild: bool,
        rebuild_requested_bundle_id: str | None = None,
    ) -> DepositBundleRecord:
        request = self._requests.get(export_request_id)
        if request is None or request.project_id != project_id:
            raise ExportStoreNotFoundError("Export request not found.")
        if request.status not in {"APPROVED", "EXPORTED"}:
            raise ExportStoreConflictError(
                "Deposit bundles require an APPROVED or EXPORTED export request."
            )
        candidate = self._candidates.get(request.candidate_snapshot_id)
        if candidate is None:
            raise ExportStoreConflictError("Pinned candidate snapshot is unavailable.")
        current_proof = self.get_current_provenance_proof(
            project_id=project_id,
            export_request_id=export_request_id,
        )
        proof_artifact = self.read_provenance_proof_artifact(proof=current_proof)
        history = list(self._deposit_bundles.get(export_request_id, []))
        current = next(
            (
                item
                for item in history
                if item.bundle_kind == bundle_kind
                and item.candidate_snapshot_id == request.candidate_snapshot_id
                and item.superseded_by_bundle_id is None
            ),
            None,
        )
        if current is not None and not force_rebuild:
            return current

        same_lineage_attempts = [
            item
            for item in history
            if item.bundle_kind == bundle_kind
            and item.candidate_snapshot_id == request.candidate_snapshot_id
        ]
        attempt_number = (max(item.attempt_number for item in same_lineage_attempts) + 1) if same_lineage_attempts else 1
        now = datetime.now(UTC)
        bundle_id = f"{export_request_id}-{bundle_kind.lower()}-{attempt_number}"
        supersedes_bundle_id = current.id if current is not None else None

        bundle_key = self._bundle_key(
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
            kind=bundle_kind,
        )
        artifact = {
            "archiveEntries": [
                "bundle/metadata.json",
                "bundle/provenance-proof.json",
                "bundle/provenance-signature.json",
                "bundle/provenance-verification-material.json",
            ],
            "metadata": {
                "bundleId": bundle_id,
                "bundleKind": bundle_kind,
                "bundleAttemptNumber": attempt_number,
                "exportRequest": {
                    "id": request.id,
                    "finalReviewId": request.final_review_id,
                    "finalDecisionBy": request.final_decision_by,
                    "finalDecisionAt": (
                        request.final_decision_at.isoformat()
                        if request.final_decision_at is not None
                        else None
                    ),
                },
                "candidateSnapshot": {
                    "id": candidate.id,
                    "candidateSha256": candidate.candidate_sha256,
                },
                "governanceReferences": {
                    "manifestId": candidate.governance_manifest_id,
                    "ledgerId": candidate.governance_ledger_id,
                    "manifestSha256": candidate.governance_manifest_sha256,
                    "ledgerSha256": candidate.governance_ledger_sha256,
                },
                "policyLineage": {
                    "policySnapshotHash": candidate.policy_snapshot_hash,
                    "policyId": candidate.policy_id,
                    "policyVersion": candidate.policy_version,
                },
                "metadata": {
                    "releasePackSha256": request.release_pack_sha256,
                },
                "provenanceProof": {
                    "proofId": current_proof.id,
                    "rootSha256": current_proof.root_sha256,
                    "proofArtifactSha256": current_proof.proof_artifact_sha256,
                },
                "exportReceiptMetadata": (
                    {
                        "receiptId": request.receipt_id,
                        "receiptSha256": request.receipt_sha256,
                    }
                    if request.receipt_id is not None or request.receipt_sha256 is not None
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
        artifact_sha = hashlib.sha256(
            str(artifact).encode("utf-8")
        ).hexdigest()

        bundle = DepositBundleRecord(
            id=bundle_id,
            project_id=project_id,
            export_request_id=export_request_id,
            candidate_snapshot_id=request.candidate_snapshot_id,
            provenance_proof_id=current_proof.id,
            provenance_proof_artifact_sha256=current_proof.proof_artifact_sha256,
            bundle_kind=bundle_kind,  # type: ignore[arg-type]
            status="SUCCEEDED",
            attempt_number=attempt_number,
            supersedes_bundle_id=supersedes_bundle_id,
            superseded_by_bundle_id=None,
            bundle_key=bundle_key,
            bundle_sha256=artifact_sha,
            failure_reason=None,
            created_by=actor_user_id,
            created_at=now,
            started_at=now,
            finished_at=now,
            canceled_by=None,
            canceled_at=None,
        )
        if current is not None:
            history = [
                replace(item, superseded_by_bundle_id=bundle.id) if item.id == current.id else item
                for item in history
            ]
        history.insert(0, bundle)
        self._deposit_bundles[export_request_id] = history
        self._bundle_artifacts[bundle.id] = artifact
        self._bundle_verification_projections[bundle.id] = BundleVerificationProjectionRecord(
            bundle_id=bundle.id,
            status="PENDING",
            last_verification_run_id=None,
            verified_at=None,
            updated_at=now,
        )
        events = list(self._bundle_events.get(bundle.id, []))
        if force_rebuild:
            events.append(
                BundleEventRecord(
                    id=f"{bundle.id}-event-rebuild",
                    bundle_id=bundle.id,
                    event_type="BUNDLE_REBUILD_REQUESTED",
                    verification_run_id=None,
                    validation_run_id=None,
                    actor_user_id=actor_user_id,
                    reason=(
                        f"requested_from:{rebuild_requested_bundle_id}"
                        if rebuild_requested_bundle_id is not None
                        else None
                    ),
                    created_at=now,
                )
            )
        events.extend(
            [
                BundleEventRecord(
                    id=f"{bundle.id}-event-queued",
                    bundle_id=bundle.id,
                    event_type="BUNDLE_BUILD_QUEUED",
                    verification_run_id=None,
                    validation_run_id=None,
                    actor_user_id=actor_user_id,
                    reason=None,
                    created_at=now + timedelta(microseconds=1),
                ),
                BundleEventRecord(
                    id=f"{bundle.id}-event-started",
                    bundle_id=bundle.id,
                    event_type="BUNDLE_BUILD_STARTED",
                    verification_run_id=None,
                    validation_run_id=None,
                    actor_user_id=actor_user_id,
                    reason=None,
                    created_at=now + timedelta(microseconds=2),
                ),
                BundleEventRecord(
                    id=f"{bundle.id}-event-succeeded",
                    bundle_id=bundle.id,
                    event_type="BUNDLE_BUILD_SUCCEEDED",
                    verification_run_id=None,
                    validation_run_id=None,
                    actor_user_id=actor_user_id,
                    reason=f"bundle_sha256:{artifact_sha}",
                    created_at=now + timedelta(microseconds=3),
                ),
            ]
        )
        self._bundle_events[bundle.id] = events
        return bundle

    def create_or_get_deposit_bundle(self, **kwargs) -> DepositBundleRecord:  # type: ignore[no-untyped-def]
        return self._build_bundle_attempt(
            project_id=str(kwargs["project_id"]),
            export_request_id=str(kwargs["export_request_id"]),
            bundle_kind=str(kwargs["bundle_kind"]),
            actor_user_id=str(kwargs["actor_user_id"]),
            force_rebuild=False,
        )

    def rebuild_deposit_bundle(self, **kwargs) -> DepositBundleRecord:  # type: ignore[no-untyped-def]
        project_id = str(kwargs["project_id"])
        export_request_id = str(kwargs["export_request_id"])
        bundle_id = str(kwargs["bundle_id"])
        actor_user_id = str(kwargs["actor_user_id"])
        target = self.get_deposit_bundle(
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
        )
        return self._build_bundle_attempt(
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_kind=target.bundle_kind,
            actor_user_id=actor_user_id,
            force_rebuild=True,
            rebuild_requested_bundle_id=bundle_id,
        )

    def list_deposit_bundles(self, **kwargs) -> tuple[DepositBundleRecord, ...]:  # type: ignore[no-untyped-def]
        project_id = str(kwargs["project_id"])
        export_request_id = str(kwargs["export_request_id"])
        request = self._requests.get(export_request_id)
        if request is None or request.project_id != project_id:
            raise ExportStoreNotFoundError("Export request not found.")
        return tuple(self._deposit_bundles.get(export_request_id, []))

    def get_deposit_bundle(self, **kwargs) -> DepositBundleRecord:  # type: ignore[no-untyped-def]
        project_id = str(kwargs["project_id"])
        export_request_id = str(kwargs["export_request_id"])
        bundle_id = str(kwargs["bundle_id"])
        request = self._requests.get(export_request_id)
        if request is None or request.project_id != project_id:
            raise ExportStoreNotFoundError("Export request not found.")
        match = next(
            (item for item in self._deposit_bundles.get(export_request_id, []) if item.id == bundle_id),
            None,
        )
        if match is None:
            raise ExportStoreNotFoundError("Deposit bundle not found.")
        return match

    def get_deposit_bundle_status(self, **kwargs) -> DepositBundleRecord:  # type: ignore[no-untyped-def]
        return self.get_deposit_bundle(**kwargs)

    def list_deposit_bundle_events(self, **kwargs) -> tuple[BundleEventRecord, ...]:  # type: ignore[no-untyped-def]
        bundle = self.get_deposit_bundle(
            project_id=str(kwargs["project_id"]),
            export_request_id=str(kwargs["export_request_id"]),
            bundle_id=str(kwargs["bundle_id"]),
        )
        events = sorted(
            self._bundle_events.get(bundle.id, []),
            key=lambda item: (item.created_at, item.id),
        )
        return tuple(events)

    def get_bundle_verification_projection(self, **kwargs):  # type: ignore[no-untyped-def]
        bundle = self.get_deposit_bundle(
            project_id=str(kwargs["project_id"]),
            export_request_id=str(kwargs["export_request_id"]),
            bundle_id=str(kwargs["bundle_id"]),
        )
        return self._bundle_verification_projections.get(bundle.id)

    def list_bundle_verification_runs(
        self, **kwargs
    ) -> tuple[BundleVerificationRunRecord, ...]:  # type: ignore[no-untyped-def]
        bundle = self.get_deposit_bundle(
            project_id=str(kwargs["project_id"]),
            export_request_id=str(kwargs["export_request_id"]),
            bundle_id=str(kwargs["bundle_id"]),
        )
        runs = sorted(
            self._bundle_verification_runs.get(bundle.id, []),
            key=lambda item: (item.attempt_number, item.created_at, item.id),
            reverse=True,
        )
        return tuple(runs)

    def get_bundle_verification_run(
        self, **kwargs
    ) -> BundleVerificationRunRecord:  # type: ignore[no-untyped-def]
        bundle = self.get_deposit_bundle(
            project_id=str(kwargs["project_id"]),
            export_request_id=str(kwargs["export_request_id"]),
            bundle_id=str(kwargs["bundle_id"]),
        )
        verification_run_id = str(kwargs["verification_run_id"])
        run = next(
            (
                item
                for item in self._bundle_verification_runs.get(bundle.id, [])
                if item.id == verification_run_id
            ),
            None,
        )
        if run is None:
            raise ExportStoreNotFoundError("Bundle verification run not found.")
        return run

    def get_current_bundle_verification_run(
        self, **kwargs
    ) -> BundleVerificationRunRecord | None:  # type: ignore[no-untyped-def]
        bundle = self.get_deposit_bundle(
            project_id=str(kwargs["project_id"]),
            export_request_id=str(kwargs["export_request_id"]),
            bundle_id=str(kwargs["bundle_id"]),
        )
        return next(
            (
                item
                for item in self._bundle_verification_runs.get(bundle.id, [])
                if item.superseded_by_verification_run_id is None
            ),
            None,
        )

    def create_bundle_verification_run(
        self, **kwargs
    ) -> BundleVerificationRunRecord:  # type: ignore[no-untyped-def]
        project_id = str(kwargs["project_id"])
        export_request_id = str(kwargs["export_request_id"])
        bundle_id = str(kwargs["bundle_id"])
        actor_user_id = str(kwargs["actor_user_id"])
        bundle = self.get_deposit_bundle(
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
        )
        if bundle.status != "SUCCEEDED":
            raise ExportStoreConflictError(
                "Bundle verification requires a SUCCEEDED bundle attempt."
            )
        artifact = self._bundle_artifacts.get(bundle.id)
        if artifact is None:
            raise ExportStoreConflictError(
                "Bundle verification requires an immutable succeeded bundle artifact."
            )
        runs = list(self._bundle_verification_runs.get(bundle.id, []))
        current = next((item for item in runs if item.superseded_by_verification_run_id is None), None)
        attempt_number = (max((item.attempt_number for item in runs), default=0) + 1)
        now = datetime.now(UTC)
        run_id = f"{bundle.id}-verify-{attempt_number}"
        computed_sha = hashlib.sha256(str(artifact).encode("utf-8")).hexdigest()
        failures: list[str] = []
        signature_payload = artifact.get("provenanceSignature")
        signature_status = "VALID"
        if not isinstance(signature_payload, dict):
            signature_status = "MISSING"
            failures.append("Bundle proof signature material is missing or incomplete.")
        if computed_sha != bundle.bundle_sha256:
            failures.append("Bundle archive hash does not match the pinned immutable hash.")
        result = "VALID" if not failures else "INVALID"
        run_status = "SUCCEEDED" if result == "VALID" else "FAILED"
        failure_reason = "; ".join(failures)[:5000] if failures else None
        run = BundleVerificationRunRecord(
            id=run_id,
            project_id=project_id,
            bundle_id=bundle.id,
            attempt_number=attempt_number,
            supersedes_verification_run_id=current.id if current is not None else None,
            superseded_by_verification_run_id=None,
            status=run_status,  # type: ignore[arg-type]
            result_json={
                "verificationResult": result,
                "bundleSha256": bundle.bundle_sha256,
                "rootSha256": (
                    artifact.get("provenanceProofArtifact", {})
                    .get("merkle", {})
                    .get("rootSha256")
                    if isinstance(artifact.get("provenanceProofArtifact"), dict)
                    else None
                ),
                "signatureStatus": signature_status,
                "failures": failures,
            },
            created_by=actor_user_id,
            created_at=now,
            started_at=now,
            finished_at=now,
            canceled_by=None,
            canceled_at=None,
            failure_reason=failure_reason,
        )
        if current is not None:
            runs = [
                replace(item, superseded_by_verification_run_id=run.id)
                if item.id == current.id
                else item
                for item in runs
            ]
        runs.insert(0, run)
        self._bundle_verification_runs[bundle.id] = runs

        projection = self._bundle_verification_projections.get(bundle.id)
        if projection is None:
            projection = BundleVerificationProjectionRecord(
                bundle_id=bundle.id,
                status="PENDING",
                last_verification_run_id=None,
                verified_at=None,
                updated_at=now,
            )
        if run.status == "SUCCEEDED":
            projection = replace(
                projection,
                status="VERIFIED",
                last_verification_run_id=run.id,
                verified_at=now,
                updated_at=now,
            )
            event_type = "BUNDLE_VERIFICATION_SUCCEEDED"
        else:
            if projection.status != "VERIFIED":
                projection = replace(
                    projection,
                    status="FAILED",
                    last_verification_run_id=run.id,
                    verified_at=None,
                    updated_at=now,
                )
            else:
                projection = replace(projection, updated_at=now)
            event_type = "BUNDLE_VERIFICATION_FAILED"
        self._bundle_verification_projections[bundle.id] = projection

        self._bundle_events.setdefault(bundle.id, []).extend(
            [
                BundleEventRecord(
                    id=f"{run.id}-event-started",
                    bundle_id=bundle.id,
                    event_type="BUNDLE_VERIFICATION_STARTED",
                    verification_run_id=run.id,
                    validation_run_id=None,
                    actor_user_id=actor_user_id,
                    reason=None,
                    created_at=now + timedelta(microseconds=1),
                ),
                BundleEventRecord(
                    id=f"{run.id}-event-terminal",
                    bundle_id=bundle.id,
                    event_type=event_type,  # type: ignore[arg-type]
                    verification_run_id=run.id,
                    validation_run_id=None,
                    actor_user_id=actor_user_id,
                    reason=run.failure_reason,
                    created_at=now + timedelta(microseconds=2),
                ),
            ]
        )
        return run

    def cancel_bundle_verification_run(
        self, **kwargs
    ) -> BundleVerificationRunRecord:  # type: ignore[no-untyped-def]
        bundle = self.get_deposit_bundle(
            project_id=str(kwargs["project_id"]),
            export_request_id=str(kwargs["export_request_id"]),
            bundle_id=str(kwargs["bundle_id"]),
        )
        verification_run_id = str(kwargs["verification_run_id"])
        actor_user_id = str(kwargs["actor_user_id"])
        run = self.get_bundle_verification_run(
            project_id=str(kwargs["project_id"]),
            export_request_id=str(kwargs["export_request_id"]),
            bundle_id=bundle.id,
            verification_run_id=verification_run_id,
        )
        if run.status not in {"QUEUED", "RUNNING"}:
            raise ExportStoreConflictError(
                "Bundle verification cancel is allowed only for QUEUED or RUNNING runs."
            )
        now = datetime.now(UTC)
        canceled = replace(
            run,
            status="CANCELED",
            canceled_by=actor_user_id,
            canceled_at=now,
            finished_at=now,
            failure_reason="Bundle verification run canceled.",
        )
        self._bundle_verification_runs[bundle.id] = [
            canceled if item.id == run.id else item
            for item in self._bundle_verification_runs.get(bundle.id, [])
        ]
        self._bundle_events.setdefault(bundle.id, []).append(
            BundleEventRecord(
                id=f"{run.id}-event-canceled",
                bundle_id=bundle.id,
                event_type="BUNDLE_VERIFICATION_CANCELED",
                verification_run_id=run.id,
                validation_run_id=None,
                actor_user_id=actor_user_id,
                reason="Bundle verification run canceled.",
                created_at=now,
            )
        )
        return canceled

    def list_bundle_profiles(self) -> tuple[BundleProfileRecord, ...]:
        return list_bundle_profiles()

    def get_bundle_validation_projection(
        self, **kwargs
    ) -> BundleValidationProjectionRecord | None:  # type: ignore[no-untyped-def]
        bundle = self.get_deposit_bundle(
            project_id=str(kwargs["project_id"]),
            export_request_id=str(kwargs["export_request_id"]),
            bundle_id=str(kwargs["bundle_id"]),
        )
        profile_id = str(kwargs["profile_id"]).strip().upper()
        return self._bundle_validation_projections.get((bundle.id, profile_id))

    def list_bundle_validation_runs(
        self, **kwargs
    ) -> tuple[BundleValidationRunRecord, ...]:  # type: ignore[no-untyped-def]
        bundle = self.get_deposit_bundle(
            project_id=str(kwargs["project_id"]),
            export_request_id=str(kwargs["export_request_id"]),
            bundle_id=str(kwargs["bundle_id"]),
        )
        profile_id = str(kwargs["profile_id"]).strip().upper()
        runs = sorted(
            self._bundle_validation_runs.get((bundle.id, profile_id), []),
            key=lambda item: (item.attempt_number, item.created_at, item.id),
            reverse=True,
        )
        return tuple(runs)

    def get_bundle_validation_run(
        self, **kwargs
    ) -> BundleValidationRunRecord:  # type: ignore[no-untyped-def]
        bundle = self.get_deposit_bundle(
            project_id=str(kwargs["project_id"]),
            export_request_id=str(kwargs["export_request_id"]),
            bundle_id=str(kwargs["bundle_id"]),
        )
        profile_id = str(kwargs["profile_id"]).strip().upper()
        validation_run_id = str(kwargs["validation_run_id"])
        run = next(
            (
                item
                for item in self._bundle_validation_runs.get((bundle.id, profile_id), [])
                if item.id == validation_run_id
            ),
            None,
        )
        if run is None:
            raise ExportStoreNotFoundError("Bundle validation run not found.")
        return run

    def get_current_bundle_validation_run(
        self, **kwargs
    ) -> BundleValidationRunRecord | None:  # type: ignore[no-untyped-def]
        bundle = self.get_deposit_bundle(
            project_id=str(kwargs["project_id"]),
            export_request_id=str(kwargs["export_request_id"]),
            bundle_id=str(kwargs["bundle_id"]),
        )
        profile_id = str(kwargs["profile_id"]).strip().upper()
        return next(
            (
                item
                for item in self._bundle_validation_runs.get((bundle.id, profile_id), [])
                if item.superseded_by_validation_run_id is None
            ),
            None,
        )

    def create_bundle_validation_run(
        self, **kwargs
    ) -> BundleValidationRunRecord:  # type: ignore[no-untyped-def]
        project_id = str(kwargs["project_id"])
        export_request_id = str(kwargs["export_request_id"])
        bundle_id = str(kwargs["bundle_id"])
        actor_user_id = str(kwargs["actor_user_id"])
        normalized_profile_id = str(kwargs["profile_id"]).strip().upper()
        try:
            profile = get_bundle_profile(profile_id=normalized_profile_id)
        except ValueError as error:
            raise ExportStoreConflictError(str(error)) from error

        bundle = self.get_deposit_bundle(
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
        )
        if bundle.status != "SUCCEEDED":
            raise ExportStoreConflictError(
                "Bundle validation requires a SUCCEEDED bundle attempt."
            )
        artifact = self._bundle_artifacts.get(bundle.id)
        if artifact is None:
            raise ExportStoreConflictError(
                "Bundle validation requires an immutable succeeded bundle artifact."
            )

        lineage_key = (bundle.id, profile.id)
        runs = list(self._bundle_validation_runs.get(lineage_key, []))
        current = next((item for item in runs if item.superseded_by_validation_run_id is None), None)
        attempt_number = (max((item.attempt_number for item in runs), default=0) + 1)
        now = datetime.now(UTC)
        profile_snapshot_sha256 = bundle_profile_snapshot_sha256(profile=profile)
        profile_snapshot_key = (
            "controlled/derived/provenance/"
            f"{project_id}/export-requests/{export_request_id}/bundles/{bundle.id}/"
            f"profiles/{profile.id.lower()}/{profile_snapshot_sha256}.json"
        )

        verification_projection = self._bundle_verification_projections.get(bundle.id)
        verification_projection_status = (
            verification_projection.status if verification_projection is not None else None
        )

        validation_output = validate_bundle_artifact_against_profile(
            bundle_id=bundle.id,
            bundle_kind=bundle.bundle_kind,
            bundle_sha256=bundle.bundle_sha256 or "",
            bundle_artifact=artifact,
            expected_proof_artifact_sha256=bundle.provenance_proof_artifact_sha256,
            verification_projection_status=verification_projection_status,
            profile=profile,
            checked_at=now,
        )
        result_json = dict(validation_output.payload)
        result_json["profileSnapshotKey"] = profile_snapshot_key
        result_json["profileSnapshotSha256"] = profile_snapshot_sha256
        result_json["profileSnapshot"] = build_bundle_profile_snapshot(profile=profile)
        result_json["profileId"] = profile.id
        result_json["attemptNumber"] = attempt_number

        run_status = "SUCCEEDED" if validation_output.result == "VALID" else "FAILED"
        failure_reason = (
            "; ".join(
                str(item)
                for item in result_json.get("failures", [])
                if isinstance(item, str) and item.strip()
            )[:5000]
            if run_status == "FAILED"
            else None
        )
        run = BundleValidationRunRecord(
            id=f"{bundle.id}-validate-{profile.id.lower()}-{attempt_number}",
            project_id=project_id,
            bundle_id=bundle.id,
            profile_id=profile.id,
            profile_snapshot_key=profile_snapshot_key,
            profile_snapshot_sha256=profile_snapshot_sha256,
            status=run_status,  # type: ignore[arg-type]
            attempt_number=attempt_number,
            supersedes_validation_run_id=current.id if current is not None else None,
            superseded_by_validation_run_id=None,
            result_json=result_json,
            failure_reason=failure_reason,
            created_by=actor_user_id,
            created_at=now,
            started_at=now,
            finished_at=now,
            canceled_by=None,
            canceled_at=None,
        )
        if current is not None:
            runs = [
                replace(item, superseded_by_validation_run_id=run.id)
                if item.id == current.id
                else item
                for item in runs
            ]
        runs.insert(0, run)
        self._bundle_validation_runs[lineage_key] = runs

        projection = self._bundle_validation_projections.get(lineage_key)
        if projection is None:
            projection = BundleValidationProjectionRecord(
                bundle_id=bundle.id,
                profile_id=profile.id,
                status="PENDING",
                last_validation_run_id=None,
                ready_at=None,
                updated_at=now,
            )
        if run.status == "SUCCEEDED":
            projection = BundleValidationProjectionRecord(
                bundle_id=bundle.id,
                profile_id=profile.id,
                status="READY",
                last_validation_run_id=run.id,
                ready_at=now,
                updated_at=now,
            )
            terminal_event = "BUNDLE_VALIDATION_SUCCEEDED"
        else:
            if projection.status == "READY":
                projection = replace(projection, updated_at=now)
            else:
                projection = BundleValidationProjectionRecord(
                    bundle_id=bundle.id,
                    profile_id=profile.id,
                    status="FAILED",
                    last_validation_run_id=run.id,
                    ready_at=None,
                    updated_at=now,
                )
            terminal_event = "BUNDLE_VALIDATION_FAILED"
        self._bundle_validation_projections[lineage_key] = projection

        self._bundle_events.setdefault(bundle.id, []).extend(
            [
                BundleEventRecord(
                    id=f"{run.id}-event-started",
                    bundle_id=bundle.id,
                    event_type="BUNDLE_VALIDATION_STARTED",
                    verification_run_id=None,
                    validation_run_id=run.id,
                    actor_user_id=actor_user_id,
                    reason=f"profile:{profile.id}",
                    created_at=now + timedelta(microseconds=1),
                ),
                BundleEventRecord(
                    id=f"{run.id}-event-terminal",
                    bundle_id=bundle.id,
                    event_type=terminal_event,  # type: ignore[arg-type]
                    verification_run_id=None,
                    validation_run_id=run.id,
                    actor_user_id=actor_user_id,
                    reason=failure_reason or f"profile:{profile.id}",
                    created_at=now + timedelta(microseconds=2),
                ),
            ]
        )
        return run

    def cancel_bundle_validation_run(
        self, **kwargs
    ) -> BundleValidationRunRecord:  # type: ignore[no-untyped-def]
        bundle = self.get_deposit_bundle(
            project_id=str(kwargs["project_id"]),
            export_request_id=str(kwargs["export_request_id"]),
            bundle_id=str(kwargs["bundle_id"]),
        )
        profile_id = str(kwargs["profile_id"]).strip().upper()
        validation_run_id = str(kwargs["validation_run_id"])
        actor_user_id = str(kwargs["actor_user_id"])
        run = self.get_bundle_validation_run(
            project_id=str(kwargs["project_id"]),
            export_request_id=str(kwargs["export_request_id"]),
            bundle_id=bundle.id,
            profile_id=profile_id,
            validation_run_id=validation_run_id,
        )
        if run.status not in {"QUEUED", "RUNNING"}:
            raise ExportStoreConflictError(
                "Bundle validation cancel is allowed only for QUEUED or RUNNING runs."
            )
        now = datetime.now(UTC)
        canceled = replace(
            run,
            status="CANCELED",
            canceled_by=actor_user_id,
            canceled_at=now,
            finished_at=now,
            failure_reason="Bundle validation run canceled.",
        )
        key = (bundle.id, profile_id)
        self._bundle_validation_runs[key] = [
            canceled if item.id == run.id else item
            for item in self._bundle_validation_runs.get(key, [])
        ]
        self._bundle_events.setdefault(bundle.id, []).append(
            BundleEventRecord(
                id=f"{run.id}-event-canceled",
                bundle_id=bundle.id,
                event_type="BUNDLE_VALIDATION_CANCELED",
                verification_run_id=None,
                validation_run_id=run.id,
                actor_user_id=actor_user_id,
                reason="Bundle validation run canceled.",
                created_at=now,
            )
        )
        return canceled

    def read_deposit_bundle_artifact(self, **kwargs) -> dict[str, object]:  # type: ignore[no-untyped-def]
        bundle = kwargs["bundle"]
        if not isinstance(bundle, DepositBundleRecord):
            raise ExportStoreNotFoundError("Deposit bundle not found.")
        artifact = self._bundle_artifacts.get(bundle.id)
        if artifact is None:
            raise ExportStoreNotFoundError("Deposit bundle not found.")
        return dict(artifact)

    def cancel_deposit_bundle(self, **kwargs) -> DepositBundleRecord:  # type: ignore[no-untyped-def]
        project_id = str(kwargs["project_id"])
        export_request_id = str(kwargs["export_request_id"])
        bundle_id = str(kwargs["bundle_id"])
        actor_user_id = str(kwargs["actor_user_id"])
        bundle = self.get_deposit_bundle(
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
        )
        if bundle.status not in {"QUEUED", "RUNNING"}:
            raise ExportStoreConflictError(
                "Only QUEUED or RUNNING deposit bundles can be canceled."
            )
        now = datetime.now(UTC)
        updated = replace(
            bundle,
            status="CANCELED",
            canceled_by=actor_user_id,
            canceled_at=now,
            finished_at=now,
        )
        self._deposit_bundles[export_request_id] = [
            updated if item.id == bundle.id else item
            for item in self._deposit_bundles.get(export_request_id, [])
        ]
        self._bundle_events.setdefault(bundle.id, []).append(
            BundleEventRecord(
                id=f"{bundle.id}-event-canceled",
                bundle_id=bundle.id,
                event_type="BUNDLE_BUILD_CANCELED",
                verification_run_id=None,
                validation_run_id=None,
                actor_user_id=actor_user_id,
                reason=None,
                created_at=now,
            )
        )
        return updated

    def ensure_service_account_user(
        self,
        *,
        user_id: str,
        oidc_sub: str,
        email: str,
        display_name: str,
    ) -> None:
        _ = (user_id, oidc_sub, email, display_name)

    def attach_request_receipt(self, **kwargs):  # type: ignore[no-untyped-def]
        export_request_id = str(kwargs["export_request_id"])
        actor_user_id = str(kwargs["actor_user_id"])
        receipt_key = str(kwargs["receipt_key"])
        receipt_sha256 = str(kwargs["receipt_sha256"])
        exported_at = kwargs["exported_at"]
        request = self._requests.get(export_request_id)
        if request is None:
            raise ExportStoreNotFoundError("Export request not found.")
        if request.status not in {"APPROVED", "EXPORTED"}:
            raise ExportStoreConflictError(
                "Only APPROVED or EXPORTED requests can attach gateway receipts."
            )
        now = datetime.now(UTC)
        receipts = list(self._request_receipts.get(export_request_id, []))
        supersedes = receipts[0].id if receipts else None
        attempt_number = len(receipts) + 1
        receipt = ExportReceiptRecord(
            id=f"{export_request_id}-receipt-{attempt_number}",
            export_request_id=export_request_id,
            attempt_number=attempt_number,
            supersedes_receipt_id=supersedes,
            superseded_by_receipt_id=None,
            receipt_key=receipt_key,
            receipt_sha256=receipt_sha256,
            created_by=actor_user_id,
            created_at=now,
            exported_at=exported_at,
        )
        if receipts:
            receipts[0] = replace(
                receipts[0],
                superseded_by_receipt_id=receipt.id,
            )
        receipts.insert(0, receipt)
        self._request_receipts[export_request_id] = receipts
        self._request_events.setdefault(export_request_id, []).append(
            ExportRequestEventRecord(
                id=f"{export_request_id}-event-{len(self._request_events[export_request_id]) + 1}",
                export_request_id=export_request_id,
                event_type="REQUEST_RECEIPT_ATTACHED",
                from_status=request.status,
                to_status=request.status,
                actor_user_id=actor_user_id,
                reason=f"receipt_attempt:{attempt_number}",
                created_at=now,
            )
        )
        self._request_events[export_request_id].append(
            ExportRequestEventRecord(
                id=f"{export_request_id}-event-{len(self._request_events[export_request_id]) + 1}",
                export_request_id=export_request_id,
                event_type="REQUEST_EXPORTED",
                from_status=request.status,
                to_status="EXPORTED",
                actor_user_id=actor_user_id,
                reason=f"receipt_attempt:{attempt_number}",
                created_at=now,
            )
        )
        self._requests[export_request_id] = replace(
            request,
            status="EXPORTED",
            receipt_id=receipt.id,
            receipt_key=receipt_key,
            receipt_sha256=receipt_sha256,
            receipt_created_by=actor_user_id,
            receipt_created_at=now,
            exported_at=exported_at,
            last_queue_activity_at=now,
            updated_at=now,
        )
        return self._requests[export_request_id], receipt

    def claim_request_review(self, **kwargs):  # type: ignore[no-untyped-def]
        export_request_id = str(kwargs["export_request_id"])
        review_id = str(kwargs["review_id"])
        expected_review_etag = str(kwargs["expected_review_etag"])
        actor_user_id = str(kwargs["actor_user_id"])
        request = self._requests[export_request_id]
        if request.status in {"APPROVED", "EXPORTED", "REJECTED", "RETURNED"}:
            raise ExportStoreConflictError("Terminal export requests cannot be claimed.")
        reviews = self._request_reviews[export_request_id]
        active = self._active_review(reviews)
        if active is None or active.id != review_id:
            raise ExportStoreConflictError(
                "Claim action must target the active required review stage."
            )
        if active.review_etag != expected_review_etag:
            raise ExportStoreConflictError(
                "Review stage changed; refresh to use the latest reviewEtag."
            )
        if active.assigned_reviewer_user_id not in {None, actor_user_id}:
            raise ExportStoreConflictError(
                "Review stage is already claimed by another reviewer."
            )
        if request.requires_second_review and active.review_stage == "SECONDARY":
            primary = next((review for review in reviews if review.review_stage == "PRIMARY"), None)
            if primary is None or primary.status != "APPROVED":
                raise ExportStoreConflictError(
                    "Secondary review requires an approved primary stage."
                )
            if primary.acted_by_user_id == actor_user_id:
                raise ExportStoreConflictError(
                    "Primary and secondary reviews must be by distinct reviewers."
                )
        now = datetime.now(UTC)
        updated = replace(
            active,
            assigned_reviewer_user_id=actor_user_id,
            assigned_at=active.assigned_at or now,
            review_etag=f"{active.id}-etag-claim-{now.timestamp()}",
            updated_at=now,
        )
        self._request_reviews[export_request_id] = [
            updated if review.id == review_id else review for review in reviews
        ]
        self._request_review_events[export_request_id].append(
            ExportRequestReviewEventRecord(
                id=f"{review_id}-claim-{len(self._request_review_events[export_request_id])}",
                review_id=review_id,
                export_request_id=export_request_id,
                review_stage=updated.review_stage,
                event_type="REVIEW_CLAIMED",
                actor_user_id=actor_user_id,
                assigned_reviewer_user_id=actor_user_id,
                decision_reason=None,
                return_comment=None,
                created_at=now,
            )
        )
        self._requests[export_request_id] = replace(
            request,
            last_queue_activity_at=now,
            updated_at=now,
        )
        return self._requests[export_request_id], updated

    def release_request_review(self, **kwargs):  # type: ignore[no-untyped-def]
        export_request_id = str(kwargs["export_request_id"])
        review_id = str(kwargs["review_id"])
        expected_review_etag = str(kwargs["expected_review_etag"])
        actor_user_id = str(kwargs["actor_user_id"])
        allow_admin_release = bool(kwargs["allow_admin_release"])
        request = self._requests[export_request_id]
        if request.status in {"APPROVED", "EXPORTED", "REJECTED", "RETURNED"}:
            raise ExportStoreConflictError(
                "Terminal export requests cannot release review stages."
            )
        reviews = self._request_reviews[export_request_id]
        active = self._active_review(reviews)
        if active is None or active.id != review_id:
            raise ExportStoreConflictError(
                "Release action must target the active required review stage."
            )
        if active.review_etag != expected_review_etag:
            raise ExportStoreConflictError(
                "Review stage changed; refresh to use the latest reviewEtag."
            )
        if active.assigned_reviewer_user_id is None:
            raise ExportStoreConflictError("Review stage is not currently assigned.")
        if (
            not allow_admin_release
            and active.assigned_reviewer_user_id != actor_user_id
        ):
            raise ExportStoreConflictError(
                "Only the assigned reviewer can release this stage."
            )
        now = datetime.now(UTC)
        updated = replace(
            active,
            status="PENDING" if active.status == "IN_REVIEW" else active.status,
            assigned_reviewer_user_id=None,
            assigned_at=None,
            review_etag=f"{active.id}-etag-release-{now.timestamp()}",
            updated_at=now,
        )
        self._request_reviews[export_request_id] = [
            updated if review.id == review_id else review for review in reviews
        ]
        self._request_review_events[export_request_id].append(
            ExportRequestReviewEventRecord(
                id=f"{review_id}-release-{len(self._request_review_events[export_request_id])}",
                review_id=review_id,
                export_request_id=export_request_id,
                review_stage=updated.review_stage,
                event_type="REVIEW_RELEASED",
                actor_user_id=actor_user_id,
                assigned_reviewer_user_id=None,
                decision_reason=None,
                return_comment=None,
                created_at=now,
            )
        )
        self._requests[export_request_id] = replace(
            request,
            last_queue_activity_at=now,
            updated_at=now,
        )
        return self._requests[export_request_id], updated

    def start_request_review(self, **kwargs):  # type: ignore[no-untyped-def]
        export_request_id = str(kwargs["export_request_id"])
        review_id = str(kwargs["review_id"])
        expected_review_etag = str(kwargs["expected_review_etag"])
        actor_user_id = str(kwargs["actor_user_id"])
        request = self._requests[export_request_id]
        if request.status in {"APPROVED", "EXPORTED", "REJECTED", "RETURNED"}:
            raise ExportStoreConflictError("Terminal export requests cannot start review.")
        reviews = self._request_reviews[export_request_id]
        active = self._active_review(reviews)
        if active is None or active.id != review_id:
            raise ExportStoreConflictError(
                "start-review must target the active required review stage."
            )
        if active.review_etag != expected_review_etag:
            raise ExportStoreConflictError(
                "Review stage changed; refresh to use the latest reviewEtag."
            )
        if (
            active.assigned_reviewer_user_id is not None
            and active.assigned_reviewer_user_id != actor_user_id
        ):
            raise ExportStoreConflictError("Review stage is assigned to another reviewer.")
        if request.requires_second_review and active.review_stage == "SECONDARY":
            primary = next((review for review in reviews if review.review_stage == "PRIMARY"), None)
            if primary is None or primary.status != "APPROVED":
                raise ExportStoreConflictError(
                    "Secondary review requires an approved primary stage."
                )
            if primary.acted_by_user_id == actor_user_id:
                raise ExportStoreConflictError(
                    "Primary and secondary reviews must be by distinct reviewers."
                )
        now = datetime.now(UTC)
        updated = replace(
            active,
            status="IN_REVIEW",
            assigned_reviewer_user_id=actor_user_id,
            assigned_at=active.assigned_at or now,
            review_etag=f"{active.id}-etag-start-{now.timestamp()}",
            updated_at=now,
        )
        self._request_reviews[export_request_id] = [
            updated if review.id == review_id else review for review in reviews
        ]
        self._request_review_events[export_request_id].append(
            ExportRequestReviewEventRecord(
                id=f"{review_id}-start-{len(self._request_review_events[export_request_id])}",
                review_id=review_id,
                export_request_id=export_request_id,
                review_stage=updated.review_stage,
                event_type="REVIEW_STARTED",
                actor_user_id=actor_user_id,
                assigned_reviewer_user_id=actor_user_id,
                decision_reason=None,
                return_comment=None,
                created_at=now,
            )
        )
        next_status = "IN_REVIEW"
        if request.status != "IN_REVIEW":
            self._request_events[export_request_id].append(
                ExportRequestEventRecord(
                    id=(
                        f"{export_request_id}-event-"
                        f"{len(self._request_events[export_request_id]) + 1}"
                    ),
                    export_request_id=export_request_id,
                    event_type="REQUEST_REVIEW_STARTED",
                    from_status=request.status,
                    to_status="IN_REVIEW",
                    actor_user_id=actor_user_id,
                    reason=None,
                    created_at=now,
                )
            )
        self._requests[export_request_id] = replace(
            request,
            status=next_status,
            first_review_started_by=request.first_review_started_by or actor_user_id,
            first_review_started_at=request.first_review_started_at or now,
            last_queue_activity_at=now,
            updated_at=now,
        )
        return self._requests[export_request_id], updated

    def decide_request_review(self, **kwargs):  # type: ignore[no-untyped-def]
        export_request_id = str(kwargs["export_request_id"])
        review_id = str(kwargs["review_id"])
        expected_review_etag = str(kwargs["expected_review_etag"])
        actor_user_id = str(kwargs["actor_user_id"])
        decision = str(kwargs["decision"])
        decision_reason = kwargs.get("decision_reason")
        return_comment = kwargs.get("return_comment")
        request = self._requests[export_request_id]
        if request.status in {"APPROVED", "EXPORTED", "REJECTED", "RETURNED"}:
            raise ExportStoreConflictError(
                "Terminal export requests cannot accept review decisions."
            )
        reviews = self._request_reviews[export_request_id]
        active = self._active_review(reviews)
        if active is None or active.id != review_id:
            raise ExportStoreConflictError(
                "Decision action must target the active required review stage."
            )
        if active.review_etag != expected_review_etag:
            raise ExportStoreConflictError(
                "Review stage changed; refresh to use the latest reviewEtag."
            )
        if active.status != "IN_REVIEW":
            raise ExportStoreConflictError(
                "Review stage must be IN_REVIEW before a decision is recorded."
            )
        if active.assigned_reviewer_user_id != actor_user_id:
            raise ExportStoreConflictError(
                "Only the assigned reviewer can record a decision."
            )
        if decision == "REJECT" and not isinstance(decision_reason, str):
            raise ExportStoreConflictError("decisionReason is required for REJECT.")
        if decision == "RETURN" and not isinstance(return_comment, str):
            raise ExportStoreConflictError("returnComment is required for RETURN.")

        now = datetime.now(UTC)
        primary = next((review for review in reviews if review.review_stage == "PRIMARY"), None)
        next_review_status = "APPROVED"
        next_review_event_type = "REVIEW_APPROVED"
        next_request_status = request.status
        next_request_event_type = None
        request_event_reason = None

        if request.requires_second_review and active.review_stage == "SECONDARY":
            if primary is None or primary.status != "APPROVED":
                raise ExportStoreConflictError(
                    "Secondary review requires an approved primary stage."
                )
            if primary.acted_by_user_id == actor_user_id:
                raise ExportStoreConflictError(
                    "Primary and secondary reviews must be by distinct reviewers."
                )

        if decision == "APPROVE":
            if request.requires_second_review and active.review_stage == "SECONDARY":
                next_request_status = "APPROVED"
                next_request_event_type = "REQUEST_APPROVED"
            elif request.requires_second_review and active.review_stage == "PRIMARY":
                next_request_status = "IN_REVIEW"
            else:
                next_request_status = "APPROVED"
                next_request_event_type = "REQUEST_APPROVED"
            request_event_reason = decision_reason
        elif decision == "REJECT":
            next_review_status = "REJECTED"
            next_review_event_type = "REVIEW_REJECTED"
            next_request_status = "REJECTED"
            next_request_event_type = "REQUEST_REJECTED"
            request_event_reason = decision_reason
        else:
            next_review_status = "RETURNED"
            next_review_event_type = "REVIEW_RETURNED"
            next_request_status = "RETURNED"
            next_request_event_type = "REQUEST_RETURNED"
            request_event_reason = return_comment

        updated_review = replace(
            active,
            status=next_review_status,  # type: ignore[arg-type]
            acted_by_user_id=actor_user_id,
            acted_at=now,
            decision_reason=decision_reason if isinstance(decision_reason, str) else None,
            return_comment=return_comment if isinstance(return_comment, str) else None,
            review_etag=f"{active.id}-etag-decision-{now.timestamp()}",
            updated_at=now,
        )
        self._request_reviews[export_request_id] = [
            updated_review if review.id == review_id else review for review in reviews
        ]
        self._request_review_events[export_request_id].append(
            ExportRequestReviewEventRecord(
                id=f"{review_id}-decision-{len(self._request_review_events[export_request_id])}",
                review_id=review_id,
                export_request_id=export_request_id,
                review_stage=updated_review.review_stage,
                event_type=next_review_event_type,  # type: ignore[arg-type]
                actor_user_id=actor_user_id,
                assigned_reviewer_user_id=actor_user_id,
                decision_reason=updated_review.decision_reason,
                return_comment=updated_review.return_comment,
                created_at=now,
            )
        )
        if next_request_event_type is not None:
            self._request_events[export_request_id].append(
                ExportRequestEventRecord(
                    id=(
                        f"{export_request_id}-event-"
                        f"{len(self._request_events[export_request_id]) + 1}"
                    ),
                    export_request_id=export_request_id,
                    event_type=next_request_event_type,  # type: ignore[arg-type]
                    from_status=request.status,
                    to_status=next_request_status,  # type: ignore[arg-type]
                    actor_user_id=actor_user_id,
                    reason=request_event_reason,
                    created_at=now,
                )
            )
        is_terminal = next_request_status in {"APPROVED", "REJECTED", "RETURNED"}
        self._requests[export_request_id] = replace(
            request,
            status=next_request_status,  # type: ignore[arg-type]
            last_queue_activity_at=now,
            retention_until=(
                request.retention_until
                if not is_terminal
                else request.retention_until or now + timedelta(days=90)
            ),
            final_review_id=review_id if is_terminal else request.final_review_id,
            final_decision_by=actor_user_id if is_terminal else request.final_decision_by,
            final_decision_at=now if is_terminal else request.final_decision_at,
            final_decision_reason=(
                updated_review.decision_reason if is_terminal else request.final_decision_reason
            ),
            final_return_comment=(
                updated_review.return_comment if is_terminal else request.final_return_comment
            ),
            updated_at=now,
        )
        return self._requests[export_request_id], updated_review

    @staticmethod
    def _is_open_status(status: str) -> bool:
        return status in {"SUBMITTED", "RESUBMITTED", "IN_REVIEW"}

    def record_request_reminder(self, **kwargs):  # type: ignore[no-untyped-def]
        project_id = str(kwargs["project_id"])
        export_request_id = str(kwargs["export_request_id"])
        actor_user_id = str(kwargs["actor_user_id"])
        reason = kwargs.get("reason")
        request = self._requests.get(export_request_id)
        if request is None or request.project_id != project_id:
            raise ExportStoreNotFoundError("Export request not found.")
        if not self._is_open_status(request.status):
            raise ExportStoreConflictError(
                "Only open export requests can accept reminder/escalation events."
            )
        now = datetime.now(UTC)
        latest = next(
            (
                event
                for event in reversed(self._request_events[export_request_id])
                if event.event_type == "REQUEST_REMINDER_SENT"
            ),
            None,
        )
        if latest is not None and latest.created_at > (now - timedelta(hours=12)):
            raise ExportStoreConflictError(
                "Reminder/escalation cooldown is still active for this request."
            )
        self._request_events[export_request_id].append(
            ExportRequestEventRecord(
                id=f"{export_request_id}-event-{len(self._request_events[export_request_id]) + 1}",
                export_request_id=export_request_id,
                event_type="REQUEST_REMINDER_SENT",
                from_status=request.status,
                to_status=request.status,
                actor_user_id=actor_user_id,
                reason=str(reason) if isinstance(reason, str) else None,
                created_at=now,
            )
        )
        self._requests[export_request_id] = replace(
            request,
            last_queue_activity_at=now,
            updated_at=now,
        )
        return self._requests[export_request_id]

    def record_request_escalation(self, **kwargs):  # type: ignore[no-untyped-def]
        project_id = str(kwargs["project_id"])
        export_request_id = str(kwargs["export_request_id"])
        actor_user_id = str(kwargs["actor_user_id"])
        reason = kwargs.get("reason")
        request = self._requests.get(export_request_id)
        if request is None or request.project_id != project_id:
            raise ExportStoreNotFoundError("Export request not found.")
        if not self._is_open_status(request.status):
            raise ExportStoreConflictError(
                "Only open export requests can accept reminder/escalation events."
            )
        now = datetime.now(UTC)
        if request.sla_due_at is None or request.sla_due_at > (now - timedelta(hours=24)):
            raise ExportStoreConflictError(
                "Escalation threshold has not been met for this request."
            )
        latest = next(
            (
                event
                for event in reversed(self._request_events[export_request_id])
                if event.event_type == "REQUEST_ESCALATED"
            ),
            None,
        )
        if latest is not None and latest.created_at > (now - timedelta(hours=24)):
            raise ExportStoreConflictError(
                "Reminder/escalation cooldown is still active for this request."
            )
        self._request_events[export_request_id].append(
            ExportRequestEventRecord(
                id=f"{export_request_id}-event-{len(self._request_events[export_request_id]) + 1}",
                export_request_id=export_request_id,
                event_type="REQUEST_ESCALATED",
                from_status=request.status,
                to_status=request.status,
                actor_user_id=actor_user_id,
                reason=str(reason) if isinstance(reason, str) else None,
                created_at=now,
            )
        )
        self._requests[export_request_id] = replace(
            request,
            last_queue_activity_at=now,
            updated_at=now,
        )
        return self._requests[export_request_id]

    def apply_retention_policies(self, *, limit: int = 500) -> int:
        now = datetime.now(UTC)
        normalized_limit = max(1, min(limit, 5000))
        updates = 0
        for request in sorted(self._requests.values(), key=lambda item: (item.updated_at, item.id)):
            if updates >= normalized_limit:
                break
            if request.retention_until is not None:
                continue
            next_retention_until: datetime | None = None
            if self._is_open_status(request.status):
                activity_at = request.last_queue_activity_at or request.submitted_at
                if activity_at <= (now - timedelta(days=30)):
                    next_retention_until = now + timedelta(days=60)
            elif request.status in {"APPROVED", "EXPORTED"}:
                next_retention_until = now + timedelta(days=180)
            elif request.status in {"REJECTED", "RETURNED"}:
                next_retention_until = now + timedelta(days=90)
            if next_retention_until is None:
                continue
            self._requests[request.id] = replace(
                request,
                retention_until=next_retention_until,
                last_queue_activity_at=request.last_queue_activity_at or now,
                updated_at=now,
            )
            updates += 1
        return updates

    def run_operations_maintenance(
        self, *, actor_user_id: str, batch_limit: int = 200
    ) -> ExportOperationsMaintenanceResult:
        now = datetime.now(UTC)
        reminders_appended = 0
        escalations_appended = 0
        normalized_batch_limit = max(1, min(batch_limit, 500))

        reminder_candidates = sorted(
            (
                request
                for request in self._requests.values()
                if self._is_open_status(request.status)
                and (request.last_queue_activity_at or request.submitted_at)
                <= (now - timedelta(hours=24))
            ),
            key=lambda item: ((item.last_queue_activity_at or item.submitted_at), item.id),
        )
        for request in reminder_candidates[:normalized_batch_limit]:
            try:
                self.record_request_reminder(
                    project_id=request.project_id,
                    export_request_id=request.id,
                    actor_user_id=actor_user_id,
                    reason="SLA reminder threshold reached.",
                )
                reminders_appended += 1
            except ExportStoreConflictError:
                continue

        escalation_candidates = sorted(
            (
                request
                for request in self._requests.values()
                if self._is_open_status(request.status)
                and request.sla_due_at is not None
                and request.sla_due_at <= (now - timedelta(hours=24))
            ),
            key=lambda item: (item.sla_due_at or now, item.id),
        )
        for request in escalation_candidates[:normalized_batch_limit]:
            try:
                self.record_request_escalation(
                    project_id=request.project_id,
                    export_request_id=request.id,
                    actor_user_id=actor_user_id,
                    reason="SLA escalation threshold reached.",
                )
                escalations_appended += 1
            except ExportStoreConflictError:
                continue

        retention_updates_applied = self.apply_retention_policies(
            limit=normalized_batch_limit * 3
        )
        return ExportOperationsMaintenanceResult(
            run_at=now,
            reminders_appended=reminders_appended,
            escalations_appended=escalations_appended,
            retention_updates_applied=retention_updates_applied,
            retention_audit_safe=True,
        )

    def get_operations_export_status(self) -> ExportOperationsStatusRecord:
        now = datetime.now(UTC)
        stale_cutoff = now - timedelta(days=30)
        reminder_due_cutoff = now - timedelta(hours=24)
        reminder_cooldown_cutoff = now - timedelta(hours=12)
        escalation_due_cutoff = now - timedelta(hours=24)
        escalation_cooldown_cutoff = now - timedelta(hours=24)
        pending_cutoff = now + timedelta(days=14)

        open_request_count = 0
        aging_unstarted_count = 0
        aging_no_sla_count = 0
        aging_on_track_count = 0
        aging_due_soon_count = 0
        aging_overdue_count = 0
        stale_open_count = 0
        reminder_due_count = 0
        escalation_due_count = 0
        escalated_open_count = 0
        retention_pending_count = 0
        terminal_approved_count = 0
        terminal_exported_count = 0
        terminal_rejected_count = 0
        terminal_returned_count = 0
        reminders_sent_total = 0
        reminders_sent_last_24h = 0
        escalations_total = 0

        latest_reminder: dict[str, datetime] = {}
        latest_escalation: dict[str, datetime] = {}
        for request_id, events in self._request_events.items():
            for event in events:
                if event.event_type == "REQUEST_REMINDER_SENT":
                    reminders_sent_total += 1
                    if event.created_at >= now - timedelta(hours=24):
                        reminders_sent_last_24h += 1
                    last = latest_reminder.get(request_id)
                    if last is None or event.created_at > last:
                        latest_reminder[request_id] = event.created_at
                elif event.event_type == "REQUEST_ESCALATED":
                    escalations_total += 1
                    last_escalation = latest_escalation.get(request_id)
                    if last_escalation is None or event.created_at > last_escalation:
                        latest_escalation[request_id] = event.created_at

        for request in self._requests.values():
            if request.retention_until is not None and request.retention_until <= pending_cutoff:
                retention_pending_count += 1
            if request.status == "APPROVED":
                terminal_approved_count += 1
            elif request.status == "EXPORTED":
                terminal_exported_count += 1
            elif request.status == "REJECTED":
                terminal_rejected_count += 1
            elif request.status == "RETURNED":
                terminal_returned_count += 1
            if not self._is_open_status(request.status):
                continue
            open_request_count += 1
            activity_at = request.last_queue_activity_at or request.submitted_at
            if activity_at <= stale_cutoff:
                stale_open_count += 1
            if request.sla_due_at is None:
                if request.first_review_started_at is None:
                    aging_unstarted_count += 1
                else:
                    aging_no_sla_count += 1
            else:
                remaining_seconds = int((request.sla_due_at - now).total_seconds())
                if remaining_seconds < 0:
                    aging_overdue_count += 1
                elif request.first_review_started_at is None:
                    aging_unstarted_count += 1
                elif remaining_seconds <= 24 * 60 * 60:
                    aging_due_soon_count += 1
                else:
                    aging_on_track_count += 1

                if request.sla_due_at <= escalation_due_cutoff:
                    last_escalation = latest_escalation.get(request.id)
                    if last_escalation is None or last_escalation <= escalation_cooldown_cutoff:
                        escalation_due_count += 1

            if activity_at <= reminder_due_cutoff:
                last_reminder = latest_reminder.get(request.id)
                if last_reminder is None or last_reminder <= reminder_cooldown_cutoff:
                    reminder_due_count += 1
            if request.id in latest_escalation:
                escalated_open_count += 1

        return ExportOperationsStatusRecord(
            generated_at=now,
            open_request_count=open_request_count,
            aging_unstarted_count=aging_unstarted_count,
            aging_no_sla_count=aging_no_sla_count,
            aging_on_track_count=aging_on_track_count,
            aging_due_soon_count=aging_due_soon_count,
            aging_overdue_count=aging_overdue_count,
            stale_open_count=stale_open_count,
            reminder_due_count=reminder_due_count,
            reminders_sent_last_24h=reminders_sent_last_24h,
            reminders_sent_total=reminders_sent_total,
            escalation_due_count=escalation_due_count,
            escalated_open_count=escalated_open_count,
            escalations_total=escalations_total,
            retention_pending_count=retention_pending_count,
            retention_pending_window_days=14,
            terminal_approved_count=terminal_approved_count,
            terminal_exported_count=terminal_exported_count,
            terminal_rejected_count=terminal_rejected_count,
            terminal_returned_count=terminal_returned_count,
            policy_sla_hours=72,
            policy_reminder_after_hours=24,
            policy_reminder_cooldown_hours=12,
            policy_escalation_after_sla_hours=24,
            policy_escalation_cooldown_hours=24,
            policy_stale_open_after_days=30,
            policy_retention_stale_open_days=60,
            policy_retention_terminal_approved_days=180,
            policy_retention_terminal_other_days=90,
        )

    def force_request_status(self, *, export_request_id: str, status: str) -> None:
        row = self._requests[export_request_id]
        self._requests[export_request_id] = replace(
            row,
            status=status,  # type: ignore[arg-type]
            updated_at=datetime.now(UTC),
        )


def _candidate(
    *,
    candidate_id: str,
    project_id: str = "project-1",
    candidate_kind: Literal[
        "SAFEGUARDED_PREVIEW",
        "POLICY_RERUN",
        "DEPOSIT_BUNDLE",
        "SAFEGUARDED_DERIVATIVE",
    ] = "SAFEGUARDED_PREVIEW",
    eligibility_status: Literal["ELIGIBLE", "SUPERSEDED"] = "ELIGIBLE",
    supersedes_candidate_snapshot_id: str | None = None,
    created_at: datetime | None = None,
) -> ExportCandidateSnapshotRecord:
    now = created_at or datetime.now(UTC)
    return ExportCandidateSnapshotRecord(
        id=candidate_id,
        project_id=project_id,
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
        candidate_kind=candidate_kind,
        artefact_manifest_json={
            "fileList": [
                {
                    "fileName": "output-manifest.json",
                    "sha256": "d" * 64,
                    "fileSizeBytes": 1200,
                    "sourceRef": "/Users/test/.ukde-storage/controlled/path/output-manifest.json",
                    "sourceKind": "RUN_OUTPUT_MANIFEST",
                }
            ],
            "redactionCountsByCategory": {"PERSON_NAME": 3},
            "reviewerOverrideCount": 0,
            "conservativeAreaMaskCount": 0,
            "riskFlags": [],
            "approvedModelReferencesByRole": {
                "TRANSCRIPTION_PRIMARY": {
                    "modelId": "model-1",
                    "checksumSha256": "e" * 64,
                }
            },
        },
        candidate_sha256="f" * 64,
        eligibility_status=eligibility_status,
        supersedes_candidate_snapshot_id=supersedes_candidate_snapshot_id,
        superseded_by_candidate_snapshot_id=None,
        created_by="user-1",
        created_at=now,
    )


def _build_service(
    *,
    store: InMemoryExportStore,
    role_map: dict[str, Literal["PROJECT_LEAD", "RESEARCHER", "REVIEWER"]] | None = None,
) -> ExportService:
    roles = role_map or {
        "researcher-1": "RESEARCHER",
        "researcher-2": "RESEARCHER",
        "lead-1": "PROJECT_LEAD",
        "reviewer-1": "REVIEWER",
    }
    settings = SimpleNamespace(
        storage_controlled_raw_prefix="controlled/raw/",
        storage_controlled_derived_prefix="controlled/derived/",
        storage_safeguarded_exports_prefix="safeguarded/exports/",
    )
    project_service = FakeProjectService(roles)
    return ExportService(
        settings=settings,  # type: ignore[arg-type]
        store=store,  # type: ignore[arg-type]
        project_service=project_service,  # type: ignore[arg-type]
    )


def test_release_pack_preview_is_deterministic_and_masks_internal_paths() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    user = _principal(user_id="researcher-1")

    first = service.get_candidate_release_pack_preview(
        current_user=user,
        project_id="project-1",
        candidate_id="candidate-1",
        purpose_statement="Release pack preview for deterministic checks.",
        bundle_profile=None,
    )
    second = service.get_candidate_release_pack_preview(
        current_user=user,
        project_id="project-1",
        candidate_id="candidate-1",
        purpose_statement="Release pack preview for deterministic checks.",
        bundle_profile=None,
    )

    assert first["releasePackSha256"] == second["releasePackSha256"]
    assert first["releasePack"] == second["releasePack"]
    files = first["releasePack"]["files"]  # type: ignore[index]
    assert isinstance(files, list) and files
    first_file = files[0]
    assert isinstance(first_file, dict)
    assert str(first_file.get("sourceRef", "")).startswith("/") is False
    assert ".ukde-storage" not in str(first_file.get("sourceRef", ""))


def test_request_submission_persists_frozen_release_pack_and_risk_pin() -> None:
    candidate = _candidate(candidate_id="candidate-high")
    candidate = replace(
        candidate,
        artefact_manifest_json={
            **candidate.artefact_manifest_json,
            "reviewerOverrideCount": 2,
        },
    )
    store = InMemoryExportStore((candidate,))
    service = _build_service(store=store)
    user = _principal(user_id="researcher-1")

    created = service.create_export_request(
        current_user=user,
        project_id="project-1",
        candidate_snapshot_id=candidate.id,
        purpose_statement="Submit safeguarded output for governance review.",
        bundle_profile=None,
    )

    assert created.status == "SUBMITTED"
    assert created.risk_classification == "HIGH"
    assert created.review_path == "DUAL"
    assert created.requires_second_review is True
    assert created.release_pack_json["riskClassification"] == "HIGH"
    assert created.release_pack_json["requestScope"] == "REQUEST_FROZEN"
    assert created.release_pack_json["candidateSnapshotId"] == candidate.id

    release_pack = service.get_export_request_release_pack(
        current_user=user,
        project_id="project-1",
        export_request_id=created.id,
    )
    assert release_pack["releasePackSha256"] == created.release_pack_sha256
    assert release_pack["releasePack"] == created.release_pack_json


def test_export_request_validation_summary_passes_for_fresh_submission() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    user = _principal(user_id="researcher-1")
    created = service.create_export_request(
        current_user=user,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Validate frozen request summary for canonical baseline.",
        bundle_profile=None,
    )

    summary = service.get_export_request_validation_summary(
        current_user=user,
        project_id="project-1",
        export_request_id=created.id,
    )

    assert summary["isValid"] is True
    release_pack = summary["releasePack"]
    audit = summary["auditCompleteness"]
    assert isinstance(release_pack, dict)
    assert isinstance(audit, dict)
    assert release_pack["passed"] is True
    assert audit["passed"] is True
    assert release_pack["issueCount"] == 0
    assert audit["issueCount"] == 0


def test_export_request_validation_summary_detects_release_pack_drift() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    user = _principal(user_id="researcher-1")
    created = service.create_export_request(
        current_user=user,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Validate release-pack drift detection for tampered payload.",
        bundle_profile=None,
    )
    tampered_payload = dict(created.release_pack_json)
    tampered_payload["candidateSnapshotId"] = "tampered-candidate"
    store._requests[created.id] = replace(
        created,
        release_pack_json=tampered_payload,
    )

    summary = service.get_export_request_validation_summary(
        current_user=user,
        project_id="project-1",
        export_request_id=created.id,
    )

    assert summary["isValid"] is False
    release_pack = summary["releasePack"]
    assert isinstance(release_pack, dict)
    assert release_pack["passed"] is False
    issue_codes = {
        str(issue.get("code"))
        for issue in release_pack["issues"]  # type: ignore[index]
        if isinstance(issue, dict)
    }
    assert "RELEASE_PACK_REQUEST_LINEAGE_MISMATCH" in issue_codes
    assert "RELEASE_PACK_DRIFT_PAYLOAD_MISMATCH" in issue_codes


def test_export_request_validation_summary_detects_missing_audit_history() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    user = _principal(user_id="researcher-1")
    created = service.create_export_request(
        current_user=user,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Validate append-only audit stream completeness expectations.",
        bundle_profile=None,
    )
    store._request_events[created.id] = []

    summary = service.get_export_request_validation_summary(
        current_user=user,
        project_id="project-1",
        export_request_id=created.id,
    )

    assert summary["isValid"] is False
    audit = summary["auditCompleteness"]
    assert isinstance(audit, dict)
    assert audit["passed"] is False
    issue_codes = {
        str(issue.get("code"))
        for issue in audit["issues"]  # type: ignore[index]
        if isinstance(issue, dict)
    }
    assert "AUDIT_REQUEST_EVENT_STREAM_EMPTY" in issue_codes


def test_resubmission_creates_successor_revision_and_preserves_prior_history() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    user = _principal(user_id="researcher-1")

    created = service.create_export_request(
        current_user=user,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Initial request for screened export output.",
        bundle_profile=None,
    )
    store.force_request_status(export_request_id=created.id, status="RETURNED")

    successor = service.resubmit_export_request(
        current_user=user,
        project_id="project-1",
        export_request_id=created.id,
        candidate_snapshot_id="candidate-1",
        purpose_statement="Updated request after reviewer return comments.",
        bundle_profile="DUAL_REVIEW",
    )

    predecessor_after = service.get_export_request(
        current_user=user,
        project_id="project-1",
        export_request_id=created.id,
    )
    assert successor.status == "RESUBMITTED"
    assert successor.request_revision == created.request_revision + 1
    assert successor.supersedes_export_request_id == created.id
    assert predecessor_after.status == "RETURNED"
    assert predecessor_after.superseded_by_export_request_id == successor.id


def test_request_visibility_and_mutation_roles_are_enforced() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    researcher_1 = _principal(user_id="researcher-1")
    researcher_2 = _principal(user_id="researcher-2")
    lead = _principal(user_id="lead-1")
    reviewer = _principal(user_id="reviewer-1")
    auditor = _principal(user_id="auditor-1", platform_roles=("AUDITOR",))

    first = service.create_export_request(
        current_user=researcher_1,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Researcher one request for safeguarded output review.",
        bundle_profile=None,
    )
    second = service.create_export_request(
        current_user=researcher_2,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Researcher two request for safeguarded output review.",
        bundle_profile=None,
    )
    store.force_request_status(export_request_id=first.id, status="RETURNED")

    own_only = service.list_export_requests(
        current_user=researcher_1,
        project_id="project-1",
    )
    assert {item.id for item in own_only.items} == {first.id}

    lead_view = service.list_export_requests(
        current_user=lead,
        project_id="project-1",
    )
    assert {item.id for item in lead_view.items} == {first.id, second.id}

    auditor_view = service.list_export_requests(
        current_user=auditor,
        project_id="project-1",
    )
    assert {item.id for item in auditor_view.items} == {first.id, second.id}

    with pytest.raises(ExportAccessDeniedError):
        service.create_export_request(
            current_user=reviewer,
            project_id="project-1",
            candidate_snapshot_id="candidate-1",
            purpose_statement="Reviewer cannot submit requester-side requests.",
            bundle_profile=None,
        )


def test_requester_side_events_and_reviews_surfaces_return_lineage_records() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    user = _principal(user_id="researcher-1")

    created = service.create_export_request(
        current_user=user,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Create request to validate requester-side read surfaces.",
        bundle_profile=None,
    )
    events = service.get_export_request_events(
        current_user=user,
        project_id="project-1",
        export_request_id=created.id,
    )
    reviews = service.get_export_request_reviews(
        current_user=user,
        project_id="project-1",
        export_request_id=created.id,
    )
    review_events = service.get_export_request_review_events(
        current_user=user,
        project_id="project-1",
        export_request_id=created.id,
    )

    assert len(events) == 1
    assert events[0].event_type == "REQUEST_SUBMITTED"
    assert events[0].to_status == "SUBMITTED"
    assert len(reviews) == 1
    assert reviews[0].review_stage == "PRIMARY"
    assert reviews[0].status == "PENDING"
    assert len(review_events) == 1
    assert review_events[0].event_type == "REVIEW_CREATED"
    assert review_events[0].review_id == reviews[0].id


def test_resubmission_requires_returned_request() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    user = _principal(user_id="researcher-1")
    created = service.create_export_request(
        current_user=user,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Baseline request before invalid resubmission test.",
        bundle_profile=None,
    )

    with pytest.raises(ExportConflictError):
        service.resubmit_export_request(
            current_user=user,
            project_id="project-1",
            export_request_id=created.id,
            candidate_snapshot_id="candidate-1",
            purpose_statement="Attempting to resubmit before return.",
            bundle_profile=None,
        )


def test_researcher_cannot_read_another_users_request_detail() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    first_user = _principal(user_id="researcher-1")
    second_user = _principal(user_id="researcher-2")
    created = service.create_export_request(
        current_user=first_user,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Request owner detail visibility test.",
        bundle_profile=None,
    )

    with pytest.raises(ExportAccessDeniedError):
        service.get_export_request(
            current_user=second_user,
            project_id="project-1",
            export_request_id=created.id,
        )

    with pytest.raises(ExportNotFoundError):
        service.get_export_request(
            current_user=first_user,
            project_id="project-1",
            export_request_id="missing-request-id",
        )


def test_researcher_cannot_read_another_users_validation_summary() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    owner = _principal(user_id="researcher-1")
    other = _principal(user_id="researcher-2")
    created = service.create_export_request(
        current_user=owner,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Owner-only validation summary visibility check.",
        bundle_profile=None,
    )

    with pytest.raises(ExportAccessDeniedError):
        service.get_export_request_validation_summary(
            current_user=other,
            project_id="project-1",
            export_request_id=created.id,
        )


def test_review_queue_filters_mutations_and_terminal_projection_flow() -> None:
    candidate = _candidate(candidate_id="candidate-high")
    candidate = replace(
        candidate,
        artefact_manifest_json={
            **candidate.artefact_manifest_json,
            "reviewerOverrideCount": 1,
        },
    )
    store = InMemoryExportStore((candidate,))
    service = _build_service(
        store=store,
        role_map={
            "researcher-1": "RESEARCHER",
            "reviewer-1": "REVIEWER",
            "reviewer-2": "REVIEWER",
            "lead-1": "PROJECT_LEAD",
        },
    )
    requester = _principal(user_id="researcher-1")
    reviewer_1 = _principal(user_id="reviewer-1")
    reviewer_2 = _principal(user_id="reviewer-2")

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-high",
        purpose_statement="Submit a high-risk candidate that requires dual review.",
        bundle_profile=None,
    )
    assert created.requires_second_review is True

    initial_queue = service.list_export_review_queue(
        current_user=reviewer_1,
        project_id="project-1",
    )
    assert len(initial_queue) == 1
    active_primary = initial_queue[0].active_review_id
    assert active_primary is not None

    primary_review = service.get_export_request_reviews(
        current_user=reviewer_1,
        project_id="project-1",
        export_request_id=created.id,
    )[0]
    claimed_request, claimed_review = service.claim_export_request_review(
        current_user=reviewer_1,
        project_id="project-1",
        export_request_id=created.id,
        review_id=primary_review.id,
        review_etag=primary_review.review_etag,
    )
    assert claimed_review.assigned_reviewer_user_id == "reviewer-1"
    started_request, started_review = service.start_export_request_review(
        current_user=reviewer_1,
        project_id="project-1",
        export_request_id=created.id,
        review_id=claimed_review.id,
        review_etag=claimed_review.review_etag,
    )
    assert started_review.status == "IN_REVIEW"
    assert started_request.status == "IN_REVIEW"

    primary_approved_request, _ = service.decide_export_request(
        current_user=reviewer_1,
        project_id="project-1",
        export_request_id=created.id,
        review_id=started_review.id,
        review_etag=started_review.review_etag,
        decision="APPROVE",
        decision_reason="Primary reviewer sign-off.",
        return_comment=None,
    )
    assert primary_approved_request.status == "IN_REVIEW"

    secondary_review = next(
        review
        for review in service.get_export_request_reviews(
            current_user=reviewer_1,
            project_id="project-1",
            export_request_id=created.id,
        )
        if review.review_stage == "SECONDARY"
    )
    secondary_claimed_request, secondary_claimed_review = service.claim_export_request_review(
        current_user=reviewer_2,
        project_id="project-1",
        export_request_id=created.id,
        review_id=secondary_review.id,
        review_etag=secondary_review.review_etag,
    )
    assert secondary_claimed_request.status == "IN_REVIEW"
    secondary_started_request, secondary_started_review = service.start_export_request_review(
        current_user=reviewer_2,
        project_id="project-1",
        export_request_id=created.id,
        review_id=secondary_claimed_review.id,
        review_etag=secondary_claimed_review.review_etag,
    )
    assert secondary_started_review.status == "IN_REVIEW"
    assert secondary_started_request.status == "IN_REVIEW"

    with pytest.raises(ExportConflictError):
        service.decide_export_request(
            current_user=reviewer_1,
            project_id="project-1",
            export_request_id=created.id,
            review_id=secondary_started_review.id,
            review_etag=secondary_started_review.review_etag,
            decision="APPROVE",
            decision_reason="Attempting to satisfy both stages.",
            return_comment=None,
        )

    approved_request, approved_review = service.decide_export_request(
        current_user=reviewer_2,
        project_id="project-1",
        export_request_id=created.id,
        review_id=secondary_started_review.id,
        review_etag=secondary_started_review.review_etag,
        decision="APPROVE",
        decision_reason="Secondary reviewer sign-off.",
        return_comment=None,
    )
    assert approved_review.status == "APPROVED"
    assert approved_request.status == "APPROVED"
    assert approved_request.final_decision_by == "reviewer-2"

    closed_queue = service.list_export_review_queue(
        current_user=reviewer_1,
        project_id="project-1",
    )
    assert len(closed_queue) == 0
    approved_queue = service.list_export_review_queue(
        current_user=reviewer_1,
        project_id="project-1",
        status="APPROVED",
    )
    assert len(approved_queue) == 1


def test_review_decision_validation_and_access_restrictions() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    reviewer = _principal(user_id="reviewer-1")
    auditor = _principal(user_id="auditor-1", platform_roles=("AUDITOR",))
    admin_as_requester = _principal(user_id="researcher-1", platform_roles=("ADMIN",))

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Request to validate review decision controls.",
        bundle_profile=None,
    )
    queue = service.list_export_review_queue(
        current_user=auditor,
        project_id="project-1",
    )
    assert len(queue) == 1

    review = service.get_export_request_reviews(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
    )[0]
    _, claimed = service.claim_export_request_review(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=review.id,
        review_etag=review.review_etag,
    )
    _, started = service.start_export_request_review(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=claimed.id,
        review_etag=claimed.review_etag,
    )

    with pytest.raises(ExportValidationError):
        service.decide_export_request(
            current_user=reviewer,
            project_id="project-1",
            export_request_id=created.id,
            review_id=started.id,
            review_etag=started.review_etag,
            decision="REJECT",
            decision_reason=None,
            return_comment=None,
        )

    with pytest.raises(ExportAccessDeniedError):
        service.decide_export_request(
            current_user=admin_as_requester,
            project_id="project-1",
            export_request_id=created.id,
            review_id=started.id,
            review_etag=started.review_etag,
            decision="APPROVE",
            decision_reason="Requester self-approval attempt.",
            return_comment=None,
        )

    with pytest.raises(ExportAccessDeniedError):
        service.claim_export_request_review(
            current_user=auditor,
            project_id="project-1",
            export_request_id=created.id,
            review_id=started.id,
            review_etag=started.review_etag,
        )


def test_stale_review_etag_conflict_is_rejected() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    reviewer = _principal(user_id="reviewer-1")

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Request for stale review etag conflict coverage.",
        bundle_profile=None,
    )
    review = service.get_export_request_reviews(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
    )[0]
    _, claimed = service.claim_export_request_review(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=review.id,
        review_etag=review.review_etag,
    )
    with pytest.raises(ExportConflictError):
        service.claim_export_request_review(
            current_user=reviewer,
            project_id="project-1",
            export_request_id=created.id,
            review_id=review.id,
            review_etag=review.review_etag,
        )
    assert claimed.review_etag != review.review_etag


def test_stale_review_etag_conflicts_are_rejected_for_release_start_and_decision() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    reviewer = _principal(user_id="reviewer-1")

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Request for stale review etag conflict checks across all writes.",
        bundle_profile=None,
    )
    review = service.get_export_request_reviews(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
    )[0]
    _, claimed = service.claim_export_request_review(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=review.id,
        review_etag=review.review_etag,
    )
    with pytest.raises(ExportConflictError):
        service.release_export_request_review(
            current_user=reviewer,
            project_id="project-1",
            export_request_id=created.id,
            review_id=review.id,
            review_etag=review.review_etag,
        )
    _, released = service.release_export_request_review(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=review.id,
        review_etag=claimed.review_etag,
    )
    with pytest.raises(ExportConflictError):
        service.start_export_request_review(
            current_user=reviewer,
            project_id="project-1",
            export_request_id=created.id,
            review_id=review.id,
            review_etag=claimed.review_etag,
        )
    _, started = service.start_export_request_review(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=review.id,
        review_etag=released.review_etag,
    )
    with pytest.raises(ExportConflictError):
        service.decide_export_request(
            current_user=reviewer,
            project_id="project-1",
            export_request_id=created.id,
            review_id=review.id,
            review_etag=released.review_etag,
            decision="APPROVE",
            decision_reason="Stale decision etag should conflict.",
            return_comment=None,
        )
    assert started.review_etag != released.review_etag


def test_return_decision_requires_return_comment() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    reviewer = _principal(user_id="reviewer-1")

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Request to validate return rationale requirements.",
        bundle_profile=None,
    )
    review = service.get_export_request_reviews(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
    )[0]
    _, claimed = service.claim_export_request_review(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=review.id,
        review_etag=review.review_etag,
    )
    _, started = service.start_export_request_review(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=claimed.id,
        review_etag=claimed.review_etag,
    )

    with pytest.raises(ExportValidationError):
        service.decide_export_request(
            current_user=reviewer,
            project_id="project-1",
            export_request_id=created.id,
            review_id=started.id,
            review_etag=started.review_etag,
            decision="RETURN",
            decision_reason=None,
            return_comment=None,
        )


def test_dual_review_blocks_same_reviewer_on_secondary_stage() -> None:
    candidate = _candidate(candidate_id="candidate-high")
    candidate = replace(
        candidate,
        artefact_manifest_json={
            **candidate.artefact_manifest_json,
            "reviewerOverrideCount": 1,
        },
    )
    store = InMemoryExportStore((candidate,))
    service = _build_service(
        store=store,
        role_map={
            "researcher-1": "RESEARCHER",
            "reviewer-1": "REVIEWER",
        },
    )
    requester = _principal(user_id="researcher-1")
    reviewer = _principal(user_id="reviewer-1")

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-high",
        purpose_statement="Dual-review request for distinct-reviewer enforcement checks.",
        bundle_profile=None,
    )
    primary = next(
        review
        for review in service.get_export_request_reviews(
            current_user=reviewer,
            project_id="project-1",
            export_request_id=created.id,
        )
        if review.review_stage == "PRIMARY"
    )
    _, claimed_primary = service.claim_export_request_review(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=primary.id,
        review_etag=primary.review_etag,
    )
    _, started_primary = service.start_export_request_review(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=claimed_primary.id,
        review_etag=claimed_primary.review_etag,
    )
    _, approved_primary = service.decide_export_request(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=started_primary.id,
        review_etag=started_primary.review_etag,
        decision="APPROVE",
        decision_reason="Primary approval",
        return_comment=None,
    )
    assert approved_primary.status == "APPROVED"

    secondary = next(
        review
        for review in service.get_export_request_reviews(
            current_user=reviewer,
            project_id="project-1",
            export_request_id=created.id,
        )
        if review.review_stage == "SECONDARY"
    )
    with pytest.raises(ExportConflictError):
        service.claim_export_request_review(
            current_user=reviewer,
            project_id="project-1",
            export_request_id=created.id,
            review_id=secondary.id,
            review_etag=secondary.review_etag,
        )
    with pytest.raises(ExportConflictError):
        service.start_export_request_review(
            current_user=reviewer,
            project_id="project-1",
            export_request_id=created.id,
            review_id=secondary.id,
            review_etag=secondary.review_etag,
        )


def test_secondary_decision_enforces_distinct_reviewer_even_if_projection_is_stale() -> None:
    candidate = _candidate(candidate_id="candidate-high")
    candidate = replace(
        candidate,
        artefact_manifest_json={
            **candidate.artefact_manifest_json,
            "reviewerOverrideCount": 1,
        },
    )
    store = InMemoryExportStore((candidate,))
    service = _build_service(
        store=store,
        role_map={
            "researcher-1": "RESEARCHER",
            "reviewer-1": "REVIEWER",
        },
    )
    requester = _principal(user_id="researcher-1")
    reviewer = _principal(user_id="reviewer-1")

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-high",
        purpose_statement="Dual-review defensive decision guard test.",
        bundle_profile=None,
    )
    primary = next(
        review
        for review in service.get_export_request_reviews(
            current_user=reviewer,
            project_id="project-1",
            export_request_id=created.id,
        )
        if review.review_stage == "PRIMARY"
    )
    _, claimed_primary = service.claim_export_request_review(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=primary.id,
        review_etag=primary.review_etag,
    )
    _, started_primary = service.start_export_request_review(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=claimed_primary.id,
        review_etag=claimed_primary.review_etag,
    )
    service.decide_export_request(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=started_primary.id,
        review_etag=started_primary.review_etag,
        decision="APPROVE",
        decision_reason="Primary approval",
        return_comment=None,
    )

    secondary = next(
        review
        for review in store._request_reviews[created.id]
        if review.review_stage == "SECONDARY"
    )
    tampered_secondary = replace(
        secondary,
        status="IN_REVIEW",
        assigned_reviewer_user_id="reviewer-1",
        assigned_at=datetime.now(UTC),
        review_etag=f"{secondary.id}-tampered-etag",
        updated_at=datetime.now(UTC),
    )
    store._request_reviews[created.id] = [
        tampered_secondary if review.id == secondary.id else review
        for review in store._request_reviews[created.id]
    ]
    with pytest.raises(ExportConflictError):
        service.decide_export_request(
            current_user=reviewer,
            project_id="project-1",
            export_request_id=created.id,
            review_id=tampered_secondary.id,
            review_etag=tampered_secondary.review_etag,
            decision="RETURN",
            decision_reason=None,
            return_comment="Secondary reviewer must be distinct.",
        )


def test_review_history_is_append_only_and_reconstructable_after_projection_updates() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    reviewer = _principal(user_id="reviewer-1")

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Request for append-only review history reconstruction checks.",
        bundle_profile=None,
    )
    review = service.get_export_request_reviews(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
    )[0]
    _, claimed = service.claim_export_request_review(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=review.id,
        review_etag=review.review_etag,
    )
    _, started = service.start_export_request_review(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=claimed.id,
        review_etag=claimed.review_etag,
    )
    _, released = service.release_export_request_review(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=started.id,
        review_etag=started.review_etag,
    )
    _, restarted = service.start_export_request_review(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=released.id,
        review_etag=released.review_etag,
    )
    returned_request, returned_review = service.decide_export_request(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=restarted.id,
        review_etag=restarted.review_etag,
        decision="RETURN",
        decision_reason=None,
        return_comment="Need corrected safeguarded output metadata.",
    )
    assert returned_request.status == "RETURNED"
    assert returned_review.status == "RETURNED"

    request_events = service.get_export_request_events(
        current_user=requester,
        project_id="project-1",
        export_request_id=created.id,
    )
    review_events = service.get_export_request_review_events(
        current_user=requester,
        project_id="project-1",
        export_request_id=created.id,
    )
    request_event_types = [event.event_type for event in request_events]
    review_event_types = [event.event_type for event in review_events]
    assert request_event_types.count("REQUEST_SUBMITTED") == 1
    assert request_event_types.count("REQUEST_REVIEW_STARTED") == 1
    assert request_event_types.count("REQUEST_RETURNED") == 1
    assert review_event_types == [
        "REVIEW_CREATED",
        "REVIEW_CLAIMED",
        "REVIEW_STARTED",
        "REVIEW_RELEASED",
        "REVIEW_STARTED",
        "REVIEW_RETURNED",
    ]
    assert review_events[-1].return_comment == returned_review.return_comment


def test_only_reviewer_and_admin_can_mutate_review_stages() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    lead = _principal(user_id="lead-1")
    admin = _principal(user_id="admin-1", platform_roles=("ADMIN",))

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Request for review-stage mutation RBAC coverage.",
        bundle_profile=None,
    )
    review = service.get_export_request_reviews(
        current_user=requester,
        project_id="project-1",
        export_request_id=created.id,
    )[0]
    with pytest.raises(ExportAccessDeniedError):
        service.claim_export_request_review(
            current_user=requester,
            project_id="project-1",
            export_request_id=created.id,
            review_id=review.id,
            review_etag=review.review_etag,
        )
    with pytest.raises(ExportAccessDeniedError):
        service.claim_export_request_review(
            current_user=lead,
            project_id="project-1",
            export_request_id=created.id,
            review_id=review.id,
            review_etag=review.review_etag,
        )
    _, admin_claimed = service.claim_export_request_review(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
        review_id=review.id,
        review_etag=review.review_etag,
    )
    assert admin_claimed.assigned_reviewer_user_id == "admin-1"


def test_gateway_receipt_attachment_projects_request_to_exported_and_tracks_history() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(
        store=store,
        role_map={
            "researcher-1": "RESEARCHER",
            "reviewer-1": "REVIEWER",
        },
    )
    requester = _principal(user_id="researcher-1")
    reviewer = _principal(user_id="reviewer-1")
    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Request that will be exported through gateway receipt attach.",
        bundle_profile=None,
    )
    review = service.get_export_request_reviews(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
    )[0]
    _, claimed = service.claim_export_request_review(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=review.id,
        review_etag=review.review_etag,
    )
    _, started = service.start_export_request_review(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=claimed.id,
        review_etag=claimed.review_etag,
    )
    approved, _ = service.decide_export_request(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=started.id,
        review_etag=started.review_etag,
        decision="APPROVE",
        decision_reason="Approved before gateway export.",
        return_comment=None,
    )
    assert approved.status == "APPROVED"

    first_exported, first_receipt = service.attach_gateway_export_request_receipt(
        export_request_id=created.id,
        gateway_user_id="service-export-gateway",
        gateway_oidc_sub="service-export-gateway",
        gateway_email="service-export-gateway@local.ukde",
        gateway_display_name="Gateway",
        receipt_key="safeguarded/exports/project-1/request-1/receipt-1.json",
        receipt_sha256="1" * 64,
        exported_at=datetime.now(UTC),
    )
    assert first_exported.status == "EXPORTED"
    assert first_exported.receipt_id == first_receipt.id

    second_exported, second_receipt = service.attach_gateway_export_request_receipt(
        export_request_id=created.id,
        gateway_user_id="service-export-gateway",
        gateway_oidc_sub="service-export-gateway",
        gateway_email="service-export-gateway@local.ukde",
        gateway_display_name="Gateway",
        receipt_key="safeguarded/exports/project-1/request-1/receipt-2.json",
        receipt_sha256="2" * 64,
        exported_at=datetime.now(UTC),
    )
    assert second_exported.status == "EXPORTED"
    assert second_receipt.attempt_number == 2
    assert second_receipt.supersedes_receipt_id == first_receipt.id

    history = service.list_export_request_receipts(
        current_user=requester,
        project_id="project-1",
        export_request_id=created.id,
    )
    assert len(history) == 2
    assert history[0].id == second_receipt.id
    assert history[1].superseded_by_receipt_id == second_receipt.id

    current = service.get_export_request_receipt(
        current_user=requester,
        project_id="project-1",
        export_request_id=created.id,
    )
    assert current.id == second_receipt.id


def test_gateway_receipt_attachment_rejects_non_approved_requests_and_invalid_prefix() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Request remains submitted for invalid gateway attach checks.",
        bundle_profile=None,
    )

    with pytest.raises(ExportConflictError):
        service.attach_gateway_export_request_receipt(
            export_request_id=created.id,
            gateway_user_id="service-export-gateway",
            gateway_oidc_sub="service-export-gateway",
            gateway_email="service-export-gateway@local.ukde",
            gateway_display_name="Gateway",
            receipt_key="safeguarded/exports/project-1/request-1/receipt-1.json",
            receipt_sha256="1" * 64,
            exported_at=datetime.now(UTC),
        )

    store.force_request_status(export_request_id=created.id, status="APPROVED")
    with pytest.raises(ExportValidationError):
        service.attach_gateway_export_request_receipt(
            export_request_id=created.id,
            gateway_user_id="service-export-gateway",
            gateway_oidc_sub="service-export-gateway",
            gateway_email="service-export-gateway@local.ukde",
            gateway_display_name="Gateway",
            receipt_key="controlled/derived/project-1/leak.json",
            receipt_sha256="1" * 64,
            exported_at=datetime.now(UTC),
        )


def test_export_operations_status_summarizes_aging_retention_and_terminal_counts() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    admin = _principal(user_id="admin-1", platform_roles=("ADMIN",))

    open_request = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Open request for operations summary coverage.",
        bundle_profile=None,
    )
    returned_request = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Returned request for retention summary coverage.",
        bundle_profile=None,
    )
    exported_request = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Exported request for terminal summary coverage.",
        bundle_profile=None,
    )

    now = datetime.now(UTC)
    store._requests[open_request.id] = replace(  # type: ignore[attr-defined]
        store._requests[open_request.id],  # type: ignore[attr-defined]
        status="IN_REVIEW",
        first_review_started_at=now - timedelta(days=41),
        sla_due_at=now - timedelta(days=35),
        last_queue_activity_at=now - timedelta(days=40),
        updated_at=now - timedelta(days=40),
    )
    store._requests[returned_request.id] = replace(  # type: ignore[attr-defined]
        store._requests[returned_request.id],  # type: ignore[attr-defined]
        status="RETURNED",
        retention_until=now + timedelta(days=3),
        updated_at=now - timedelta(days=1),
    )
    store._requests[exported_request.id] = replace(  # type: ignore[attr-defined]
        store._requests[exported_request.id],  # type: ignore[attr-defined]
        status="EXPORTED",
        retention_until=now + timedelta(days=2),
        updated_at=now - timedelta(days=1),
    )

    summary = service.get_export_operations_status(current_user=admin)

    assert summary.open_request_count == 1
    assert summary.aging_overdue_count == 1
    assert summary.stale_open_count == 1
    assert summary.reminder_due_count == 1
    assert summary.escalation_due_count == 1
    assert summary.retention_pending_count >= 2
    assert summary.terminal_exported_count == 1
    assert summary.terminal_returned_count == 1


def test_export_operations_maintenance_appends_reminder_and_escalation_events() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    admin = _principal(user_id="admin-1", platform_roles=("ADMIN",))

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Maintenance appends reminder and escalation events.",
        bundle_profile=None,
    )
    now = datetime.now(UTC)
    stale_request = replace(
        store._requests[created.id],  # type: ignore[attr-defined]
        status="IN_REVIEW",
        first_review_started_at=now - timedelta(days=5),
        sla_due_at=now - timedelta(days=3),
        last_queue_activity_at=now - timedelta(days=2),
        updated_at=now - timedelta(days=2),
    )
    store._requests[created.id] = stale_request  # type: ignore[attr-defined]
    before_activity_at = stale_request.last_queue_activity_at

    result = service.run_export_operations_maintenance(current_user=admin, batch_limit=50)

    assert result.reminders_appended >= 1
    assert result.escalations_appended >= 1
    updated_request = service.get_export_request(
        current_user=requester,
        project_id="project-1",
        export_request_id=created.id,
    )
    assert before_activity_at is not None
    assert updated_request.last_queue_activity_at is not None
    assert updated_request.last_queue_activity_at > before_activity_at
    event_types = [
        event.event_type
        for event in service.get_export_request_events(
            current_user=requester,
            project_id="project-1",
            export_request_id=created.id,
        )
    ]
    assert "REQUEST_REMINDER_SENT" in event_types
    assert "REQUEST_ESCALATED" in event_types

    second = service.run_export_operations_maintenance(current_user=admin, batch_limit=50)
    assert second.reminders_appended == 0
    assert second.escalations_appended == 0


def test_export_operations_maintenance_applies_retention_without_deleting_history() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    admin = _principal(user_id="admin-1", platform_roles=("ADMIN",))

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Retention maintenance should not delete audit history.",
        bundle_profile=None,
    )
    store._requests[created.id] = replace(  # type: ignore[attr-defined]
        store._requests[created.id],  # type: ignore[attr-defined]
        status="RETURNED",
        retention_until=None,
    )
    before_events = service.get_export_request_events(
        current_user=requester,
        project_id="project-1",
        export_request_id=created.id,
    )
    before_reviews = service.get_export_request_reviews(
        current_user=requester,
        project_id="project-1",
        export_request_id=created.id,
    )

    result = service.run_export_operations_maintenance(current_user=admin, batch_limit=20)

    assert result.retention_updates_applied >= 1
    updated = service.get_export_request(
        current_user=requester,
        project_id="project-1",
        export_request_id=created.id,
    )
    assert updated.retention_until is not None
    after_events = service.get_export_request_events(
        current_user=requester,
        project_id="project-1",
        export_request_id=created.id,
    )
    after_reviews = service.get_export_request_reviews(
        current_user=requester,
        project_id="project-1",
        export_request_id=created.id,
    )
    assert len(after_events) == len(before_events)
    assert len(after_reviews) == len(before_reviews)


def test_export_operations_routes_require_platform_roles() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    researcher = _principal(user_id="researcher-1")

    with pytest.raises(ExportAccessDeniedError):
        service.get_export_operations_status(current_user=researcher)
    with pytest.raises(ExportAccessDeniedError):
        service.run_export_operations_maintenance(current_user=researcher)


def test_approved_request_generates_initial_provenance_proof_and_summary_reads_current() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    reviewer = _principal(user_id="reviewer-1")

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Create request and ensure approval generates provenance proof.",
        bundle_profile=None,
    )
    review = service.get_export_request_reviews(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
    )[0]
    _, claimed = service.claim_export_request_review(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=review.id,
        review_etag=review.review_etag,
    )
    _, started = service.start_export_request_review(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=claimed.id,
        review_etag=claimed.review_etag,
    )
    approved_request, _ = service.decide_export_request(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=started.id,
        review_etag=started.review_etag,
        decision="APPROVE",
        decision_reason="Approved for provenance generation coverage.",
        return_comment=None,
    )
    assert approved_request.status == "APPROVED"

    proofs = service.list_export_request_provenance_proofs(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
    )
    assert len(proofs) == 1
    assert proofs[0].attempt_number == 1
    assert proofs[0].superseded_by_proof_id is None

    summary = service.get_export_request_provenance_summary(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
    )
    assert summary["currentProofId"] == proofs[0].id
    assert summary["rootSha256"] == proofs[0].root_sha256
    assert summary["proofAttemptCount"] == 1

    current = service.get_export_request_current_provenance_proof(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
    )
    assert current["proof"].id == proofs[0].id
    assert isinstance(current["artifact"], dict)


def test_provenance_regeneration_is_append_only_and_admin_only() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    reviewer = _principal(user_id="reviewer-1")
    admin = _principal(user_id="admin-1", platform_roles=("ADMIN",))

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Create request and verify append-only provenance regeneration.",
        bundle_profile=None,
    )
    review = service.get_export_request_reviews(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
    )[0]
    _, claimed = service.claim_export_request_review(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=review.id,
        review_etag=review.review_etag,
    )
    _, started = service.start_export_request_review(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=claimed.id,
        review_etag=claimed.review_etag,
    )
    service.decide_export_request(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        review_id=started.id,
        review_etag=started.review_etag,
        decision="APPROVE",
        decision_reason="Approval before regeneration coverage.",
        return_comment=None,
    )

    with pytest.raises(ExportAccessDeniedError):
        service.regenerate_export_request_provenance_proof(
            current_user=reviewer,
            project_id="project-1",
            export_request_id=created.id,
        )

    regenerated = service.regenerate_export_request_provenance_proof(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
    )
    assert regenerated.attempt_number == 2
    assert regenerated.supersedes_proof_id is not None

    proofs = service.list_export_request_provenance_proofs(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
    )
    assert len(proofs) == 2
    assert proofs[0].id == regenerated.id
    assert proofs[1].superseded_by_proof_id == regenerated.id

    by_id = service.get_export_request_provenance_proof(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        proof_id=proofs[1].id,
    )
    assert by_id["proof"].id == proofs[1].id


def test_provenance_reads_require_approved_or_exported_status() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    reviewer = _principal(user_id="reviewer-1")

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Create request and ensure non-approved provenance reads are blocked.",
        bundle_profile=None,
    )

    with pytest.raises(ExportConflictError):
        service.get_export_request_provenance_summary(
            current_user=reviewer,
            project_id="project-1",
            export_request_id=created.id,
        )


def _approve_request(
    *,
    service: ExportService,
    request_id: str,
    reviewer: SessionPrincipal,
) -> ExportRequestRecord:
    review = service.get_export_request_reviews(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=request_id,
    )[0]
    _, claimed = service.claim_export_request_review(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=request_id,
        review_id=review.id,
        review_etag=review.review_etag,
    )
    _, started = service.start_export_request_review(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=request_id,
        review_id=claimed.id,
        review_etag=claimed.review_etag,
    )
    approved, _ = service.decide_export_request(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=request_id,
        review_id=started.id,
        review_etag=started.review_etag,
        decision="APPROVE",
        decision_reason="Approve for bundle workflow coverage.",
        return_comment=None,
    )
    return approved


def test_bundle_creation_requires_approved_or_exported_request() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    reviewer = _principal(user_id="reviewer-1")

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Attempt bundle creation before approval should fail.",
        bundle_profile=None,
    )

    with pytest.raises(ExportConflictError):
        service.create_export_request_bundle(
            current_user=reviewer,
            project_id="project-1",
            export_request_id=created.id,
            bundle_kind="SAFEGUARDED_DEPOSIT",
        )


def test_bundle_create_is_idempotent_and_rebuild_is_append_only() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    reviewer = _principal(user_id="reviewer-1")

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Create and rebuild deposit bundles with append-only lineage.",
        bundle_profile=None,
    )
    _approve_request(service=service, request_id=created.id, reviewer=reviewer)

    first = service.create_export_request_bundle(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        bundle_kind="SAFEGUARDED_DEPOSIT",
    )
    second = service.create_export_request_bundle(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        bundle_kind="SAFEGUARDED_DEPOSIT",
    )
    assert first.id == second.id
    assert first.attempt_number == 1

    rebuilt = service.rebuild_export_request_bundle(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=first.id,
    )
    assert rebuilt.attempt_number == 2
    assert rebuilt.supersedes_bundle_id == first.id

    bundles = service.list_export_request_bundles(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
    )
    assert len(bundles) == 2
    assert bundles[0].id == rebuilt.id
    assert bundles[1].superseded_by_bundle_id == rebuilt.id


def test_bundle_detail_contains_proof_artifact_and_verification_material() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    reviewer = _principal(user_id="reviewer-1")

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Bundle detail should include provenance proof and verification material.",
        bundle_profile=None,
    )
    _approve_request(service=service, request_id=created.id, reviewer=reviewer)

    bundle = service.create_export_request_bundle(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        bundle_kind="SAFEGUARDED_DEPOSIT",
    )
    detail = service.get_export_request_bundle(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=bundle.id,
    )
    artifact = detail["artifact"]
    assert isinstance(artifact, dict)
    assert isinstance(artifact.get("provenanceProofArtifact"), dict)
    assert isinstance(artifact.get("provenanceVerificationMaterial"), dict)
    assert isinstance(artifact.get("provenanceSignature"), dict)
    computed_sha = hashlib.sha256(str(artifact).encode("utf-8")).hexdigest()
    assert bundle.bundle_sha256 == computed_sha


def test_bundle_events_are_append_only_and_ordered() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    reviewer = _principal(user_id="reviewer-1")

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Bundle events should preserve ordered append-only lifecycle history.",
        bundle_profile=None,
    )
    _approve_request(service=service, request_id=created.id, reviewer=reviewer)

    first = service.create_export_request_bundle(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        bundle_kind="SAFEGUARDED_DEPOSIT",
    )
    events_first = service.list_export_request_bundle_events(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=first.id,
    )
    assert [event.event_type for event in events_first] == [
        "BUNDLE_BUILD_QUEUED",
        "BUNDLE_BUILD_STARTED",
        "BUNDLE_BUILD_SUCCEEDED",
    ]

    rebuilt = service.rebuild_export_request_bundle(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=first.id,
    )
    events_rebuilt = service.list_export_request_bundle_events(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=rebuilt.id,
    )
    assert [event.event_type for event in events_rebuilt][:2] == [
        "BUNDLE_REBUILD_REQUESTED",
        "BUNDLE_BUILD_QUEUED",
    ]


def test_controlled_evidence_bundle_access_and_mutation_rbac() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    reviewer = _principal(user_id="reviewer-1")
    admin = _principal(user_id="admin-1", platform_roles=("ADMIN",))
    auditor = _principal(user_id="auditor-1", platform_roles=("AUDITOR",))

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Controlled evidence bundle access should be restricted.",
        bundle_profile=None,
    )
    _approve_request(service=service, request_id=created.id, reviewer=reviewer)

    with pytest.raises(ExportAccessDeniedError):
        service.create_export_request_bundle(
            current_user=reviewer,
            project_id="project-1",
            export_request_id=created.id,
            bundle_kind="CONTROLLED_EVIDENCE",
        )

    controlled = service.create_export_request_bundle(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
        bundle_kind="CONTROLLED_EVIDENCE",
    )
    with pytest.raises(ExportAccessDeniedError):
        service.get_export_request_bundle(
            current_user=requester,
            project_id="project-1",
            export_request_id=created.id,
            bundle_id=controlled.id,
        )
    detail = service.get_export_request_bundle(
        current_user=auditor,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=controlled.id,
    )
    assert detail["bundle"].id == controlled.id


def test_bundle_cancel_rejects_terminal_states() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    reviewer = _principal(user_id="reviewer-1")

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Cancel should be rejected for terminal bundle attempts.",
        bundle_profile=None,
    )
    _approve_request(service=service, request_id=created.id, reviewer=reviewer)
    bundle = service.create_export_request_bundle(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        bundle_kind="SAFEGUARDED_DEPOSIT",
    )
    with pytest.raises(ExportConflictError):
        service.cancel_export_request_bundle(
            current_user=reviewer,
            project_id="project-1",
            export_request_id=created.id,
            bundle_id=bundle.id,
        )


def test_bundle_verification_is_admin_only_and_auditor_read_only() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    reviewer = _principal(user_id="reviewer-1")
    admin = _principal(user_id="admin-1", platform_roles=("ADMIN",))
    auditor = _principal(user_id="auditor-1", platform_roles=("AUDITOR",))

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Verify safeguarded bundle role boundaries.",
        bundle_profile=None,
    )
    _approve_request(service=service, request_id=created.id, reviewer=reviewer)
    bundle = service.create_export_request_bundle(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        bundle_kind="SAFEGUARDED_DEPOSIT",
    )

    with pytest.raises(ExportAccessDeniedError):
        service.start_export_request_bundle_verification(
            current_user=reviewer,
            project_id="project-1",
            export_request_id=created.id,
            bundle_id=bundle.id,
        )

    run = service.start_export_request_bundle_verification(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=bundle.id,
    )
    assert run.attempt_number == 1
    assert run.status == "SUCCEEDED"

    verification = service.get_export_request_bundle_verification(
        current_user=auditor,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=bundle.id,
    )
    assert verification["latestAttempt"] is not None

    with pytest.raises(ExportAccessDeniedError):
        service.cancel_export_request_bundle_verification_run(
            current_user=auditor,
            project_id="project-1",
            export_request_id=created.id,
            bundle_id=bundle.id,
            verification_run_id=run.id,
        )


def test_bundle_verification_runs_are_append_only_and_keep_last_success_projection() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    reviewer = _principal(user_id="reviewer-1")
    admin = _principal(user_id="admin-1", platform_roles=("ADMIN",))

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Verify append-only bundle verification lineage.",
        bundle_profile=None,
    )
    _approve_request(service=service, request_id=created.id, reviewer=reviewer)
    bundle = service.create_export_request_bundle(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        bundle_kind="SAFEGUARDED_DEPOSIT",
    )

    first = service.start_export_request_bundle_verification(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=bundle.id,
    )
    assert first.status == "SUCCEEDED"

    # Tamper one bundled file to force the next verification attempt to fail.
    artifact = dict(store._bundle_artifacts[bundle.id])
    tampered_metadata = dict(artifact.get("metadata", {}))
    tampered_metadata["bundleKind"] = "TAMPERED"
    artifact["metadata"] = tampered_metadata
    store._bundle_artifacts[bundle.id] = artifact

    second = service.start_export_request_bundle_verification(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=bundle.id,
    )
    assert second.status == "FAILED"
    assert second.supersedes_verification_run_id == first.id

    runs = service.list_export_request_bundle_verification_runs(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=bundle.id,
    )
    assert len(runs) == 2
    assert runs[0].id == second.id
    assert runs[1].superseded_by_verification_run_id == second.id

    status_payload = service.get_export_request_bundle_verification_status(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=bundle.id,
    )
    projection = status_payload["projection"]
    assert isinstance(projection, BundleVerificationProjectionRecord)
    assert projection.status == "VERIFIED"
    assert projection.last_verification_run_id == first.id


def test_bundle_verification_start_requires_succeeded_bundle_attempt() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    reviewer = _principal(user_id="reviewer-1")
    admin = _principal(user_id="admin-1", platform_roles=("ADMIN",))

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Ensure verification cannot start for non-succeeded bundles.",
        bundle_profile=None,
    )
    _approve_request(service=service, request_id=created.id, reviewer=reviewer)
    bundle = service.create_export_request_bundle(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        bundle_kind="SAFEGUARDED_DEPOSIT",
    )
    store._deposit_bundles[created.id] = [
        replace(item, status="RUNNING") if item.id == bundle.id else item
        for item in store._deposit_bundles.get(created.id, [])
    ]

    with pytest.raises(ExportConflictError):
        service.start_export_request_bundle_verification(
            current_user=admin,
            project_id="project-1",
            export_request_id=created.id,
            bundle_id=bundle.id,
        )


def test_bundle_verification_cancel_rejects_terminal_and_allows_running() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    reviewer = _principal(user_id="reviewer-1")
    admin = _principal(user_id="admin-1", platform_roles=("ADMIN",))

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Cancel verification should only allow queued/running runs.",
        bundle_profile=None,
    )
    _approve_request(service=service, request_id=created.id, reviewer=reviewer)
    bundle = service.create_export_request_bundle(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        bundle_kind="SAFEGUARDED_DEPOSIT",
    )
    terminal = service.start_export_request_bundle_verification(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=bundle.id,
    )
    with pytest.raises(ExportConflictError):
        service.cancel_export_request_bundle_verification_run(
            current_user=admin,
            project_id="project-1",
            export_request_id=created.id,
            bundle_id=bundle.id,
            verification_run_id=terminal.id,
        )

    now = datetime.now(UTC)
    running = BundleVerificationRunRecord(
        id=f"{bundle.id}-verify-running",
        project_id="project-1",
        bundle_id=bundle.id,
        attempt_number=99,
        supersedes_verification_run_id=terminal.id,
        superseded_by_verification_run_id=None,
        status="RUNNING",
        result_json={},
        created_by=admin.user_id,
        created_at=now,
        started_at=now,
        finished_at=None,
        canceled_by=None,
        canceled_at=None,
        failure_reason=None,
    )
    store._bundle_verification_runs[bundle.id] = [running] + [
        replace(item, superseded_by_verification_run_id=running.id)
        if item.id == terminal.id
        else item
        for item in store._bundle_verification_runs.get(bundle.id, [])
    ]
    canceled = service.cancel_export_request_bundle_verification_run(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=bundle.id,
        verification_run_id=running.id,
    )
    assert canceled.status == "CANCELED"


def test_bundle_validation_admin_only_and_controlled_read_boundaries() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    reviewer = _principal(user_id="reviewer-1")
    admin = _principal(user_id="admin-1", platform_roles=("ADMIN",))
    auditor = _principal(user_id="auditor-1", platform_roles=("AUDITOR",))
    safeguarded_profile = "SAFEGUARDED_DEPOSIT_CORE_V1"
    controlled_profile = "CONTROLLED_EVIDENCE_CORE_V1"

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Validate safeguarded and controlled bundle access boundaries.",
        bundle_profile=None,
    )
    _approve_request(service=service, request_id=created.id, reviewer=reviewer)

    safeguarded = service.create_export_request_bundle(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        bundle_kind="SAFEGUARDED_DEPOSIT",
    )
    service.start_export_request_bundle_verification(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=safeguarded.id,
    )
    with pytest.raises(ExportAccessDeniedError):
        service.start_export_request_bundle_validation(
            current_user=reviewer,
            project_id="project-1",
            export_request_id=created.id,
            bundle_id=safeguarded.id,
            profile_id=safeguarded_profile,
        )
    safeguarded_run = service.start_export_request_bundle_validation(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=safeguarded.id,
        profile_id=safeguarded_profile,
    )
    assert safeguarded_run.status == "SUCCEEDED"

    controlled = service.create_export_request_bundle(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
        bundle_kind="CONTROLLED_EVIDENCE",
    )
    service.start_export_request_bundle_verification(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=controlled.id,
    )
    controlled_run = service.start_export_request_bundle_validation(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=controlled.id,
        profile_id=controlled_profile,
    )
    assert controlled_run.status == "SUCCEEDED"

    with pytest.raises(ExportAccessDeniedError):
        service.get_export_request_bundle_validation_status(
            current_user=reviewer,
            project_id="project-1",
            export_request_id=created.id,
            bundle_id=controlled.id,
            profile_id=controlled_profile,
        )
    controlled_status = service.get_export_request_bundle_validation_status(
        current_user=auditor,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=controlled.id,
        profile_id=controlled_profile,
    )
    assert controlled_status["latestAttempt"] is not None


def test_bundle_validation_runs_preserve_ready_projection_on_failed_retry() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    reviewer = _principal(user_id="reviewer-1")
    admin = _principal(user_id="admin-1", platform_roles=("ADMIN",))
    profile_id = "SAFEGUARDED_DEPOSIT_CORE_V1"

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Validation retries should preserve last known good readiness.",
        bundle_profile=None,
    )
    _approve_request(service=service, request_id=created.id, reviewer=reviewer)
    bundle = service.create_export_request_bundle(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        bundle_kind="SAFEGUARDED_DEPOSIT",
    )
    service.start_export_request_bundle_verification(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=bundle.id,
    )

    first = service.start_export_request_bundle_validation(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=bundle.id,
        profile_id=profile_id,
    )
    assert first.status == "SUCCEEDED"

    artifact = dict(store._bundle_artifacts[bundle.id])
    metadata = dict(artifact.get("metadata", {}))
    nested_metadata = (
        dict(metadata.get("metadata"))
        if isinstance(metadata.get("metadata"), dict)
        else {}
    )
    nested_metadata.pop("releasePackSha256", None)
    metadata["metadata"] = nested_metadata
    artifact["metadata"] = metadata
    store._bundle_artifacts[bundle.id] = artifact

    second = service.start_export_request_bundle_validation(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=bundle.id,
        profile_id=profile_id,
    )
    assert second.status == "FAILED"
    assert second.supersedes_validation_run_id == first.id

    runs = service.list_export_request_bundle_validation_runs(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=bundle.id,
        profile_id=profile_id,
    )
    assert len(runs) == 2
    assert runs[0].id == second.id
    assert runs[1].superseded_by_validation_run_id == second.id

    status_payload = service.get_export_request_bundle_validation_status(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=bundle.id,
        profile_id=profile_id,
    )
    projection = status_payload["projection"]
    assert isinstance(projection, BundleValidationProjectionRecord)
    assert projection.status == "READY"
    assert projection.last_validation_run_id == first.id
    latest_attempt = status_payload["latestAttempt"]
    last_successful = status_payload["lastSuccessfulAttempt"]
    assert isinstance(latest_attempt, BundleValidationRunRecord)
    assert latest_attempt.id == second.id
    assert isinstance(last_successful, BundleValidationRunRecord)
    assert last_successful.id == first.id


def test_bundle_validation_pending_then_failed_without_prior_success() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    reviewer = _principal(user_id="reviewer-1")
    admin = _principal(user_id="admin-1", platform_roles=("ADMIN",))
    profile_id = "SAFEGUARDED_DEPOSIT_CORE_V1"

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Pending validation should move to failed with no prior success.",
        bundle_profile=None,
    )
    _approve_request(service=service, request_id=created.id, reviewer=reviewer)
    bundle = service.create_export_request_bundle(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        bundle_kind="SAFEGUARDED_DEPOSIT",
    )

    pending = service.get_export_request_bundle_validation_status(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=bundle.id,
        profile_id=profile_id,
    )
    assert pending["projection"] is None
    assert pending["latestAttempt"] is None

    failed = service.start_export_request_bundle_validation(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=bundle.id,
        profile_id=profile_id,
    )
    assert failed.status == "FAILED"

    status_payload = service.get_export_request_bundle_validation_status(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=bundle.id,
        profile_id=profile_id,
    )
    projection = status_payload["projection"]
    assert isinstance(projection, BundleValidationProjectionRecord)
    assert projection.status == "FAILED"
    assert projection.last_validation_run_id == failed.id
    assert status_payload["lastSuccessfulAttempt"] is None


def test_bundle_validation_cancel_rejects_terminal_and_allows_running() -> None:
    store = InMemoryExportStore((_candidate(candidate_id="candidate-1"),))
    service = _build_service(store=store)
    requester = _principal(user_id="researcher-1")
    reviewer = _principal(user_id="reviewer-1")
    admin = _principal(user_id="admin-1", platform_roles=("ADMIN",))
    profile_id = "SAFEGUARDED_DEPOSIT_CORE_V1"

    created = service.create_export_request(
        current_user=requester,
        project_id="project-1",
        candidate_snapshot_id="candidate-1",
        purpose_statement="Cancel validation should only allow queued/running runs.",
        bundle_profile=None,
    )
    _approve_request(service=service, request_id=created.id, reviewer=reviewer)
    bundle = service.create_export_request_bundle(
        current_user=reviewer,
        project_id="project-1",
        export_request_id=created.id,
        bundle_kind="SAFEGUARDED_DEPOSIT",
    )
    service.start_export_request_bundle_verification(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=bundle.id,
    )
    terminal = service.start_export_request_bundle_validation(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=bundle.id,
        profile_id=profile_id,
    )
    with pytest.raises(ExportConflictError):
        service.cancel_export_request_bundle_validation_run(
            current_user=admin,
            project_id="project-1",
            export_request_id=created.id,
            bundle_id=bundle.id,
            profile_id=profile_id,
            validation_run_id=terminal.id,
        )

    now = datetime.now(UTC)
    running = BundleValidationRunRecord(
        id=f"{bundle.id}-validate-running",
        project_id="project-1",
        bundle_id=bundle.id,
        profile_id=profile_id,
        profile_snapshot_key=f"profiles/{profile_id.lower()}/snapshot.json",
        profile_snapshot_sha256="a" * 64,
        status="RUNNING",
        attempt_number=99,
        supersedes_validation_run_id=terminal.id,
        superseded_by_validation_run_id=None,
        result_json={},
        failure_reason=None,
        created_by=admin.user_id,
        created_at=now,
        started_at=now,
        finished_at=None,
        canceled_by=None,
        canceled_at=None,
    )
    store._bundle_validation_runs[(bundle.id, profile_id)] = [running] + [
        replace(item, superseded_by_validation_run_id=running.id)
        if item.id == terminal.id
        else item
        for item in store._bundle_validation_runs.get((bundle.id, profile_id), [])
    ]
    canceled = service.cancel_export_request_bundle_validation_run(
        current_user=admin,
        project_id="project-1",
        export_request_id=created.id,
        bundle_id=bundle.id,
        profile_id=profile_id,
        validation_run_id=running.id,
    )
    assert canceled.status == "CANCELED"
