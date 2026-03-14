import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class SessionTokenClaims:
    session_id: str
    expires_at_epoch: int


def _urlsafe_b64encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _urlsafe_b64decode(payload: str) -> bytes:
    padding = "=" * (-len(payload) % 4)
    return base64.urlsafe_b64decode(payload + padding)


def issue_session_token(
    *,
    session_id: str,
    expires_at: datetime,
    secret: str,
) -> str:
    claims_payload = {
        "sid": session_id,
        "exp": int(expires_at.astimezone(UTC).timestamp()),
    }
    payload = _urlsafe_b64encode(
        json.dumps(claims_payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return f"{payload}.{signature}"


def parse_session_token(
    token: str,
    *,
    secret: str,
    now: datetime | None = None,
) -> SessionTokenClaims | None:
    try:
        payload, signature = token.split(".", 1)
    except ValueError:
        return None

    expected_signature = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None

    try:
        claims = json.loads(_urlsafe_b64decode(payload).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return None

    session_id = claims.get("sid")
    expires_at_epoch = claims.get("exp")
    if not isinstance(session_id, str) or not isinstance(expires_at_epoch, int):
        return None

    current = now or datetime.now(UTC)
    if expires_at_epoch <= int(current.timestamp()):
        return None

    return SessionTokenClaims(
        session_id=session_id,
        expires_at_epoch=expires_at_epoch,
    )
