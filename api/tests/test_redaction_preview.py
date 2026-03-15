from __future__ import annotations

import hashlib
import json

from app.documents.redaction_preview import (
    PreviewFinding,
    PreviewLine,
    PreviewMaskSpan,
    PreviewToken,
    build_safeguarded_preview_artifact,
    canonical_preview_manifest_bytes,
    canonical_preview_manifest_sha256,
    resolve_mask_spans,
)


def test_resolve_mask_spans_uses_pinned_overlap_precedence() -> None:
    spans = [
        PreviewMaskSpan(
            finding_id="finding-non-token-longer",
            line_id="line-1",
            start=0,
            end=8,
            token_linked=False,
            action_precedence_rank=3,
        ),
        PreviewMaskSpan(
            finding_id="finding-token-shorter",
            line_id="line-1",
            start=0,
            end=5,
            token_linked=True,
            action_precedence_rank=3,
        ),
        PreviewMaskSpan(
            finding_id="finding-later-overlap",
            line_id="line-1",
            start=3,
            end=6,
            token_linked=True,
            action_precedence_rank=3,
        ),
    ]
    resolved = resolve_mask_spans(spans)
    assert [item.finding_id for item in resolved] == ["finding-non-token-longer"]


def test_safeguarded_preview_masks_alnum_and_preserves_whitespace_punctuation() -> None:
    artifact = build_safeguarded_preview_artifact(
        lines=[PreviewLine(line_id="line-1", text="John,  aged 42!")],
        tokens=[],
        findings=[
            PreviewFinding(
                finding_id="finding-1",
                decision_status="APPROVED",
                line_id="line-1",
                span_start=0,
                span_end=4,
                token_refs_json=None,
                area_mask_id=None,
            )
        ],
    )
    assert "line-1: ████,  aged 42!" in artifact.text
    assert "John" not in artifact.text
    assert b"John" not in artifact.png_bytes


def test_preview_hash_changes_only_when_resolved_decisions_change() -> None:
    lines = [PreviewLine(line_id="line-1", text="Alice Example")]
    tokens = [
        PreviewToken(
            token_id="token-1",
            line_id="line-1",
            token_index=0,
            token_text="Alice",
        )
    ]
    pending_artifact = build_safeguarded_preview_artifact(
        lines=lines,
        tokens=tokens,
        findings=[
            PreviewFinding(
                finding_id="finding-1",
                decision_status="NEEDS_REVIEW",
                line_id="line-1",
                span_start=0,
                span_end=5,
                token_refs_json=[{"tokenId": "token-1", "lineId": "line-1"}],
                area_mask_id=None,
            )
        ],
    )
    false_positive_artifact = build_safeguarded_preview_artifact(
        lines=lines,
        tokens=tokens,
        findings=[
            PreviewFinding(
                finding_id="finding-1",
                decision_status="FALSE_POSITIVE",
                line_id="line-1",
                span_start=0,
                span_end=5,
                token_refs_json=[{"tokenId": "token-1", "lineId": "line-1"}],
                area_mask_id=None,
            )
        ],
    )
    approved_artifact = build_safeguarded_preview_artifact(
        lines=lines,
        tokens=tokens,
        findings=[
            PreviewFinding(
                finding_id="finding-1",
                decision_status="APPROVED",
                line_id="line-1",
                span_start=0,
                span_end=5,
                token_refs_json=[{"tokenId": "token-1", "lineId": "line-1"}],
                area_mask_id=None,
            )
        ],
    )
    assert pending_artifact.sha256 == false_positive_artifact.sha256
    assert approved_artifact.sha256 != pending_artifact.sha256


def test_area_mask_only_findings_are_marked_without_fake_token_spans() -> None:
    artifact = build_safeguarded_preview_artifact(
        lines=[PreviewLine(line_id="line-1", text="Unreadable margin note")],
        tokens=[],
        findings=[
            PreviewFinding(
                finding_id="finding-mask-only",
                decision_status="OVERRIDDEN",
                line_id=None,
                span_start=None,
                span_end=None,
                token_refs_json=None,
                area_mask_id="mask-1",
            )
        ],
    )
    assert artifact.applied_spans == ()
    assert artifact.area_mask_only_finding_ids == ("finding-mask-only",)
    assert "AREA_MASK_ONLY_FINDINGS" in artifact.text


def test_line_level_area_mask_only_findings_redact_entire_line() -> None:
    raw_value = "AB123456C"
    artifact = build_safeguarded_preview_artifact(
        lines=[PreviewLine(line_id="line-1", text=f"Folded note {raw_value} remains unreadable")],
        tokens=[],
        findings=[
            PreviewFinding(
                finding_id="finding-mask-line",
                decision_status="OVERRIDDEN",
                line_id="line-1",
                span_start=None,
                span_end=None,
                token_refs_json=None,
                area_mask_id="mask-1",
            )
        ],
    )
    assert raw_value not in artifact.text
    assert raw_value.encode("utf-8") not in artifact.png_bytes
    assert "[AREA_MASK:1]" in artifact.text


