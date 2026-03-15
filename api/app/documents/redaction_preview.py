from __future__ import annotations

import hashlib
import io
import json
import math
from dataclasses import dataclass
from typing import Mapping, Literal, Sequence


MaskableDecisionStatus = Literal["AUTO_APPLIED", "APPROVED", "OVERRIDDEN"]


@dataclass(frozen=True)
class PreviewLine:
    line_id: str
    text: str


@dataclass(frozen=True)
class PreviewToken:
    token_id: str
    line_id: str
    token_index: int
    token_text: str


@dataclass(frozen=True)
class PreviewFinding:
    finding_id: str
    decision_status: str
    line_id: str | None
    span_start: int | None
    span_end: int | None
    token_refs_json: list[dict[str, object]] | None
    area_mask_id: str | None
    action_type: str = "MASK"
    replacement_text: str | None = None


@dataclass(frozen=True)
class PreviewMaskSpan:
    finding_id: str
    line_id: str
    start: int
    end: int
    token_linked: bool
    action_precedence_rank: int
    action_type: str = "MASK"
    replacement_text: str | None = None


@dataclass(frozen=True)
class SafeguardedPreviewArtifact:
    text: str
    sha256: str
    png_bytes: bytes
    applied_spans: tuple[PreviewMaskSpan, ...]
    area_mask_only_finding_ids: tuple[str, ...]


_MASKABLE_STATUSES: set[str] = {"AUTO_APPLIED", "APPROVED", "OVERRIDDEN"}
_APPLIED_DECISION_STATUSES: set[str] = {"AUTO_APPLIED", "APPROVED", "OVERRIDDEN"}
_ACTION_PRECEDENCE_RANK_MASK = 3
_ACTION_PRECEDENCE_RANK_PSEUDONYMIZE = 2
_ACTION_PRECEDENCE_RANK_GENERALIZE = 1
_MANIFEST_ALLOWED_ACTIONS: set[str] = {"MASK", "PSEUDONYMIZE", "GENERALIZE"}
_MAX_RENDER_LINES = 220
_MAX_RENDER_LINE_LENGTH = 260


def _is_maskable_status(value: str) -> bool:
    return value in _MASKABLE_STATUSES


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def _build_token_offsets(
    *,
    line_text: str,
    tokens: Sequence[PreviewToken],
) -> dict[str, tuple[int, int]]:
    offsets: dict[str, tuple[int, int]] = {}
    ordered = sorted(tokens, key=lambda item: (item.token_index, item.token_id))
    consumed: list[tuple[int, int]] = []
    cursor = 0
    for token in ordered:
        needle = token.token_text.strip()
        if not needle:
            continue
        start = line_text.find(needle, cursor)
        if start < 0:
            start = line_text.find(needle)
            while start >= 0 and any(
                _overlaps(start, start + len(needle), used_start, used_end)
                for used_start, used_end in consumed
            ):
                start = line_text.find(needle, start + 1)
        if start < 0:
            continue
        end = start + len(needle)
        consumed.append((start, end))
        cursor = end
        offsets[token.token_id] = (start, end)
    return offsets


def _resolve_token_span_for_finding(
    *,
    finding: PreviewFinding,
    token_offsets_by_line: dict[str, dict[str, tuple[int, int]]],
) -> tuple[str, int, int] | None:
    if not isinstance(finding.token_refs_json, Sequence):
        return None
    candidate_line_id = finding.line_id
    starts: list[int] = []
    ends: list[int] = []
    for ref in finding.token_refs_json:
        if not isinstance(ref, dict):
            continue
        token_id = str(ref.get("tokenId") or "").strip()
        if not token_id:
            continue
        if candidate_line_id is None:
            candidate_line = str(ref.get("lineId") or "").strip()
            if candidate_line:
                candidate_line_id = candidate_line
        if candidate_line_id is None:
            continue
        token_offsets = token_offsets_by_line.get(candidate_line_id)
        if token_offsets is None:
            continue
        token_span = token_offsets.get(token_id)
        if token_span is None:
            continue
        starts.append(token_span[0])
        ends.append(token_span[1])
    if candidate_line_id is None or not starts or not ends:
        return None
    return candidate_line_id, min(starts), max(ends)


