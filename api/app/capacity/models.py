from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

CapacityTestKind = Literal["LOAD", "SOAK", "BENCHMARK"]
CapacityTestStatus = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]
CapacityEnvelopeRole = Literal[
    "transcription-vlm",
    "assist-llm",
    "privacy-ner",
    "privacy-rules",
    "transcription-fallback",
    "embedding-search",
]
CapacityEnvelopeStatus = Literal["MEETING", "BREACHING", "UNAVAILABLE"]


@dataclass(frozen=True)
class CapacityTestRunRecord:
    id: str
    test_kind: CapacityTestKind
    scenario_name: str
    status: CapacityTestStatus
    results_key: str | None
    results_sha256: str | None
    started_by: str
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    scenario_json: dict[str, object]
    results_json: dict[str, object] | None
    failure_reason: str | None


@dataclass(frozen=True)
class CapacityTestRunPage:
    items: list[CapacityTestRunRecord]
    next_cursor: int | None
