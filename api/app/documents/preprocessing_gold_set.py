from __future__ import annotations

import base64
import json
import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Literal, Mapping

from app.documents.preprocessing import (
    expand_profile_params,
    hash_params_canonical,
    process_preprocess_page_bytes,
    serialize_params_canonical,
)

GoldSetComparisonMode = Literal["HASH", "SSIM"]

GOLD_SET_PROJECT_ID = "goldset-project"
GOLD_SET_DOCUMENT_ID = "goldset-document"


@dataclass(frozen=True)
class PreprocessGoldSetFixture:
    fixture_id: str
    seed: int
    scenario: str
    width: int
    height: int
    source_dpi: int | None
    tags: tuple[str, ...]
    notes: str | None = None


@dataclass(frozen=True)
class PreprocessGoldSetRecord:
    record_id: str
    fixture_id: str
    profile_id: str
    paired_fixture_id: str | None
    comparison_mode: GoldSetComparisonMode
    pipeline_version: str
    container_digest: str
    profile_version: str
    profile_revision: int
    params_json: dict[str, object]
    params_hash: str
    expected_gray_sha256: str
    expected_bin_sha256: str | None
    require_binary_output: bool
    expected_quality_gate_status: str
    required_warnings: tuple[str, ...]
    forbidden_warnings: tuple[str, ...]
    metric_floors: dict[str, float]
    metric_ceilings: dict[str, float]
    ssim_min: float | None = None
    reference_gray_png_base64: str | None = None


@dataclass(frozen=True)
class PreprocessGoldSetManifest:
    schema_version: int
    fixture_pack_id: str
    fixture_pack_version: str
    generated_at: str
    generated_by: str
    approval: Mapping[str, str]
    records: tuple[PreprocessGoldSetRecord, ...]


@dataclass(frozen=True)
class PreprocessGoldSetRecordResult:
    record_id: str
    fixture_id: str
    profile_id: str
    actual_gray_sha256: str
    actual_bin_sha256: str | None
    actual_quality_gate_status: str
    warnings: tuple[str, ...]
    numeric_metrics: Mapping[str, float]
    failures: tuple[str, ...]


@dataclass(frozen=True)
class PreprocessGoldSetEvaluation:
    generated_at: str
    record_results: tuple[PreprocessGoldSetRecordResult, ...]

    @property
    def failures(self) -> tuple[str, ...]:
        failures: list[str] = []
        for result in self.record_results:
            failures.extend(result.failures)
        return tuple(failures)

    @property
    def passed(self) -> bool:
        return len(self.failures) == 0

    def format_failure_summary(self) -> str:
        if self.passed:
            return "No preprocessing gold-set drift detected."
        lines = ["Preprocessing gold-set regression failures:"]
        lines.extend(f"- {failure}" for failure in self.failures)
        return "\n".join(lines)


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _require_image_lib():
    try:
        from PIL import Image, ImageChops, ImageDraw, ImageFilter, UnidentifiedImageError
    except ModuleNotFoundError as error:
        raise RuntimeError("Pillow is required for preprocessing gold-set harness.") from error
    return Image, ImageChops, ImageDraw, ImageFilter, UnidentifiedImageError


