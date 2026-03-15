from __future__ import annotations

import hashlib
import json
import math
from typing import Mapping, Sequence

_APPLIED_DECISION_STATES: set[str] = {"AUTO_APPLIED", "APPROVED", "OVERRIDDEN"}
_ALLOWED_ACTION_TYPES: set[str] = {"MASK", "PSEUDONYMIZE", "GENERALIZE"}
_GENESIS_HASH = "GENESIS"
_LEDGER_KIND = "CONTROLLED_REDACTION_EVIDENCE_LEDGER"


def _normalized_optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    return trimmed


def _normalized_optional_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return int(value)


def _normalized_optional_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    normalized = float(value)
    if not math.isfinite(normalized):
        return None
    return normalized


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _to_json_primitive(value: object) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        return None
    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        for key in sorted(value.keys(), key=lambda item: str(item)):
            normalized[str(key)] = _to_json_primitive(value[key])
        return normalized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_to_json_primitive(item) for item in value]
    return str(value)


def _normalized_action_type(value: object) -> str:
    action = _normalized_optional_text(value)
    if action is None:
        return "MASK"
    normalized = action.upper()
    if normalized in _ALLOWED_ACTION_TYPES:
        return normalized
    return "MASK"


def _safe_bbox_token(value: object) -> str | None:
    if not isinstance(value, Mapping):
        return None
    return hashlib.sha256(_canonical_json_bytes(_to_json_primitive(value))).hexdigest()[:16]


def _token_ref_count(value: object) -> int:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return 0
    return sum(1 for item in value if isinstance(item, Mapping))


def _extract_page_index_by_id(snapshot_payload: Mapping[str, object]) -> dict[str, int]:
    page_index_by_id: dict[str, int] = {}
    outputs_payload = snapshot_payload.get("outputs")
    if isinstance(outputs_payload, Sequence) and not isinstance(outputs_payload, (str, bytes)):
        for item in outputs_payload:
            if not isinstance(item, Mapping):
                continue
            page_id = _normalized_optional_text(item.get("pageId"))
            page_index = _normalized_optional_int(item.get("pageIndex"))
            if page_id is None or page_index is None:
                continue
            page_index_by_id[page_id] = page_index
    findings_payload = snapshot_payload.get("findings")
    if isinstance(findings_payload, Sequence) and not isinstance(findings_payload, (str, bytes)):
        for item in findings_payload:
            if not isinstance(item, Mapping):
                continue
            page_id = _normalized_optional_text(item.get("pageId"))
            page_index = _normalized_optional_int(item.get("pageIndex"))
            if page_id is None or page_index is None:
                continue
            if page_id in page_index_by_id:
                continue
            page_index_by_id[page_id] = page_index
    return page_index_by_id


def _extract_policy_lineage(snapshot_payload: Mapping[str, object]) -> dict[str, str | None]:
    run_payload = snapshot_payload.get("run")
    run = dict(run_payload) if isinstance(run_payload, Mapping) else {}
    return {
        "policySnapshotHash": _normalized_optional_text(run.get("policySnapshotHash")),
        "policyId": _normalized_optional_text(run.get("policyId")),
        "policyFamilyId": _normalized_optional_text(run.get("policyFamilyId")),
        "policyVersion": _normalized_optional_text(run.get("policyVersion")),
    }


