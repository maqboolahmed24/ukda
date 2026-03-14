from dataclasses import dataclass
from typing import Literal

from app.core.config import Settings, get_settings

StorageWriter = Literal["app", "export_gateway"]


@dataclass(frozen=True)
class StorageBoundary:
    controlled_raw_prefix: str
    controlled_derived_prefix: str
    safeguarded_exports_prefix: str

    def writable_prefixes_for(self, writer: StorageWriter) -> tuple[str, ...]:
        if writer == "export_gateway":
            return (self.safeguarded_exports_prefix,)
        return (self.controlled_raw_prefix, self.controlled_derived_prefix)

    def can_write(self, *, writer: StorageWriter, object_key: str) -> bool:
        key = object_key.lstrip("/")
        return any(key.startswith(prefix) for prefix in self.writable_prefixes_for(writer))


def resolve_storage_boundary(settings: Settings | None = None) -> StorageBoundary:
    resolved = settings or get_settings()
    return StorageBoundary(
        controlled_raw_prefix=resolved.storage_controlled_raw_prefix,
        controlled_derived_prefix=resolved.storage_controlled_derived_prefix,
        safeguarded_exports_prefix=resolved.storage_safeguarded_exports_prefix,
    )