def _apply_texture_noise(image, *, rng: random.Random, center: int, spread: int):  # type: ignore[no-untyped-def]
    pixels = image.load()
    if pixels is None:
        return image
    width, height = image.size
    for y in range(height):
        for x in range(width):
            checker = ((x // 7) + (y // 7)) % 2
            drift = 5 if checker else -5
            value = center + drift + rng.randint(-spread, spread)
            pixels[x, y] = max(0, min(255, value))
    return image


def render_preprocess_gold_set_fixture(fixture: PreprocessGoldSetFixture) -> bytes:
    Image, ImageChops, ImageDraw, ImageFilter, _ = _require_image_lib()
    rng = random.Random(fixture.seed)
    width = max(256, int(fixture.width))
    height = max(256, int(fixture.height))
    scenario = fixture.scenario.strip().lower()

    if scenario == "binarization_harm":
        image = Image.new("L", (width, height), color=188)
        image = _apply_texture_noise(image, rng=rng, center=188, spread=12)
    elif scenario == "low_contrast":
        image = Image.new("L", (width, height), color=195)
        image = _apply_texture_noise(image, rng=rng, center=194, spread=9)
    else:
        image = Image.new("L", (width, height), color=247)
        image = _apply_texture_noise(image, rng=rng, center=244, spread=4)

    draw = ImageDraw.Draw(image)
    if scenario == "binarization_help":
        line_count = 28
    elif scenario == "binarization_harm":
        line_count = 30
    else:
        line_count = 42
    line_height = max(14, height // (line_count + 6))
    base_y = 32
    ink_range = (18, 80)
    if scenario in {"low_contrast", "binarization_harm", "faded_ink"}:
        ink_range = (128, 178)
    elif scenario == "binarization_help":
        ink_range = (35, 110)

    for line_index in range(line_count):
        y = base_y + (line_index * line_height) + rng.randint(-2, 2)
        if y >= height - 16:
            break
        if scenario == "binarization_help":
            segments = 3 + rng.randint(0, 2)
        else:
            segments = 4 + rng.randint(0, 3)
        cursor = 24 + rng.randint(0, 18)
        for _ in range(segments):
            if scenario == "binarization_help":
                run = rng.randint(max(14, width // 16), max(30, width // 7))
            else:
                run = rng.randint(max(18, width // 12), max(40, width // 5))
            x0 = cursor
            x1 = min(width - 20, cursor + run)
            if x1 <= x0:
                continue
            stroke = (
                1
                if scenario in {"low_contrast", "binarization_harm", "binarization_help"}
                else 2
            )
            draw.line(
                (x0, y, x1, y + rng.randint(-1, 1)),
                fill=rng.randint(*ink_range),
                width=stroke,
            )
            cursor = x1 + rng.randint(8, 20)
            if cursor >= width - 24:
                break

    # Stamp marks and digitized noise.
    for _ in range(18):
        x = rng.randint(24, width - 28)
        y = rng.randint(24, height - 28)
        radius = rng.randint(3, 9)
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            outline=rng.randint(*ink_range),
            width=1,
        )

    if scenario in {"bleed_recto", "bleed_verso"}:
        ghost = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT).filter(
            ImageFilter.GaussianBlur(radius=1.8)
        )
        ghost_ink = ghost.point(lambda value: int(round((255 - value) * 0.22)))
        image = ImageChops.add(image, ghost_ink)

    if scenario in {"skew", "high_skew"}:
        skew_deg = 2.4 if scenario == "skew" else 4.8
        image = image.rotate(skew_deg, resample=Image.Resampling.BICUBIC, fillcolor=245)

    if scenario in {"blur", "binarization_harm"}:
        radius = 1.2 if scenario == "blur" else 1.6
        image = image.filter(ImageFilter.GaussianBlur(radius=radius))

    if scenario == "faded_ink":
        image = image.point(lambda value: min(255, int(round(value * 1.04))))

    if scenario == "binarization_help":
        image = image.point(lambda value: max(0, int(round(value * 0.96))))

    output = BytesIO()
    image.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue()


def _binary_black_ratio(payload: bytes) -> float:
    Image, _, _, _, UnidentifiedImageError = _require_image_lib()
    try:
        with Image.open(BytesIO(payload)) as opened:
            grayscale = opened.convert("L")
    except UnidentifiedImageError:
        return 0.0
    values = grayscale.tobytes()
    if not values:
        return 0.0
    black = sum(1 for value in values if value < 128)
    return black / float(len(values))


def _global_ssim(reference_png: bytes, candidate_png: bytes) -> float:
    Image, _, _, _, UnidentifiedImageError = _require_image_lib()
    try:
        with Image.open(BytesIO(reference_png)) as reference:
            ref_gray = reference.convert("L")
        with Image.open(BytesIO(candidate_png)) as candidate:
            cand_gray = candidate.convert("L")
    except UnidentifiedImageError as error:
        raise RuntimeError("SSIM comparison payload is not a decodable image.") from error

    if ref_gray.size != cand_gray.size:
        cand_gray = cand_gray.resize(ref_gray.size, resample=Image.Resampling.BICUBIC)

    left = ref_gray.tobytes()
    right = cand_gray.tobytes()
    sample_count = min(len(left), len(right))
    if sample_count == 0:
        return 1.0

    mu_x = sum(left) / sample_count
    mu_y = sum(right) / sample_count
    var_x = sum((value - mu_x) ** 2 for value in left) / sample_count
    var_y = sum((value - mu_y) ** 2 for value in right) / sample_count
    cov = sum(
        (left[index] - mu_x) * (right[index] - mu_y) for index in range(sample_count)
    ) / sample_count

    c1 = (0.01 * 255.0) ** 2
    c2 = (0.03 * 255.0) ** 2
    numerator = (2.0 * mu_x * mu_y + c1) * (2.0 * cov + c2)
    denominator = (mu_x**2 + mu_y**2 + c1) * (var_x + var_y + c2)
    if denominator == 0:
        return 1.0
    return max(0.0, min(1.0, numerator / denominator))


def _as_float_dict(value: object) -> dict[str, float]:
    if not isinstance(value, Mapping):
        return {}
    parsed: dict[str, float] = {}
    for key, raw in value.items():
        if not isinstance(key, str):
            continue
        if isinstance(raw, bool):
            continue
        if isinstance(raw, (float, int)) and math.isfinite(float(raw)):
            parsed[key] = float(raw)
    return parsed


def _parse_fixture(value: object) -> PreprocessGoldSetFixture:
    if not isinstance(value, Mapping):
        raise ValueError("Fixture entry must be an object.")
    fixture_id = str(value.get("fixtureId", "")).strip()
    if not fixture_id:
        raise ValueError("Fixture entry requires fixtureId.")
    tags_raw = value.get("tags")
    tags: tuple[str, ...]
    if isinstance(tags_raw, list):
        tags = tuple(str(item).strip() for item in tags_raw if str(item).strip())
    else:
        tags = ()
    source_dpi_raw = value.get("sourceDpi")
    source_dpi = (
        int(source_dpi_raw)
        if isinstance(source_dpi_raw, int) and source_dpi_raw > 0
        else None
    )
    return PreprocessGoldSetFixture(
        fixture_id=fixture_id,
        seed=int(value.get("seed", 0)),
        scenario=str(value.get("scenario", "baseline")),
        width=int(value.get("width", 720)),
        height=int(value.get("height", 960)),
        source_dpi=source_dpi,
        tags=tags,
        notes=str(value.get("notes")).strip() if value.get("notes") else None,
    )


def load_preprocess_gold_set_fixture_pack(path: Path) -> tuple[str, str, tuple[PreprocessGoldSetFixture, ...]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("Fixture pack must be a JSON object.")
    fixture_pack_id = str(raw.get("fixturePackId", "")).strip()
    fixture_pack_version = str(raw.get("fixturePackVersion", "")).strip()
    if not fixture_pack_id or not fixture_pack_version:
        raise ValueError("Fixture pack requires fixturePackId and fixturePackVersion.")
    fixtures_raw = raw.get("fixtures")
    if not isinstance(fixtures_raw, list) or not fixtures_raw:
        raise ValueError("Fixture pack requires a non-empty fixtures array.")
    fixtures = tuple(_parse_fixture(item) for item in fixtures_raw)
    return fixture_pack_id, fixture_pack_version, fixtures


def _parse_record(value: object) -> PreprocessGoldSetRecord:
    if not isinstance(value, Mapping):
        raise ValueError("Baseline record must be an object.")
    required_id = str(value.get("recordId", "")).strip()
    fixture_id = str(value.get("fixtureId", "")).strip()
    profile_id = str(value.get("profileId", "")).strip().upper()
    if not required_id or not fixture_id or not profile_id:
        raise ValueError("Baseline record requires recordId, fixtureId, and profileId.")
    params = value.get("paramsJson")
    if not isinstance(params, Mapping):
        raise ValueError(f"Record {required_id} requires paramsJson.")
    metric_floors = _as_float_dict(value.get("metricFloors"))
    metric_ceilings = _as_float_dict(value.get("metricCeilings"))
    required_warnings_raw = value.get("requiredWarnings")
    forbidden_warnings_raw = value.get("forbiddenWarnings")
    comparison_mode_raw = str(value.get("comparisonMode", "HASH")).strip().upper()
    if comparison_mode_raw not in {"HASH", "SSIM"}:
        raise ValueError(f"Record {required_id} has unsupported comparisonMode.")
    return PreprocessGoldSetRecord(
        record_id=required_id,
        fixture_id=fixture_id,
        profile_id=profile_id,
        paired_fixture_id=(
            str(value.get("pairedFixtureId", "")).strip() or None
            if value.get("pairedFixtureId") is not None
            else None
        ),
        comparison_mode=comparison_mode_raw,  # type: ignore[arg-type]
        pipeline_version=str(value.get("pipelineVersion", "")).strip(),
        container_digest=str(value.get("containerDigest", "")).strip(),
        profile_version=str(value.get("profileVersion", "")).strip(),
        profile_revision=int(value.get("profileRevision", 0)),
        params_json=json.loads(_canonical_json(params)),
        params_hash=str(value.get("paramsHash", "")).strip(),
        expected_gray_sha256=str(value.get("expectedGraySha256", "")).strip(),
        expected_bin_sha256=(
            str(value.get("expectedBinSha256", "")).strip() or None
            if value.get("expectedBinSha256") is not None
            else None
        ),
        require_binary_output=bool(value.get("requireBinaryOutput", False)),
        expected_quality_gate_status=str(value.get("expectedQualityGateStatus", "")).strip(),
        required_warnings=tuple(
            str(item).strip()
            for item in required_warnings_raw
            if str(item).strip()
        )
        if isinstance(required_warnings_raw, list)
        else (),
        forbidden_warnings=tuple(
            str(item).strip()
            for item in forbidden_warnings_raw
            if str(item).strip()
        )
        if isinstance(forbidden_warnings_raw, list)
        else (),
        metric_floors=metric_floors,
        metric_ceilings=metric_ceilings,
        ssim_min=(
            float(value["ssimMin"])
            if isinstance(value.get("ssimMin"), (int, float))
            and math.isfinite(float(value["ssimMin"]))
            else None
        ),
        reference_gray_png_base64=(
            str(value.get("referenceGrayPngBase64", "")).strip() or None
            if value.get("referenceGrayPngBase64") is not None
            else None
        ),
    )


def load_preprocess_gold_set_manifest(path: Path) -> PreprocessGoldSetManifest:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("Baseline manifest must be a JSON object.")
    records_raw = raw.get("records")
    if not isinstance(records_raw, list) or not records_raw:
        raise ValueError("Baseline manifest requires a non-empty records array.")
    approval_raw = raw.get("approval")
    approval = approval_raw if isinstance(approval_raw, Mapping) else {}
    return PreprocessGoldSetManifest(
        schema_version=int(raw.get("schemaVersion", 0)),
        fixture_pack_id=str(raw.get("fixturePackId", "")).strip(),
        fixture_pack_version=str(raw.get("fixturePackVersion", "")).strip(),
        generated_at=str(raw.get("generatedAt", "")).strip(),
        generated_by=str(raw.get("generatedBy", "")).strip(),
        approval={str(key): str(value) for key, value in approval.items()},
        records=tuple(_parse_record(item) for item in records_raw),
    )


def _evaluate_record(
    *,
    fixture: PreprocessGoldSetFixture,
    fixture_index: Mapping[str, int],
    paired_fixture: PreprocessGoldSetFixture | None,
    record: PreprocessGoldSetRecord,
) -> PreprocessGoldSetRecordResult:
    failures: list[str] = []
    source_payload = render_preprocess_gold_set_fixture(fixture)
    paired_payload = (
        render_preprocess_gold_set_fixture(paired_fixture)
        if paired_fixture is not None
        else None
    )
    _, expanded_params = expand_profile_params(
        profile_id=record.profile_id,
        params_json=record.params_json,
    )
    canonical_params = serialize_params_canonical(expanded_params)
    actual_params_hash = hash_params_canonical(expanded_params)
    expected_canonical = serialize_params_canonical(record.params_json)
    if canonical_params != expected_canonical:
        failures.append(
            f"{record.record_id}: paramsJson is not canonical expanded profile params."
        )
    if actual_params_hash != record.params_hash:
        failures.append(
            f"{record.record_id}: params hash drift (expected {record.params_hash}, got {actual_params_hash})."
        )
    pipeline_version = str(expanded_params.get("algorithm_version", "")).strip()
    if record.pipeline_version and pipeline_version != record.pipeline_version:
        failures.append(
            f"{record.record_id}: pipelineVersion mismatch (expected {record.pipeline_version}, got {pipeline_version})."
        )

    outcome = process_preprocess_page_bytes(
        source_payload=source_payload,
        source_dpi=fixture.source_dpi,
        source_width=fixture.width,
        source_height=fixture.height,
        params_json=expanded_params,
        paired_source_payload=paired_payload,
    )
    if outcome.quality_gate_status != record.expected_quality_gate_status:
        failures.append(
            f"{record.record_id}: quality gate drift (expected {record.expected_quality_gate_status}, got {outcome.quality_gate_status})."
        )

    warnings = tuple(outcome.warnings_json)
    for warning in record.required_warnings:
        if warning not in warnings:
            failures.append(
                f"{record.record_id}: missing required warning {warning}."
            )
    for warning in record.forbidden_warnings:
        if warning in warnings:
            failures.append(
                f"{record.record_id}: forbidden warning {warning} present."
            )

    if record.comparison_mode == "HASH":
        if outcome.sha256_gray != record.expected_gray_sha256:
            failures.append(
                f"{record.record_id}: gray hash drift (expected {record.expected_gray_sha256}, got {outcome.sha256_gray})."
            )
    else:
        if record.ssim_min is None:
            failures.append(f"{record.record_id}: SSIM mode requires ssimMin.")
        if not record.reference_gray_png_base64:
            failures.append(
                f"{record.record_id}: SSIM mode requires referenceGrayPngBase64."
            )
        if record.reference_gray_png_base64 and record.ssim_min is not None:
            reference = base64.b64decode(record.reference_gray_png_base64)
            ssim = _global_ssim(reference, outcome.gray_png_bytes)
            if ssim < record.ssim_min:
                failures.append(
                    f"{record.record_id}: SSIM drift (minimum {record.ssim_min:.6f}, got {ssim:.6f})."
                )

    if record.require_binary_output:
        if outcome.bin_png_bytes is None or outcome.sha256_bin is None:
            failures.append(f"{record.record_id}: binary output required but missing.")
        elif record.expected_bin_sha256 and outcome.sha256_bin != record.expected_bin_sha256:
            failures.append(
                f"{record.record_id}: binary hash drift (expected {record.expected_bin_sha256}, got {outcome.sha256_bin})."
            )
    elif outcome.bin_png_bytes is not None:
        failures.append(f"{record.record_id}: unexpected binary output present.")

    numeric_metrics: dict[str, float] = {}
    for key, value in outcome.metrics_json.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            numeric_metrics[key] = float(value)
    if outcome.bin_png_bytes:
        numeric_metrics["binary_black_ratio"] = _binary_black_ratio(outcome.bin_png_bytes)

    for metric_name, floor in record.metric_floors.items():
        value = numeric_metrics.get(metric_name)
        if value is None:
            failures.append(f"{record.record_id}: metric {metric_name} missing for floor check.")
            continue
        if value < floor:
            failures.append(
                f"{record.record_id}: metric floor failed ({metric_name} expected >= {floor:.6f}, got {value:.6f})."
            )
    for metric_name, ceiling in record.metric_ceilings.items():
        value = numeric_metrics.get(metric_name)
        if value is None:
            failures.append(
                f"{record.record_id}: metric {metric_name} missing for ceiling check."
            )
            continue
        if value > ceiling:
            failures.append(
                f"{record.record_id}: metric ceiling failed ({metric_name} expected <= {ceiling:.6f}, got {value:.6f})."
            )

    page_index = fixture_index.get(record.fixture_id, -1)
    run_id = f"goldset-{record.record_id}"
    gray_key = (
        f"controlled/derived/{GOLD_SET_PROJECT_ID}/{GOLD_SET_DOCUMENT_ID}/preprocess/"
        f"{run_id}/gray/{page_index}.png"
    )
    if not gray_key.startswith(
        f"controlled/derived/{GOLD_SET_PROJECT_ID}/{GOLD_SET_DOCUMENT_ID}/preprocess/"
    ):
        failures.append(
            f"{record.record_id}: output key escaped preprocess derived prefix."
        )
    if record.require_binary_output:
        bin_key = (
            f"controlled/derived/{GOLD_SET_PROJECT_ID}/{GOLD_SET_DOCUMENT_ID}/preprocess/"
            f"{run_id}/bin/{page_index}.png"
        )
        if not bin_key.startswith(
            f"controlled/derived/{GOLD_SET_PROJECT_ID}/{GOLD_SET_DOCUMENT_ID}/preprocess/"
        ):
            failures.append(
                f"{record.record_id}: binary key escaped preprocess derived prefix."
            )

    return PreprocessGoldSetRecordResult(
        record_id=record.record_id,
        fixture_id=record.fixture_id,
        profile_id=record.profile_id,
        actual_gray_sha256=outcome.sha256_gray,
        actual_bin_sha256=outcome.sha256_bin,
        actual_quality_gate_status=outcome.quality_gate_status,
        warnings=warnings,
        numeric_metrics=numeric_metrics,
        failures=tuple(failures),
    )


def evaluate_preprocess_gold_set(
    *,
    fixture_pack_path: Path,
    baseline_manifest_path: Path,
) -> PreprocessGoldSetEvaluation:
    fixture_pack_id, fixture_pack_version, fixtures = load_preprocess_gold_set_fixture_pack(
        fixture_pack_path
    )
    manifest = load_preprocess_gold_set_manifest(baseline_manifest_path)
    if manifest.fixture_pack_id != fixture_pack_id:
        raise ValueError(
            f"Baseline fixturePackId mismatch: {manifest.fixture_pack_id} != {fixture_pack_id}"
        )
    if manifest.fixture_pack_version != fixture_pack_version:
        raise ValueError(
            "Baseline fixturePackVersion mismatch: "
            f"{manifest.fixture_pack_version} != {fixture_pack_version}"
        )

    fixture_by_id = {fixture.fixture_id: fixture for fixture in fixtures}
    fixture_index = {fixture.fixture_id: index for index, fixture in enumerate(fixtures)}
    results: list[PreprocessGoldSetRecordResult] = []
    for record in manifest.records:
        fixture = fixture_by_id.get(record.fixture_id)
        if fixture is None:
            results.append(
                PreprocessGoldSetRecordResult(
                    record_id=record.record_id,
                    fixture_id=record.fixture_id,
                    profile_id=record.profile_id,
                    actual_gray_sha256="",
                    actual_bin_sha256=None,
                    actual_quality_gate_status="",
                    warnings=(),
                    numeric_metrics={},
                    failures=(f"{record.record_id}: fixture {record.fixture_id} is missing from fixture pack.",),
                )
            )
            continue
        paired_fixture = (
            fixture_by_id.get(record.paired_fixture_id)
            if record.paired_fixture_id
            else None
        )
        if record.paired_fixture_id and paired_fixture is None:
            results.append(
                PreprocessGoldSetRecordResult(
                    record_id=record.record_id,
                    fixture_id=record.fixture_id,
                    profile_id=record.profile_id,
                    actual_gray_sha256="",
                    actual_bin_sha256=None,
                    actual_quality_gate_status="",
                    warnings=(),
                    numeric_metrics={},
                    failures=(
                        f"{record.record_id}: paired fixture {record.paired_fixture_id} is missing from fixture pack.",
                    ),
                )
            )
            continue
        results.append(
            _evaluate_record(
                fixture=fixture,
                fixture_index=fixture_index,
                paired_fixture=paired_fixture,
                record=record,
            )
        )

    return PreprocessGoldSetEvaluation(
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        record_results=tuple(results),
    )


def write_preprocess_gold_set_artifact(
    *,
    evaluation: PreprocessGoldSetEvaluation,
    path: Path,
) -> None:
    payload = {
        "generatedAt": evaluation.generated_at,
        "passed": evaluation.passed,
        "failures": list(evaluation.failures),
        "records": [
            {
                "recordId": result.record_id,
                "fixtureId": result.fixture_id,
                "profileId": result.profile_id,
                "actualGraySha256": result.actual_gray_sha256,
                "actualBinSha256": result.actual_bin_sha256,
                "qualityGateStatus": result.actual_quality_gate_status,
                "warnings": list(result.warnings),
                "numericMetrics": dict(result.numeric_metrics),
                "failures": list(result.failures),
            }
            for result in evaluation.record_results
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def regenerate_preprocess_gold_set_manifest(
    *,
    fixture_pack_path: Path,
    baseline_manifest_path: Path,
    approved_by: str,
    approval_reference: str,
    approval_summary: str,
) -> None:
    fixture_pack_id, fixture_pack_version, fixtures = load_preprocess_gold_set_fixture_pack(
        fixture_pack_path
    )
    manifest = load_preprocess_gold_set_manifest(baseline_manifest_path)
    fixture_by_id = {fixture.fixture_id: fixture for fixture in fixtures}
    refreshed_records: list[dict[str, object]] = []
    for record in manifest.records:
        fixture = fixture_by_id.get(record.fixture_id)
        if fixture is None:
            raise ValueError(
                f"Cannot regenerate baseline: fixture {record.fixture_id} is missing."
            )
        paired_fixture = (
            fixture_by_id.get(record.paired_fixture_id)
            if record.paired_fixture_id
            else None
        )
        if record.paired_fixture_id and paired_fixture is None:
            raise ValueError(
                f"Cannot regenerate baseline: paired fixture {record.paired_fixture_id} is missing."
            )

        source_payload = render_preprocess_gold_set_fixture(fixture)
        paired_payload = (
            render_preprocess_gold_set_fixture(paired_fixture)
            if paired_fixture is not None
            else None
        )
        _, expanded_params = expand_profile_params(
            profile_id=record.profile_id,
            params_json=record.params_json,
        )
        outcome = process_preprocess_page_bytes(
            source_payload=source_payload,
            source_dpi=fixture.source_dpi,
            source_width=fixture.width,
            source_height=fixture.height,
            params_json=expanded_params,
            paired_source_payload=paired_payload,
        )

        entry: dict[str, object] = {
            "recordId": record.record_id,
            "fixtureId": record.fixture_id,
            "profileId": record.profile_id,
            "pairedFixtureId": record.paired_fixture_id,
            "comparisonMode": record.comparison_mode,
            "pipelineVersion": record.pipeline_version,
            "containerDigest": record.container_digest,
            "profileVersion": record.profile_version,
            "profileRevision": record.profile_revision,
            "paramsJson": expanded_params,
            "paramsHash": hash_params_canonical(expanded_params),
            "expectedGraySha256": outcome.sha256_gray,
            "expectedBinSha256": outcome.sha256_bin,
            "requireBinaryOutput": record.require_binary_output,
            "expectedQualityGateStatus": record.expected_quality_gate_status,
            "requiredWarnings": list(record.required_warnings),
            "forbiddenWarnings": list(record.forbidden_warnings),
            "metricFloors": dict(record.metric_floors),
            "metricCeilings": dict(record.metric_ceilings),
            "ssimMin": record.ssim_min,
        }
        if record.comparison_mode == "SSIM":
            entry["referenceGrayPngBase64"] = base64.b64encode(
                outcome.gray_png_bytes
            ).decode("ascii")
        refreshed_records.append(entry)

    payload = {
        "schemaVersion": manifest.schema_version or 1,
        "fixturePackId": fixture_pack_id,
        "fixturePackVersion": fixture_pack_version,
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "generatedBy": "scripts/update_preprocessing_gold_set_baseline.py",
        "approval": {
            "approvedBy": approved_by.strip(),
            "approvalReference": approval_reference.strip(),
            "approvalSummary": approval_summary.strip(),
        },
        "records": refreshed_records,
    }
    baseline_manifest_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=False) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "GOLD_SET_DOCUMENT_ID",
    "GOLD_SET_PROJECT_ID",
    "PreprocessGoldSetEvaluation",
    "PreprocessGoldSetFixture",
    "PreprocessGoldSetManifest",
    "PreprocessGoldSetRecord",
    "PreprocessGoldSetRecordResult",
    "evaluate_preprocess_gold_set",
    "load_preprocess_gold_set_fixture_pack",
    "load_preprocess_gold_set_manifest",
    "regenerate_preprocess_gold_set_manifest",
    "render_preprocess_gold_set_fixture",
    "write_preprocess_gold_set_artifact",
]
