from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping, Sequence

from app.exports.models import (
    ExportCandidateSnapshotRecord,
    ExportReceiptRecord,
    ExportRequestEventRecord,
    ExportRequestRecord,
    ExportRequestReviewEventRecord,
    ExportRequestReviewRecord,
)

_HEX_CHARS = set("0123456789abcdef")
_TERMINAL_REQUEST_STATUSES = {"APPROVED", "EXPORTED", "REJECTED", "RETURNED"}
_OPEN_REQUEST_STATUSES = {"SUBMITTED", "RESUBMITTED", "IN_REVIEW"}
_REVIEW_TERMINAL_STATUSES = {"APPROVED", "REJECTED", "RETURNED"}
_MODEL_IMMUTABLE_REF_KEYS = (
    "checksumSha256",
    "sha256",
    "immutableVersion",
    "version",
    "modelVersion",
    "approvedModelVersion",
    "modelChecksumSha256",
)


@dataclass(frozen=True)
class ExportValidationIssue:
    code: str
    detail: str
    field: str | None = None
    expected: str | None = None
    actual: str | None = None
    blocking: bool = True

    def to_payload(self) -> dict[str, object]:
        return {
            "code": self.code,
            "detail": self.detail,
            "field": self.field,
            "expected": self.expected,
            "actual": self.actual,
            "blocking": self.blocking,
        }


@dataclass(frozen=True)
class ExportValidationReport:
    check_id: str
    issues: tuple[ExportValidationIssue, ...]
    facts: Mapping[str, object]

    @property
    def passed(self) -> bool:
        return len(self.issues) == 0

    def to_payload(self) -> dict[str, object]:
        return {
            "checkId": self.check_id,
            "passed": self.passed,
            "issueCount": len(self.issues),
            "issues": [issue.to_payload() for issue in self.issues],
            "facts": dict(self.facts),
        }


@dataclass(frozen=True)
class ExportValidationSummary:
    request_id: str
    project_id: str
    request_status: str
    request_revision: int
    generated_at: str
    release_pack: ExportValidationReport
    audit_completeness: ExportValidationReport

    @property
    def passed(self) -> bool:
        return self.release_pack.passed and self.audit_completeness.passed

    def to_payload(self) -> dict[str, object]:
        return {
            "requestId": self.request_id,
            "projectId": self.project_id,
            "requestStatus": self.request_status,
            "requestRevision": self.request_revision,
            "generatedAt": self.generated_at,
            "isValid": self.passed,
            "releasePack": self.release_pack.to_payload(),
            "auditCompleteness": self.audit_completeness.to_payload(),
        }

    def format_failure_summary(self) -> str:
        if self.passed:
            return "No export validation regressions detected."
        lines = [
            f"Export validation failures for request {self.request_id}:",
        ]
        for report in (self.release_pack, self.audit_completeness):
            for issue in report.issues:
                field_fragment = f" field={issue.field}" if issue.field else ""
                expected_fragment = (
                    f" expected={issue.expected}" if issue.expected is not None else ""
                )
                actual_fragment = f" actual={issue.actual}" if issue.actual is not None else ""
                lines.append(
                    f"- [{report.check_id}] {issue.code}:{field_fragment} {issue.detail}"
                    f"{expected_fragment}{actual_fragment}".strip()
                )
        return "\n".join(lines)


