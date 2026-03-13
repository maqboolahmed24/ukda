import json
import logging
import re
from datetime import UTC, datetime
from functools import lru_cache

from app.core.config import Settings, get_settings

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_SENSITIVE_KEY_FRAGMENTS = (
    "token",
    "password",
    "secret",
    "cookie",
    "authorization",
    "raw",
    "content",
    "bytes",
    "credential",
)


def _sanitize_text(value: str, *, max_length: int = 512) -> str:
    collapsed = _CONTROL_CHARS_RE.sub(" ", value)
    collapsed = collapsed.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    collapsed = " ".join(collapsed.split())
    return collapsed[:max_length]


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(fragment in lowered for fragment in _SENSITIVE_KEY_FRAGMENTS)


def _sanitize_value(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, list):
        return [_sanitize_value(entry) for entry in value[:20]]
    if isinstance(value, dict):
        sanitized: dict[str, object] = {}
        for raw_key, raw_value in list(value.items())[:20]:
            key = _sanitize_text(str(raw_key), max_length=64)
            if _is_sensitive_key(key):
                continue
            sanitized[key] = _sanitize_value(raw_value)
        return sanitized
    return _sanitize_text(str(value))


def sanitize_telemetry_payload(payload: dict[str, object] | None) -> dict[str, object]:
    if payload is None:
        return {}

    sanitized: dict[str, object] = {}
    for raw_key, raw_value in payload.items():
        key = _sanitize_text(raw_key, max_length=64)
        if not key or _is_sensitive_key(key):
            continue
        sanitized[key] = _sanitize_value(raw_value)
    return sanitized


class _JsonTelemetryFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "logger": record.name,
            "level": record.levelname,
            "event": _sanitize_text(str(getattr(record, "event", "telemetry_log")), max_length=80),
            "message": _sanitize_text(record.getMessage()),
        }

        raw_extra = getattr(record, "payload", None)
        if isinstance(raw_extra, dict):
            payload["payload"] = sanitize_telemetry_payload(raw_extra)
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


@lru_cache
def _logger() -> logging.Logger:
    settings: Settings = get_settings()
    logger = logging.getLogger("ukde.telemetry")
    logger.setLevel(settings.telemetry_log_level)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_JsonTelemetryFormatter())
        logger.addHandler(handler)
    return logger


def emit_telemetry_log(
    *,
    event: str,
    message: str,
    payload: dict[str, object] | None = None,
    level: int = logging.INFO,
) -> None:
    logger = _logger()
    logger.log(level, _sanitize_text(message), extra={"event": event, "payload": payload or {}})


def telemetry_log_level_name() -> str:
    logger = _logger()
    return logging.getLevelName(logger.level)
