import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.audit.middleware import correlation_id_middleware
from app.audit.service import get_audit_service
from app.core.config import get_settings
from app.core.model_stack import validate_model_stack
from app.projects.store import ProjectStore, ProjectStoreUnavailableError
from app.security.middleware import (
    create_rate_limit_middleware,
    create_security_headers_middleware,
)
from app.security.status import get_security_status_service

logger = logging.getLogger(__name__)


def _run_startup_security_bootstrap() -> None:
    settings = get_settings()
    should_write_startup_audit = settings.app_env in {"staging", "prod", "preview"}
    audit_service = get_audit_service() if should_write_startup_audit else None
    model_stack_result = validate_model_stack(settings)
    if model_stack_result.status != "ok":
        if audit_service is not None:
            audit_service.record_event_best_effort(
                event_type="OUTBOUND_CALL_BLOCKED",
                actor_user_id=None,
                metadata={
                    "method": "VALIDATE",
                    "url": "model_stack://startup",
                    "host": "model-stack",
                    "purpose": "model_stack_startup_validation",
                    "reason": model_stack_result.detail,
                },
                request_id="system-startup-model-stack",
            )
        message = f"Model stack startup validation failed: {model_stack_result.detail}"
        if settings.enforce_model_startup_validation:
            raise RuntimeError(message)
        logger.warning(message)

    security_status_service = get_security_status_service()
    security_status_service.run_startup_egress_deny_test(audit_service=audit_service)

    if not should_write_startup_audit:
        return

    project_store = ProjectStore(settings)
    try:
        project_store.ensure_schema()
    except ProjectStoreUnavailableError as error:
        logger.warning("Project baseline bootstrap could not complete at startup: %s", error)
        return

    if project_store.consume_baseline_seed_inserted():
        assert audit_service is not None
        audit_service.record_event_best_effort(
            event_type="BASELINE_POLICY_SNAPSHOT_SEEDED",
            actor_user_id=None,
            object_type="baseline_policy_snapshot",
            object_id="baseline-phase0-v1",
            metadata={
                "snapshot_id": "baseline-phase0-v1",
                "seeded_by": "SYSTEM_PHASE_0",
            },
            request_id="system-startup-baseline-seed",
        )


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        docs_url=None,
        openapi_url=None,
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.web_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.middleware("http")(create_security_headers_middleware(settings))
    app.middleware("http")(create_rate_limit_middleware(settings))
    app.middleware("http")(correlation_id_middleware)
    app.include_router(api_router)
    app.add_event_handler("startup", _run_startup_security_bootstrap)
    return app


app = create_app()
