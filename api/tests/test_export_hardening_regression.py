from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

from app.audit.service import get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.core.storage_boundaries import resolve_storage_boundary
from app.exports.models import (
    ExportCandidateSnapshotRecord,
    ExportRequestEventRecord,
    ExportRequestRecord,
    ExportRequestReviewEventRecord,
    ExportRequestReviewRecord,
)
from app.exports.validation import build_export_validation_summary
from app.main import app
from fastapi.testclient import TestClient

EVALUATION_ARTIFACT_PATH = (
    Path(__file__).parent / ".artifacts" / "export-hardening" / "last-evaluation.json"
)


class SpyAuditService:
    def __init__(self) -> None:
        self.recorded: list[dict[str, object]] = []

    def record_event_best_effort(self, **kwargs):  # type: ignore[no-untyped-def]
        self.recorded.append(kwargs)
        return None


def _canonical_json_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


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


def _candidate() -> ExportCandidateSnapshotRecord:
    now = datetime.now(UTC)
    return ExportCandidateSnapshotRecord(
        id="candidate-1",
        project_id="project-1",
        source_phase="PHASE6",
        source_artifact_kind="REDACTION_RUN_OUTPUT",
        source_run_id="run-1",
        source_artifact_id="run-output-1",
        governance_run_id="run-1",
        governance_manifest_id="manifest-1",
        governance_ledger_id="ledger-1",
        governance_manifest_sha256="a" * 64,
        governance_ledger_sha256="b" * 64,
        policy_snapshot_hash="c" * 64,
        policy_id="policy-1",
        policy_family_id="family-1",
        policy_version="v1",
        candidate_kind="SAFEGUARDED_PREVIEW",
        artefact_manifest_json={
            "fileList": [
                {
                    "fileName": "output-manifest.json",
                    "sha256": "d" * 64,
                    "fileSizeBytes": 128,
                    "sourceRef": "controlled/derived/redaction-run-1/output-manifest.json",
                    "sourceKind": "RUN_OUTPUT_MANIFEST",
                }
            ],
            "approvedModelReferencesByRole": {
                "TRANSCRIPTION_PRIMARY": {
                    "modelId": "model-main",
                    "checksumSha256": "e" * 64,
                }
            },
            "redactionCountsByCategory": {"PERSON_NAME": 3},
            "reviewerOverrideCount": 0,
            "conservativeAreaMaskCount": 0,
            "riskFlags": [],
        },
        candidate_sha256="f" * 64,
        eligibility_status="ELIGIBLE",
        supersedes_candidate_snapshot_id=None,
        superseded_by_candidate_snapshot_id=None,
        created_by="reviewer-1",
        created_at=now,
    )


def _release_pack(candidate: ExportCandidateSnapshotRecord) -> tuple[dict[str, object], str, str]:
    manifest_sha = hashlib.sha256(
        _canonical_json_bytes(candidate.artefact_manifest_json)
    ).hexdigest()
    payload: dict[str, object] = {
        "schemaVersion": 1,
        "requestScope": "REQUEST_FROZEN",
        "requestId": "request-1",
        "candidateSnapshotId": candidate.id,
        "candidateSha256": candidate.candidate_sha256,
        "candidateKind": candidate.candidate_kind,
        "candidateSourcePhase": candidate.source_phase,
        "candidateSourceArtifactKind": candidate.source_artifact_kind,
        "candidateSourceArtifactId": candidate.source_artifact_id,
        "candidateSourceRunId": candidate.source_run_id,
        "requestRevision": 1,
        "requestPurposeStatement": "Canonical release-pack validation baseline.",
        "bundleProfile": None,
        "files": [
            {
                "fileName": "output-manifest.json",
                "fileSizeBytes": 128,
                "sha256": "d" * 64,
                "sourceRef": "output-manifest.json",
                "sourceKind": "RUN_OUTPUT_MANIFEST",
            }
        ],
        "fileCount": 1,
        "sourceArtefactReferences": [],
        "manifestIntegrity": {
            "artefactManifestSha256": manifest_sha,
            "status": "MATCHED_CANDIDATE_SNAPSHOT",
        },
        "policyLineage": {
            "policySnapshotHash": candidate.policy_snapshot_hash,
            "policyId": candidate.policy_id,
            "policyFamilyId": candidate.policy_family_id,
            "policyVersion": candidate.policy_version,
        },
        "approvedModelReferencesByRole": {
            "TRANSCRIPTION_PRIMARY": {
                "modelId": "model-main",
                "checksumSha256": "e" * 64,
            }
        },
        "redactionCountsByCategory": {"PERSON_NAME": 3},
        "reviewerOverrideCount": 0,
        "conservativeAreaMaskCount": 0,
        "riskFlags": [],
        "classifierReasonCodes": [],
        "riskClassification": "STANDARD",
        "reviewPath": "SINGLE",
        "requiresSecondReview": False,
        "governancePins": {
            "governanceRunId": candidate.governance_run_id,
            "governanceManifestId": candidate.governance_manifest_id,
            "governanceLedgerId": candidate.governance_ledger_id,
            "governanceManifestSha256": candidate.governance_manifest_sha256,
            "governanceLedgerSha256": candidate.governance_ledger_sha256,
        },
        "releaseReviewChecklist": [
            "candidate_snapshot_is_immutable",
            "governance_manifest_and_ledger_are_pinned",
            "policy_lineage_is_pinned",
            "risk_classification_is_pinned_at_submission",
        ],
    }
    sha = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    key = f"exports/requests/request-1/release-pack/{sha}.json"
    return payload, sha, key


