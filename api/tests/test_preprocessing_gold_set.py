from __future__ import annotations

import json
from pathlib import Path

from app.documents.preprocessing_gold_set import (
    evaluate_preprocess_gold_set,
    load_preprocess_gold_set_manifest,
    write_preprocess_gold_set_artifact,
)

FIXTURE_PACK_PATH = (
    Path(__file__).parent / "fixtures" / "preprocessing-gold-set" / "fixture-pack.v1.json"
)
BASELINE_MANIFEST_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "preprocessing-gold-set"
    / "baseline-manifest.v1.json"
)
EVALUATION_ARTIFACT_PATH = (
    Path(__file__).parent
    / ".artifacts"
    / "preprocessing-gold-set"
    / "last-evaluation.json"
)


def _evaluate_current_baseline() -> tuple[bool, str]:
    evaluation = evaluate_preprocess_gold_set(
        fixture_pack_path=FIXTURE_PACK_PATH,
        baseline_manifest_path=BASELINE_MANIFEST_PATH,
    )
    write_preprocess_gold_set_artifact(
        evaluation=evaluation,
        path=EVALUATION_ARTIFACT_PATH,
    )
    return evaluation.passed, evaluation.format_failure_summary()


def test_preprocessing_gold_set_baseline_manifest_is_current() -> None:
    passed, failure_summary = _evaluate_current_baseline()
    assert passed, failure_summary


def test_preprocessing_gold_set_harness_detects_unapproved_hash_drift(
    tmp_path: Path,
) -> None:
    manifest = load_preprocess_gold_set_manifest(BASELINE_MANIFEST_PATH)
    mutated = json.loads(BASELINE_MANIFEST_PATH.read_text(encoding="utf-8"))
    mutated["records"][0]["expectedGraySha256"] = "0" * 64
    mutated_path = tmp_path / "mutated-baseline.json"
    mutated_path.write_text(json.dumps(mutated, indent=2) + "\n", encoding="utf-8")

    evaluation = evaluate_preprocess_gold_set(
        fixture_pack_path=FIXTURE_PACK_PATH,
        baseline_manifest_path=mutated_path,
    )

    assert manifest.records[0].record_id in evaluation.format_failure_summary()
    assert not evaluation.passed
    assert any("hash drift" in failure for failure in evaluation.failures)


def test_preprocessing_gold_set_binarization_helpful_vs_harmful_floor() -> None:
    evaluation = evaluate_preprocess_gold_set(
        fixture_pack_path=FIXTURE_PACK_PATH,
        baseline_manifest_path=BASELINE_MANIFEST_PATH,
    )
    assert evaluation.passed, evaluation.format_failure_summary()

    by_record_id = {result.record_id: result for result in evaluation.record_results}
    helpful = by_record_id["aggressive-page-008-helpful"]
    harmful = by_record_id["aggressive-page-009-harmful"]
    assert "HIGH_BLUR" not in helpful.warnings
    assert "HIGH_SKEW" not in helpful.warnings
    assert "HIGH_BLUR" in harmful.warnings
    assert "HIGH_SKEW" in harmful.warnings
    helpful_blur = helpful.numeric_metrics.get("blur_score")
    harmful_blur = harmful.numeric_metrics.get("blur_score")
    assert helpful_blur is not None
    assert harmful_blur is not None
    assert harmful_blur <= helpful_blur - 0.05
