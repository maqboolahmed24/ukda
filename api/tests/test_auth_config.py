import pytest
from app.core.config import Settings


def test_dev_auth_cannot_be_enabled_outside_local(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("AUTH_DEV_MODE_ENABLED", "true")
    monkeypatch.setenv("AUTH_SESSION_SECRET", "replace-me")
    with pytest.raises(ValueError, match="AUTH_DEV_MODE_ENABLED"):
        Settings()


def test_oidc_requires_full_configuration(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("OIDC_ISSUER_URL", "https://issuer.example")
    monkeypatch.setenv("OIDC_CLIENT_ID", "client-id-only")
    monkeypatch.delenv("OIDC_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("OIDC_REDIRECT_URI", raising=False)
    with pytest.raises(ValueError, match="OIDC requires"):
        Settings()
