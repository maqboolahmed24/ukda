from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run_launch_package_builder(*args: str) -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[2]
    return subprocess.run(
        [sys.executable, "scripts/build_launch_readiness_package.py", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )


def _write_catalog(path: Path, *, rehearsal_status: str = "COMPLETED") -> None:
    payload = {
        "runbooks": [
            {
                "id": "runbook-release-readiness",
                "slug": "release-readiness-evidence-and-blocker-policy",
                "title": "Release readiness evidence and blocker policy",
                "ownerUserId": "user-release-manager",
                "lastReviewedAt": "2026-03-18T23:40:00+00:00",
                "status": "ACTIVE",
                "storageKey": "docs/runbooks/release-readiness-evidence-and-blocker-policy.md",
            }
        ],
        "handover": {
            "launchDayOwnerUserId": "user-release-manager",
            "onCallPrimaryUserId": "user-oncall-primary",
            "onCallSecondaryUserId": "user-oncall-secondary",
            "modelOwnership": {
                "modelServiceMapOwnerUserId": "user-model-platform-owner",
                "approvedModelLifecycleOwnerUserId": "user-model-governance-owner",
                "rollbackExecutionOwnerUserId": "user-model-ops-owner",
            },
            "escalationPath": [],
            "postLaunchGuardrails": [],
            "noGoCriteria": [
                {
                    "id": "no-go-readiness-blockers",
                    "title": "Readiness blockers present",
                    "detail": "Blocking checks must pass.",
                }
            ],
        },
        "launchReadiness": {
            "goLiveRehearsal": {
                "status": rehearsal_status,
                "completedAt": "2026-03-18T21:58:00+00:00",
            },
            "incidentResponseTabletop": {
                "status": rehearsal_status,
                "completedAt": "2026-03-18T22:42:00+00:00",
            },
            "modelRollbackRehearsal": {
                "status": rehearsal_status,
                "completedAt": "2026-03-18T23:18:00+00:00",
            },
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_launch_package_builder_passes_when_all_inputs_green(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog.json"
    readiness = tmp_path / "readiness.json"
    smoke = tmp_path / "smoke.json"
    release_gate = tmp_path / "release-gate.json"

    _write_catalog(catalog)
    readiness.write_text(
        json.dumps(
            {
                "overallStatus": "PASS",
                "blockingFailureCount": 0,
                "categories": [
                    {"id": "resilience_capacity", "status": "PASS", "checks": []},
                    {"id": "security_hardening", "status": "PASS", "checks": []},
                    {"id": "accessibility", "status": "PASS", "checks": []},
                    {"id": "egress_controls", "status": "PASS", "checks": []},
                ],
            }
        ),
        encoding="utf-8",
    )
    smoke.write_text(json.dumps({"overallStatus": "PASS"}), encoding="utf-8")
    release_gate.write_text(json.dumps({"overallStatus": "PASS"}), encoding="utf-8")

    output_dir = tmp_path / "output"
    result = _run_launch_package_builder(
        "--catalog",
        str(catalog),
        "--readiness-report",
        str(readiness),
        "--smoke-report",
        str(smoke),
        "--release-gate-report",
        str(release_gate),
        "--output",
        str(output_dir),
        "--strict",
    )

    assert result.returncode == 0
    package = json.loads((output_dir / "ship-no-ship-package.json").read_text(encoding="utf-8"))
    assert package["decision"] == "SHIP"
    assert package["blockerCount"] == 0


def test_launch_package_builder_blocks_when_tabletop_not_completed(
    tmp_path: Path,
) -> None:
    catalog = tmp_path / "catalog.json"
    readiness = tmp_path / "readiness.json"
    smoke = tmp_path / "smoke.json"
    release_gate = tmp_path / "release-gate.json"

    _write_catalog(catalog, rehearsal_status="PENDING")
    readiness.write_text(
        json.dumps(
            {
                "overallStatus": "PASS",
                "blockingFailureCount": 0,
                "categories": [
                    {"id": "resilience_capacity", "status": "PASS", "checks": []},
                    {"id": "security_hardening", "status": "PASS", "checks": []},
                    {"id": "accessibility", "status": "PASS", "checks": []},
                    {"id": "egress_controls", "status": "PASS", "checks": []},
                ],
            }
        ),
        encoding="utf-8",
    )
    smoke.write_text(json.dumps({"overallStatus": "PASS"}), encoding="utf-8")
    release_gate.write_text(json.dumps({"overallStatus": "PASS"}), encoding="utf-8")

    output_dir = tmp_path / "output"
    result = _run_launch_package_builder(
        "--catalog",
        str(catalog),
        "--readiness-report",
        str(readiness),
        "--smoke-report",
        str(smoke),
        "--release-gate-report",
        str(release_gate),
        "--output",
        str(output_dir),
        "--strict",
    )

    assert result.returncode == 1
    package = json.loads((output_dir / "ship-no-ship-package.json").read_text(encoding="utf-8"))
    assert package["decision"] == "NO_SHIP"
    blocker_ids = {item["id"] for item in package["blockers"]}
    assert "incident-tabletop-not-complete" in blocker_ids
