from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from time import sleep
from typing import Any

from ukde_workers.config import WorkerConfig


@dataclass(frozen=True)
class WorkerStatus:
    service: str
    environment: str
    queue_name: str
    heartbeat_seconds: int
    heartbeat_at: str
    mode: str
    telemetry_mode: str
    queue_depth: int | None
    queue_depth_state: str
    queue_depth_detail: str


@dataclass(frozen=True)
class WorkerRunResult:
    worker_id: str
    queue_name: str
    action: str
    job_id: str | None
    status: str | None
    detail: str
    occurred_at: str


def _resolve_job_service() -> Any | None:
    try:
        from app.jobs.service import get_job_service  # type: ignore
    except Exception:
        return None
    try:
        return get_job_service()
    except Exception:
        return None


def _run_risk_acceptance_expiry_pass() -> tuple[int, str | None]:
    try:
        from app.audit.service import get_audit_service  # type: ignore
        from app.security.findings.service import get_security_findings_service  # type: ignore
    except Exception:
        return (0, None)
    try:
        security_service = get_security_findings_service()
        expired = security_service.evaluate_due_acceptances_system()
    except Exception as error:
        return (0, error.__class__.__name__)

    if not expired:
        return (0, None)

    try:
        audit_service = get_audit_service()
    except Exception:
        return (len(expired), "audit_unavailable")

    for record in expired:
        audit_service.record_event_best_effort(
            event_type="RISK_ACCEPTANCE_EXPIRED",
            actor_user_id="system-risk-expiry-evaluator",
            metadata={
                "route": "worker://risk-acceptance-expiry-evaluator",
                "risk_acceptance_id": record.id,
                "status": record.status,
                "expires_at": record.expires_at.isoformat() if record.expires_at else None,
            },
            request_id="worker-risk-acceptance-expiry",
        )
    return (len(expired), None)


def _queue_depth_status(resolved: WorkerConfig) -> tuple[int | None, str, str]:
    job_service = _resolve_job_service()
    if job_service is None:
        return (
            None,
            "UNAVAILABLE",
            "API jobs service is unavailable in this runtime environment.",
        )
    try:
        queue_depth = int(job_service.queue_depth())
    except Exception:
        return (
            None,
            "UNAVAILABLE",
            "Queue depth could not be loaded from jobs persistence.",
        )
    return (queue_depth, "AVAILABLE", "Queue depth from unsuperseded queued jobs.")


def bootstrap_status(config: WorkerConfig | None = None) -> WorkerStatus:
    resolved = config or WorkerConfig.from_env()
    queue_depth, queue_depth_state, queue_depth_detail = _queue_depth_status(resolved)
    return WorkerStatus(
        service="workers",
        environment=resolved.environment,
        queue_name=resolved.queue_name,
        heartbeat_seconds=resolved.heartbeat_seconds,
        heartbeat_at=datetime.now(UTC).isoformat(),
        mode="operational" if queue_depth_state == "AVAILABLE" else "bootstrap",
        telemetry_mode="internal-only",
        queue_depth=queue_depth,
        queue_depth_state=queue_depth_state,
        queue_depth_detail=queue_depth_detail,
    )


def status_payload(config: WorkerConfig | None = None) -> dict[str, object]:
    return asdict(bootstrap_status(config))


def run_once(config: WorkerConfig | None = None) -> WorkerRunResult:
    resolved = config or WorkerConfig.from_env()
    expired_count, expiry_error = _run_risk_acceptance_expiry_pass()
    expiry_detail = (
        f"Expired {expired_count} risk acceptance(s)."
        if expiry_error is None
        else f"Risk-acceptance expiry evaluator failed ({expiry_error})."
    )
    job_service = _resolve_job_service()
    now = datetime.now(UTC).isoformat()
    if job_service is None:
        return WorkerRunResult(
            worker_id=resolved.worker_id,
            queue_name=resolved.queue_name,
            action="unavailable",
            job_id=None,
            status=None,
            detail=(
                "Jobs service is unavailable; run within the full UKDE workspace "
                f"environment. {expiry_detail}"
            ),
            occurred_at=now,
        )

    try:
        result = job_service.run_worker_once(
            worker_id=resolved.worker_id,
            lease_seconds=resolved.heartbeat_seconds,
        )
    except Exception as error:  # noqa: BLE001
        return WorkerRunResult(
            worker_id=resolved.worker_id,
            queue_name=resolved.queue_name,
            action="error",
            job_id=None,
            status=None,
            detail=f"Worker execution failed: {error.__class__.__name__}. {expiry_detail}",
            occurred_at=now,
        )

    if result is None:
        return WorkerRunResult(
            worker_id=resolved.worker_id,
            queue_name=resolved.queue_name,
            action="idle",
            job_id=None,
            status=None,
            detail=f"No queued jobs were available. {expiry_detail}",
            occurred_at=now,
        )

    return WorkerRunResult(
        worker_id=resolved.worker_id,
        queue_name=resolved.queue_name,
        action="processed",
        job_id=result.id,
        status=result.status,
        detail=f"Processed {result.type} attempt {result.attempt_number}. {expiry_detail}",
        occurred_at=now,
    )


def run_loop(config: WorkerConfig | None = None) -> list[WorkerRunResult]:
    resolved = config or WorkerConfig.from_env()
    max_iterations = resolved.run_loop_max_iterations
    results: list[WorkerRunResult] = []
    iteration = 0
    while True:
        if max_iterations > 0 and iteration >= max_iterations:
            break
        outcome = run_once(resolved)
        results.append(outcome)
        iteration += 1
        if outcome.action == "processed":
            continue
        sleep(resolved.poll_seconds)
    return results
