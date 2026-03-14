from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Mapping, Sequence

PAGE_XML_NAMESPACE = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15"
PAGE_XML_NS = {"pc": PAGE_XML_NAMESPACE}
_COLLINEAR_EPSILON = 1e-6


class LayoutContractValidationError(ValueError):
    """Canonical layout payload is structurally invalid."""


@dataclass(frozen=True)
class LayoutPoint:
    x: float
    y: float


@dataclass(frozen=True)
class LayoutRegion:
    region_id: str
    region_type: str
    polygon: tuple[LayoutPoint, ...]
    line_ids: tuple[str, ...]
    include_in_reading_order: bool = True


@dataclass(frozen=True)
class LayoutLine:
    line_id: str
    parent_region_id: str
    polygon: tuple[LayoutPoint, ...]
    baseline: tuple[LayoutPoint, ...] | None


@dataclass(frozen=True)
class LayoutReadingOrderEdge:
    from_id: str
    to_id: str


@dataclass(frozen=True)
class LayoutReadingOrderGroup:
    group_id: str
    ordered: bool
    region_ids: tuple[str, ...]


@dataclass(frozen=True)
class LayoutReadingOrderMeta:
    mode: str
    source: str
    ambiguity_score: float
    column_certainty: float
    overlap_conflict_score: float
    orphan_line_count: int
    non_text_complexity_score: float
    order_withheld: bool
    version_etag: str | None = None
    layout_version_id: str | None = None


@dataclass(frozen=True)
class LayoutCanonicalPage:
    schema_version: int
    run_id: str
    page_id: str
    page_index: int
    page_width: int
    page_height: int
    regions: tuple[LayoutRegion, ...]
    lines: tuple[LayoutLine, ...]
    reading_order_edges: tuple[LayoutReadingOrderEdge, ...]
    reading_order_groups: tuple[LayoutReadingOrderGroup, ...]
    reading_order_meta: LayoutReadingOrderMeta


def canonical_json_bytes(payload: Mapping[str, object]) -> bytes:
    serialized = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return serialized + b"\n"


def _normalize_identifier(value: object, *, field_name: str, max_length: int = 200) -> str:
    if not isinstance(value, str):
        raise LayoutContractValidationError(f"{field_name} must be a string.")
    normalized = value.strip()
    if not normalized:
        raise LayoutContractValidationError(f"{field_name} is required.")
    if len(normalized) > max_length:
        raise LayoutContractValidationError(
            f"{field_name} must be {max_length} characters or fewer."
        )
    return normalized


def _normalize_number(value: object, *, field_name: str) -> float:
    if not isinstance(value, (int, float)):
        raise LayoutContractValidationError(f"{field_name} must be numeric.")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise LayoutContractValidationError(f"{field_name} must be finite.")
    return numeric


def _normalize_int(value: object, *, field_name: str, minimum: int = 0) -> int:
    if not isinstance(value, int):
        raise LayoutContractValidationError(f"{field_name} must be an integer.")
    if value < minimum:
        raise LayoutContractValidationError(f"{field_name} must be >= {minimum}.")
    return int(value)


def _normalize_bool(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise LayoutContractValidationError(f"{field_name} must be boolean.")
    return value


def _normalize_point(
    value: object,
    *,
    field_name: str,
    page_width: int,
    page_height: int,
) -> LayoutPoint:
    if isinstance(value, Mapping):
        raw_x = value.get("x")
        raw_y = value.get("y")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) == 2:
        raw_x = value[0]
        raw_y = value[1]
    else:
        raise LayoutContractValidationError(
            f"{field_name} must be a point mapping with x/y or a [x, y] pair."
        )

    x = round(_normalize_number(raw_x, field_name=f"{field_name}.x"), 4)
    y = round(_normalize_number(raw_y, field_name=f"{field_name}.y"), 4)
    if x < 0 or x > page_width:
        raise LayoutContractValidationError(
            f"{field_name}.x must be between 0 and page width ({page_width})."
        )
    if y < 0 or y > page_height:
        raise LayoutContractValidationError(
            f"{field_name}.y must be between 0 and page height ({page_height})."
        )
    return LayoutPoint(x=x, y=y)


def _points_equal(left: LayoutPoint, right: LayoutPoint) -> bool:
    return left.x == right.x and left.y == right.y


def _is_collinear(a: LayoutPoint, b: LayoutPoint, c: LayoutPoint) -> bool:
    area = (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)
    return abs(area) <= _COLLINEAR_EPSILON


def _normalize_polyline(
    values: object,
    *,
    field_name: str,
    page_width: int,
    page_height: int,
    minimum_points: int,
    closed: bool,
) -> tuple[LayoutPoint, ...]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise LayoutContractValidationError(f"{field_name} must be an array of points.")
    if len(values) == 0:
        raise LayoutContractValidationError(f"{field_name} cannot be empty.")

    raw_points = [
        _normalize_point(
            point,
            field_name=f"{field_name}[{index}]",
            page_width=page_width,
            page_height=page_height,
        )
        for index, point in enumerate(values)
    ]
    deduped: list[LayoutPoint] = []
    for point in raw_points:
        if deduped and _points_equal(deduped[-1], point):
            continue
        deduped.append(point)

    if closed and len(deduped) > 1 and _points_equal(deduped[0], deduped[-1]):
        deduped.pop()

    simplified: list[LayoutPoint] = []
    for point in deduped:
        if len(simplified) < 2:
            simplified.append(point)
            continue
        if _is_collinear(simplified[-2], simplified[-1], point):
            simplified[-1] = point
        else:
            simplified.append(point)

    if len(simplified) < minimum_points:
        raise LayoutContractValidationError(
            f"{field_name} must contain at least {minimum_points} non-collinear points."
        )
    return tuple(simplified)


