import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODEL_ROOT = Path("~/Library/Application Support/UKDataExtraction/models").expanduser()
DEFAULT_STORAGE_ROOT = (DEFAULT_REPO_ROOT / ".ukde-storage").resolve()
DEFAULT_MODEL_CATALOG_PATH = DEFAULT_REPO_ROOT / "infra" / "models" / "catalog.phase-0.1.json"
DEFAULT_MODEL_SERVICE_MAP_PATH = (
    DEFAULT_REPO_ROOT / "infra" / "models" / "service-map.phase-0.1.json"
)
DEFAULT_MODEL_ALLOWLIST = [
    "TRANSCRIPTION_PRIMARY",
    "ASSIST",
    "PRIVACY_NER",
    "PRIVACY_RULES",
    "TRANSCRIPTION_FALLBACK",
    "EMBEDDING_SEARCH",
]
DEFAULT_OUTBOUND_ALLOWLIST = [
    "localhost",
    "127.0.0.1",
    "::1",
    ".internal",
    ".local",
]
DEFAULT_SECURITY_CSP = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "img-src 'self' data: blob:; "
    "font-src 'self' data:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "connect-src 'self' http: https:"
)
DEFAULT_SECURITY_PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=()"
DEFAULT_AUTH_SESSION_SECRET = "ukde-dev-session-secret-change-me"
DEFAULT_AUTH_DEV_SEED_USERS = [
    {
        "key": "project-lead",
        "oidc_sub": "dev-project-lead-001",
        "email": "project-lead@local.ukde",
        "display_name": "Dev Project Lead",
        "platform_roles": [],
    },
    {
        "key": "researcher",
        "oidc_sub": "dev-researcher-001",
        "email": "researcher@local.ukde",
        "display_name": "Dev Researcher",
        "platform_roles": [],
    },
    {
        "key": "reviewer",
        "oidc_sub": "dev-reviewer-001",
        "email": "reviewer@local.ukde",
        "display_name": "Dev Reviewer",
        "platform_roles": [],
    },
    {
        "key": "admin",
        "oidc_sub": "dev-admin-001",
        "email": "admin@local.ukde",
        "display_name": "Dev Admin",
        "platform_roles": ["ADMIN"],
    },
    {
        "key": "auditor",
        "oidc_sub": "dev-auditor-001",
        "email": "auditor@local.ukde",
        "display_name": "Dev Auditor",
        "platform_roles": ["AUDITOR"],
    },
]


class DevSeedIdentity(BaseModel):
    key: str
    oidc_sub: str
    email: str
    display_name: str
    platform_roles: list[Literal["ADMIN", "AUDITOR"]] = []


