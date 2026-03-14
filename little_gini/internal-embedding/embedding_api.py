from __future__ import annotations

import os
from typing import List, Union

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


MODEL_DIR = _required_env("EMBED_MODEL_DIR")
MODEL_ALIAS = os.getenv("EMBED_MODEL_ALIAS", "bge-small-en-v1.5").strip() or "bge-small-en-v1.5"
MAX_SEQ_LENGTH = int(os.getenv("EMBED_MAX_SEQ_LENGTH", "512"))

model = SentenceTransformer(MODEL_DIR, device="cpu", local_files_only=True)
model.max_seq_length = MAX_SEQ_LENGTH


def _normalize_input(value: Union[str, List[str]]) -> List[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return value
    raise HTTPException(status_code=400, detail="input must be a string or list of strings")


def _count_tokens(texts: List[str]) -> int:
    tokenizer = model.tokenizer
    encoded = tokenizer(
        texts,
        truncation=True,
        max_length=MAX_SEQ_LENGTH,
        add_special_tokens=True,
    )
    return sum(len(ids) for ids in encoded["input_ids"])


class EmbeddingRequest(BaseModel):
    model: str
    input: Union[str, List[str]]
    encoding_format: str | None = Field(default=None)


class ModelCard(BaseModel):
    id: str
    object: str = "model"
    owned_by: str = "internal"


app = FastAPI(title="UKDA Internal Embedding Service", version="1.0.0")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": MODEL_ALIAS,
    }


@app.get("/v1/models")
def list_models() -> dict:
    model_card = ModelCard(id=MODEL_ALIAS)
    return {
        "object": "list",
        "data": [model_card.model_dump()],
    }


@app.post("/v1/embeddings")
def embeddings(payload: EmbeddingRequest) -> dict:
    if payload.model != MODEL_ALIAS:
        raise HTTPException(
            status_code=400,
            detail=f"model must be '{MODEL_ALIAS}'",
        )

    texts = _normalize_input(payload.input)
    vectors = model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    total_tokens = _count_tokens(texts)

    data = [
        {
            "object": "embedding",
            "index": i,
            "embedding": vector.tolist(),
        }
        for i, vector in enumerate(vectors)
    ]

    return {
        "object": "list",
        "data": data,
        "model": MODEL_ALIAS,
        "usage": {
            "prompt_tokens": total_tokens,
            "total_tokens": total_tokens,
        },
    }
