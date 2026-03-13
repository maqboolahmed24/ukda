from app.auth.service import get_auth_service
from app.core.config import get_settings
from app.main import create_app
from app.projects.service import get_project_service
from app.security.status import get_security_status_service
from fastapi.testclient import TestClient


def _clear_caches() -> None:
    get_settings.cache_clear()
    get_auth_service.cache_clear()
    get_project_service.cache_clear()
    get_security_status_service.cache_clear()


def test_security_headers_are_applied() -> None:
    _clear_caches()
    client = TestClient(create_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert "X-Content-Type-Options" in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "Referrer-Policy" in response.headers
    assert "Permissions-Policy" in response.headers
    assert (
        "Content-Security-Policy" in response.headers
        or "Content-Security-Policy-Report-Only" in response.headers
    )


def test_rate_limit_applies_to_auth_and_protected_paths(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_RATE_LIMIT_MAX_REQUESTS", "2")
    monkeypatch.setenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("PROTECTED_RATE_LIMIT_MAX_REQUESTS", "2")
    monkeypatch.setenv("PROTECTED_RATE_LIMIT_WINDOW_SECONDS", "60")
    _clear_caches()
    client = TestClient(create_app())

    auth_first = client.get("/auth/providers")
    auth_second = client.get("/auth/providers")
    auth_third = client.get("/auth/providers")

    assert auth_first.status_code == 200
    assert auth_second.status_code == 200
    assert auth_third.status_code == 429
    assert auth_third.json()["code"] == "RATE_LIMIT_EXCEEDED"

    protected_first = client.get("/projects")
    protected_second = client.get("/projects")
    protected_third = client.get("/projects")

    assert protected_first.status_code == 401
    assert protected_second.status_code == 401
    assert protected_third.status_code == 429
    assert protected_third.json()["scope"] == "protected"

    _clear_caches()