def build_layout_canonical_page(
    payload: Mapping[str, object],
    *,
    expected_run_id: str | None = None,
    expected_page_id: str | None = None,
    expected_page_index: int | None = None,
    expected_page_width: int | None = None,
    expected_page_height: int | None = None,
) -> LayoutCanonicalPage:
    schema_version = int(payload.get("schemaVersion", 1))
    if schema_version != 1:
        raise LayoutContractValidationError("schemaVersion must be 1.")

    run_id = _normalize_identifier(payload.get("runId"), field_name="runId")
    page_id = _normalize_identifier(payload.get("pageId"), field_name="pageId")
    page_index = _normalize_int(payload.get("pageIndex"), field_name="pageIndex", minimum=0)

    page_metadata = payload.get("page")
    if not isinstance(page_metadata, Mapping):
        raise LayoutContractValidationError("page metadata is required.")
    width = _normalize_int(page_metadata.get("width"), field_name="page.width", minimum=1)
    height = _normalize_int(page_metadata.get("height"), field_name="page.height", minimum=1)

    if expected_run_id is not None and run_id != expected_run_id:
        raise LayoutContractValidationError("runId does not match expected run.")
    if expected_page_id is not None and page_id != expected_page_id:
        raise LayoutContractValidationError("pageId does not match expected page.")
    if expected_page_index is not None and page_index != expected_page_index:
        raise LayoutContractValidationError("pageIndex does not match expected page index.")
    if expected_page_width is not None and width != expected_page_width:
        raise LayoutContractValidationError("page.width does not match expected page width.")
    if expected_page_height is not None and height != expected_page_height:
        raise LayoutContractValidationError("page.height does not match expected page height.")

    raw_regions = payload.get("regions")
    if not isinstance(raw_regions, Sequence) or isinstance(raw_regions, (str, bytes)):
        raise LayoutContractValidationError("regions must be an array.")
    raw_lines = payload.get("lines")
    if not isinstance(raw_lines, Sequence) or isinstance(raw_lines, (str, bytes)):
        raise LayoutContractValidationError("lines must be an array.")

    regions: list[LayoutRegion] = []
    region_ids: set[str] = set()
    for index, raw_region in enumerate(raw_regions):
        if not isinstance(raw_region, Mapping):
            raise LayoutContractValidationError(f"regions[{index}] must be an object.")
        region_id = _normalize_identifier(raw_region.get("id"), field_name=f"regions[{index}].id")
        if region_id in region_ids:
            raise LayoutContractValidationError(f"Duplicate region id '{region_id}'.")
        region_ids.add(region_id)
        region_type = _normalize_identifier(
            raw_region.get("type", "TEXT"),
            field_name=f"regions[{index}].type",
            max_length=64,
        )
        polygon = _normalize_polyline(
            raw_region.get("polygon"),
            field_name=f"regions[{index}].polygon",
            page_width=width,
            page_height=height,
            minimum_points=3,
            closed=True,
        )
        line_ids: tuple[str, ...]
        raw_line_ids = raw_region.get("lineIds")
        if raw_line_ids is None:
            line_ids = tuple()
        elif isinstance(raw_line_ids, Sequence) and not isinstance(raw_line_ids, (str, bytes)):
            deduped_line_ids: list[str] = []
            seen_line_ids: set[str] = set()
            for line_ref_index, raw_line_id in enumerate(raw_line_ids):
                line_id = _normalize_identifier(
                    raw_line_id,
                    field_name=f"regions[{index}].lineIds[{line_ref_index}]",
                )
                if line_id in seen_line_ids:
                    continue
                seen_line_ids.add(line_id)
                deduped_line_ids.append(line_id)
            line_ids = tuple(deduped_line_ids)
        else:
            raise LayoutContractValidationError(f"regions[{index}].lineIds must be an array.")
        regions.append(
            LayoutRegion(
                region_id=region_id,
                region_type=region_type,
                polygon=polygon,
                line_ids=line_ids,
                include_in_reading_order=_normalize_bool(
                    raw_region.get("includeInReadingOrder", True),
                    field_name=f"regions[{index}].includeInReadingOrder",
                ),
            )
        )

    lines: list[LayoutLine] = []
    line_ids: set[str] = set()
    for index, raw_line in enumerate(raw_lines):
        if not isinstance(raw_line, Mapping):
            raise LayoutContractValidationError(f"lines[{index}] must be an object.")
        line_id = _normalize_identifier(raw_line.get("id"), field_name=f"lines[{index}].id")
        if line_id in line_ids:
            raise LayoutContractValidationError(f"Duplicate line id '{line_id}'.")
        line_ids.add(line_id)
        parent_region_id = _normalize_identifier(
            raw_line.get("parentRegionId"),
            field_name=f"lines[{index}].parentRegionId",
        )
        if parent_region_id not in region_ids:
            raise LayoutContractValidationError(
                f"lines[{index}].parentRegionId references unknown region '{parent_region_id}'."
            )
        polygon = _normalize_polyline(
            raw_line.get("polygon"),
            field_name=f"lines[{index}].polygon",
            page_width=width,
            page_height=height,
            minimum_points=3,
            closed=True,
        )
        raw_baseline = raw_line.get("baseline")
        baseline = (
            _normalize_polyline(
                raw_baseline,
                field_name=f"lines[{index}].baseline",
                page_width=width,
                page_height=height,
                minimum_points=2,
                closed=False,
            )
            if raw_baseline is not None
            else None
        )
        lines.append(
            LayoutLine(
                line_id=line_id,
                parent_region_id=parent_region_id,
                polygon=polygon,
                baseline=baseline,
            )
        )

    line_ids_by_region: dict[str, list[str]] = {region_id: [] for region_id in region_ids}
    for line in lines:
        line_ids_by_region[line.parent_region_id].append(line.line_id)

    normalized_regions: list[LayoutRegion] = []
    for region in sorted(regions, key=lambda item: item.region_id):
        inferred = sorted(line_ids_by_region[region.region_id])
        if region.line_ids:
            for line_id in region.line_ids:
                if line_id not in line_ids:
                    raise LayoutContractValidationError(
                        f"Region '{region.region_id}' references unknown line '{line_id}'."
                    )
                line = next(item for item in lines if item.line_id == line_id)
                if line.parent_region_id != region.region_id:
                    raise LayoutContractValidationError(
                        f"Region '{region.region_id}' references line '{line_id}' with mismatched parent."
                    )
            line_ids_for_region = tuple(region.line_ids)
        else:
            line_ids_for_region = tuple(inferred)
        normalized_regions.append(
            LayoutRegion(
                region_id=region.region_id,
                region_type=region.region_type,
                polygon=region.polygon,
                line_ids=line_ids_for_region,
                include_in_reading_order=region.include_in_reading_order,
            )
        )

    known_element_ids = {region.region_id for region in normalized_regions} | {
        line.line_id for line in lines
    }
    raw_reading_order = payload.get("readingOrder", [])
    if not isinstance(raw_reading_order, Sequence) or isinstance(
        raw_reading_order, (str, bytes)
    ):
        raise LayoutContractValidationError("readingOrder must be an array when provided.")

    reading_order_edges: list[LayoutReadingOrderEdge] = []
    seen_edges: set[tuple[str, str]] = set()
    for index, raw_edge in enumerate(raw_reading_order):
        if not isinstance(raw_edge, Mapping):
            raise LayoutContractValidationError(f"readingOrder[{index}] must be an object.")
        from_id = _normalize_identifier(raw_edge.get("fromId"), field_name=f"readingOrder[{index}].fromId")
        to_id = _normalize_identifier(raw_edge.get("toId"), field_name=f"readingOrder[{index}].toId")
        if from_id not in known_element_ids or to_id not in known_element_ids:
            raise LayoutContractValidationError(
                f"readingOrder[{index}] references unknown element IDs."
            )
        edge_key = (from_id, to_id)
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        reading_order_edges.append(LayoutReadingOrderEdge(from_id=from_id, to_id=to_id))

    raw_reading_order_groups = payload.get("readingOrderGroups", [])
    if not isinstance(raw_reading_order_groups, Sequence) or isinstance(
        raw_reading_order_groups, (str, bytes)
    ):
        raise LayoutContractValidationError("readingOrderGroups must be an array when provided.")
    reading_order_groups: list[LayoutReadingOrderGroup] = []
    grouped_region_ids: set[str] = set()
    known_region_ids_for_groups = {region.region_id for region in normalized_regions}
    for index, raw_group in enumerate(raw_reading_order_groups):
        if not isinstance(raw_group, Mapping):
            raise LayoutContractValidationError(
                f"readingOrderGroups[{index}] must be an object."
            )
        group_id = _normalize_identifier(
            raw_group.get("id", f"g-{index + 1:04d}"),
            field_name=f"readingOrderGroups[{index}].id",
        )
        ordered = _normalize_bool(
            raw_group.get("ordered", True),
            field_name=f"readingOrderGroups[{index}].ordered",
        )
        raw_group_region_ids = raw_group.get("regionIds")
        if not isinstance(raw_group_region_ids, Sequence) or isinstance(
            raw_group_region_ids, (str, bytes)
        ):
            raise LayoutContractValidationError(
                f"readingOrderGroups[{index}].regionIds must be an array."
            )
        region_ids: list[str] = []
        seen_in_group: set[str] = set()
        for region_index, raw_region_id in enumerate(raw_group_region_ids):
            region_id = _normalize_identifier(
                raw_region_id,
                field_name=(
                    f"readingOrderGroups[{index}].regionIds[{region_index}]"
                ),
            )
            if region_id not in region_ids and region_id not in known_region_ids_for_groups:
                raise LayoutContractValidationError(
                    f"readingOrderGroups[{index}] references unknown region '{region_id}'."
                )
            if region_id in seen_in_group:
                raise LayoutContractValidationError(
                    f"readingOrderGroups[{index}] contains duplicate region '{region_id}'."
                )
            if region_id in grouped_region_ids:
                raise LayoutContractValidationError(
                    f"readingOrder region '{region_id}' cannot be repeated across groups."
                )
            seen_in_group.add(region_id)
            grouped_region_ids.add(region_id)
            region_ids.append(region_id)
        if not region_ids:
            continue
        reading_order_groups.append(
            LayoutReadingOrderGroup(
                group_id=group_id,
                ordered=ordered,
                region_ids=tuple(region_ids),
            )
        )

    raw_reading_order_meta = payload.get("readingOrderMeta", {})
    if not isinstance(raw_reading_order_meta, Mapping):
        raise LayoutContractValidationError("readingOrderMeta must be an object when provided.")
    default_mode = (
        "ORDERED"
        if reading_order_groups and all(group.ordered for group in reading_order_groups)
        else "UNORDERED"
        if reading_order_groups
        else "WITHHELD"
    )
    mode = _normalize_identifier(
        raw_reading_order_meta.get("mode", default_mode),
        field_name="readingOrderMeta.mode",
        max_length=24,
    ).upper()
    if mode not in {"ORDERED", "UNORDERED", "WITHHELD"}:
        raise LayoutContractValidationError(
            "readingOrderMeta.mode must be ORDERED, UNORDERED, or WITHHELD."
        )
    source = _normalize_identifier(
        raw_reading_order_meta.get("source", "AUTO_INFERRED"),
        field_name="readingOrderMeta.source",
        max_length=48,
    )
    ambiguity_score = round(
        _normalize_number(
            raw_reading_order_meta.get(
                "ambiguityScore",
                1.0 if mode == "WITHHELD" else 0.0,
            ),
            field_name="readingOrderMeta.ambiguityScore",
        ),
        6,
    )
    column_certainty = round(
        _normalize_number(
            raw_reading_order_meta.get(
                "columnCertainty",
                0.0 if mode == "WITHHELD" else 1.0,
            ),
            field_name="readingOrderMeta.columnCertainty",
        ),
        6,
    )
    overlap_conflict_score = round(
        _normalize_number(
            raw_reading_order_meta.get("overlapConflictScore", 0.0),
            field_name="readingOrderMeta.overlapConflictScore",
        ),
        6,
    )
    orphan_line_count = _normalize_int(
        raw_reading_order_meta.get("orphanLineCount", 0),
        field_name="readingOrderMeta.orphanLineCount",
        minimum=0,
    )
    non_text_complexity_score = round(
        _normalize_number(
            raw_reading_order_meta.get("nonTextComplexityScore", 0.0),
            field_name="readingOrderMeta.nonTextComplexityScore",
        ),
        6,
    )
    order_withheld = _normalize_bool(
        raw_reading_order_meta.get("orderWithheld", mode == "WITHHELD"),
        field_name="readingOrderMeta.orderWithheld",
    )
    version_etag = (
        _normalize_identifier(
            raw_reading_order_meta.get("versionEtag"),
            field_name="readingOrderMeta.versionEtag",
            max_length=160,
        )
        if raw_reading_order_meta.get("versionEtag") is not None
        else None
    )
    layout_version_id = (
        _normalize_identifier(
            raw_reading_order_meta.get("layoutVersionId"),
            field_name="readingOrderMeta.layoutVersionId",
            max_length=160,
        )
        if raw_reading_order_meta.get("layoutVersionId") is not None
        else None
    )

    return LayoutCanonicalPage(
        schema_version=1,
        run_id=run_id,
        page_id=page_id,
        page_index=page_index,
        page_width=width,
        page_height=height,
        regions=tuple(normalized_regions),
        lines=tuple(sorted(lines, key=lambda item: item.line_id)),
        reading_order_edges=tuple(
            sorted(reading_order_edges, key=lambda item: (item.from_id, item.to_id))
        ),
        reading_order_groups=tuple(reading_order_groups),
        reading_order_meta=LayoutReadingOrderMeta(
            mode=mode,
            source=source,
            ambiguity_score=ambiguity_score,
            column_certainty=column_certainty,
            overlap_conflict_score=overlap_conflict_score,
            orphan_line_count=orphan_line_count,
            non_text_complexity_score=non_text_complexity_score,
            order_withheld=order_withheld,
            version_etag=version_etag,
            layout_version_id=layout_version_id,
        ),
    )


