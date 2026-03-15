from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Literal, Mapping, Sequence


class RedactionGeometryValidationError(ValueError):
    """Raised when redaction geometry is malformed or unsafe."""


RedactionAnchorKind = Literal["TOKEN_LINKED", "AREA_MASK_BACKED", "BBOX_ONLY", "NONE"]
RedactionGeometrySource = Literal["TOKEN_REF", "BBOX_REF", "AREA_MASK"]


@dataclass(frozen=True)
class NormalizedBox:
    x: float
    y: float
    width: float
    height: float

    def as_dict(self) -> dict[str, float]:
        return {
            "x": round(self.x, 4),
            "y": round(self.y, 4),
            "width": round(self.width, 4),
            "height": round(self.height, 4),
        }

    def key(self) -> tuple[float, float, float, float]:
        return (
            round(self.x, 4),
            round(self.y, 4),
            round(self.width, 4),
            round(self.height, 4),
        )


@dataclass(frozen=True)
class NormalizedPoint:
    x: float
    y: float

    def as_dict(self) -> dict[str, float]:
        return {"x": round(self.x, 4), "y": round(self.y, 4)}


def _as_finite_number(value: object, *, field_name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise RedactionGeometryValidationError(f"{field_name} must be numeric.")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise RedactionGeometryValidationError(f"{field_name} must be finite.")
    return numeric


def _bounded(
    value: float,
    *,
    minimum: float,
    maximum: float,
    field_name: str,
) -> float:
    if value < minimum or value > maximum:
        raise RedactionGeometryValidationError(
            f"{field_name} must be between {minimum} and {maximum}."
        )
    return value


def _normalize_point(
    value: object,
    *,
    field_name: str,
    page_width: float | None,
    page_height: float | None,
) -> NormalizedPoint:
    if isinstance(value, Mapping):
        raw_x = value.get("x")
        raw_y = value.get("y")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) == 2:
        raw_x = value[0]
        raw_y = value[1]
    else:
        raise RedactionGeometryValidationError(
            f"{field_name} must be a point object or [x, y] pair."
        )
    x = _as_finite_number(raw_x, field_name=f"{field_name}.x")
    y = _as_finite_number(raw_y, field_name=f"{field_name}.y")
    if page_width is not None:
        x = _bounded(x, minimum=0.0, maximum=page_width, field_name=f"{field_name}.x")
    if page_height is not None:
        y = _bounded(y, minimum=0.0, maximum=page_height, field_name=f"{field_name}.y")
    return NormalizedPoint(x=x, y=y)


def normalize_box(
    value: object,
    *,
    field_name: str,
    page_width: float | None,
    page_height: float | None,
) -> NormalizedBox:
    if isinstance(value, Mapping):
        raw_x = value.get("x")
        raw_y = value.get("y")
        raw_width = value.get("width", value.get("w"))
        raw_height = value.get("height", value.get("h"))
        x = _as_finite_number(raw_x, field_name=f"{field_name}.x")
        y = _as_finite_number(raw_y, field_name=f"{field_name}.y")
        width = _as_finite_number(raw_width, field_name=f"{field_name}.width")
        height = _as_finite_number(raw_height, field_name=f"{field_name}.height")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) == 4:
        x1 = _as_finite_number(value[0], field_name=f"{field_name}[0]")
        y1 = _as_finite_number(value[1], field_name=f"{field_name}[1]")
        x2 = _as_finite_number(value[2], field_name=f"{field_name}[2]")
        y2 = _as_finite_number(value[3], field_name=f"{field_name}[3]")
        width = x2 - x1
        height = y2 - y1
        x = x1
        y = y1
    else:
        raise RedactionGeometryValidationError(
            f"{field_name} must be a bbox object or [x1, y1, x2, y2] array."
        )
    if width <= 0.0:
        raise RedactionGeometryValidationError(f"{field_name}.width must be greater than zero.")
    if height <= 0.0:
        raise RedactionGeometryValidationError(f"{field_name}.height must be greater than zero.")
    if page_width is not None:
        x = _bounded(x, minimum=0.0, maximum=page_width, field_name=f"{field_name}.x")
        _ = _bounded(
            x + width,
            minimum=0.0,
            maximum=page_width,
            field_name=f"{field_name}.x+width",
        )
    if page_height is not None:
        y = _bounded(y, minimum=0.0, maximum=page_height, field_name=f"{field_name}.y")
        _ = _bounded(
            y + height,
            minimum=0.0,
            maximum=page_height,
            field_name=f"{field_name}.y+height",
        )
    return NormalizedBox(x=x, y=y, width=width, height=height)


