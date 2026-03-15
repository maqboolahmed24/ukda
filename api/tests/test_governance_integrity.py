from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.documents.evidence_ledger import canonical_evidence_ledger_payload
from app.documents.governance import (
    LedgerVerificationRunRecord,
    RedactionEvidenceLedgerRecord,
    RedactionManifestRecord,
    resolve_governance_ready_pair_from_attempts,
)
from app.documents.governance_integrity import (
    build_governance_integrity_evaluation,
    reconcile_ledger_payload,
    reconcile_manifest_payload,
    validate_candidate_snapshot_handoff,
    validate_manifest_hash,
    validate_provenance_handoff,
    write_governance_integrity_artifact,
)
from app.documents.redaction_preview import (
    canonical_preview_manifest_bytes,
    canonical_preview_manifest_payload,
)

EVALUATION_ARTIFACT_PATH = (
    Path(__file__).parent
    / ".artifacts"
    / "governance-integrity"
    / "last-evaluation.json"
)


def _approved_snapshot_payload() -> dict[str, object]:
    return {
        "runId": "run-1",
        "run": {
            "policySnapshotHash": "policy-hash-1",
            "policyId": "policy-main",
            "policyFamilyId": "policy-family-main",
            "policyVersion": "v1",
        },
        "findings": [
            {
                "id": "finding-1",
                "decisionStatus": "APPROVED",
                "pageId": "page-1",
                "pageIndex": 1,
                "lineId": "line-1",
                "category": "EMAIL",
                "actionType": "MASK",
                "spanStart": 16,
                "spanEnd": 36,
                "spanBasisKind": "LINE_TEXT",
                "spanBasisRef": "line-1",
                "basisPrimary": "NER",
                "basisSecondaryJson": {"detector": "regex-email"},
                "decisionBy": "reviewer-1",
                "decisionAt": "2026-03-14T11:00:00+00:00",
            },
            {
                "id": "finding-2",
                "decisionStatus": "OVERRIDDEN",
                "pageId": "page-2",
                "pageIndex": 2,
                "lineId": "line-4",
                "category": "PHONE",
                "actionType": "MASK",
                "basisPrimary": "RULE",
                "decisionBy": "reviewer-2",
                "decisionAt": "2026-03-14T11:05:00+00:00",
                "decisionReason": "Confirmed direct identifier.",
            },
            {
                "id": "finding-3",
                "decisionStatus": "NEEDS_REVIEW",
                "pageId": "page-2",
                "pageIndex": 2,
                "lineId": "line-5",
                "category": "NAME",
            },
        ],
    }


def _candidate_snapshot_payload() -> dict[str, object]:
    return {
        "id": "candidate-1",
        "sourcePhase": "PHASE6",
        "sourceArtifactKind": "REDACTION_RUN_OUTPUT",
        "sourceArtifactId": "redaction-run-output-1",
        "candidateSha256": "f" * 64,
        "governanceRunId": "run-1",
        "governanceManifestId": "manifest-1",
        "governanceLedgerId": "ledger-1",
        "governanceManifestSha256": "a" * 64,
        "governanceLedgerSha256": "b" * 64,
        "policySnapshotHash": "policy-hash-1",
        "policyId": "policy-main",
        "policyFamilyId": "policy-family-main",
        "policyVersion": "v1",
    }


def _manifest_record(
    *,
    manifest_id: str,
    attempt_number: int,
    snapshot_sha: str,
    created_at: datetime,
) -> RedactionManifestRecord:
    return RedactionManifestRecord(
        id=manifest_id,
        run_id="run-1",
        project_id="project-1",
        document_id="doc-1",
        source_review_snapshot_key=f"controlled/approved/{snapshot_sha}.json",
        source_review_snapshot_sha256=snapshot_sha,
        attempt_number=attempt_number,
        supersedes_manifest_id=None,
        superseded_by_manifest_id=None,
        status="SUCCEEDED",
        manifest_key=f"controlled/derived/manifest/{manifest_id}.json",
        manifest_sha256=("1" * 64) if attempt_number == 1 else ("2" * 64),
        format_version=1,
        started_at=created_at - timedelta(minutes=2),
        finished_at=created_at - timedelta(minutes=1),
        canceled_by=None,
        canceled_at=None,
        failure_reason=None,
        created_by="reviewer-1",
        created_at=created_at,
    )


