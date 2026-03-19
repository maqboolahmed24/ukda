#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

Environment = Literal["dev", "staging", "prod"]
Mode = Literal["promote", "rollback"]
Status = Literal["PASS", "FAIL", "SKIP"]
BlockingPolicy = Literal["BLOCKING", "WARNING"]


@dataclass(frozen=True)
class GateCheckResult:
    id: str
    title: str
    status: Status
    blocking_policy: BlockingPolicy
    detail: str
    evidence: list[dict[str, object]]

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "blockingPolicy": self.blocking_policy,
            "detail": self.detail,
            "evidence": self.evidence,
        }


def _evidence_path(repo_root: Path, path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(repo_root))
    except ValueError:
        return str(resolved)


def _load_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _check_transition(
    *,
    mode: Mode,
    source_env: str | None,
    target_env: Environment,
) -> GateCheckResult:
    if mode == "rollback":
        detail = "Rollback mode selected; release-path transition checks are not required."
        return GateCheckResult(
            id="transition-policy",
            title="Promotion path policy",
            status="PASS",
            blocking_policy="BLOCKING",
            detail=detail,
            evidence=[],
        )

    if not source_env:
        return GateCheckResult(
            id="transition-policy",
            title="Promotion path policy",
            status="FAIL",
            blocking_policy="BLOCKING",
            detail="Promotion mode requires --source-env.",
            evidence=[],
        )

    allowed = {("dev", "staging"), ("staging", "prod")}
    if (source_env, target_env) not in allowed:
        return GateCheckResult(
            id="transition-policy",
            title="Promotion path policy",
            status="FAIL",
            blocking_policy="BLOCKING",
            detail=(
                f"Invalid promotion transition {source_env}->{target_env}. "
                "Allowed transitions: dev->staging, staging->prod."
            ),
            evidence=[],
        )
    return GateCheckResult(
        id="transition-policy",
        title="Promotion path policy",
        status="PASS",
        blocking_policy="BLOCKING",
        detail=f"Promotion transition {source_env}->{target_env} is allowed.",
        evidence=[],
    )


def _check_profile_values(*, repo_root: Path, environment: Environment) -> GateCheckResult:
    profile_path = repo_root / "infra" / "helm" / "ukde" / f"values-{environment}.yaml"
    if not profile_path.exists():
        return GateCheckResult(
            id="deployment-profile",
            title="Environment deployment profile",
            status="FAIL",
            blocking_policy="BLOCKING",
            detail=f"Missing deployment profile: {profile_path}",
            evidence=[],
        )

    try:
        text = profile_path.read_text(encoding="utf-8")
    except OSError as error:
        return GateCheckResult(
            id="deployment-profile",
            title="Environment deployment profile",
            status="FAIL",
            blocking_policy="BLOCKING",
            detail=f"Could not read profile file: {error}",
            evidence=[],
        )

    expected = f"environment: {environment}"
    if expected not in text:
        return GateCheckResult(
            id="deployment-profile",
            title="Environment deployment profile",
            status="FAIL",
            blocking_policy="BLOCKING",
            detail=f"Profile {profile_path} does not declare '{expected}'.",
            evidence=[
                {
                    "label": "Profile file",
                    "path": _evidence_path(repo_root, profile_path),
                }
            ],
        )

    possible_secret_markers = ("password:", "token:", "secret:", "api_key:", "apikey:")
    lower = text.lower()
    findings = [marker for marker in possible_secret_markers if marker in lower]
    if findings:
        return GateCheckResult(
            id="deployment-profile",
            title="Environment deployment profile",
            status="FAIL",
            blocking_policy="BLOCKING",
            detail=(
                f"Profile {profile_path} appears to include inline secret-like keys: "
                f"{', '.join(findings)}."
            ),
            evidence=[
                {
                    "label": "Profile file",
                    "path": _evidence_path(repo_root, profile_path),
                }
            ],
        )

    return GateCheckResult(
        id="deployment-profile",
        title="Environment deployment profile",
        status="PASS",
        blocking_policy="BLOCKING",
        detail=f"Profile {profile_path.name} is explicit and free of inline secret markers.",
        evidence=[
            {
                "label": "Profile file",
                "path": _evidence_path(repo_root, profile_path),
            }
        ],
    )