def _format_points(points: tuple[LayoutPoint, ...]) -> str:
    return " ".join(f"{point.x:.4f},{point.y:.4f}" for point in points)


def serialize_layout_pagexml(page: LayoutCanonicalPage) -> bytes:
    ET.register_namespace("", PAGE_XML_NAMESPACE)
    root = ET.Element(f"{{{PAGE_XML_NAMESPACE}}}PcGts")
    page_element = ET.SubElement(
        root,
        f"{{{PAGE_XML_NAMESPACE}}}Page",
        {
            "runId": page.run_id,
            "pageId": page.page_id,
            "pageIndex": str(page.page_index),
            "imageWidth": str(page.page_width),
            "imageHeight": str(page.page_height),
        },
    )
    lines_by_region: dict[str, list[LayoutLine]] = {region.region_id: [] for region in page.regions}
    for line in page.lines:
        lines_by_region.setdefault(line.parent_region_id, []).append(line)

    for region in page.regions:
        region_element = ET.SubElement(
            page_element,
            f"{{{PAGE_XML_NAMESPACE}}}TextRegion",
            {
                "id": region.region_id,
                "type": region.region_type,
                "includeInReadingOrder": (
                    "true" if region.include_in_reading_order else "false"
                ),
            },
        )
        ET.SubElement(
            region_element,
            f"{{{PAGE_XML_NAMESPACE}}}Coords",
            {"points": _format_points(region.polygon)},
        )
        region_lines = lines_by_region.get(region.region_id, [])
        region_lines_by_id = {line.line_id: line for line in region_lines}
        declared_line_ids = set(region.line_ids)
        ordered_line_ids = list(region.line_ids) + [
            line.line_id
            for line in sorted(region_lines, key=lambda item: item.line_id)
            if line.line_id not in declared_line_ids
        ]
        for line_id in ordered_line_ids:
            line = region_lines_by_id.get(line_id)
            if line is None:
                continue
            line_element = ET.SubElement(
                region_element,
                f"{{{PAGE_XML_NAMESPACE}}}TextLine",
                {"id": line.line_id},
            )
            ET.SubElement(
                line_element,
                f"{{{PAGE_XML_NAMESPACE}}}Coords",
                {"points": _format_points(line.polygon)},
            )
            if line.baseline is not None:
                ET.SubElement(
                    line_element,
                    f"{{{PAGE_XML_NAMESPACE}}}Baseline",
                    {"points": _format_points(line.baseline)},
                )

    if page.reading_order_edges or page.reading_order_groups:
        reading_order_attributes = {
            "mode": page.reading_order_meta.mode,
            "source": page.reading_order_meta.source,
            "ambiguityScore": f"{page.reading_order_meta.ambiguity_score:.6f}",
            "columnCertainty": f"{page.reading_order_meta.column_certainty:.6f}",
            "overlapConflictScore": f"{page.reading_order_meta.overlap_conflict_score:.6f}",
            "orphanLineCount": str(page.reading_order_meta.orphan_line_count),
            "nonTextComplexityScore": (
                f"{page.reading_order_meta.non_text_complexity_score:.6f}"
            ),
            "orderWithheld": "true" if page.reading_order_meta.order_withheld else "false",
        }
        if page.reading_order_meta.version_etag is not None:
            reading_order_attributes["versionEtag"] = page.reading_order_meta.version_etag
        if page.reading_order_meta.layout_version_id is not None:
            reading_order_attributes["layoutVersionId"] = page.reading_order_meta.layout_version_id
        reading_order = ET.SubElement(
            page_element,
            f"{{{PAGE_XML_NAMESPACE}}}ReadingOrder",
            reading_order_attributes,
        )
        for index, group in enumerate(page.reading_order_groups):
            group_tag = "OrderedGroup" if group.ordered else "UnorderedGroup"
            group_element = ET.SubElement(
                reading_order,
                f"{{{PAGE_XML_NAMESPACE}}}{group_tag}",
                {
                    "id": group.group_id,
                    "index": str(index),
                },
            )
            for region_index, region_id in enumerate(group.region_ids):
                ET.SubElement(
                    group_element,
                    f"{{{PAGE_XML_NAMESPACE}}}RegionRefIndexed",
                    {
                        "regionRef": region_id,
                        "index": str(region_index),
                    },
                )
        for index, edge in enumerate(page.reading_order_edges):
            ET.SubElement(
                reading_order,
                f"{{{PAGE_XML_NAMESPACE}}}Relation",
                {
                    "index": str(index),
                    "from": edge.from_id,
                    "to": edge.to_id,
                },
            )

    payload = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return payload + b"\n"