def canonical_evidence_ledger_payload(
    *,
    run_id: str,
    approved_snapshot_sha256: str,
    approved_snapshot_payload: Mapping[str, object],
    hash_chain_version: str = "v1",
) -> dict[str, object]:
    normalized_run_id = _normalized_optional_text(run_id)
    normalized_snapshot_sha256 = _normalized_optional_text(approved_snapshot_sha256)
    if normalized_run_id is None:
        raise ValueError("run_id is required for evidence-ledger serialization.")
    if normalized_snapshot_sha256 is None:
        raise ValueError("approved_snapshot_sha256 is required for evidence-ledger serialization.")
    payload_run_id = _normalized_optional_text(approved_snapshot_payload.get("runId"))
    if payload_run_id is not None and payload_run_id != normalized_run_id:
        raise ValueError("Approved snapshot run id does not match target run id.")

    page_index_by_id = _extract_page_index_by_id(approved_snapshot_payload)
    policy_lineage = _extract_policy_lineage(approved_snapshot_payload)
    findings_payload = approved_snapshot_payload.get("findings")
    findings = (
        [item for item in findings_payload if isinstance(item, Mapping)]
        if isinstance(findings_payload, Sequence)
        and not isinstance(findings_payload, (str, bytes))
        else []
    )

    ordered_findings = sorted(
        findings,
        key=lambda item: (
            _normalized_optional_int(item.get("pageIndex"))
            or page_index_by_id.get(_normalized_optional_text(item.get("pageId")) or "", 0),
            _normalized_optional_text(item.get("pageId")) or "",
            _normalized_optional_text(item.get("lineId")) or "",
            _normalized_optional_text(item.get("decisionAt"))
            or _normalized_optional_text(item.get("updatedAt"))
            or "",
            _normalized_optional_text(item.get("id")) or "",
        ),
    )

    rows: list[dict[str, object]] = []
    previous_hash = _GENESIS_HASH
    row_index = 0
    for item in ordered_findings:
        decision_state = (_normalized_optional_text(item.get("decisionStatus")) or "").upper()
        if decision_state not in _APPLIED_DECISION_STATES:
            continue
        entry_id = _normalized_optional_text(item.get("id"))
        page_id = _normalized_optional_text(item.get("pageId"))
        category = _normalized_optional_text(item.get("category"))
        if entry_id is None or page_id is None or category is None:
            continue

        row_index += 1
        token_ref_count = _token_ref_count(item.get("tokenRefsJson"))
        before_text_ref: dict[str, object] = {
            "lineId": _normalized_optional_text(item.get("lineId")),
            "spanBasisKind": _normalized_optional_text(item.get("spanBasisKind")),
            "spanBasisRef": _normalized_optional_text(item.get("spanBasisRef")),
            "spanStart": _normalized_optional_int(item.get("spanStart")),
            "spanEnd": _normalized_optional_int(item.get("spanEnd")),
            "tokenRefCount": token_ref_count if token_ref_count > 0 else None,
            "bboxToken": _safe_bbox_token(item.get("bboxRefs")),
            "areaMaskId": _normalized_optional_text(item.get("areaMaskId")),
        }
        after_text_ref: dict[str, object] = {
            "actionType": _normalized_action_type(item.get("actionType")),
            "redactionState": "REDACTED_REFERENCE",
        }
        detector_evidence = {
            "basisPrimary": (_normalized_optional_text(item.get("basisPrimary")) or "UNKNOWN").upper(),
            "basisSecondaryJson": _to_json_primitive(item.get("basisSecondaryJson"))
            if isinstance(item.get("basisSecondaryJson"), Mapping)
            else None,
        }

        override_reason = _normalized_optional_text(item.get("decisionReason"))
        if override_reason is None:
            risk_reasons = item.get("overrideRiskReasonCodesJson")
            if isinstance(risk_reasons, Sequence) and not isinstance(risk_reasons, (str, bytes)):
                normalized_reasons = [
                    reason.strip()
                    for reason in risk_reasons
                    if isinstance(reason, str) and reason.strip()
                ]
                if normalized_reasons:
                    override_reason = ";".join(sorted(set(normalized_reasons)))

        row_without_hash = {
            "rowId": f"{entry_id}:{row_index}",
            "rowIndex": row_index,
            "findingId": entry_id,
            "pageId": page_id,
            "pageIndex": _normalized_optional_int(item.get("pageIndex"))
            or page_index_by_id.get(page_id),
            "lineId": _normalized_optional_text(item.get("lineId")),
            "category": category.upper(),
            "actionType": _normalized_action_type(item.get("actionType")),
            "beforeTextRef": before_text_ref,
            "afterTextRef": after_text_ref,
            "detectorEvidence": detector_evidence,
            "assistExplanationKey": _normalized_optional_text(item.get("assistExplanationKey")),
            "assistExplanationSha256": _normalized_optional_text(
                item.get("assistExplanationSha256")
            ),
            "actorUserId": _normalized_optional_text(item.get("decisionBy")),
            "decisionTimestamp": _normalized_optional_text(item.get("decisionAt"))
            or _normalized_optional_text(item.get("updatedAt")),
            "overrideReason": override_reason,
            "finalDecisionState": decision_state,
            "policySnapshotHash": policy_lineage.get("policySnapshotHash"),
            "policyId": policy_lineage.get("policyId"),
            "policyFamilyId": policy_lineage.get("policyFamilyId"),
            "policyVersion": policy_lineage.get("policyVersion"),
            "prevHash": previous_hash,
        }
        row_hash = hashlib.sha256(_canonical_json_bytes(row_without_hash)).hexdigest()
        row_payload = dict(row_without_hash)
        row_payload["rowHash"] = row_hash
        rows.append(row_payload)
        previous_hash = row_hash

    return {
        "ledgerSchemaVersion": 1,
        "ledgerKind": _LEDGER_KIND,
        "runId": normalized_run_id,
        "approvedSnapshotSha256": normalized_snapshot_sha256,
        "hashChainVersion": _normalized_optional_text(hash_chain_version) or "v1",
        "internalOnly": True,
        "rowCount": len(rows),
        "headHash": previous_hash,
        "rows": rows,
    }


