from __future__ import annotations

import base64
import binascii
import os
from collections.abc import Mapping
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response


def _env(name: str, default: str) -> str:
    value = os.getenv(name, "").strip()
    return value or default


ENGINE_BASE_URL = _env("VLM_GATEWAY_ENGINE_BASE_URL", "http://internal-vlm-engine:8000").rstrip("/")
KRAKEN_BASE_URL = _env("VLM_GATEWAY_KRAKEN_BASE_URL", "http://host.docker.internal:8040").rstrip("/")
MODEL_ALIAS = _env("VLM_GATEWAY_MODEL_ALIAS", "Qwen2.5-VL-3B-Instruct")
REQUEST_TIMEOUT = float(_env("VLM_GATEWAY_TIMEOUT_SECONDS", "180"))

app = FastAPI(title="UKDA Internal VLM Gateway", version="1.0.0")
client = httpx.AsyncClient(timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=5.0))


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await client.aclose()


def _extract_data_url(part: Mapping[str, Any]) -> str:
    image_payload = part.get("image_url")
    url = part.get("url")
    if isinstance(image_payload, Mapping):
        payload_url = image_payload.get("url")
        if isinstance(payload_url, str):
            url = payload_url
    elif isinstance(image_payload, str):
        url = image_payload

    if not isinstance(url, str) or not url:
        raise HTTPException(status_code=400, detail="image_url part is missing url")
    if not url.startswith("data:image/"):
        raise HTTPException(
            status_code=400,
            detail="image_url must be a data:image/* URL (remote URLs are blocked)",
        )
    if "," not in url:
        raise HTTPException(status_code=400, detail="image_url data URL is malformed")
    return url


def _extract_base64_payload(data_url: str) -> str:
    payload = data_url.split(",", 1)[1]
    try:
        base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as error:
        raise HTTPException(status_code=400, detail="image_url contains invalid base64 data") from error
    return payload


async def _ocr_image(payload_b64: str, index: int) -> str:
    try:
        response = await client.post(
            f"{KRAKEN_BASE_URL}/ocr",
            json={"image_base64": payload_b64, "reorder": True},
        )
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=503,
            detail=f"kraken dependency unavailable for image_{index}",
        ) from error

    if response.status_code != 200:
        raise HTTPException(
            status_code=503,
            detail=f"kraken dependency returned {response.status_code} for image_{index}",
        )

    body = response.json()
    text = str(body.get("text", "")).strip()
    return text


async def _normalize_messages(payload: dict[str, Any]) -> list[str]:
    messages = payload.get("messages")
    if not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="messages must be a list")

    normalized: list[dict[str, Any]] = []
    ocr_segments: list[str] = []
    image_index = 0
    for message in messages:
        if not isinstance(message, dict):
            raise HTTPException(status_code=400, detail="each message must be an object")

        candidate = dict(message)
        content = candidate.get("content")
        if isinstance(content, str):
            normalized.append(candidate)
            continue

        if not isinstance(content, list):
            raise HTTPException(
                status_code=400,
                detail="message content must be either a string or an array of content parts",
            )

        flattened_parts: list[str] = []
        for part in content:
            if not isinstance(part, dict):
                raise HTTPException(status_code=400, detail="content parts must be objects")

            part_type = part.get("type")
            if part_type == "text":
                flattened_parts.append(str(part.get("text", "")))
                continue

            if part_type == "image_url":
                image_index += 1
                data_url = _extract_data_url(part)
                payload_b64 = _extract_base64_payload(data_url)
                ocr_text = await _ocr_image(payload_b64, image_index)
                segment = f"[image_{image_index}_ocr]\n{ocr_text}"
                flattened_parts.append(segment)
                ocr_segments.append(segment)
                continue

            raise HTTPException(
                status_code=400,
                detail=f'Unsupported content part type: "{part_type}"',
            )

        candidate["content"] = "\n\n".join(flattened_parts)
        normalized.append(candidate)

    payload["messages"] = normalized
    return ocr_segments


def _response_from_upstream(upstream: httpx.Response) -> Response:
    content_type = upstream.headers.get("content-type", "application/json")
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=content_type.split(";", 1)[0],
        headers={"content-type": content_type},
    )


async def _probe(url: str) -> tuple[bool, int | None, str]:
    try:
        response = await client.get(url)
        ok = response.status_code == 200
        detail = "ok" if ok else f"http {response.status_code}"
        return ok, response.status_code, detail
    except httpx.HTTPError as error:
        return False, None, str(error)


@app.get("/health")
async def health() -> JSONResponse:
    engine_ok, engine_code, engine_detail = await _probe(f"{ENGINE_BASE_URL}/v1/models")
    kraken_ok, kraken_code, kraken_detail = await _probe(f"{KRAKEN_BASE_URL}/health")

    status_code = 200 if engine_ok and kraken_ok else 503
    payload = {
        "status": "ok" if status_code == 200 else "degraded",
        "service": "internal-vlm-gateway",
        "model": MODEL_ALIAS,
        "components": {
            "engine": {
                "ok": engine_ok,
                "status_code": engine_code,
                "detail": engine_detail,
            },
            "kraken": {
                "ok": kraken_ok,
                "status_code": kraken_code,
                "detail": kraken_detail,
            },
        },
    }
    return JSONResponse(content=payload, status_code=status_code)


@app.get("/v1/models")
async def list_models(request: Request) -> Response:
    headers: dict[str, str] = {}
    auth = request.headers.get("authorization")
    if auth:
        headers["authorization"] = auth
    try:
        response = await client.get(f"{ENGINE_BASE_URL}/v1/models", headers=headers)
    except httpx.HTTPError as error:
        raise HTTPException(status_code=503, detail="internal-vlm engine unavailable") from error
    return _response_from_upstream(response)


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> Response:
    try:
        payload = await request.json()
    except Exception as error:
        raise HTTPException(status_code=400, detail="invalid JSON request body") from error

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="request body must be a JSON object")

    ocr_segments = await _normalize_messages(payload)

    headers: dict[str, str] = {}
    auth = request.headers.get("authorization")
    if auth:
        headers["authorization"] = auth
    try:
        response = await client.post(
            f"{ENGINE_BASE_URL}/v1/chat/completions",
            json=payload,
            headers=headers,
        )
    except httpx.HTTPError as error:
        raise HTTPException(status_code=503, detail="internal-vlm engine unavailable") from error

    if ocr_segments and response.status_code == 200:
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type.lower():
            try:
                body = response.json()
            except Exception:
                body = None
            if isinstance(body, dict):
                choices = body.get("choices")
                if isinstance(choices, list) and choices:
                    message = choices[0].get("message")
                    if isinstance(message, dict):
                        current = str(message.get("content") or "").strip()
                        if not current:
                            fallback_text = "\n\n".join(ocr_segments).strip()
                            if fallback_text:
                                message["content"] = fallback_text
                                return JSONResponse(content=body, status_code=200)

    return _response_from_upstream(response)