def _resolve_span_for_finding(
    *,
    finding: PreviewFinding,
    line_lengths: dict[str, int],
    token_offsets_by_line: dict[str, dict[str, tuple[int, int]]],
) -> PreviewMaskSpan | None:
    if not _is_maskable_status(str(finding.decision_status or "").strip().upper()):
        return None
    action_type = _normalized_action_type(finding.action_type)
    action_precedence_rank = _resolve_action_precedence_rank(action_type)
    replacement_text = (
        str(finding.replacement_text).strip()
        if isinstance(finding.replacement_text, str) and str(finding.replacement_text).strip()
        else None
    )
    if action_type == "MASK":
        replacement_text = None
    token_span = _resolve_token_span_for_finding(
        finding=finding,
        token_offsets_by_line=token_offsets_by_line,
    )
    if token_span is not None:
        line_id, start, end = token_span
        if line_id in line_lengths and 0 <= start < end <= line_lengths[line_id]:
            return PreviewMaskSpan(
                finding_id=finding.finding_id,
                line_id=line_id,
                start=start,
                end=end,
                token_linked=True,
                action_precedence_rank=action_precedence_rank,
                action_type=action_type,
                replacement_text=replacement_text,
            )
    line_id = finding.line_id
    if line_id is None or line_id not in line_lengths:
        return None
    if not isinstance(finding.span_start, int) or not isinstance(finding.span_end, int):
        return None
    if finding.span_start < 0 or finding.span_end <= finding.span_start:
        return None
    if finding.span_end > line_lengths[line_id]:
        return None
    return PreviewMaskSpan(
        finding_id=finding.finding_id,
        line_id=line_id,
        start=int(finding.span_start),
        end=int(finding.span_end),
        token_linked=False,
        action_precedence_rank=action_precedence_rank,
        action_type=action_type,
        replacement_text=replacement_text,
    )


def resolve_mask_spans(
    spans: Sequence[PreviewMaskSpan],
) -> tuple[PreviewMaskSpan, ...]:
    by_line: dict[str, list[PreviewMaskSpan]] = {}
    for span in spans:
        by_line.setdefault(span.line_id, []).append(span)
    resolved: list[PreviewMaskSpan] = []
    for line_id in sorted(by_line.keys()):
        ordered = sorted(
            by_line[line_id],
            key=lambda item: (
                item.start,
                -(item.end - item.start),
                0 if item.token_linked else 1,
                -item.action_precedence_rank,
                item.finding_id,
            ),
        )
        accepted: list[PreviewMaskSpan] = []
        for candidate in ordered:
            if any(
                _overlaps(candidate.start, candidate.end, item.start, item.end)
                for item in accepted
            ):
                continue
            accepted.append(candidate)
        accepted.sort(key=lambda item: (item.start, item.end, item.finding_id))
        resolved.extend(accepted)
    return tuple(resolved)


def _mask_char(character: str) -> str:
    if character.isspace():
        return character
    if character.isalnum():
        return "█"
    return character


def _resolve_action_precedence_rank(action_type: str) -> int:
    if action_type == "MASK":
        return _ACTION_PRECEDENCE_RANK_MASK
    if action_type == "PSEUDONYMIZE":
        return _ACTION_PRECEDENCE_RANK_PSEUDONYMIZE
    if action_type == "GENERALIZE":
        return _ACTION_PRECEDENCE_RANK_GENERALIZE
    return _ACTION_PRECEDENCE_RANK_MASK


def _render_span_text(
    *,
    line_text: str,
    span: PreviewMaskSpan,
) -> str:
    source_text = line_text[span.start : span.end]
    if (
        span.action_type in {"PSEUDONYMIZE", "GENERALIZE"}
        and isinstance(span.replacement_text, str)
        and span.replacement_text.strip()
    ):
        return span.replacement_text.strip()
    return "".join(_mask_char(character) for character in source_text)


