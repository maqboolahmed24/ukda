from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Literal

import psycopg

from app.core.config import Settings
from app.core.model_stack import validate_model_stack
from app.telemetry.service import get_telemetry_service


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    status: Literal["ok", "fail"]
    detail: str


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_psycopg_conninfo(database_url: str) -> str:
    if database_url.startswith("postgresql+psycopg://"):
        return database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    return database_url


def check_database_readiness(database_url: str) -> ReadinessCheck:
    telemetry_service = get_telemetry_service()
    started_at = perf_counter()
    conninfo = _as_psycopg_conninfo(database_url)

    if not conninfo.startswith("postgresql://"):
        duration_ms = (perf_counter() - started_at) * 1000
        telemetry_service.record_readiness_database(
            duration_ms=duration_ms,
            success=False,
        )
        return ReadinessCheck(
            name="database",
            status="fail",
            detail="DATABASE_URL must use a PostgreSQL connection string.",
        )

    try:
        with psycopg.connect(conninfo=conninfo, connect_timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
    except psycopg.Error as error:
        duration_ms = (perf_counter() - started_at) * 1000
        telemetry_service.record_readiness_database(
            duration_ms=duration_ms,
            success=False,
        )
        return ReadinessCheck(
            name="database",
            status="fail",
            detail=f"Database readiness check failed: {error.__class__.__name__}",
        )

    duration_ms = (perf_counter() - started_at) * 1000
    telemetry_service.record_readiness_database(
        duration_ms=duration_ms,
        success=True,
    )

    return ReadinessCheck(
        name="database",
        status="ok",
        detail="Database responded to SELECT 1.",
    )


def check_model_stack_readiness(settings: Settings) -> ReadinessCheck:
    model_stack_result = validate_model_stack(settings)
    return ReadinessCheck(
        name="model_stack",
        status=model_stack_result.status,
        detail=model_stack_result.detail,
    )


def evaluate_readiness(settings: Settings) -> tuple[dict[str, object], bool]:
    checks = [
        check_database_readiness(settings.database_url),
        check_model_stack_readiness(settings),
    ]
    is_ready = all(check.status == "ok" for check in checks)

    payload: dict[str, object] = {
        "service": "api",
        "status": "READY" if is_ready else "NOT_READY",
        "environment": settings.environment,
        "version": settings.version,
        "timestamp": utc_timestamp(),
        "checks": [
            {"name": check.name, "status": check.status.upper(), "detail": check.detail}
            for check in checks
        ],
    }

    if not is_ready:
        failing_checks = ", ".join(check.name for check in checks if check.status != "ok")
        payload["detail"] = f"Readiness failed for: {failing_checks}"

    return payload, is_ready
