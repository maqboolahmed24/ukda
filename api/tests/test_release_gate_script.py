from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run_release_gate(*args: str) -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[2]
    return subprocess.run(
        [sys.executable, "scripts/run_release_gate.py", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )


def test_release_gate_blocks_invalid_promotion_transition(tmp_path: Path) -> None:
    readiness = tmp_path / "readiness.json"
    readiness.write_text(
        json.dumps({"overallStatus": "PASS", "blockingFailureCount": 0}),
        encoding="utf-8",
    )
    smoke = tmp_path / "smoke.json"
    smoke.write_text(
        json.dumps({"overallStatus": "PASS", "failureCount": 0, "profile": "prod"}),
        encoding="utf-8",
    )

    result = _run_release_gate(
        "--mode",
        "promote",
        "--source-env",
        "dev",
        "--target-env",
        "prod",
        "--readiness-report",
        str(readiness),
        "--smoke-report",
        str(smoke),
        "--strict",
        "--output",
        str(tmp_path / "output"),
    )

    assert result.returncode == 1
    report = json.loads(
        (tmp_path / "output" / "release-gate-report.json").read_text(encoding="utf-8")
    )
    assert report["overallStatus"] == "FAIL"
    assert any(item["checkId"] == "transition-policy" for item in report["blockers"])


def test_release_gate_passes_for_staging_to_prod(tmp_path: Path) -> None:
    readiness = tmp_path / "readiness.json"
    readiness.write_text(
        json.dumps({"overallStatus": "PASS", "blockingFailureCount": 0}),
        encoding="utf-8",
    )
    smoke = tmp_path / "smoke.json"
    smoke.write_text(
        json.dumps({"overallStatus": "PASS", "failureCount": 0, "profile": "prod"}),
        encoding="utf-8",
    )

    result = _run_release_gate(
        "--mode",
        "promote",
        "--source-env",
        "staging",
        "--target-env",
        "prod",
        "--readiness-report",
        str(readiness),
        "--smoke-report",
        str(smoke),
        "--strict",
        "--output",
        str(tmp_path / "output"),
    )

    assert result.returncode == 0
    report = json.loads(
        (tmp_path / "output" / "release-gate-report.json").read_text(encoding="utf-8")
    )
    assert report["overallStatus"] == "PASS"
    assert report["blockingFailureCount"] == 0
