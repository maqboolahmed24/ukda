from __future__ import annotations

from io import BytesIO

import pytest

from app.documents.layout_contract import build_layout_canonical_page
from app.documents.layout_segmentation import segment_layout_page_bytes


def _render_fixture(
    *,
    width: int,
    height: int,
    line_boxes: list[tuple[int, int, int, int]],
) -> bytes:
    try:
        from PIL import Image, ImageDraw
    except ModuleNotFoundError as error:  # pragma: no cover - dependency guard
        raise RuntimeError("Pillow is required for layout segmentation tests.") from error

    image = Image.new("L", (width, height), color=245)
    draw = ImageDraw.Draw(image)
    for x0, y0, x1, y1 in line_boxes:
        draw.rectangle((x0, y0, x1, y1), fill=18)
    payload = BytesIO()
    image.save(payload, format="PNG", optimize=False, compress_level=9)
    return payload.getvalue()


def _two_column_line_boxes() -> list[tuple[int, int, int, int]]:
    boxes: list[tuple[int, int, int, int]] = []
    for index in range(10):
        y0 = 80 + (index * 44)
        y1 = y0 + 14
        boxes.append((80, y0, 430, y1))
        boxes.append((560, y0, 920, y1))
    return boxes


def test_segmentation_generates_valid_polygons_and_required_metrics() -> None:
    payload = _render_fixture(
        width=1000,
        height=1400,
        line_boxes=_two_column_line_boxes(),
    )

    outcome = segment_layout_page_bytes(
        page_image_payload=payload,
        run_id="layout-run-1",
        page_id="page-1",
        page_index=0,
        page_width=1000,
        page_height=1400,
        model_id="layout-rule-v1",
        profile_id="DEFAULT",
        params_json={},
    )

    canonical = build_layout_canonical_page(
        outcome.canonical_page_payload,
        expected_run_id="layout-run-1",
        expected_page_id="page-1",
        expected_page_index=0,
        expected_page_width=1000,
        expected_page_height=1400,
    )
    assert len(canonical.regions) >= 2
    assert len(canonical.lines) >= 12
    assert outcome.page_recall_status in {
        "COMPLETE",
        "NEEDS_MANUAL_REVIEW",
        "NEEDS_RESCUE",
    }
    assert outcome.recall_check_version == "layout-recall-v1"
    assert 0 <= outcome.missed_text_risk_score <= 1
    assert isinstance(outcome.recall_signals_json, dict)
    assert "candidate_count" in outcome.recall_signals_json

    assert "num_regions" in outcome.metrics_json
    assert "num_lines" in outcome.metrics_json
    assert "region_coverage_percent" in outcome.metrics_json
    assert "line_coverage_percent" in outcome.metrics_json
    assert "missed_text_risk_score" in outcome.metrics_json
    assert "rescue_candidate_count" in outcome.metrics_json
    assert set(outcome.warnings_json).issubset(
        {"LOW_LINES", "OVERLAPS", "COMPLEX_LAYOUT"}
    )


def test_segmentation_is_deterministic_for_same_input() -> None:
    payload = _render_fixture(
        width=1000,
        height=1400,
        line_boxes=_two_column_line_boxes(),
    )

    first = segment_layout_page_bytes(
        page_image_payload=payload,
        run_id="layout-run-2",
        page_id="page-2",
        page_index=1,
        page_width=1000,
        page_height=1400,
        model_id="layout-rule-v1",
        profile_id="DEFAULT",
        params_json={},
    )
    second = segment_layout_page_bytes(
        page_image_payload=payload,
        run_id="layout-run-2",
        page_id="page-2",
        page_index=1,
        page_width=1000,
        page_height=1400,
        model_id="layout-rule-v1",
        profile_id="DEFAULT",
        params_json={},
    )

    assert first == second
    first_regions = [str(region["id"]) for region in first.canonical_page_payload["regions"]]
    second_regions = [str(region["id"]) for region in second.canonical_page_payload["regions"]]
    assert first_regions == second_regions
    first_lines = [str(line["id"]) for line in first.canonical_page_payload["lines"]]
    second_lines = [str(line["id"]) for line in second.canonical_page_payload["lines"]]
    assert first_lines == second_lines


def test_segmentation_marks_sparse_page_for_rescue_and_low_lines_warning() -> None:
    payload = _render_fixture(
        width=1000,
        height=1400,
        line_boxes=[(420, 680, 560, 688)],
    )

    outcome = segment_layout_page_bytes(
        page_image_payload=payload,
        run_id="layout-run-3",
        page_id="page-3",
        page_index=2,
        page_width=1000,
        page_height=1400,
        model_id="layout-rule-v1",
        profile_id="DEFAULT",
        params_json={},
    )

    assert outcome.page_recall_status in {"NEEDS_RESCUE", "NEEDS_MANUAL_REVIEW"}
    assert outcome.page_recall_status != "COMPLETE"
    assert outcome.recall_signals_json["candidate_count"] >= 0
    assert "LOW_LINES" in outcome.warnings_json


def test_segmentation_has_no_network_egress_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    import socket

    def _blocked(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("Unexpected network call from layout segmentation.")

    monkeypatch.setattr(socket, "create_connection", _blocked)
    payload = _render_fixture(
        width=1000,
        height=1400,
        line_boxes=_two_column_line_boxes(),
    )
    outcome = segment_layout_page_bytes(
        page_image_payload=payload,
        run_id="layout-run-4",
        page_id="page-4",
        page_index=3,
        page_width=1000,
        page_height=1400,
        model_id="layout-rule-v1",
        profile_id="DEFAULT",
        params_json={},
    )
    assert outcome.metrics_json["num_lines"] > 0
