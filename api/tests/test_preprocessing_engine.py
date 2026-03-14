from __future__ import annotations

import random
from io import BytesIO

import pytest

from app.documents.preprocessing import (
    expand_profile_params,
    get_preprocess_profile_definition,
    hash_params_canonical,
    list_preprocess_profile_definitions,
    process_preprocess_page_bytes,
)
from app.security.outbound import OutboundRequestBlockedError, validate_outbound_url

PIL = pytest.importorskip("PIL")
from PIL import Image, ImageDraw  # type: ignore[assignment]


def _build_seeded_page(seed: int, *, width: int = 720, height: int = 960) -> bytes:
    rng = random.Random(seed)
    image = Image.new("L", (width, height), color=255)
    draw = ImageDraw.Draw(image)

    for line_index in range(42):
        y = 40 + line_index * 20 + rng.randint(-2, 2)
        x0 = 20 + rng.randint(0, 25)
        x1 = width - 30 - rng.randint(0, 20)
        ink = 20 + rng.randint(0, 80)
        draw.line((x0, y, x1, y + rng.randint(-1, 1)), fill=ink, width=1)

    for _ in range(20):
        x = rng.randint(40, width - 60)
        y = rng.randint(40, height - 60)
        radius = rng.randint(4, 10)
        ink = 10 + rng.randint(0, 90)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=ink, width=1)

    rotated = image.rotate(2.75, resample=Image.Resampling.BICUBIC, fillcolor=255)
    output = BytesIO()
    rotated.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue()


