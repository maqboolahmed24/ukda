from __future__ import annotations

import json
from pathlib import Path

from app.documents.transcription_gold_set import (
    evaluate_transcription_gold_set,
    load_transcription_gold_set_baseline_manifest,
    write_transcription_gold_set_artifact,
)

FIXTURE_PACK_PATH = (
    Path(__file__).parent / "fixtures" / "transcription-gold-set" / "fixture-pack.v1.json"
)
BASELINE_MANIFEST_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "transcription-gold-set"
    / "baseline-manifest.v1.json"
)
EVALUATION_ARTIFACT_PATH = (
    Path(__file__).parent
    / ".artifacts"
    / "transcription-gold-set"
    / "last-evaluation.json"
)


def _evaluate_current_baseline() -> tuple[bool, str]:
    evaluation = evaluate_transcription_gold_set(
        fixture_pack_path=FIXTURE_PACK_PATH,
        baseline_manifest_path=BASELINE_MANIFEST_PATH,
    )
    write_transcription_gold_set_artifact(
        evaluation=evaluation,
        path=EVALUATION_ARTIFACT_PATH,
    )
    return evaluation.passed, evaluation.format_failure_summary()


def test_transcription_gold_set_baseline_manifest_is_current() -> None:
    passed, failure_summary = _evaluate_current_baseline()
    assert passed, failure_summary


def test_transcription_gold_set_harness_detects_slice_regression(
    tmp_path: Path,
) -> None:
    manifest = load_transcription_gold_set_baseline_manifest(BASELINE_MANIFEST_PATH)
    mutated = json.loads(BASELINE_MANIFEST_PATH.read_text(encoding="utf-8"))
    for row in mutated["expectations"]:
        if row.get("sliceName") == "rescue_source":
            row["expectedCer"] = 0.0
    mutated_path = tmp_path / "mutated-baseline.json"
    mutated_path.write_text(json.dumps(mutated, indent=2) + "\n", encoding="utf-8")

    evaluation = evaluate_transcription_gold_set(
        fixture_pack_path=FIXTURE_PACK_PATH,
        baseline_manifest_path=mutated_path,
    )

    assert manifest.baseline_version == "v1"
    assert not evaluation.passed
    summary = evaluation.format_failure_summary()
    assert "rescue_source" in summary
    assert any("CER drift" in item for item in evaluation.failures)


def test_transcription_gold_set_reports_ordinary_rescue_and_fallback_slices() -> None:
    evaluation = evaluate_transcription_gold_set(
        fixture_pack_path=FIXTURE_PACK_PATH,
        baseline_manifest_path=BASELINE_MANIFEST_PATH,
    )
    assert evaluation.passed, evaluation.format_failure_summary()

    by_slice = {row.slice_name: row for row in evaluation.slice_results}
    assert by_slice["ordinary_line"].case_count == 2
    assert by_slice["rescue_source"].case_count == 2
    assert by_slice["fallback_invoked"].case_count == 1
    assert "run-alpha" in by_slice["ordinary_line"].run_ids
    assert "run-beta" in by_slice["rescue_source"].run_ids
    assert by_slice["fallback_invoked"].transcript_version_ids == ("tv-4",)
