from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

SecurityFindingSeverity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
SecurityFindingStatus = Literal["OPEN", "IN_PROGRESS", "RESOLVED"]

RiskAcceptanceStatus = Literal["ACTIVE", "EXPIRED", "REVOKED"]
RiskAcceptanceEventType = Literal[
    "ACCEPTANCE_CREATED",
    "ACCEPTANCE_REVIEW_SCHEDULED",
    "ACCEPTANCE_RENEWED",
    "ACCEPTANCE_EXPIRED",
    "ACCEPTANCE_REVOKED",
]


@dataclass(frozen=True)
class SecurityFindingRecord:
    id: str
    status: SecurityFindingStatus
    severity: SecurityFindingSeverity
    owner_user_id: str
    source: str
    opened_at: datetime
    resolved_at: datetime | None
    resolution_summary: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class RiskAcceptanceRecord:
    id: str
    finding_id: str
    status: RiskAcceptanceStatus
    justification: str
    approved_by: str
    accepted_at: datetime
    expires_at: datetime | None
    review_date: datetime | None
    revoked_by: str | None
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class RiskAcceptanceEventRecord:
    id: int
    risk_acceptance_id: str
    event_type: RiskAcceptanceEventType
    actor_user_id: str | None
    expires_at: datetime | None
    review_date: datetime | None
    reason: str | None
    created_at: datetime