def _request(
    candidate: ExportCandidateSnapshotRecord,
) -> tuple[ExportRequestRecord, dict[str, object], str, str]:
    now = datetime.now(UTC)
    release_pack, release_pack_sha, release_pack_key = _release_pack(candidate)
    record = ExportRequestRecord(
        id="request-1",
        project_id="project-1",
        candidate_snapshot_id=candidate.id,
        candidate_origin_phase=candidate.source_phase,
        candidate_kind=candidate.candidate_kind,
        bundle_profile=None,
        risk_classification="STANDARD",
        risk_reason_codes_json=(),
        review_path="SINGLE",
        requires_second_review=False,
        supersedes_export_request_id=None,
        superseded_by_export_request_id=None,
        request_revision=1,
        purpose_statement="Canonical release-pack validation baseline.",
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
        release_pack_key=release_pack_key,
        release_pack_sha256=release_pack_sha,
        release_pack_json=release_pack,
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
    return record, release_pack, release_pack_sha, release_pack_key


def _request_events(request: ExportRequestRecord) -> tuple[ExportRequestEventRecord, ...]:
    return (
        ExportRequestEventRecord(
            id="event-1",
            export_request_id=request.id,
            event_type="REQUEST_SUBMITTED",
            from_status=None,
            to_status="SUBMITTED",
            actor_user_id=request.submitted_by,
            reason=None,
            created_at=request.submitted_at,
        ),
    )


def _reviews(request: ExportRequestRecord) -> tuple[ExportRequestReviewRecord, ...]:
    return (
        ExportRequestReviewRecord(
            id="review-1",
            export_request_id=request.id,
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
            created_at=request.submitted_at,
            updated_at=request.updated_at,
        ),
    )


def _review_events(request: ExportRequestRecord) -> tuple[ExportRequestReviewEventRecord, ...]:
    return (
        ExportRequestReviewEventRecord(
            id="review-event-1",
            review_id="review-1",
            export_request_id=request.id,
            review_stage="PRIMARY",
            event_type="REVIEW_CREATED",
            actor_user_id=request.submitted_by,
            assigned_reviewer_user_id=None,
            decision_reason=None,
            return_comment=None,
            created_at=request.submitted_at,
        ),
    )


def test_export_hardening_regression_suite_writes_deterministic_artifact() -> None:
    candidate = _candidate()
    request, expected_pack, expected_sha, expected_key = _request(candidate)
    request_events = _request_events(request)
    reviews = _reviews(request)
    review_events = _review_events(request)

    canonical_summary = build_export_validation_summary(
        request=request,
        candidate=candidate,
        expected_release_pack=expected_pack,
        expected_release_pack_sha256=expected_sha,
        expected_release_pack_key=expected_key,
        request_events=request_events,
        reviews=reviews,
        review_events=review_events,
        receipts=(),
    )

    tampered_request = ExportRequestRecord(
        **{
            **request.__dict__,
            "release_pack_json": {
                **request.release_pack_json,
                "candidateSnapshotId": "tampered-candidate",
            },
        }
    )
    tampered_summary = build_export_validation_summary(
        request=tampered_request,
        candidate=candidate,
        expected_release_pack=expected_pack,
        expected_release_pack_sha256=expected_sha,
        expected_release_pack_key=expected_key,
        request_events=request_events,
        reviews=reviews,
        review_events=review_events,
        receipts=(),
    )

    boundary = resolve_storage_boundary(
        SimpleNamespace(
            storage_controlled_raw_prefix="controlled/raw/",
            storage_controlled_derived_prefix="controlled/derived/",
            storage_safeguarded_exports_prefix="safeguarded/exports/",
        )
    )
    storage_checks = {
        "appWriterBlockedForSafeguardedExports": not boundary.can_write(
            writer="app",
            object_key="safeguarded/exports/project-1/request-1/receipt.json",
        ),
        "gatewayWriterAllowedForSafeguardedExports": boundary.can_write(
            writer="export_gateway",
            object_key="safeguarded/exports/project-1/request-1/receipt.json",
        ),
        "gatewayWriterBlockedForControlledDerived": not boundary.can_write(
            writer="export_gateway",
            object_key="controlled/derived/project-1/run-1/output.json",
        ),
    }

    client = TestClient(app)
    spy_audit = SpyAuditService()
    app.dependency_overrides[get_audit_service] = lambda: spy_audit
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="researcher-1"
    )
    try:
        candidate_download = client.get(
            "/projects/project-1/export-candidates/candidate-1/download"
        )
        request_download = client.get("/projects/project-1/export-requests/request-1/download")
        bundle_download = client.get("/projects/project-1/export-bundles/request-1/download")
        denied_internal_attach = client.post(
            "/internal/export-requests/request-1/receipt",
            json={
                "receiptKey": "safeguarded/exports/project-1/request-1/receipt-1.json",
                "receiptSha256": "1" * 64,
                "exportedAt": datetime.now(UTC).isoformat(),
            },
        )
        denied_public_attach = client.post(
            "/projects/project-1/export-requests/request-1/receipt",
            json={
                "receiptKey": "safeguarded/exports/project-1/request-1/receipt-1.json",
                "receiptSha256": "1" * 64,
                "exportedAt": datetime.now(UTC).isoformat(),
            },
        )
    finally:
        app.dependency_overrides.clear()

    access_denied_events = [
        event for event in spy_audit.recorded if event.get("event_type") == "ACCESS_DENIED"
    ]
    denied_metadata_safe = all(
        isinstance(event.get("metadata"), dict)
        and "receiptSha256" not in event["metadata"]  # type: ignore[index]
        and "receiptKey" not in event["metadata"]  # type: ignore[index]
        for event in access_denied_events
    )
    egress_checks = {
        "candidateDownloadBypassClosed": candidate_download.status_code == 404,
        "requestDownloadBypassClosed": request_download.status_code == 404,
        "bundleDownloadBypassClosed": bundle_download.status_code == 404,
        "internalReceiptAttachDeniedWithoutGatewayAuth": denied_internal_attach.status_code == 403,
        "publicReceiptMutationBlocked": denied_public_attach.status_code in {404, 405},
        "deniedAttemptsAuditLoggedSafely": len(access_denied_events) >= 1 and denied_metadata_safe,
    }

    evaluation_payload = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "passed": (
            canonical_summary.passed
            and not tampered_summary.passed
            and all(storage_checks.values())
            and all(egress_checks.values())
        ),
        "releasePackValidation": {
            "canonicalPassed": canonical_summary.release_pack.passed,
            "tamperedDetected": not tampered_summary.release_pack.passed,
            "canonical": canonical_summary.release_pack.to_payload(),
            "tampered": tampered_summary.release_pack.to_payload(),
        },
        "auditCompletenessValidation": {
            "canonicalPassed": canonical_summary.audit_completeness.passed,
            "canonical": canonical_summary.audit_completeness.to_payload(),
        },
        "storageBoundaryChecks": storage_checks,
        "egressDenialChecks": egress_checks,
    }
    EVALUATION_ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVALUATION_ARTIFACT_PATH.write_text(
        json.dumps(evaluation_payload, indent=2) + "\n",
        encoding="utf-8",
    )

    assert evaluation_payload["passed"], json.dumps(evaluation_payload, indent=2)
