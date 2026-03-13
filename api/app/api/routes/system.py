from fastapi import APIRouter, Response, status

from app.core.config import get_settings
from app.core.readiness import evaluate_readiness, utc_timestamp

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    settings = get_settings()
    return {
        "service": "api",
        "status": "OK",
        "environment": settings.environment,
        "version": settings.version,
        "timestamp": utc_timestamp(),
    }


@router.get("/readyz")
def readyz(response: Response) -> dict[str, object]:
    settings = get_settings()
    payload, is_ready = evaluate_readiness(settings)
    response.status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return payload
