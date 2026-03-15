from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping, Sequence

from app.documents.redaction_preview import (
    PreviewFinding,
    PreviewLine,
    PreviewToken,
    build_safeguarded_preview_artifact,
    canonical_preview_manifest_bytes,
)

_REQUIRED_SLICE_IDS = {
    "direct_identifier",
    "near_miss",
    "unreadable_risk",
    "overlapping_span",
    "dual_review_override",
}

_RUNBOOK_LINKS = {
    "PRIVACY_FIXTURE_METADATA_INCOMPLETE": (
        "docs/runbooks/privacy-regression-triage.md#privacy_fixture_metadata_incomplete"
    ),
    "PRIVACY_FIXTURE_PUBLIC_DATA_DEPENDENCY": (
        "docs/runbooks/privacy-regression-triage.md#privacy_fixture_public_data_dependency"
    ),
    "PRIVACY_FIXTURE_SLICE_MISSING": (
        "docs/runbooks/privacy-regression-triage.md#privacy_fixture_slice_missing"
    ),
    "PRIVACY_DISCLOSURE_PREVIEW_TEXT_LEAK": (
        "docs/runbooks/privacy-regression-triage.md#privacy_disclosure_preview_text_leak"
    ),
    "PRIVACY_DISCLOSURE_PREVIEW_PNG_LEAK": (
        "docs/runbooks/privacy-regression-triage.md#privacy_disclosure_preview_png_leak"
    ),
    "PRIVACY_DISCLOSURE_MANIFEST_LEAK": (
        "docs/runbooks/privacy-regression-triage.md#privacy_disclosure_manifest_leak"
    ),
    "PRIVACY_DISCLOSURE_CASE_INVALID": (
        "docs/runbooks/privacy-regression-triage.md#privacy_disclosure_case_invalid"
    ),
    "PRIVACY_DISCLOSURE_COVERAGE_GAP": (
        "docs/runbooks/privacy-regression-triage.md#privacy_disclosure_coverage_gap"
    ),
    "PRIVACY_DUAL_REVIEW_FIXTURE_INVALID": (
        "docs/runbooks/privacy-regression-triage.md#privacy_dual_review_fixture_invalid"
    ),
}


@dataclass(frozen=True)
class PrivacyRegressionCase:
    case_id: str
    slice_id: str
    fixture_type: str
    raw_values: tuple[str, ...]
    lines: tuple[PreviewLine, ...]
    tokens: tuple[PreviewToken, ...]
    findings: tuple[PreviewFinding, ...]
    manifest_run_id: str
    manifest_page_rows: tuple[tuple[str, str], ...]
    manifest_preview_keys_by_page: Mapping[str, str] | None
    manifest_approved_snapshot_sha256: str | None
    metadata: Mapping[str, object] | None


@dataclass(frozen=True)
class PrivacyRegressionFailure:
    error_code: str
    detail: str
    case_id: str | None = None
    slice_id: str | None = None
    artifact: str | None = None


@dataclass(frozen=True)
class PrivacyRegressionCaseResult:
    case_id: str
    slice_id: str
    fixture_type: str
    token_linked: bool
    area_mask_backed: bool
    checked_raw_value_count: int
    failures: tuple[PrivacyRegressionFailure, ...]


@dataclass(frozen=True)
class PrivacyRegressionEvaluation:
    fixture_pack_id: str
    fixture_pack_version: str
    generated_at: str
    case_results: tuple[PrivacyRegressionCaseResult, ...]
    failures: tuple[PrivacyRegressionFailure, ...]

    @property
    def passed(self) -> bool:
        return len(self.failures) == 0

    def format_failure_summary(self) -> str:
        if self.passed:
            return "No privacy disclosure regressions detected."
        lines = ["Privacy regression failures:"]
        for failure in self.failures:
            case_segment = (
                f" case={failure.case_id} slice={failure.slice_id}" if failure.case_id else ""
            )
            artifact_segment = f" artifact={failure.artifact}" if failure.artifact else ""
            lines.append(
                f"- {failure.error_code}:{case_segment}{artifact_segment} {failure.detail}".strip()
            )
        return "\n".join(lines)


