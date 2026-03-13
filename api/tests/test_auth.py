from datetime import UTC, datetime, timedelta
from typing import Literal

import pytest
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.auth.service import AuthService, get_auth_service
from app.core.config import get_settings
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:
    yield
    app.dependency_overrides.clear()


def _principal(*, roles: tuple[Literal["ADMIN", "AUDITOR"], ...]) -> SessionPrincipal:
    return SessionPrincipal(
        session_id="session-test",
        auth_source="bearer",
        user_id="user-test",
        oidc_sub="oidc-user-test",
        email="user@test.local",
        display_name="User Test",
        platform_roles=roles,
        issued_at=datetime.now(UTC) - timedelta(minutes=2),
        expires_at=datetime.now(UTC) + timedelta(minutes=58),
        csrf_token="csrf-token",
    )


def test_protected_route_rejects_unauthenticated_requests() -> None:
    response = client.get("/projects")
    assert response.status_code == 401


def test_protected_route_rejects_invalid_tokens() -> None:
    response = client.get(
        "/projects",
        headers={"Authorization": "Bearer invalid-token-value"},
    )
    assert response.status_code == 401


def test_current_user_resolves_for_authenticated_session() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=("ADMIN",))

    response = client.get("/auth/session")

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["id"] == "user-test"
    assert "ADMIN" in payload["user"]["platformRoles"]


def test_auth_providers_uses_camel_case_seed_fields() -> None:
    settings = get_settings().model_copy(update={"auth_dev_mode_enabled": True})
    app.dependency_overrides[get_auth_service] = lambda: AuthService(settings=settings)

    response = client.get("/auth/providers")

    assert response.status_code == 200
    payload = response.json()
    assert payload["devEnabled"] is True
    assert len(payload["devSeeds"]) > 0
    first_seed = payload["devSeeds"][0]
    assert "displayName" in first_seed
    assert "platformRoles" in first_seed
    assert "display_name" not in first_seed
    assert "platform_roles" not in first_seed


def test_admin_route_denies_non_platform_user() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=())

    response = client.get("/admin/overview")

    assert response.status_code == 403


def test_admin_route_allows_admin_role() -> None:
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(roles=("ADMIN",))

    response = client.get("/admin/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"] == "admin"
