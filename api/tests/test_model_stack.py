from dataclasses import dataclass
from pathlib import Path

from app.core.model_stack import validate_model_stack


@dataclass
class StubSettings:
    repo_root: Path
    model_deployment_root: Path
    model_artifact_root: Path
    model_catalog_path: Path
    model_service_map_path: Path
    model_allowlist: list[str]
    outbound_allowlist: list[str]
    openai_base_url: str


def _write_model_catalog(path: Path) -> None:
    path.write_text(
        """
{
  "version": "phase-0.1",
  "models": [
    {
      "role": "TRANSCRIPTION_PRIMARY",
      "service": "internal-vlm",
      "model": "Qwen2.5-VL-3B-Instruct",
      "artifact_path": "qwen/qwen2.5-vl-3b-instruct"
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )


def _write_model_catalog_with_two_roles(path: Path) -> None:
    path.write_text(
        """
{
  "version": "phase-0.1",
  "models": [
    {
      "role": "TRANSCRIPTION_PRIMARY",
      "service": "internal-vlm",
      "model": "Qwen2.5-VL-3B-Instruct",
      "artifact_path": "qwen/primary"
    },
    {
      "role": "ASSIST",
      "service": "internal-llm",
      "model": "Qwen3-4B",
      "artifact_path": "assist/qwen3-4b"
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )


def _write_model_catalog_with_duplicate_service(path: Path) -> None:
    path.write_text(
        """
{
  "version": "phase-0.1",
  "models": [
    {
      "role": "TRANSCRIPTION_PRIMARY",
      "service": "internal-vlm",
      "model": "Qwen2.5-VL-3B-Instruct",
      "artifact_path": "qwen/primary"
    },
    {
      "role": "ASSIST",
      "service": "internal-vlm",
      "model": "Qwen3-4B",
      "artifact_path": "assist/qwen3-4b"
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )


def _write_model_catalog_with_overlapping_paths(path: Path) -> None:
    path.write_text(
        """
{
  "version": "phase-0.1",
  "models": [
    {
      "role": "TRANSCRIPTION_PRIMARY",
      "service": "internal-vlm",
      "model": "Qwen2.5-VL-3B-Instruct",
      "artifact_path": "isolated/primary"
    },
    {
      "role": "ASSIST",
      "service": "internal-llm",
      "model": "Qwen3-4B",
      "artifact_path": "isolated/primary/assist"
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )


def _write_model_catalog_with_mutable_cache_path(path: Path) -> None:
    path.write_text(
        """
{
  "version": "phase-0.1",
  "models": [
    {
      "role": "TRANSCRIPTION_PRIMARY",
      "service": "internal-vlm",
      "model": "Qwen2.5-VL-3B-Instruct",
      "artifact_path": "cache/primary"
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )


def _write_service_map(path: Path) -> None:
    path.write_text(
        """
{
  "version": "phase-0.1",
  "services": {
    "internal-vlm": {
      "base_url": "http://127.0.0.1:8010/v1",
      "protocol": "openai-compatible",
      "endpoints": {
        "health": "/health",
        "models": "/v1/models",
        "chat": "/v1/chat/completions"
      }
    }
  }
}
""".strip(),
        encoding="utf-8",
    )


def _write_service_map_with_two_services(path: Path) -> None:
    path.write_text(
        """
{
  "version": "phase-0.1",
  "services": {
    "internal-vlm": {
      "base_url": "http://127.0.0.1:8010/v1",
      "protocol": "openai-compatible",
      "endpoints": {
        "health": "/health",
        "models": "/v1/models",
        "chat": "/v1/chat/completions"
      }
    },
    "internal-llm": {
      "base_url": "http://127.0.0.1:8011/v1",
      "protocol": "openai-compatible",
      "endpoints": {
        "health": "/health",
        "models": "/v1/models",
        "chat": "/v1/chat/completions"
      }
    }
  }
}
""".strip(),
        encoding="utf-8",
    )


def _write_public_service_map(path: Path) -> None:
    path.write_text(
        """
{
  "version": "phase-0.1",
  "services": {
    "internal-vlm": {
      "base_url": "https://public.example.com/v1",
      "protocol": "openai-compatible",
      "endpoints": {
        "health": "/health",
        "models": "/v1/models",
        "chat": "/v1/chat/completions"
      }
    }
  }
}
""".strip(),
        encoding="utf-8",
    )


def test_model_stack_validation_succeeds_for_valid_files(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    deployment_root = tmp_path / "model-deployments"
    artifact_root = tmp_path / "model-artifacts"
    deployment_root.mkdir()
    artifact_root.mkdir()

    catalog_path = tmp_path / "catalog.json"
    service_map_path = tmp_path / "service-map.json"
    _write_model_catalog(catalog_path)
    _write_service_map(service_map_path)
    (artifact_root / "qwen" / "qwen2.5-vl-3b-instruct").mkdir(parents=True)

    result = validate_model_stack(
        StubSettings(
            repo_root=repo_root,
            model_deployment_root=deployment_root,
            model_artifact_root=artifact_root,
            model_catalog_path=catalog_path,
            model_service_map_path=service_map_path,
            model_allowlist=["TRANSCRIPTION_PRIMARY"],
            outbound_allowlist=["localhost", "127.0.0.1", "::1"],
            openai_base_url="http://127.0.0.1:8010/v1",
        )
    )

    assert result.status == "ok"


def test_model_stack_validation_fails_if_model_root_is_inside_repo(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    catalog_path = tmp_path / "catalog.json"
    service_map_path = tmp_path / "service-map.json"
    _write_model_catalog(catalog_path)
    _write_service_map(service_map_path)

    result = validate_model_stack(
        StubSettings(
            repo_root=repo_root,
            model_deployment_root=repo_root / "models",
            model_artifact_root=tmp_path / "model-artifacts",
            model_catalog_path=catalog_path,
            model_service_map_path=service_map_path,
            model_allowlist=["TRANSCRIPTION_PRIMARY"],
            outbound_allowlist=["localhost", "127.0.0.1", "::1"],
            openai_base_url="http://127.0.0.1:8010/v1",
        )
    )

    assert result.status == "fail"
    assert "outside the repository" in result.detail


def test_model_stack_validation_fails_when_required_artifact_path_is_missing(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    deployment_root = tmp_path / "model-deployments"
    artifact_root = tmp_path / "model-artifacts"
    deployment_root.mkdir()
    artifact_root.mkdir()

    catalog_path = tmp_path / "catalog.json"
    service_map_path = tmp_path / "service-map.json"
    _write_model_catalog(catalog_path)
    _write_service_map(service_map_path)

    result = validate_model_stack(
        StubSettings(
            repo_root=repo_root,
            model_deployment_root=deployment_root,
            model_artifact_root=artifact_root,
            model_catalog_path=catalog_path,
            model_service_map_path=service_map_path,
            model_allowlist=["TRANSCRIPTION_PRIMARY"],
            outbound_allowlist=["localhost", "127.0.0.1", "::1"],
            openai_base_url="http://127.0.0.1:8010/v1",
        )
    )

    assert result.status == "fail"
    assert "does not exist" in result.detail


def test_model_stack_validation_fails_for_disallowed_service_base_url(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    deployment_root = tmp_path / "model-deployments"
    artifact_root = tmp_path / "model-artifacts"
    deployment_root.mkdir()
    artifact_root.mkdir()
    (artifact_root / "qwen" / "qwen2.5-vl-3b-instruct").mkdir(parents=True)

    catalog_path = tmp_path / "catalog.json"
    service_map_path = tmp_path / "service-map.json"
    _write_model_catalog(catalog_path)
    _write_public_service_map(service_map_path)

    result = validate_model_stack(
        StubSettings(
            repo_root=repo_root,
            model_deployment_root=deployment_root,
            model_artifact_root=artifact_root,
            model_catalog_path=catalog_path,
            model_service_map_path=service_map_path,
            model_allowlist=["TRANSCRIPTION_PRIMARY"],
            outbound_allowlist=["model-gateway.internal"],
            openai_base_url="http://model-gateway.internal/v1",
        )
    )

    assert result.status == "fail"
    assert "outside the outbound allowlist" in result.detail


def test_model_stack_validation_fails_when_roles_share_the_same_service(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    deployment_root = tmp_path / "model-deployments"
    artifact_root = tmp_path / "model-artifacts"
    deployment_root.mkdir()
    artifact_root.mkdir()

    (artifact_root / "qwen" / "primary").mkdir(parents=True)
    (artifact_root / "assist" / "qwen3-4b").mkdir(parents=True)

    catalog_path = tmp_path / "catalog.json"
    service_map_path = tmp_path / "service-map.json"
    _write_model_catalog_with_duplicate_service(catalog_path)
    _write_service_map_with_two_services(service_map_path)

    result = validate_model_stack(
        StubSettings(
            repo_root=repo_root,
            model_deployment_root=deployment_root,
            model_artifact_root=artifact_root,
            model_catalog_path=catalog_path,
            model_service_map_path=service_map_path,
            model_allowlist=["TRANSCRIPTION_PRIMARY", "ASSIST"],
            outbound_allowlist=["localhost", "127.0.0.1", "::1"],
            openai_base_url="http://127.0.0.1:8010/v1",
        )
    )

    assert result.status == "fail"
    assert "own deployment unit" in result.detail


def test_model_stack_validation_fails_when_artifact_roots_overlap(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    deployment_root = tmp_path / "model-deployments"
    artifact_root = tmp_path / "model-artifacts"
    deployment_root.mkdir()
    artifact_root.mkdir()

    (artifact_root / "isolated" / "primary" / "assist").mkdir(parents=True)

    catalog_path = tmp_path / "catalog.json"
    service_map_path = tmp_path / "service-map.json"
    _write_model_catalog_with_overlapping_paths(catalog_path)
    _write_service_map_with_two_services(service_map_path)

    result = validate_model_stack(
        StubSettings(
            repo_root=repo_root,
            model_deployment_root=deployment_root,
            model_artifact_root=artifact_root,
            model_catalog_path=catalog_path,
            model_service_map_path=service_map_path,
            model_allowlist=["TRANSCRIPTION_PRIMARY", "ASSIST"],
            outbound_allowlist=["localhost", "127.0.0.1", "::1"],
            openai_base_url="http://127.0.0.1:8010/v1",
        )
    )

    assert result.status == "fail"
    assert "must not share artefact roots" in result.detail


def test_model_stack_validation_fails_for_shared_mutable_cache_artifact_path(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    deployment_root = tmp_path / "model-deployments"
    artifact_root = tmp_path / "model-artifacts"
    deployment_root.mkdir()
    artifact_root.mkdir()

    (artifact_root / "cache" / "primary").mkdir(parents=True)

    catalog_path = tmp_path / "catalog.json"
    service_map_path = tmp_path / "service-map.json"
    _write_model_catalog_with_mutable_cache_path(catalog_path)
    _write_service_map(service_map_path)

    result = validate_model_stack(
        StubSettings(
            repo_root=repo_root,
            model_deployment_root=deployment_root,
            model_artifact_root=artifact_root,
            model_catalog_path=catalog_path,
            model_service_map_path=service_map_path,
            model_allowlist=["TRANSCRIPTION_PRIMARY"],
            outbound_allowlist=["localhost", "127.0.0.1", "::1"],
            openai_base_url="http://127.0.0.1:8010/v1",
        )
    )

    assert result.status == "fail"
    assert "shared mutable/cache" in result.detail
