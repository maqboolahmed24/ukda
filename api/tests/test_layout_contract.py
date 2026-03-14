from __future__ import annotations

import hashlib

import pytest

from app.documents.layout_contract import (
    LayoutContractValidationError,
    build_layout_canonical_page,
    canonical_json_bytes,
    derive_layout_overlay,
    parse_layout_pagexml,
    serialize_layout_pagexml,
    validate_layout_overlay_payload,
)


def _canonical_payload() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "runId": "layout-run-1",
        "pageId": "page-1",
        "pageIndex": 0,
        "page": {"width": 1000, "height": 1400},
        "regions": [
            {
                "id": "region-1",
                "type": "TEXT",
                "polygon": [[20, 40], [980, 40], [980, 320], [20, 320]],
                "lineIds": ["line-1"],
            }
        ],
        "lines": [
            {
                "id": "line-1",
                "parentRegionId": "region-1",
                "polygon": [[40, 80], [960, 80], [960, 120], [40, 120]],
                "baseline": [[48, 112], [950, 112]],
            }
        ],
        "readingOrder": [{"fromId": "region-1", "toId": "line-1"}],
        "readingOrderGroups": [
            {"id": "g-0001", "ordered": True, "regionIds": ["region-1"]}
        ],
        "readingOrderMeta": {
            "schemaVersion": 1,
            "mode": "ORDERED",
            "source": "AUTO_INFERRED",
            "ambiguityScore": 0.1,
            "columnCertainty": 0.9,
            "overlapConflictScore": 0.0,
            "orphanLineCount": 0,
            "nonTextComplexityScore": 0.0,
            "orderWithheld": False,
            "versionEtag": "layout-etag-1",
            "layoutVersionId": "layout-version-1",
        },
    }


def test_pagexml_round_trip_and_overlay_derivation_are_stable() -> None:
    page = build_layout_canonical_page(_canonical_payload())
    pagexml_first = serialize_layout_pagexml(page)
    parsed = parse_layout_pagexml(pagexml_first)
    pagexml_second = serialize_layout_pagexml(parsed)

    assert pagexml_first == pagexml_second
    assert hashlib.sha256(pagexml_first).hexdigest() == hashlib.sha256(pagexml_second).hexdigest()

    overlay = validate_layout_overlay_payload(
        derive_layout_overlay(parsed),
        expected_run_id="layout-run-1",
        expected_page_id="page-1",
        expected_page_index=0,
    )
    overlay_bytes = canonical_json_bytes(overlay)
    assert hashlib.sha256(overlay_bytes).hexdigest()
    assert overlay["schemaVersion"] == 1
    assert overlay["runId"] == "layout-run-1"
    assert overlay["pageId"] == "page-1"
    assert len(overlay["elements"]) == 2
    assert overlay["readingOrderGroups"][0]["id"] == "g-0001"
    assert overlay["readingOrderMeta"]["mode"] == "ORDERED"
    assert overlay["readingOrderMeta"]["versionEtag"] == "layout-etag-1"


def test_geometry_validation_rejects_out_of_bounds_polygon() -> None:
    payload = _canonical_payload()
    payload["regions"] = [
        {
            "id": "region-1",
            "type": "TEXT",
            "polygon": [[20, 40], [1800, 40], [980, 320], [20, 320]],
            "lineIds": ["line-1"],
        }
    ]
    with pytest.raises(LayoutContractValidationError):
        build_layout_canonical_page(payload)


def test_geometry_validation_rejects_nan_coordinates() -> None:
    payload = _canonical_payload()
    payload["lines"] = [
        {
            "id": "line-1",
            "parentRegionId": "region-1",
            "polygon": [[40, 80], [960, 80], [960, float("nan")], [40, 120]],
            "baseline": [[48, 112], [950, 112]],
        }
    ]
    with pytest.raises(LayoutContractValidationError):
        build_layout_canonical_page(payload)


def test_polygon_normalization_is_deterministic() -> None:
    payload = _canonical_payload()
    payload["regions"] = [
        {
            "id": "region-1",
            "type": "TEXT",
            "polygon": [[20, 40], [200, 40], [980, 40], [980, 320], [20, 320], [20, 40]],
            "lineIds": ["line-1"],
        }
    ]
    page = build_layout_canonical_page(payload)
    assert len(page.regions[0].polygon) == 4
    assert page.regions[0].polygon[0].x == 20
    assert page.regions[0].polygon[0].y == 40


def test_reading_order_groups_reject_duplicate_region_assignment() -> None:
    payload = _canonical_payload()
    payload["readingOrderGroups"] = [
        {"id": "g-0001", "ordered": True, "regionIds": ["region-1"]},
        {"id": "g-0002", "ordered": True, "regionIds": ["region-1"]},
    ]
    with pytest.raises(LayoutContractValidationError):
        build_layout_canonical_page(payload)
