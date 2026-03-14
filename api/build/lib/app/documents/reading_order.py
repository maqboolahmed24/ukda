from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean, median
from typing import Literal, Mapping, Sequence

ReadingOrderMode = Literal["ORDERED", "UNORDERED", "WITHHELD"]


@dataclass(frozen=True)
class ReadingOrderGroup:
    group_id: str
    ordered: bool
    region_ids: tuple[str, ...]


@dataclass(frozen=True)
class ReadingOrderInferenceResult:
    mode: ReadingOrderMode
    groups: tuple[ReadingOrderGroup, ...]
    edges: tuple[dict[str, str], ...]
    column_certainty: float
    overlap_conflict_score: float
    orphan_line_count: int
    non_text_complexity_score: float
    reading_order_ambiguity_score: float

    @property
    def order_withheld(self) -> bool:
        return self.mode == "WITHHELD"

    def to_meta_payload(
        self,
        *,
        version_etag: str | None = None,
        layout_version_id: str | None = None,
        source: str = "AUTO_INFERRED",
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "schemaVersion": 1,
            "mode": self.mode,
            "source": source,
            "columnCertainty": round(self.column_certainty, 6),
            "overlapConflictScore": round(self.overlap_conflict_score, 6),
            "orphanLineCount": self.orphan_line_count,
            "nonTextComplexityScore": round(self.non_text_complexity_score, 6),
            "ambiguityScore": round(self.reading_order_ambiguity_score, 6),
            "orderWithheld": self.order_withheld,
        }
        if version_etag is not None:
            payload["versionEtag"] = version_etag
        if layout_version_id is not None:
            payload["layoutVersionId"] = layout_version_id
        return payload

    def to_groups_payload(self) -> list[dict[str, object]]:
        return [
            {
                "id": group.group_id,
                "ordered": group.ordered,
                "regionIds": list(group.region_ids),
            }
            for group in self.groups
        ]


@dataclass(frozen=True)
class _RegionBox:
    region_id: str
    region_type: str
    line_ids: tuple[str, ...]
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center_x(self) -> float:
        return self.x0 + (self.width / 2.0)

    @property
    def center_y(self) -> float:
        return self.y0 + (self.height / 2.0)

    @property
    def is_text_like(self) -> bool:
        region_type = self.region_type.upper()
        if region_type in {"TEXT", "PARAGRAPH", "HEADING"}:
            return True
        return len(self.line_ids) > 0


def _clamp(value: float, *, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _polygon_bbox(points: Sequence[Mapping[str, object]]) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for point in points:
        raw_x = point.get("x")
        raw_y = point.get("y")
        if not isinstance(raw_x, (int, float)) or not isinstance(raw_y, (int, float)):
            continue
        x = float(raw_x)
        y = float(raw_y)
        if not math.isfinite(x) or not math.isfinite(y):
            continue
        xs.append(x)
        ys.append(y)
    if not xs or not ys:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(xs), min(ys), max(xs), max(ys))


def _box_iou(left: _RegionBox, right: _RegionBox) -> float:
    overlap_x0 = max(left.x0, right.x0)
    overlap_y0 = max(left.y0, right.y0)
    overlap_x1 = min(left.x1, right.x1)
    overlap_y1 = min(left.y1, right.y1)
    if overlap_x1 <= overlap_x0 or overlap_y1 <= overlap_y0:
        return 0.0
    intersection = (overlap_x1 - overlap_x0) * (overlap_y1 - overlap_y0)
    denominator = max(1e-9, left.area + right.area - intersection)
    return intersection / denominator


def _horizontal_overlap_ratio(left: _RegionBox, right: _RegionBox) -> float:
    overlap = max(0.0, min(left.x1, right.x1) - max(left.x0, right.x0))
    denominator = max(1e-9, min(left.width, right.width))
    return overlap / denominator


