from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

from app.auth.models import SessionPrincipal
from app.core.config import Settings, get_settings

RunbookStatus = Literal["ACTIVE", "REVIEW_REQUIRED", "DRAFT", "ARCHIVED"]
IncidentSeverity = Literal["SEV1", "SEV2", "SEV3", "SEV4"]
IncidentStatus = Literal["OPEN", "MITIGATING", "RESOLVED"]

_RUNBOOK_STATUSES: set[str] = {"ACTIVE", "REVIEW_REQUIRED", "DRAFT", "ARCHIVED"}
_INCIDENT_SEVERITIES: set[str] = {"SEV1", "SEV2", "SEV3", "SEV4"}
_INCIDENT_STATUSES: set[str] = {"OPEN", "MITIGATING", "RESOLVED"}
_RUNBOOK_READ_ROLES: set[str] = {"ADMIN"}
_INCIDENT_READ_ROLES: set[str] = {"ADMIN", "AUDITOR"}

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_ORDERED_LIST_RE = re.compile(r"^\d+\.\s+(.*)$")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")


@dataclass(frozen=True)
class RunbookRecord:
    id: str
    slug: str
    title: str
    owner_user_id: str
    last_reviewed_at: datetime
    status: RunbookStatus
    storage_key: str


@dataclass(frozen=True)
class RunbookContent:
    runbook: RunbookRecord
    content_markdown: str
    content_html: str


@dataclass(frozen=True)
class IncidentRecord:
    id: str
    severity: IncidentSeverity
    status: IncidentStatus
    started_at: datetime
    resolved_at: datetime | None
    incident_commander_user_id: str
    summary: str


@dataclass(frozen=True)
class IncidentTimelineEventRecord:
    id: str
    incident_id: str
    event_type: str
    actor_user_id: str
    summary: str
    created_at: datetime


@dataclass(frozen=True)
class IncidentStatusSnapshot:
    generated_at: datetime
    open_incident_count: int
    unresolved_high_severity_count: int
    by_status: list[dict[str, object]]
    by_severity: list[dict[str, object]]
    no_go_triggered: bool
    no_go_reasons: list[str]
    latest_started_at: datetime | None
    go_live_rehearsal_status: str
    incident_response_tabletop_status: str
    model_rollback_rehearsal_status: str


class LaunchOperationsAccessDeniedError(RuntimeError):
    """Current session cannot access launch-operations routes."""


class LaunchOperationsNotFoundError(RuntimeError):
    """Requested launch-operations record does not exist."""


class LaunchOperationsDataUnavailableError(RuntimeError):
    """Launch-operations catalog or backing document data is unavailable."""


