from functools import lru_cache

from app.core.config import Settings, get_settings
from app.exports.models import ExportStubEventRecord
from app.exports.store import ExportStubStore


class ExportStubService:
    def __init__(
        self,
        *,
        settings: Settings,
        store: ExportStubStore | None = None,
    ) -> None:
        self._settings = settings
        self._store = store or ExportStubStore(settings)

    def record_attempt(
        self,
        *,
        project_id: str | None,
        route: str,
        method: str,
        actor_user_id: str | None,
        request_id: str,
    ) -> ExportStubEventRecord:
        return self._store.append_stub_event(
            project_id=project_id,
            route=route,
            method=method,
            actor_user_id=actor_user_id,
            request_id=request_id,
        )


@lru_cache
def get_export_stub_service() -> ExportStubService:
    settings = get_settings()
    return ExportStubService(settings=settings)
