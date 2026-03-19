from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run_seed_refresh(*args: str) -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[2]
    return subprocess.run(
        [sys.executable, "scripts/refresh_nonprod_seed_data.py", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )


def test_seed_refresh_validate_passes_for_dev(tmp_path: Path) -> None:
    result = _run_seed_refresh(
        "--environment",
        "dev",
        "--strict",
        "--output",
        str(tmp_path / "output"),
    )
    assert result.returncode == 0

    report_path = tmp_path / "output" / "nonprod-seed-refresh-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["overallStatus"] == "PASS"
    assert report["mode"] == "validate"
    assert report["applied"] is False


def test_seed_refresh_rejects_prod_even_without_apply(tmp_path: Path) -> None:
    result = _run_seed_refresh(
        "--environment",
        "prod",
        "--strict",
        "--output",
        str(tmp_path / "output"),
    )
    assert result.returncode == 1

    report_path = tmp_path / "output" / "nonprod-seed-refresh-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["overallStatus"] == "FAIL"
    assert "blocked in prod" in str(report["detail"]).lower()
