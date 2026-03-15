from __future__ import annotations

import json
from pathlib import Path

from app.documents.privacy_regression import (
    evaluate_privacy_regression_pack,
    write_privacy_regression_artifact,
)

FIXTURE_PACK_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "privacy-direct-identifiers-gold-set"
    / "fixture-pack.v1.json"
)
EVALUATION_ARTIFACT_PATH = (
    Path(__file__).parent
    / ".artifacts"
    / "privacy-regression"
    / "last-evaluation.json"
)


def _evaluate_and_write(path: Path = FIXTURE_PACK_PATH):
    evaluation = evaluate_privacy_regression_pack(path)
    write_privacy_regression_artifact(
        evaluation=evaluation,
        path=EVALUATION_ARTIFACT_PATH,
    )
    return evaluation


def test_privacy_regression_pack_disclosure_gates_are_green() -> None:
    evaluation = _evaluate_and_write()
    assert evaluation.passed, evaluation.format_failure_summary()


def test_privacy_regression_harness_detects_manifest_leaks(tmp_path: Path) -> None:
    mutated = json.loads(FIXTURE_PACK_PATH.read_text(encoding="utf-8"))
    assert isinstance(mutated.get("cases"), list)
    target_case = next(
        row for row in mutated["cases"] if row.get("caseId") == "email-01"
    )
    assert isinstance(target_case, dict)
    target_case["rawValues"] = ["regression-email-01"]
    mutated_path = tmp_path / "fixture-pack.mutated.v1.json"
    mutated_path.write_text(json.dumps(mutated, indent=2) + "\n", encoding="utf-8")

    evaluation = _evaluate_and_write(mutated_path)

    assert not evaluation.passed
    assert any(
        failure.error_code == "PRIVACY_DISCLOSURE_MANIFEST_LEAK"
        and failure.case_id == "email-01"
        for failure in evaluation.failures
    )