def _ledger_record(
    *,
    ledger_id: str,
    attempt_number: int,
    snapshot_sha: str,
    ledger_sha256: str,
    created_at: datetime,
) -> RedactionEvidenceLedgerRecord:
    return RedactionEvidenceLedgerRecord(
        id=ledger_id,
        run_id="run-1",
        project_id="project-1",
        document_id="doc-1",
        source_review_snapshot_key=f"controlled/approved/{snapshot_sha}.json",
        source_review_snapshot_sha256=snapshot_sha,
        attempt_number=attempt_number,
        supersedes_ledger_id=None,
        superseded_by_ledger_id=None,
        status="SUCCEEDED",
        ledger_key=f"controlled/derived/ledger/{ledger_id}.json",
        ledger_sha256=ledger_sha256,
        hash_chain_version="v1",
        started_at=created_at - timedelta(minutes=2),
        finished_at=created_at - timedelta(minutes=1),
        canceled_by=None,
        canceled_at=None,
        failure_reason=None,
        created_by="reviewer-1",
        created_at=created_at,
    )


def _verification_record(
    *,
    verification_id: str,
    attempt_number: int,
    verification_result: str,
    ledger_sha256: str,
    created_at: datetime,
) -> LedgerVerificationRunRecord:
    return LedgerVerificationRunRecord(
        id=verification_id,
        run_id="run-1",
        attempt_number=attempt_number,
        supersedes_verification_run_id=None,
        superseded_by_verification_run_id=None,
        status="SUCCEEDED",
        verification_result=verification_result,  # type: ignore[arg-type]
        result_json={
            "isValid": verification_result == "VALID",
            "detail": verification_result,
            "ledgerSha256": ledger_sha256,
        },
        started_at=created_at - timedelta(minutes=1),
        finished_at=created_at,
        canceled_by=None,
        canceled_at=None,
        failure_reason=None,
        created_by="admin-1",
        created_at=created_at,
    )


def test_governance_integrity_harness_passes_for_canonical_payloads() -> None:
    snapshot_sha = "b" * 64
    approved_snapshot = _approved_snapshot_payload()
    page_rows = (("page-1", "preview-sha-1"), ("page-2", "preview-sha-2"))
    manifest_payload = canonical_preview_manifest_payload(
        run_id="run-1",
        page_rows=page_rows,
        approved_snapshot_sha256=snapshot_sha,
        approved_snapshot_payload=approved_snapshot,
    )
    manifest_bytes = canonical_preview_manifest_bytes(
        run_id="run-1",
        page_rows=page_rows,
        approved_snapshot_sha256=snapshot_sha,
        approved_snapshot_payload=approved_snapshot,
    )
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    ledger_payload = canonical_evidence_ledger_payload(
        run_id="run-1",
        approved_snapshot_sha256=snapshot_sha,
        approved_snapshot_payload=approved_snapshot,
    )
    candidate = _candidate_snapshot_payload()

    evaluation = build_governance_integrity_evaluation(
        reports=(
            validate_manifest_hash(
                manifest_bytes=manifest_bytes,
                expected_sha256=manifest_sha,
            ),
            reconcile_manifest_payload(
                manifest_payload=manifest_payload,
                approved_snapshot_payload=approved_snapshot,
            ),
            reconcile_ledger_payload(
                ledger_payload=ledger_payload,
                run_id="run-1",
                approved_snapshot_sha256=snapshot_sha,
                approved_snapshot_payload=approved_snapshot,
            ),
            validate_candidate_snapshot_handoff(snapshot=candidate),
            validate_provenance_handoff(snapshot=candidate),
        ),
    )
    write_governance_integrity_artifact(
        evaluation=evaluation,
        path=EVALUATION_ARTIFACT_PATH,
    )

    assert evaluation.passed, evaluation.format_failure_summary()