def canonical_evidence_ledger_bytes(
    *,
    run_id: str,
    approved_snapshot_sha256: str,
    approved_snapshot_payload: Mapping[str, object],
    hash_chain_version: str = "v1",
) -> bytes:
    payload = canonical_evidence_ledger_payload(
        run_id=run_id,
        approved_snapshot_sha256=approved_snapshot_sha256,
        approved_snapshot_payload=approved_snapshot_payload,
        hash_chain_version=hash_chain_version,
    )
    return _canonical_json_bytes(payload)


def canonical_evidence_ledger_sha256(
    *,
    run_id: str,
    approved_snapshot_sha256: str,
    approved_snapshot_payload: Mapping[str, object],
    hash_chain_version: str = "v1",
) -> str:
    payload_bytes = canonical_evidence_ledger_bytes(
        run_id=run_id,
        approved_snapshot_sha256=approved_snapshot_sha256,
        approved_snapshot_payload=approved_snapshot_payload,
        hash_chain_version=hash_chain_version,
    )
    return hashlib.sha256(payload_bytes).hexdigest()


def verify_canonical_evidence_ledger_payload(
    payload: Mapping[str, object],
    *,
    expected_run_id: str | None = None,
    expected_snapshot_sha256: str | None = None,
) -> dict[str, object]:
    run_id = _normalized_optional_text(payload.get("runId"))
    snapshot_sha256 = _normalized_optional_text(payload.get("approvedSnapshotSha256"))
    rows_payload = payload.get("rows")
    rows = (
        [row for row in rows_payload if isinstance(row, Mapping)]
        if isinstance(rows_payload, Sequence) and not isinstance(rows_payload, (str, bytes))
        else []
    )
    expected_run = _normalized_optional_text(expected_run_id)
    expected_snapshot = _normalized_optional_text(expected_snapshot_sha256)

    detail = "VALID"
    first_invalid_row_index: int | None = None
    first_invalid_row_id: str | None = None
    is_valid = True

    if expected_run is not None and run_id != expected_run:
        is_valid = False
        detail = "RUN_ID_MISMATCH"
    if is_valid and expected_snapshot is not None and snapshot_sha256 != expected_snapshot:
        is_valid = False
        detail = "SNAPSHOT_SHA256_MISMATCH"

    previous_hash = _GENESIS_HASH
    checked_rows = 0
    if is_valid:
        for index, row in enumerate(rows, start=1):
            row_payload = dict(row)
            row_hash = _normalized_optional_text(row_payload.get("rowHash"))
            row_id = _normalized_optional_text(row_payload.get("rowId"))
            prev_hash = _normalized_optional_text(row_payload.get("prevHash"))
            if prev_hash != previous_hash:
                is_valid = False
                detail = "PREV_HASH_MISMATCH"
            row_payload.pop("rowHash", None)
            computed_row_hash = hashlib.sha256(_canonical_json_bytes(_to_json_primitive(row_payload))).hexdigest()
            if is_valid and row_hash != computed_row_hash:
                is_valid = False
                detail = "ROW_HASH_MISMATCH"
            if not is_valid:
                first_invalid_row_index = index
                first_invalid_row_id = row_id
                break
            checked_rows = index
            previous_hash = computed_row_hash

    head_hash = _normalized_optional_text(payload.get("headHash"))
    if is_valid and head_hash != previous_hash:
        is_valid = False
        detail = "HEAD_HASH_MISMATCH"

    result: dict[str, object] = {
        "isValid": is_valid,
        "detail": detail,
        "rowCount": len(rows),
        "checkedRows": checked_rows,
        "headHash": previous_hash,
        "firstInvalidRowIndex": first_invalid_row_index,
        "firstInvalidRowId": first_invalid_row_id,
        "runId": run_id,
        "approvedSnapshotSha256": snapshot_sha256,
    }
    return result


def extract_ledger_rows(payload: Mapping[str, object]) -> list[dict[str, object]]:
    rows_payload = payload.get("rows")
    if not isinstance(rows_payload, Sequence) or isinstance(rows_payload, (str, bytes)):
        return []
    return [dict(item) for item in rows_payload if isinstance(item, Mapping)]


__all__ = [
    "canonical_evidence_ledger_bytes",
    "canonical_evidence_ledger_payload",
    "canonical_evidence_ledger_sha256",
    "extract_ledger_rows",
    "verify_canonical_evidence_ledger_payload",
]
