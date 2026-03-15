from __future__ import annotations

import pytest

from app.documents.redaction_geometry import (
    RedactionGeometryValidationError,
    build_finding_geometry_payload,
    normalize_area_mask_geometry,
    normalize_token_refs_and_bbox_refs,
)


def test_normalize_token_refs_rejects_unknown_token_ids() -> None:
    with pytest.raises(RedactionGeometryValidationError) as error:
        normalize_token_refs_and_bbox_refs(
            token_refs_json=[
                {
                    "tokenId": "tok-missing",
                    "bboxJson": {"x": 10, "y": 15, "w": 20, "h": 12},
                }
            ],
            bbox_refs={},
            page_width=200,
            page_height=300,
            valid_token_ids={"tok-1", "tok-2"},
        )
    assert "unknown tokenId" in str(error.value)


def test_normalize_token_refs_rejects_out_of_bounds_geometry() -> None:
    with pytest.raises(RedactionGeometryValidationError) as error:
        normalize_token_refs_and_bbox_refs(
            token_refs_json=[
                {
                    "tokenId": "tok-1",
                    "bboxJson": {"x": 190, "y": 20, "w": 20, "h": 10},
                }
            ],
            bbox_refs={},
            page_width=200,
            page_height=300,
            valid_token_ids={"tok-1"},
        )
    assert "x+width" in str(error.value)


def test_normalize_area_mask_geometry_canonicalizes_bbox_arrays() -> None:
    normalized = normalize_area_mask_geometry(
        {"bbox": [40, 100, 220, 140]},
        page_width=1000,
        page_height=1400,
    )
    assert normalized == {
        "bbox": {
            "x": 40.0,
            "y": 100.0,
            "width": 180.0,
            "height": 40.0,
        }
    }


def test_build_finding_geometry_payload_marks_area_mask_backed_findings() -> None:
    payload = build_finding_geometry_payload(
        token_refs_json=[
            {
                "tokenId": "tok-1",
                "lineId": "line-9",
                "bboxJson": {"x": 15, "y": 20, "width": 18, "height": 10},
            }
        ],
        bbox_refs={"lineId": "line-9"},
        area_mask_geometry_json={"bbox": {"x": 10, "y": 18, "width": 40, "height": 18}},
    )
    assert payload["anchorKind"] == "AREA_MASK_BACKED"
    assert payload["tokenIds"] == ["tok-1"]
    assert any(box["source"] == "AREA_MASK" for box in payload["boxes"])
