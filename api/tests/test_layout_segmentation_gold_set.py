from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from app.documents.layout_segmentation import segment_layout_page_bytes


@dataclass(frozen=True)
class _GoldFixture:
    fixture_id: str
    width: int
    height: int
    expected_line_boxes: tuple[tuple[int, int, int, int], ...]
    expected_region_boxes: tuple[tuple[int, int, int, int], ...]
    line_recall_floor: float
    region_overlap_floor: float


def _render_fixture(fixture: _GoldFixture) -> bytes:
    try:
        from PIL import Image, ImageDraw
    except ModuleNotFoundError as error:  # pragma: no cover - dependency guard
        raise RuntimeError("Pillow is required for layout gold-set tests.") from error

    image = Image.new("L", (fixture.width, fixture.height), color=245)
    draw = ImageDraw.Draw(image)
    for box in fixture.expected_line_boxes:
        draw.rectangle(box, fill=18)
    payload = BytesIO()
    image.save(payload, format="PNG", optimize=False, compress_level=9)
    return payload.getvalue()


def _render_fixture_with_faint_regions(
    *,
    width: int,
    height: int,
    line_boxes: tuple[tuple[int, int, int, int], ...],
    faint_boxes: tuple[tuple[int, int, int, int], ...],
) -> bytes:
    try:
        from PIL import Image, ImageDraw
    except ModuleNotFoundError as error:  # pragma: no cover - dependency guard
        raise RuntimeError("Pillow is required for layout gold-set tests.") from error

    image = Image.new("L", (width, height), color=245)
    draw = ImageDraw.Draw(image)
    for box in line_boxes:
        draw.rectangle(box, fill=18)
    for box in faint_boxes:
        draw.rectangle(box, fill=130)
    payload = BytesIO()
    image.save(payload, format="PNG", optimize=False, compress_level=9)
    return payload.getvalue()


def _bbox_from_polygon(polygon: list[dict[str, float]]) -> tuple[float, float, float, float]:
    xs = [float(point["x"]) for point in polygon]
    ys = [float(point["y"]) for point in polygon]
    return min(xs), min(ys), max(xs), max(ys)


