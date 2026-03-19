#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

Status = Literal["PASS", "FAIL"]
Environment = Literal["dev", "staging", "prod"]


@dataclass(frozen=True)
class SmokeCheck:
    id: str
    title: str
    command: str
    required_in: tuple[Environment, ...]


@dataclass(frozen=True)
class SmokeSuite:
    version: str
    checks: tuple[SmokeCheck, ...]


SUITE = SmokeSuite(
    version="release-smoke-v1",
    checks=(
        SmokeCheck(
            id="auth-project-access",
            title="Auth and project access sanity",
            command=(
                "${PYTHON_BIN} -m pytest -q "
                "api/tests/test_auth.py "
                "api/tests/test_projects_service.py"
            ),
            required_in=("dev", "staging", "prod"),
        ),
        SmokeCheck(
            id="ingest-document-handling",
            title="Ingest and document-handling sanity",
            command="${PYTHON_BIN} -m pytest -q api/tests/test_documents_routes.py",
            required_in=("dev", "staging", "prod"),
        ),
        SmokeCheck(
            id="transcription-privacy-governance",
            title="Transcription/privacy/governance happy-path sanity",
            command=(
                "${PYTHON_BIN} -m pytest -q "
                "api/tests/test_transcription_gold_set.py "
                "api/tests/test_documents_redaction_phase5_rules.py "
                "api/tests/test_governance_integrity.py"
            ),
            required_in=("dev", "staging", "prod"),
        ),
        SmokeCheck(
            id="export-review-sanity",
            title="Export request and review flow sanity",
            command="${PYTHON_BIN} -m pytest -q api/tests/test_export_routes.py",
            required_in=("dev", "staging", "prod"),
        ),
        SmokeCheck(
            id="egress-no-bypass-sanity",
            title="No-bypass controls sanity",
            command=(
                "${PYTHON_BIN} -m pytest -q "
                "api/tests/test_outbound_policy.py "
                "api/tests/test_export_hardening_regression.py"
            ),
            required_in=("dev", "staging", "prod"),
        ),
        SmokeCheck(
            id="admin-operations-status-sanity",
            title="Admin operations/status sanity",
            command=(
                "${PYTHON_BIN} -m pytest -q "
                "api/tests/test_operations_routes.py "
                "api/tests/test_launch_routes.py "
                "api/tests/test_security_routes.py "
                "api/tests/test_capacity_routes.py "
                "api/tests/test_recovery_routes.py"
            ),
            required_in=("dev", "staging", "prod"),
        ),
        SmokeCheck(
            id="admin-shell-surface-sanity",
            title="Admin shell route and command surface sanity",
            command=(
                "${PNPM_BIN} -s vitest run "
                "web/lib/routes.test.ts "
                "web/lib/admin-console.test.ts "
                "web/lib/command-registry.test.ts "
                "web/lib/data/query-keys.test.ts "
                "packages/contracts/src/index.test.ts"
            ),
            required_in=("dev", "staging", "prod"),
        ),
    ),
)


def _apply_placeholders(command: str, *, python_bin: str, pnpm_bin: str) -> str:
    return command.replace("${PYTHON_BIN}", shlex.quote(python_bin)).replace(
        "${PNPM_BIN}",
        shlex.quote(pnpm_bin),
    )


def _sha256_hex(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_command(command: str, *, cwd: Path) -> tuple[int, str]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        shell=True,
        text=True,
        capture_output=True,
        check=False,
        env=os.environ.copy(),
    )
    merged = f"$ {command}\n\n{completed.stdout}\n{completed.stderr}".strip() + "\n"
    return completed.returncode, merged


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the release smoke suite and emit deterministic machine-readable output.",
    )
    parser.add_argument(
        "--profile",
        choices=("dev", "staging", "prod"),
        required=True,
        help="Release target environment profile.",
    )
    parser.add_argument(
        "--output",
        default="output/smoke/latest",
        help="Directory where smoke logs and report are written.",
    )
    parser.add_argument(
        "--python-bin",
        default="python3",
        help="Python executable used for smoke check commands.",
    )
    parser.add_argument(
        "--pnpm-bin",
        default="pnpm",
        help="pnpm executable used for smoke check commands.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any smoke check fails.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    output_dir = (repo_root / args.output).resolve()
    logs_dir = output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "release-smoke-report.json"

    selected_checks = [
        check for check in SUITE.checks if args.profile in set(check.required_in)
    ]
    check_payloads: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []

    for check in selected_checks:
        command = _apply_placeholders(
            check.command,
            python_bin=args.python_bin,
            pnpm_bin=args.pnpm_bin,
        )
        started_at = datetime.now(UTC)
        return_code, output = _run_command(command, cwd=repo_root)
        ended_at = datetime.now(UTC)

        status: Status = "PASS" if return_code == 0 else "FAIL"
        duration_seconds = max(0.0, (ended_at - started_at).total_seconds())
        safe_check_id = check.id.replace("/", "-")
        log_path = logs_dir / f"{safe_check_id}.log"
        log_path.write_text(output, encoding="utf-8")
        evidence_path = str(log_path.relative_to(repo_root))
        evidence_sha = _sha256_hex(log_path)

        detail = (
            "Smoke check passed."
            if status == "PASS"
            else f"Smoke check failed with exit code {return_code}."
        )
        payload = {
            "id": check.id,
            "title": check.title,
            "status": status,
            "detail": detail,
            "durationSeconds": round(duration_seconds, 3),
            "command": command,
            "exitCode": return_code,
            "evidence": [
                {
                    "label": "Execution log",
                    "path": evidence_path,
                    "sha256": evidence_sha,
                }
            ],
        }
        check_payloads.append(payload)
        if status == "FAIL":
            failures.append(
                {
                    "checkId": check.id,
                    "detail": detail,
                    "evidencePath": evidence_path,
                }
            )

    overall_status: Status = "FAIL" if failures else "PASS"
    detail = (
        "Release smoke suite passed."
        if overall_status == "PASS"
        else "Release smoke suite contains failures."
    )

    report = {
        "suiteVersion": SUITE.version,
        "profile": args.profile,
        "generatedAt": datetime.now(UTC).isoformat(),
        "overallStatus": overall_status,
        "detail": detail,
        "failureCount": len(failures),
        "checkCount": len(check_payloads),
        "checks": check_payloads,
        "failures": failures,
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    print(f"release-smoke: report written to {report_path}")
    print(
        "release-smoke: "
        f"profile={args.profile} overall={overall_status} failures={len(failures)}"
    )

    if args.strict and failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
