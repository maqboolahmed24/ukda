from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ExportStubEventRecord:
    id: str
    project_id: str | None
    route: str
    method: str
    actor_user_id: str | None
    request_id: str
    created_at: datetime