def _iou(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> float:
    x0 = max(left[0], right[0])
    y0 = max(left[1], right[1])
    x1 = min(left[2], right[2])
    y1 = min(left[3], right[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    intersection = (x1 - x0) * (y1 - y0)
    left_area = max(1e-9, (left[2] - left[0]) * (left[3] - left[1]))
    right_area = max(1e-9, (right[2] - right[0]) * (right[3] - right[1]))
    union = max(1e-9, left_area + right_area - intersection)
    return intersection / union


def _line_detection_recall(
    expected: tuple[tuple[int, int, int, int], ...],
    predicted: list[tuple[float, float, float, float]],
) -> float:
    if not expected:
        return 1.0
    matched_predicted: set[int] = set()
    matched_expected = 0
    for expected_box in expected:
        expected_as_float = (
            float(expected_box[0]),
            float(expected_box[1]),
            float(expected_box[2]),
            float(expected_box[3]),
        )
        best_index: int | None = None
        best_iou = 0.0
        for index, predicted_box in enumerate(predicted):
            if index in matched_predicted:
                continue
            score = _iou(expected_as_float, predicted_box)
            if score > best_iou:
                best_iou = score
                best_index = index
        if best_index is not None and best_iou >= 0.50:
            matched_expected += 1
            matched_predicted.add(best_index)
    return matched_expected / float(len(expected))


def _region_overlap_score(
    expected: tuple[tuple[int, int, int, int], ...],
    predicted: list[tuple[float, float, float, float]],
) -> float:
    if not expected:
        return 1.0
    if not predicted:
        return 0.0
    scores: list[float] = []
    for expected_box in expected:
        expected_as_float = (
            float(expected_box[0]),
            float(expected_box[1]),
            float(expected_box[2]),
            float(expected_box[3]),
        )
        best = max(_iou(expected_as_float, predicted_box) for predicted_box in predicted)
        scores.append(best)
    return sum(scores) / float(len(scores))


def _fixtures() -> tuple[_GoldFixture, ...]:
    single_column_lines = tuple(
        (80, 100 + (index * 52), 920, 114 + (index * 52)) for index in range(12)
    )
    two_column_lines = tuple(
        line
        for index in range(10)
        for line in (
            (90, 120 + (index * 46), 430, 134 + (index * 46)),
            (570, 120 + (index * 46), 910, 134 + (index * 46)),
        )
    )
    return (
        _GoldFixture(
            fixture_id="single-column-clean",
            width=1000,
            height=1400,
            expected_line_boxes=single_column_lines,
            expected_region_boxes=((72, 90, 928, 700),),
            line_recall_floor=0.90,
            region_overlap_floor=0.72,
        ),
        _GoldFixture(
            fixture_id="two-column-layout",
            width=1000,
            height=1400,
            expected_line_boxes=two_column_lines,
            expected_region_boxes=((80, 110, 440, 560), (560, 110, 920, 560)),
            line_recall_floor=0.82,
            region_overlap_floor=0.65,
        ),
    )


def test_layout_segmentation_structural_gold_set_floors() -> None:
    failures: list[str] = []
    for fixture in _fixtures():
        payload = _render_fixture(fixture)
        outcome = segment_layout_page_bytes(
            page_image_payload=payload,
            run_id=f"gold-{fixture.fixture_id}",
            page_id=f"gold-page-{fixture.fixture_id}",
            page_index=0,
            page_width=fixture.width,
            page_height=fixture.height,
            model_id="layout-rule-v1",
            profile_id="GOLD_SET",
            params_json={},
        )
        regions = [
            _bbox_from_polygon(region["polygon"])
            for region in outcome.canonical_page_payload["regions"]  # type: ignore[index]
        ]
        lines = [
            _bbox_from_polygon(line["polygon"])
            for line in outcome.canonical_page_payload["lines"]  # type: ignore[index]
        ]

        line_recall = _line_detection_recall(fixture.expected_line_boxes, lines)
        region_overlap = _region_overlap_score(fixture.expected_region_boxes, regions)

        if line_recall < fixture.line_recall_floor:
            failures.append(
                f"{fixture.fixture_id}: line detection recall {line_recall:.3f} < {fixture.line_recall_floor:.3f}"
            )
        if region_overlap < fixture.region_overlap_floor:
            failures.append(
                f"{fixture.fixture_id}: region overlap score {region_overlap:.3f} < {fixture.region_overlap_floor:.3f}"
            )

    assert not failures, "\n".join(failures)


def test_layout_recall_gold_set_floor_and_rescue_candidate_quality() -> None:
    base_lines = tuple(
        (90, 120 + (index * 46), 910, 134 + (index * 46)) for index in range(10)
    )
    clean_payload = _render_fixture_with_faint_regions(
        width=1000,
        height=1400,
        line_boxes=base_lines,
        faint_boxes=(),
    )
    clean_outcome = segment_layout_page_bytes(
        page_image_payload=clean_payload,
        run_id="gold-recall-clean",
        page_id="gold-recall-clean-page",
        page_index=0,
        page_width=1000,
        page_height=1400,
        model_id="layout-rule-v1",
        profile_id="GOLD_SET_RECALL",
        params_json={},
    )
    assert clean_outcome.recall_check_version == "layout-recall-v1"
    assert clean_outcome.missed_text_risk_score <= 0.25
    assert clean_outcome.page_recall_status == "COMPLETE"
    assert len(clean_outcome.rescue_candidates) == 0

    faint_payload = _render_fixture_with_faint_regions(
        width=1000,
        height=1400,
        line_boxes=base_lines,
        faint_boxes=((50, 280, 130, 306), (52, 338, 142, 364)),
    )
    faint_outcome = segment_layout_page_bytes(
        page_image_payload=faint_payload,
        run_id="gold-recall-faint",
        page_id="gold-recall-faint-page",
        page_index=0,
        page_width=1000,
        page_height=1400,
        model_id="layout-rule-v1",
        profile_id="GOLD_SET_RECALL",
        params_json={},
    )
    assert faint_outcome.missed_text_risk_score >= 0.25
    assert faint_outcome.page_recall_status in {"NEEDS_RESCUE", "NEEDS_MANUAL_REVIEW"}
    assert any(candidate.status == "ACCEPTED" for candidate in faint_outcome.rescue_candidates)
    assert all(
        isinstance(candidate.geometry_json.get("bbox"), dict)
        for candidate in faint_outcome.rescue_candidates
    )