class Settings(BaseSettings):
    app_name: str = "UKDE API"
    version: str = "0.1.0"
    app_env: Literal["dev", "staging", "prod", "test"] = Field(
        default="dev",
        alias="APP_ENV",
    )
    api_prefix: str = ""
    web_origins_raw: str = Field(
        default="http://127.0.0.1:3000,http://localhost:3000",
        alias="WEB_ORIGINS",
    )
    database_url: str = Field(
        default="postgresql://ukde:ukde@127.0.0.1:5432/ukde",
        alias="DATABASE_URL",
    )
    telemetry_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        alias="TELEMETRY_LOG_LEVEL",
    )
    telemetry_export_mode: Literal["none", "otlp_http"] = Field(
        default="none",
        alias="TELEMETRY_EXPORT_MODE",
    )
    telemetry_otlp_endpoint: str | None = Field(
        default=None,
        alias="TELEMETRY_OTLP_ENDPOINT",
    )
    telemetry_timeline_limit: int = Field(
        default=400,
        alias="TELEMETRY_TIMELINE_LIMIT",
    )
    storage_controlled_raw_prefix: str = Field(
        default="controlled/raw/",
        alias="STORAGE_CONTROLLED_RAW_PREFIX",
    )
    storage_controlled_root: Path = Field(
        default=DEFAULT_STORAGE_ROOT,
        alias="STORAGE_CONTROLLED_ROOT",
    )
    storage_controlled_derived_prefix: str = Field(
        default="controlled/derived/",
        alias="STORAGE_CONTROLLED_DERIVED_PREFIX",
    )
    storage_safeguarded_exports_prefix: str = Field(
        default="safeguarded/exports/",
        alias="STORAGE_SAFEGUARDED_EXPORTS_PREFIX",
    )
    documents_max_upload_bytes: int = Field(
        default=64 * 1024 * 1024,
        alias="DOCUMENTS_MAX_UPLOAD_BYTES",
    )
    documents_project_quota_bytes: int = Field(
        default=512 * 1024 * 1024,
        alias="DOCUMENTS_PROJECT_QUOTA_BYTES",
    )
    documents_project_quota_documents: int = Field(
        default=2_000,
        alias="DOCUMENTS_PROJECT_QUOTA_DOCUMENTS",
    )
    documents_project_quota_pages: int = Field(
        default=200_000,
        alias="DOCUMENTS_PROJECT_QUOTA_PAGES",
    )
    documents_resumable_chunk_bytes: int = Field(
        default=4 * 1024 * 1024,
        alias="DOCUMENTS_RESUMABLE_CHUNK_BYTES",
    )
    document_scanner_backend: Literal["auto", "stub", "none"] = Field(
        default="auto",
        alias="DOCUMENT_SCANNER_BACKEND",
    )
    openai_base_url: str = Field(
        default="http://127.0.0.1:8010/v1",
        alias="OPENAI_BASE_URL",
    )
    openai_api_key: str = Field(default="internal-local-dev", alias="OPENAI_API_KEY")
    model_deployment_root: Path = Field(
        default=DEFAULT_MODEL_ROOT,
        alias="MODEL_DEPLOYMENT_ROOT",
    )
    model_artifact_root: Path = Field(
        default=DEFAULT_MODEL_ROOT,
        alias="MODEL_ARTIFACT_ROOT",
    )
    model_catalog_path: Path = Field(
        default=DEFAULT_MODEL_CATALOG_PATH,
        alias="MODEL_CATALOG_PATH",
    )
    model_allowlist_raw: str = Field(
        default=",".join(DEFAULT_MODEL_ALLOWLIST),
        alias="MODEL_ALLOWLIST",
    )
    outbound_allowlist_raw: str = Field(
        default=",".join(DEFAULT_OUTBOUND_ALLOWLIST),
        alias="OUTBOUND_ALLOWLIST",
    )
    model_service_map_path: Path = Field(
        default=DEFAULT_MODEL_SERVICE_MAP_PATH,
        alias="MODEL_SERVICE_MAP_PATH",
    )
    model_warm_start: bool = Field(default=True, alias="MODEL_WARM_START")
    model_startup_validation_mode: Literal["warn", "strict"] = Field(
        default="warn",
        alias="MODEL_STARTUP_VALIDATION_MODE",
    )
    security_csp_mode: Literal["enforce", "report-only"] = Field(
        default="enforce",
        alias="SECURITY_CSP_MODE",
    )
    security_csp_value: str = Field(
        default=DEFAULT_SECURITY_CSP,
        alias="SECURITY_CSP_VALUE",
    )
    security_referrer_policy: str = Field(
        default="strict-origin-when-cross-origin",
        alias="SECURITY_REFERRER_POLICY",
    )
    security_permissions_policy: str = Field(
        default=DEFAULT_SECURITY_PERMISSIONS_POLICY,
        alias="SECURITY_PERMISSIONS_POLICY",
    )
    security_last_backup_at: str | None = Field(
        default=None,
        alias="SECURITY_LAST_BACKUP_AT",
    )
    auth_rate_limit_window_seconds: int = Field(
        default=60,
        alias="AUTH_RATE_LIMIT_WINDOW_SECONDS",
    )
    auth_rate_limit_max_requests: int = Field(
        default=30,
        alias="AUTH_RATE_LIMIT_MAX_REQUESTS",
    )
    protected_rate_limit_window_seconds: int = Field(
        default=60,
        alias="PROTECTED_RATE_LIMIT_WINDOW_SECONDS",
    )
    protected_rate_limit_max_requests: int = Field(
        default=300,
        alias="PROTECTED_RATE_LIMIT_MAX_REQUESTS",
    )
    auth_session_secret: str = Field(
        default=DEFAULT_AUTH_SESSION_SECRET,
        alias="AUTH_SESSION_SECRET",
    )
    auth_session_ttl_seconds: int = Field(
        default=3600,
        alias="AUTH_SESSION_TTL_SECONDS",
    )
    auth_cookie_name: str = Field(default="ukde_session", alias="AUTH_COOKIE_NAME")
    auth_csrf_cookie_name: str = Field(default="ukde_csrf", alias="AUTH_CSRF_COOKIE_NAME")
    auth_dev_mode_enabled: bool = Field(default=False, alias="AUTH_DEV_MODE_ENABLED")
    auth_dev_seed_users_raw: str = Field(
        default=json.dumps(DEFAULT_AUTH_DEV_SEED_USERS),
        alias="AUTH_DEV_SEED_USERS",
    )
    oidc_issuer_url: str | None = Field(default=None, alias="OIDC_ISSUER_URL")
    oidc_client_id: str | None = Field(default=None, alias="OIDC_CLIENT_ID")
    oidc_client_secret: str | None = Field(default=None, alias="OIDC_CLIENT_SECRET")
    oidc_redirect_uri: str | None = Field(default=None, alias="OIDC_REDIRECT_URI")
    oidc_scopes_raw: str = Field(default="openid profile email", alias="OIDC_SCOPES")
    oidc_post_login_redirect_path: str = Field(
        default="/projects",
        alias="OIDC_POST_LOGIN_REDIRECT_PATH",
    )
    oidc_post_logout_redirect_path: str = Field(
        default="/login",
        alias="OIDC_POST_LOGOUT_REDIRECT_PATH",
    )

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator(
        "model_deployment_root",
        "model_artifact_root",
        "storage_controlled_root",
        mode="before",
    )
    @classmethod
    def _coerce_path(cls, value: Path | str) -> Path:
        if isinstance(value, Path):
            return value.expanduser()
        return Path(value).expanduser()

    @field_validator("model_catalog_path", "model_service_map_path", mode="after")
    @classmethod
    def _resolve_repo_relative_paths(cls, value: Path) -> Path:
        if value.is_absolute():
            return value
        return (DEFAULT_REPO_ROOT / value).resolve()

    @field_validator("storage_controlled_root", mode="after")
    @classmethod
    def _resolve_storage_root_path(cls, value: Path) -> Path:
        if value.is_absolute():
            return value
        return (DEFAULT_REPO_ROOT / value).resolve()

    @field_validator("auth_session_ttl_seconds")
    @classmethod
    def _validate_session_ttl(cls, value: int) -> int:
        if value < 300:
            raise ValueError("AUTH_SESSION_TTL_SECONDS must be at least 300 seconds.")
        return value

    @field_validator(
        "auth_rate_limit_window_seconds",
        "protected_rate_limit_window_seconds",
    )
    @classmethod
    def _validate_rate_limit_windows(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Rate-limit window seconds must be at least 1.")
        if value > 3600:
            raise ValueError("Rate-limit window seconds must be 3600 or lower.")
        return value

    @field_validator(
        "auth_rate_limit_max_requests",
        "protected_rate_limit_max_requests",
    )
    @classmethod
    def _validate_rate_limit_max_requests(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Rate-limit max requests must be at least 1.")
        if value > 10000:
            raise ValueError("Rate-limit max requests must be 10000 or lower.")
        return value

    @field_validator("telemetry_timeline_limit")
    @classmethod
    def _validate_telemetry_timeline_limit(cls, value: int) -> int:
        if value < 100:
            raise ValueError("TELEMETRY_TIMELINE_LIMIT must be at least 100.")
        if value > 5000:
            raise ValueError("TELEMETRY_TIMELINE_LIMIT must be 5000 or lower.")
        return value

    @field_validator(
        "documents_max_upload_bytes",
        "documents_project_quota_bytes",
        "documents_project_quota_documents",
        "documents_project_quota_pages",
        "documents_resumable_chunk_bytes",
    )
    @classmethod
    def _validate_document_limits(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Document limits must be at least 1.")
        return value

    @field_validator("documents_max_upload_bytes", "documents_project_quota_bytes")
    @classmethod
    def _validate_document_quota_fields(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Document upload limits must be positive integers.")
        return value

    @field_validator(
        "storage_controlled_raw_prefix",
        "storage_controlled_derived_prefix",
        "storage_safeguarded_exports_prefix",
    )
    @classmethod
    def _validate_storage_prefix(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Storage prefixes cannot be empty.")
        if normalized.startswith("/"):
            raise ValueError("Storage prefixes must be relative object-key prefixes.")
        if not normalized.endswith("/"):
            normalized = f"{normalized}/"
        return normalized

    @field_validator(
        "oidc_issuer_url",
        "oidc_client_id",
        "oidc_client_secret",
        "oidc_redirect_uri",
        "telemetry_otlp_endpoint",
        "security_last_backup_at",
        mode="before",
    )
    @classmethod
    def _empty_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator(
        "security_csp_value",
        "security_referrer_policy",
        "security_permissions_policy",
    )
    @classmethod
    def _validate_security_header_values(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Security header values cannot be empty.")
        return normalized

    @model_validator(mode="after")
    def _validate_auth_boundaries(self) -> "Settings":
        if self.auth_dev_mode_enabled and self.app_env in {"staging", "prod"}:
            raise ValueError("AUTH_DEV_MODE_ENABLED must be false outside dev/test.")

        if (
            self.app_env in {"staging", "prod"}
            and self.auth_session_secret == DEFAULT_AUTH_SESSION_SECRET
        ):
            raise ValueError("AUTH_SESSION_SECRET must be replaced outside dev/test.")

        has_any_oidc = any(
            [
                self.oidc_issuer_url,
                self.oidc_client_id,
                self.oidc_client_secret,
                self.oidc_redirect_uri,
            ]
        )
        has_all_oidc = all(
            [
                self.oidc_issuer_url,
                self.oidc_client_id,
                self.oidc_client_secret,
                self.oidc_redirect_uri,
            ]
        )
        if has_any_oidc and not has_all_oidc:
            raise ValueError(
                (
                    "OIDC requires OIDC_ISSUER_URL, OIDC_CLIENT_ID, "
                    "OIDC_CLIENT_SECRET, and OIDC_REDIRECT_URI."
                )
            )

        return self

    @staticmethod
    def _parse_env_list(raw_value: str) -> list[str]:
        value = raw_value.strip()
        if not value:
            return []
        if value.startswith("["):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(entry).strip() for entry in parsed if str(entry).strip()]
            except json.JSONDecodeError:
                pass
        if value.startswith("[") and value.endswith("]"):
            value = value[1:-1]
        return [entry.strip().strip('"').strip("'") for entry in value.split(",") if entry.strip()]

    @property
    def environment(self) -> str:
        return self.app_env

    @property
    def web_origins(self) -> list[str]:
        return self._parse_env_list(self.web_origins_raw)

    @property
    def model_allowlist(self) -> list[str]:
        return self._parse_env_list(self.model_allowlist_raw)

    @property
    def outbound_allowlist(self) -> list[str]:
        return [entry.lower() for entry in self._parse_env_list(self.outbound_allowlist_raw)]

    @property
    def repo_root(self) -> Path:
        return DEFAULT_REPO_ROOT

    @property
    def oidc_enabled(self) -> bool:
        return all(
            [
                self.oidc_issuer_url,
                self.oidc_client_id,
                self.oidc_client_secret,
                self.oidc_redirect_uri,
            ]
        )

    @property
    def oidc_scopes(self) -> list[str]:
        raw = self.oidc_scopes_raw.strip()
        if not raw:
            return ["openid", "profile", "email"]
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(scope).strip() for scope in parsed if str(scope).strip()]
            except json.JSONDecodeError:
                pass
        return [scope.strip() for scope in raw.replace(",", " ").split() if scope.strip()]

    @property
    def auth_cookie_secure(self) -> bool:
        return self.app_env in {"staging", "prod"}

    @property
    def enforce_model_startup_validation(self) -> bool:
        if self.model_startup_validation_mode == "strict":
            return True
        return self.app_env in {"staging", "prod"}

    @property
    def effective_document_scanner_backend(self) -> Literal["stub", "none"]:
        if self.document_scanner_backend == "stub":
            return "stub"
        if self.document_scanner_backend == "none":
            return "none"
        if self.app_env in {"dev", "test"}:
            return "stub"
        return "none"

    @property
    def auth_dev_seed_users(self) -> list[DevSeedIdentity]:
        try:
            parsed = json.loads(self.auth_dev_seed_users_raw)
        except json.JSONDecodeError as error:
            raise ValueError("AUTH_DEV_SEED_USERS must be valid JSON.") from error
        if not isinstance(parsed, list):
            raise ValueError("AUTH_DEV_SEED_USERS must be a JSON array.")
        return [DevSeedIdentity.model_validate(entry) for entry in parsed]


@lru_cache
def get_settings() -> Settings:
    return Settings()