def _parse_points(points: str, *, field_name: str) -> list[dict[str, float]]:
    stripped = points.strip()
    if not stripped:
        raise LayoutContractValidationError(f"{field_name} points are empty.")
    parsed: list[dict[str, float]] = []
    for index, pair in enumerate(stripped.split()):
        if "," not in pair:
            raise LayoutContractValidationError(
                f"{field_name}[{index}] must be encoded as 'x,y'."
            )
        raw_x, raw_y = pair.split(",", 1)
        parsed.append(
            {
                "x": float(raw_x),
                "y": float(raw_y),
            }
        )
    return parsed


def parse_layout_pagexml(payload: bytes) -> LayoutCanonicalPage:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as error:
        raise LayoutContractValidationError("PAGE-XML payload could not be parsed.") from error

    page_element = root.find("pc:Page", PAGE_XML_NS)
    if page_element is None:
        raise LayoutContractValidationError("PAGE-XML payload is missing Page element.")
    run_id = page_element.get("runId")
    page_id = page_element.get("pageId")
    page_index = page_element.get("pageIndex")
    page_width = page_element.get("imageWidth")
    page_height = page_element.get("imageHeight")
    if (
        run_id is None
        or page_id is None
        or page_index is None
        or page_width is None
        or page_height is None
    ):
        raise LayoutContractValidationError("PAGE-XML Page element is missing required metadata.")

    regions: list[dict[str, object]] = []
    lines: list[dict[str, object]] = []
    for region_element in page_element.findall("pc:TextRegion", PAGE_XML_NS):
        region_id = region_element.get("id")
        region_type = region_element.get("type", "TEXT")
        include_in_reading_order_raw = region_element.get("includeInReadingOrder")
        coords = region_element.find("pc:Coords", PAGE_XML_NS)
        if region_id is None or coords is None:
            raise LayoutContractValidationError("TextRegion is missing id or Coords.")
        regions.append(
            {
                "id": region_id,
                "type": region_type,
                "includeInReadingOrder": (
                    include_in_reading_order_raw.lower() != "false"
                    if isinstance(include_in_reading_order_raw, str)
                    else True
                ),
                "polygon": _parse_points(
                    coords.get("points", ""),
                    field_name=f"region:{region_id}",
                ),
            }
        )
        for line_element in region_element.findall("pc:TextLine", PAGE_XML_NS):
            line_id = line_element.get("id")
            line_coords = line_element.find("pc:Coords", PAGE_XML_NS)
            if line_id is None or line_coords is None:
                raise LayoutContractValidationError("TextLine is missing id or Coords.")
            baseline_element = line_element.find("pc:Baseline", PAGE_XML_NS)
            lines.append(
                {
                    "id": line_id,
                    "parentRegionId": region_id,
                    "polygon": _parse_points(
                        line_coords.get("points", ""),
                        field_name=f"line:{line_id}",
                    ),
                    "baseline": (
                        _parse_points(
                            baseline_element.get("points", ""),
                            field_name=f"line:{line_id}:baseline",
                        )
                        if baseline_element is not None
                        else None
                    ),
                }
            )

    reading_order_edges: list[dict[str, str]] = []
    reading_order_groups: list[dict[str, object]] = []
    reading_order_meta: dict[str, object] = {}
    reading_order_element = page_element.find("pc:ReadingOrder", PAGE_XML_NS)
    if reading_order_element is not None:
        mode = reading_order_element.get("mode")
        source = reading_order_element.get("source")
        ambiguity_score = reading_order_element.get("ambiguityScore")
        column_certainty = reading_order_element.get("columnCertainty")
        overlap_conflict_score = reading_order_element.get("overlapConflictScore")
        orphan_line_count = reading_order_element.get("orphanLineCount")
        non_text_complexity_score = reading_order_element.get("nonTextComplexityScore")
        order_withheld = reading_order_element.get("orderWithheld")
        version_etag = reading_order_element.get("versionEtag")
        layout_version_id = reading_order_element.get("layoutVersionId")
        if mode is not None:
            reading_order_meta["mode"] = mode
        if source is not None:
            reading_order_meta["source"] = source
        if ambiguity_score is not None:
            reading_order_meta["ambiguityScore"] = float(ambiguity_score)
        if column_certainty is not None:
            reading_order_meta["columnCertainty"] = float(column_certainty)
        if overlap_conflict_score is not None:
            reading_order_meta["overlapConflictScore"] = float(overlap_conflict_score)
        if orphan_line_count is not None:
            reading_order_meta["orphanLineCount"] = int(orphan_line_count)
        if non_text_complexity_score is not None:
            reading_order_meta["nonTextComplexityScore"] = float(non_text_complexity_score)
        if order_withheld is not None:
            reading_order_meta["orderWithheld"] = order_withheld.lower() == "true"
        if version_etag is not None:
            reading_order_meta["versionEtag"] = version_etag
        if layout_version_id is not None:
            reading_order_meta["layoutVersionId"] = layout_version_id

        for group in reading_order_element.findall("pc:OrderedGroup", PAGE_XML_NS):
            group_id = group.get("id")
            if group_id is None:
                continue
            refs = [
                ref.get("regionRef")
                for ref in group.findall("pc:RegionRefIndexed", PAGE_XML_NS)
            ]
            reading_order_groups.append(
                {
                    "id": group_id,
                    "ordered": True,
                    "regionIds": [value for value in refs if isinstance(value, str)],
                }
            )
        for group in reading_order_element.findall("pc:UnorderedGroup", PAGE_XML_NS):
            group_id = group.get("id")
            if group_id is None:
                continue
            refs = [
                ref.get("regionRef")
                for ref in group.findall("pc:RegionRefIndexed", PAGE_XML_NS)
            ]
            reading_order_groups.append(
                {
                    "id": group_id,
                    "ordered": False,
                    "regionIds": [value for value in refs if isinstance(value, str)],
                }
            )
        for relation in reading_order_element.findall("pc:Relation", PAGE_XML_NS):
            from_id = relation.get("from")
            to_id = relation.get("to")
            if from_id is None or to_id is None:
                continue
            reading_order_edges.append({"fromId": from_id, "toId": to_id})

    return build_layout_canonical_page(
        {
            "schemaVersion": 1,
            "runId": run_id,
            "pageId": page_id,
            "pageIndex": int(page_index),
            "page": {"width": int(page_width), "height": int(page_height)},
            "regions": regions,
            "lines": lines,
            "readingOrder": reading_order_edges,
            "readingOrderGroups": reading_order_groups,
            "readingOrderMeta": reading_order_meta,
        }
    )