def _apply_line_spans(
    *,
    line_text: str,
    spans: Sequence[PreviewMaskSpan],
) -> str:
    if not line_text:
        return line_text
    if not spans:
        return line_text
    output_parts: list[str] = []
    cursor = 0
    for span in sorted(spans, key=lambda item: (item.start, item.end, item.finding_id)):
        if span.start < cursor:
            continue
        output_parts.append(line_text[cursor : span.start])
        output_parts.append(
            _render_span_text(
                line_text=line_text,
                span=span,
            )
        )
        cursor = span.end
    output_parts.append(line_text[cursor:])
    return "".join(output_parts)


def _mask_entire_line(line_text: str) -> str:
    if not line_text:
        return line_text
    return "".join(_mask_char(character) for character in line_text)


def _render_preview_png(text: str) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    source_lines = text.splitlines()
    if not source_lines:
        source_lines = [""]
    lines = source_lines[:_MAX_RENDER_LINES]
    prepared_lines = [
        line[:_MAX_RENDER_LINE_LENGTH] for line in lines
    ]
    max_chars = max((len(item) for item in prepared_lines), default=1)
    margin = 16
    line_height = 15
    width = min(1600, max(520, margin * 2 + (max_chars * 8)))
    height = min(2600, max(120, margin * 2 + (len(prepared_lines) * line_height)))
    image = Image.new("RGB", (width, height), color=(14, 18, 29))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    y = margin
    for line in prepared_lines:
        draw.text((margin, y), line, fill=(230, 236, 246), font=font)
        y += line_height
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def build_safeguarded_preview_artifact(
    *,
    lines: Sequence[PreviewLine],
    tokens: Sequence[PreviewToken],
    findings: Sequence[PreviewFinding],
) -> SafeguardedPreviewArtifact:
    ordered_lines = sorted(lines, key=lambda item: item.line_id)
    line_text_by_id = {item.line_id: item.text for item in ordered_lines}
    line_lengths = {line_id: len(text) for line_id, text in line_text_by_id.items()}
    tokens_by_line: dict[str, list[PreviewToken]] = {}
    for token in tokens:
        tokens_by_line.setdefault(token.line_id, []).append(token)
    token_offsets_by_line = {
        line_id: _build_token_offsets(line_text=text, tokens=tokens_by_line.get(line_id, ()))
        for line_id, text in line_text_by_id.items()
    }

    candidate_spans: list[PreviewMaskSpan] = []
    area_mask_only_finding_ids: set[str] = set()
    line_area_mask_markers: dict[str, set[str]] = {}
    line_area_mask_full_redaction: set[str] = set()
    page_area_mask_markers: set[str] = set()
    for finding in findings:
        resolved_span = _resolve_span_for_finding(
            finding=finding,
            line_lengths=line_lengths,
            token_offsets_by_line=token_offsets_by_line,
        )
        if resolved_span is not None:
            candidate_spans.append(resolved_span)
            continue
        if (
            _is_maskable_status(str(finding.decision_status or "").strip().upper())
            and finding.area_mask_id is not None
        ):
            area_mask_only_finding_ids.add(finding.finding_id)
            normalized_mask_id = finding.area_mask_id.strip()
            if finding.line_id and finding.line_id in line_text_by_id:
                line_area_mask_markers.setdefault(finding.line_id, set()).add(normalized_mask_id)
                # Line-level area masks are conservative fallbacks: redact the full rendered line
                # so no raw value can leak when token/span anchors are unavailable.
                line_area_mask_full_redaction.add(finding.line_id)
            else:
                page_area_mask_markers.add(normalized_mask_id)

    resolved_spans = resolve_mask_spans(candidate_spans)
    spans_by_line: dict[str, list[PreviewMaskSpan]] = {}
    for span in resolved_spans:
        spans_by_line.setdefault(span.line_id, []).append(span)

    output_lines: list[str] = []
    for line in ordered_lines:
        masked_text = _apply_line_spans(
            line_text=line.text,
            spans=spans_by_line.get(line.line_id, ()),
        )
        if line.line_id in line_area_mask_full_redaction:
            masked_text = _mask_entire_line(masked_text)
        markers = sorted(line_area_mask_markers.get(line.line_id, set()))
        if markers:
            masked_text = f"{masked_text} [AREA_MASK:{len(markers)}]"
        output_lines.append(f"{line.line_id}: {masked_text}")

    if page_area_mask_markers:
        output_lines.append("")
        output_lines.append("AREA_MASK_ONLY_FINDINGS:")
        for marker in sorted(page_area_mask_markers):
            output_lines.append(f"- {marker}")

    if not output_lines:
        output_lines = ["NO_TRANSCRIPTION_LINES_AVAILABLE"]

    text = "\n".join(output_lines) + "\n"
    sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    png_bytes = _render_preview_png(text)
    return SafeguardedPreviewArtifact(
        text=text,
        sha256=sha256,
        png_bytes=png_bytes,
        applied_spans=resolved_spans,
        area_mask_only_finding_ids=tuple(sorted(area_mask_only_finding_ids)),
    )


