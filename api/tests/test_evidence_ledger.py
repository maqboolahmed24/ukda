from __future__ import annotations

import json

import pytest

from app.documents.evidence_ledger import (
    canonical_evidence_ledger_bytes,
    canonical_evidence_ledger_payload,
    verify_canonical_evidence_ledger_payload,
)


def _snapshot_payload() -> dict[str, object]:
    return {
        "runId": "run-1",
        "run": {
            "policySnapshotHash": "policy-hash-1",
            "policyId": "policy-main",
            "policyFamilyId": "family-main",
            "policyVersion": "v1",
        },
        "findings": [
            {
                "id": "finding-1",
                "pageId": "page-1",
                "pageIndex": 1,
                "lineId": "line-1",
                "category": "email",
                "actionType": "MASK",
                "spanStart": 0,
                "spanEnd": 12,
                "spanBasisKind": "LINE_TEXT",
                "spanBasisRef": "line-1",
                "tokenRefsJson": [{"tokenId": "token-1"}],
                "bboxRefs": {"lineId": "line-1", "tokenBboxes": [{"x": 1, "y": 2}]},
                "basisPrimary": "NER",
                "basisSecondaryJson": {"signal": "rule-email"},
                "assistExplanationKey": "assist/key-1",
                "assistExplanationSha256": "a" * 64,
                "decisionStatus": "APPROVED",
                "decisionBy": "reviewer-1",
                "decisionAt": "2026-03-14T10:00:00+00:00",
            },
            {
                "id": "finding-2",
                "pageId": "page-1",
                "pageIndex": 1,
                "lineId": "line-2",
                "category": "phone",
                "decisionStatus": "NEEDS_REVIEW",
            },
        ],
    }


def test_canonical_evidence_ledger_is_deterministic() -> None:
    payload = _snapshot_payload()
    first = canonical_evidence_ledger_bytes(
        run_id="run-1",
        approved_snapshot_sha256="b" * 64,
        approved_snapshot_payload=payload,
    )
    second = canonical_evidence_ledger_bytes(
        run_id="run-1",
        approved_snapshot_sha256="b" * 64,
        approved_snapshot_payload=payload,
    )
    assert first == second
    decoded = json.loads(first.decode("utf-8"))
    assert decoded["rowCount"] == 1
    assert decoded["rows"][0]["findingId"] == "finding-1"
    assert decoded["rows"][0]["assistExplanationKey"] == "assist/key-1"


def test_canonical_evidence_ledger_hash_chain_verifies() -> None:
    payload = canonical_evidence_ledger_payload(
        run_id="run-1",
        approved_snapshot_sha256="b" * 64,
        approved_snapshot_payload=_snapshot_payload(),
    )
    verification = verify_canonical_evidence_ledger_payload(
        payload,
        expected_run_id="run-1",
        expected_snapshot_sha256="b" * 64,
    )
    assert verification["isValid"] is True
    assert verification["detail"] == "VALID"
    assert verification["checkedRows"] == 1


def test_canonical_evidence_ledger_detects_tamper() -> None:
    payload = canonical_evidence_ledger_payload(
        run_id="run-1",
        approved_snapshot_sha256="b" * 64,
        approved_snapshot_payload=_snapshot_payload(),
    )
    payload["rows"][0]["category"] = "NAME"  # type: ignore[index]
    verification = verify_canonical_evidence_ledger_payload(
        payload,
        expected_run_id="run-1",
        expected_snapshot_sha256="b" * 64,
    )
    assert verification["isValid"] is False
    assert verification["detail"] == "ROW_HASH_MISMATCH"
    assert verification["firstInvalidRowIndex"] == 1


def test_canonical_evidence_ledger_requires_snapshot_hash() -> None:
    with pytest.raises(ValueError):
        canonical_evidence_ledger_payload(
            run_id="run-1",
            approved_snapshot_sha256="",
            approved_snapshot_payload=_snapshot_payload(),
        )
