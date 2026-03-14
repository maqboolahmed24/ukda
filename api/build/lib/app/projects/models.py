from dataclasses import dataclass
from datetime import datetime
from typing import Literal

AccessTier = Literal["OPEN", "SAFEGUARDED", "CONTROLLED"]
ProjectRole = Literal["PROJECT_LEAD", "RESEARCHER", "REVIEWER"]
ProjectStatus = Literal["ACTIVE", "ARCHIVED"]


@dataclass(frozen=True)
class BaselinePolicySnapshot:
    id: str
    snapshot_hash: str
    rules_json: str
    seeded_by: str
    created_at: datetime


@dataclass(frozen=True)
class ProjectSummary:
    id: str
    name: str
    purpose: str
    status: ProjectStatus
    created_by: str
    created_at: datetime
    intended_access_tier: AccessTier
    baseline_policy_snapshot_id: str
    current_user_role: ProjectRole | None


@dataclass(frozen=True)
class ProjectMember:
    project_id: str
    user_id: str
    email: str
    display_name: str
    role: ProjectRole
    created_at: datetime
    updated_at: datetime