def canonical_preview_manifest_payload(
    *,
    run_id: str,
    page_rows: Sequence[tuple[str, str]],
    approved_snapshot_sha256: str | None = None,
    approved_snapshot_payload: Mapping[str, object] | None = None,
    preview_keys_by_page: Mapping[str, str] | None = None,
) -> dict[str, object]:
    del preview_keys_by_page

    normalized_snapshot = (
        dict(approved_snapshot_payload)
        if isinstance(approved_snapshot_payload, Mapping)
        else {}
    )
    normalized_approved_snapshot_sha256 = (
        approved_snapshot_sha256.strip()
        if isinstance(approved_snapshot_sha256, str) and approved_snapshot_sha256.strip()
        else _normalized_optional_text(normalized_snapshot.get("approvedSnapshotSha256"))
    )

    run_metadata = normalized_snapshot.get("run")
    run_payload = dict(run_metadata) if isinstance(run_metadata, Mapping) else {}
    policy_lineage = {
        "policySnapshotHash": _normalized_optional_text(run_payload.get("policySnapshotHash")),
        "policyId": _normalized_optional_text(run_payload.get("policyId")),
        "policyFamilyId": _normalized_optional_text(run_payload.get("policyFamilyId")),
        "policyVersion": _normalized_optional_text(run_payload.get("policyVersion")),
    }

    page_index_by_id: dict[str, int] = {}
    outputs_payload = normalized_snapshot.get("outputs")
    if isinstance(outputs_payload, Sequence) and not isinstance(outputs_payload, (str, bytes)):
        for item in outputs_payload:
            if not isinstance(item, Mapping):
                continue
            page_id = _normalized_optional_text(item.get("pageId"))
            page_index = _normalized_optional_int(item.get("pageIndex"))
            if page_id is None or page_index is None:
                continue
            page_index_by_id[page_id] = page_index

    findings_payload = normalized_snapshot.get("findings")
    if isinstance(findings_payload, Sequence) and not isinstance(findings_payload, (str, bytes)):
        for item in findings_payload:
            if not isinstance(item, Mapping):
                continue
            page_id = _normalized_optional_text(item.get("pageId"))
            page_index = _normalized_optional_int(item.get("pageIndex"))
            if page_id is None or page_index is None or page_id in page_index_by_id:
                continue
            page_index_by_id[page_id] = page_index

    output_pages = [
        {"pageId": page_id, "previewSha256": preview_sha256}
        for page_id, preview_sha256 in sorted(page_rows, key=lambda item: (item[0], item[1]))
    ]
    entries = _build_screening_safe_manifest_entries(
        snapshot_payload=normalized_snapshot,
        policy_lineage=policy_lineage,
        page_index_by_id=page_index_by_id,
    )
    review_lineage = _build_review_lineage(normalized_snapshot)

    payload: dict[str, object] = {
        "manifestSchemaVersion": 1,
        "manifestKind": "SCREENING_SAFE_REDACTION_MANIFEST",
        "runId": run_id,
        "internalOnly": True,
        "exportApproved": False,
        "notExportApproved": True,
        "exportApprovalStatus": "NOT_EXPORT_APPROVED",
        "policyLineage": policy_lineage,
        "reviewLineage": review_lineage,
        "outputs": {"pageCount": len(output_pages), "pages": output_pages},
        "entryCount": len(entries),
        "entries": entries,
    }
    if normalized_approved_snapshot_sha256 is not None:
        payload["approvedSnapshotSha256"] = normalized_approved_snapshot_sha256
    return payload


