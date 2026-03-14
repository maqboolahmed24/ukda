from __future__ import annotations

import base64
import binascii
import os
import subprocess
import tempfile
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _resolve_model_path(model_dir: Path, file_name: str, env_name: str) -> Path:
    path = (model_dir / file_name).resolve()
    if not path.is_file():
        raise RuntimeError(f"Missing model file for {env_name}: {path}")
    return path


MODEL_DIR = Path(_required_env("KRAKEN_MODEL_DIR")).resolve()
MODEL_ALIAS = os.getenv("KRAKEN_MODEL_ALIAS", "Kraken").strip() or "Kraken"
RECOGNITION_MODEL_FILE = (
    os.getenv("KRAKEN_RECOGNITION_MODEL_FILE", "catmus-print-fondue-large.mlmodel").strip()
    or "catmus-print-fondue-large.mlmodel"
)
SEGMENTATION_MODEL_FILE = (
    os.getenv("KRAKEN_SEGMENTATION_MODEL_FILE", "blla.mlmodel").strip() or "blla.mlmodel"
)
KRAKEN_DEVICE = os.getenv("KRAKEN_DEVICE", "cpu").strip() or "cpu"
KRAKEN_OCR_TIMEOUT_SECONDS = int(os.getenv("KRAKEN_OCR_TIMEOUT_SECONDS", "120"))

RECOGNITION_MODEL_PATH = _resolve_model_path(
    MODEL_DIR,
    RECOGNITION_MODEL_FILE,
    "KRAKEN_RECOGNITION_MODEL_FILE",
)
SEGMENTATION_MODEL_PATH = _resolve_model_path(
    MODEL_DIR,
    SEGMENTATION_MODEL_FILE,
    "KRAKEN_SEGMENTATION_MODEL_FILE",
)


class OCRRequest(BaseModel):
    image_base64: str = Field(min_length=4)
    reorder: bool = True

    @model_validator(mode="after")
    def validate_image_payload(self) -> "OCRRequest":
        candidate = self.image_base64.strip()
        if not candidate:
            raise ValueError("image_base64 must not be empty")
        return self


def _decode_image_payload(image_base64: str) -> bytes:
    payload = image_base64.strip()
    if payload.startswith("data:") and "," in payload:
        payload = payload.split(",", 1)[1]
    try:
        return base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as error:
        raise HTTPException(status_code=400, detail="image_base64 must be valid base64") from error


def _run_kraken_ocr(*, input_path: Path, output_path: Path, reorder: bool) -> tuple[str, str]:
    command = [
        "kraken",
        "--device",
        KRAKEN_DEVICE,
        "-i",
        str(input_path),
        str(output_path),
        "segment",
        "-bl",
        "-i",
        str(SEGMENTATION_MODEL_PATH),
        "ocr",
        "-m",
        str(RECOGNITION_MODEL_PATH),
    ]
    if not reorder:
        command.append("--no-reorder")

    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=KRAKEN_OCR_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise HTTPException(status_code=504, detail="kraken OCR request timed out") from error
    except subprocess.CalledProcessError as error:
        stderr = (error.stderr or "").strip()
        stdout = (error.stdout or "").strip()
        detail = stderr or stdout or "unknown kraken error"
        raise HTTPException(status_code=500, detail=f"kraken OCR failed: {detail[-2000:]}") from error

    if not output_path.exists():
        raise HTTPException(status_code=500, detail="kraken OCR did not produce an output file")

    text = output_path.read_text(encoding="utf-8", errors="replace").strip()
    logs = ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()
    return text, logs


app = FastAPI(title="UKDA Kraken Fallback Service", version="1.0.0")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "kraken",
        "model": MODEL_ALIAS,
        "model_dir": str(MODEL_DIR),
        "recognition_model": RECOGNITION_MODEL_PATH.name,
        "segmentation_model": SEGMENTATION_MODEL_PATH.name,
    }


@app.post("/ocr")
def ocr(payload: OCRRequest) -> dict:
    image_bytes = _decode_image_payload(payload.image_base64)

    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="ukda-kraken-") as tmpdir:
        tmp_path = Path(tmpdir)
        input_path = tmp_path / "input.png"
        output_path = tmp_path / "output.txt"
        input_path.write_bytes(image_bytes)

        text, logs = _run_kraken_ocr(
            input_path=input_path,
            output_path=output_path,
            reorder=payload.reorder,
        )

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return {
        "model": MODEL_ALIAS,
        "text": text,
        "elapsed_ms": elapsed_ms,
        "meta": {
            "engine": "kraken",
            "recognition_model": RECOGNITION_MODEL_PATH.name,
            "segmentation_model": SEGMENTATION_MODEL_PATH.name,
            "device": KRAKEN_DEVICE,
            "reorder": payload.reorder,
            "log_excerpt": logs[-500:] if logs else "",
        },
    }


@app.post("/transcribe")
def transcribe(payload: OCRRequest) -> dict:
    return ocr(payload)