def _as_region_box(raw_region: Mapping[str, object]) -> _RegionBox:
    region_id = str(raw_region.get("id") or "").strip()
    region_type = str(raw_region.get("type") or "TEXT").strip() or "TEXT"
    raw_polygon = raw_region.get("polygon")
    points = (
        list(raw_polygon)
        if isinstance(raw_polygon, Sequence) and not isinstance(raw_polygon, (str, bytes))
        else []
    )
    x0, y0, x1, y1 = _polygon_bbox(points)
    raw_line_ids = raw_region.get("lineIds")
    line_ids: list[str] = []
    if isinstance(raw_line_ids, Sequence) and not isinstance(raw_line_ids, (str, bytes)):
        seen: set[str] = set()
        for raw_line_id in raw_line_ids:
            line_id = str(raw_line_id).strip()
            if not line_id or line_id in seen:
                continue
            seen.add(line_id)
            line_ids.append(line_id)
    return _RegionBox(
        region_id=region_id,
        region_type=region_type,
        line_ids=tuple(line_ids),
        x0=x0,
        y0=y0,
        x1=x1,
        y1=y1,
    )


def _resolve_line_sort_key(raw_line: Mapping[str, object]) -> tuple[float, float, str]:
    line_id = str(raw_line.get("id") or "").strip()
    raw_polygon = raw_line.get("polygon")
    points = (
        list(raw_polygon)
        if isinstance(raw_polygon, Sequence) and not isinstance(raw_polygon, (str, bytes))
        else []
    )
    x0, y0, x1, y1 = _polygon_bbox(points)
    return ((y0 + y1) / 2.0, (x0 + x1) / 2.0, line_id)


def _cluster_columns(regions: Sequence[_RegionBox]) -> list[list[_RegionBox]]:
    if not regions:
        return []
    median_width = median([max(1.0, region.width) for region in regions])
    cluster_gap = max(24.0, median_width * 0.55)
    clusters: list[list[_RegionBox]] = []
    for region in sorted(regions, key=lambda item: (item.center_x, item.center_y, item.region_id)):
        best_index: int | None = None
        best_score = -1.0
        for index, cluster in enumerate(clusters):
            cluster_center = mean(item.center_x for item in cluster)
            cluster_box = _RegionBox(
                region_id="cluster",
                region_type="TEXT",
                line_ids=tuple(),
                x0=min(item.x0 for item in cluster),
                y0=min(item.y0 for item in cluster),
                x1=max(item.x1 for item in cluster),
                y1=max(item.y1 for item in cluster),
            )
            overlap = _horizontal_overlap_ratio(region, cluster_box)
            distance = abs(region.center_x - cluster_center)
            if overlap < 0.12 and distance > cluster_gap:
                continue
            score = overlap - (distance / max(1.0, cluster_gap * 2.0))
            if score > best_score:
                best_score = score
                best_index = index
        if best_index is None:
            clusters.append([region])
        else:
            clusters[best_index].append(region)
    clusters.sort(
        key=lambda cluster: (
            mean(item.center_x for item in cluster),
            mean(item.center_y for item in cluster),
        )
    )
    for cluster in clusters:
        cluster.sort(key=lambda item: (item.center_y, item.center_x, item.region_id))
    return clusters


def _compute_column_certainty(clusters: Sequence[Sequence[_RegionBox]]) -> float:
    if not clusters:
        return 0.0
    if len(clusters) == 1:
        return 0.7
    centers = [mean(item.center_x for item in cluster) for cluster in clusters]
    widths = [max(1.0, max(item.width for item in cluster)) for cluster in clusters]
    gaps = [centers[index + 1] - centers[index] for index in range(len(centers) - 1)]
    min_gap = min(gaps) if gaps else 0.0
    avg_width = mean(widths) if widths else 1.0
    gap_score = _clamp(min_gap / max(1.0, avg_width * 0.6), minimum=0.0, maximum=1.0)
    cluster_sizes = [len(cluster) for cluster in clusters]
    size_balance = 1.0
    if len(cluster_sizes) > 1:
        spread = max(cluster_sizes) - min(cluster_sizes)
        size_balance = _clamp(
            1.0 - (float(spread) / float(max(1, sum(cluster_sizes)))),
            minimum=0.0,
            maximum=1.0,
        )
    return _clamp(
        (gap_score * 0.75) + (size_balance * 0.25),
        minimum=0.0,
        maximum=1.0,
    )


