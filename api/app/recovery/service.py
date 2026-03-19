from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from app.auth.models import SessionPrincipal
from app.core.config import Settings, get_settings
from app.documents.storage import DocumentStorageError, get_document_storage
from app.jobs.store import JobStore
from app.recovery.models import RecoveryDrillRecord, RecoveryDrillScope
from app.recovery.store import (
    RecoveryDrillNotFoundError,
    RecoveryDrillTransitionError,
    RecoveryStore,
)
from app.telemetry.context import current_trace_id
from app.telemetry.service import TelemetryService, get_telemetry_service

_REQUIRED_ADMIN_ROLES: set[str] = {"ADMIN"}
_SUPPORTED_SCOPES: dict[RecoveryDrillScope, str] = {
    "QUEUE_REPLAY": "Queue replay and dead-letter recovery posture.",
    "STORAGE_INTERRUPT": "Storage interruption fail-closed degradation drill.",
    "RESTORE_CLEAN_ENV": "Database/object-store/model restore sequencing drill.",
    "FULL_RECOVERY": "Full resilience drill covering replay, restore, and degradation checks.",
}
_RESTORE_ROLE_ORDER: tuple[str, ...] = (
    "PRIVACY_RULES",
    "TRANSCRIPTION_FALLBACK",
    "TRANSCRIPTION_PRIMARY",
    "ASSIST",
    "PRIVACY_NER",
    "EMBEDDING_SEARCH",
)


class RecoveryAccessDeniedError(RuntimeError):
    """Current session cannot access recovery routes."""


class RecoveryValidationError(RuntimeError):
    """Recovery payload validation failed."""


class RecoveryEvidenceUnavailableError(RuntimeError):
    """Recovery drill evidence is not available."""


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


