#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path


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


def _resolve_readiness_category(
    readiness_report: dict[str, object],
    *,
    category_id: str,
) -> dict[str, object] | None:
    categories = readiness_report.get("categories")
    if not isinstance(categories, list):
        return None
    for item in categories:
        if not isinstance(item, dict):
            continue
        if str(item.get("id", "")).strip() == category_id:
            return item
    return None


def _category_status(
    readiness_report: dict[str, object],
    *,
    category_id: str,
) -> str:
    category = _resolve_readiness_category(readiness_report, category_id=category_id)
    if category is None:
        return "UNAVAILABLE"
    return str(category.get("status", "UNAVAILABLE")).strip().upper() or "UNAVAILABLE"


def _category_evidence_paths(
    readiness_report: dict[str, object],
    *,
    category_id: str,
) -> list[str]:
    category = _resolve_readiness_category(readiness_report, category_id=category_id)
    if category is None:
        return []
    checks = category.get("checks")
    if not isinstance(checks, list):
        return []
    paths: list[str] = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        evidence = check.get("evidence")
        if not isinstance(evidence, list):
            continue
        for item in evidence:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path", "")).strip()
            if path:
                paths.append(path)
    deduped = sorted(set(paths))
    return deduped


def _launch_rehearsal_status(catalog: dict[str, object], key: str) -> tuple[str, str | None]:
    launch_readiness = catalog.get("launchReadiness")
    if not isinstance(launch_readiness, dict):
        return ("PENDING", None)
    section = launch_readiness.get(key)
    if not isinstance(section, dict):
        return ("PENDING", None)
    status = str(section.get("status", "PENDING")).strip().upper() or "PENDING"
    completed_at = (
        str(section.get("completedAt", "")).strip() or None
        if section.get("completedAt") is not None
        else None
    )
    return (status, completed_at)


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _as_markdown(package: dict[str, object]) -> str:
    decision = str(package.get("decision", "NO_SHIP"))
    generated_at = str(package.get("generatedAt", ""))
    blockers = package.get("blockers")
    no_go_criteria = package.get("noGoCriteria")
    handover = package.get("operationalHandover")
    guardrails = package.get("postLaunchGuardrails")
    runbooks = package.get("runbookLinks")
    evidence = package.get("evidenceStatus")

    lines: list[str] = [
        "# Ship / No-Ship Launch Package",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Decision: `{decision}`",
        "",
        "## Evidence status",
    ]
    if isinstance(evidence, dict):
        for key, value in evidence.items():
            lines.append(f"- `{key}`: `{value}`")
    else:
        lines.append("- unavailable")

    lines.append("")
    lines.append("## Blocking findings")
    if isinstance(blockers, list) and blockers:
        for blocker in blockers:
            if not isinstance(blocker, dict):
                continue
            lines.append(
                f"- `{str(blocker.get('id', '')).strip()}`: {str(blocker.get('detail', '')).strip()}"
            )
    else:
        lines.append("- None")

    lines.append("")
    lines.append("## No-go criteria")
    if isinstance(no_go_criteria, list):
        for criterion in no_go_criteria:
            if not isinstance(criterion, dict):
                continue
            lines.append(
                f"- `{str(criterion.get('id', '')).strip()}`: {str(criterion.get('detail', '')).strip()}"
            )
    else:
        lines.append("- Not specified")

    lines.append("")
    lines.append("## Operational handover")
    if isinstance(handover, dict):
        lines.append(
            f"- Launch day owner: `{str(handover.get('launchDayOwnerUserId', '')).strip()}`"
        )
        lines.append(
            f"- On-call primary: `{str(handover.get('onCallPrimaryUserId', '')).strip()}`"
        )
        lines.append(
            f"- On-call secondary: `{str(handover.get('onCallSecondaryUserId', '')).strip()}`"
        )
        model_ownership = handover.get("modelOwnership")
        if isinstance(model_ownership, dict):
            lines.append(
                "- Model service map owner: "
                f"`{str(model_ownership.get('modelServiceMapOwnerUserId', '')).strip()}`"
            )
            lines.append(
                "- Approved-model lifecycle owner: "
                f"`{str(model_ownership.get('approvedModelLifecycleOwnerUserId', '')).strip()}`"
            )
            lines.append(
                "- Rollback execution owner: "
                f"`{str(model_ownership.get('rollbackExecutionOwnerUserId', '')).strip()}`"
            )
        escalation_path = handover.get("escalationPath")
        if isinstance(escalation_path, list) and escalation_path:
            lines.append("- Escalation path:")
            for step in escalation_path:
                if not isinstance(step, dict):
                    continue
                level = str(step.get("level", "")).strip()
                title = str(step.get("title", "")).strip()
                owner = str(step.get("ownerUserId", "")).strip()
                sla = str(step.get("targetResponseSlaMinutes", "")).strip()
                lines.append(f"  - `{level}` {title} ({owner}), SLA {sla} min")
    else:
        lines.append("- unavailable")

    lines.append("")
    lines.append("## Post-launch guardrails")
    if isinstance(guardrails, list):
        for item in guardrails:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- "
                f"`{str(item.get('id', '')).strip()}`: {str(item.get('title', '')).strip()} "
                f"(owner `{str(item.get('ownerUserId', '')).strip()}`; "
                f"trigger: {str(item.get('trigger', '')).strip()}; "
                f"rollback: {str(item.get('rollbackAction', '')).strip()})"
            )
    else:
        lines.append("- unavailable")

    lines.append("")
    lines.append("## Runbook links")
    if isinstance(runbooks, list):
        for item in runbooks:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- `{str(item.get('id', '')).strip()}` -> `{str(item.get('storageKey', '')).strip()}`"
            )
    else:
        lines.append("- unavailable")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the final Phase 11 ship/no-ship launch package.",
    )
    parser.add_argument(
        "--catalog",
        default="infra/readiness/launch-operations-catalog.v1.json",
        help="Path to launch operations catalog.",
    )
    parser.add_argument(
        "--readiness-report",
        default="output/readiness/latest/readiness-report.json",
        help="Path to readiness audit report.",
    )
    parser.add_argument(
        "--smoke-report",
        default="output/smoke/latest/release-smoke-report.json",
        help="Path to release smoke report.",
    )
    parser.add_argument(
        "--release-gate-report",
        default="output/release-gates/latest/release-gate-report.json",
        help="Path to release gate report.",
    )
    parser.add_argument(
        "--output",
        default="output/launch/latest",
        help="Output directory for launch package artifacts.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when blockers are present.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    catalog_path = (repo_root / args.catalog).resolve()
    readiness_path = (repo_root / args.readiness_report).resolve()
    smoke_path = (repo_root / args.smoke_report).resolve()
    release_gate_path = (repo_root / args.release_gate_report).resolve()
    output_dir = (repo_root / args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    catalog = _load_json(catalog_path)
    readiness = _load_json(readiness_path)
    smoke = _load_json(smoke_path)
    release_gate = _load_json(release_gate_path)

    blockers: list[dict[str, object]] = []
    evidence_status: dict[str, str] = {}

    if readiness is None:
        evidence_status["readiness"] = "UNAVAILABLE"
        blockers.append(
            {
                "id": "readiness-report-missing",
                "detail": f"Missing or invalid readiness report at {readiness_path}",
            }
        )
    else:
        readiness_status = str(readiness.get("overallStatus", "UNAVAILABLE")).strip().upper()
        blocking_failure_count = int(readiness.get("blockingFailureCount", 0) or 0)
        evidence_status["readiness"] = readiness_status
        if readiness_status != "PASS" or blocking_failure_count > 0:
            blockers.append(
                {
                    "id": "readiness-blocker",
                    "detail": (
                        "Readiness report is not PASS or contains blocking failures "
                        f"(overallStatus={readiness_status}, blockingFailureCount={blocking_failure_count})."
                    ),
                    "evidencePath": _display_path(readiness_path, repo_root),
                }
            )

    if smoke is None:
        evidence_status["goLiveRehearsal"] = "UNAVAILABLE"
        blockers.append(
            {
                "id": "smoke-report-missing",
                "detail": f"Missing or invalid smoke report at {smoke_path}",
            }
        )
    else:
        smoke_status = str(smoke.get("overallStatus", "UNAVAILABLE")).strip().upper()
        evidence_status["goLiveRehearsal"] = smoke_status
        if smoke_status != "PASS":
            blockers.append(
                {
                    "id": "go-live-rehearsal-failed",
                    "detail": f"Release smoke report is not PASS (overallStatus={smoke_status}).",
                    "evidencePath": _display_path(smoke_path, repo_root),
                }
            )

    if release_gate is None:
        evidence_status["releaseGate"] = "UNAVAILABLE"
        blockers.append(
            {
                "id": "release-gate-report-missing",
                "detail": f"Missing or invalid release gate report at {release_gate_path}",
            }
        )
    else:
        gate_status = str(release_gate.get("overallStatus", "UNAVAILABLE")).strip().upper()
        evidence_status["releaseGate"] = gate_status
        if gate_status != "PASS":
            blockers.append(
                {
                    "id": "release-gate-failed",
                    "detail": f"Release gate report is not PASS (overallStatus={gate_status}).",
                    "evidencePath": _display_path(release_gate_path, repo_root),
                }
            )

    if catalog is None:
        evidence_status["incidentTabletop"] = "UNAVAILABLE"
        evidence_status["modelRollbackRehearsal"] = "UNAVAILABLE"
        blockers.append(
            {
                "id": "launch-catalog-missing",
                "detail": f"Missing or invalid launch operations catalog at {catalog_path}",
            }
        )
        no_go_criteria: list[dict[str, object]] = []
        handover: dict[str, object] = {}
        guardrails: list[dict[str, object]] = []
        runbooks: list[dict[str, object]] = []
    else:
        no_go_criteria_raw = (
            (catalog.get("handover") or {}).get("noGoCriteria")
            if isinstance(catalog.get("handover"), dict)
            else []
        )
        no_go_criteria = (
            [item for item in no_go_criteria_raw if isinstance(item, dict)]
            if isinstance(no_go_criteria_raw, list)
            else []
        )
        handover = (
            dict(catalog.get("handover"))
            if isinstance(catalog.get("handover"), dict)
            else {}
        )
        guardrails_raw = handover.get("postLaunchGuardrails")
        guardrails = (
            [item for item in guardrails_raw if isinstance(item, dict)]
            if isinstance(guardrails_raw, list)
            else []
        )
        runbooks_raw = catalog.get("runbooks")
        runbooks = (
            [item for item in runbooks_raw if isinstance(item, dict)]
            if isinstance(runbooks_raw, list)
            else []
        )

        go_live_status, go_live_completed_at = _launch_rehearsal_status(
            catalog, "goLiveRehearsal"
        )
        tabletop_status, tabletop_completed_at = _launch_rehearsal_status(
            catalog, "incidentResponseTabletop"
        )
        rollback_status, rollback_completed_at = _launch_rehearsal_status(
            catalog, "modelRollbackRehearsal"
        )
        evidence_status["goLiveRehearsal"] = go_live_status
        evidence_status["incidentTabletop"] = tabletop_status
        evidence_status["modelRollbackRehearsal"] = rollback_status

        if go_live_status != "COMPLETED":
            blockers.append(
                {
                    "id": "go-live-rehearsal-not-complete",
                    "detail": "Go-live rehearsal is not marked COMPLETED in launch catalog.",
                    "evidencePath": _display_path(catalog_path, repo_root),
                }
            )
        if tabletop_status != "COMPLETED":
            blockers.append(
                {
                    "id": "incident-tabletop-not-complete",
                    "detail": "Incident response tabletop is not marked COMPLETED in launch catalog.",
                    "evidencePath": _display_path(catalog_path, repo_root),
                }
            )
        if rollback_status != "COMPLETED":
            blockers.append(
                {
                    "id": "model-rollback-not-complete",
                    "detail": "Model rollback rehearsal is not marked COMPLETED in launch catalog.",
                    "evidencePath": _display_path(catalog_path, repo_root),
                }
            )

        if not go_live_completed_at:
            blockers.append(
                {
                    "id": "go-live-rehearsal-missing-completed-at",
                    "detail": "Go-live rehearsal lacks a completedAt timestamp.",
                    "evidencePath": _display_path(catalog_path, repo_root),
                }
            )
        if not tabletop_completed_at:
            blockers.append(
                {
                    "id": "incident-tabletop-missing-completed-at",
                    "detail": "Incident response tabletop lacks a completedAt timestamp.",
                    "evidencePath": _display_path(catalog_path, repo_root),
                }
            )
        if not rollback_completed_at:
            blockers.append(
                {
                    "id": "model-rollback-missing-completed-at",
                    "detail": "Model rollback rehearsal lacks a completedAt timestamp.",
                    "evidencePath": _display_path(catalog_path, repo_root),
                }
            )

    if readiness is not None:
        evidence_status["capacity"] = _category_status(
            readiness, category_id="resilience_capacity"
        )
        evidence_status["security"] = _category_status(
            readiness, category_id="security_hardening"
        )
        evidence_status["sloOps"] = _category_status(
            readiness, category_id="accessibility"
        )
        evidence_status["exportNoBypass"] = _category_status(
            readiness, category_id="egress_controls"
        )
        if evidence_status["security"] != "PASS":
            blockers.append(
                {
                    "id": "security-readiness-not-pass",
                    "detail": "Security readiness category is not PASS.",
                    "evidencePath": _display_path(readiness_path, repo_root),
                }
            )
        if evidence_status["exportNoBypass"] != "PASS":
            blockers.append(
                {
                    "id": "egress-controls-not-pass",
                    "detail": "Egress controls readiness category is not PASS.",
                    "evidencePath": _display_path(readiness_path, repo_root),
                }
            )

    package = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "decision": "NO_SHIP" if blockers else "SHIP",
        "detail": (
            "Ship blockers remain. Do not proceed."
            if blockers
            else "All blocking launch checks are satisfied."
        ),
        "evidenceStatus": evidence_status,
        "evidencePaths": {
            "readinessReport": _display_path(readiness_path, repo_root),
            "smokeReport": _display_path(smoke_path, repo_root),
            "releaseGateReport": _display_path(release_gate_path, repo_root),
            "capacityEvidence": (
                _category_evidence_paths(readiness, category_id="resilience_capacity")
                if readiness is not None
                else []
            ),
            "securityEvidence": (
                _category_evidence_paths(readiness, category_id="security_hardening")
                if readiness is not None
                else []
            ),
            "egressEvidence": (
                _category_evidence_paths(readiness, category_id="egress_controls")
                if readiness is not None
                else []
            ),
        },
        "blockerCount": len(blockers),
        "blockers": blockers,
        "noGoCriteria": no_go_criteria,
        "operationalHandover": {
            key: value
            for key, value in handover.items()
            if key in {
                "launchDayOwnerUserId",
                "onCallPrimaryUserId",
                "onCallSecondaryUserId",
                "escalationPath",
                "modelOwnership",
            }
        },
        "postLaunchGuardrails": guardrails,
        "runbookLinks": [
            {
                "id": str(item.get("id", "")).strip(),
                "slug": str(item.get("slug", "")).strip(),
                "title": str(item.get("title", "")).strip(),
                "storageKey": str(item.get("storageKey", "")).strip(),
                "ownerUserId": str(item.get("ownerUserId", "")).strip(),
                "lastReviewedAt": str(item.get("lastReviewedAt", "")).strip(),
                "status": str(item.get("status", "")).strip(),
            }
            for item in runbooks
        ],
    }

    json_output_path = output_dir / "ship-no-ship-package.json"
    markdown_output_path = output_dir / "ship-no-ship-package.md"
    json_output_path.write_text(
        json.dumps(package, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    markdown_output_path.write_text(_as_markdown(package), encoding="utf-8")

    print(f"launch-package: json written to {json_output_path}")
    print(f"launch-package: markdown written to {markdown_output_path}")
    print(
        "launch-package: "
        f"decision={package['decision']} blockers={len(blockers)}"
    )

    if args.strict and blockers:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
