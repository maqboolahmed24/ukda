from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

PseudonymRegistryEntryStatus = Literal["ACTIVE", "RETIRED"]
PseudonymRegistryEntryEventType = Literal[
    "ENTRY_CREATED",
    "ENTRY_REUSED",
    "ENTRY_RETIRED",
]


@dataclass(frozen=True)
class PseudonymRegistryEntryRecord:
    id: str
    project_id: str
    source_run_id: str
    source_fingerprint_hmac_sha256: str
    alias_value: str
    policy_id: str
    salt_version_ref: str
    alias_strategy_version: str
    created_by: str
    created_at: datetime
    last_used_run_id: str | None
    updated_at: datetime
    status: PseudonymRegistryEntryStatus
    retired_at: datetime | None
    retired_by: str | None
    supersedes_entry_id: str | None
    superseded_by_entry_id: str | None


@dataclass(frozen=True)
class PseudonymRegistryEntryEventRecord:
    id: str
    entry_id: str
    event_type: PseudonymRegistryEntryEventType
    run_id: str
    actor_user_id: str | None
    created_at: datetime