def _as_mapping(value: object) -> Mapping[str, object] | None:
    return value if isinstance(value, Mapping) else None


def _as_trimmed_string(value: object) -> str:
    return str(value).strip() if isinstance(value, str) else ""


def _as_line(value: object) -> PreviewLine:
    payload = _as_mapping(value)
    if payload is None:
        raise ValueError("previewFixture.lines entries must be objects.")
    line_id = _as_trimmed_string(payload.get("lineId"))
    if not line_id:
        raise ValueError("previewFixture.lines entries require lineId.")
    return PreviewLine(
        line_id=line_id,
        text=str(payload.get("text") or ""),
    )


def _as_token(value: object) -> PreviewToken:
    payload = _as_mapping(value)
    if payload is None:
        raise ValueError("previewFixture.tokens entries must be objects.")
    token_id = _as_trimmed_string(payload.get("tokenId"))
    line_id = _as_trimmed_string(payload.get("lineId"))
    if not token_id or not line_id:
        raise ValueError("previewFixture.tokens entries require tokenId and lineId.")
    token_index_raw = payload.get("tokenIndex")
    token_index = int(token_index_raw) if isinstance(token_index_raw, int) else 0
    return PreviewToken(
        token_id=token_id,
        line_id=line_id,
        token_index=token_index,
        token_text=str(payload.get("tokenText") or ""),
    )


