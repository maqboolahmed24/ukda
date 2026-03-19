from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.auth.models import SessionPrincipal
from app.core.config import Settings, get_settings
from app.documents.storage import DocumentStorageError
from app.recovery.models import RecoveryDrillEventRecord, RecoveryDrillPage, RecoveryDrillRecord
from app.recovery.service import RecoveryAccessDeniedError, RecoveryService


class FakeRecoveryStore:
    def __init__(self) -> None:
        self.drills: dict[str, RecoveryDrillRecord] = {}
        self.events_by_drill: dict[str, list[RecoveryDrillEventRecord]] = {}
        self._sequence = 0
        self._event_sequence = 0

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def _next_id(self) -> str:
        self._sequence += 1
        return f"recovery-test-{self._sequence}"

    def _append_event(
        self,
        *,
        drill_id: str,
        event_type,
        from_status,
        to_status,
        actor_user_id,
        details: dict[str, object] | None = None,
    ) -> None:
        self._event_sequence += 1
        self.events_by_drill.setdefault(drill_id, []).append(
            RecoveryDrillEventRecord(
                id=self._event_sequence,
                drill_id=drill_id,
                event_type=event_type,
                from_status=from_status,
                to_status=to_status,
                actor_user_id=actor_user_id,
                details_json=dict(details or {}),
                created_at=self._now(),
            )
        )

    def create_drill(self, *, scope, started_by: str) -> RecoveryDrillRecord:
        now = self._now()
        drill = RecoveryDrillRecord(
            id=self._next_id(),
            scope=scope,
            status="QUEUED",
            started_by=started_by,
            started_at=None,
            finished_at=None,
            canceled_by=None,
            canceled_at=None,
            evidence_summary_json={},
            failure_reason=None,
            evidence_storage_key=None,
            evidence_storage_sha256=None,
            created_at=now,
            updated_at=now,
        )
        self.drills[drill.id] = drill
        self._append_event(
            drill_id=drill.id,
            event_type="DRILL_CREATED",
            from_status=None,
            to_status="QUEUED",
            actor_user_id=started_by,
            details={"scope": scope},
        )
        return drill

    def mark_running(self, *, drill_id: str) -> RecoveryDrillRecord:
        current = self.drills[drill_id]
        if current.status == "RUNNING":
            return current
        if current.status != "QUEUED":
            raise RuntimeError("invalid transition")
        updated = replace(
            current,
            status="RUNNING",
            started_at=current.started_at or self._now(),
            updated_at=self._now(),
            failure_reason=None,
        )
        self.drills[drill_id] = updated
        self._append_event(
            drill_id=drill_id,
            event_type="DRILL_STARTED",
            from_status="QUEUED",
            to_status="RUNNING",
            actor_user_id=None,
            details={"started_at": updated.started_at.isoformat() if updated.started_at else None},
        )
        return updated

    def mark_succeeded(
        self,
        *,
        drill_id: str,
        evidence_summary_json: dict[str, object],
        evidence_storage_key: str,
        evidence_storage_sha256: str,
    ) -> RecoveryDrillRecord:
        current = self.drills[drill_id]
        if current.status == "SUCCEEDED":
            return current
        if current.status != "RUNNING":
            raise RuntimeError("invalid transition")
        updated = replace(
            current,
            status="SUCCEEDED",
            finished_at=self._now(),
            updated_at=self._now(),
            evidence_summary_json=dict(evidence_summary_json),
            evidence_storage_key=evidence_storage_key,
            evidence_storage_sha256=evidence_storage_sha256,
            failure_reason=None,
        )
        self.drills[drill_id] = updated
        self._append_event(
            drill_id=drill_id,
            event_type="DRILL_FINISHED",
            from_status="RUNNING",
            to_status="SUCCEEDED",
            actor_user_id=None,
            details={
                "evidence_storage_key": evidence_storage_key,
                "evidence_storage_sha256": evidence_storage_sha256,
            },
        )
        return updated

    def mark_failed(
        self,
        *,
        drill_id: str,
        failure_reason: str,
        evidence_summary_json: dict[str, object],
        evidence_storage_key: str | None = None,
        evidence_storage_sha256: str | None = None,
    ) -> RecoveryDrillRecord:
        current = self.drills[drill_id]
        if current.status == "FAILED":
            return current
        if current.status not in {"QUEUED", "RUNNING"}:
            raise RuntimeError("invalid transition")
        updated = replace(
            current,
            status="FAILED",
            finished_at=self._now(),
            updated_at=self._now(),
            failure_reason=failure_reason,
            evidence_summary_json=dict(evidence_summary_json),
            evidence_storage_key=evidence_storage_key,
            evidence_storage_sha256=evidence_storage_sha256,
        )
        self.drills[drill_id] = updated
        self._append_event(
            drill_id=drill_id,
            event_type="DRILL_FAILED",
            from_status=current.status,
            to_status="FAILED",
            actor_user_id=None,
            details={"failure_reason": failure_reason},
        )
        return updated

    def cancel_drill(self, *, drill_id: str, canceled_by: str) -> RecoveryDrillRecord:
        current = self.drills[drill_id]
        if current.status == "CANCELED":
            return current
        if current.status not in {"QUEUED", "RUNNING"}:
            raise RuntimeError("invalid transition")
        now = self._now()
        updated = replace(
            current,
            status="CANCELED",
            canceled_by=canceled_by,
            canceled_at=now,
            finished_at=now,
            updated_at=now,
        )
        self.drills[drill_id] = updated
        self._append_event(
            drill_id=drill_id,
            event_type="DRILL_CANCELED",
            from_status=current.status,
            to_status="CANCELED",
            actor_user_id=canceled_by,
            details={"reason": "manual_cancel"},
        )
        return updated

    def get_drill(self, *, drill_id: str) -> RecoveryDrillRecord:
        return self.drills[drill_id]

    def list_drills(self, *, cursor: int, page_size: int) -> RecoveryDrillPage:
        ordered = sorted(
            self.drills.values(),
            key=lambda item: (item.created_at, item.id),
            reverse=True,
        )
        selected = ordered[cursor : cursor + page_size + 1]
        has_more = len(selected) > page_size
        return RecoveryDrillPage(
            items=selected[:page_size],
            next_cursor=(cursor + page_size) if has_more else None,
        )

    def list_drill_events(
        self,
        *,
        drill_id: str,
        cursor: int,
        page_size: int,
    ) -> tuple[list[RecoveryDrillEventRecord], int | None]:
        ordered = list(reversed(self.events_by_drill.get(drill_id, [])))
        selected = ordered[cursor : cursor + page_size + 1]
        has_more = len(selected) > page_size
        return selected[:page_size], (cursor + page_size) if has_more else None

    def count_active_drills(self) -> int:
        return sum(1 for item in self.drills.values() if item.status in {"QUEUED", "RUNNING"})


