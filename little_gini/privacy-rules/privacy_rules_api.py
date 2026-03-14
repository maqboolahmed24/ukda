from __future__ import annotations

import os
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from pydantic import BaseModel, Field


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


MODEL_DIR = Path(_required_env("PRIVACY_RULES_SPACY_MODEL_DIR")).resolve()
SERVICE_NAME = os.getenv("PRIVACY_RULES_SERVICE_NAME", "Presidio").strip() or "Presidio"
DEFAULT_LANGUAGE = os.getenv("PRIVACY_RULES_LANGUAGE", "en").strip() or "en"


def _validate_model_dir() -> None:
    required = [
        MODEL_DIR / "meta.json",
        MODEL_DIR / "config.cfg",
        MODEL_DIR / "tokenizer",
        MODEL_DIR / "vocab" / "strings.json",
    ]
    for path in required:
        if not path.exists():
            raise RuntimeError(f"Missing required spaCy asset: {path}")


_validate_model_dir()

nlp_configuration = {
    "nlp_engine_name": "spacy",
    "models": [
        {
            "lang_code": DEFAULT_LANGUAGE,
            "model_name": str(MODEL_DIR),
        }
    ],
}
nlp_engine = NlpEngineProvider(nlp_configuration=nlp_configuration).create_engine()
analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=[DEFAULT_LANGUAGE])


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1)
    language: str = DEFAULT_LANGUAGE
    entities: List[str] | None = None
    score_threshold: float = Field(default=0.35, ge=0.0, le=1.0)


app = FastAPI(title="UKDA Privacy Rules Service", version="1.0.0")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "language": DEFAULT_LANGUAGE,
        "model_dir": str(MODEL_DIR),
    }


@app.post("/analyze")
def analyze(payload: AnalyzeRequest) -> dict:
    if payload.language != DEFAULT_LANGUAGE:
        raise HTTPException(
            status_code=400,
            detail=f"language must be '{DEFAULT_LANGUAGE}'",
        )

    results = analyzer.analyze(
        text=payload.text,
        language=payload.language,
        entities=payload.entities,
        score_threshold=payload.score_threshold,
    )

    findings = [
        {
            "entity_type": item.entity_type,
            "start": item.start,
            "end": item.end,
            "score": float(item.score),
        }
        for item in results
    ]

    return {
        "service": SERVICE_NAME,
        "language": payload.language,
        "count": len(findings),
        "findings": findings,
    }