def normalize_polygon(
    value: object,
    *,
    field_name: str,
    page_width: float | None,
    page_height: float | None,
) -> dict[str, object]:
    points_value: object
    if isinstance(value, Mapping):
        points_value = value.get("points")
    else:
        points_value = value
    if not isinstance(points_value, Sequence) or isinstance(points_value, (str, bytes)):
        raise RedactionGeometryValidationError(f"{field_name}.points must be an array.")
    if len(points_value) < 3:
        raise RedactionGeometryValidationError(
            f"{field_name}.points must include at least three points."
        )
    normalized: list[dict[str, float]] = []
    for index, point in enumerate(points_value):
        normalized_point = _normalize_point(
            point,
            field_name=f"{field_name}.points[{index}]",
            page_width=page_width,
            page_height=page_height,
        )
        normalized.append(normalized_point.as_dict())
    unique_points = {
        (point["x"], point["y"])
        for point in normalized
    }
    if len(unique_points) < 3:
        raise RedactionGeometryValidationError(
            f"{field_name}.points must contain at least three distinct points."
        )
    return {"points": normalized}


def normalize_area_mask_geometry(
    geometry_json: Mapping[str, object],
    *,
    page_width: int,
    page_height: int,
) -> dict[str, object]:
    if page_width <= 0 or page_height <= 0:
        raise RedactionGeometryValidationError("Page dimensions must be positive.")
    normalized: dict[str, object] = {}
    if "bbox" in geometry_json:
        normalized["bbox"] = normalize_box(
            geometry_json["bbox"],
            field_name="geometryJson.bbox",
            page_width=float(page_width),
            page_height=float(page_height),
        ).as_dict()
    if "polygon" in geometry_json:
        normalized["polygon"] = normalize_polygon(
            geometry_json["polygon"],
            field_name="geometryJson.polygon",
            page_width=float(page_width),
            page_height=float(page_height),
        )
    if not normalized:
        raise RedactionGeometryValidationError(
            "geometryJson must include a bbox and/or polygon."
        )
    return normalized


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def normalize_token_refs_and_bbox_refs(
    *,
    token_refs_json: Sequence[Mapping[str, object]] | None,
    bbox_refs: Mapping[str, object] | None,
    page_width: int,
    page_height: int,
    valid_token_ids: set[str] | None,
) -> tuple[list[dict[str, object]] | None, dict[str, object]]:
    if page_width <= 0 or page_height <= 0:
        raise RedactionGeometryValidationError("Page dimensions must be positive.")
    normalized_token_refs: list[dict[str, object]] = []
    by_token_id: dict[str, dict[str, object]] = {}
    if token_refs_json is not None:
        for index, ref in enumerate(token_refs_json):
            token_id = str(ref.get("tokenId") or "").strip()
            if not token_id:
                raise RedactionGeometryValidationError(
                    f"tokenRefsJson[{index}].tokenId is required."
                )
            if valid_token_ids is not None and token_id not in valid_token_ids:
                raise RedactionGeometryValidationError(
                    f"tokenRefsJson[{index}] references unknown tokenId '{token_id}'."
                )
            normalized_ref: dict[str, object] = {"tokenId": token_id}
            if isinstance(ref.get("tokenIndex"), int):
                normalized_ref["tokenIndex"] = int(ref["tokenIndex"])
            source_ref_id = str(ref.get("sourceRefId") or "").strip()
            if source_ref_id:
                normalized_ref["sourceRefId"] = source_ref_id
            line_id = str(ref.get("lineId") or "").strip()
            if line_id:
                normalized_ref["lineId"] = line_id
            if ref.get("bboxJson") is not None:
                normalized_ref["bboxJson"] = normalize_box(
                    ref["bboxJson"],
                    field_name=f"tokenRefsJson[{index}].bboxJson",
                    page_width=float(page_width),
                    page_height=float(page_height),
                ).as_dict()
            if ref.get("polygonJson") is not None:
                normalized_ref["polygonJson"] = normalize_polygon(
                    ref["polygonJson"],
                    field_name=f"tokenRefsJson[{index}].polygonJson",
                    page_width=float(page_width),
                    page_height=float(page_height),
                )
            existing = by_token_id.get(token_id)
            if existing is not None:
                if _canonical_json(existing) != _canonical_json(normalized_ref):
                    raise RedactionGeometryValidationError(
                        "Conflicting duplicate token geometry references are not allowed."
                    )
                continue
            by_token_id[token_id] = normalized_ref
            normalized_token_refs.append(normalized_ref)

    normalized_bbox_refs: dict[str, object] = {}
    bbox_mapping = bbox_refs if isinstance(bbox_refs, Mapping) else {}
    line_id = str(bbox_mapping.get("lineId") or "").strip()
    if line_id:
        normalized_bbox_refs["lineId"] = line_id
    if bbox_mapping.get("bbox") is not None:
        normalized_bbox_refs["bbox"] = normalize_box(
            bbox_mapping["bbox"],
            field_name="bboxRefs.bbox",
            page_width=float(page_width),
            page_height=float(page_height),
        ).as_dict()
    if bbox_mapping.get("polygon") is not None:
        normalized_bbox_refs["polygon"] = normalize_polygon(
            bbox_mapping["polygon"],
            field_name="bboxRefs.polygon",
            page_width=float(page_width),
            page_height=float(page_height),
        )
    token_bbox_values = bbox_mapping.get("tokenBboxes")
    token_bboxes: list[dict[str, float]] = []
    if isinstance(token_bbox_values, Sequence) and not isinstance(token_bbox_values, (str, bytes)):
        for index, raw_box in enumerate(token_bbox_values):
            token_bboxes.append(
                normalize_box(
                    raw_box,
                    field_name=f"bboxRefs.tokenBboxes[{index}]",
                    page_width=float(page_width),
                    page_height=float(page_height),
                ).as_dict()
            )
    if token_bboxes:
        normalized_bbox_refs["tokenBboxes"] = token_bboxes

    token_ref_boxes = [
        dict(ref["bboxJson"])
        for ref in normalized_token_refs
        if isinstance(ref.get("bboxJson"), Mapping)
    ]
    if token_ref_boxes and token_bboxes:
        left = sorted(
            (
                (
                    round(float(box["x"]), 4),
                    round(float(box["y"]), 4),
                    round(float(box["width"]), 4),
                    round(float(box["height"]), 4),
                )
                for box in token_ref_boxes
            )
        )
        right = sorted(
            (
                (
                    round(float(box["x"]), 4),
                    round(float(box["y"]), 4),
                    round(float(box["width"]), 4),
                    round(float(box["height"]), 4),
                )
                for box in token_bboxes
            )
        )
        if left != right:
            raise RedactionGeometryValidationError(
                "bboxRefs.tokenBboxes conflicts with tokenRefsJson bbox geometry."
            )
    elif token_ref_boxes and not token_bboxes:
        normalized_bbox_refs["tokenBboxes"] = token_ref_boxes

    return (
        (normalized_token_refs if normalized_token_refs else None),
        normalized_bbox_refs,
    )