class FakeTelemetryService:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def record_timeline(self, **kwargs):  # type: ignore[no-untyped-def]
        self.events.append(kwargs)


class FakeJobStore:
    def __init__(self, *, queue_depth: int = 2, dead_letter: int = 0, replay_eligible: int = 0) -> None:
        self._queue_depth = queue_depth
        self._dead_letter = dead_letter
        self._replay_eligible = replay_eligible

    def count_dead_letter_jobs(self) -> int:
        return self._dead_letter

    def count_replay_eligible_jobs(self) -> int:
        return self._replay_eligible

    def list_dead_letter_jobs(self, *, limit: int) -> list[dict[str, object]]:
        _ = limit
        return []

    def count_open_jobs(self) -> int:
        return self._queue_depth


class _FailClosedStorage:
    def read_object_bytes(self, object_key: str) -> bytes:
        _ = object_key
        raise DocumentStorageError("expected controlled read failure")


class _UnexpectedReadStorage:
    def read_object_bytes(self, object_key: str) -> bytes:
        _ = object_key
        return b"unexpected"


def _principal(*, roles: tuple[str, ...]) -> SessionPrincipal:
    return SessionPrincipal(
        session_id="session-recovery",
        auth_source="bearer",
        user_id="user-recovery",
        oidc_sub="oidc-user-recovery",
        email="recovery@test.local",
        display_name="Recovery User",
        platform_roles=roles,
        issued_at=datetime.now(UTC) - timedelta(minutes=5),
        expires_at=datetime.now(UTC) + timedelta(minutes=55),
        csrf_token="csrf-recovery",
    )


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=True), encoding="utf-8")


def _build_settings(tmp_path: Path) -> Settings:
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    artifact_root = tmp_path / "model-artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    catalog_path = tmp_path / "catalog.json"
    service_map_path = tmp_path / "service-map.json"
    _write_json(
        catalog_path,
        {
            "version": "test",
            "models": [
                {"role": "PRIVACY_RULES", "service": "privacy-rules", "artifact_path": "privacy/rules"},
                {
                    "role": "TRANSCRIPTION_FALLBACK",
                    "service": "fallback",
                    "artifact_path": "transcription/fallback",
                },
                {
                    "role": "TRANSCRIPTION_PRIMARY",
                    "service": "transcription-primary",
                    "artifact_path": "transcription/primary",
                },
                {"role": "ASSIST", "service": "assist", "artifact_path": "assist/model"},
                {"role": "PRIVACY_NER", "service": "privacy-ner", "artifact_path": "privacy/ner"},
                {"role": "EMBEDDING_SEARCH", "service": "embedding", "artifact_path": "embedding/model"},
            ],
        },
    )
    _write_json(
        service_map_path,
        {
            "version": "test",
            "services": {
                "privacy-rules": {"base_url": "http://privacy-rules.internal"},
                "fallback": {"base_url": "http://fallback.internal"},
                "transcription-primary": {"base_url": "http://transcription.internal"},
                "assist": {"base_url": "http://assist.internal"},
                "privacy-ner": {"base_url": "http://privacy-ner.internal"},
                "embedding": {"base_url": "http://embedding.internal"},
            },
        },
    )
    return get_settings().model_copy(
        update={
            "storage_controlled_root": storage_root,
            "model_artifact_root": artifact_root,
            "model_catalog_path": catalog_path,
            "model_service_map_path": service_map_path,
        }
    )


