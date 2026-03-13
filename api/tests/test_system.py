from datetime import UTC, datetime, timedelta

import pytest
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.core.config import get_settings
from app.core.readiness import ReadinessCheck
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:
    yield
    app.dependency_overrides.clear()


def test_healthz_returns_ok() -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "api"
    assert payload["status"] == "OK"


def test_readyz_returns_service_unavailable_when_db_unreachable() -> None:
    response = client.get("/readyz")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "NOT_READY"
    checks = {check["name"]: check["status"] for check in payload["checks"]}
    assert checks["database"] == "FAIL"


def test_readyz_returns_ok_when_all_checks_pass(monkeypatch) -> None:
    from app.core import readiness

    monkeypatch.setattr(
        readiness,
        "check_database_readiness",
        lambda _: ReadinessCheck(
            name="database",
            status="ok",
            detail="Database responded.",
        ),
    )
    monkeypatch.setattr(
        readiness,
        "check_model_stack_readiness",
        lambda _: ReadinessCheck(
            name="model_stack",
            status="ok",
            detail="Model stack validated.",
        ),
    )

    response = client.get("/readyz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "READY"
    assert payload["environment"] == get_settings().environment


def test_meta_endpoint_requires_authentication() -> None:
    response = client.get("/api/meta")

    assert response.status_code == 401


def test_meta_endpoint_returns_authenticated_payload() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: SessionPrincipal(
        session_id="session-1",
        auth_source="bearer",
        user_id="user-1",
        oidc_sub="oidc-user-1",
        email="user@example.com",
        display_name="User One",
        platform_roles=("ADMIN",),
        issued_at=datetime.now(UTC) - timedelta(minutes=5),
        expires_at=datetime.now(UTC) + timedelta(minutes=55),
        csrf_token="csrf-1",
    )

    response = client.get("/api/meta")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "AUTHENTICATED"
    assert payload["actor"]["id"] == "user-1"
