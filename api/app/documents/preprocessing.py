from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from typing import Any, Mapping

from app.documents.models import PreprocessQualityGateStatus

_SUPPORTED_PROFILE_IDS = ("BALANCED", "CONSERVATIVE", "AGGRESSIVE", "BLEED_THROUGH")
_DEFAULT_PROFILE_ID = "BALANCED"
_PROFILE_VERSION = "v1"
_PROFILE_REVISION = 2

# Pinned canonical v1 baseline.
_BASELINE_PARAMS: dict[str, object] = {
    "algorithm_version": "preprocess-v1-grayscale",
    "grayscale_mode": "BT.601",
    "deskew_max_abs_angle_deg": 12.0,
    "deskew_apply_min_abs_angle_deg": 0.15,
    "deskew_step_deg": 0.25,
    "background_norm_gaussian_sigma_px": 21.0,
    "denoise_median_kernel_px": 3,
    "contrast_clahe_tile_grid": [8, 8],
    "contrast_clahe_clip_limit": 2.0,
    "interpolation": "bicubic",
    "dpi_page_width_inches": 8.27,
    "dpi_page_height_inches": 11.69,
    "warn_high_skew_abs_angle_deg": 3.0,
    "warn_high_blur_threshold": 0.20,
    "warn_low_contrast_threshold": 0.25,
}

_PROFILE_OVERRIDES: dict[str, dict[str, object]] = {
    # Canonical v1 profile keeps baseline values exactly.
    "BALANCED": {},
    "CONSERVATIVE": {
        "deskew_apply_min_abs_angle_deg": 0.25,
        "background_norm_gaussian_sigma_px": 17.0,
        "contrast_clahe_clip_limit": 1.7,
    },
    "AGGRESSIVE": {
        "deskew_apply_min_abs_angle_deg": 0.10,
        "background_norm_gaussian_sigma_px": 27.0,
        "contrast_clahe_clip_limit": 2.4,
        "binary_output_enabled": True,
        "binary_adaptive_radius_px": 11,
        "binary_adaptive_offset": 9,
    },
    "BLEED_THROUGH": {
        "deskew_apply_min_abs_angle_deg": 0.10,
        "background_norm_gaussian_sigma_px": 25.0,
        "contrast_clahe_clip_limit": 2.2,
        "binary_output_enabled": True,
        "binary_adaptive_radius_px": 11,
        "binary_adaptive_offset": 9,
        "bleed_through_mode": "PAIRED_PREFERRED",
        "bleed_pair_gaussian_sigma_px": 9.0,
        "bleed_pair_weight": 0.25,
        "bleed_single_fallback_enabled": True,
        "bleed_single_fallback_sigma_px": 5.5,
    },
}

_PROFILE_METADATA: dict[str, dict[str, object]] = {
    "BALANCED": {
        "label": "Balanced",
        "description": (
            "Canonical baseline profile tuned for deterministic preprocessing with "
            "conservative quality-gate behavior."
        ),
        "is_advanced": False,
        "is_gated": False,
    },
    "CONSERVATIVE": {
        "label": "Conservative",
        "description": (
            "Low-risk variant with reduced enhancement intensity for fragile historical scans."
        ),
        "is_advanced": False,
        "is_gated": False,
    },
    "AGGRESSIVE": {
        "label": "Aggressive",
        "description": (
            "Stronger cleanup profile with optional adaptive binarization for difficult pages."
        ),
        "is_advanced": True,
        "is_gated": True,
    },
    "BLEED_THROUGH": {
        "label": "Bleed-through",
        "description": (
            "Advanced profile tuned for show-through reduction; best results use paired recto/verso pages."
        ),
        "is_advanced": True,
        "is_gated": True,
    },
}