def _check_readiness_report(*, repo_root: Path, report_path: Path) -> GateCheckResult:
    payload = _load_json(report_path)
    if payload is None:
        return GateCheckResult(
            id="readiness-evidence",
            title="Cross-phase readiness evidence",
            status="FAIL",
            blocking_policy="BLOCKING",
            detail=f"Missing or invalid readiness report at {report_path}.",
            evidence=[],
        )
    overall_status = str(payload.get("overallStatus", "")).strip().upper()
    blocking_failures = int(payload.get("blockingFailureCount", 0) or 0)
    if overall_status != "PASS" or blocking_failures > 0:
        return GateCheckResult(
            id="readiness-evidence",
            title="Cross-phase readiness evidence",
            status="FAIL",
            blocking_policy="BLOCKING",
            detail=(
                "Readiness gate failed: "
                f"overallStatus={overall_status or 'UNKNOWN'} "
                f"blockingFailureCount={blocking_failures}."
            ),
            evidence=[
                {
                    "label": "Readiness report",
                    "path": _evidence_path(repo_root, report_path),
                }
            ],
        )
    return GateCheckResult(
        id="readiness-evidence",
        title="Cross-phase readiness evidence",
        status="PASS",
        blocking_policy="BLOCKING",
        detail="Readiness report is PASS with zero blocking failures.",
        evidence=[
            {
                "label": "Readiness report",
                "path": _evidence_path(repo_root, report_path),
            }
        ],
    )


def _check_smoke_report(
    *,
    repo_root: Path,
    report_path: Path,
    target_env: Environment,
) -> GateCheckResult:
    payload = _load_json(report_path)
    if payload is None:
        return GateCheckResult(
            id="smoke-suite",
            title="Release smoke-suite evidence",
            status="FAIL",
            blocking_policy="BLOCKING",
            detail=f"Missing or invalid smoke report at {report_path}.",
            evidence=[],
        )
    overall_status = str(payload.get("overallStatus", "")).strip().upper()
    profile = str(payload.get("profile", "")).strip()
    failures = int(payload.get("failureCount", 0) or 0)
    if profile and profile != target_env:
        return GateCheckResult(
            id="smoke-suite",
            title="Release smoke-suite evidence",
            status="FAIL",
            blocking_policy="BLOCKING",
            detail=f"Smoke report profile mismatch. expected={target_env} actual={profile}.",
            evidence=[
                {
                    "label": "Smoke report",
                    "path": _evidence_path(repo_root, report_path),
                }
            ],
        )
    if overall_status != "PASS" or failures > 0:
        return GateCheckResult(
            id="smoke-suite",
            title="Release smoke-suite evidence",
            status="FAIL",
            blocking_policy="BLOCKING",
            detail=f"Smoke gate failed: overallStatus={overall_status} failureCount={failures}.",
            evidence=[
                {
                    "label": "Smoke report",
                    "path": _evidence_path(repo_root, report_path),
                }
            ],
        )
    return GateCheckResult(
        id="smoke-suite",
        title="Release smoke-suite evidence",
        status="PASS",
        blocking_policy="BLOCKING",
        detail="Smoke report is PASS with zero failures.",
        evidence=[
            {
                "label": "Smoke report",
                "path": _evidence_path(repo_root, report_path),
            }
        ],
    )


def _check_seed_report(
    *,
    repo_root: Path,
    report_path: Path,
    target_env: Environment,
) -> GateCheckResult:
    if target_env == "prod":
        return GateCheckResult(
            id="nonprod-seed",
            title="Non-production seed-data policy",
            status="SKIP",
            blocking_policy="WARNING",
            detail="Target is prod; non-production seed refresh is intentionally skipped.",
            evidence=[],
        )

    payload = _load_json(report_path)
    if payload is None:
        return GateCheckResult(
            id="nonprod-seed",
            title="Non-production seed-data policy",
            status="FAIL",
            blocking_policy="BLOCKING",
            detail=f"Missing or invalid seed report at {report_path}.",
            evidence=[],
        )
    overall_status = str(payload.get("overallStatus", "")).strip().upper()
    environment = str(payload.get("environment", "")).strip()
    classification = str(payload.get("classification", "")).strip().upper()
    if environment != target_env:
        return GateCheckResult(
            id="nonprod-seed",
            title="Non-production seed-data policy",
            status="FAIL",
            blocking_policy="BLOCKING",
            detail=f"Seed report environment mismatch. expected={target_env} actual={environment}.",
            evidence=[
                {
                    "label": "Seed report",
                    "path": _evidence_path(repo_root, report_path),
                }
            ],
        )
    if classification != "SYNTHETIC_ONLY":
        return GateCheckResult(
            id="nonprod-seed",
            title="Non-production seed-data policy",
            status="FAIL",
            blocking_policy="BLOCKING",
            detail=f"Seed report classification must be SYNTHETIC_ONLY (actual={classification}).",
            evidence=[
                {
                    "label": "Seed report",
                    "path": _evidence_path(repo_root, report_path),
                }
            ],
        )
    if overall_status != "PASS":
        return GateCheckResult(
            id="nonprod-seed",
            title="Non-production seed-data policy",
            status="FAIL",
            blocking_policy="BLOCKING",
            detail=f"Seed report overallStatus must be PASS (actual={overall_status}).",
            evidence=[
                {
                    "label": "Seed report",
                    "path": _evidence_path(repo_root, report_path),
                }
            ],
        )
    return GateCheckResult(
        id="nonprod-seed",
        title="Non-production seed-data policy",
        status="PASS",
        blocking_policy="BLOCKING",
        detail="Non-production seed report is PASS and synthetic-only.",
        evidence=[
            {
                "label": "Seed report",
                "path": _evidence_path(repo_root, report_path),
            }
        ],
    )


