from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from gliner import GLiNER
from pydantic import BaseModel, Field


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


MODEL_DIR = Path(_required_env("NER_MODEL_DIR")).resolve()
MODEL_ALIAS = os.getenv("NER_MODEL_ALIAS", "GLiNER-small-v2.1").strip() or "GLiNER-small-v2.1"

DEFAULT_LABELS = [
    "person",
    "email",
    "phone number",
    "organization",
    "location",
    "date",
]

REQUIRED_FILES = [
    "gliner_config.json",
    "config.json",
    "tokenizer_config.json",
    "spm.model",
    "encoder/config.json",
]


def _validate_artifacts() -> None:
    if not MODEL_DIR.exists():
        raise RuntimeError(f"Model directory does not exist: {MODEL_DIR}")

    has_weights = (MODEL_DIR / "model.safetensors").exists() or (MODEL_DIR / "pytorch_model.bin").exists()
    if not has_weights:
        raise RuntimeError(
            f"Missing model weights in {MODEL_DIR}. Expected model.safetensors or pytorch_model.bin"
        )

    for rel_path in REQUIRED_FILES:
        candidate = MODEL_DIR / rel_path
        if not candidate.exists():
            raise RuntimeError(f"Missing required artifact: {candidate}")


def _build_runtime_model_dir() -> Path:
    runtime_dir = Path("/tmp/gliner-runtime-model")
    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    # Link large/static files from read-only artifact mount.
    for filename in ["config.json", "tokenizer_config.json", "spm.model", "README.md"]:
        src = MODEL_DIR / filename
        if src.exists():
            os.symlink(src, runtime_dir / filename)

    for weight_name in ["model.safetensors", "pytorch_model.bin"]:
        src = MODEL_DIR / weight_name
        if src.exists():
            os.symlink(src, runtime_dir / weight_name)
            break

    encoder_src = MODEL_DIR / "encoder"
    encoder_dst = runtime_dir / "encoder"
    if encoder_src.exists():
        os.symlink(encoder_src, encoder_dst)

    config_path = MODEL_DIR / "gliner_config.json"
    config_data = json.loads(config_path.read_text(encoding="utf-8"))

    # Force local encoder config path so runtime remains offline/local-only.
    if (MODEL_DIR / "encoder").exists():
        config_data["model_name"] = str((runtime_dir / "encoder").resolve())

    (runtime_dir / "gliner_config.json").write_text(
        json.dumps(config_data, indent=2),
        encoding="utf-8",
    )

    return runtime_dir


_validate_artifacts()
RUNTIME_MODEL_DIR = _build_runtime_model_dir()
model = GLiNER.from_pretrained(str(RUNTIME_MODEL_DIR), local_files_only=True)


class NerRequest(BaseModel):
    text: str = Field(min_length=1)
    labels: List[str] | None = None
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    flat_ner: bool = True


app = FastAPI(title="UKDA Internal NER Service", version="1.0.0")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": MODEL_ALIAS,
    }


@app.post("/analyze")
def analyze(payload: NerRequest) -> dict:
    labels = payload.labels or DEFAULT_LABELS
    if len(labels) == 0:
        raise HTTPException(status_code=400, detail="labels must not be empty")

    entities = model.predict_entities(
        payload.text,
        labels,
        threshold=payload.threshold,
        flat_ner=payload.flat_ner,
    )

    return {
        "model": MODEL_ALIAS,
        "labels": labels,
        "entities": entities,
    }