_WARNING_LOW_DPI = "LOW_DPI"
_WARNING_HIGH_SKEW = "HIGH_SKEW"
_WARNING_HIGH_BLUR = "HIGH_BLUR"
_WARNING_LOW_CONTRAST = "LOW_CONTRAST"
_WARNING_BLEED_PAIR_UNAVAILABLE = "BLEED_PAIR_UNAVAILABLE"


class PreprocessPipelineError(RuntimeError):
    """Preprocessing pipeline execution failed."""


@dataclass(frozen=True)
class PreprocessPageOutcome:
    gray_png_bytes: bytes
    bin_png_bytes: bytes | None
    metrics_json: dict[str, object]
    warnings_json: list[str]
    quality_gate_status: PreprocessQualityGateStatus
    sha256_gray: str
    sha256_bin: str | None


@dataclass(frozen=True)
class PreprocessProfileDefinition:
    profile_id: str
    profile_version: str
    profile_revision: int
    label: str
    description: str
    params_json: dict[str, object]
    params_hash: str
    is_advanced: bool
    is_gated: bool
    supersedes_profile_id: str | None = None
    supersedes_profile_revision: int | None = None


def normalize_profile_id(profile_id: str | None) -> str:
    if not isinstance(profile_id, str):
        return _DEFAULT_PROFILE_ID
    normalized = profile_id.strip().upper()
    if not normalized:
        return _DEFAULT_PROFILE_ID
    if normalized not in _SUPPORTED_PROFILE_IDS:
        raise PreprocessPipelineError(
            "profileId must be BALANCED, CONSERVATIVE, AGGRESSIVE, or BLEED_THROUGH."
        )
    return normalized


def _build_canonical_profile_params(profile_id: str) -> dict[str, object]:
    merged: dict[str, object] = dict(_BASELINE_PARAMS)
    merged.update(_PROFILE_OVERRIDES[profile_id])
    merged["profile_id"] = profile_id
    merged["param_contract"] = "ukde.preprocess.v1"
    return canonicalize_params_dict(merged)


def list_preprocess_profile_definitions() -> list[PreprocessProfileDefinition]:
    definitions: list[PreprocessProfileDefinition] = []
    for profile_id in _SUPPORTED_PROFILE_IDS:
        metadata = _PROFILE_METADATA[profile_id]
        params_json = _build_canonical_profile_params(profile_id)
        definitions.append(
            PreprocessProfileDefinition(
                profile_id=profile_id,
                profile_version=_PROFILE_VERSION,
                profile_revision=_PROFILE_REVISION,
                label=str(metadata["label"]),
                description=str(metadata["description"]),
                params_json=params_json,
                params_hash=hash_params_canonical(params_json),
                is_advanced=bool(metadata["is_advanced"]),
                is_gated=bool(metadata["is_gated"]),
                # Fresh environments do not seed prior revisions, so avoid dangling
                # self-referential lineage pointers that violate FK constraints.
                supersedes_profile_id=None,
                supersedes_profile_revision=None,
            )
        )
    return definitions


def get_preprocess_profile_definition(profile_id: str | None) -> PreprocessProfileDefinition:
    normalized_profile_id = normalize_profile_id(profile_id)
    for definition in list_preprocess_profile_definitions():
        if definition.profile_id == normalized_profile_id:
            return definition
    raise PreprocessPipelineError("Unsupported preprocess profile definition.")


def canonicalize_json(value: object) -> object:
    if isinstance(value, dict):
        normalized: dict[str, object] = {}
        for key in sorted(value):
            if not isinstance(key, str):
                raise PreprocessPipelineError("paramsJson keys must be strings.")
            normalized[key] = canonicalize_json(value[key])
        return normalized
    if isinstance(value, list):
        return [canonicalize_json(item) for item in value]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise PreprocessPipelineError("paramsJson contains non-finite numeric values.")
        if value.is_integer():
            return int(value)
        return float(f"{value:.12g}")
    if isinstance(value, str):
        return value
    raise PreprocessPipelineError("paramsJson contains unsupported value types.")