def canonical_preview_manifest_bytes(
    *,
    run_id: str,
    page_rows: Sequence[tuple[str, str]],
    approved_snapshot_sha256: str | None = None,
    approved_snapshot_payload: Mapping[str, object] | None = None,
    preview_keys_by_page: Mapping[str, str] | None = None,
) -> bytes:
    payload = canonical_preview_manifest_payload(
        run_id=run_id,
        page_rows=page_rows,
        approved_snapshot_sha256=approved_snapshot_sha256,
        approved_snapshot_payload=approved_snapshot_payload,
        preview_keys_by_page=preview_keys_by_page,
    )
    return json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_preview_manifest_sha256(
    *,
    run_id: str,
    page_rows: Sequence[tuple[str, str]],
    approved_snapshot_sha256: str | None = None,
    approved_snapshot_payload: Mapping[str, object] | None = None,
    preview_keys_by_page: Mapping[str, str] | None = None,
) -> str:
    payload_bytes = canonical_preview_manifest_bytes(
        run_id=run_id,
        page_rows=page_rows,
        approved_snapshot_sha256=approved_snapshot_sha256,
        approved_snapshot_payload=approved_snapshot_payload,
        preview_keys_by_page=preview_keys_by_page,
    )
    return hashlib.sha256(payload_bytes).hexdigest()


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


def _safe_bbox_token(value: object) -> str | None:
    if not isinstance(value, Mapping):
        return None
    canonical_bytes = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()[:16]