def _check_rollback_runbooks(repo_root: Path) -> GateCheckResult:
    required_files = [
        repo_root / "docs" / "runbooks" / "deployment-runbook.md",
        repo_root / "docs" / "runbooks" / "backup-restore-runbook.md",
    ]
    missing = [path for path in required_files if not path.exists()]
    if missing:
        return GateCheckResult(
            id="rollback-runbooks",
            title="Rollback runbook references",
            status="FAIL",
            blocking_policy="BLOCKING",
            detail="Missing rollback runbook references required by release automation.",
            evidence=[
                {
                    "label": "Missing file",
                    "path": _evidence_path(repo_root, path),
                }
                for path in missing
            ],
        )
    return GateCheckResult(
        id="rollback-runbooks",
        title="Rollback runbook references",
        status="PASS",
        blocking_policy="BLOCKING",
        detail="Rollback runbook references are present.",
        evidence=[
            {"label": "Runbook", "path": _evidence_path(repo_root, path)}
            for path in required_files
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate machine-readable release promotion/rollback gates.",
    )
    parser.add_argument("--mode", choices=("promote", "rollback"), required=True)
    parser.add_argument("--target-env", choices=("dev", "staging", "prod"), required=True)
    parser.add_argument("--source-env", choices=("dev", "staging", "prod"), default="")
    parser.add_argument(
        "--readiness-report",
        default="output/readiness/latest/readiness-report.json",
        help="Path to readiness report JSON.",
    )
    parser.add_argument(
        "--smoke-report",
        default="output/smoke/latest/release-smoke-report.json",
        help="Path to smoke report JSON.",
    )
    parser.add_argument(
        "--seed-report",
        default="output/seeds/latest/nonprod-seed-refresh-report.json",
        help="Path to non-production seed refresh report JSON.",
    )
    parser.add_argument(
        "--output",
        default="output/release-gates/latest",
        help="Directory where release gate outputs are written.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when blocking checks fail.",
    )
    args = parser.parse_args()

    mode: Mode = args.mode  # type: ignore[assignment]
    target_env: Environment = args.target_env  # type: ignore[assignment]
    source_env = args.source_env or None

    repo_root = Path(__file__).resolve().parents[1]
    output_dir = (repo_root / args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "release-gate-report.json"

    checks = [
        _check_transition(mode=mode, source_env=source_env, target_env=target_env),
        _check_profile_values(repo_root=repo_root, environment=target_env),
        _check_readiness_report(
            repo_root=repo_root,
            report_path=(repo_root / args.readiness_report).resolve(),
        ),
        _check_smoke_report(
            repo_root=repo_root,
            report_path=(repo_root / args.smoke_report).resolve(),
            target_env=target_env,
        ),
        _check_seed_report(
            repo_root=repo_root,
            report_path=(repo_root / args.seed_report).resolve(),
            target_env=target_env,
        ),
        _check_rollback_runbooks(repo_root),
    ]

    blockers = [
        check
        for check in checks
        if check.status == "FAIL" and check.blocking_policy == "BLOCKING"
    ]
    warnings = [
        check
        for check in checks
        if check.status == "FAIL" and check.blocking_policy == "WARNING"
    ]
    overall_status: Literal["PASS", "FAIL"] = "FAIL" if blockers else "PASS"
    detail = (
        "Release gate checks passed."
        if overall_status == "PASS"
        else "Release gate checks contain blocking failures."
    )

    report = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "mode": mode,
        "sourceEnvironment": source_env,
        "targetEnvironment": target_env,
        "overallStatus": overall_status,
        "detail": detail,
        "blockingFailureCount": len(blockers),
        "warningFailureCount": len(warnings),
        "checkCount": len(checks),
        "checks": [check.to_dict() for check in checks],
        "blockers": [
            {
                "checkId": check.id,
                "detail": check.detail,
            }
            for check in blockers
        ],
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    print(f"release-gate: report written to {report_path}")
    print(
        "release-gate: "
        f"mode={mode} target={target_env} overall={overall_status} blockers={len(blockers)}"
    )

    if args.strict and blockers:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