def derive_layout_overlay(page: LayoutCanonicalPage) -> dict[str, object]:
    elements: list[dict[str, object]] = []
    for region in page.regions:
        elements.append(
            {
                "id": region.region_id,
                "type": "REGION",
                "parentId": None,
                "childIds": list(region.line_ids),
                "regionType": region.region_type,
                "includeInReadingOrder": region.include_in_reading_order,
                "polygon": [{"x": point.x, "y": point.y} for point in region.polygon],
            }
        )
    for line in page.lines:
        line_element: dict[str, object] = {
            "id": line.line_id,
            "type": "LINE",
            "parentId": line.parent_region_id,
            "polygon": [{"x": point.x, "y": point.y} for point in line.polygon],
        }
        if line.baseline is not None:
            line_element["baseline"] = [{"x": point.x, "y": point.y} for point in line.baseline]
        elements.append(line_element)

    elements.sort(key=lambda item: (str(item.get("type")), str(item.get("id"))))
    reading_order = [
        {"fromId": edge.from_id, "toId": edge.to_id}
        for edge in page.reading_order_edges
    ]
    reading_order_groups = [
        {
            "id": group.group_id,
            "ordered": group.ordered,
            "regionIds": list(group.region_ids),
        }
        for group in page.reading_order_groups
    ]
    reading_order_meta: dict[str, object] = {
        "schemaVersion": 1,
        "mode": page.reading_order_meta.mode,
        "source": page.reading_order_meta.source,
        "ambiguityScore": page.reading_order_meta.ambiguity_score,
        "columnCertainty": page.reading_order_meta.column_certainty,
        "overlapConflictScore": page.reading_order_meta.overlap_conflict_score,
        "orphanLineCount": page.reading_order_meta.orphan_line_count,
        "nonTextComplexityScore": page.reading_order_meta.non_text_complexity_score,
        "orderWithheld": page.reading_order_meta.order_withheld,
    }
    if page.reading_order_meta.version_etag is not None:
        reading_order_meta["versionEtag"] = page.reading_order_meta.version_etag
    if page.reading_order_meta.layout_version_id is not None:
        reading_order_meta["layoutVersionId"] = page.reading_order_meta.layout_version_id

    return {
        "schemaVersion": 1,
        "runId": page.run_id,
        "pageId": page.page_id,
        "pageIndex": page.page_index,
        "page": {
            "width": page.page_width,
            "height": page.page_height,
        },
        "elements": elements,
        "readingOrder": reading_order,
        "readingOrderGroups": reading_order_groups,
        "readingOrderMeta": reading_order_meta,
    }


