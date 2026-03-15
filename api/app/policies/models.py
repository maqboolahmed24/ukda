from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

PolicyStatus = Literal["DRAFT", "ACTIVE", "RETIRED"]
PolicyValidationStatus = Literal["NOT_VALIDATED", "VALID", "INVALID"]
PolicyEventType = Literal[
    "POLICY_CREATED",
    "POLICY_EDITED",
    "POLICY_VALIDATED_VALID",
    "POLICY_VALIDATED_INVALID",
    "POLICY_ACTIVATED",
    "POLICY_RETIRED",
]
PolicyCompareTargetKind = Literal["POLICY", "BASELINE_SNAPSHOT"]
PolicyExplainabilityTraceOutcome = Literal[
    "AUTO_APPLY",
    "REVIEW_REQUIRED",
    "BLOCKED",
    "UNSPECIFIED",
]


@dataclass(frozen=True)
class RedactionPolicyRecord:
    id: str
    project_id: str
    policy_family_id: str
    name: str
    version: int
    seeded_from_baseline_snapshot_id: str | None
    supersedes_policy_id: str | None
    superseded_by_policy_id: str | None
    rules_json: dict[str, object]
    version_etag: str
    status: PolicyStatus
    created_by: str
    created_at: datetime
    activated_by: str | None
    activated_at: datetime | None
    retired_by: str | None
    retired_at: datetime | None
    validation_status: PolicyValidationStatus
    validated_rules_sha256: str | None
    last_validated_by: str | None
    last_validated_at: datetime | None


@dataclass(frozen=True)
class ProjectPolicyProjectionRecord:
    project_id: str
    active_policy_id: str | None
    active_policy_family_id: str | None
    updated_at: datetime


@dataclass(frozen=True)
class PolicyEventRecord:
    id: str
    policy_id: str
    event_type: PolicyEventType
    actor_user_id: str | None
    reason: str | None
    rules_sha256: str
    rules_snapshot_key: str
    created_at: datetime


@dataclass(frozen=True)
class BaselinePolicySnapshotRecord:
    id: str
    snapshot_hash: str
    rules_json: dict[str, object]
    created_at: datetime
    seeded_by: str


@dataclass(frozen=True)
class PolicyValidationResult:
    policy: RedactionPolicyRecord
    issues: tuple[str, ...]


@dataclass(frozen=True)
class PolicyRulesDiffItem:
    path: str
    before: object | None
    after: object | None


@dataclass(frozen=True)
class PolicyCompareResult:
    source_policy: RedactionPolicyRecord
    target_kind: PolicyCompareTargetKind
    target_policy: RedactionPolicyRecord | None
    target_baseline_snapshot_id: str | None
    source_rules_sha256: str
    target_rules_sha256: str
    differences: tuple[PolicyRulesDiffItem, ...]


@dataclass(frozen=True)
class ActiveProjectPolicyView:
    projection: ProjectPolicyProjectionRecord | None
    policy: RedactionPolicyRecord | None


@dataclass(frozen=True)
class PolicyRuleSnapshotRecord:
    policy_id: str
    rules_sha256: str
    rules_snapshot_key: str
    rules_json: dict[str, object]
    created_at: datetime


@dataclass(frozen=True)
class PolicyLineageSnapshot:
    policy: RedactionPolicyRecord
    projection: ProjectPolicyProjectionRecord | None
    lineage: tuple[RedactionPolicyRecord, ...]
    events: tuple[PolicyEventRecord, ...]
    active_policy_differs: bool


@dataclass(frozen=True)
class PolicyUsageRunRecord:
    run_id: str
    project_id: str
    document_id: str
    run_kind: str
    run_status: str
    supersedes_redaction_run_id: str | None
    policy_family_id: str | None
    policy_version: str | None
    run_created_at: datetime
    run_finished_at: datetime | None
    governance_readiness_status: str | None
    governance_generation_status: str | None
    governance_manifest_id: str | None
    governance_ledger_id: str | None
    governance_manifest_sha256: str | None
    governance_ledger_sha256: str | None
    governance_ledger_verification_status: str | None


@dataclass(frozen=True)
class PolicyUsageManifestRecord:
    id: str
    run_id: str
    project_id: str
    document_id: str
    status: str
    attempt_number: int
    manifest_sha256: str | None
    source_review_snapshot_sha256: str
    created_at: datetime


@dataclass(frozen=True)
class PolicyUsageLedgerRecord:
    id: str
    run_id: str
    project_id: str
    document_id: str
    status: str
    attempt_number: int
    ledger_sha256: str | None
    source_review_snapshot_sha256: str
    created_at: datetime


@dataclass(frozen=True)
class PolicyUsagePseudonymSummary:
    total_entries: int
    active_entries: int
    retired_entries: int
    alias_strategy_versions: tuple[str, ...]
    salt_version_refs: tuple[str, ...]


@dataclass(frozen=True)
class PolicyUsageSnapshot:
    policy: RedactionPolicyRecord
    runs: tuple[PolicyUsageRunRecord, ...]
    manifests: tuple[PolicyUsageManifestRecord, ...]
    ledgers: tuple[PolicyUsageLedgerRecord, ...]
    pseudonym_summary: PolicyUsagePseudonymSummary


@dataclass(frozen=True)
class PolicyExplainabilityCategoryRule:
    id: str
    action: str
    review_required_below: float | None
    auto_apply_above: float | None
    confidence_threshold: float | None
    requires_reviewer: bool
    escalation_flags: tuple[str, ...]


@dataclass(frozen=True)
class PolicyExplainabilityTrace:
    category_id: str
    sample_confidence: float
    selected_action: str
    outcome: PolicyExplainabilityTraceOutcome
    rationale: str


@dataclass(frozen=True)
class PolicyExplainabilitySnapshot:
    policy: RedactionPolicyRecord
    rules_sha256: str
    category_rules: tuple[PolicyExplainabilityCategoryRule, ...]
    defaults: dict[str, object]
    reviewer_requirements: bool | dict[str, object] | None
    escalation_flags: bool | dict[str, object] | None
    pseudonymisation: dict[str, object] | None
    generalisation: dict[str, object] | tuple[object, ...] | None
    reviewer_explanation_mode: str | None
    deterministic_traces: tuple[PolicyExplainabilityTrace, ...]


@dataclass(frozen=True)
class PolicySnapshotView:
    policy: RedactionPolicyRecord
    event: PolicyEventRecord
    snapshot: PolicyRuleSnapshotRecord
