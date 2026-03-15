from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping, Sequence

from app.documents.evidence_ledger import (
    canonical_evidence_ledger_payload,
    verify_canonical_evidence_ledger_payload,
)

_APPLIED_DECISION_STATES = {"AUTO_APPLIED", "APPROVED", "OVERRIDDEN"}


@dataclass(frozen=True)
class GovernanceIntegrityIssue:
    code: str
    detail: str
    item_id: str | None = None


@dataclass(frozen=True)
class GovernanceIntegrityReport:
    check_id: str
    issues: tuple[GovernanceIntegrityIssue, ...]

    @property
    def passed(self) -> bool:
        return len(self.issues) == 0


@dataclass(frozen=True)
class GovernanceIntegrityEvaluation:
    generated_at: str
    reports: tuple[GovernanceIntegrityReport, ...]

    @property
    def passed(self) -> bool:
        return all(report.passed for report in self.reports)

    def format_failure_summary(self) -> str:
        if self.passed:
            return "No governance-integrity regressions detected."
        lines = ["Governance integrity failures:"]
        for report in self.reports:
            for issue in report.issues:
                item = f" item={issue.item_id}" if issue.item_id else ""
                lines.append(
                    f"- [{report.check_id}] {issue.code}:{item} {issue.detail}".strip()
                )
        return "\n".join(lines)