def canonicalize_params_dict(value: Mapping[str, object]) -> dict[str, object]:
    normalized = canonicalize_json(dict(value))
    if not isinstance(normalized, dict):
        raise PreprocessPipelineError("paramsJson must be a JSON object.")
    return normalized


def serialize_params_canonical(params_json: Mapping[str, object]) -> str:
    normalized = canonicalize_params_dict(params_json)
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def hash_params_canonical(params_json: Mapping[str, object]) -> str:
    canonical = serialize_params_canonical(params_json)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def expand_profile_params(
    *,
    profile_id: str | None,
    params_json: Mapping[str, object] | None,
) -> tuple[str, dict[str, object]]:
    definition = get_preprocess_profile_definition(profile_id)
    merged: dict[str, object] = dict(definition.params_json)
    if params_json:
        merged.update(canonicalize_params_dict(params_json))
    merged["profile_id"] = definition.profile_id
    merged["param_contract"] = "ukde.preprocess.v1"
    return definition.profile_id, canonicalize_params_dict(merged)


def _resolve_median_kernel(value: object) -> int:
    if not isinstance(value, int):
        raise PreprocessPipelineError("denoise_median_kernel_px must be an integer.")
    if value < 3:
        return 3
    if value % 2 == 0:
        return value + 1
    return value


def _resolve_tile_grid(value: object) -> tuple[int, int]:
    if not isinstance(value, list) or len(value) != 2:
        raise PreprocessPipelineError("contrast_clahe_tile_grid must be [x, y].")
    x, y = value
    if not isinstance(x, int) or not isinstance(y, int):
        raise PreprocessPipelineError("contrast_clahe_tile_grid values must be integers.")
    return max(1, x), max(1, y)


def _require_image_lib():
    try:
        from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError
    except ModuleNotFoundError as error:
        raise PreprocessPipelineError(
            "Pillow dependency is required for preprocessing execution."
        ) from error
    return Image, ImageChops, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError


