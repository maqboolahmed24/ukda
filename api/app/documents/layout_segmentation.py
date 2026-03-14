from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, replace
from io import BytesIO
from statistics import median
from typing import Mapping, Sequence

from app.documents.layout_contract import (
    LayoutCanonicalPage,
    build_layout_canonical_page,
)
from app.documents.models import (
    LayoutRescueCandidateKind,
    LayoutRescueCandidateStatus,
    PageRecallStatus,
)
from app.documents.reading_order import infer_reading_order

_LAYOUT_WARNING_LOW_LINES = "LOW_LINES"
_LAYOUT_WARNING_OVERLAPS = "OVERLAPS"
_LAYOUT_WARNING_COMPLEX_LAYOUT = "COMPLEX_LAYOUT"
_LAYOUT_ALGORITHM_VERSION = "layout-segmentation-v1"
_LAYOUT_RECALL_CHECK_VERSION = "layout-recall-v1"


class LayoutSegmentationError(RuntimeError):
    """Layout segmentation execution failed."""


@dataclass(frozen=True)
class LayoutRescueCandidateDraft:
    id: str
    candidate_kind: LayoutRescueCandidateKind
    geometry_json: dict[str, object]
    confidence: float
    source_signal: str
    status: LayoutRescueCandidateStatus


@dataclass(frozen=True)
class LayoutSegmentationOutcome:
    canonical_page_payload: dict[str, object]
    metrics_json: dict[str, object]
    warnings_json: list[str]
    page_recall_status: PageRecallStatus
    recall_check_version: str
    missed_text_risk_score: float
    recall_signals_json: dict[str, object]
    rescue_candidates: list[LayoutRescueCandidateDraft]


@dataclass(frozen=True)
class _Box:
    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def width(self) -> int:
        return max(0, self.x1 - self.x0)

    @property
    def height(self) -> int:
        return max(0, self.y1 - self.y0)

    @property
    def area(self) -> int:
        return self.width * self.height


@dataclass(frozen=True)
class _LineCandidate:
    box: _Box
    sort_y: float
    sort_x: float


@dataclass(frozen=True)
class _RegionCandidate:
    box: _Box
    line_indexes: tuple[int, ...]


@dataclass(frozen=True)
class _InkComponent:
    box: _Box
    pixel_count: int
    dark_pixel_count: int


def _require_image_lib():
    try:
        from PIL import Image, UnidentifiedImageError
    except ModuleNotFoundError as error:  # pragma: no cover - dependency guard
        raise LayoutSegmentationError(
            "Pillow dependency is required for layout segmentation."
        ) from error
    return Image, UnidentifiedImageError