def build_finding_geometry_payload(
    *,
    token_refs_json: Sequence[Mapping[str, object]] | None,
    bbox_refs: Mapping[str, object] | None,
    area_mask_geometry_json: Mapping[str, object] | None,
) -> dict[str, object]:
    boxes: list[dict[str, object]] = []
    polygons: list[dict[str, object]] = []
    token_ids: list[str] = []
    line_id: str | None = None

    if token_refs_json is not None:
        for ref in token_refs_json:
            token_id = str(ref.get("tokenId") or "").strip()
            if token_id and token_id not in token_ids:
                token_ids.append(token_id)
            if line_id is None:
                candidate_line_id = str(ref.get("lineId") or "").strip()
                if candidate_line_id:
                    line_id = candidate_line_id
            bbox_value = ref.get("bboxJson")
            if isinstance(bbox_value, Mapping):
                try:
                    normalized = normalize_box(
                        bbox_value,
                        field_name="tokenRefsJson.bboxJson",
                        page_width=None,
                        page_height=None,
                    ).as_dict()
                except RedactionGeometryValidationError:
                    normalized = {}
                if normalized:
                    boxes.append({**normalized, "source": "TOKEN_REF"})
            polygon_value = ref.get("polygonJson")
            if polygon_value is not None:
                try:
                    normalized_polygon = normalize_polygon(
                        polygon_value,
                        field_name="tokenRefsJson.polygonJson",
                        page_width=None,
                        page_height=None,
                    )
                except RedactionGeometryValidationError:
                    normalized_polygon = {}
                if normalized_polygon:
                    polygons.append(
                        {
                            "points": normalized_polygon["points"],
                            "source": "TOKEN_REF",
                        }
                    )

    bbox_mapping = bbox_refs if isinstance(bbox_refs, Mapping) else {}
    if line_id is None:
        candidate_line_id = str(bbox_mapping.get("lineId") or "").strip()
        if candidate_line_id:
            line_id = candidate_line_id
    if isinstance(bbox_mapping.get("tokenBboxes"), Sequence) and not isinstance(
        bbox_mapping.get("tokenBboxes"), (str, bytes)
    ):
        for raw_box in bbox_mapping["tokenBboxes"]:  # type: ignore[index]
            if not isinstance(raw_box, Mapping):
                continue
            try:
                normalized = normalize_box(
                    raw_box,
                    field_name="bboxRefs.tokenBboxes",
                    page_width=None,
                    page_height=None,
                ).as_dict()
            except RedactionGeometryValidationError:
                continue
            boxes.append({**normalized, "source": "BBOX_REF"})
    if bbox_mapping.get("bbox") is not None:
        try:
            normalized_bbox = normalize_box(
                bbox_mapping["bbox"],
                field_name="bboxRefs.bbox",
                page_width=None,
                page_height=None,
            ).as_dict()
        except RedactionGeometryValidationError:
            normalized_bbox = {}
        if normalized_bbox:
            boxes.append({**normalized_bbox, "source": "BBOX_REF"})
    if bbox_mapping.get("polygon") is not None:
        try:
            normalized_polygon = normalize_polygon(
                bbox_mapping["polygon"],
                field_name="bboxRefs.polygon",
                page_width=None,
                page_height=None,
            )
        except RedactionGeometryValidationError:
            normalized_polygon = {}
        if normalized_polygon:
            polygons.append(
                {
                    "points": normalized_polygon["points"],
                    "source": "BBOX_REF",
                }
            )

    if isinstance(area_mask_geometry_json, Mapping):
        bbox_value = area_mask_geometry_json.get("bbox")
        if bbox_value is not None:
            try:
                normalized_bbox = normalize_box(
                    bbox_value,
                    field_name="areaMask.geometryJson.bbox",
                    page_width=None,
                    page_height=None,
                ).as_dict()
            except RedactionGeometryValidationError:
                normalized_bbox = {}
            if normalized_bbox:
                boxes.append({**normalized_bbox, "source": "AREA_MASK"})
        polygon_value = area_mask_geometry_json.get("polygon")
        if polygon_value is not None:
            try:
                normalized_polygon = normalize_polygon(
                    polygon_value,
                    field_name="areaMask.geometryJson.polygon",
                    page_width=None,
                    page_height=None,
                )
            except RedactionGeometryValidationError:
                normalized_polygon = {}
            if normalized_polygon:
                polygons.append(
                    {
                        "points": normalized_polygon["points"],
                        "source": "AREA_MASK",
                    }
                )

    anchor_kind: RedactionAnchorKind
    if area_mask_geometry_json is not None:
        anchor_kind = "AREA_MASK_BACKED"
    elif token_ids:
        anchor_kind = "TOKEN_LINKED"
    elif boxes or polygons or line_id:
        anchor_kind = "BBOX_ONLY"
    else:
        anchor_kind = "NONE"

    deduped_boxes: list[dict[str, object]] = []
    seen_box_keys: set[tuple[float, float, float, float, str]] = set()
    for box in boxes:
        source = str(box.get("source") or "BBOX_REF")
        key = (
            round(float(box["x"]), 4),
            round(float(box["y"]), 4),
            round(float(box["width"]), 4),
            round(float(box["height"]), 4),
            source,
        )
        if key in seen_box_keys:
            continue
        seen_box_keys.add(key)
        deduped_boxes.append(
            {
                "x": key[0],
                "y": key[1],
                "width": key[2],
                "height": key[3],
                "source": source,
            }
        )

    deduped_polygons: list[dict[str, object]] = []
    seen_polygon_keys: set[str] = set()
    for polygon in polygons:
        if not isinstance(polygon.get("points"), Sequence):
            continue
        source = str(polygon.get("source") or "BBOX_REF")
        payload = {
            "points": polygon["points"],
            "source": source,
        }
        key = _canonical_json(payload)
        if key in seen_polygon_keys:
            continue
        seen_polygon_keys.add(key)
        deduped_polygons.append(payload)

    return {
        "anchorKind": anchor_kind,
        "lineId": line_id,
        "tokenIds": token_ids,
        "boxes": deduped_boxes,
        "polygons": deduped_polygons,
    }