def _regions_to_groups(
    *,
    main_clusters: Sequence[Sequence[_RegionBox]],
    side_regions: Sequence[_RegionBox],
    ordered: bool,
) -> tuple[ReadingOrderGroup, ...]:
    groups: list[ReadingOrderGroup] = []
    group_index = 1
    for cluster in main_clusters:
        region_ids = tuple(region.region_id for region in cluster if region.region_id)
        if not region_ids:
            continue
        groups.append(
            ReadingOrderGroup(
                group_id=f"g-{group_index:04d}",
                ordered=ordered,
                region_ids=region_ids,
            )
        )
        group_index += 1
    if side_regions:
        groups.append(
            ReadingOrderGroup(
                group_id=f"g-{group_index:04d}",
                ordered=False,
                region_ids=tuple(
                    region.region_id
                    for region in sorted(
                        side_regions,
                        key=lambda item: (item.center_y, item.center_x, item.region_id),
                    )
                    if region.region_id
                ),
            )
        )
    return tuple(group for group in groups if group.region_ids)


def build_reading_order_edges(
    *,
    groups: Sequence[ReadingOrderGroup],
    lines: Sequence[Mapping[str, object]],
) -> tuple[dict[str, str], ...]:
    lines_by_region: dict[str, list[Mapping[str, object]]] = {}
    for raw_line in lines:
        region_id = str(raw_line.get("parentRegionId") or "").strip()
        if not region_id:
            continue
        lines_by_region.setdefault(region_id, []).append(raw_line)
    for region_id in list(lines_by_region):
        lines_by_region[region_id].sort(key=_resolve_line_sort_key)

    edges: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def append_edge(from_id: str, to_id: str) -> None:
        edge = (from_id, to_id)
        if not from_id or not to_id or edge in seen:
            return
        seen.add(edge)
        edges.append({"fromId": from_id, "toId": to_id})

    for group in groups:
        previous_region_last_line: str | None = None
        previous_region_id: str | None = None
        for region_id in group.region_ids:
            region_lines = lines_by_region.get(region_id, [])
            line_ids = [str(line.get("id") or "").strip() for line in region_lines]
            line_ids = [line_id for line_id in line_ids if line_id]
            if line_ids:
                append_edge(region_id, line_ids[0])
                for index in range(len(line_ids) - 1):
                    append_edge(line_ids[index], line_ids[index + 1])
            if group.ordered:
                if previous_region_last_line and line_ids:
                    append_edge(previous_region_last_line, line_ids[0])
                elif previous_region_id and line_ids:
                    append_edge(previous_region_id, line_ids[0])
                elif previous_region_id and not line_ids:
                    append_edge(previous_region_id, region_id)
            previous_region_id = region_id
            previous_region_last_line = line_ids[-1] if line_ids else None
    return tuple(edges)