def _build_low_contrast_texture_page(
    seed: int,
    *,
    width: int = 720,
    height: int = 960,
) -> bytes:
    rng = random.Random(seed)
    image = Image.new("L", (width, height), color=186)
    pixels = image.load()
    assert pixels is not None
    for y in range(height):
        for x in range(width):
            noise = rng.randint(-14, 14)
            band = ((x // 6) + (y // 6)) % 2
            value = 182 + (6 if band else -6) + noise
            pixels[x, y] = max(0, min(255, value))
    output = BytesIO()
    image.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue()


def _binary_black_ratio(payload: bytes) -> float:
    with Image.open(BytesIO(payload)) as opened:
        bitmap = opened.convert("L")
    pixels = bitmap.tobytes()
    if not pixels:
        return 0.0
    black = sum(1 for value in pixels if value < 128)
    return black / float(len(pixels))


def test_canonical_params_hash_is_stable_for_semantic_equivalents() -> None:
    _, expanded_a = expand_profile_params(
        profile_id="balanced",
        params_json={
            "deskew_apply_min_abs_angle_deg": 0.1500000000,
            "contrast_clahe_tile_grid": [8.0, 8],
            "nested": {"b": 2, "a": 1},
        },
    )
    _, expanded_b = expand_profile_params(
        profile_id="BALANCED",
        params_json={
            "nested": {"a": 1.0, "b": 2},
            "contrast_clahe_tile_grid": [8, 8.0],
            "deskew_apply_min_abs_angle_deg": 0.15,
        },
    )
    assert hash_params_canonical(expanded_a) == hash_params_canonical(expanded_b)


def test_profile_registry_definitions_are_versioned_and_hash_stable() -> None:
    definitions = list_preprocess_profile_definitions()
    assert [entry.profile_id for entry in definitions] == [
        "BALANCED",
        "CONSERVATIVE",
        "AGGRESSIVE",
        "BLEED_THROUGH",
    ]
    assert all(entry.profile_version == "v1" for entry in definitions)
    assert all(entry.profile_revision == 2 for entry in definitions)
    assert all(entry.supersedes_profile_id is not None for entry in definitions)
    assert all(entry.supersedes_profile_revision == 1 for entry in definitions)
    assert all(len(entry.params_hash) == 64 for entry in definitions)

    aggressive = get_preprocess_profile_definition("aggressive")
    assert aggressive.is_advanced is True
    assert aggressive.is_gated is True
    bleed = get_preprocess_profile_definition("bleed_through")
    assert bleed.is_advanced is True
    assert bleed.is_gated is True


def test_profile_registry_hash_matches_default_expanded_params() -> None:
    for definition in list_preprocess_profile_definitions():
        _, expanded = expand_profile_params(profile_id=definition.profile_id, params_json=None)
        assert hash_params_canonical(expanded) == definition.params_hash


def test_deskew_stability_is_deterministic_on_repeat_runs() -> None:
    _, params = expand_profile_params(profile_id="BALANCED", params_json={})
    payload = _build_seeded_page(1234)

    first = process_preprocess_page_bytes(
        source_payload=payload,
        source_dpi=300,
        source_width=720,
        source_height=960,
        params_json=params,
    )
    second = process_preprocess_page_bytes(
        source_payload=payload,
        source_dpi=300,
        source_width=720,
        source_height=960,
        params_json=params,
    )

    assert first.sha256_gray == second.sha256_gray
    assert first.metrics_json["skew_angle_deg"] == second.metrics_json["skew_angle_deg"]
    assert float(first.metrics_json["skew_angle_deg"]) <= 12.0


def test_binary_output_is_profile_controlled() -> None:
    payload = _build_seeded_page(412)
    _, balanced_params = expand_profile_params(profile_id="BALANCED", params_json={})
    _, aggressive_params = expand_profile_params(profile_id="AGGRESSIVE", params_json={})

    balanced = process_preprocess_page_bytes(
        source_payload=payload,
        source_dpi=300,
        source_width=720,
        source_height=960,
        params_json=balanced_params,
    )
    aggressive = process_preprocess_page_bytes(
        source_payload=payload,
        source_dpi=300,
        source_width=720,
        source_height=960,
        params_json=aggressive_params,
    )

    assert balanced.bin_png_bytes is None
    assert balanced.sha256_bin is None
    assert aggressive.bin_png_bytes is not None
    assert aggressive.sha256_bin is not None
    assert len(aggressive.sha256_bin) == 64


def test_binarization_regression_covers_helpful_and_harmful_pages() -> None:
    _, aggressive_params = expand_profile_params(profile_id="AGGRESSIVE", params_json={})
    helpful_payload = _build_seeded_page(2024)
    harmful_payload = _build_low_contrast_texture_page(2025)

    helpful = process_preprocess_page_bytes(
        source_payload=helpful_payload,
        source_dpi=300,
        source_width=720,
        source_height=960,
        params_json=aggressive_params,
    )
    harmful = process_preprocess_page_bytes(
        source_payload=harmful_payload,
        source_dpi=300,
        source_width=720,
        source_height=960,
        params_json=aggressive_params,
    )

    assert helpful.bin_png_bytes is not None
    assert harmful.bin_png_bytes is not None
    helpful_black_ratio = _binary_black_ratio(helpful.bin_png_bytes)
    harmful_black_ratio = _binary_black_ratio(harmful.bin_png_bytes)
    assert 0.01 <= helpful_black_ratio <= 0.45
    assert harmful_black_ratio >= helpful_black_ratio + 0.08


def test_bleed_through_profile_pair_availability_is_explicit() -> None:
    _, bleed_params = expand_profile_params(profile_id="BLEED_THROUGH", params_json={})
    payload = _build_seeded_page(177)
    pair_payload = _build_seeded_page(178)

    paired = process_preprocess_page_bytes(
        source_payload=payload,
        source_dpi=300,
        source_width=720,
        source_height=960,
        params_json=bleed_params,
        paired_source_payload=pair_payload,
    )
    missing_pair = process_preprocess_page_bytes(
        source_payload=payload,
        source_dpi=300,
        source_width=720,
        source_height=960,
        params_json=bleed_params,
        paired_source_payload=None,
    )

    assert paired.metrics_json["bleed_through_pair_available"] is True
    assert paired.metrics_json["bleed_through_pair_used"] is True
    assert "BLEED_PAIR_UNAVAILABLE" not in paired.warnings_json
    assert missing_pair.metrics_json["bleed_through_pair_available"] is False
    assert missing_pair.metrics_json["bleed_through_pair_used"] is False
    assert "BLEED_PAIR_UNAVAILABLE" in missing_pair.warnings_json


def test_bleed_through_runtime_stays_within_performance_gate() -> None:
    _, balanced_params = expand_profile_params(profile_id="BALANCED", params_json={})
    _, bleed_params = expand_profile_params(profile_id="BLEED_THROUGH", params_json={})
    payload = _build_seeded_page(337)
    pair_payload = _build_seeded_page(338)

    balanced = process_preprocess_page_bytes(
        source_payload=payload,
        source_dpi=300,
        source_width=720,
        source_height=960,
        params_json=balanced_params,
    )
    bleed = process_preprocess_page_bytes(
        source_payload=payload,
        source_dpi=300,
        source_width=720,
        source_height=960,
        params_json=bleed_params,
        paired_source_payload=pair_payload,
    )

    balanced_ms = int(balanced.metrics_json["processing_time_ms"])
    bleed_ms = int(bleed.metrics_json["processing_time_ms"])
    assert bleed_ms <= max(2500, balanced_ms * 4 + 250)


def test_preprocess_jobs_remain_under_no_egress_policy() -> None:
    with pytest.raises(OutboundRequestBlockedError):
        validate_outbound_url(
            method="GET",
            url="https://example.com/blocked",
            purpose="preprocess_job_guard_test",
        )