def validate_layout_overlay_payload(
    payload: Mapping[str, object],
    *,
    expected_run_id: str | None = None,
    expected_page_id: str | None = None,
    expected_page_index: int | None = None,
) -> dict[str, object]:
    schema_version = _normalize_int(
        payload.get("schemaVersion"), field_name="schemaVersion", minimum=1
    )
    if schema_version != 1:
        raise LayoutContractValidationError("overlay schemaVersion must be 1.")
    run_id = _normalize_identifier(payload.get("runId"), field_name="runId")
    page_id = _normalize_identifier(payload.get("pageId"), field_name="pageId")
    page_index = _normalize_int(payload.get("pageIndex"), field_name="pageIndex", minimum=0)
    page = payload.get("page")
    if not isinstance(page, Mapping):
        raise LayoutContractValidationError("overlay page metadata is required.")
    page_width = _normalize_int(page.get("width"), field_name="page.width", minimum=1)
    page_height = _normalize_int(page.get("height"), field_name="page.height", minimum=1)

    if expected_run_id is not None and run_id != expected_run_id:
        raise LayoutContractValidationError("overlay runId does not match expected run.")
    if expected_page_id is not None and page_id != expected_page_id:
        raise LayoutContractValidationError("overlay pageId does not match expected page.")
    if expected_page_index is not None and page_index != expected_page_index:
        raise LayoutContractValidationError("overlay pageIndex does not match expected page.")

    raw_elements = payload.get("elements")
    if not isinstance(raw_elements, Sequence) or isinstance(raw_elements, (str, bytes)):
        raise LayoutContractValidationError("overlay elements must be an array.")

    normalized_elements: list[dict[str, object]] = []
    ids: set[str] = set()
    for index, raw_element in enumerate(raw_elements):
        if not isinstance(raw_element, Mapping):
            raise LayoutContractValidationError(f"elements[{index}] must be an object.")
        element_id = _normalize_identifier(raw_element.get("id"), field_name=f"elements[{index}].id")
        element_type = _normalize_identifier(
            raw_element.get("type"),
            field_name=f"elements[{index}].type",
            max_length=32,
        )
        if element_id in ids:
            raise LayoutContractValidationError(f"Duplicate overlay element id '{element_id}'.")
        ids.add(element_id)
        parent_id: str | None
        if raw_element.get("parentId") is None:
            parent_id = None
        else:
            parent_id = _normalize_identifier(
                raw_element.get("parentId"),
                field_name=f"elements[{index}].parentId",
            )
        polygon = _normalize_polyline(
            raw_element.get("polygon"),
            field_name=f"elements[{index}].polygon",
            page_width=page_width,
            page_height=page_height,
            minimum_points=3,
            closed=True,
        )
        normalized: dict[str, object] = {
            "id": element_id,
            "type": element_type,
            "parentId": parent_id,
            "polygon": [{"x": point.x, "y": point.y} for point in polygon],
        }
        if element_type == "REGION":
            child_ids_raw = raw_element.get("childIds", [])
            if not isinstance(child_ids_raw, Sequence) or isinstance(child_ids_raw, (str, bytes)):
                raise LayoutContractValidationError(
                    f"elements[{index}].childIds must be an array for REGION elements."
                )
            child_ids = [
                _normalize_identifier(
                    child_id,
                    field_name=f"elements[{index}].childIds[{child_index}]",
                )
                for child_index, child_id in enumerate(child_ids_raw)
            ]
            normalized["childIds"] = sorted(set(child_ids))
            if isinstance(raw_element.get("regionType"), str):
                normalized["regionType"] = _normalize_identifier(
                    raw_element.get("regionType"),
                    field_name=f"elements[{index}].regionType",
                    max_length=64,
                )
            normalized["includeInReadingOrder"] = _normalize_bool(
                raw_element.get("includeInReadingOrder", True),
                field_name=f"elements[{index}].includeInReadingOrder",
            )
        elif element_type == "LINE" and raw_element.get("baseline") is not None:
            baseline = _normalize_polyline(
                raw_element.get("baseline"),
                field_name=f"elements[{index}].baseline",
                page_width=page_width,
                page_height=page_height,
                minimum_points=2,
                closed=False,
            )
            normalized["baseline"] = [{"x": point.x, "y": point.y} for point in baseline]
        normalized_elements.append(normalized)

    line_ids = {str(item["id"]) for item in normalized_elements if item.get("type") == "LINE"}
    for item in normalized_elements:
        if item.get("type") == "LINE":
            parent_id = item.get("parentId")
            if parent_id is None:
                raise LayoutContractValidationError("LINE elements must define parentId.")
        if item.get("type") == "REGION":
            for child_id in item.get("childIds", []):
                if child_id not in line_ids:
                    raise LayoutContractValidationError(
                        f"REGION element '{item['id']}' references unknown child line '{child_id}'."
                    )

    normalized_reading_order: list[dict[str, str]] = []
    raw_reading_order = payload.get("readingOrder", [])
    if not isinstance(raw_reading_order, Sequence) or isinstance(raw_reading_order, (str, bytes)):
        raise LayoutContractValidationError("readingOrder must be an array.")
    seen_edges: set[tuple[str, str]] = set()
    for index, raw_edge in enumerate(raw_reading_order):
        if not isinstance(raw_edge, Mapping):
            raise LayoutContractValidationError(f"readingOrder[{index}] must be an object.")
        from_id = _normalize_identifier(raw_edge.get("fromId"), field_name=f"readingOrder[{index}].fromId")
        to_id = _normalize_identifier(raw_edge.get("toId"), field_name=f"readingOrder[{index}].toId")
        if from_id not in ids or to_id not in ids:
            raise LayoutContractValidationError(
                f"readingOrder[{index}] references unknown element IDs."
            )
        edge = (from_id, to_id)
        if edge in seen_edges:
            continue
        seen_edges.add(edge)
        normalized_reading_order.append({"fromId": from_id, "toId": to_id})

    region_ids = {str(item["id"]) for item in normalized_elements if item.get("type") == "REGION"}
    raw_reading_order_groups = payload.get("readingOrderGroups", [])
    if not isinstance(raw_reading_order_groups, Sequence) or isinstance(
        raw_reading_order_groups, (str, bytes)
    ):
        raise LayoutContractValidationError("readingOrderGroups must be an array.")
    normalized_reading_order_groups: list[dict[str, object]] = []
    grouped_region_ids: set[str] = set()
    for index, raw_group in enumerate(raw_reading_order_groups):
        if not isinstance(raw_group, Mapping):
            raise LayoutContractValidationError(
                f"readingOrderGroups[{index}] must be an object."
            )
        group_id = _normalize_identifier(
            raw_group.get("id", f"g-{index + 1:04d}"),
            field_name=f"readingOrderGroups[{index}].id",
        )
        ordered = _normalize_bool(
            raw_group.get("ordered", True),
            field_name=f"readingOrderGroups[{index}].ordered",
        )
        raw_group_region_ids = raw_group.get("regionIds")
        if not isinstance(raw_group_region_ids, Sequence) or isinstance(
            raw_group_region_ids, (str, bytes)
        ):
            raise LayoutContractValidationError(
                f"readingOrderGroups[{index}].regionIds must be an array."
            )
        group_region_ids: list[str] = []
        seen_in_group: set[str] = set()
        for region_index, raw_region_id in enumerate(raw_group_region_ids):
            region_id = _normalize_identifier(
                raw_region_id,
                field_name=f"readingOrderGroups[{index}].regionIds[{region_index}]",
            )
            if region_id not in region_ids:
                raise LayoutContractValidationError(
                    f"readingOrderGroups[{index}] references unknown region '{region_id}'."
                )
            if region_id in seen_in_group:
                raise LayoutContractValidationError(
                    f"readingOrderGroups[{index}] contains duplicate region '{region_id}'."
                )
            if region_id in grouped_region_ids:
                raise LayoutContractValidationError(
                    f"readingOrder region '{region_id}' cannot be repeated across groups."
                )
            seen_in_group.add(region_id)
            grouped_region_ids.add(region_id)
            group_region_ids.append(region_id)
        if not group_region_ids:
            continue
        normalized_reading_order_groups.append(
            {
                "id": group_id,
                "ordered": ordered,
                "regionIds": group_region_ids,
            }
        )

    raw_reading_order_meta = payload.get("readingOrderMeta", {})
    if not isinstance(raw_reading_order_meta, Mapping):
        raise LayoutContractValidationError("readingOrderMeta must be an object.")
    default_mode = (
        "ORDERED"
        if normalized_reading_order_groups
        and all(bool(group["ordered"]) for group in normalized_reading_order_groups)
        else "UNORDERED"
        if normalized_reading_order_groups
        else "WITHHELD"
    )
    mode = _normalize_identifier(
        raw_reading_order_meta.get("mode", default_mode),
        field_name="readingOrderMeta.mode",
        max_length=24,
    ).upper()
    if mode not in {"ORDERED", "UNORDERED", "WITHHELD"}:
        raise LayoutContractValidationError(
            "readingOrderMeta.mode must be ORDERED, UNORDERED, or WITHHELD."
        )
    source = _normalize_identifier(
        raw_reading_order_meta.get("source", "AUTO_INFERRED"),
        field_name="readingOrderMeta.source",
        max_length=48,
    )
    normalized_reading_order_meta: dict[str, object] = {
        "schemaVersion": 1,
        "mode": mode,
        "source": source,
        "ambiguityScore": round(
            _normalize_number(
                raw_reading_order_meta.get(
                    "ambiguityScore",
                    1.0 if mode == "WITHHELD" else 0.0,
                ),
                field_name="readingOrderMeta.ambiguityScore",
            ),
            6,
        ),
        "columnCertainty": round(
            _normalize_number(
                raw_reading_order_meta.get(
                    "columnCertainty",
                    0.0 if mode == "WITHHELD" else 1.0,
                ),
                field_name="readingOrderMeta.columnCertainty",
            ),
            6,
        ),
        "overlapConflictScore": round(
            _normalize_number(
                raw_reading_order_meta.get("overlapConflictScore", 0.0),
                field_name="readingOrderMeta.overlapConflictScore",
            ),
            6,
        ),
        "orphanLineCount": _normalize_int(
            raw_reading_order_meta.get("orphanLineCount", 0),
            field_name="readingOrderMeta.orphanLineCount",
            minimum=0,
        ),
        "nonTextComplexityScore": round(
            _normalize_number(
                raw_reading_order_meta.get("nonTextComplexityScore", 0.0),
                field_name="readingOrderMeta.nonTextComplexityScore",
            ),
            6,
        ),
        "orderWithheld": _normalize_bool(
            raw_reading_order_meta.get("orderWithheld", mode == "WITHHELD"),
            field_name="readingOrderMeta.orderWithheld",
        ),
    }
    if raw_reading_order_meta.get("versionEtag") is not None:
        normalized_reading_order_meta["versionEtag"] = _normalize_identifier(
            raw_reading_order_meta.get("versionEtag"),
            field_name="readingOrderMeta.versionEtag",
            max_length=160,
        )
    if raw_reading_order_meta.get("layoutVersionId") is not None:
        normalized_reading_order_meta["layoutVersionId"] = _normalize_identifier(
            raw_reading_order_meta.get("layoutVersionId"),
            field_name="readingOrderMeta.layoutVersionId",
            max_length=160,
        )

    normalized_elements.sort(key=lambda item: (str(item.get("type")), str(item.get("id"))))
    normalized_reading_order.sort(key=lambda item: (item["fromId"], item["toId"]))
    return {
        "schemaVersion": 1,
        "runId": run_id,
        "pageId": page_id,
        "pageIndex": page_index,
        "page": {"width": page_width, "height": page_height},
        "elements": normalized_elements,
        "readingOrder": normalized_reading_order,
        "readingOrderGroups": normalized_reading_order_groups,
        "readingOrderMeta": normalized_reading_order_meta,
    }