def _as_mapping_list(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _normalized_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    return trimmed


def _normalized_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return int(value)


def _expected_decisions_from_snapshot(
    approved_snapshot_payload: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    expected: dict[str, dict[str, object]] = {}
    for finding in _as_mapping_list(approved_snapshot_payload.get("findings")):
        decision = (_normalized_text(finding.get("decisionStatus")) or "").upper()
        if decision not in _APPLIED_DECISION_STATES:
            continue
        finding_id = _normalized_text(finding.get("id"))
        if finding_id is None:
            continue
        expected[finding_id] = {
            "findingId": finding_id,
            "category": (_normalized_text(finding.get("category")) or "").upper(),
            "pageIndex": _normalized_int(finding.get("pageIndex")),
            "lineId": _normalized_text(finding.get("lineId")),
            "finalDecisionState": decision,
        }
    return expected


def _sha256_hex(payload_bytes: bytes) -> str:
    return hashlib.sha256(payload_bytes).hexdigest()


def validate_manifest_hash(
    *,
    manifest_bytes: bytes,
    expected_sha256: str,
) -> GovernanceIntegrityReport:
    actual = _sha256_hex(manifest_bytes)
    if actual == expected_sha256:
        return GovernanceIntegrityReport(check_id="manifest_hash", issues=())
    return GovernanceIntegrityReport(
        check_id="manifest_hash",
        issues=(
            GovernanceIntegrityIssue(
                code="MANIFEST_HASH_MISMATCH",
                detail=(
                    "Manifest stream hash does not match expected immutable hash."
                    f" expected={expected_sha256} actual={actual}"
                ),
            ),
        ),
    )


def reconcile_manifest_payload(
    *,
    manifest_payload: Mapping[str, object],
    approved_snapshot_payload: Mapping[str, object],
) -> GovernanceIntegrityReport:
    issues: list[GovernanceIntegrityIssue] = []
    expected = _expected_decisions_from_snapshot(approved_snapshot_payload)
    entries = _as_mapping_list(manifest_payload.get("entries"))

    actual_by_entry_id: dict[str, list[Mapping[str, object]]] = {}
    for entry in entries:
        entry_id = _normalized_text(entry.get("entryId"))
        if entry_id is None:
            issues.append(
                GovernanceIntegrityIssue(
                    code="MANIFEST_ENTRY_ID_MISSING",
                    detail="Manifest entry is missing entryId.",
                )
            )
            continue
        actual_by_entry_id.setdefault(entry_id, []).append(entry)

    for finding_id, expected_row in sorted(expected.items()):
        actual_rows = actual_by_entry_id.get(finding_id, [])
        if len(actual_rows) == 0:
            issues.append(
                GovernanceIntegrityIssue(
                    code="MANIFEST_ENTRY_MISSING",
                    item_id=finding_id,
                    detail="Approved decision is missing from screening-safe manifest.",
                )
            )
            continue
        if len(actual_rows) > 1:
            issues.append(
                GovernanceIntegrityIssue(
                    code="MANIFEST_ENTRY_DUPLICATE",
                    item_id=finding_id,
                    detail="Approved decision appears more than once in manifest.",
                )
            )
        actual = actual_rows[0]
        actual_category = (_normalized_text(actual.get("category")) or "").upper()
        if expected_row["category"] != actual_category:
            issues.append(
                GovernanceIntegrityIssue(
                    code="MANIFEST_CATEGORY_MISMATCH",
                    item_id=finding_id,
                    detail=(
                        "Manifest category does not match approved decision lineage."
                        f" expected={expected_row['category']} actual={actual_category}"
                    ),
                )
            )
        actual_page_index = _normalized_int(actual.get("pageIndex"))
        if expected_row["pageIndex"] != actual_page_index:
            issues.append(
                GovernanceIntegrityIssue(
                    code="MANIFEST_PAGE_INDEX_MISMATCH",
                    item_id=finding_id,
                    detail=(
                        "Manifest page index does not match approved decision."
                        f" expected={expected_row['pageIndex']} actual={actual_page_index}"
                    ),
                )
            )
        actual_line_id = _normalized_text(actual.get("lineId"))
        if expected_row["lineId"] != actual_line_id:
            issues.append(
                GovernanceIntegrityIssue(
                    code="MANIFEST_LINE_ID_MISMATCH",
                    item_id=finding_id,
                    detail=(
                        "Manifest line reference does not match approved decision."
                        f" expected={expected_row['lineId']} actual={actual_line_id}"
                    ),
                )
            )
        decision_state = (_normalized_text(actual.get("finalDecisionState")) or "").upper()
        if decision_state != expected_row["finalDecisionState"]:
            issues.append(
                GovernanceIntegrityIssue(
                    code="MANIFEST_DECISION_STATE_MISMATCH",
                    item_id=finding_id,
                    detail=(
                        "Manifest decision state does not match approved decision."
                        f" expected={expected_row['finalDecisionState']} actual={decision_state}"
                    ),
                )
            )

    for entry_id in sorted(actual_by_entry_id):
        if entry_id in expected:
            continue
        issues.append(
            GovernanceIntegrityIssue(
                code="MANIFEST_ENTRY_ORPHAN",
                item_id=entry_id,
                detail="Manifest entry cannot be reconciled to approved decision lineage.",
            )
        )

    return GovernanceIntegrityReport(
        check_id="manifest_reconciliation",
        issues=tuple(issues),
    )


def reconcile_ledger_payload(
    *,
    ledger_payload: Mapping[str, object],
    run_id: str,
    approved_snapshot_sha256: str,
    approved_snapshot_payload: Mapping[str, object],
) -> GovernanceIntegrityReport:
    issues: list[GovernanceIntegrityIssue] = []
    expected_payload = canonical_evidence_ledger_payload(
        run_id=run_id,
        approved_snapshot_sha256=approved_snapshot_sha256,
        approved_snapshot_payload=approved_snapshot_payload,
    )
    expected_rows = _as_mapping_list(expected_payload.get("rows"))
    actual_rows = _as_mapping_list(ledger_payload.get("rows"))
    expected_by_id: dict[str, Mapping[str, object]] = {}
    for row in expected_rows:
        row_id = _normalized_text(row.get("rowId"))
        if row_id is None:
            continue
        expected_by_id[row_id] = row
    actual_by_id: dict[str, Mapping[str, object]] = {}
    for row in actual_rows:
        row_id = _normalized_text(row.get("rowId"))
        if row_id is None:
            continue
        actual_by_id[row_id] = row

    for row_id in sorted(key for key in expected_by_id if key is not None):
        if row_id not in actual_by_id:
            issues.append(
                GovernanceIntegrityIssue(
                    code="LEDGER_ROW_MISSING",
                    item_id=row_id,
                    detail="Ledger row is missing for an approved decision lineage entry.",
                )
            )
            continue
        expected_row = expected_by_id[row_id]
        actual_row = actual_by_id[row_id]
        for field in (
            "findingId",
            "category",
            "actionType",
            "pageIndex",
            "lineId",
            "overrideReason",
            "actorUserId",
            "decisionTimestamp",
            "prevHash",
            "rowHash",
        ):
            if expected_row.get(field) == actual_row.get(field):
                continue
            issues.append(
                GovernanceIntegrityIssue(
                    code="LEDGER_FIELD_MISMATCH",
                    item_id=row_id,
                    detail=f"Ledger field '{field}' does not match canonical lineage expectation.",
                )
            )

    for row_id in sorted(key for key in actual_by_id if key is not None):
        if row_id in expected_by_id:
            continue
        issues.append(
            GovernanceIntegrityIssue(
                code="LEDGER_ROW_ORPHAN",
                item_id=row_id,
                detail="Ledger row cannot be reconciled to canonical approved decision lineage.",
            )
        )

    verification = verify_canonical_evidence_ledger_payload(
        ledger_payload,
        expected_run_id=run_id,
        expected_snapshot_sha256=approved_snapshot_sha256,
    )
    if not bool(verification.get("isValid")):
        issues.append(
            GovernanceIntegrityIssue(
                code=f"LEDGER_CHAIN_{verification.get('detail')}",
                item_id=(
                    str(verification.get("firstInvalidRowId"))
                    if isinstance(verification.get("firstInvalidRowId"), str)
                    else None
                ),
                detail="Ledger hash-chain verification failed for current payload bytes.",
            )
        )

    expected_row_indexes = list(range(1, len(actual_rows) + 1))
    actual_row_indexes = [
        _normalized_int(row.get("rowIndex"))
        for row in actual_rows
    ]
    if actual_row_indexes != expected_row_indexes:
        issues.append(
            GovernanceIntegrityIssue(
                code="LEDGER_ROW_INDEX_SEQUENCE_INVALID",
                detail="Ledger row indexes are not append-only contiguous sequence values.",
            )
        )

    return GovernanceIntegrityReport(
        check_id="ledger_reconciliation",
        issues=tuple(issues),
    )


def validate_candidate_snapshot_handoff(
    *,
    snapshot: Mapping[str, object],
    required_source_artifact_kind: str = "REDACTION_RUN_OUTPUT",
) -> GovernanceIntegrityReport:
    issues: list[GovernanceIntegrityIssue] = []
    source_artifact_kind = _normalized_text(snapshot.get("sourceArtifactKind"))
    source_phase = _normalized_text(snapshot.get("sourcePhase"))
    if source_phase == "PHASE6" and source_artifact_kind != required_source_artifact_kind:
        issues.append(
            GovernanceIntegrityIssue(
                code="CANDIDATE_SOURCE_ARTIFACT_KIND_INVALID",
                detail=(
                    "Phase 6 candidate snapshot must pin"
                    f" sourceArtifactKind={required_source_artifact_kind}."
                ),
            )
        )
    for field in (
        "governanceRunId",
        "governanceManifestId",
        "governanceLedgerId",
        "governanceManifestSha256",
        "governanceLedgerSha256",
    ):
        if _normalized_text(snapshot.get(field)) is not None:
            continue
        issues.append(
            GovernanceIntegrityIssue(
                code="CANDIDATE_GOVERNANCE_PIN_MISSING",
                item_id=field,
                detail="Candidate snapshot is missing required pinned governance lineage field.",
            )
        )

    return GovernanceIntegrityReport(
        check_id="candidate_snapshot_handoff",
        issues=tuple(issues),
    )


def validate_provenance_handoff(
    *,
    snapshot: Mapping[str, object],
) -> GovernanceIntegrityReport:
    issues: list[GovernanceIntegrityIssue] = []
    required_fields = (
        "sourceArtifactKind",
        "sourceArtifactId",
        "candidateSha256",
        "governanceManifestId",
        "governanceLedgerId",
        "governanceManifestSha256",
        "governanceLedgerSha256",
    )
    for field in required_fields:
        if _normalized_text(snapshot.get(field)) is not None:
            continue
        issues.append(
            GovernanceIntegrityIssue(
                code="PROVENANCE_HANDOFF_FIELD_MISSING",
                item_id=field,
                detail="Pinned candidate lineage is missing required provenance handoff field.",
            )
        )
    policy_snapshot_hash = _normalized_text(snapshot.get("policySnapshotHash"))
    policy_id = _normalized_text(snapshot.get("policyId"))
    policy_family_id = _normalized_text(snapshot.get("policyFamilyId"))
    policy_version = _normalized_text(snapshot.get("policyVersion"))
    if policy_snapshot_hash is None and not (
        policy_id is not None and policy_family_id is not None and policy_version is not None
    ):
        issues.append(
            GovernanceIntegrityIssue(
                code="PROVENANCE_POLICY_LINEAGE_MISSING",
                detail=(
                    "Pinned candidate lineage must include either policySnapshotHash or"
                    " explicit policy id/family/version fields."
                ),
            )
        )
    return GovernanceIntegrityReport(
        check_id="provenance_handoff",
        issues=tuple(issues),
    )


def build_governance_integrity_evaluation(
    reports: Sequence[GovernanceIntegrityReport],
) -> GovernanceIntegrityEvaluation:
    return GovernanceIntegrityEvaluation(
        generated_at=datetime.now(UTC).isoformat(),
        reports=tuple(reports),
    )


def write_governance_integrity_artifact(
    *,
    evaluation: GovernanceIntegrityEvaluation,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generatedAt": evaluation.generated_at,
        "passed": evaluation.passed,
        "reports": [
            {
                "checkId": report.check_id,
                "passed": report.passed,
                "issues": [
                    {
                        "code": issue.code,
                        "detail": issue.detail,
                        "itemId": issue.item_id,
                    }
                    for issue in report.issues
                ],
            }
            for report in evaluation.reports
        ],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


__all__ = [
    "GovernanceIntegrityEvaluation",
    "GovernanceIntegrityIssue",
    "GovernanceIntegrityReport",
    "build_governance_integrity_evaluation",
    "reconcile_ledger_payload",
    "reconcile_manifest_payload",
    "validate_candidate_snapshot_handoff",
    "validate_manifest_hash",
    "validate_provenance_handoff",
    "write_governance_integrity_artifact",
]