def _parse_datetime(value: object, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise LaunchOperationsDataUnavailableError(f"{field} must be an ISO datetime string.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise LaunchOperationsDataUnavailableError(
            f"{field} is not a valid ISO datetime string."
        ) from error
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _inline_markdown_to_html(value: str) -> str:
    parts: list[str] = []
    last_index = 0
    for match in _INLINE_CODE_RE.finditer(value):
        start, end = match.span()
        parts.append(html.escape(value[last_index:start], quote=True))
        parts.append(f"<code>{html.escape(match.group(1), quote=True)}</code>")
        last_index = end
    parts.append(html.escape(value[last_index:], quote=True))
    return "".join(parts)


def _markdown_to_html(value: str) -> str:
    lines = value.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    output: list[str] = []
    paragraph_buffer: list[str] = []
    code_buffer: list[str] = []
    list_mode: Literal["ul", "ol"] | None = None
    in_code_block = False

    def flush_paragraph() -> None:
        if not paragraph_buffer:
            return
        merged = " ".join(item.strip() for item in paragraph_buffer if item.strip())
        if merged:
            output.append(f"<p>{_inline_markdown_to_html(merged)}</p>")
        paragraph_buffer.clear()

    def close_list() -> None:
        nonlocal list_mode
        if list_mode is None:
            return
        output.append(f"</{list_mode}>")
        list_mode = None

    def close_code() -> None:
        nonlocal in_code_block
        if not in_code_block:
            return
        output.append(f"<pre><code>{html.escape('\n'.join(code_buffer), quote=True)}</code></pre>")
        code_buffer.clear()
        in_code_block = False

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

        if in_code_block:
            if stripped.startswith("```"):
                close_code()
            else:
                code_buffer.append(raw_line)
            continue

        if stripped.startswith("```"):
            flush_paragraph()
            close_list()
            in_code_block = True
            code_buffer.clear()
            continue

        if not stripped:
            flush_paragraph()
            close_list()
            continue

        heading_match = _HEADING_RE.match(stripped)
        if heading_match:
            flush_paragraph()
            close_list()
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()
            output.append(f"<h{level}>{_inline_markdown_to_html(heading_text)}</h{level}>")
            continue

        item_text: str | None = None
        next_list_mode: Literal["ul", "ol"] | None = None
        if stripped.startswith("- ") or stripped.startswith("* "):
            item_text = stripped[2:].strip()
            next_list_mode = "ul"
        else:
            ordered_match = _ORDERED_LIST_RE.match(stripped)
            if ordered_match:
                item_text = ordered_match.group(1).strip()
                next_list_mode = "ol"

        if item_text is not None and next_list_mode is not None:
            flush_paragraph()
            if list_mode != next_list_mode:
                close_list()
                output.append(f"<{next_list_mode}>")
                list_mode = next_list_mode
            output.append(f"<li>{_inline_markdown_to_html(item_text)}</li>")
            continue

        close_list()
        paragraph_buffer.append(stripped)

    flush_paragraph()
    close_list()
    close_code()

    if not output:
        return "<p></p>"
    return "\n".join(output)


class LaunchOperationsService:
    def __init__(self, *, settings: Settings, catalog_path: Path | None = None) -> None:
        self._settings = settings
        self._catalog_path = catalog_path or (
            settings.repo_root / "infra" / "readiness" / "launch-operations-catalog.v1.json"
        )

    @staticmethod
    def _require_any_role(current_user: SessionPrincipal, allowed_roles: set[str]) -> None:
        current_roles = set(current_user.platform_roles)
        if current_roles.intersection(allowed_roles):
            return
        raise LaunchOperationsAccessDeniedError(
            "Current session cannot access launch-operations routes."
        )

    def _load_catalog(self) -> dict[str, object]:
        if not self._catalog_path.exists():
            raise LaunchOperationsDataUnavailableError(
                f"Launch operations catalog is missing: {self._catalog_path}"
            )
        try:
            payload = json.loads(self._catalog_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise LaunchOperationsDataUnavailableError(
                "Launch operations catalog could not be loaded."
            ) from error
        if not isinstance(payload, dict):
            raise LaunchOperationsDataUnavailableError(
                "Launch operations catalog must be a JSON object."
            )
        return payload

    @staticmethod
    def _normalize_runbook_status(value: object) -> RunbookStatus:
        candidate = str(value).strip().upper()
        if candidate in _RUNBOOK_STATUSES:
            return candidate  # type: ignore[return-value]
        return "REVIEW_REQUIRED"

    @staticmethod
    def _normalize_incident_severity(value: object) -> IncidentSeverity:
        candidate = str(value).strip().upper()
        if candidate in _INCIDENT_SEVERITIES:
            return candidate  # type: ignore[return-value]
        return "SEV4"

    @staticmethod
    def _normalize_incident_status(value: object) -> IncidentStatus:
        candidate = str(value).strip().upper()
        if candidate in _INCIDENT_STATUSES:
            return candidate  # type: ignore[return-value]
        return "OPEN"

    def _parse_runbooks(self, payload: dict[str, object]) -> list[RunbookRecord]:
        raw_items = payload.get("runbooks")
        if not isinstance(raw_items, list):
            raise LaunchOperationsDataUnavailableError("runbooks must be an array.")
        records: list[RunbookRecord] = []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            record = RunbookRecord(
                id=str(raw_item.get("id", "")).strip(),
                slug=str(raw_item.get("slug", "")).strip(),
                title=str(raw_item.get("title", "")).strip(),
                owner_user_id=str(raw_item.get("ownerUserId", "")).strip(),
                last_reviewed_at=_parse_datetime(
                    raw_item.get("lastReviewedAt"), field="runbook.lastReviewedAt"
                ),
                status=self._normalize_runbook_status(raw_item.get("status")),
                storage_key=str(raw_item.get("storageKey", "")).strip(),
            )
            if (
                not record.id
                or not record.slug
                or not record.title
                or not record.owner_user_id
                or not record.storage_key
            ):
                continue
            records.append(record)
        records.sort(key=lambda item: (item.status != "ACTIVE", item.title.lower(), item.id))
        return records

    def _parse_incidents(self, payload: dict[str, object]) -> list[IncidentRecord]:
        raw_items = payload.get("incidents")
        if not isinstance(raw_items, list):
            raise LaunchOperationsDataUnavailableError("incidents must be an array.")
        records: list[IncidentRecord] = []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            resolved_raw = raw_item.get("resolvedAt")
            resolved_at = (
                _parse_datetime(resolved_raw, field="incident.resolvedAt")
                if isinstance(resolved_raw, str) and resolved_raw.strip()
                else None
            )
            record = IncidentRecord(
                id=str(raw_item.get("id", "")).strip(),
                severity=self._normalize_incident_severity(raw_item.get("severity")),
                status=self._normalize_incident_status(raw_item.get("status")),
                started_at=_parse_datetime(raw_item.get("startedAt"), field="incident.startedAt"),
                resolved_at=resolved_at,
                incident_commander_user_id=str(
                    raw_item.get("incidentCommanderUserId", "")
                ).strip(),
                summary=str(raw_item.get("summary", "")).strip(),
            )
            if (
                not record.id
                or not record.incident_commander_user_id
                or not record.summary
            ):
                continue
            records.append(record)
        records.sort(key=lambda item: (item.started_at, item.id), reverse=True)
        return records

    def _parse_incident_timeline(
        self, payload: dict[str, object]
    ) -> list[IncidentTimelineEventRecord]:
        raw_items = payload.get("incidentTimelineEvents")
        if not isinstance(raw_items, list):
            raise LaunchOperationsDataUnavailableError(
                "incidentTimelineEvents must be an array."
            )
        records: list[IncidentTimelineEventRecord] = []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            record = IncidentTimelineEventRecord(
                id=str(raw_item.get("id", "")).strip(),
                incident_id=str(raw_item.get("incidentId", "")).strip(),
                event_type=str(raw_item.get("eventType", "")).strip(),
                actor_user_id=str(raw_item.get("actorUserId", "")).strip(),
                summary=str(raw_item.get("summary", "")).strip(),
                created_at=_parse_datetime(
                    raw_item.get("createdAt"), field="incidentTimelineEvent.createdAt"
                ),
            )
            if (
                not record.id
                or not record.incident_id
                or not record.event_type
                or not record.actor_user_id
                or not record.summary
            ):
                continue
            records.append(record)
        records.sort(key=lambda item: (item.created_at, item.id))
        return records

    def list_runbooks(self, *, current_user: SessionPrincipal) -> list[RunbookRecord]:
        self._require_any_role(current_user, _RUNBOOK_READ_ROLES)
        payload = self._load_catalog()
        return self._parse_runbooks(payload)

    def get_runbook(self, *, current_user: SessionPrincipal, runbook_id: str) -> RunbookRecord:
        self._require_any_role(current_user, _RUNBOOK_READ_ROLES)
        runbook_id = runbook_id.strip()
        if not runbook_id:
            raise LaunchOperationsNotFoundError("Runbook not found.")
        for record in self.list_runbooks(current_user=current_user):
            if record.id == runbook_id:
                return record
        raise LaunchOperationsNotFoundError("Runbook not found.")

    def get_runbook_content(
        self, *, current_user: SessionPrincipal, runbook_id: str
    ) -> RunbookContent:
        runbook = self.get_runbook(current_user=current_user, runbook_id=runbook_id)
        runbook_path = (self._settings.repo_root / runbook.storage_key).resolve()
        try:
            runbook_path.relative_to(self._settings.repo_root)
        except ValueError as error:
            raise LaunchOperationsDataUnavailableError(
                "Runbook storage key resolves outside the repository root."
            ) from error
        if not runbook_path.exists() or not runbook_path.is_file():
            raise LaunchOperationsDataUnavailableError(
                f"Runbook content file is missing: {runbook.storage_key}"
            )
        try:
            content_markdown = runbook_path.read_text(encoding="utf-8")
        except OSError as error:
            raise LaunchOperationsDataUnavailableError(
                "Runbook content file could not be loaded."
            ) from error
        return RunbookContent(
            runbook=runbook,
            content_markdown=content_markdown,
            content_html=_markdown_to_html(content_markdown),
        )

    def list_incidents(self, *, current_user: SessionPrincipal) -> list[IncidentRecord]:
        self._require_any_role(current_user, _INCIDENT_READ_ROLES)
        payload = self._load_catalog()
        return self._parse_incidents(payload)

    def get_incident(self, *, current_user: SessionPrincipal, incident_id: str) -> IncidentRecord:
        self._require_any_role(current_user, _INCIDENT_READ_ROLES)
        incident_id = incident_id.strip()
        if not incident_id:
            raise LaunchOperationsNotFoundError("Incident not found.")
        for record in self.list_incidents(current_user=current_user):
            if record.id == incident_id:
                return record
        raise LaunchOperationsNotFoundError("Incident not found.")

    def list_incident_timeline(
        self, *, current_user: SessionPrincipal, incident_id: str
    ) -> list[IncidentTimelineEventRecord]:
        self._require_any_role(current_user, _INCIDENT_READ_ROLES)
        self.get_incident(current_user=current_user, incident_id=incident_id)
        payload = self._load_catalog()
        events = self._parse_incident_timeline(payload)
        return [item for item in events if item.incident_id == incident_id]

    @staticmethod
    def _status_counts(
        incidents: list[IncidentRecord],
        *,
        key_fn,
    ) -> list[dict[str, object]]:  # type: ignore[no-untyped-def]
        counts: dict[str, int] = {}
        for item in incidents:
            key = str(key_fn(item))
            counts[key] = counts.get(key, 0) + 1
        return [
            {"key": key, "count": counts[key]}
            for key in sorted(counts.keys())
        ]

    @staticmethod
    def _launch_status(value: object) -> str:
        candidate = str(value).strip().upper()
        if candidate in {"COMPLETED", "PENDING", "BLOCKED"}:
            return candidate
        return "PENDING"

    def get_incident_status(self, *, current_user: SessionPrincipal) -> IncidentStatusSnapshot:
        self._require_any_role(current_user, _INCIDENT_READ_ROLES)
        payload = self._load_catalog()
        incidents = self._parse_incidents(payload)

        open_incident_count = sum(1 for item in incidents if item.status != "RESOLVED")
        unresolved_high = sum(
            1
            for item in incidents
            if item.status != "RESOLVED" and item.severity in {"SEV1", "SEV2"}
        )

        launch_readiness = payload.get("launchReadiness")
        if not isinstance(launch_readiness, dict):
            launch_readiness = {}
        go_live_status = self._launch_status(
            (launch_readiness.get("goLiveRehearsal") or {}).get("status")  # type: ignore[union-attr]
            if isinstance(launch_readiness.get("goLiveRehearsal"), dict)
            else None
        )
        tabletop_status = self._launch_status(
            (launch_readiness.get("incidentResponseTabletop") or {}).get("status")  # type: ignore[union-attr]
            if isinstance(launch_readiness.get("incidentResponseTabletop"), dict)
            else None
        )
        rollback_status = self._launch_status(
            (launch_readiness.get("modelRollbackRehearsal") or {}).get("status")  # type: ignore[union-attr]
            if isinstance(launch_readiness.get("modelRollbackRehearsal"), dict)
            else None
        )

        reasons: list[str] = []
        if unresolved_high > 0:
            reasons.append("Open SEV1/SEV2 incidents require mitigation before ship.")
        if go_live_status != "COMPLETED":
            reasons.append("Go-live rehearsal is not marked COMPLETED.")
        if tabletop_status != "COMPLETED":
            reasons.append("Incident response tabletop is not marked COMPLETED.")
        if rollback_status != "COMPLETED":
            reasons.append("Primary VLM rollback rehearsal is not marked COMPLETED.")

        latest_started_at = incidents[0].started_at if incidents else None
        return IncidentStatusSnapshot(
            generated_at=datetime.now(UTC),
            open_incident_count=open_incident_count,
            unresolved_high_severity_count=unresolved_high,
            by_status=self._status_counts(incidents, key_fn=lambda item: item.status),
            by_severity=self._status_counts(incidents, key_fn=lambda item: item.severity),
            no_go_triggered=bool(reasons),
            no_go_reasons=reasons,
            latest_started_at=latest_started_at,
            go_live_rehearsal_status=go_live_status,
            incident_response_tabletop_status=tabletop_status,
            model_rollback_rehearsal_status=rollback_status,
        )


@lru_cache
def get_launch_operations_service() -> LaunchOperationsService:
    settings = get_settings()
    return LaunchOperationsService(settings=settings)


__all__ = [
    "IncidentRecord",
    "IncidentStatusSnapshot",
    "IncidentTimelineEventRecord",
    "LaunchOperationsAccessDeniedError",
    "LaunchOperationsDataUnavailableError",
    "LaunchOperationsNotFoundError",
    "LaunchOperationsService",
    "RunbookContent",
    "RunbookRecord",
    "get_launch_operations_service",
]
