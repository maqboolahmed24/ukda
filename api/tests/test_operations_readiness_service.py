from __future__ import annotations

import json
from pathlib import Path

from app.core.config import get_settings
from app.operations.readiness import ReadinessAuditService


def _write_report(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "matrixVersion": "phase-11-cross-phase-readiness-v1",
        "generatedAt": "2026-03-18T21:00:00+00:00",
        "overallStatus": "PASS",
        "detail": "Cross-phase readiness evidence is available.",
        "blockingFailureCount": 0,
        "categoryCount": 2,
        "categories": [
            {
                "id": "accessibility",
                "title": "Accessibility",
                "status": "PASS",
                "blockingPolicy": "BLOCKING",
                "summary": "Accessibility checks passed.",
                "auditorVisible": True,
                "checks": [
                    {
                        "id": "a11y-route-suite",
                        "title": "Route accessibility suite",
                        "status": "PASS",
                        "blockingPolicy": "BLOCKING",
                        "detail": "All assertions passed.",
                        "durationSeconds": 3.2,
                        "command": "pnpm -s vitest run ...",
                        "exitCode": 0,
                        "evidence": [
                            {
                                "label": "Execution log",
                                "path": "output/readiness/latest/logs/accessibility.log",
                                "sha256": "abc123",
                            }
                        ],
                    }
                ],
            },
            {
                "id": "security_hardening",
                "title": "Security hardening",
                "status": "PASS",
                "blockingPolicy": "BLOCKING",
                "summary": "Security checks passed.",
                "auditorVisible": False,
                "checks": [
                    {
                        "id": "security-regression-suite",
                        "title": "Security regression suite",
                        "status": "PASS",
                        "blockingPolicy": "BLOCKING",
                        "detail": "All assertions passed.",
                        "durationSeconds": 4.1,
                        "command": ".venv/bin/python -m pytest ...",
                        "exitCode": 0,
                        "evidence": [
                            {
                                "label": "Execution log",
                                "path": "output/readiness/latest/logs/security.log",
                                "sha256": "def456",
                            }
                        ],
                    }
                ],
            },
        ],
        "blockers": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_readiness_audit_service_filters_admin_only_categories_for_auditor(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "output" / "readiness" / "latest" / "readiness-report.json"
    _write_report(report_path)
    service = ReadinessAuditService(settings=get_settings(), report_path=report_path)

    admin = service.get_readiness_snapshot(include_admin_details=True).to_dict()
    auditor = service.get_readiness_snapshot(include_admin_details=False).to_dict()

    assert any(item["id"] == "security_hardening" for item in admin["categories"])  # type: ignore[index]
    assert all(
        item["id"] != "security_hardening" for item in auditor["categories"]  # type: ignore[index]
    )
    assert any(
        check.get("command")
        for item in admin["categories"]  # type: ignore[index]
        for check in item["checks"]  # type: ignore[index]
    )
    assert all(
        check.get("command") is None
        for item in auditor["categories"]  # type: ignore[index]
        for check in item["checks"]  # type: ignore[index]
    )


def test_readiness_audit_service_returns_unavailable_when_report_missing(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "output" / "readiness" / "latest" / "readiness-report.json"
    service = ReadinessAuditService(settings=get_settings(), report_path=report_path)

    snapshot = service.get_readiness_snapshot(include_admin_details=True)

    assert snapshot.overall_status == "UNAVAILABLE"
    assert snapshot.category_count == 0
    assert "not found" in snapshot.detail