def _compact_secondary_basis_summary(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    summary: dict[str, object] = {"summaryMode": "COMPACT_SCREENING_SAFE"}

    corroborating = value.get("corroboratingDetectors")
    if isinstance(corroborating, Sequence) and not isinstance(corroborating, (str, bytes)):
        detector_count = 0
        bases: set[str] = set()
        sources: set[str] = set()
        max_confidence: float | None = None
        for item in corroborating:
            if not isinstance(item, Mapping):
                continue
            detector_count += 1
            basis_value = _normalized_optional_text(item.get("basis"))
            if basis_value is not None:
                bases.add(basis_value.upper())
            source_value = _normalized_optional_text(item.get("source"))
            if source_value is not None:
                sources.add(source_value.upper())
            confidence_value = _normalized_optional_float(item.get("confidence"))
            if confidence_value is None:
                continue
            if max_confidence is None or confidence_value > max_confidence:
                max_confidence = confidence_value
        if detector_count > 0:
            summary["corroboratingDetectorCount"] = detector_count
        if bases:
            summary["corroboratingBases"] = sorted(bases)
        if sources:
            summary["corroboratingSources"] = sorted(sources)
        if max_confidence is not None:
            summary["maxCorroboratingConfidence"] = max_confidence

    fusion = value.get("fusion")
    if isinstance(fusion, Mapping):
        cluster_size = _normalized_optional_int(fusion.get("clusterSize"))
        if cluster_size is not None:
            summary["fusionClusterSize"] = cluster_size
        review_reasons = fusion.get("reviewReasons")
        if isinstance(review_reasons, Sequence) and not isinstance(
            review_reasons, (str, bytes)
        ):
            normalized_reasons = sorted(
                {
                    reason.strip()
                    for reason in review_reasons
                    if isinstance(reason, str) and reason.strip()
                }
            )
            if normalized_reasons:
                summary["fusionReviewReasons"] = normalized_reasons

    assist_present = False
    if "assistSummary" in value:
        assist_present = True
    assist_payload = value.get("assist")
    if isinstance(assist_payload, Mapping) and "summary" in assist_payload:
        assist_present = True
    if assist_present:
        summary["assistExplanationIncluded"] = False

    if set(summary.keys()) == {"summaryMode"}:
        return None
    return summary


def _normalized_action_type(value: object) -> str:
    action = _normalized_optional_text(value)
    if action is None:
        return "MASK"
    normalized = action.upper()
    if normalized in _MANIFEST_ALLOWED_ACTIONS:
        return normalized
    return "MASK"


def _build_screening_safe_manifest_entries(
    *,
    snapshot_payload: Mapping[str, object],
    policy_lineage: Mapping[str, object],
    page_index_by_id: Mapping[str, int],
) -> list[dict[str, object]]:
    findings_payload = snapshot_payload.get("findings")
    if not isinstance(findings_payload, Sequence) or isinstance(findings_payload, (str, bytes)):
        return []
    entries: list[dict[str, object]] = []
    for item in findings_payload:
        if not isinstance(item, Mapping):
            continue
        decision_state = _normalized_optional_text(item.get("decisionStatus"))
        if decision_state is None:
            continue
        normalized_decision_state = decision_state.upper()
        if normalized_decision_state not in _APPLIED_DECISION_STATUSES:
            continue
        entry_id = _normalized_optional_text(item.get("id"))
        category = _normalized_optional_text(item.get("category"))
        page_id = _normalized_optional_text(item.get("pageId"))
        if entry_id is None or category is None or page_id is None:
            continue

        line_id = _normalized_optional_text(item.get("lineId"))
        page_index = _normalized_optional_int(item.get("pageIndex"))
        if page_index is None:
            page_index = page_index_by_id.get(page_id)
        decision_timestamp = (
            _normalized_optional_text(item.get("decisionAt"))
            or _normalized_optional_text(item.get("updatedAt"))
        )

        token_ref_count = 0
        token_refs = item.get("tokenRefsJson")
        if isinstance(token_refs, Sequence) and not isinstance(token_refs, (str, bytes)):
            token_ref_count = sum(1 for token in token_refs if isinstance(token, Mapping))
        location_ref: dict[str, object] = {}
        span_basis_kind = _normalized_optional_text(item.get("spanBasisKind"))
        span_basis_ref = _normalized_optional_text(item.get("spanBasisRef"))
        span_start = _normalized_optional_int(item.get("spanStart"))
        span_end = _normalized_optional_int(item.get("spanEnd"))
        area_mask_id = _normalized_optional_text(item.get("areaMaskId"))
        bbox_token = _safe_bbox_token(item.get("bboxRefs"))
        if span_basis_kind is not None:
            location_ref["spanBasisKind"] = span_basis_kind
        if span_basis_ref is not None:
            location_ref["spanBasisRef"] = span_basis_ref
        if span_start is not None:
            location_ref["spanStart"] = span_start
        if span_end is not None:
            location_ref["spanEnd"] = span_end
        if token_ref_count > 0:
            location_ref["tokenRefCount"] = token_ref_count
        if area_mask_id is not None:
            location_ref["areaMaskId"] = area_mask_id
        if bbox_token is not None:
            location_ref["bboxToken"] = bbox_token

        entry = {
            "entryId": entry_id,
            "appliedAction": _normalized_action_type(item.get("actionType")),
            "category": category.upper(),
            "pageId": page_id,
            "pageIndex": page_index,
            "lineId": line_id,
            "locationRef": location_ref,
            "basisPrimary": (
                _normalized_optional_text(item.get("basisPrimary")) or "UNKNOWN"
            ).upper(),
            "confidence": _normalized_optional_float(item.get("confidence")),
            "secondaryBasisSummary": _compact_secondary_basis_summary(
                item.get("basisSecondaryJson")
            ),
            "finalDecisionState": normalized_decision_state,
            "reviewState": normalized_decision_state,
            "policySnapshotHash": _normalized_optional_text(
                policy_lineage.get("policySnapshotHash")
            ),
            "policyId": _normalized_optional_text(policy_lineage.get("policyId")),
            "policyFamilyId": _normalized_optional_text(policy_lineage.get("policyFamilyId")),
            "policyVersion": _normalized_optional_text(policy_lineage.get("policyVersion")),
            "decisionTimestamp": decision_timestamp,
            "decisionBy": _normalized_optional_text(item.get("decisionBy")),
            "decisionEtag": _normalized_optional_text(item.get("decisionEtag")),
        }
        entries.append(entry)

    entries.sort(
        key=lambda item: (
            item.get("pageIndex") if isinstance(item.get("pageIndex"), int) else 0,
            str(item.get("pageId") or ""),
            str(item.get("lineId") or ""),
            str(item.get("decisionTimestamp") or ""),
            str(item.get("entryId") or ""),
        )
    )
    return entries


def _build_review_lineage(snapshot_payload: Mapping[str, object]) -> dict[str, object]:
    review_payload = snapshot_payload.get("review")
    review = dict(review_payload) if isinstance(review_payload, Mapping) else {}
    page_reviews_payload = snapshot_payload.get("pageReviews")
    page_reviews = (
        [item for item in page_reviews_payload if isinstance(item, Mapping)]
        if isinstance(page_reviews_payload, Sequence)
        and not isinstance(page_reviews_payload, (str, bytes))
        else []
    )

    page_approved_count = 0
    second_review_required_count = 0
    second_review_approved_count = 0
    reviewer_ids: set[str] = set()
    for item in page_reviews:
        review_status = _normalized_optional_text(item.get("reviewStatus"))
        if isinstance(review_status, str) and review_status.upper() == "APPROVED":
            page_approved_count += 1
        requires_second_review = bool(item.get("requiresSecondReview"))
        if requires_second_review:
            second_review_required_count += 1
            second_review_status = _normalized_optional_text(item.get("secondReviewStatus"))
            if isinstance(second_review_status, str) and second_review_status.upper() == "APPROVED":
                second_review_approved_count += 1
        first_reviewer = _normalized_optional_text(item.get("firstReviewedBy"))
        if first_reviewer is not None:
            reviewer_ids.add(first_reviewer)
        second_reviewer = _normalized_optional_text(item.get("secondReviewedBy"))
        if second_reviewer is not None:
            reviewer_ids.add(second_reviewer)

    run_approved_by = _normalized_optional_text(review.get("approvedBy"))
    if run_approved_by is not None:
        reviewer_ids.add(run_approved_by)
    run_review_started_by = _normalized_optional_text(review.get("reviewStartedBy"))
    if run_review_started_by is not None:
        reviewer_ids.add(run_review_started_by)

    return {
        "runReviewStatus": (
            _normalized_optional_text(review.get("reviewStatus")) or "APPROVED"
        ).upper(),
        "reviewStartedBy": run_review_started_by,
        "reviewStartedAt": _normalized_optional_text(review.get("reviewStartedAt")),
        "approvedBy": run_approved_by,
        "approvedAt": _normalized_optional_text(review.get("approvedAt")),
        "lockedAt": _normalized_optional_text(review.get("lockedAt")),
        "pageSignOffs": {
            "pageCount": len(page_reviews),
            "approvedPageCount": page_approved_count,
            "secondReviewRequiredCount": second_review_required_count,
            "secondReviewApprovedCount": second_review_approved_count,
            "reviewerUserIds": sorted(reviewer_ids),
        },
    }