def _canonical_json_bytes(payload: Mapping[str, object]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_hex(payload_bytes: bytes) -> str:
    return hashlib.sha256(payload_bytes).hexdigest()


def _normalized_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def _safe_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return int(value)


def _is_sha256_hex(value: object) -> bool:
    normalized = _normalized_text(value)
    if normalized is None:
        return False
    lowered = normalized.lower()
    return len(lowered) == 64 and all(ch in _HEX_CHARS for ch in lowered)


def _append_issue(
    issues: list[ExportValidationIssue],
    *,
    code: str,
    detail: str,
    field: str | None = None,
    expected: object | None = None,
    actual: object | None = None,
) -> None:
    issues.append(
        ExportValidationIssue(
            code=code,
            detail=detail,
            field=field,
            expected=str(expected) if expected is not None else None,
            actual=str(actual) if actual is not None else None,
            blocking=True,
        )
    )


def _require_dict_field(
    payload: Mapping[str, object],
    *,
    field: str,
    issues: list[ExportValidationIssue],
) -> Mapping[str, object] | None:
    value = payload.get(field)
    if isinstance(value, Mapping):
        return value
    _append_issue(
        issues,
        code="RELEASE_PACK_FIELD_INVALID",
        detail="Required field must be an object.",
        field=field,
        expected="object",
        actual=type(value).__name__,
    )
    return None


def _require_list_field(
    payload: Mapping[str, object],
    *,
    field: str,
    issues: list[ExportValidationIssue],
) -> Sequence[object] | None:
    value = payload.get(field)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    _append_issue(
        issues,
        code="RELEASE_PACK_FIELD_INVALID",
        detail="Required field must be an array.",
        field=field,
        expected="array",
        actual=type(value).__name__,
    )
    return None


def _validate_release_pack_required_fields(
    *,
    payload: Mapping[str, object],
    issues: list[ExportValidationIssue],
) -> None:
    expected_string_fields = (
        "requestScope",
        "candidateSnapshotId",
        "candidateSha256",
        "candidateKind",
        "candidateSourcePhase",
        "candidateSourceArtifactKind",
        "candidateSourceArtifactId",
        "riskClassification",
        "reviewPath",
    )
    for field in expected_string_fields:
        if _normalized_text(payload.get(field)) is not None:
            continue
        _append_issue(
            issues,
            code="RELEASE_PACK_FIELD_MISSING",
            detail="Required release-pack field is missing or empty.",
            field=field,
        )

    request_revision = _safe_int(payload.get("requestRevision"))
    if request_revision is None or request_revision <= 0:
        _append_issue(
            issues,
            code="RELEASE_PACK_FIELD_INVALID",
            detail="requestRevision must be a positive integer.",
            field="requestRevision",
            expected="positive integer",
            actual=payload.get("requestRevision"),
        )
    file_count = _safe_int(payload.get("fileCount"))
    if file_count is None or file_count < 0:
        _append_issue(
            issues,
            code="RELEASE_PACK_FIELD_INVALID",
            detail="fileCount must be a non-negative integer.",
            field="fileCount",
            expected="non-negative integer",
            actual=payload.get("fileCount"),
        )
    requires_second_review = payload.get("requiresSecondReview")
    if not isinstance(requires_second_review, bool):
        _append_issue(
            issues,
            code="RELEASE_PACK_FIELD_INVALID",
            detail="requiresSecondReview must be boolean.",
            field="requiresSecondReview",
            expected="boolean",
            actual=type(requires_second_review).__name__,
        )

    _ = _require_list_field(payload, field="files", issues=issues)
    _ = _require_dict_field(payload, field="policyLineage", issues=issues)
    _ = _require_dict_field(payload, field="approvedModelReferencesByRole", issues=issues)
    _ = _require_dict_field(payload, field="redactionCountsByCategory", issues=issues)
    _ = _require_list_field(payload, field="riskFlags", issues=issues)
    _ = _require_list_field(payload, field="classifierReasonCodes", issues=issues)
    _ = _require_dict_field(payload, field="governancePins", issues=issues)
    _ = _require_list_field(payload, field="releaseReviewChecklist", issues=issues)

    override_count = _safe_int(payload.get("reviewerOverrideCount"))
    if override_count is None or override_count < 0:
        _append_issue(
            issues,
            code="RELEASE_PACK_FIELD_INVALID",
            detail="reviewerOverrideCount must be a non-negative integer.",
            field="reviewerOverrideCount",
            expected="non-negative integer",
            actual=payload.get("reviewerOverrideCount"),
        )
    area_mask_count = _safe_int(payload.get("conservativeAreaMaskCount"))
    if area_mask_count is None or area_mask_count < 0:
        _append_issue(
            issues,
            code="RELEASE_PACK_FIELD_INVALID",
            detail="conservativeAreaMaskCount must be a non-negative integer.",
            field="conservativeAreaMaskCount",
            expected="non-negative integer",
            actual=payload.get("conservativeAreaMaskCount"),
        )


def _validate_release_pack_model_lineage(
    *,
    payload: Mapping[str, object],
    issues: list[ExportValidationIssue],
) -> None:
    raw_model_map = payload.get("approvedModelReferencesByRole")
    if not isinstance(raw_model_map, Mapping):
        return
    if len(raw_model_map) == 0:
        _append_issue(
            issues,
            code="RELEASE_PACK_MODEL_LINEAGE_EMPTY",
            detail=(
                "approvedModelReferencesByRole must include at least one model role "
                "lineage pin."
            ),
            field="approvedModelReferencesByRole",
        )
        return

    for role in sorted(raw_model_map):
        role_name = _normalized_text(role)
        if role_name is None:
            _append_issue(
                issues,
                code="RELEASE_PACK_MODEL_ROLE_INVALID",
                detail="Model role name must be a non-empty string.",
                field="approvedModelReferencesByRole",
                actual=role,
            )
            continue
        entry = raw_model_map.get(role)
        if not isinstance(entry, Mapping):
            _append_issue(
                issues,
                code="RELEASE_PACK_MODEL_LINEAGE_INVALID",
                detail="Model role lineage entry must be an object.",
                field=f"approvedModelReferencesByRole.{role_name}",
                expected="object",
                actual=type(entry).__name__,
            )
            continue
        has_immutable_ref = any(
            _normalized_text(entry.get(key)) is not None for key in _MODEL_IMMUTABLE_REF_KEYS
        )
        if has_immutable_ref:
            continue
        _append_issue(
            issues,
            code="RELEASE_PACK_MODEL_LINEAGE_UNPINNED",
            detail="Model role lineage is missing immutable checksum/version references.",
            field=f"approvedModelReferencesByRole.{role_name}",
        )


def _validate_release_pack_manifest_integrity(
    *,
    payload: Mapping[str, object],
    candidate: ExportCandidateSnapshotRecord | None,
    issues: list[ExportValidationIssue],
) -> None:
    raw_integrity = payload.get("manifestIntegrity")
    if not isinstance(raw_integrity, Mapping):
        _append_issue(
            issues,
            code="RELEASE_PACK_MANIFEST_INTEGRITY_MISSING",
            detail="manifestIntegrity must be present for deterministic manifest pin verification.",
            field="manifestIntegrity",
        )
        return

    expected_manifest_sha = (
        _sha256_hex(_canonical_json_bytes(candidate.artefact_manifest_json))
        if candidate is not None
        else None
    )
    manifest_sha = _normalized_text(raw_integrity.get("artefactManifestSha256"))
    if manifest_sha is None:
        _append_issue(
            issues,
            code="RELEASE_PACK_MANIFEST_SHA_MISSING",
            detail="manifestIntegrity.artefactManifestSha256 is required.",
            field="manifestIntegrity.artefactManifestSha256",
        )
    elif expected_manifest_sha is not None and manifest_sha != expected_manifest_sha:
        _append_issue(
            issues,
            code="RELEASE_PACK_MANIFEST_SHA_MISMATCH",
            detail="Release pack manifest hash does not match pinned candidate manifest bytes.",
            field="manifestIntegrity.artefactManifestSha256",
            expected=expected_manifest_sha,
            actual=manifest_sha,
        )

    status = _normalized_text(raw_integrity.get("status"))
    if status != "MATCHED_CANDIDATE_SNAPSHOT":
        _append_issue(
            issues,
            code="RELEASE_PACK_MANIFEST_STATUS_INVALID",
            detail="Manifest integrity status must confirm candidate snapshot pin match.",
            field="manifestIntegrity.status",
            expected="MATCHED_CANDIDATE_SNAPSHOT",
            actual=status,
        )


def validate_release_pack(
    *,
    request: ExportRequestRecord,
    candidate: ExportCandidateSnapshotRecord | None,
    expected_release_pack: Mapping[str, object] | None,
    expected_release_pack_sha256: str | None,
    expected_release_pack_key: str | None,
) -> ExportValidationReport:
    issues: list[ExportValidationIssue] = []
    payload = request.release_pack_json
    canonical_payload_sha = _sha256_hex(_canonical_json_bytes(payload))
    expected_key_from_stored_sha = (
        f"exports/requests/{request.id}/release-pack/{request.release_pack_sha256}.json"
    )
    facts: dict[str, object] = {
        "computedPayloadSha256": canonical_payload_sha,
        "storedPayloadSha256": request.release_pack_sha256,
        "storedPayloadKey": request.release_pack_key,
        "expectedKeyFromStoredSha256": expected_key_from_stored_sha,
    }
    if expected_release_pack_sha256 is not None:
        facts["expectedPayloadSha256"] = expected_release_pack_sha256
    if expected_release_pack_key is not None:
        facts["expectedPayloadKey"] = expected_release_pack_key
    facts["hasPinnedCandidateSnapshot"] = candidate is not None

    if canonical_payload_sha != request.release_pack_sha256:
        _append_issue(
            issues,
            code="RELEASE_PACK_SHA_MISMATCH",
            detail="release_pack_sha256 does not match canonical bytes of release_pack_json.",
            field="releasePackSha256",
            expected=canonical_payload_sha,
            actual=request.release_pack_sha256,
        )
    if request.release_pack_key != expected_key_from_stored_sha:
        _append_issue(
            issues,
            code="RELEASE_PACK_KEY_MISMATCH",
            detail="release_pack_key must be derived from request id and release-pack sha256.",
            field="releasePackKey",
            expected=expected_key_from_stored_sha,
            actual=request.release_pack_key,
        )
    if candidate is None:
        _append_issue(
            issues,
            code="RELEASE_PACK_CANDIDATE_SNAPSHOT_MISSING",
            detail=(
                "Pinned candidate snapshot for request cannot be loaded for release-pack "
                "lineage verification."
            ),
            field="candidateSnapshotId",
            actual=request.candidate_snapshot_id,
        )

    _validate_release_pack_required_fields(payload=payload, issues=issues)
    _validate_release_pack_model_lineage(payload=payload, issues=issues)
    _validate_release_pack_manifest_integrity(
        payload=payload,
        candidate=candidate,
        issues=issues,
    )

    if _normalized_text(payload.get("requestScope")) != "REQUEST_FROZEN":
        _append_issue(
            issues,
            code="RELEASE_PACK_SCOPE_INVALID",
            detail="Frozen request release packs must use requestScope=REQUEST_FROZEN.",
            field="requestScope",
            expected="REQUEST_FROZEN",
            actual=payload.get("requestScope"),
        )

    lineage_field_checks: tuple[tuple[str, object], ...] = (
        ("candidateSnapshotId", request.candidate_snapshot_id),
        ("requestRevision", request.request_revision),
        ("riskClassification", request.risk_classification),
        ("reviewPath", request.review_path),
        ("requiresSecondReview", request.requires_second_review),
    )
    for field, expected in lineage_field_checks:
        if payload.get(field) == expected:
            continue
        _append_issue(
            issues,
            code="RELEASE_PACK_REQUEST_LINEAGE_MISMATCH",
            detail="Frozen release-pack field does not match pinned export-request lineage.",
            field=field,
            expected=expected,
            actual=payload.get(field),
        )
    actual_reason_codes = payload.get("classifierReasonCodes")
    expected_reason_codes = list(request.risk_reason_codes_json)
    if actual_reason_codes != expected_reason_codes:
        _append_issue(
            issues,
            code="RELEASE_PACK_RISK_REASON_CODES_MISMATCH",
            detail=(
                "classifierReasonCodes must match pinned request "
                "risk_reason_codes_json ordering."
            ),
            field="classifierReasonCodes",
            expected=expected_reason_codes,
            actual=actual_reason_codes,
        )

    if candidate is not None:
        candidate_lineage_checks: tuple[tuple[str, object], ...] = (
            ("candidateSha256", candidate.candidate_sha256),
            ("candidateKind", candidate.candidate_kind),
            ("candidateSourcePhase", candidate.source_phase),
            ("candidateSourceArtifactKind", candidate.source_artifact_kind),
            ("candidateSourceArtifactId", candidate.source_artifact_id),
            ("candidateSourceRunId", candidate.source_run_id),
        )
        for field, expected in candidate_lineage_checks:
            if payload.get(field) == expected:
                continue
            _append_issue(
                issues,
                code="RELEASE_PACK_CANDIDATE_LINEAGE_MISMATCH",
                detail=(
                    "Frozen release-pack field does not match pinned candidate snapshot "
                    "lineage."
                ),
                field=field,
                expected=expected,
                actual=payload.get(field),
            )

        policy_lineage = payload.get("policyLineage")
        if isinstance(policy_lineage, Mapping):
            policy_checks: tuple[tuple[str, object], ...] = (
                ("policySnapshotHash", candidate.policy_snapshot_hash),
                ("policyId", candidate.policy_id),
                ("policyFamilyId", candidate.policy_family_id),
                ("policyVersion", candidate.policy_version),
            )
            for field, expected in policy_checks:
                if policy_lineage.get(field) == expected:
                    continue
                _append_issue(
                    issues,
                    code="RELEASE_PACK_POLICY_LINEAGE_MISMATCH",
                    detail="policyLineage entry does not match pinned candidate policy lineage.",
                    field=f"policyLineage.{field}",
                    expected=expected,
                    actual=policy_lineage.get(field),
                )

        governance_pins = payload.get("governancePins")
        if isinstance(governance_pins, Mapping):
            governance_checks: tuple[tuple[str, object], ...] = (
                ("governanceRunId", candidate.governance_run_id),
                ("governanceManifestId", candidate.governance_manifest_id),
                ("governanceLedgerId", candidate.governance_ledger_id),
                ("governanceManifestSha256", candidate.governance_manifest_sha256),
                ("governanceLedgerSha256", candidate.governance_ledger_sha256),
            )
            for field, expected in governance_checks:
                if governance_pins.get(field) == expected:
                    continue
                _append_issue(
                    issues,
                    code="RELEASE_PACK_GOVERNANCE_PIN_MISMATCH",
                    detail=(
                        "governancePins entry does not match pinned candidate governance "
                        "lineage."
                    ),
                    field=f"governancePins.{field}",
                    expected=expected,
                    actual=governance_pins.get(field),
                )

    if (
        expected_release_pack_sha256 is not None
        and request.release_pack_sha256 != expected_release_pack_sha256
    ):
        _append_issue(
            issues,
            code="RELEASE_PACK_DRIFT_SHA_MISMATCH",
            detail=(
                "Frozen release-pack sha no longer matches deterministic reconstruction "
                "over pinned request and candidate lineage."
            ),
            field="releasePackSha256",
            expected=expected_release_pack_sha256,
            actual=request.release_pack_sha256,
        )
    if (
        expected_release_pack_key is not None
        and request.release_pack_key != expected_release_pack_key
    ):
        _append_issue(
            issues,
            code="RELEASE_PACK_DRIFT_KEY_MISMATCH",
            detail=(
                "Frozen release-pack key no longer matches deterministic reconstruction "
                "over pinned request and candidate lineage."
            ),
            field="releasePackKey",
            expected=expected_release_pack_key,
            actual=request.release_pack_key,
        )
    if expected_release_pack is not None:
        expected_canonical_sha = _sha256_hex(_canonical_json_bytes(expected_release_pack))
        if expected_canonical_sha != canonical_payload_sha:
            _append_issue(
                issues,
                code="RELEASE_PACK_DRIFT_PAYLOAD_MISMATCH",
                detail=(
                    "Frozen release-pack payload has drifted from expected deterministic "
                    "payload."
                ),
                field="releasePackJson",
                expected=expected_canonical_sha,
                actual=canonical_payload_sha,
            )

    return ExportValidationReport(
        check_id="release_pack",
        issues=tuple(issues),
        facts=facts,
    )


def _validate_request_event_stream(
    *,
    request: ExportRequestRecord,
    request_events: Sequence[ExportRequestEventRecord],
    issues: list[ExportValidationIssue],
) -> str:
    if len(request_events) == 0:
        _append_issue(
            issues,
            code="AUDIT_REQUEST_EVENT_STREAM_EMPTY",
            detail="export_request_events must include at least one submission/resubmission event.",
            field="exportRequestEvents",
        )
        return request.status

    expected_first_event = (
        "REQUEST_RESUBMITTED"
        if request.request_revision > 1 or request.supersedes_export_request_id is not None
        else "REQUEST_SUBMITTED"
    )
    first = request_events[0]
    expected_first_status = (
        "RESUBMITTED" if expected_first_event == "REQUEST_RESUBMITTED" else "SUBMITTED"
    )
    if first.event_type != expected_first_event:
        _append_issue(
            issues,
            code="AUDIT_REQUEST_FIRST_EVENT_INVALID",
            detail="First request event must match submission lineage.",
            field="exportRequestEvents[0].eventType",
            expected=expected_first_event,
            actual=first.event_type,
        )
    if first.from_status is not None:
        _append_issue(
            issues,
            code="AUDIT_REQUEST_FIRST_FROM_STATUS_INVALID",
            detail="First request event must have from_status=NULL.",
            field="exportRequestEvents[0].fromStatus",
            expected="None",
            actual=first.from_status,
        )
    if first.to_status != expected_first_status:
        _append_issue(
            issues,
            code="AUDIT_REQUEST_FIRST_TO_STATUS_INVALID",
            detail="First request event to_status must match submission lineage.",
            field="exportRequestEvents[0].toStatus",
            expected=expected_first_status,
            actual=first.to_status,
        )

    event_rules: dict[str, tuple[set[str], str]] = {
        "REQUEST_REVIEW_STARTED": ({"SUBMITTED", "RESUBMITTED", "IN_REVIEW"}, "IN_REVIEW"),
        "REQUEST_APPROVED": ({"IN_REVIEW"}, "APPROVED"),
        "REQUEST_REJECTED": ({"IN_REVIEW"}, "REJECTED"),
        "REQUEST_RETURNED": ({"IN_REVIEW"}, "RETURNED"),
        "REQUEST_EXPORTED": ({"APPROVED", "EXPORTED"}, "EXPORTED"),
    }
    preserving_rules: dict[str, set[str]] = {
        "REQUEST_RECEIPT_ATTACHED": {"APPROVED", "EXPORTED"},
        "REQUEST_REMINDER_SENT": _OPEN_REQUEST_STATUSES,
        "REQUEST_ESCALATED": _OPEN_REQUEST_STATUSES,
    }

    derived_status = first.to_status
    previous_timestamp = first.created_at
    for index, event in enumerate(request_events[1:], start=1):
        if event.created_at < previous_timestamp:
            _append_issue(
                issues,
                code="AUDIT_REQUEST_EVENT_ORDER_INVALID",
                detail="Request events must be append-only chronological.",
                field=f"exportRequestEvents[{index}].createdAt",
            )
        previous_timestamp = event.created_at

        if event.event_type in preserving_rules:
            allowed_statuses = preserving_rules[event.event_type]
            if derived_status not in allowed_statuses:
                _append_issue(
                    issues,
                    code="AUDIT_REQUEST_EVENT_CONTRADICTION",
                    detail="Status-preserving request event is not allowed in current status.",
                    field=f"exportRequestEvents[{index}].eventType",
                    expected=sorted(allowed_statuses),
                    actual=derived_status,
                )
            if event.from_status != derived_status or event.to_status != derived_status:
                _append_issue(
                    issues,
                    code="AUDIT_REQUEST_STATUS_PRESERVING_MISMATCH",
                    detail=(
                        "Status-preserving request event from/to statuses must match "
                        "current projection."
                    ),
                    field=f"exportRequestEvents[{index}]",
                    expected=derived_status,
                    actual=f"from={event.from_status},to={event.to_status}",
                )
            continue

        rule = event_rules.get(event.event_type)
        if rule is None:
            _append_issue(
                issues,
                code="AUDIT_REQUEST_EVENT_TYPE_UNEXPECTED",
                detail="Unexpected request event type in append-only stream.",
                field=f"exportRequestEvents[{index}].eventType",
                actual=event.event_type,
            )
            continue
        allowed_from, expected_to = rule
        if event.from_status not in allowed_from:
            _append_issue(
                issues,
                code="AUDIT_REQUEST_EVENT_FROM_STATUS_INVALID",
                detail="Request event from_status is not valid for event type.",
                field=f"exportRequestEvents[{index}].fromStatus",
                expected=sorted(allowed_from),
                actual=event.from_status,
            )
        if event.from_status != derived_status:
            _append_issue(
                issues,
                code="AUDIT_REQUEST_EVENT_CHAIN_BREAK",
                detail=(
                    "Request event from_status does not match derived status from prior "
                    "append-only events."
                ),
                field=f"exportRequestEvents[{index}].fromStatus",
                expected=derived_status,
                actual=event.from_status,
            )
        if event.to_status != expected_to:
            _append_issue(
                issues,
                code="AUDIT_REQUEST_EVENT_TO_STATUS_INVALID",
                detail="Request event to_status does not match expected transition target.",
                field=f"exportRequestEvents[{index}].toStatus",
                expected=expected_to,
                actual=event.to_status,
            )
        derived_status = event.to_status

    if derived_status != request.status:
        _append_issue(
            issues,
            code="AUDIT_REQUEST_PROJECTION_STATUS_MISMATCH",
            detail="Request projection status does not reconcile with append-only request events.",
            field="exportRequest.status",
            expected=derived_status,
            actual=request.status,
        )
    return derived_status


def _validate_review_streams(
    *,
    request: ExportRequestRecord,
    reviews: Sequence[ExportRequestReviewRecord],
    review_events: Sequence[ExportRequestReviewEventRecord],
    issues: list[ExportValidationIssue],
) -> None:
    if len(reviews) == 0:
        _append_issue(
            issues,
            code="AUDIT_REVIEW_STREAM_EMPTY",
            detail="export_request_reviews must include at least one stage projection row.",
            field="exportRequestReviews",
        )
        return

    required_reviews = [review for review in reviews if review.is_required]
    primary_required = [
        review for review in required_reviews if review.review_stage == "PRIMARY"
    ]
    secondary_required = [
        review for review in required_reviews if review.review_stage == "SECONDARY"
    ]

    if len(primary_required) != 1:
        _append_issue(
            issues,
            code="AUDIT_REVIEW_PRIMARY_REQUIRED_INVALID",
            detail="Exactly one required PRIMARY review stage must exist.",
            field="exportRequestReviews",
            expected=1,
            actual=len(primary_required),
        )
    if request.requires_second_review and len(secondary_required) != 1:
        _append_issue(
            issues,
            code="AUDIT_REVIEW_SECONDARY_REQUIRED_MISSING",
            detail="DUAL review path requires exactly one required SECONDARY review stage.",
            field="exportRequestReviews",
            expected=1,
            actual=len(secondary_required),
        )
    if not request.requires_second_review and len(secondary_required) > 0:
        _append_issue(
            issues,
            code="AUDIT_REVIEW_SECONDARY_UNEXPECTED",
            detail="SINGLE review path must not require a SECONDARY stage.",
            field="exportRequestReviews",
            expected=0,
            actual=len(secondary_required),
        )
    if request.review_path == "DUAL" and not request.requires_second_review:
        _append_issue(
            issues,
            code="AUDIT_REVIEW_PATH_PROJECTION_CONTRADICTION",
            detail="review_path=DUAL requires requires_second_review=true.",
            field="exportRequest.reviewPath",
            expected="requiresSecondReview=true",
            actual="requiresSecondReview=false",
        )
    if request.review_path == "SINGLE" and request.requires_second_review:
        _append_issue(
            issues,
            code="AUDIT_REVIEW_PATH_PROJECTION_CONTRADICTION",
            detail="review_path=SINGLE requires requires_second_review=false.",
            field="exportRequest.reviewPath",
            expected="requiresSecondReview=false",
            actual="requiresSecondReview=true",
        )

    review_by_id: dict[str, ExportRequestReviewRecord] = {review.id: review for review in reviews}
    events_by_review: dict[str, list[ExportRequestReviewEventRecord]] = {
        review.id: [] for review in reviews
    }
    for event in review_events:
        review = review_by_id.get(event.review_id)
        if review is None:
            _append_issue(
                issues,
                code="AUDIT_REVIEW_EVENT_ORPHAN",
                detail="Review event references unknown review_id.",
                field="exportRequestReviewEvents.reviewId",
                actual=event.review_id,
            )
            continue
        if event.review_stage != review.review_stage:
            _append_issue(
                issues,
                code="AUDIT_REVIEW_EVENT_STAGE_MISMATCH",
                detail="Review event stage does not match current stage projection row.",
                field=f"exportRequestReviewEvents.{event.id}.reviewStage",
                expected=review.review_stage,
                actual=event.review_stage,
            )
        events_by_review[event.review_id].append(event)

    for review in reviews:
        events = events_by_review.get(review.id, [])
        event_types = {event.event_type for event in events}
        if "REVIEW_CREATED" not in event_types:
            _append_issue(
                issues,
                code="AUDIT_REVIEW_CREATED_EVENT_MISSING",
                detail="Each review stage projection must reconcile to a REVIEW_CREATED event.",
                field=f"exportRequestReviews.{review.id}",
            )
        if review.status == "IN_REVIEW" and "REVIEW_STARTED" not in event_types:
            _append_issue(
                issues,
                code="AUDIT_REVIEW_STARTED_EVENT_MISSING",
                detail="IN_REVIEW stage is missing REVIEW_STARTED event.",
                field=f"exportRequestReviews.{review.id}.status",
            )
        if review.status in _REVIEW_TERMINAL_STATUSES:
            expected_event = {
                "APPROVED": "REVIEW_APPROVED",
                "REJECTED": "REVIEW_REJECTED",
                "RETURNED": "REVIEW_RETURNED",
            }[review.status]
            if expected_event not in event_types:
                _append_issue(
                    issues,
                    code="AUDIT_REVIEW_TERMINAL_EVENT_MISSING",
                    detail="Terminal review stage is missing matching terminal event.",
                    field=f"exportRequestReviews.{review.id}.status",
                    expected=expected_event,
                    actual=sorted(event_types),
                )
            if review.acted_by_user_id is None or review.acted_at is None:
                _append_issue(
                    issues,
                    code="AUDIT_REVIEW_TERMINAL_ACTOR_MISSING",
                    detail="Terminal review stage must persist acted_by_user_id and acted_at.",
                    field=f"exportRequestReviews.{review.id}",
                )
        else:
            if review.acted_by_user_id is not None or review.acted_at is not None:
                _append_issue(
                    issues,
                    code="AUDIT_REVIEW_NON_TERMINAL_ACTOR_INVALID",
                    detail="Non-terminal review stages cannot have acted_by_user_id/acted_at set.",
                    field=f"exportRequestReviews.{review.id}",
                )


def _validate_receipt_lineage(
    *,
    request: ExportRequestRecord,
    request_events: Sequence[ExportRequestEventRecord],
    receipts: Sequence[ExportReceiptRecord],
    issues: list[ExportValidationIssue],
) -> None:
    receipt_by_id: dict[str, ExportReceiptRecord] = {}
    for receipt in receipts:
        if receipt.id in receipt_by_id:
            _append_issue(
                issues,
                code="AUDIT_RECEIPT_ID_DUPLICATE",
                detail="Receipt lineage ids must be unique.",
                field="exportReceipts.id",
                actual=receipt.id,
            )
        receipt_by_id[receipt.id] = receipt

    attempts = sorted(receipt.attempt_number for receipt in receipts)
    expected_attempts = list(range(1, len(receipts) + 1))
    if attempts != expected_attempts:
        _append_issue(
            issues,
            code="AUDIT_RECEIPT_ATTEMPT_SEQUENCE_INVALID",
            detail="Receipt attempt numbers must be append-only contiguous values starting at 1.",
            field="exportReceipts.attemptNumber",
            expected=expected_attempts,
            actual=attempts,
        )

    for receipt in receipts:
        if (
            receipt.supersedes_receipt_id is not None
            and receipt.supersedes_receipt_id not in receipt_by_id
        ):
            _append_issue(
                issues,
                code="AUDIT_RECEIPT_SUPERSEDES_MISSING",
                detail="Receipt supersedes_receipt_id must reference an existing receipt id.",
                field=f"exportReceipts.{receipt.id}.supersedesReceiptId",
                actual=receipt.supersedes_receipt_id,
            )
        if (
            receipt.superseded_by_receipt_id is not None
            and receipt.superseded_by_receipt_id not in receipt_by_id
        ):
            _append_issue(
                issues,
                code="AUDIT_RECEIPT_SUPERSEDED_BY_MISSING",
                detail="Receipt superseded_by_receipt_id must reference an existing receipt id.",
                field=f"exportReceipts.{receipt.id}.supersededByReceiptId",
                actual=receipt.superseded_by_receipt_id,
            )

    current_receipts = [
        receipt for receipt in receipts if receipt.superseded_by_receipt_id is None
    ]
    if len(receipts) > 0 and len(current_receipts) != 1:
        _append_issue(
            issues,
            code="AUDIT_RECEIPT_CURRENT_LINEAGE_INVALID",
            detail="Receipt lineage must have exactly one current (not superseded) row.",
            field="exportReceipts",
            expected=1,
            actual=len(current_receipts),
        )

    current_receipt = current_receipts[0] if len(current_receipts) == 1 else None
    if request.receipt_id is None and len(receipts) > 0:
        _append_issue(
            issues,
            code="AUDIT_RECEIPT_PROJECTION_MISSING",
            detail="Request projection is missing receipt_id while receipt lineage rows exist.",
            field="exportRequest.receiptId",
        )
    if request.receipt_id is not None and request.receipt_id not in receipt_by_id:
        _append_issue(
            issues,
            code="AUDIT_RECEIPT_PROJECTION_ORPHAN",
            detail="Request projection receipt_id must reference an existing receipt lineage row.",
            field="exportRequest.receiptId",
            actual=request.receipt_id,
        )
    if current_receipt is not None:
        projection_checks: tuple[tuple[str, object, object], ...] = (
            ("receiptId", request.receipt_id, current_receipt.id),
            ("receiptKey", request.receipt_key, current_receipt.receipt_key),
            ("receiptSha256", request.receipt_sha256, current_receipt.receipt_sha256),
            ("receiptCreatedBy", request.receipt_created_by, current_receipt.created_by),
            ("receiptCreatedAt", request.receipt_created_at, current_receipt.created_at),
            ("exportedAt", request.exported_at, current_receipt.exported_at),
        )
        for field, actual, expected in projection_checks:
            if actual == expected:
                continue
            _append_issue(
                issues,
                code="AUDIT_RECEIPT_PROJECTION_MISMATCH",
                detail=(
                    "Request receipt projection does not reconcile with current receipt "
                    "lineage row."
                ),
                field=f"exportRequest.{field}",
                expected=expected,
                actual=actual,
            )

    attach_reasons = {
        _normalized_text(event.reason)
        for event in request_events
        if event.event_type == "REQUEST_RECEIPT_ATTACHED"
    }
    export_reasons = {
        _normalized_text(event.reason)
        for event in request_events
        if event.event_type == "REQUEST_EXPORTED"
    }
    for receipt in receipts:
        reason = f"receipt_attempt:{receipt.attempt_number}"
        if reason not in attach_reasons:
            _append_issue(
                issues,
                code="AUDIT_RECEIPT_ATTACHED_EVENT_MISSING",
                detail="Each receipt attempt must have a REQUEST_RECEIPT_ATTACHED request event.",
                field="exportRequestEvents.reason",
                actual=reason,
            )
        if reason not in export_reasons:
            _append_issue(
                issues,
                code="AUDIT_RECEIPT_EXPORTED_EVENT_MISSING",
                detail="Each receipt attempt must have a REQUEST_EXPORTED request event.",
                field="exportRequestEvents.reason",
                actual=reason,
            )

    if request.status == "EXPORTED":
        if len(receipts) == 0:
            _append_issue(
                issues,
                code="AUDIT_EXPORTED_STATUS_RECEIPT_MISSING",
                detail="EXPORTED request status requires at least one receipt lineage row.",
                field="exportRequest.status",
            )
        if request.exported_at is None:
            _append_issue(
                issues,
                code="AUDIT_EXPORTED_STATUS_TIMESTAMP_MISSING",
                detail="EXPORTED request status requires exported_at projection timestamp.",
                field="exportRequest.exportedAt",
            )
    elif len(receipts) > 0:
        _append_issue(
            issues,
            code="AUDIT_RECEIPT_WITH_NON_EXPORTED_STATUS",
            detail="Receipt lineage rows exist but request projection status is not EXPORTED.",
            field="exportRequest.status",
            actual=request.status,
        )


def _validate_projection_fields(
    *,
    request: ExportRequestRecord,
    reviews: Sequence[ExportRequestReviewRecord],
    request_events: Sequence[ExportRequestEventRecord],
    issues: list[ExportValidationIssue],
) -> None:
    final_review = (
        next((review for review in reviews if review.id == request.final_review_id), None)
        if request.final_review_id is not None
        else None
    )
    terminal_event_types = {event.event_type for event in request_events}
    expected_terminal_event: str | None = {
        "APPROVED": "REQUEST_APPROVED",
        "EXPORTED": "REQUEST_APPROVED",
        "REJECTED": "REQUEST_REJECTED",
        "RETURNED": "REQUEST_RETURNED",
    }.get(request.status)
    if expected_terminal_event is not None and expected_terminal_event not in terminal_event_types:
        _append_issue(
            issues,
            code="AUDIT_TERMINAL_EVENT_MISSING",
            detail="Terminal request projection requires corresponding terminal request event.",
            field="exportRequest.status",
            expected=expected_terminal_event,
            actual=sorted(terminal_event_types),
        )

    if request.status in _TERMINAL_REQUEST_STATUSES:
        if request.final_review_id is None:
            _append_issue(
                issues,
                code="AUDIT_TERMINAL_FINAL_REVIEW_MISSING",
                detail="Terminal request projection must include final_review_id.",
                field="exportRequest.finalReviewId",
            )
        if request.final_decision_by is None or request.final_decision_at is None:
            _append_issue(
                issues,
                code="AUDIT_TERMINAL_FINAL_DECISION_MISSING",
                detail=(
                    "Terminal request projection must include final decision actor and "
                    "timestamp."
                ),
                field="exportRequest.finalDecisionAt",
            )
        if final_review is None and request.final_review_id is not None:
            _append_issue(
                issues,
                code="AUDIT_TERMINAL_FINAL_REVIEW_ORPHAN",
                detail="final_review_id must reference an existing review stage projection row.",
                field="exportRequest.finalReviewId",
                actual=request.final_review_id,
            )
        if final_review is not None:
            expected_final_review_status = {
                "APPROVED": "APPROVED",
                "EXPORTED": "APPROVED",
                "REJECTED": "REJECTED",
                "RETURNED": "RETURNED",
            }[request.status]
            if final_review.status != expected_final_review_status:
                _append_issue(
                    issues,
                    code="AUDIT_TERMINAL_FINAL_REVIEW_STATUS_MISMATCH",
                    detail=(
                        "Final review stage projection status must match terminal request "
                        "status lineage."
                    ),
                    field="exportRequest.finalReviewId",
                    expected=expected_final_review_status,
                    actual=final_review.status,
                )
        if request.status == "RETURNED" and _normalized_text(request.final_return_comment) is None:
            _append_issue(
                issues,
                code="AUDIT_RETURNED_COMMENT_MISSING",
                detail="RETURNED terminal request projection requires final_return_comment.",
                field="exportRequest.finalReturnComment",
            )
        if request.status == "REJECTED" and _normalized_text(request.final_decision_reason) is None:
            _append_issue(
                issues,
                code="AUDIT_REJECTED_REASON_MISSING",
                detail="REJECTED terminal request projection requires final_decision_reason.",
                field="exportRequest.finalDecisionReason",
            )
    else:
        if (
            request.final_review_id is not None
            or request.final_decision_by is not None
            or request.final_decision_at is not None
        ):
            _append_issue(
                issues,
                code="AUDIT_NON_TERMINAL_FINAL_DECISION_INVALID",
                detail="Non-terminal request projection cannot contain final-decision fields.",
                field="exportRequest.status",
                actual=request.status,
            )


def validate_audit_completeness(
    *,
    request: ExportRequestRecord,
    request_events: Sequence[ExportRequestEventRecord],
    reviews: Sequence[ExportRequestReviewRecord],
    review_events: Sequence[ExportRequestReviewEventRecord],
    receipts: Sequence[ExportReceiptRecord],
) -> ExportValidationReport:
    issues: list[ExportValidationIssue] = []
    _ = _validate_request_event_stream(
        request=request,
        request_events=request_events,
        issues=issues,
    )
    _validate_review_streams(
        request=request,
        reviews=reviews,
        review_events=review_events,
        issues=issues,
    )
    _validate_projection_fields(
        request=request,
        reviews=reviews,
        request_events=request_events,
        issues=issues,
    )
    _validate_receipt_lineage(
        request=request,
        request_events=request_events,
        receipts=receipts,
        issues=issues,
    )
    facts: dict[str, object] = {
        "requestEventCount": len(request_events),
        "reviewCount": len(reviews),
        "reviewEventCount": len(review_events),
        "receiptCount": len(receipts),
    }
    return ExportValidationReport(
        check_id="audit_completeness",
        issues=tuple(issues),
        facts=facts,
    )


def build_export_validation_summary(
    *,
    request: ExportRequestRecord,
    candidate: ExportCandidateSnapshotRecord | None,
    expected_release_pack: Mapping[str, object] | None,
    expected_release_pack_sha256: str | None,
    expected_release_pack_key: str | None,
    request_events: Sequence[ExportRequestEventRecord],
    reviews: Sequence[ExportRequestReviewRecord],
    review_events: Sequence[ExportRequestReviewEventRecord],
    receipts: Sequence[ExportReceiptRecord],
) -> ExportValidationSummary:
    release_pack_report = validate_release_pack(
        request=request,
        candidate=candidate,
        expected_release_pack=expected_release_pack,
        expected_release_pack_sha256=expected_release_pack_sha256,
        expected_release_pack_key=expected_release_pack_key,
    )
    audit_report = validate_audit_completeness(
        request=request,
        request_events=request_events,
        reviews=reviews,
        review_events=review_events,
        receipts=receipts,
    )
    return ExportValidationSummary(
        request_id=request.id,
        project_id=request.project_id,
        request_status=request.status,
        request_revision=request.request_revision,
        generated_at=datetime.now(UTC).isoformat(),
        release_pack=release_pack_report,
        audit_completeness=audit_report,
    )


def write_export_validation_artifact(
    *,
    summary: ExportValidationSummary,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary.to_payload(), indent=2) + "\n", encoding="utf-8")


__all__ = [
    "ExportValidationIssue",
    "ExportValidationReport",
    "ExportValidationSummary",
    "build_export_validation_summary",
    "validate_audit_completeness",
    "validate_release_pack",
    "write_export_validation_artifact",
]