def _as_findings(value: object) -> tuple[PreviewFinding, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("previewFixture.findings must be an array.")
    findings: list[PreviewFinding] = []
    for item in value:
        payload = _as_mapping(item)
        if payload is None:
            raise ValueError("previewFixture.findings entries must be objects.")
        finding_id = _as_trimmed_string(payload.get("findingId"))
        if not finding_id:
            raise ValueError("previewFixture.findings entries require findingId.")
        token_refs_json = payload.get("tokenRefsJson")
        parsed_token_refs: list[dict[str, object]] | None = None
        if isinstance(token_refs_json, Sequence) and not isinstance(token_refs_json, (str, bytes)):
            parsed_token_refs = [
                dict(entry)
                for entry in token_refs_json
                if isinstance(entry, Mapping)
            ]
        findings.append(
            PreviewFinding(
                finding_id=finding_id,
                decision_status=_as_trimmed_string(payload.get("decisionStatus")).upper()
                or "NEEDS_REVIEW",
                line_id=_as_trimmed_string(payload.get("lineId")) or None,
                span_start=payload.get("spanStart")
                if isinstance(payload.get("spanStart"), int)
                else None,
                span_end=payload.get("spanEnd")
                if isinstance(payload.get("spanEnd"), int)
                else None,
                token_refs_json=parsed_token_refs,
                area_mask_id=_as_trimmed_string(payload.get("areaMaskId")) or None,
            )
        )
    return tuple(findings)


def _as_manifest_page_rows(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("previewFixture.manifest.pageRows must be an array.")
    rows: list[tuple[str, str]] = []
    for entry in value:
        payload = _as_mapping(entry)
        if payload is None:
            raise ValueError("previewFixture.manifest.pageRows entries must be objects.")
        page_id = _as_trimmed_string(payload.get("pageId"))
        preview_sha256 = _as_trimmed_string(payload.get("previewSha256"))
        if not page_id or not preview_sha256:
            raise ValueError("previewFixture.manifest.pageRows requires pageId and previewSha256.")
        rows.append((page_id, preview_sha256))
    return tuple(rows)


def load_privacy_regression_fixture_pack(
    path: Path,
) -> tuple[
    str,
    str,
    Mapping[str, object],
    tuple[PrivacyRegressionCase, ...],
    tuple[str, ...],
    tuple[PrivacyRegressionFailure, ...],
]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("Privacy regression fixture pack must be a JSON object.")

    fixture_pack_id = _as_trimmed_string(raw.get("fixturePackId"))
    fixture_pack_version = _as_trimmed_string(raw.get("fixturePackVersion"))
    if not fixture_pack_id or not fixture_pack_version:
        raise ValueError("Fixture pack requires fixturePackId and fixturePackVersion.")

    failures: list[PrivacyRegressionFailure] = []
    ownership = _as_mapping(raw.get("ownership"))
    owner_team = _as_trimmed_string(ownership.get("ownerTeam")) if ownership else ""
    maintainers = ownership.get("maintainers") if ownership else None
    public_data_dependency = ownership.get("publicDataDependency") if ownership else None
    if not owner_team or not isinstance(maintainers, Sequence) or len(list(maintainers)) == 0:
        failures.append(
            PrivacyRegressionFailure(
                error_code="PRIVACY_FIXTURE_METADATA_INCOMPLETE",
                detail="Fixture pack ownership metadata must define ownerTeam and maintainers.",
            )
        )
    if public_data_dependency is not False:
        failures.append(
            PrivacyRegressionFailure(
                error_code="PRIVACY_FIXTURE_PUBLIC_DATA_DEPENDENCY",
                detail="Fixture pack must explicitly assert publicDataDependency=false.",
            )
        )

    slice_entries = raw.get("regressionSlices")
    present_slices: set[str] = set()
    if isinstance(slice_entries, Sequence) and not isinstance(slice_entries, (str, bytes)):
        for entry in slice_entries:
            payload = _as_mapping(entry)
            if payload is None:
                continue
            slice_id = _as_trimmed_string(payload.get("sliceId")).lower()
            if slice_id:
                present_slices.add(slice_id)
    missing_slices = sorted(_REQUIRED_SLICE_IDS - present_slices)
    for slice_id in missing_slices:
        failures.append(
            PrivacyRegressionFailure(
                error_code="PRIVACY_FIXTURE_SLICE_MISSING",
                slice_id=slice_id,
                detail=f"Fixture pack is missing required regression slice '{slice_id}'.",
            )
        )

    cases_raw = raw.get("cases")
    if not isinstance(cases_raw, Sequence) or isinstance(cases_raw, (str, bytes)):
        raise ValueError("Fixture pack requires a cases array.")

    parsed_cases: list[PrivacyRegressionCase] = []
    for row in cases_raw:
        payload = _as_mapping(row)
        if payload is None:
            continue
        preview_fixture = _as_mapping(payload.get("previewFixture"))
        if preview_fixture is None:
            continue
        case_id = _as_trimmed_string(payload.get("caseId"))
        slice_id = _as_trimmed_string(payload.get("sliceId")).lower()
        fixture_type = _as_trimmed_string(payload.get("fixtureType")).lower()
        if not case_id or not slice_id or not fixture_type:
            failures.append(
                PrivacyRegressionFailure(
                    error_code="PRIVACY_DISCLOSURE_CASE_INVALID",
                    case_id=case_id or None,
                    slice_id=slice_id or None,
                    detail="caseId, sliceId, and fixtureType are required for disclosure fixtures.",
                )
            )
            continue
        try:
            lines_raw = preview_fixture.get("lines")
            tokens_raw = preview_fixture.get("tokens")
            findings_raw = preview_fixture.get("findings")
            if not isinstance(lines_raw, Sequence) or isinstance(lines_raw, (str, bytes)):
                raise ValueError("previewFixture.lines must be an array.")
            if not isinstance(tokens_raw, Sequence) or isinstance(tokens_raw, (str, bytes)):
                raise ValueError("previewFixture.tokens must be an array.")
            lines = tuple(_as_line(item) for item in lines_raw)
            tokens = tuple(_as_token(item) for item in tokens_raw)
            findings = _as_findings(findings_raw)
            manifest_payload = _as_mapping(preview_fixture.get("manifest"))
            if manifest_payload is None:
                raise ValueError("previewFixture.manifest is required.")
            run_id = _as_trimmed_string(manifest_payload.get("runId"))
            if not run_id:
                raise ValueError("previewFixture.manifest.runId is required.")
            page_rows = _as_manifest_page_rows(manifest_payload.get("pageRows"))
            preview_keys = manifest_payload.get("previewKeysByPage")
            preview_keys_by_page = (
                {str(key): str(value) for key, value in dict(preview_keys).items()}
                if isinstance(preview_keys, Mapping)
                else None
            )
            approved_snapshot_sha256 = (
                _as_trimmed_string(manifest_payload.get("approvedSnapshotSha256")) or None
            )
            raw_values = tuple(
                value.strip()
                for value in payload.get("rawValues", [])
                if isinstance(value, str) and value.strip()
            )
            parsed_cases.append(
                PrivacyRegressionCase(
                    case_id=case_id,
                    slice_id=slice_id,
                    fixture_type=fixture_type,
                    raw_values=raw_values,
                    lines=lines,
                    tokens=tokens,
                    findings=findings,
                    manifest_run_id=run_id,
                    manifest_page_rows=page_rows,
                    manifest_preview_keys_by_page=preview_keys_by_page,
                    manifest_approved_snapshot_sha256=approved_snapshot_sha256,
                    metadata=_as_mapping(payload.get("metadata")),
                )
            )
        except ValueError as error:
            failures.append(
                PrivacyRegressionFailure(
                    error_code="PRIVACY_DISCLOSURE_CASE_INVALID",
                    case_id=case_id or None,
                    slice_id=slice_id or None,
                    detail=str(error),
                )
            )

    return (
        fixture_pack_id,
        fixture_pack_version,
        _as_mapping(raw.get("policySnapshot")) or {},
        tuple(parsed_cases),
        tuple(sorted(present_slices)),
        tuple(failures),
    )


def evaluate_privacy_regression_pack(path: Path) -> PrivacyRegressionEvaluation:
    (
        fixture_pack_id,
        fixture_pack_version,
        _policy_snapshot,
        cases,
        _present_slices,
        parse_failures,
    ) = load_privacy_regression_fixture_pack(path)

    failures: list[PrivacyRegressionFailure] = list(parse_failures)
    case_results: list[PrivacyRegressionCaseResult] = []

    token_linked_covered = False
    area_mask_backed_covered = False
    dual_review_fixture_valid = False

    for case in cases:
        case_failures: list[PrivacyRegressionFailure] = []
        artifact = build_safeguarded_preview_artifact(
            lines=case.lines,
            tokens=case.tokens,
            findings=case.findings,
        )
        manifest_bytes = canonical_preview_manifest_bytes(
            run_id=case.manifest_run_id,
            page_rows=case.manifest_page_rows,
            approved_snapshot_sha256=case.manifest_approved_snapshot_sha256,
            preview_keys_by_page=case.manifest_preview_keys_by_page,
        )

        case_token_linked = any(
            isinstance(finding.token_refs_json, Sequence) and len(finding.token_refs_json) > 0
            for finding in case.findings
        )
        case_area_mask_backed = any(
            finding.area_mask_id is not None
            and finding.span_start is None
            and finding.span_end is None
            and (
                finding.token_refs_json is None
                or len(finding.token_refs_json) == 0
            )
            for finding in case.findings
        )
        token_linked_covered = token_linked_covered or case_token_linked
        area_mask_backed_covered = area_mask_backed_covered or case_area_mask_backed

        if case.fixture_type == "dual_review_override":
            metadata = case.metadata or {}
            if metadata.get("dualReviewRequired") is True:
                dual_review_fixture_valid = True

        for raw_value in case.raw_values:
            raw_bytes = raw_value.encode("utf-8")
            if raw_value in artifact.text:
                case_failures.append(
                    PrivacyRegressionFailure(
                        error_code="PRIVACY_DISCLOSURE_PREVIEW_TEXT_LEAK",
                        case_id=case.case_id,
                        slice_id=case.slice_id,
                        artifact="preview_text",
                        detail=(
                            f"Raw value '{raw_value}' leaked into safeguarded preview text for "
                            f"case={case.case_id}, slice={case.slice_id}."
                        ),
                    )
                )
            if raw_bytes in artifact.png_bytes:
                case_failures.append(
                    PrivacyRegressionFailure(
                        error_code="PRIVACY_DISCLOSURE_PREVIEW_PNG_LEAK",
                        case_id=case.case_id,
                        slice_id=case.slice_id,
                        artifact="preview_png",
                        detail=(
                            f"Raw value '{raw_value}' leaked into safeguarded preview PNG for "
                            f"case={case.case_id}, slice={case.slice_id}."
                        ),
                    )
                )
            if raw_bytes in manifest_bytes:
                case_failures.append(
                    PrivacyRegressionFailure(
                        error_code="PRIVACY_DISCLOSURE_MANIFEST_LEAK",
                        case_id=case.case_id,
                        slice_id=case.slice_id,
                        artifact="run_manifest",
                        detail=(
                            f"Raw value '{raw_value}' leaked into run-level manifest for "
                            f"case={case.case_id}, slice={case.slice_id}."
                        ),
                    )
                )

        case_results.append(
            PrivacyRegressionCaseResult(
                case_id=case.case_id,
                slice_id=case.slice_id,
                fixture_type=case.fixture_type,
                token_linked=case_token_linked,
                area_mask_backed=case_area_mask_backed,
                checked_raw_value_count=len(case.raw_values),
                failures=tuple(case_failures),
            )
        )
        failures.extend(case_failures)

    if not token_linked_covered:
        failures.append(
            PrivacyRegressionFailure(
                error_code="PRIVACY_DISCLOSURE_COVERAGE_GAP",
                detail="Disclosure pack must include at least one token-linked fixture.",
            )
        )
    if not area_mask_backed_covered:
        failures.append(
            PrivacyRegressionFailure(
                error_code="PRIVACY_DISCLOSURE_COVERAGE_GAP",
                detail="Disclosure pack must include at least one area-mask-backed fixture.",
            )
        )
    if not dual_review_fixture_valid:
        failures.append(
            PrivacyRegressionFailure(
                error_code="PRIVACY_DUAL_REVIEW_FIXTURE_INVALID",
                detail=(
                    "Dual-review override coverage requires at least one dual_review_override case "
                    "with metadata.dualReviewRequired=true."
                ),
            )
        )

    return PrivacyRegressionEvaluation(
        fixture_pack_id=fixture_pack_id,
        fixture_pack_version=fixture_pack_version,
        generated_at=datetime.now(UTC).isoformat(),
        case_results=tuple(case_results),
        failures=tuple(failures),
    )


def write_privacy_regression_artifact(
    *,
    evaluation: PrivacyRegressionEvaluation,
    path: Path,
) -> None:
    artifact = {
        "fixturePackId": evaluation.fixture_pack_id,
        "fixturePackVersion": evaluation.fixture_pack_version,
        "generatedAt": evaluation.generated_at,
        "summary": {
            "passed": evaluation.passed,
            "caseCount": len(evaluation.case_results),
            "failureCount": len(evaluation.failures),
        },
        "failures": [
            {
                "errorCode": failure.error_code,
                "runbook": _RUNBOOK_LINKS.get(failure.error_code),
                "caseId": failure.case_id,
                "sliceId": failure.slice_id,
                "artifact": failure.artifact,
                "detail": failure.detail,
            }
            for failure in evaluation.failures
        ],
        "caseResults": [
            {
                "caseId": case.case_id,
                "sliceId": case.slice_id,
                "fixtureType": case.fixture_type,
                "tokenLinked": case.token_linked,
                "areaMaskBacked": case.area_mask_backed,
                "checkedRawValueCount": case.checked_raw_value_count,
                "failures": [
                    {
                        "errorCode": failure.error_code,
                        "runbook": _RUNBOOK_LINKS.get(failure.error_code),
                        "artifact": failure.artifact,
                        "detail": failure.detail,
                    }
                    for failure in case.failures
                ],
            }
            for case in evaluation.case_results
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")


__all__ = [
    "PrivacyRegressionCase",
    "PrivacyRegressionCaseResult",
    "PrivacyRegressionEvaluation",
    "PrivacyRegressionFailure",
    "evaluate_privacy_regression_pack",
    "load_privacy_regression_fixture_pack",
    "write_privacy_regression_artifact",
]