def infer_reading_order(
    *,
    regions: Sequence[Mapping[str, object]],
    lines: Sequence[Mapping[str, object]],
) -> ReadingOrderInferenceResult:
    normalized_regions = [_as_region_box(region) for region in regions]
    text_like_regions = [region for region in normalized_regions if region.is_text_like]
    side_regions = [region for region in normalized_regions if not region.is_text_like]
    target_regions = text_like_regions if text_like_regions else normalized_regions
    column_clusters = _cluster_columns(target_regions)
    column_certainty = _compute_column_certainty(column_clusters)

    overlap_conflict_score = 0.0
    for index, left in enumerate(target_regions):
        for right in target_regions[index + 1 :]:
            overlap_conflict_score = max(overlap_conflict_score, _box_iou(left, right))

    known_region_ids = {region.region_id for region in normalized_regions if region.region_id}
    orphan_line_count = 0
    for raw_line in lines:
        parent_region_id = str(raw_line.get("parentRegionId") or "").strip()
        if not parent_region_id or parent_region_id not in known_region_ids:
            orphan_line_count += 1

    non_text_complexity_score = _clamp(
        float(len(side_regions)) / float(max(1, len(normalized_regions))),
        minimum=0.0,
        maximum=1.0,
    )
    orphan_ratio = _clamp(
        float(orphan_line_count) / float(max(1, len(lines))),
        minimum=0.0,
        maximum=1.0,
    )

    ambiguity_score = _clamp(
        ((1.0 - column_certainty) * 0.40)
        + (overlap_conflict_score * 0.25)
        + (orphan_ratio * 0.20)
        + (non_text_complexity_score * 0.15),
        minimum=0.0,
        maximum=1.0,
    )

    if ambiguity_score >= 0.60:
        mode: ReadingOrderMode = "WITHHELD"
        groups: tuple[ReadingOrderGroup, ...] = tuple()
        edges = tuple()
    elif ambiguity_score >= 0.35 or column_certainty < 0.75:
        mode = "UNORDERED"
        groups = _regions_to_groups(
            main_clusters=column_clusters,
            side_regions=side_regions,
            ordered=False,
        )
        edges = build_reading_order_edges(groups=groups, lines=lines)
    else:
        mode = "ORDERED"
        groups = _regions_to_groups(
            main_clusters=column_clusters,
            side_regions=side_regions,
            ordered=True,
        )
        edges = build_reading_order_edges(groups=groups, lines=lines)

    return ReadingOrderInferenceResult(
        mode=mode,
        groups=groups,
        edges=edges,
        column_certainty=column_certainty,
        overlap_conflict_score=overlap_conflict_score,
        orphan_line_count=orphan_line_count,
        non_text_complexity_score=non_text_complexity_score,
        reading_order_ambiguity_score=ambiguity_score,
    )


def normalize_reading_order_groups(
    *,
    groups: Sequence[Mapping[str, object]],
    known_region_ids: set[str],
) -> tuple[ReadingOrderGroup, ...]:
    normalized_groups: list[ReadingOrderGroup] = []
    consumed_region_ids: set[str] = set()
    for group_index, raw_group in enumerate(groups, start=1):
        group_id = str(raw_group.get("id") or f"g-{group_index:04d}").strip()
        if not group_id:
            group_id = f"g-{group_index:04d}"
        ordered = bool(raw_group.get("ordered", True))
        raw_region_ids = raw_group.get("regionIds")
        if not isinstance(raw_region_ids, Sequence) or isinstance(
            raw_region_ids, (str, bytes)
        ):
            raise ValueError("reading-order groups must define regionIds arrays.")
        region_ids: list[str] = []
        seen_in_group: set[str] = set()
        for raw_region_id in raw_region_ids:
            region_id = str(raw_region_id).strip()
            if not region_id:
                continue
            if region_id not in known_region_ids:
                raise ValueError(
                    f"Reading-order group '{group_id}' references unknown region '{region_id}'."
                )
            if region_id in seen_in_group:
                raise ValueError(
                    f"Reading-order group '{group_id}' contains duplicate region '{region_id}'."
                )
            if region_id in consumed_region_ids:
                raise ValueError(
                    f"Reading-order region '{region_id}' cannot appear in multiple groups."
                )
            seen_in_group.add(region_id)
            consumed_region_ids.add(region_id)
            region_ids.append(region_id)
        if not region_ids:
            continue
        normalized_groups.append(
            ReadingOrderGroup(
                group_id=group_id,
                ordered=ordered,
                region_ids=tuple(region_ids),
            )
        )
    return tuple(normalized_groups)


__all__ = [
    "ReadingOrderGroup",
    "ReadingOrderInferenceResult",
    "ReadingOrderMode",
    "build_reading_order_edges",
    "infer_reading_order",
    "normalize_reading_order_groups",
]