def test_governance_integrity_harness_detects_manifest_and_ledger_tamper() -> None:
    snapshot_sha = "b" * 64
    approved_snapshot = _approved_snapshot_payload()
    page_rows = (("page-1", "preview-sha-1"), ("page-2", "preview-sha-2"))
    manifest_payload = canonical_preview_manifest_payload(
        run_id="run-1",
        page_rows=page_rows,
        approved_snapshot_sha256=snapshot_sha,
        approved_snapshot_payload=approved_snapshot,
    )
    manifest_bytes = canonical_preview_manifest_bytes(
        run_id="run-1",
        page_rows=page_rows,
        approved_snapshot_sha256=snapshot_sha,
        approved_snapshot_payload=approved_snapshot,
    )
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    mutated_manifest = json.loads(manifest_bytes.decode("utf-8"))
    mutated_manifest["entries"][0]["pageIndex"] = 9
    mutated_manifest_bytes = json.dumps(
        mutated_manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    ledger_payload = canonical_evidence_ledger_payload(
        run_id="run-1",
        approved_snapshot_sha256=snapshot_sha,
        approved_snapshot_payload=approved_snapshot,
    )
    ledger_payload["rows"][0]["category"] = "NAME"  # type: ignore[index]

    manifest_hash_report = validate_manifest_hash(
        manifest_bytes=mutated_manifest_bytes,
        expected_sha256=manifest_sha,
    )
    manifest_reconcile_report = reconcile_manifest_payload(
        manifest_payload=mutated_manifest,
        approved_snapshot_payload=approved_snapshot,
    )
    ledger_reconcile_report = reconcile_ledger_payload(
        ledger_payload=ledger_payload,
        run_id="run-1",
        approved_snapshot_sha256=snapshot_sha,
        approved_snapshot_payload=approved_snapshot,
    )
    assert not manifest_hash_report.passed
    assert any(issue.code == "MANIFEST_HASH_MISMATCH" for issue in manifest_hash_report.issues)
    assert not manifest_reconcile_report.passed
    assert any(
        issue.code == "MANIFEST_PAGE_INDEX_MISMATCH"
        for issue in manifest_reconcile_report.issues
    )
    assert not ledger_reconcile_report.passed
    assert any(
        issue.code.startswith("LEDGER_CHAIN_")
        for issue in ledger_reconcile_report.issues
    )

    # Sanity check: unmutated payloads reconcile.
    assert reconcile_manifest_payload(
        manifest_payload=manifest_payload,
        approved_snapshot_payload=approved_snapshot,
    ).passed


def test_ready_pair_preserves_existing_until_replacement_verifies_valid() -> None:
    now = datetime.now(UTC)
    manifest_old = _manifest_record(
        manifest_id="manifest-old",
        attempt_number=1,
        snapshot_sha="snap-old",
        created_at=now - timedelta(minutes=10),
    )
    manifest_new = _manifest_record(
        manifest_id="manifest-new",
        attempt_number=2,
        snapshot_sha="snap-new",
        created_at=now - timedelta(minutes=2),
    )
    ledger_old = _ledger_record(
        ledger_id="ledger-old",
        attempt_number=1,
        snapshot_sha="snap-old",
        ledger_sha256="old-ledger-sha",
        created_at=now - timedelta(minutes=9),
    )
    ledger_new = _ledger_record(
        ledger_id="ledger-new",
        attempt_number=2,
        snapshot_sha="snap-new",
        ledger_sha256="new-ledger-sha",
        created_at=now - timedelta(minutes=1),
    )
    verification_old_valid = _verification_record(
        verification_id="verify-old",
        attempt_number=1,
        verification_result="VALID",
        ledger_sha256="old-ledger-sha",
        created_at=now - timedelta(minutes=8),
    )

    resolution = resolve_governance_ready_pair_from_attempts(
        manifests=(manifest_old, manifest_new),
        ledgers=(ledger_old, ledger_new),
        successful_verifications=(verification_old_valid,),
        existing_ready_manifest_id="manifest-old",
        existing_ready_ledger_id="ledger-old",
    )
    assert resolution.ready_manifest is not None
    assert resolution.ready_ledger is not None
    assert resolution.ready_manifest.id == "manifest-old"
    assert resolution.ready_ledger.id == "ledger-old"
    assert resolution.ledger_verification_status == "VALID"


def test_ready_pair_promotes_only_after_replacement_verifies_valid() -> None:
    now = datetime.now(UTC)
    manifest_old = _manifest_record(
        manifest_id="manifest-old",
        attempt_number=1,
        snapshot_sha="snap-old",
        created_at=now - timedelta(minutes=20),
    )
    manifest_new = _manifest_record(
        manifest_id="manifest-new",
        attempt_number=2,
        snapshot_sha="snap-new",
        created_at=now - timedelta(minutes=6),
    )
    ledger_old = _ledger_record(
        ledger_id="ledger-old",
        attempt_number=1,
        snapshot_sha="snap-old",
        ledger_sha256="old-ledger-sha",
        created_at=now - timedelta(minutes=19),
    )
    ledger_new = _ledger_record(
        ledger_id="ledger-new",
        attempt_number=2,
        snapshot_sha="snap-new",
        ledger_sha256="new-ledger-sha",
        created_at=now - timedelta(minutes=5),
    )
    verification_old_valid = _verification_record(
        verification_id="verify-old",
        attempt_number=1,
        verification_result="VALID",
        ledger_sha256="old-ledger-sha",
        created_at=now - timedelta(minutes=18),
    )
    verification_new_valid = _verification_record(
        verification_id="verify-new",
        attempt_number=2,
        verification_result="VALID",
        ledger_sha256="new-ledger-sha",
        created_at=now - timedelta(minutes=4),
    )

    resolution = resolve_governance_ready_pair_from_attempts(
        manifests=(manifest_old, manifest_new),
        ledgers=(ledger_old, ledger_new),
        successful_verifications=(verification_old_valid, verification_new_valid),
        existing_ready_manifest_id="manifest-old",
        existing_ready_ledger_id="ledger-old",
    )
    assert resolution.ready_manifest is not None
    assert resolution.ready_ledger is not None
    assert resolution.ready_manifest.id == "manifest-new"
    assert resolution.ready_ledger.id == "ledger-new"
    assert resolution.ledger_verification_status == "VALID"


def test_ready_pair_survives_invalid_replacement_verification() -> None:
    now = datetime.now(UTC)
    manifest_old = _manifest_record(
        manifest_id="manifest-old",
        attempt_number=1,
        snapshot_sha="snap-old",
        created_at=now - timedelta(minutes=30),
    )
    manifest_new = _manifest_record(
        manifest_id="manifest-new",
        attempt_number=2,
        snapshot_sha="snap-new",
        created_at=now - timedelta(minutes=8),
    )
    ledger_old = _ledger_record(
        ledger_id="ledger-old",
        attempt_number=1,
        snapshot_sha="snap-old",
        ledger_sha256="old-ledger-sha",
        created_at=now - timedelta(minutes=29),
    )
    ledger_new = _ledger_record(
        ledger_id="ledger-new",
        attempt_number=2,
        snapshot_sha="snap-new",
        ledger_sha256="new-ledger-sha",
        created_at=now - timedelta(minutes=7),
    )
    verification_old_valid = _verification_record(
        verification_id="verify-old",
        attempt_number=1,
        verification_result="VALID",
        ledger_sha256="old-ledger-sha",
        created_at=now - timedelta(minutes=28),
    )
    verification_new_invalid = _verification_record(
        verification_id="verify-new-invalid",
        attempt_number=2,
        verification_result="INVALID",
        ledger_sha256="new-ledger-sha",
        created_at=now - timedelta(minutes=6),
    )

    resolution = resolve_governance_ready_pair_from_attempts(
        manifests=(manifest_old, manifest_new),
        ledgers=(ledger_old, ledger_new),
        successful_verifications=(verification_new_invalid, verification_old_valid),
        existing_ready_manifest_id="manifest-old",
        existing_ready_ledger_id="ledger-old",
    )
    assert resolution.ready_manifest is not None
    assert resolution.ready_ledger is not None
    assert resolution.ready_manifest.id == "manifest-old"
    assert resolution.ready_ledger.id == "ledger-old"
    assert resolution.ledger_verification_status == "VALID"


def test_candidate_and_provenance_handoff_checks_fail_for_missing_pins() -> None:
    candidate = _candidate_snapshot_payload()
    broken = dict(candidate)
    broken["sourceArtifactKind"] = "DERIVATIVE_SNAPSHOT"
    broken["governanceManifestSha256"] = None
    broken["governanceLedgerSha256"] = None
    broken["policySnapshotHash"] = None
    broken["policyId"] = None
    broken["policyFamilyId"] = None
    broken["policyVersion"] = None

    candidate_report = validate_candidate_snapshot_handoff(snapshot=broken)
    provenance_report = validate_provenance_handoff(snapshot=broken)
    assert not candidate_report.passed
    assert any(
        issue.code == "CANDIDATE_SOURCE_ARTIFACT_KIND_INVALID"
        for issue in candidate_report.issues
    )
    assert not provenance_report.passed
    assert any(
        issue.code == "PROVENANCE_HANDOFF_FIELD_MISSING"
        for issue in provenance_report.issues
    )
    assert any(
        issue.code == "PROVENANCE_POLICY_LINEAGE_MISSING"
        for issue in provenance_report.issues
    )
