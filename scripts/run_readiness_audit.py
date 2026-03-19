#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

Status = Literal["PASS", "FAIL", "UNAVAILABLE"]
BlockingPolicy = Literal["BLOCKING", "WARNING"]


@dataclass(frozen=True)
class CheckDefinition:
    id: str
    title: str
    command: str
    blocking_policy: BlockingPolicy


@dataclass(frozen=True)
class CategoryDefinition:
    id: str
    title: str
    summary: str
    blocking_policy: BlockingPolicy
    auditor_visible: bool
    checks: list[CheckDefinition]


@dataclass(frozen=True)
class MatrixDefinition:
    version: str
    categories: list[CategoryDefinition]


def _load_matrix(path: Path) -> MatrixDefinition:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise RuntimeError(f"Could not read matrix file: {error}") from error
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Matrix JSON is invalid: {error}") from error
    if not isinstance(payload, dict):
        raise RuntimeError("Matrix payload must be a JSON object.")
    categories_raw = payload.get("categories")
    if not isinstance(categories_raw, list):
        raise RuntimeError("Matrix categories must be an array.")

    categories: list[CategoryDefinition] = []
    for category_raw in categories_raw:
        if not isinstance(category_raw, dict):
            continue
        checks_raw = category_raw.get("checks")
        if not isinstance(checks_raw, list):
            continue
        checks: list[CheckDefinition] = []
        for check_raw in checks_raw:
            if not isinstance(check_raw, dict):
                continue
            check_id = str(check_raw.get("id", "")).strip()
            title = str(check_raw.get("title", "")).strip()
            command = str(check_raw.get("command", "")).strip()
            if not (check_id and title and command):
                continue
            policy = str(check_raw.get("blockingPolicy", "BLOCKING")).strip().upper()
            if policy not in {"BLOCKING", "WARNING"}:
                policy = "BLOCKING"
            checks.append(
                CheckDefinition(
                    id=check_id,
                    title=title,
                    command=command,
                    blocking_policy=policy,  # type: ignore[arg-type]
                )
            )
        if not checks:
            continue
        category_id = str(category_raw.get("id", "")).strip()
        title = str(category_raw.get("title", "")).strip()
        summary = str(category_raw.get("summary", "")).strip()
        if not category_id or not title:
            continue
        policy = str(category_raw.get("blockingPolicy", "BLOCKING")).strip().upper()
        if policy not in {"BLOCKING", "WARNING"}:
            policy = "BLOCKING"
        categories.append(
            CategoryDefinition(
                id=category_id,
                title=title,
                summary=summary,
                blocking_policy=policy,  # type: ignore[arg-type]
                auditor_visible=bool(category_raw.get("auditorVisible", False)),
                checks=checks,
            )
        )
    if not categories:
        raise RuntimeError("Matrix does not contain any valid categories.")

    version = str(payload.get("version", "")).strip() or "phase-11-cross-phase-readiness-v1"
    return MatrixDefinition(version=version, categories=categories)


def _apply_placeholders(command: str, *, python_bin: str, pnpm_bin: str) -> str:
    return (
        command.replace("${PYTHON_BIN}", shlex.quote(python_bin)).replace(
            "${PNPM_BIN}", shlex.quote(pnpm_bin)
        )
    )


def _sha256_hex(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_output_dirs(output_dir: Path) -> Path:
    logs_dir = output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


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


def _check_status(return_code: int) -> Status:
    return "PASS" if return_code == 0 else "FAIL"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the cross-phase readiness audit matrix and emit a machine-readable report."
    )
    parser.add_argument(
        "--matrix",
        default="infra/readiness/cross-phase-readiness-matrix.json",
        help="Path to the readiness matrix definition JSON.",
    )
    parser.add_argument(
        "--output",
        default="output/readiness/latest",
        help="Directory where readiness evidence and report files are written.",
    )
    parser.add_argument(
        "--python-bin",
        default="python3",
        help="Python executable used for matrix commands with ${PYTHON_BIN}.",
    )
    parser.add_argument(
        "--pnpm-bin",
        default="pnpm",
        help="pnpm executable used for matrix commands with ${PNPM_BIN}.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when any blocking check fails.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    matrix_path = (repo_root / args.matrix).resolve()
    output_dir = (repo_root / args.output).resolve()
    report_path = output_dir / "readiness-report.json"
    logs_dir = _ensure_output_dirs(output_dir)

    try:
        matrix = _load_matrix(matrix_path)
    except RuntimeError as error:
        print(f"readiness-audit: {error}", file=sys.stderr)
        return 2

    categories_payload: list[dict[str, object]] = []
    blockers: list[dict[str, object]] = []
    warning_failures = 0

    for category in matrix.categories:
        check_payloads: list[dict[str, object]] = []
        category_failed = False
        category_blocking_failures = 0
        for check in category.checks:
            command = _apply_placeholders(
                check.command,
                python_bin=args.python_bin,
                pnpm_bin=args.pnpm_bin,
            )
            started_at = datetime.now(UTC)
            return_code, output = _run_command(command, cwd=repo_root)
            ended_at = datetime.now(UTC)
            duration_seconds = max(0.0, (ended_at - started_at).total_seconds())
            status = _check_status(return_code)

            safe_category = category.id.replace("/", "-")
            safe_check = check.id.replace("/", "-")
            log_path = logs_dir / f"{safe_category}__{safe_check}.log"
            log_path.write_text(output, encoding="utf-8")
            evidence_path = str(log_path.relative_to(repo_root))
            evidence_sha = _sha256_hex(log_path)

            detail = (
                "Check passed."
                if status == "PASS"
                else f"Check failed with exit code {return_code}."
            )
            check_payloads.append(
                {
                    "id": check.id,
                    "title": check.title,
                    "status": status,
                    "blockingPolicy": check.blocking_policy,
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
            )

            if status == "FAIL":
                category_failed = True
                if check.blocking_policy == "BLOCKING":
                    category_blocking_failures += 1
                    blockers.append(
                        {
                            "categoryId": category.id,
                            "checkId": check.id,
                            "detail": detail,
                            "evidencePath": evidence_path,
                        }
                    )
                else:
                    warning_failures += 1

        category_status: Status = "FAIL" if category_failed else "PASS"
        categories_payload.append(
            {
                "id": category.id,
                "title": category.title,
                "status": category_status,
                "blockingPolicy": category.blocking_policy,
                "summary": category.summary,
                "auditorVisible": category.auditor_visible,
                "checks": check_payloads,
                "blockingFailureCount": category_blocking_failures,
            }
        )

    blocking_failure_count = len(blockers)
    overall_status: Status = "FAIL" if blocking_failure_count > 0 else "PASS"
    detail = (
        "Cross-phase readiness contains blocking failures."
        if overall_status == "FAIL"
        else "Cross-phase readiness blocking checks passed."
    )
    if warning_failures > 0:
        detail = f"{detail} Warning-level failures: {warning_failures}."

    report = {
        "matrixVersion": matrix.version,
        "generatedAt": datetime.now(UTC).isoformat(),
        "overallStatus": overall_status,
        "detail": detail,
        "blockingFailureCount": blocking_failure_count,
        "warningFailureCount": warning_failures,
        "categoryCount": len(categories_payload),
        "matrixPath": str(matrix_path.relative_to(repo_root)),
        "categories": categories_payload,
        "blockers": blockers,
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    print(f"readiness-audit: report written to {report_path}")
    print(
        "readiness-audit: "
        f"overall={overall_status} blocking_failures={blocking_failure_count} "
        f"warning_failures={warning_failures}"
    )

    if args.strict and blocking_failure_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