def _resolve_bool_param(value: object, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _resolve_bleed_mode(params_json: Mapping[str, object]) -> str:
    raw_value = params_json.get("bleed_through_mode")
    if not isinstance(raw_value, str):
        return "OFF"
    normalized = raw_value.strip().upper().replace("-", "_")
    if normalized in {"OFF", "PAIRED_PREFERRED", "SINGLE_FALLBACK"}:
        return normalized
    return "OFF"


def _estimate_dpi(
    *,
    source_dpi: int | None,
    width_px: int,
    height_px: int,
    params: Mapping[str, object],
) -> int | None:
    if isinstance(source_dpi, int) and source_dpi > 0:
        return source_dpi
    width_in = float(params.get("dpi_page_width_inches", 8.27))
    height_in = float(params.get("dpi_page_height_inches", 11.69))
    if width_in <= 0 or height_in <= 0:
        return None
    estimated = max(width_px / width_in, height_px / height_in)
    if not math.isfinite(estimated) or estimated <= 0:
        return None
    return int(round(estimated))


def _row_projection_variance(image) -> float:  # type: ignore[no-untyped-def]
    width, height = image.size
    raw = image.tobytes()
    if width < 1 or height < 1 or not raw:
        return 0.0
    row_scores: list[float] = []
    offset = 0
    for _ in range(height):
        row = raw[offset : offset + width]
        offset += width
        # Invert intensity to measure text "ink" energy.
        row_scores.append(sum(255 - value for value in row))
    mean = sum(row_scores) / float(len(row_scores))
    variance = sum((value - mean) ** 2 for value in row_scores) / float(len(row_scores))
    return variance


def _measure_skew_angle(
    *,
    grayscale_image,  # type: ignore[no-untyped-def]
    max_abs_angle_deg: float,
    step_deg: float,
) -> float:
    Image, _, ImageFilter, _, _, _ = _require_image_lib()
    # Slight blur reduces quantization noise for projection scoring.
    candidate_image = grayscale_image.filter(ImageFilter.GaussianBlur(radius=1.0))
    threshold = int(sum(candidate_image.histogram()[128:]) / max(1, candidate_image.size[0] * candidate_image.size[1]) > 0.5)
    # Deterministic threshold around mid-gray when histogram signal is weak.
    binary = candidate_image.point(
        lambda value: 255 if value > (160 if threshold else 128) else 0,
        mode="L",
    )
    safe_step = max(0.05, min(1.0, step_deg))
    span = int(max_abs_angle_deg / safe_step)
    best_angle = 0.0
    best_score = -1.0
    for index in range(-span, span + 1):
        angle = float(index) * safe_step
        rotated = binary.rotate(
            angle,
            resample=Image.Resampling.BICUBIC,
            expand=True,
            fillcolor=255,
        )
        score = _row_projection_variance(rotated)
        if score > best_score:
            best_score = score
            best_angle = angle
    return round(best_angle, 4)


def _percentile_from_histogram(histogram: list[int], percentile: float) -> int:
    total = sum(histogram)
    if total < 1:
        return 0
    threshold = total * min(1.0, max(0.0, percentile))
    running = 0
    for index, count in enumerate(histogram):
        running += count
        if running >= threshold:
            return index
    return len(histogram) - 1


def _contrast_equalize_tiles(
    image,  # type: ignore[no-untyped-def]
    *,
    tile_grid: tuple[int, int],
    clip_limit: float,
):
    Image, _, _, ImageOps, _, _ = _require_image_lib()
    width, height = image.size
    tiles_x, tiles_y = tile_grid
    tile_w = max(1, width // tiles_x)
    tile_h = max(1, height // tiles_y)
    blend_alpha = min(1.0, max(0.0, clip_limit / 4.0))
    output = image.copy()
    for tile_y in range(tiles_y):
        for tile_x in range(tiles_x):
            left = tile_x * tile_w
            upper = tile_y * tile_h
            right = width if tile_x == tiles_x - 1 else min(width, left + tile_w)
            lower = height if tile_y == tiles_y - 1 else min(height, upper + tile_h)
            if right <= left or lower <= upper:
                continue
            box = (left, upper, right, lower)
            tile = image.crop(box)
            equalized = ImageOps.equalize(tile)
            blended = (
                equalized
                if blend_alpha >= 1.0
                else Image.blend(tile, equalized, blend_alpha)
            )
            output.paste(blended, box)
    return output


def _load_paired_grayscale(
    *,
    paired_source_payload: bytes,
    target_size: tuple[int, int],
):
    (
        Image,
        _ImageChops,
        _ImageFilter,
        _ImageOps,
        _ImageStat,
        UnidentifiedImageError,
    ) = _require_image_lib()
    try:
        with Image.open(BytesIO(paired_source_payload)) as opened:
            paired_grayscale = opened.convert("RGB").convert("L")
    except UnidentifiedImageError:
        return None
    if paired_grayscale.size != target_size:
        paired_grayscale = paired_grayscale.resize(
            target_size,
            resample=Image.Resampling.BICUBIC,
        )
    return paired_grayscale.transpose(Image.Transpose.FLIP_LEFT_RIGHT)


def _apply_bleed_through_reduction(
    image,
    *,
    params_json: Mapping[str, object],
    paired_source_payload: bytes | None,
) -> tuple[object, bool, bool]:
    Image, ImageChops, ImageFilter, _ImageOps, _ImageStat, _UnidentifiedImageError = (
        _require_image_lib()
    )
    bleed_mode = _resolve_bleed_mode(params_json)
    if bleed_mode == "OFF":
        return image, False, False

    pair_available = bool(paired_source_payload)
    if pair_available and isinstance(paired_source_payload, bytes):
        paired = _load_paired_grayscale(
            paired_source_payload=paired_source_payload,
            target_size=image.size,
        )
        if paired is not None:
            sigma = float(params_json.get("bleed_pair_gaussian_sigma_px", 9.0))
            weight = float(params_json.get("bleed_pair_weight", 0.25))
            clamped_weight = min(1.0, max(0.0, weight))
            paired_background = paired.filter(
                ImageFilter.GaussianBlur(radius=max(0.5, sigma))
            )
            paired_ink = ImageChops.invert(paired_background)
            suppression = paired_ink.point(
                lambda value, factor=clamped_weight: int(round(value * factor))
            )
            corrected = ImageChops.add(image, suppression)
            return corrected, True, True

    if _resolve_bool_param(
        params_json.get("bleed_single_fallback_enabled"),
        default=False,
    ):
        fallback_sigma = float(params_json.get("bleed_single_fallback_sigma_px", 5.5))
        low_frequency = image.filter(
            ImageFilter.GaussianBlur(radius=max(0.5, fallback_sigma))
        )
        baseline = Image.new("L", image.size, color=128)
        corrected = ImageChops.add(ImageChops.subtract(image, low_frequency), baseline)
        return corrected, False, pair_available

    return image, False, pair_available


def _adaptive_binarize(
    image,
    *,
    radius_px: float,
    offset: float,
):
    (
        Image,
        _ImageChops,
        ImageFilter,
        _ImageOps,
        _ImageStat,
        _UnidentifiedImageError,
    ) = _require_image_lib()
    safe_radius = max(1, int(round(radius_px)))
    clamped_offset = min(64, max(0, int(round(offset))))
    local_mean = image.filter(ImageFilter.BoxBlur(radius=float(safe_radius)))
    source_bytes = image.tobytes()
    local_bytes = local_mean.tobytes()
    output = bytearray(len(source_bytes))
    for index, (source_value, local_value) in enumerate(
        zip(source_bytes, local_bytes, strict=False)
    ):
        threshold = max(0, min(255, local_value - clamped_offset))
        output[index] = 0 if source_value < threshold else 255
    return Image.frombytes("L", image.size, bytes(output))


def _derive_quality_gate_and_warnings(
    *,
    dpi_estimate: int | None,
    skew_angle_deg: float,
    blur_score: float,
    contrast_score: float,
    params: Mapping[str, object],
) -> tuple[PreprocessQualityGateStatus, list[str]]:
    warnings: list[str] = []
    if dpi_estimate is None or dpi_estimate < 200:
        warnings.append(_WARNING_LOW_DPI)
    if abs(skew_angle_deg) >= float(params.get("warn_high_skew_abs_angle_deg", 3.0)):
        warnings.append(_WARNING_HIGH_SKEW)
    if blur_score < float(params.get("warn_high_blur_threshold", 0.20)):
        warnings.append(_WARNING_HIGH_BLUR)
    if contrast_score < float(params.get("warn_low_contrast_threshold", 0.25)):
        warnings.append(_WARNING_LOW_CONTRAST)
    if dpi_estimate is None:
        return "REVIEW_REQUIRED", sorted(set(warnings))
    if dpi_estimate < 150:
        return "BLOCKED", sorted(set(warnings))
    if dpi_estimate < 200:
        return "REVIEW_REQUIRED", sorted(set(warnings))
    return "PASS", sorted(set(warnings))


def process_preprocess_page_bytes(
    *,
    source_payload: bytes,
    source_dpi: int | None,
    source_width: int,
    source_height: int,
    params_json: Mapping[str, object],
    paired_source_payload: bytes | None = None,
) -> PreprocessPageOutcome:
    (
        Image,
        ImageChops,
        ImageFilter,
        _ImageOps,
        ImageStat,
        UnidentifiedImageError,
    ) = _require_image_lib()
    started = time.perf_counter()
    try:
        with Image.open(BytesIO(source_payload)) as opened:
            grayscale = opened.convert("RGB").convert("L")
    except UnidentifiedImageError as error:
        raise PreprocessPipelineError("Source page payload is not a decodable image.") from error

    # 2) Resolution standardization / derived dpi estimate.
    dpi_estimate = _estimate_dpi(
        source_dpi=source_dpi,
        width_px=max(1, source_width),
        height_px=max(1, source_height),
        params=params_json,
    )

    # 3) Deskew.
    max_angle = float(params_json.get("deskew_max_abs_angle_deg", 12.0))
    step = float(params_json.get("deskew_step_deg", 0.25))
    skew_angle = _measure_skew_angle(
        grayscale_image=grayscale,
        max_abs_angle_deg=max_angle,
        step_deg=step,
    )
    apply_min = float(params_json.get("deskew_apply_min_abs_angle_deg", 0.15))
    if abs(skew_angle) >= apply_min:
        deskewed = grayscale.rotate(
            -skew_angle,
            resample=Image.Resampling.BICUBIC,
            expand=False,
            fillcolor=255,
        )
    else:
        deskewed = grayscale.copy()

    # 4) Background normalization.
    sigma = float(params_json.get("background_norm_gaussian_sigma_px", 21.0))
    background = deskewed.filter(ImageFilter.GaussianBlur(radius=max(0.5, sigma)))
    baseline = Image.new("L", deskewed.size, color=128)
    normalized = ImageChops.add(ImageChops.subtract(deskewed, background), baseline)
    bleed_mode = _resolve_bleed_mode(params_json)
    normalized, bleed_pair_used, bleed_pair_available = _apply_bleed_through_reduction(
        normalized,
        params_json=params_json,
        paired_source_payload=paired_source_payload,
    )

    # 5) Denoise.
    median_kernel = _resolve_median_kernel(params_json.get("denoise_median_kernel_px", 3))
    denoised = normalized.filter(ImageFilter.MedianFilter(size=median_kernel))

    # 6) Local contrast equalization.
    tile_grid = _resolve_tile_grid(params_json.get("contrast_clahe_tile_grid", [8, 8]))
    clip_limit = float(params_json.get("contrast_clahe_clip_limit", 2.0))
    contrasted = _contrast_equalize_tiles(
        denoised,
        tile_grid=tile_grid,
        clip_limit=clip_limit,
    )

    # 7) Persist output payload hash.
    out = BytesIO()
    contrasted.save(out, format="PNG", optimize=False, compress_level=9)
    gray_png = out.getvalue()
    sha256_gray = hashlib.sha256(gray_png).hexdigest()

    # Metrics contract.
    laplacian = deskewed.filter(
        ImageFilter.Kernel(
            size=(3, 3),
            kernel=(0, 1, 0, 1, -4, 1, 0, 1, 0),
            scale=1,
            offset=128,
        )
    )
    blur_variance = float(ImageStat.Stat(laplacian).var[0])
    blur_score = min(1.0, max(0.0, blur_variance / (blur_variance + 3200.0)))

    low_freq = normalized.filter(ImageFilter.GaussianBlur(radius=max(1.0, sigma / 2.0)))
    bg_variance = float(ImageStat.Stat(low_freq).var[0])
    background_variance = min(1.0, max(0.0, bg_variance / (bg_variance + 2500.0)))

    contrasted_hist = contrasted.histogram()
    p10 = _percentile_from_histogram(contrasted_hist, 0.10)
    p90 = _percentile_from_histogram(contrasted_hist, 0.90)
    contrast_score = min(1.0, max(0.0, float(p90 - p10) / 255.0))

    median = contrasted.filter(ImageFilter.MedianFilter(size=3))
    abs_diff = ImageChops.difference(contrasted, median)
    diff_hist = abs_diff.histogram()
    mad = _percentile_from_histogram(diff_hist, 0.50)
    noise_score = min(1.0, max(0.0, float(mad) / 32.0))

    quality_gate_status, warnings = _derive_quality_gate_and_warnings(
        dpi_estimate=dpi_estimate,
        skew_angle_deg=abs(skew_angle),
        blur_score=blur_score,
        contrast_score=contrast_score,
        params=params_json,
    )
    if (
        bleed_mode == "PAIRED_PREFERRED"
        and not bleed_pair_used
        and not bleed_pair_available
    ):
        warnings.append(_WARNING_BLEED_PAIR_UNAVAILABLE)
    warnings = sorted(set(warnings))

    binary_enabled = _resolve_bool_param(
        params_json.get("binary_output_enabled"),
        default=False,
    )
    bin_png: bytes | None = None
    sha256_bin: str | None = None
    if binary_enabled:
        adaptive_radius = float(params_json.get("binary_adaptive_radius_px", 11.0))
        adaptive_offset = float(params_json.get("binary_adaptive_offset", 9.0))
        binary = _adaptive_binarize(
            contrasted,
            radius_px=adaptive_radius,
            offset=adaptive_offset,
        )
        binary_out = BytesIO()
        binary.save(binary_out, format="PNG", optimize=False, compress_level=9)
        bin_png = binary_out.getvalue()
        sha256_bin = hashlib.sha256(bin_png).hexdigest()

    processing_time_ms = int(round((time.perf_counter() - started) * 1000))
    metrics = {
        "skew_angle_deg": float(f"{abs(skew_angle):.4f}"),
        "dpi_estimate": dpi_estimate,
        "blur_score": float(f"{blur_score:.6f}"),
        "background_variance": float(f"{background_variance:.6f}"),
        "contrast_score": float(f"{contrast_score:.6f}"),
        "noise_score": float(f"{noise_score:.6f}"),
        "processing_time_ms": processing_time_ms,
        "binary_output_enabled": binary_enabled,
        "bleed_through_mode": bleed_mode,
        "bleed_through_pair_available": bleed_pair_available,
        "bleed_through_pair_used": bleed_pair_used,
        "warnings": list(warnings),
    }

    return PreprocessPageOutcome(
        gray_png_bytes=gray_png,
        bin_png_bytes=bin_png,
        metrics_json=metrics,
        warnings_json=warnings,
        quality_gate_status=quality_gate_status,
        sha256_gray=sha256_gray,
        sha256_bin=sha256_bin,
    )


def build_preprocess_manifest(
    *,
    run_id: str,
    project_id: str,
    document_id: str,
    profile_id: str,
    profile_version: str,
    profile_revision: int,
    profile_params_hash: str,
    params_json: Mapping[str, object],
    params_hash: str,
    pipeline_version: str,
    container_digest: str,
    source_page_count: int,
    manifest_generated_at: datetime | None,
    items: list[dict[str, Any]],
) -> bytes:
    generated_at = manifest_generated_at or datetime.now(UTC)
    generated_at_iso = generated_at.isoformat().replace("+00:00", "Z")
    payload = {
        "schemaVersion": 2,
        "kind": "preprocess-manifest",
        "generatedAt": generated_at_iso,
        "projectId": project_id,
        "documentId": document_id,
        "runId": run_id,
        "profile": {
            "id": profile_id,
            "version": profile_version,
            "revision": profile_revision,
            "registryParamsHash": profile_params_hash,
        },
        "paramsHash": params_hash,
        "pipelineVersion": pipeline_version,
        "containerDigest": container_digest,
        "paramsJson": canonicalize_params_dict(dict(params_json)),
        "source": {
            "pageCount": max(0, int(source_page_count)),
            "lineage": "source-pages-immutable",
        },
        "items": items,
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return encoded + b"\n"


__all__ = [
    "PreprocessProfileDefinition",
    "PreprocessPageOutcome",
    "PreprocessPipelineError",
    "build_preprocess_manifest",
    "canonicalize_params_dict",
    "expand_profile_params",
    "get_preprocess_profile_definition",
    "hash_params_canonical",
    "list_preprocess_profile_definitions",
    "normalize_profile_id",
    "process_preprocess_page_bytes",
    "serialize_params_canonical",
]