def test_recovery_service_runs_full_recovery_and_persists_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _build_settings(tmp_path)
    store = FakeRecoveryStore()
    telemetry = FakeTelemetryService()
    service = RecoveryService(
        settings=settings,
        store=store,
        telemetry_service=telemetry,
        job_store=FakeJobStore(queue_depth=4, dead_letter=1, replay_eligible=2),
    )
    monkeypatch.setattr("app.recovery.service.get_document_storage", lambda: _FailClosedStorage())

    run, evidence = service.create_and_run_drill(
        current_user=_principal(roles=("ADMIN",)),
        scope="FULL_RECOVERY",
    )

    assert run.status == "SUCCEEDED"
    assert evidence is not None
    assert evidence["gates"]["allPassed"] is True
    assert run.evidence_storage_key is not None
    assert run.evidence_storage_sha256 is not None

    evidence_path = settings.storage_controlled_root / run.evidence_storage_key
    assert evidence_path.exists()
    evidence_sha = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    assert evidence_sha == run.evidence_storage_sha256

    messages = {str(item.get("message")) for item in telemetry.events}
    assert "Recovery drill queued." in messages
    assert "Recovery drill started." in messages
    assert "Recovery drill finished." in messages


def test_recovery_service_enforces_admin_only_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _build_settings(tmp_path)
    service = RecoveryService(
        settings=settings,
        store=FakeRecoveryStore(),
        telemetry_service=FakeTelemetryService(),
        job_store=FakeJobStore(),
    )
    monkeypatch.setattr("app.recovery.service.get_document_storage", lambda: _FailClosedStorage())

    with pytest.raises(RecoveryAccessDeniedError):
        service.get_recovery_status(current_user=_principal(roles=("AUDITOR",)))

    with pytest.raises(RecoveryAccessDeniedError):
        service.create_and_run_drill(
            current_user=_principal(roles=("AUDITOR",)),
            scope="QUEUE_REPLAY",
        )


def test_recovery_service_reads_persisted_evidence_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _build_settings(tmp_path)
    store = FakeRecoveryStore()
    service = RecoveryService(
        settings=settings,
        store=store,
        telemetry_service=FakeTelemetryService(),
        job_store=FakeJobStore(),
    )
    monkeypatch.setattr("app.recovery.service.get_document_storage", lambda: _FailClosedStorage())

    run, _ = service.create_and_run_drill(
        current_user=_principal(roles=("ADMIN",)),
        scope="QUEUE_REPLAY",
    )
    assert run.evidence_storage_key is not None
    assert run.id in store.drills

    store.drills[run.id] = replace(
        store.drills[run.id],
        evidence_summary_json={"summary": "tampered-db-copy"},
    )
    _, payload = service.get_drill_evidence(
        current_user=_principal(roles=("ADMIN",)),
        drill_id=run.id,
    )

    assert payload.get("schemaVersion") == 1
    assert payload.get("summary") != "tampered-db-copy"
    assert isinstance(payload.get("events"), list)
    assert len(payload["events"]) > 0


def test_recovery_service_marks_failed_when_storage_gate_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _build_settings(tmp_path)
    telemetry = FakeTelemetryService()
    service = RecoveryService(
        settings=settings,
        store=FakeRecoveryStore(),
        telemetry_service=telemetry,
        job_store=FakeJobStore(),
    )
    monkeypatch.setattr("app.recovery.service.get_document_storage", lambda: _UnexpectedReadStorage())

    run, evidence = service.create_and_run_drill(
        current_user=_principal(roles=("ADMIN",)),
        scope="STORAGE_INTERRUPT",
    )

    assert run.status == "FAILED"
    assert evidence is not None
    assert evidence["gates"]["allPassed"] is False
    assert run.evidence_storage_key is not None
    assert run.evidence_storage_sha256 is not None
    assert (settings.storage_controlled_root / run.evidence_storage_key).exists()
    assert any(item.get("message") == "Recovery drill failed gate checks." for item in telemetry.events)
