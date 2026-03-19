from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from app.core.config import Settings, get_settings

_SAFE_AUDITOR_CATEGORY_IDS: set[str] = {
    "accessibility",
    "governance_integrity",
    "privacy_safety",
    "provenance_verification",
    "egress_controls",
    "discovery_safety",
}
_ALLOWED_STATUS: set[str] = {"PASS", "FAIL", "UNAVAILABLE"}
_ALLOWED_BLOCKING_POLICY: set[str] = {"BLOCKING", "WARNING"}


@dataclass(frozen=True)
class ReadinessAuditSnapshot:
    matrix_version: str
    generated_at: datetime
    overall_status: str
    detail: str
    blocking_failure_count: int
    category_count: int
    categories: list[dict[str, object]]
    blockers: list[dict[str, object]]

    def to_dict(self) -> dict[str, object]:
        return {
            "matrixVersion": self.matrix_version,
            "generatedAt": self.generated_at.isoformat(),
            "overallStatus": self.overall_status,
            "detail": self.detail,
            "blockingFailureCount": self.blocking_failure_count,
            "categoryCount": self.category_count,
            "categories": self.categories,
            "blockers": self.blockers,
        }


class ReadinessAuditService:
    def __init__(self, *, settings: Settings, report_path: Path | None = None) -> None:
        self._settings = settings
        self._report_path = report_path or (
            settings.repo_root / "output" / "readiness" / "latest" / "readiness-report.json"
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def _unavailable_snapshot(self, detail: str) -> ReadinessAuditSnapshot:
        return ReadinessAuditSnapshot(
            matrix_version="phase-11-cross-phase-readiness-v1",
            generated_at=self._now(),
            overall_status="UNAVAILABLE",
            detail=detail,
            blocking_failure_count=0,
            category_count=0,
            categories=[],
            blockers=[],
        )

    @staticmethod
    def _normalize_status(value: object) -> str:
        candidate = str(value).strip().upper()
        if candidate in _ALLOWED_STATUS:
            return candidate
        return "UNAVAILABLE"

    @staticmethod
    def _normalize_blocking_policy(value: object) -> str:
        candidate = str(value).strip().upper()
        if candidate in _ALLOWED_BLOCKING_POLICY:
            return candidate
        return "BLOCKING"

    @staticmethod
    def _as_non_negative_int(value: object) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return 0
        return max(0, parsed)

    @staticmethod
    def _as_non_negative_float(value: object) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return 0.0
        if parsed < 0:
            return 0.0
        return parsed

    @staticmethod
    def _as_datetime(value: object) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    def _load_report(self) -> dict[str, object] | None:
        if not self._report_path.exists():
            return None
        try:
            payload = json.loads(self._report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def _normalize_evidence(
        self,
        payload: object,
    ) -> list[dict[str, object]]:
        if not isinstance(payload, list):
            return []
        normalized: list[dict[str, object]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "")).strip() or "Evidence"
            path = str(item.get("path", "")).strip()
            if not path:
                continue
            sha256 = str(item.get("sha256", "")).strip()
            normalized.append(
                {
                    "label": label,
                    "path": path,
                    "sha256": sha256 or None,
                }
            )
        return normalized

    def _normalize_checks(
        self,
        payload: object,
        *,
        include_admin_details: bool,
    ) -> list[dict[str, object]]:
        if not isinstance(payload, list):
            return []
        checks: list[dict[str, object]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            entry: dict[str, object] = {
                "id": str(item.get("id", "")).strip() or "unknown-check",
                "title": str(item.get("title", "")).strip() or "Unnamed check",
                "status": self._normalize_status(item.get("status")),
                "blockingPolicy": self._normalize_blocking_policy(
                    item.get("blockingPolicy")
                ),
                "detail": str(item.get("detail", "")).strip(),
                "durationSeconds": self._as_non_negative_float(
                    item.get("durationSeconds", 0)
                ),
                "evidence": self._normalize_evidence(item.get("evidence")),
            }
            if include_admin_details:
                command = item.get("command")
                if isinstance(command, str) and command.strip():
                    entry["command"] = command.strip()
                exit_code = item.get("exitCode")
                if exit_code is not None:
                    try:
                        entry["exitCode"] = int(exit_code)
                    except (TypeError, ValueError):
                        entry["exitCode"] = None
            checks.append(entry)
        return checks

    def _normalize_categories(
        self,
        payload: object,
        *,
        include_admin_details: bool,
    ) -> list[dict[str, object]]:
        if not isinstance(payload, list):
            return []
        categories: list[dict[str, object]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            category_id = str(item.get("id", "")).strip() or "unknown-category"
            auditor_visible = bool(item.get("auditorVisible", False))
            if not include_admin_details and not (
                auditor_visible and category_id in _SAFE_AUDITOR_CATEGORY_IDS
            ):
                continue
            checks = self._normalize_checks(
                item.get("checks"), include_admin_details=include_admin_details
            )
            categories.append(
                {
                    "id": category_id,
                    "title": str(item.get("title", "")).strip() or "Unnamed category",
                    "status": self._normalize_status(item.get("status")),
                    "blockingPolicy": self._normalize_blocking_policy(
                        item.get("blockingPolicy")
                    ),
                    "summary": str(item.get("summary", "")).strip(),
                    "auditorVisible": auditor_visible,
                    "checks": checks,
                }
            )
        return categories

    def _normalize_blockers(
        self,
        payload: object,
        *,
        include_admin_details: bool,
    ) -> list[dict[str, object]]:
        if not isinstance(payload, list):
            return []
        blockers: list[dict[str, object]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            category_id = str(item.get("categoryId", "")).strip() or "unknown-category"
            if not include_admin_details and category_id not in _SAFE_AUDITOR_CATEGORY_IDS:
                continue
            blocker: dict[str, object] = {
                "categoryId": category_id,
                "checkId": str(item.get("checkId", "")).strip() or "unknown-check",
                "detail": str(item.get("detail", "")).strip(),
                "evidencePath": str(item.get("evidencePath", "")).strip() or None,
            }
            blockers.append(blocker)
        return blockers

    def get_readiness_snapshot(
        self,
        *,
        include_admin_details: bool,
    ) -> ReadinessAuditSnapshot:
        payload = self._load_report()
        if payload is None:
            return self._unavailable_snapshot(
                f"Readiness evidence report not found at {self._report_path}."
            )
        generated_at = self._as_datetime(payload.get("generatedAt")) or self._now()
        categories = self._normalize_categories(
            payload.get("categories"), include_admin_details=include_admin_details
        )
        blockers = self._normalize_blockers(
            payload.get("blockers"), include_admin_details=include_admin_details
        )
        overall_status = self._normalize_status(payload.get("overallStatus"))
        if overall_status == "PASS" and blockers:
            overall_status = "FAIL"
        if not categories and overall_status != "UNAVAILABLE":
            overall_status = "UNAVAILABLE"

        return ReadinessAuditSnapshot(
            matrix_version=str(payload.get("matrixVersion", "")).strip()
            or "phase-11-cross-phase-readiness-v1",
            generated_at=generated_at,
            overall_status=overall_status,
            detail=str(payload.get("detail", "")).strip()
            or (
                "Cross-phase readiness evidence is available."
                if overall_status == "PASS"
                else "Cross-phase readiness evidence contains blocking failures."
            ),
            blocking_failure_count=self._as_non_negative_int(
                payload.get("blockingFailureCount")
            ),
            category_count=len(categories),
            categories=categories,
            blockers=blockers,
        )


@lru_cache
def get_readiness_audit_service() -> ReadinessAuditService:
    settings = get_settings()
    return ReadinessAuditService(settings=settings)


__all__ = [
    "ReadinessAuditService",
    "ReadinessAuditSnapshot",
    "get_readiness_audit_service",
]