def _resolve_float_param(
    params_json: Mapping[str, object],
    *,
    key: str,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    raw = params_json.get(key)
    if isinstance(raw, bool):
        return default
    if isinstance(raw, (float, int)):
        numeric = float(raw)
        if math.isfinite(numeric):
            return max(minimum, min(maximum, numeric))
    return default


def _resolve_int_param(
    params_json: Mapping[str, object],
    *,
    key: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    raw = params_json.get(key)
    if isinstance(raw, bool):
        return default
    if isinstance(raw, int):
        return max(minimum, min(maximum, raw))
    if isinstance(raw, float) and math.isfinite(raw):
        return max(minimum, min(maximum, int(round(raw))))
    return default


def _read_grayscale_image(payload: bytes) -> tuple[int, int, list[int]]:
    Image, UnidentifiedImageError = _require_image_lib()
    try:
        with Image.open(BytesIO(payload)) as opened:
            grayscale = opened.convert("L")
            width, height = grayscale.size
            values = list(grayscale.getdata())
    except UnidentifiedImageError as error:
        raise LayoutSegmentationError(
            "Layout segmentation input is not a decodable image."
        ) from error
    if width <= 0 or height <= 0:
        raise LayoutSegmentationError("Layout segmentation input has invalid dimensions.")
    if len(values) != width * height:
        raise LayoutSegmentationError("Layout segmentation input pixel buffer is invalid.")
    return width, height, values


def _otsu_threshold(values: Sequence[int]) -> int:
    histogram = [0] * 256
    for value in values:
        histogram[max(0, min(255, int(value)))] += 1
    total = float(len(values))
    if total <= 0:
        return 128
    weighted_sum = 0.0
    for intensity, count in enumerate(histogram):
        weighted_sum += intensity * float(count)

    best_threshold = 128
    best_variance = -1.0
    background_weight = 0.0
    background_sum = 0.0
    for intensity, count in enumerate(histogram):
        count_float = float(count)
        background_weight += count_float
        if background_weight <= 0:
            continue
        foreground_weight = total - background_weight
        if foreground_weight <= 0:
            break
        background_sum += intensity * count_float
        mean_background = background_sum / background_weight
        mean_foreground = (weighted_sum - background_sum) / foreground_weight
        between_class_variance = (
            background_weight
            * foreground_weight
            * (mean_background - mean_foreground) ** 2
        )
        if between_class_variance > best_variance:
            best_variance = between_class_variance
            best_threshold = intensity
    return best_threshold


def _build_dark_mask(
    *,
    values: Sequence[int],
    width: int,
    height: int,
    threshold: int,
) -> list[list[bool]]:
    rows: list[list[bool]] = []
    offset = 0
    for _ in range(height):
        row = [value <= threshold for value in values[offset : offset + width]]
        rows.append(row)
        offset += width
    return rows


def _build_intensity_range_mask(
    *,
    values: Sequence[int],
    width: int,
    height: int,
    minimum: int,
    maximum: int,
) -> list[list[bool]]:
    lower = max(0, min(255, minimum))
    upper = max(0, min(255, maximum))
    if upper < lower:
        lower, upper = upper, lower
    rows: list[list[bool]] = []
    offset = 0
    for _ in range(height):
        row = [
            lower <= value <= upper
            for value in values[offset : offset + width]
        ]
        rows.append(row)
        offset += width
    return rows


def _group_sorted_indices(indices: Sequence[int], *, max_gap: int) -> list[tuple[int, int]]:
    if not indices:
        return []
    groups: list[tuple[int, int]] = []
    start = int(indices[0])
    previous = int(indices[0])
    for raw in indices[1:]:
        current = int(raw)
        if current - previous <= max_gap + 1:
            previous = current
            continue
        groups.append((start, previous))
        start = current
        previous = current
    groups.append((start, previous))
    return groups


def _merge_nearby_groups(
    groups: Sequence[tuple[int, int]],
    *,
    max_gap: int,
) -> list[tuple[int, int]]:
    if not groups:
        return []
    merged: list[tuple[int, int]] = [groups[0]]
    for start, end in groups[1:]:
        prev_start, prev_end = merged[-1]
        if start - prev_end <= max_gap + 1:
            merged[-1] = (prev_start, max(prev_end, end))
            continue
        merged.append((start, end))
    return merged


def _clip_box(
    *,
    box: _Box,
    width: int,
    height: int,
) -> _Box:
    return _Box(
        x0=max(0, min(width, box.x0)),
        y0=max(0, min(height, box.y0)),
        x1=max(0, min(width, box.x1)),
        y1=max(0, min(height, box.y1)),
    )


def _union_box(left: _Box, right: _Box) -> _Box:
    return _Box(
        x0=min(left.x0, right.x0),
        y0=min(left.y0, right.y0),
        x1=max(left.x1, right.x1),
        y1=max(left.y1, right.y1),
    )


def _intersection_area(left: _Box, right: _Box) -> int:
    overlap_x0 = max(left.x0, right.x0)
    overlap_y0 = max(left.y0, right.y0)
    overlap_x1 = min(left.x1, right.x1)
    overlap_y1 = min(left.y1, right.y1)
    if overlap_x1 <= overlap_x0 or overlap_y1 <= overlap_y0:
        return 0
    return (overlap_x1 - overlap_x0) * (overlap_y1 - overlap_y0)


def _horizontal_overlap_ratio(left: _Box, right: _Box) -> float:
    overlap = max(0, min(left.x1, right.x1) - max(left.x0, right.x0))
    denominator = float(max(1, min(left.width, right.width)))
    return overlap / denominator


def _horizontal_distance(left: _Box, right: _Box) -> int:
    if left.x1 < right.x0:
        return right.x0 - left.x1
    if right.x1 < left.x0:
        return left.x0 - right.x1
    return 0


def _vertical_gap(left: _Box, right: _Box) -> int:
    if left.y1 < right.y0:
        return right.y0 - left.y1
    if right.y1 < left.y0:
        return left.y0 - right.y1
    return 0


def _max_overlap_score(boxes: Sequence[_Box]) -> float:
    best = 0.0
    for index, left in enumerate(boxes):
        for right in boxes[index + 1 :]:
            intersection = _intersection_area(left, right)
            if intersection <= 0:
                continue
            denominator = float(max(1, min(left.area, right.area)))
            best = max(best, intersection / denominator)
    return best


def _bbox_to_polygon_points(box: _Box) -> list[tuple[float, float]]:
    return [
        (float(box.x0), float(box.y0)),
        (float(box.x1), float(box.y0)),
        (float(box.x1), float(box.y1)),
        (float(box.x0), float(box.y1)),
    ]


def _clamp(value: float, *, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _box_iou(left: _Box, right: _Box) -> float:
    intersection = _intersection_area(left, right)
    if intersection <= 0:
        return 0.0
    union = float(max(1, left.area + right.area - intersection))
    return float(intersection) / union


def _expand_box(*, box: _Box, delta_x: int, delta_y: int, width: int, height: int) -> _Box:
    return _clip_box(
        box=_Box(
            x0=box.x0 - delta_x,
            y0=box.y0 - delta_y,
            x1=box.x1 + delta_x,
            y1=box.y1 + delta_y,
        ),
        width=width,
        height=height,
    )


def _extract_ink_components(
    *,
    candidate_mask: Sequence[Sequence[bool]],
    dark_mask: Sequence[Sequence[bool]],
    width: int,
    height: int,
    max_components: int = 12000,
) -> tuple[list[_InkComponent], bool]:
    if width <= 0 or height <= 0:
        return [], False
    visited = bytearray(width * height)
    components: list[_InkComponent] = []
    overflowed = False
    for y_index in range(height):
        row = candidate_mask[y_index]
        for x_index, active in enumerate(row):
            if not active:
                continue
            seed = y_index * width + x_index
            if visited[seed] == 1:
                continue
            stack = [seed]
            visited[seed] = 1
            min_x = x_index
            max_x = x_index
            min_y = y_index
            max_y = y_index
            pixel_count = 0
            dark_pixel_count = 0
            while stack:
                current = stack.pop()
                current_y, current_x = divmod(current, width)
                pixel_count += 1
                if dark_mask[current_y][current_x]:
                    dark_pixel_count += 1
                if current_x < min_x:
                    min_x = current_x
                if current_x > max_x:
                    max_x = current_x
                if current_y < min_y:
                    min_y = current_y
                if current_y > max_y:
                    max_y = current_y
                y_start = max(0, current_y - 1)
                y_end = min(height - 1, current_y + 1)
                x_start = max(0, current_x - 1)
                x_end = min(width - 1, current_x + 1)
                for neighbor_y in range(y_start, y_end + 1):
                    neighbor_row = candidate_mask[neighbor_y]
                    row_offset = neighbor_y * width
                    for neighbor_x in range(x_start, x_end + 1):
                        if not neighbor_row[neighbor_x]:
                            continue
                        neighbor_index = row_offset + neighbor_x
                        if visited[neighbor_index] == 1:
                            continue
                        visited[neighbor_index] = 1
                        stack.append(neighbor_index)
            components.append(
                _InkComponent(
                    box=_Box(
                        x0=min_x,
                        y0=min_y,
                        x1=max_x + 1,
                        y1=max_y + 1,
                    ),
                    pixel_count=pixel_count,
                    dark_pixel_count=dark_pixel_count,
                )
            )
            if len(components) >= max_components:
                overflowed = True
                return components, overflowed
    return components, overflowed


def _build_rescue_geometry(
    *,
    box: _Box,
    page_id: str,
    page_index: int,
    line_id: str | None,
) -> dict[str, object]:
    geometry: dict[str, object] = {
        "schemaVersion": 1,
        "pageId": page_id,
        "pageIndex": page_index,
        "bbox": {
            "x": box.x0,
            "y": box.y0,
            "width": box.width,
            "height": box.height,
        },
        "polygon": [
            {"x": float(box.x0), "y": float(box.y0)},
            {"x": float(box.x1), "y": float(box.y0)},
            {"x": float(box.x1), "y": float(box.y1)},
            {"x": float(box.x0), "y": float(box.y1)},
        ],
    }
    if line_id is not None:
        geometry["lineId"] = line_id
    return geometry


def _build_recall_assessment(
    *,
    run_id: str,
    page_id: str,
    page_index: int,
    page_width: int,
    page_height: int,
    threshold: int,
    values: Sequence[int],
    line_boxes_by_id: Mapping[str, _Box],
    warnings: Sequence[str],
    num_lines: int,
    line_coverage_percent: float,
) -> tuple[float, dict[str, object], list[LayoutRescueCandidateDraft], PageRecallStatus]:
    faint_threshold = max(threshold, min(252, threshold + 32))
    dark_values = [value for value in values if value <= threshold]
    dark_value_median = int(round(median(dark_values))) if dark_values else threshold
    faint_floor = dark_value_median + max(
        8,
        int(round((faint_threshold - dark_value_median) * 0.32)),
    )
    faint_floor = max(0, min(faint_threshold, faint_floor))
    faint_mask = _build_intensity_range_mask(
        values=values,
        width=page_width,
        height=page_height,
        minimum=faint_floor,
        maximum=faint_threshold,
    )
    core_dark_threshold = max(0, min(255, dark_value_median + 2))
    core_dark_mask = _build_dark_mask(
        values=values,
        width=page_width,
        height=page_height,
        threshold=core_dark_threshold,
    )
    components, overflowed = _extract_ink_components(
        candidate_mask=faint_mask,
        dark_mask=core_dark_mask,
        width=page_width,
        height=page_height,
    )
    if not components:
        structural_risk = 0.0
        if num_lines == 0:
            structural_risk += 0.35
        elif line_coverage_percent < 0.75:
            structural_risk += 0.20
        if "LOW_LINES" in set(warnings):
            structural_risk += 0.15
        structural_risk = _clamp(structural_risk, minimum=0.0, maximum=1.0)
        if structural_risk >= 0.60:
            page_recall_status: PageRecallStatus = "NEEDS_MANUAL_REVIEW"
        elif structural_risk >= 0.25:
            page_recall_status = "NEEDS_RESCUE"
        else:
            page_recall_status = "COMPLETE"
        signals = {
            "algorithm_version": _LAYOUT_RECALL_CHECK_VERSION,
            "threshold_value": threshold,
            "faint_threshold_value": faint_threshold,
            "faint_floor_value": faint_floor,
            "core_dark_threshold_value": core_dark_threshold,
            "faint_component_count": 0,
            "candidate_count": 0,
            "accepted_candidate_count": 0,
            "rejected_candidate_count": 0,
            "unmatched_faint_ratio": 0.0,
            "overflowed_component_scan": False,
            "structural_only_risk_score": round(structural_risk, 6),
            "line_count": num_lines,
            "line_coverage_percent": line_coverage_percent,
            "rescue_candidate_quality_score": 0.0,
        }
        return round(structural_risk, 6), signals, [], page_recall_status

    page_area = float(max(1, page_width * page_height))
    min_component_pixels = max(10, int(round(page_area * 0.000012)))
    max_component_box_area = max(1600, int(round(page_area * 0.14)))
    median_line_height = (
        median([box.height for box in line_boxes_by_id.values()])
        if line_boxes_by_id
        else 0
    )
    expand_x = max(3, int(round(page_width * 0.004)))
    expand_y = max(3, int(round(max(8.0, median_line_height * 0.6))))
    expanded_line_boxes = [
        (
            line_id,
            _expand_box(
                box=box,
                delta_x=expand_x,
                delta_y=expand_y,
                width=page_width,
                height=page_height,
            ),
        )
        for line_id, box in line_boxes_by_id.items()
    ]
    sorted_components = sorted(
        components,
        key=lambda item: (item.box.y0, item.box.x0, -item.pixel_count),
    )
    all_faint_pixels = sum(component.pixel_count for component in sorted_components)
    unmatched_faint_pixels = 0
    candidate_rows: list[LayoutRescueCandidateDraft] = []
    anomalous_line_merge_count = 0
    line_height_outlier_threshold = max(
        24,
        int(round(max(18.0, median_line_height * 1.45))),
    )
    for component_index, component in enumerate(sorted_components, start=1):
        if component.pixel_count < min_component_pixels:
            continue
        if component.box.area > max_component_box_area:
            continue

        nearest_line_id: str | None = None
        nearest_vertical_gap: int | None = None
        nearest_overlap_ratio = 0.0
        for line_id, line_box in line_boxes_by_id.items():
            overlap_ratio = _horizontal_overlap_ratio(component.box, line_box)
            vertical_gap = _vertical_gap(component.box, line_box)
            if nearest_vertical_gap is None:
                nearest_line_id = line_id
                nearest_vertical_gap = vertical_gap
                nearest_overlap_ratio = overlap_ratio
                continue
            if vertical_gap < nearest_vertical_gap:
                nearest_line_id = line_id
                nearest_vertical_gap = vertical_gap
                nearest_overlap_ratio = overlap_ratio
                continue
            if vertical_gap == nearest_vertical_gap and overlap_ratio > nearest_overlap_ratio:
                nearest_line_id = line_id
                nearest_vertical_gap = vertical_gap
                nearest_overlap_ratio = overlap_ratio

        covered_by_line = False
        covered_by_line_id: str | None = None
        for line_id, expanded_line_box in expanded_line_boxes:
            overlap_area = _intersection_area(component.box, expanded_line_box)
            if overlap_area <= 0:
                continue
            overlap_ratio = float(overlap_area) / float(max(1, component.box.area))
            # Keep strict suppression for core-line components, but preserve
            # near-line faint blobs so they can become LINE_EXPANSION rescues.
            if overlap_ratio >= 0.94:
                covered_by_line = True
                covered_by_line_id = line_id
                break

        line_expansion_gap = max(12, int(round(max(14.0, median_line_height * 2.0))))
        candidate_kind: LayoutRescueCandidateKind = "PAGE_WINDOW"
        source_signal = "UNASSOCIATED_COMPONENT_PAGE_WINDOW"
        status_override: LayoutRescueCandidateStatus | None = None
        if (
            nearest_line_id is not None
            and nearest_vertical_gap is not None
            and nearest_vertical_gap <= line_expansion_gap
            and nearest_overlap_ratio >= 0.18
        ):
            candidate_kind = "LINE_EXPANSION"
            source_signal = "UNASSOCIATED_COMPONENT_NEAR_LINE"

        if covered_by_line:
            if covered_by_line_id is None:
                continue
            covered_line = line_boxes_by_id.get(covered_by_line_id)
            if covered_line is None:
                continue
            line_height_ratio = (
                float(covered_line.height) / float(max(1.0, median_line_height))
                if median_line_height > 0
                else 1.0
            )
            if (
                covered_line.height < line_height_outlier_threshold
                and line_height_ratio < 1.35
            ):
                continue
            anomalous_line_merge_count += 1
            unmatched_faint_pixels += component.pixel_count
            candidate_kind = "LINE_EXPANSION"
            source_signal = "MERGED_COMPONENT_LINE_OUTLIER"
            nearest_line_id = covered_by_line_id
            nearest_vertical_gap = 0
            nearest_overlap_ratio = 1.0
            status_override = "ACCEPTED"
        else:
            unmatched_faint_pixels += component.pixel_count

        density = float(component.pixel_count) / float(max(1, component.box.area))
        size_score = _clamp(
            float(component.pixel_count) / float(max(1, min_component_pixels * 3)),
            minimum=0.0,
            maximum=1.0,
        )
        proximity_score = (
            1.0
            if nearest_vertical_gap is None
            else _clamp(
                1.0
                - (float(nearest_vertical_gap) / float(max(1, line_expansion_gap * 2))),
                minimum=0.0,
                maximum=1.0,
            )
        )
        confidence = _clamp(
            (density * 0.45) + (size_score * 0.35) + (proximity_score * 0.20),
            minimum=0.0,
            maximum=1.0,
        )
        status: LayoutRescueCandidateStatus = (
            status_override
            if status_override is not None
            else ("ACCEPTED" if confidence >= 0.42 else "REJECTED")
        )
        candidate_token = hashlib.sha256(
            f"{run_id}|{page_id}|{candidate_kind}|{component.box.x0}|{component.box.y0}|"
            f"{component.box.x1}|{component.box.y1}|{component_index}".encode("utf-8")
        ).hexdigest()[:10]
        candidate_rows.append(
            LayoutRescueCandidateDraft(
                id=f"resc-{page_index + 1:04d}-{component_index:03d}-{candidate_token}",
                candidate_kind=candidate_kind,
                geometry_json=_build_rescue_geometry(
                    box=component.box,
                    page_id=page_id,
                    page_index=page_index,
                    line_id=nearest_line_id if candidate_kind == "LINE_EXPANSION" else None,
                ),
                confidence=round(confidence, 6),
                source_signal=source_signal,
                status=status,
            )
        )

    candidate_rows.sort(
        key=lambda row: (
            -row.confidence,
            float(row.geometry_json["bbox"]["y"]),  # type: ignore[index]
            float(row.geometry_json["bbox"]["x"]),  # type: ignore[index]
            row.id,
        )
    )
    candidate_rows = candidate_rows[:12]

    accepted_candidates = [row for row in candidate_rows if row.status == "ACCEPTED"]
    rejected_candidates = [row for row in candidate_rows if row.status == "REJECTED"]
    unmatched_ratio = float(unmatched_faint_pixels) / float(max(1, all_faint_pixels))
    risk_score = 0.0
    risk_score += min(0.55, unmatched_ratio * 0.9)
    if num_lines == 0:
        risk_score += 0.35
    elif line_coverage_percent < 0.75:
        risk_score += 0.20
    if "LOW_LINES" in set(warnings):
        risk_score += 0.15
    risk_score += min(0.2, float(len(accepted_candidates)) * 0.06)
    if overflowed:
        risk_score = max(risk_score, 0.65)
    risk_score = _clamp(risk_score, minimum=0.0, maximum=1.0)
    unstable_candidate_set = overflowed or (
        len(candidate_rows) > 0 and len(accepted_candidates) == 0 and unmatched_ratio >= 0.12
    )
    if unstable_candidate_set or risk_score >= 0.60:
        page_recall_status: PageRecallStatus = "NEEDS_MANUAL_REVIEW"
    elif risk_score >= 0.25 or len(accepted_candidates) > 0:
        page_recall_status = "NEEDS_RESCUE"
    else:
        page_recall_status = "COMPLETE"

    rescue_candidate_quality_score = (
        sum(row.confidence for row in accepted_candidates)
        / float(len(accepted_candidates))
        if accepted_candidates
        else 0.0
    )
    signals_json: dict[str, object] = {
        "algorithm_version": _LAYOUT_RECALL_CHECK_VERSION,
        "threshold_value": threshold,
        "faint_threshold_value": faint_threshold,
        "faint_floor_value": faint_floor,
        "core_dark_threshold_value": core_dark_threshold,
        "faint_component_count": len(components),
        "line_height_outlier_threshold": line_height_outlier_threshold,
        "anomalous_line_merge_count": anomalous_line_merge_count,
        "candidate_count": len(candidate_rows),
        "accepted_candidate_count": len(accepted_candidates),
        "rejected_candidate_count": len(rejected_candidates),
        "unmatched_faint_ratio": round(unmatched_ratio, 6),
        "overflowed_component_scan": overflowed,
        "unstable_candidate_set": unstable_candidate_set,
        "line_count": num_lines,
        "line_coverage_percent": round(line_coverage_percent, 4),
        "rescue_candidate_quality_score": round(rescue_candidate_quality_score, 6),
    }
    return round(risk_score, 6), signals_json, candidate_rows, page_recall_status


def _point_line_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    if start == end:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    numerator = abs(
        (end[1] - start[1]) * point[0]
        - (end[0] - start[0]) * point[1]
        + end[0] * start[1]
        - end[1] * start[0]
    )
    denominator = math.hypot(end[1] - start[1], end[0] - start[0])
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _rdp(points: Sequence[tuple[float, float]], epsilon: float) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return list(points)
    start = points[0]
    end = points[-1]
    max_distance = -1.0
    split_index = -1
    for index in range(1, len(points) - 1):
        distance = _point_line_distance(points[index], start, end)
        if distance > max_distance:
            max_distance = distance
            split_index = index
    if max_distance > epsilon and split_index >= 0:
        left = _rdp(points[: split_index + 1], epsilon)
        right = _rdp(points[split_index:], epsilon)
        return left[:-1] + right
    return [start, end]


def _simplify_polygon(
    points: Sequence[tuple[float, float]],
    *,
    epsilon: float,
) -> list[dict[str, float]]:
    if not points:
        return []
    normalized = list(points)
    if normalized[0] == normalized[-1]:
        normalized = normalized[:-1]
    if len(normalized) <= 3:
        return [{"x": point[0], "y": point[1]} for point in normalized]

    # Process as closed polygon while preserving deterministic ordering.
    wrapped = normalized + [normalized[0]]
    simplified = _rdp(wrapped, epsilon)
    if simplified and simplified[0] == simplified[-1]:
        simplified = simplified[:-1]
    deduped: list[tuple[float, float]] = []
    for point in simplified:
        if deduped and deduped[-1] == point:
            continue
        deduped.append(point)
    if len(deduped) < 3:
        deduped = normalized
    return [{"x": point[0], "y": point[1]} for point in deduped]


def _extract_line_candidates(
    *,
    dark_mask: Sequence[Sequence[bool]],
    width: int,
    height: int,
    params_json: Mapping[str, object],
) -> list[_LineCandidate]:
    row_ratio = _resolve_float_param(
        params_json,
        key="row_text_ratio",
        default=0.012,
        minimum=0.001,
        maximum=0.3,
    )
    row_max_gap = _resolve_int_param(
        params_json,
        key="row_group_max_gap_px",
        default=2,
        minimum=0,
        maximum=16,
    )
    column_gap = _resolve_int_param(
        params_json,
        key="column_group_max_gap_px",
        default=4,
        minimum=0,
        maximum=24,
    )
    column_merge_gap = _resolve_int_param(
        params_json,
        key="column_merge_gap_px",
        default=max(18, int(width * 0.05)),
        minimum=2,
        maximum=max(32, int(width * 0.20)),
    )
    line_padding_x = _resolve_int_param(
        params_json,
        key="line_padding_x_px",
        default=3,
        minimum=0,
        maximum=20,
    )
    line_padding_y = _resolve_int_param(
        params_json,
        key="line_padding_y_px",
        default=2,
        minimum=0,
        maximum=12,
    )

    row_dark_counts = [sum(1 for pixel in row if pixel) for row in dark_mask]
    row_threshold = max(2, int(width * row_ratio))
    active_rows = [index for index, count in enumerate(row_dark_counts) if count >= row_threshold]
    row_groups = _group_sorted_indices(active_rows, max_gap=row_max_gap)
    if not row_groups:
        return []

    min_line_width = max(8, int(round(width * 0.03)))
    min_line_height = max(2, int(round(height * 0.003)))
    candidates: list[_LineCandidate] = []
    for y_start, y_end in row_groups:
        band_height = (y_end - y_start) + 1
        if band_height < min_line_height:
            continue
        column_counts = [0] * width
        for y_index in range(y_start, y_end + 1):
            row = dark_mask[y_index]
            for x_index, has_ink in enumerate(row):
                if has_ink:
                    column_counts[x_index] += 1
        column_threshold = max(1, int(math.ceil(band_height * 0.20)))
        active_columns = [
            index for index, count in enumerate(column_counts) if count >= column_threshold
        ]
        if not active_columns:
            continue
        column_groups = _group_sorted_indices(active_columns, max_gap=column_gap)
        column_groups = _merge_nearby_groups(column_groups, max_gap=column_merge_gap)
        for x_start, x_end in column_groups:
            candidate_box = _clip_box(
                box=_Box(
                    x0=x_start - line_padding_x,
                    y0=y_start - line_padding_y,
                    x1=x_end + 1 + line_padding_x,
                    y1=y_end + 1 + line_padding_y,
                ),
                width=width,
                height=height,
            )
            if candidate_box.width < min_line_width or candidate_box.height < min_line_height:
                continue
            candidates.append(
                _LineCandidate(
                    box=candidate_box,
                    sort_y=float(candidate_box.y0 + candidate_box.y1) / 2.0,
                    sort_x=float(candidate_box.x0 + candidate_box.x1) / 2.0,
                )
            )

    # Remove near-duplicate lines produced by noisy horizontal bands.
    deduped: list[_LineCandidate] = []
    for candidate in sorted(candidates, key=lambda item: (item.sort_y, item.sort_x)):
        duplicate = False
        for existing in deduped:
            intersection = _intersection_area(candidate.box, existing.box)
            if intersection <= 0:
                continue
            min_area = float(max(1, min(candidate.box.area, existing.box.area)))
            if intersection / min_area >= 0.92:
                duplicate = True
                break
        if not duplicate:
            deduped.append(candidate)
    return deduped


def _associate_lines_to_regions(
    *,
    lines: Sequence[_LineCandidate],
    width: int,
    height: int,
    params_json: Mapping[str, object],
) -> list[_RegionCandidate]:
    if not lines:
        return []
    line_heights = [line.box.height for line in lines if line.box.height > 0]
    typical_line_height = int(round(median(line_heights))) if line_heights else 12
    region_vertical_gap = _resolve_int_param(
        params_json,
        key="region_vertical_gap_px",
        default=max(20, typical_line_height * 3),
        minimum=4,
        maximum=max(40, int(height * 0.25)),
    )
    region_horizontal_overlap_threshold = _resolve_float_param(
        params_json,
        key="region_horizontal_overlap_ratio",
        default=0.15,
        minimum=0.0,
        maximum=1.0,
    )
    region_horizontal_distance_threshold = _resolve_int_param(
        params_json,
        key="region_horizontal_distance_px",
        default=max(24, int(width * 0.08)),
        minimum=4,
        maximum=max(40, int(width * 0.25)),
    )
    region_merge_vertical_gap = _resolve_int_param(
        params_json,
        key="region_merge_vertical_gap_px",
        default=max(36, typical_line_height * 6),
        minimum=8,
        maximum=max(60, int(height * 0.35)),
    )

    sorted_indices = sorted(
        range(len(lines)),
        key=lambda index: (lines[index].sort_y, lines[index].sort_x),
    )
    regions: list[_RegionCandidate] = []
    for line_index in sorted_indices:
        line_box = lines[line_index].box
        selected_region_index: int | None = None
        selected_score = -1.0
        for region_index, region in enumerate(regions):
            vertical_gap = _vertical_gap(line_box, region.box)
            if vertical_gap > region_vertical_gap:
                continue
            overlap_ratio = _horizontal_overlap_ratio(line_box, region.box)
            horizontal_distance = _horizontal_distance(line_box, region.box)
            if (
                overlap_ratio < region_horizontal_overlap_threshold
                and horizontal_distance > region_horizontal_distance_threshold
            ):
                continue
            score = overlap_ratio - (
                float(horizontal_distance) / float(max(1, width))
            ) - (float(vertical_gap) / float(max(1, height)))
            if score > selected_score:
                selected_score = score
                selected_region_index = region_index
        if selected_region_index is None:
            regions.append(_RegionCandidate(box=line_box, line_indexes=(line_index,)))
            continue

        region = regions[selected_region_index]
        regions[selected_region_index] = _RegionCandidate(
            box=_union_box(region.box, line_box),
            line_indexes=tuple(sorted((*region.line_indexes, line_index))),
        )

    merged = True
    while merged and len(regions) > 1:
        merged = False
        for left_index in range(len(regions)):
            if merged:
                break
            for right_index in range(left_index + 1, len(regions)):
                left = regions[left_index]
                right = regions[right_index]
                if _vertical_gap(left.box, right.box) > region_merge_vertical_gap:
                    continue
                if _horizontal_overlap_ratio(left.box, right.box) < 0.20:
                    continue
                merged_region = _RegionCandidate(
                    box=_union_box(left.box, right.box),
                    line_indexes=tuple(sorted(set((*left.line_indexes, *right.line_indexes)))),
                )
                regions[left_index] = merged_region
                del regions[right_index]
                merged = True
                break

    region_padding_x = _resolve_int_param(
        params_json,
        key="region_padding_x_px",
        default=8,
        minimum=0,
        maximum=32,
    )
    region_padding_y = _resolve_int_param(
        params_json,
        key="region_padding_y_px",
        default=6,
        minimum=0,
        maximum=24,
    )
    normalized_regions: list[_RegionCandidate] = []
    for region in regions:
        padded = _clip_box(
            box=_Box(
                x0=region.box.x0 - region_padding_x,
                y0=region.box.y0 - region_padding_y,
                x1=region.box.x1 + region_padding_x,
                y1=region.box.y1 + region_padding_y,
            ),
            width=width,
            height=height,
        )
        normalized_regions.append(replace(region, box=padded))
    normalized_regions.sort(
        key=lambda item: (
            (item.box.y0 + item.box.y1) / 2.0,
            (item.box.x0 + item.box.x1) / 2.0,
            item.box.y0,
            item.box.x0,
        )
    )
    return normalized_regions


def _estimate_column_count(regions: Sequence[_RegionCandidate], *, width: int) -> int:
    if not regions:
        return 0
    centers = sorted(
        float(region.box.x0 + region.box.x1) / 2.0 for region in regions if region.box.width > 0
    )
    if not centers:
        return 0
    cluster_threshold = max(24.0, width * 0.20)
    count = 1
    anchor = centers[0]
    for center in centers[1:]:
        if abs(center - anchor) >= cluster_threshold:
            count += 1
            anchor = center
    return count


def _canonical_page_to_payload(page: LayoutCanonicalPage) -> dict[str, object]:
    return {
        "schemaVersion": page.schema_version,
        "runId": page.run_id,
        "pageId": page.page_id,
        "pageIndex": page.page_index,
        "page": {"width": page.page_width, "height": page.page_height},
        "regions": [
            {
                "id": region.region_id,
                "type": region.region_type,
                "polygon": [{"x": point.x, "y": point.y} for point in region.polygon],
                "lineIds": list(region.line_ids),
                "includeInReadingOrder": region.include_in_reading_order,
            }
            for region in page.regions
        ],
        "lines": [
            {
                "id": line.line_id,
                "parentRegionId": line.parent_region_id,
                "polygon": [{"x": point.x, "y": point.y} for point in line.polygon],
                "baseline": (
                    [{"x": point.x, "y": point.y} for point in line.baseline]
                    if line.baseline is not None
                    else None
                ),
            }
            for line in page.lines
        ],
        "readingOrder": [
            {"fromId": edge.from_id, "toId": edge.to_id} for edge in page.reading_order_edges
        ],
        "readingOrderGroups": [
            {
                "id": group.group_id,
                "ordered": group.ordered,
                "regionIds": list(group.region_ids),
            }
            for group in page.reading_order_groups
        ],
        "readingOrderMeta": {
            "schemaVersion": 1,
            "mode": page.reading_order_meta.mode,
            "source": page.reading_order_meta.source,
            "ambiguityScore": page.reading_order_meta.ambiguity_score,
            "columnCertainty": page.reading_order_meta.column_certainty,
            "overlapConflictScore": page.reading_order_meta.overlap_conflict_score,
            "orphanLineCount": page.reading_order_meta.orphan_line_count,
            "nonTextComplexityScore": page.reading_order_meta.non_text_complexity_score,
            "orderWithheld": page.reading_order_meta.order_withheld,
            "versionEtag": page.reading_order_meta.version_etag,
            "layoutVersionId": page.reading_order_meta.layout_version_id,
        },
    }


def segment_layout_page_bytes(
    *,
    page_image_payload: bytes,
    run_id: str,
    page_id: str,
    page_index: int,
    page_width: int,
    page_height: int,
    model_id: str | None,
    profile_id: str | None,
    params_json: Mapping[str, object] | None,
) -> LayoutSegmentationOutcome:
    normalized_params = dict(params_json or {})
    width, height, values = _read_grayscale_image(page_image_payload)
    if width != page_width or height != page_height:
        raise LayoutSegmentationError(
            "Preprocess page dimensions do not match page metadata dimensions."
        )

    threshold_offset = _resolve_int_param(
        normalized_params,
        key="threshold_offset",
        default=0,
        minimum=-48,
        maximum=48,
    )
    otsu = _otsu_threshold(values)
    threshold = max(10, min(245, otsu + threshold_offset))
    dark_mask = _build_dark_mask(values=values, width=width, height=height, threshold=threshold)

    line_candidates = _extract_line_candidates(
        dark_mask=dark_mask,
        width=width,
        height=height,
        params_json=normalized_params,
    )
    regions = _associate_lines_to_regions(
        lines=line_candidates,
        width=width,
        height=height,
        params_json=normalized_params,
    )

    region_entries: list[dict[str, object]] = []
    line_entries: list[dict[str, object]] = []

    line_id_by_index: dict[int, str] = {}
    line_sequence = 1
    for region_index, region in enumerate(regions, start=1):
        region_id = f"r-{page_index + 1:04d}-{region_index:04d}"
        sorted_line_indexes = sorted(
            region.line_indexes,
            key=lambda index: (line_candidates[index].sort_y, line_candidates[index].sort_x),
        )
        region_line_ids: list[str] = []
        for line_index in sorted_line_indexes:
            line_id = line_id_by_index.get(line_index)
            if line_id is None:
                line_id = f"l-{page_index + 1:04d}-{line_sequence:04d}"
                line_sequence += 1
                line_id_by_index[line_index] = line_id
            region_line_ids.append(line_id)

        region_polygon = _simplify_polygon(
            _bbox_to_polygon_points(region.box),
            epsilon=1.0,
        )
        region_entries.append(
            {
                "id": region_id,
                "type": "TEXT",
                "polygon": region_polygon,
                "lineIds": region_line_ids,
            }
        )

    line_candidate_by_id = {
        line_id_by_index[index]: line_candidates[index]
        for index in sorted(line_id_by_index)
    }
    line_boxes_by_id = {
        line_id: candidate.box for line_id, candidate in line_candidate_by_id.items()
    }
    for region in region_entries:
        region_id = str(region["id"])
        region_line_ids = list(region.get("lineIds", []))
        for line_id in region_line_ids:
            line_candidate = line_candidate_by_id.get(line_id)
            if line_candidate is None:
                raise LayoutSegmentationError(
                    "Line-to-region association became inconsistent during serialization."
                )
            line_box = line_candidate.box
            line_polygon = _simplify_polygon(
                _bbox_to_polygon_points(line_box),
                epsilon=0.75,
            )
            baseline_y = float(max(line_box.y0 + 1, line_box.y1 - 1))
            baseline = [
                {"x": float(line_box.x0 + 1), "y": baseline_y},
                {"x": float(max(line_box.x0 + 1, line_box.x1 - 1)), "y": baseline_y},
            ]
            line_entries.append(
                {
                    "id": line_id,
                    "parentRegionId": region_id,
                    "polygon": line_polygon,
                    "baseline": baseline,
                }
            )
    reading_order_inference = infer_reading_order(
        regions=region_entries,
        lines=line_entries,
    )

    raw_payload: dict[str, object] = {
        "schemaVersion": 1,
        "runId": run_id,
        "pageId": page_id,
        "pageIndex": page_index,
        "page": {"width": page_width, "height": page_height},
        "regions": region_entries,
        "lines": line_entries,
        "readingOrder": list(reading_order_inference.edges),
        "readingOrderGroups": reading_order_inference.to_groups_payload(),
        "readingOrderMeta": reading_order_inference.to_meta_payload(),
    }
    canonical_page = build_layout_canonical_page(
        raw_payload,
        expected_run_id=run_id,
        expected_page_id=page_id,
        expected_page_index=page_index,
        expected_page_width=page_width,
        expected_page_height=page_height,
    )
    canonical_payload = _canonical_page_to_payload(canonical_page)

    page_area = float(max(1, page_width * page_height))
    region_boxes = [region.box for region in regions]
    line_boxes = [candidate.box for candidate in line_candidates]
    region_area_sum = float(sum(box.area for box in region_boxes))
    line_area_sum = float(sum(box.area for box in line_boxes))
    region_coverage_percent = round(min(100.0, (region_area_sum / page_area) * 100.0), 4)
    line_coverage_percent = round(min(100.0, (line_area_sum / page_area) * 100.0), 4)
    num_regions = len(canonical_page.regions)
    num_lines = len(canonical_page.lines)
    region_overlap_score = round(_max_overlap_score(region_boxes), 6)
    line_overlap_score = round(_max_overlap_score(line_boxes), 6)
    column_count = _estimate_column_count(regions, width=page_width)

    warnings: set[str] = set()
    low_line_threshold = max(3, int(round(page_height / 350.0)))
    if num_lines < low_line_threshold:
        warnings.add(_LAYOUT_WARNING_LOW_LINES)
    if region_overlap_score > 0.08 or line_overlap_score > 0.20:
        warnings.add(_LAYOUT_WARNING_OVERLAPS)
    if num_regions >= 5 or column_count >= 3:
        warnings.add(_LAYOUT_WARNING_COMPLEX_LAYOUT)

    risk_score, recall_signals_json, rescue_candidates, page_recall_status = (
        _build_recall_assessment(
            run_id=run_id,
            page_id=page_id,
            page_index=page_index,
            page_width=page_width,
            page_height=page_height,
            threshold=threshold,
            values=values,
            line_boxes_by_id=line_boxes_by_id,
            warnings=sorted(warnings),
            num_lines=num_lines,
            line_coverage_percent=line_coverage_percent,
        )
    )

    metrics_json: dict[str, object] = {
        "algorithm_version": _LAYOUT_ALGORITHM_VERSION,
        "num_regions": num_regions,
        "num_lines": num_lines,
        "region_coverage_percent": region_coverage_percent,
        "line_coverage_percent": line_coverage_percent,
        "region_overlap_score": region_overlap_score,
        "line_overlap_score": line_overlap_score,
        "column_count": column_count,
        "threshold_value": threshold,
        "model_id": model_id,
        "profile_id": profile_id,
        "reading_order_mode": reading_order_inference.mode,
        "reading_order_ambiguity_score": round(
            reading_order_inference.reading_order_ambiguity_score, 6
        ),
        "column_certainty": round(reading_order_inference.column_certainty, 6),
        "overlap_conflict_score": round(
            reading_order_inference.overlap_conflict_score, 6
        ),
        "orphan_line_count": reading_order_inference.orphan_line_count,
        "non_text_complexity_score": round(
            reading_order_inference.non_text_complexity_score, 6
        ),
        "reading_order_group_count": len(reading_order_inference.groups),
        "recall_check_version": _LAYOUT_RECALL_CHECK_VERSION,
        "missed_text_risk_score": risk_score,
        "rescue_candidate_count": len(rescue_candidates),
        "accepted_rescue_candidate_count": sum(
            1 for row in rescue_candidates if row.status == "ACCEPTED"
        ),
        "recall_unmatched_faint_ratio": recall_signals_json.get("unmatched_faint_ratio"),
        "rescue_candidate_quality_score": recall_signals_json.get(
            "rescue_candidate_quality_score"
        ),
    }
    return LayoutSegmentationOutcome(
        canonical_page_payload=canonical_payload,
        metrics_json=metrics_json,
        warnings_json=sorted(warnings),
        page_recall_status=page_recall_status,
        recall_check_version=_LAYOUT_RECALL_CHECK_VERSION,
        missed_text_risk_score=risk_score,
        recall_signals_json=recall_signals_json,
        rescue_candidates=rescue_candidates,
    )


__all__ = [
    "LayoutSegmentationError",
    "LayoutRescueCandidateDraft",
    "LayoutSegmentationOutcome",
    "segment_layout_page_bytes",
]