def test_canonical_preview_manifest_never_includes_raw_identifier_values() -> None:
    raw_value = "jane.doe@example.org"
    payload = canonical_preview_manifest_bytes(
        run_id="run-1",
        page_rows=(("page-1", "preview-sha-1"),),
        approved_snapshot_sha256="approved-sha-1",
        preview_keys_by_page={"page-1": "controlled/derived/project-1/doc-1/run-1/page-1.png"},
    )
    assert raw_value.encode("utf-8") not in payload


def test_canonical_preview_manifest_is_deterministic_and_entry_complete() -> None:
    snapshot_payload = {
        "runId": "run-1",
        "run": {
            "policySnapshotHash": "policy-sha-1",
            "policyId": "policy-main",
            "policyFamilyId": "family-main",
            "policyVersion": "v3",
        },
        "review": {
            "reviewStatus": "APPROVED",
            "reviewStartedBy": "reviewer-a",
            "approvedBy": "reviewer-b",
            "approvedAt": "2026-03-14T10:00:00+00:00",
            "lockedAt": "2026-03-14T10:01:00+00:00",
        },
        "pageReviews": [
            {
                "pageId": "page-1",
                "reviewStatus": "APPROVED",
                "requiresSecondReview": True,
                "secondReviewStatus": "APPROVED",
                "firstReviewedBy": "reviewer-a",
                "secondReviewedBy": "reviewer-b",
            }
        ],
        "findings": [
            {
                "id": "finding-applied",
                "pageId": "page-1",
                "pageIndex": 1,
                "lineId": "line-1",
                "category": "EMAIL",
                "actionType": "MASK",
                "spanStart": 0,
                "spanEnd": 18,
                "spanBasisKind": "LINE_TEXT",
                "spanBasisRef": "line-1",
                "tokenRefsJson": [{"tokenId": "token-1"}, {"tokenId": "token-2"}],
                "bboxRefs": {"lineId": "line-1", "tokenBboxes": [{"x": 1, "y": 2}]},
                "basisPrimary": "NER",
                "confidence": 0.98,
                "basisSecondaryJson": {
                    "corroboratingDetectors": [
                        {
                            "detectorId": "rule-1",
                            "basis": "RULE",
                            "confidence": 0.93,
                            "source": "RULE_ENGINE",
                            "rawValue": "sensitive@example.org",
                        }
                    ],
                    "assistSummary": "Reviewer-visible assist explanation text that must never leak",
                    "fusion": {"clusterSize": 2, "reviewReasons": ["cross_category_overlap:NAME"]},
                },
                "decisionStatus": "APPROVED",
                "decisionBy": "reviewer-a",
                "decisionAt": "2026-03-14T10:00:00+00:00",
                "decisionEtag": "etag-1",
            },
            {
                "id": "finding-pending",
                "pageId": "page-1",
                "pageIndex": 1,
                "lineId": "line-2",
                "category": "PHONE",
                "decisionStatus": "NEEDS_REVIEW",
                "decisionEtag": "etag-2",
            },
        ],
    }
    payload_first = canonical_preview_manifest_bytes(
        run_id="run-1",
        page_rows=(("page-1", "preview-sha-1"),),
        approved_snapshot_sha256="approved-sha-1",
        approved_snapshot_payload=snapshot_payload,
        preview_keys_by_page={"page-1": "controlled/derived/project-1/doc-1/run-1/page-1.png"},
    )
    payload_second = canonical_preview_manifest_bytes(
        run_id="run-1",
        page_rows=(("page-1", "preview-sha-1"),),
        approved_snapshot_sha256="approved-sha-1",
        approved_snapshot_payload=snapshot_payload,
    )
    payload_sha = canonical_preview_manifest_sha256(
        run_id="run-1",
        page_rows=(("page-1", "preview-sha-1"),),
        approved_snapshot_sha256="approved-sha-1",
        approved_snapshot_payload=snapshot_payload,
    )

    assert payload_first == payload_second
    assert payload_sha == hashlib.sha256(payload_first).hexdigest()
    decoded = json.loads(payload_first.decode("utf-8"))
    assert decoded["entryCount"] == 1
    assert decoded["entries"][0]["entryId"] == "finding-applied"
    assert decoded["entries"][0]["policySnapshotHash"] == "policy-sha-1"
    assert decoded["internalOnly"] is True
    assert decoded["notExportApproved"] is True
    assert "controlled/derived/project-1/doc-1/run-1/page-1.png" not in payload_first.decode("utf-8")
    assert "sensitive@example.org" not in payload_first.decode("utf-8")
    assert "Reviewer-visible assist explanation text" not in payload_first.decode("utf-8")
    assert decoded["entries"][0]["locationRef"]["bboxToken"] == hashlib.sha256(
        b'{"lineId":"line-1","tokenBboxes":[{"x":1,"y":2}]}'
    ).hexdigest()[:16]