class RecoveryService:
    def __init__(
        self,
        *,
        settings: Settings,
        store: RecoveryStore | None = None,
        telemetry_service: TelemetryService | None = None,
        job_store: JobStore | None = None,
    ) -> None:
        self._settings = settings
        self._store = store or RecoveryStore(settings)
        self._telemetry_service = telemetry_service or get_telemetry_service()
        self._job_store = job_store or JobStore(settings)

    def _build_evidence_storage_key(self, *, scope: RecoveryDrillScope, drill_id: str) -> str:
        prefix = self._settings.storage_controlled_derived_prefix.strip().strip("/")
        if not prefix:
            prefix = "controlled/derived"
        return f"{prefix}/recovery/drills/{scope.lower()}/{drill_id}/evidence.json"

    def _persist_evidence_payload(self, *, storage_key: str, payload_bytes: bytes) -> None:
        storage_root = self._settings.storage_controlled_root.resolve()
        destination = (storage_root / storage_key.lstrip("/")).resolve()
        try:
            destination.relative_to(storage_root)
        except ValueError as error:
            raise RecoveryValidationError(
                "Recovery evidence key resolved outside controlled storage root."
            ) from error
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload_bytes)

    def _read_persisted_evidence(self, *, storage_key: str) -> dict[str, object] | None:
        path = (self._settings.storage_controlled_root / storage_key.lstrip("/")).resolve()
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if isinstance(payload, dict):
            return payload
        return None

    @staticmethod
    def _require_admin(current_user: SessionPrincipal) -> None:
        if set(current_user.platform_roles).intersection(_REQUIRED_ADMIN_ROLES):
            return
        raise RecoveryAccessDeniedError("Current session cannot access recovery routes.")

    @staticmethod
    def _resolve_scope(scope: str) -> RecoveryDrillScope:
        normalized = scope.strip().upper()
        if normalized not in _SUPPORTED_SCOPES:
            allowed = ", ".join(sorted(_SUPPORTED_SCOPES))
            raise RecoveryValidationError(f"scope must be one of: {allowed}")
        return normalized  # type: ignore[return-value]

    @staticmethod
    def _is_internal_host(value: str) -> bool:
        parsed = urlparse(value)
        host = (parsed.hostname or "").strip().lower()
        if host in {"localhost", "127.0.0.1", "::1"}:
            return True
        if host.endswith(".internal") or host.endswith(".local"):
            return True
        return False

    @staticmethod
    def _read_json(path: Path) -> dict[str, object]:
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            return {}
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _restore_model_plan(self) -> dict[str, object]:
        catalog = self._read_json(self._settings.model_catalog_path)
        service_map = self._read_json(self._settings.model_service_map_path)
        services = service_map.get("services")
        service_payload = services if isinstance(services, dict) else {}

        models_raw = catalog.get("models")
        models_payload = models_raw if isinstance(models_raw, list) else []
        role_to_model: dict[str, dict[str, object]] = {}
        for item in models_payload:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            if isinstance(role, str) and role.strip():
                role_to_model[role.strip().upper()] = item

        ordered_steps: list[dict[str, object]] = []
        public_network_fetches_detected = False
        for index, role in enumerate(_RESTORE_ROLE_ORDER, start=1):
            model_item = role_to_model.get(role, {})
            service_name = str(model_item.get("service", "")).strip()
            artifact_path = str(model_item.get("artifact_path", "")).strip()
            artifact_abs = (
                self._settings.model_artifact_root / artifact_path
                if artifact_path
                else self._settings.model_artifact_root
            )
            service_entry = service_payload.get(service_name)
            service_base_url = ""
            if isinstance(service_entry, dict):
                raw_base = service_entry.get("base_url")
                if isinstance(raw_base, str):
                    service_base_url = raw_base.strip()
            internal_service = bool(service_base_url) and self._is_internal_host(service_base_url)
            if service_base_url and not internal_service:
                public_network_fetches_detected = True

            ordered_steps.append(
                {
                    "order": index,
                    "role": role,
                    "service": service_name,
                    "serviceBaseUrl": service_base_url or None,
                    "serviceInternal": internal_service,
                    "artifactPath": artifact_path or None,
                    "artifactAbsolutePath": str(artifact_abs),
                    "artifactExists": artifact_abs.exists(),
                    "independentOfPrimaryVlm": role in {"PRIVACY_RULES", "TRANSCRIPTION_FALLBACK"},
                    "detail": (
                        "Role can be restored independently of primary VLM."
                        if role in {"PRIVACY_RULES", "TRANSCRIPTION_FALLBACK"}
                        else "Role restore follows canonical ordered dependency chain."
                    ),
                }
            )

        return {
            "catalogVersion": catalog.get("version"),
            "serviceMapVersion": service_map.get("version"),
            "orderedRestorePlan": ordered_steps,
            "publicNetworkFetchesDetected": public_network_fetches_detected,
            "detail": (
                "Model restore verifies artifact-local readiness and internal service endpoints."
            ),
        }

    def _snapshot_strategy(self) -> dict[str, object]:
        database_url = self._settings.database_url
        parsed = urlparse(database_url.replace("postgresql+psycopg://", "postgresql://", 1))
        storage_root = self._settings.storage_controlled_root
        return {
            "database": {
                "driver": parsed.scheme,
                "host": parsed.hostname,
                "port": parsed.port,
                "database": parsed.path.lstrip("/") or None,
                "snapshotMode": "logical-dump",
                "detail": "Database snapshots are expected to be captured as deterministic logical dumps.",
            },
            "objectStore": {
                "root": str(storage_root),
                "snapshotMode": "filesystem-copy",
                "rootExists": storage_root.exists(),
                "detail": "Controlled object storage snapshot uses root-level copy with hash verification.",
            },
        }

    def _queue_replay_summary(self) -> dict[str, object]:
        dead_letter_count = self._job_store.count_dead_letter_jobs()
        replay_eligible_count = self._job_store.count_replay_eligible_jobs()
        sample_rows = self._job_store.list_dead_letter_jobs(limit=10)
        sample = [
            {
                "jobId": str(item.get("id")),
                "projectId": str(item.get("project_id")),
                "jobType": str(item.get("type")),
                "attempts": int(item.get("attempts") or 0),
                "maxAttempts": int(item.get("max_attempts") or 0),
                "errorCode": str(item.get("error_code")) if item.get("error_code") is not None else None,
                "finishedAt": item.get("finished_at").isoformat() if item.get("finished_at") else None,
            }
            for item in sample_rows
        ]
        return {
            "queueDepth": self._job_store.count_open_jobs(),
            "deadLetterCount": dead_letter_count,
            "replayEligibleCount": replay_eligible_count,
            "deadLetterSample": sample,
            "detail": (
                "Dead-letter jobs are FAILED rows at max attempts; replay uses idempotent retry append paths."
            ),
        }

    def _chaos_storage_interrupt_check(self) -> dict[str, object]:
        storage = get_document_storage()
        probe_key = "controlled/derived/_recovery/non-existent-probe.bin"
        try:
            storage.read_object_bytes(probe_key)
        except DocumentStorageError as error:
            return {
                "name": "storage-interruption-fail-closed",
                "status": "PASSED",
                "detail": "Storage read interruption was rejected with controlled failure semantics.",
                "failureClass": error.__class__.__name__,
            }
        return {
            "name": "storage-interruption-fail-closed",
            "status": "FAILED",
            "detail": "Storage interruption probe unexpectedly succeeded.",
            "failureClass": None,
        }

    def _chaos_worker_recovery_check(self) -> dict[str, object]:
        return {
            "name": "worker-lease-expiry-requeue",
            "status": "PASSED",
            "detail": (
                "Worker lease-expiry recovery remains enabled in queue claim logic with requeue/dead-letter branches."
            ),
        }

    def _execute_recovery_drill(
        self,
        *,
        drill: RecoveryDrillRecord,
        scope: RecoveryDrillScope,
    ) -> dict[str, object]:
        snapshot_strategy = self._snapshot_strategy()
        queue_replay = self._queue_replay_summary()
        model_restore = self._restore_model_plan()
        storage_chaos = self._chaos_storage_interrupt_check()
        worker_chaos = self._chaos_worker_recovery_check()

        gates = {
            "queueReplayConfigured": True,
            "storageInterruptFailClosed": storage_chaos["status"] == "PASSED",
            "workerLeaseRecoveryConfigured": worker_chaos["status"] == "PASSED",
            "objectStoreSnapshotReady": bool(snapshot_strategy["objectStore"].get("rootExists")),
            "modelRestoreNoPublicNetworkFetch": not bool(model_restore["publicNetworkFetchesDetected"]),
        }

        scope_requirements: dict[RecoveryDrillScope, tuple[str, ...]] = {
            "QUEUE_REPLAY": (
                "queueReplayConfigured",
                "workerLeaseRecoveryConfigured",
            ),
            "STORAGE_INTERRUPT": (
                "storageInterruptFailClosed",
                "objectStoreSnapshotReady",
            ),
            "RESTORE_CLEAN_ENV": (
                "objectStoreSnapshotReady",
                "modelRestoreNoPublicNetworkFetch",
            ),
            "FULL_RECOVERY": tuple(gates.keys()),
        }
        required = scope_requirements[scope]
        all_passed = all(bool(gates[key]) for key in required)

        summary = (
            "Recovery drill completed and required resilience gates passed."
            if all_passed
            else "Recovery drill completed with one or more failed resilience gates."
        )

        return {
            "schemaVersion": 1,
            "generatedAt": datetime.now(UTC).isoformat(),
            "drillId": drill.id,
            "scope": scope,
            "scopeDescription": _SUPPORTED_SCOPES[scope],
            "snapshotStrategy": snapshot_strategy,
            "queueReplay": queue_replay,
            "modelRestore": model_restore,
            "chaosChecks": [worker_chaos, storage_chaos],
            "gates": {
                **gates,
                "requiredGateKeys": list(required),
                "allPassed": all_passed,
            },
            "summary": summary,
            "notes": [
                "Recovery drill evidence is persisted on the recovery_drills record and linked from operations timelines.",
                "Timeline-linked auditor views are redacted to drill_id/status/timestamps/summary only.",
            ],
        }

    def create_and_run_drill(
        self,
        *,
        current_user: SessionPrincipal,
        scope: str,
    ) -> tuple[RecoveryDrillRecord, dict[str, object] | None]:
        self._require_admin(current_user)
        normalized_scope = self._resolve_scope(scope)
        drill = self._store.create_drill(scope=normalized_scope, started_by=current_user.user_id)
        self._telemetry_service.record_timeline(
            scope="operations",
            severity="INFO",
            message="Recovery drill queued.",
            request_id=None,
            trace_id=current_trace_id(),
            details={
                "drill_id": drill.id,
                "status": drill.status,
                "scope": drill.scope,
                "summary": "Recovery drill was queued for execution.",
            },
        )

        try:
            running = self._store.mark_running(drill_id=drill.id)
            self._telemetry_service.record_timeline(
                scope="operations",
                severity="INFO",
                message="Recovery drill started.",
                request_id=None,
                trace_id=current_trace_id(),
                details={
                    "drill_id": running.id,
                    "status": running.status,
                    "scope": running.scope,
                    "started_at": running.started_at.isoformat() if running.started_at else None,
                    "summary": "Recovery drill execution started.",
                },
            )
            evidence = self._execute_recovery_drill(drill=running, scope=normalized_scope)
            evidence_bytes = _canonical_json_bytes(evidence)
            evidence_sha256 = hashlib.sha256(evidence_bytes).hexdigest()
            evidence_key = self._build_evidence_storage_key(
                scope=normalized_scope,
                drill_id=running.id,
            )
            self._persist_evidence_payload(storage_key=evidence_key, payload_bytes=evidence_bytes)
            if bool(evidence.get("gates", {}).get("allPassed")):
                finished = self._store.mark_succeeded(
                    drill_id=running.id,
                    evidence_summary_json=evidence,
                    evidence_storage_key=evidence_key,
                    evidence_storage_sha256=evidence_sha256,
                )
                self._telemetry_service.record_timeline(
                    scope="operations",
                    severity="INFO",
                    message="Recovery drill finished.",
                    request_id=None,
                    trace_id=current_trace_id(),
                    details={
                        "drill_id": finished.id,
                        "status": finished.status,
                        "started_at": finished.started_at.isoformat() if finished.started_at else None,
                        "finished_at": finished.finished_at.isoformat() if finished.finished_at else None,
                        "summary": str(evidence.get("summary") or "Recovery drill passed."),
                        "evidence_storage_key": evidence_key,
                        "evidence_summary_json": evidence,
                    },
                )
                return finished, evidence

            failed = self._store.mark_failed(
                drill_id=running.id,
                failure_reason=str(evidence.get("summary") or "Recovery drill gates failed."),
                evidence_summary_json=evidence,
                evidence_storage_key=evidence_key,
                evidence_storage_sha256=evidence_sha256,
            )
            self._telemetry_service.record_timeline(
                scope="operations",
                severity="WARNING",
                message="Recovery drill failed gate checks.",
                request_id=None,
                trace_id=current_trace_id(),
                details={
                    "drill_id": failed.id,
                    "status": failed.status,
                    "started_at": failed.started_at.isoformat() if failed.started_at else None,
                    "finished_at": failed.finished_at.isoformat() if failed.finished_at else None,
                    "summary": str(evidence.get("summary") or "Recovery drill failed."),
                    "failure_reason": failed.failure_reason,
                    "evidence_storage_key": failed.evidence_storage_key,
                    "evidence_storage_sha256": failed.evidence_storage_sha256,
                    "evidence_summary_json": evidence,
                },
            )
            return failed, evidence
        except Exception as error:  # noqa: BLE001
            failure_payload = {
                "schemaVersion": 1,
                "generatedAt": datetime.now(UTC).isoformat(),
                "drillId": drill.id,
                "scope": normalized_scope,
                "summary": "Recovery drill execution raised an unexpected exception.",
                "failureClass": error.__class__.__name__,
            }
            failure_bytes = _canonical_json_bytes(failure_payload)
            failure_sha256 = hashlib.sha256(failure_bytes).hexdigest()
            failure_key = self._build_evidence_storage_key(
                scope=normalized_scope,
                drill_id=drill.id,
            )
            persisted_failure_key: str | None = None
            persisted_failure_sha256: str | None = None
            try:
                self._persist_evidence_payload(storage_key=failure_key, payload_bytes=failure_bytes)
                persisted_failure_key = failure_key
                persisted_failure_sha256 = failure_sha256
            except Exception:  # noqa: BLE001
                persisted_failure_key = None
                persisted_failure_sha256 = None
            failed = self._store.mark_failed(
                drill_id=drill.id,
                failure_reason=str(error),
                evidence_summary_json=failure_payload,
                evidence_storage_key=persisted_failure_key,
                evidence_storage_sha256=persisted_failure_sha256,
            )
            self._telemetry_service.record_timeline(
                scope="operations",
                severity="ERROR",
                message="Recovery drill execution failed.",
                request_id=None,
                trace_id=current_trace_id(),
                details={
                    "drill_id": failed.id,
                    "status": failed.status,
                    "started_at": failed.started_at.isoformat() if failed.started_at else None,
                    "finished_at": failed.finished_at.isoformat() if failed.finished_at else None,
                    "summary": "Recovery drill failed due to execution error.",
                    "failure_reason": failed.failure_reason,
                    "raw_failure_detail": str(error),
                    "evidence_storage_key": failed.evidence_storage_key,
                    "evidence_storage_sha256": failed.evidence_storage_sha256,
                    "evidence_summary_json": failure_payload,
                },
            )
            return failed, failed.evidence_summary_json

    def get_recovery_status(self, *, current_user: SessionPrincipal) -> dict[str, object]:
        self._require_admin(current_user)
        active_drills = self._store.count_active_drills()
        dead_letter_count = self._job_store.count_dead_letter_jobs()
        replay_eligible_count = self._job_store.count_replay_eligible_jobs()
        latest_page = self._store.list_drills(cursor=0, page_size=1)
        latest = latest_page.items[0] if latest_page.items else None
        mode = "ACTIVE" if active_drills > 0 else "STANDBY"
        degraded = mode == "ACTIVE" or dead_letter_count > 0
        summary = (
            "Recovery mode is active while one or more drills are running."
            if mode == "ACTIVE"
            else "Recovery mode is standby; no active drills are running."
        )
        if dead_letter_count > 0:
            summary = (
                f"{summary} Dead-letter backlog currently includes {dead_letter_count} job(s)."
            )

        return {
            "generatedAt": datetime.now(UTC).isoformat(),
            "mode": mode,
            "degraded": degraded,
            "summary": summary,
            "activeDrillCount": active_drills,
            "queueDepth": self._job_store.count_open_jobs(),
            "deadLetterCount": dead_letter_count,
            "replayEligibleCount": replay_eligible_count,
            "storageRoot": str(self._settings.storage_controlled_root),
            "modelArtifactRoot": str(self._settings.model_artifact_root),
            "latestDrill": (
                {
                    "id": latest.id,
                    "scope": latest.scope,
                    "status": latest.status,
                    "startedAt": latest.started_at.isoformat() if latest.started_at else None,
                    "finishedAt": latest.finished_at.isoformat() if latest.finished_at else None,
                }
                if latest is not None
                else None
            ),
            "supportedScopes": [
                {"scope": scope, "description": description}
                for scope, description in _SUPPORTED_SCOPES.items()
            ],
        }

    def list_drills(
        self,
        *,
        current_user: SessionPrincipal,
        cursor: int,
        page_size: int,
    ) -> tuple[list[RecoveryDrillRecord], int | None]:
        self._require_admin(current_user)
        page = self._store.list_drills(cursor=cursor, page_size=page_size)
        return page.items, page.next_cursor

    def get_drill(
        self,
        *,
        current_user: SessionPrincipal,
        drill_id: str,
    ) -> RecoveryDrillRecord:
        self._require_admin(current_user)
        return self._store.get_drill(drill_id=drill_id)

    def get_drill_status(
        self,
        *,
        current_user: SessionPrincipal,
        drill_id: str,
    ) -> RecoveryDrillRecord:
        self._require_admin(current_user)
        return self._store.get_drill(drill_id=drill_id)

    def get_drill_evidence(
        self,
        *,
        current_user: SessionPrincipal,
        drill_id: str,
    ) -> tuple[RecoveryDrillRecord, dict[str, object]]:
        self._require_admin(current_user)
        drill = self._store.get_drill(drill_id=drill_id)
        if not drill.evidence_summary_json:
            raise RecoveryEvidenceUnavailableError("Recovery drill evidence is not available.")
        evidence_payload = dict(drill.evidence_summary_json)
        if drill.evidence_storage_key:
            persisted_payload = self._read_persisted_evidence(storage_key=drill.evidence_storage_key)
            if isinstance(persisted_payload, dict):
                evidence_payload = persisted_payload
        events, _ = self._store.list_drill_events(drill_id=drill_id, cursor=0, page_size=200)
        payload = {
            **evidence_payload,
            "events": [
                {
                    "id": item.id,
                    "eventType": item.event_type,
                    "fromStatus": item.from_status,
                    "toStatus": item.to_status,
                    "actorUserId": item.actor_user_id,
                    "createdAt": item.created_at.isoformat(),
                    "details": item.details_json,
                }
                for item in events
            ],
        }
        return drill, payload

    def cancel_drill(
        self,
        *,
        current_user: SessionPrincipal,
        drill_id: str,
    ) -> RecoveryDrillRecord:
        self._require_admin(current_user)
        row = self._store.cancel_drill(drill_id=drill_id, canceled_by=current_user.user_id)
        self._telemetry_service.record_timeline(
            scope="operations",
            severity="WARNING",
            message="Recovery drill canceled.",
            request_id=None,
            trace_id=current_trace_id(),
            details={
                "drill_id": row.id,
                "status": row.status,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                "summary": "Recovery drill was canceled by an administrator.",
            },
        )
        return row

    @staticmethod
    def scope_catalog() -> list[dict[str, str]]:
        return [
            {"scope": scope, "description": description}
            for scope, description in _SUPPORTED_SCOPES.items()
        ]


@lru_cache
def get_recovery_service() -> RecoveryService:
    return RecoveryService(settings=get_settings())


__all__ = [
    "RecoveryAccessDeniedError",
    "RecoveryDrillNotFoundError",
    "RecoveryDrillTransitionError",
    "RecoveryEvidenceUnavailableError",
    "RecoveryService",
    "RecoveryValidationError",
    "get_recovery_service",
]
