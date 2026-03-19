import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError, field_validator, model_validator

from app.core.config import Settings
from app.security.outbound import is_url_allowlisted

_MUTABLE_ARTIFACT_SEGMENTS: set[str] = {"cache", "caches", "tmp", "mutable", "shared"}


class ModelCatalogEntry(BaseModel):
    role: str
    service: str
    model: str
    artifact_path: str


class ModelCatalog(BaseModel):
    version: str
    models: list[ModelCatalogEntry]

    @model_validator(mode="after")
    def validate_unique_roles(self) -> "ModelCatalog":
        roles = [entry.role for entry in self.models]
        if len(roles) != len(set(roles)):
            raise ValueError("MODEL_CATALOG_PATH contains duplicate model roles.")
        return self


class ModelServiceEndpointMap(BaseModel):
    health: str | None = None
    models: str | None = None
    chat: str | None = None
    embeddings: str | None = None

    @field_validator("health", "models", "chat", "embeddings")
    @classmethod
    def validate_endpoint_paths(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.startswith("/"):
            raise ValueError("Service-map endpoints must be root-relative paths.")
        return value


class ModelServiceDefinition(BaseModel):
    base_url: str
    protocol: Literal["openai-compatible", "native", "rules-native"]
    endpoints: ModelServiceEndpointMap

    @field_validator("base_url")
    @classmethod
    def validate_internal_base_url(cls, value: str) -> str:
        if value.startswith("https://api.openai.com"):
            raise ValueError("Public OpenAI endpoints are not allowed in UKDE.")
        return value


class ModelServiceMap(BaseModel):
    version: str
    services: dict[str, ModelServiceDefinition]


@dataclass(frozen=True)
class ModelStackValidationResult:
    status: Literal["ok", "fail"]
    detail: str


def _read_json_file(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _is_path_within(path: Path, root: Path) -> bool:
    candidate = path.expanduser().resolve()
    root = root.expanduser().resolve()
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def _validate_internal_model_roots(settings: Settings) -> str | None:
    roots_to_check = {
        "MODEL_DEPLOYMENT_ROOT": settings.model_deployment_root,
        "MODEL_ARTIFACT_ROOT": settings.model_artifact_root,
    }

    for env_name, path in roots_to_check.items():
        if not path.is_absolute():
            return f"{env_name} must be an absolute path."
        if _is_path_within(path, settings.repo_root):
            return f"{env_name} must point outside the repository."
    return None


def _resolve_model_artifact_path(
    *,
    artifact_path: str,
    model_artifact_root: Path,
) -> Path:
    candidate = Path(artifact_path).expanduser()
    if candidate.is_absolute():
        return candidate
    return model_artifact_root / candidate


def _validate_model_artifact_source(
    *,
    settings: Settings,
    entry: ModelCatalogEntry,
) -> str | None:
    artifact_path = entry.artifact_path.strip()
    if not artifact_path:
        return f"Catalog role '{entry.role}' has an empty artifact_path."
    if "://" in artifact_path:
        return (
            f"Catalog role '{entry.role}' uses external artifact source '{artifact_path}', "
            "which is blocked by no-egress policy."
        )

    resolved_path = _resolve_model_artifact_path(
        artifact_path=artifact_path,
        model_artifact_root=settings.model_artifact_root,
    ).resolve()

    roots = [
        settings.model_artifact_root.resolve(),
        settings.model_deployment_root.resolve(),
    ]
    if not any(_is_path_within(resolved_path, root) for root in roots):
        return (
            f"Catalog role '{entry.role}' artifact_path '{artifact_path}' must resolve within "
            "MODEL_ARTIFACT_ROOT or MODEL_DEPLOYMENT_ROOT."
        )

    if not resolved_path.exists():
        return (
            f"Catalog role '{entry.role}' expects artefacts at '{resolved_path}', "
            "but the path does not exist."
        )

    return None


def _validate_model_service_role_isolation(catalog: ModelCatalog) -> str | None:
    service_to_role: dict[str, str] = {}
    for entry in catalog.models:
        existing = service_to_role.get(entry.service)
        if existing is None:
            service_to_role[entry.service] = entry.role
            continue
        if existing != entry.role:
            return (
                f"Model roles '{existing}' and '{entry.role}' both map to service "
                f"'{entry.service}'. Each model role must use its own deployment unit."
            )
    return None


def _validate_model_artifact_role_isolation(
    *,
    settings: Settings,
    catalog: ModelCatalog,
) -> str | None:
    role_paths: list[tuple[str, Path]] = []
    for entry in catalog.models:
        resolved_path = _resolve_model_artifact_path(
            artifact_path=entry.artifact_path,
            model_artifact_root=settings.model_artifact_root,
        ).resolve()
        path_segments = {segment.strip().lower() for segment in resolved_path.parts}
        if path_segments.intersection(_MUTABLE_ARTIFACT_SEGMENTS):
            return (
                f"Catalog role '{entry.role}' artifact_path '{entry.artifact_path}' resolves to "
                "a shared mutable/cache location, which is blocked."
            )
        role_paths.append((entry.role, resolved_path))

    for index, (left_role, left_path) in enumerate(role_paths):
        for right_role, right_path in role_paths[index + 1 :]:
            if left_role == right_role:
                continue
            if _is_path_within(left_path, right_path) or _is_path_within(right_path, left_path):
                return (
                    f"Catalog role '{left_role}' artifact path '{left_path}' overlaps role "
                    f"'{right_role}' path '{right_path}'. Roles must not share artefact roots."
                )
    return None


def validate_model_stack(settings: Settings) -> ModelStackValidationResult:
    root_error = _validate_internal_model_roots(settings)
    if root_error:
        return ModelStackValidationResult(status="fail", detail=root_error)

    if not settings.model_catalog_path.exists():
        return ModelStackValidationResult(
            status="fail",
            detail=f"MODEL_CATALOG_PATH does not exist: {settings.model_catalog_path}",
        )

    if not settings.model_service_map_path.exists():
        return ModelStackValidationResult(
            status="fail",
            detail=(f"MODEL_SERVICE_MAP_PATH does not exist: {settings.model_service_map_path}"),
        )

    try:
        catalog = ModelCatalog.model_validate(_read_json_file(settings.model_catalog_path))
        service_map = ModelServiceMap.model_validate(
            _read_json_file(settings.model_service_map_path)
        )
    except (json.JSONDecodeError, ValidationError, OSError, ValueError) as error:
        return ModelStackValidationResult(
            status="fail",
            detail=f"Model stack configuration validation failed: {error}",
        )

    for entry in catalog.models:
        if settings.model_allowlist and entry.role not in settings.model_allowlist:
            return ModelStackValidationResult(
                status="fail",
                detail=(
                    f"Role '{entry.role}' is not listed in MODEL_ALLOWLIST and cannot be activated."
                ),
            )
        if entry.service not in service_map.services:
            return ModelStackValidationResult(
                status="fail",
                detail=(f"Catalog role '{entry.role}' maps to unknown service '{entry.service}'."),
            )
        artifact_error = _validate_model_artifact_source(settings=settings, entry=entry)
        if artifact_error:
            return ModelStackValidationResult(status="fail", detail=artifact_error)

    role_isolation_error = _validate_model_service_role_isolation(catalog)
    if role_isolation_error:
        return ModelStackValidationResult(status="fail", detail=role_isolation_error)

    artifact_isolation_error = _validate_model_artifact_role_isolation(
        settings=settings,
        catalog=catalog,
    )
    if artifact_isolation_error:
        return ModelStackValidationResult(status="fail", detail=artifact_isolation_error)

    for service_name, service_definition in service_map.services.items():
        if not is_url_allowlisted(service_definition.base_url, settings):
            return ModelStackValidationResult(
                status="fail",
                detail=(
                    f"Service '{service_name}' base_url '{service_definition.base_url}' "
                    "is outside the outbound allowlist."
                ),
            )

    if not is_url_allowlisted(settings.openai_base_url, settings):
        return ModelStackValidationResult(
            status="fail",
            detail=(
                f"OPENAI_BASE_URL '{settings.openai_base_url}' is outside the outbound allowlist."
            ),
        )

    return ModelStackValidationResult(
        status="ok",
        detail=(
            f"Validated {len(catalog.models)} model role mappings against "
            f"{len(service_map.services)} internal services."
        ),
    )
