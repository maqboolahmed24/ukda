from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.audit.dependencies import get_audit_request_context
from app.audit.models import AuditEventType, AuditRequestContext
from app.audit.service import AuditService, get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.policies.models import (
    ActiveProjectPolicyView,
    PolicyCompareResult,
    PolicyEventRecord,
    PolicyExplainabilitySnapshot,
    PolicyLineageSnapshot,
    PolicySnapshotView,
    PolicyUsageSnapshot,
    PolicyValidationResult,
    ProjectPolicyProjectionRecord,
    RedactionPolicyRecord,
)
from app.policies.service import (
    PolicyAccessDeniedError,
    PolicyComparisonError,
    PolicyConflictError,
    PolicyNotFoundError,
    PolicyService,
    PolicyValidationError,
    get_policy_service,
)
from app.policies.store import PolicyStoreUnavailableError

router = APIRouter(
    prefix="/projects/{project_id}/policies",
    dependencies=[Depends(require_authenticated_user)],
)

PolicyStatusLiteral = Literal["DRAFT", "ACTIVE", "RETIRED"]
PolicyValidationStatusLiteral = Literal["NOT_VALIDATED", "VALID", "INVALID"]
PolicyEventTypeLiteral = Literal[
    "POLICY_CREATED",
    "POLICY_EDITED",
    "POLICY_VALIDATED_VALID",
    "POLICY_VALIDATED_INVALID",
    "POLICY_ACTIVATED",
    "POLICY_RETIRED",
]
PolicyCompareTargetKindLiteral = Literal["POLICY", "BASELINE_SNAPSHOT"]


class PolicyResponse(BaseModel):
    id: str
    project_id: str = Field(serialization_alias="projectId")
    policy_family_id: str = Field(serialization_alias="policyFamilyId")
    name: str
    version: int
    seeded_from_baseline_snapshot_id: str | None = Field(
        default=None,
        serialization_alias="seededFromBaselineSnapshotId",
    )
    supersedes_policy_id: str | None = Field(
        default=None,
        serialization_alias="supersedesPolicyId",
    )
    superseded_by_policy_id: str | None = Field(
        default=None,
        serialization_alias="supersededByPolicyId",
    )
    rules_json: dict[str, object] = Field(serialization_alias="rulesJson")
    version_etag: str = Field(serialization_alias="versionEtag")
    status: PolicyStatusLiteral
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    activated_by: str | None = Field(default=None, serialization_alias="activatedBy")
    activated_at: datetime | None = Field(default=None, serialization_alias="activatedAt")
    retired_by: str | None = Field(default=None, serialization_alias="retiredBy")
    retired_at: datetime | None = Field(default=None, serialization_alias="retiredAt")
    validation_status: PolicyValidationStatusLiteral = Field(
        serialization_alias="validationStatus"
    )
    validated_rules_sha256: str | None = Field(
        default=None,
        serialization_alias="validatedRulesSha256",
    )
    last_validated_by: str | None = Field(
        default=None,
        serialization_alias="lastValidatedBy",
    )
    last_validated_at: datetime | None = Field(
        default=None,
        serialization_alias="lastValidatedAt",
    )


class PolicyListResponse(BaseModel):
    items: list[PolicyResponse]


class PolicyProjectionResponse(BaseModel):
    project_id: str = Field(serialization_alias="projectId")
    active_policy_id: str | None = Field(default=None, serialization_alias="activePolicyId")
    active_policy_family_id: str | None = Field(
        default=None,
        serialization_alias="activePolicyFamilyId",
    )
    updated_at: datetime = Field(serialization_alias="updatedAt")


class ActivePolicyResponse(BaseModel):
    projection: PolicyProjectionResponse | None
    policy: PolicyResponse | None


class PolicyEventResponse(BaseModel):
    id: str
    policy_id: str = Field(serialization_alias="policyId")
    event_type: PolicyEventTypeLiteral = Field(serialization_alias="eventType")
    actor_user_id: str | None = Field(default=None, serialization_alias="actorUserId")
    reason: str | None = None
    rules_sha256: str = Field(serialization_alias="rulesSha256")
    rules_snapshot_key: str = Field(serialization_alias="rulesSnapshotKey")
    created_at: datetime = Field(serialization_alias="createdAt")


class PolicyEventsResponse(BaseModel):
    items: list[PolicyEventResponse]


class PolicyValidationResponse(BaseModel):
    policy: PolicyResponse
    issues: list[str]


class PolicyCompareDifferenceResponse(BaseModel):
    path: str
    before: object | None
    after: object | None


class PolicyCompareResponse(BaseModel):
    source_policy: PolicyResponse = Field(serialization_alias="sourcePolicy")
    target_kind: PolicyCompareTargetKindLiteral = Field(serialization_alias="targetKind")
    target_policy: PolicyResponse | None = Field(
        default=None,
        serialization_alias="targetPolicy",
    )
    target_baseline_snapshot_id: str | None = Field(
        default=None,
        serialization_alias="targetBaselineSnapshotId",
    )
    source_rules_sha256: str = Field(serialization_alias="sourceRulesSha256")
    target_rules_sha256: str = Field(serialization_alias="targetRulesSha256")
    difference_count: int = Field(serialization_alias="differenceCount")
    differences: list[PolicyCompareDifferenceResponse]


class PolicyLineageResponse(BaseModel):
    policy: PolicyResponse
    projection: PolicyProjectionResponse | None
    active_policy_differs: bool = Field(serialization_alias="activePolicyDiffers")
    seeded_baseline_snapshot_id: str | None = Field(
        default=None,
        serialization_alias="seededBaselineSnapshotId",
    )
    lineage: list[PolicyResponse]
    events: list[PolicyEventResponse]
    validation_events: list[PolicyEventResponse] = Field(
        serialization_alias="validationEvents"
    )
    activation_events: list[PolicyEventResponse] = Field(
        serialization_alias="activationEvents"
    )
    retirement_events: list[PolicyEventResponse] = Field(
        serialization_alias="retirementEvents"
    )


class PolicyUsageRunResponse(BaseModel):
    run_id: str = Field(serialization_alias="runId")
    project_id: str = Field(serialization_alias="projectId")
    document_id: str = Field(serialization_alias="documentId")
    run_kind: str = Field(serialization_alias="runKind")
    run_status: str = Field(serialization_alias="runStatus")
    supersedes_redaction_run_id: str | None = Field(
        default=None,
        serialization_alias="supersedesRedactionRunId",
    )
    policy_family_id: str | None = Field(default=None, serialization_alias="policyFamilyId")
    policy_version: str | None = Field(default=None, serialization_alias="policyVersion")
    run_created_at: datetime = Field(serialization_alias="runCreatedAt")
    run_finished_at: datetime | None = Field(default=None, serialization_alias="runFinishedAt")
    governance_readiness_status: str | None = Field(
        default=None,
        serialization_alias="governanceReadinessStatus",
    )
    governance_generation_status: str | None = Field(
        default=None,
        serialization_alias="governanceGenerationStatus",
    )
    governance_manifest_id: str | None = Field(
        default=None,
        serialization_alias="governanceManifestId",
    )
    governance_ledger_id: str | None = Field(
        default=None,
        serialization_alias="governanceLedgerId",
    )
    governance_manifest_sha256: str | None = Field(
        default=None,
        serialization_alias="governanceManifestSha256",
    )
    governance_ledger_sha256: str | None = Field(
        default=None,
        serialization_alias="governanceLedgerSha256",
    )
    governance_ledger_verification_status: str | None = Field(
        default=None,
        serialization_alias="governanceLedgerVerificationStatus",
    )


class PolicyUsageManifestResponse(BaseModel):
    id: str
    run_id: str = Field(serialization_alias="runId")
    project_id: str = Field(serialization_alias="projectId")
    document_id: str = Field(serialization_alias="documentId")
    status: str
    attempt_number: int = Field(serialization_alias="attemptNumber")
    manifest_sha256: str | None = Field(default=None, serialization_alias="manifestSha256")
    source_review_snapshot_sha256: str = Field(
        serialization_alias="sourceReviewSnapshotSha256"
    )
    created_at: datetime = Field(serialization_alias="createdAt")


class PolicyUsageLedgerResponse(BaseModel):
    id: str
    run_id: str = Field(serialization_alias="runId")
    project_id: str = Field(serialization_alias="projectId")
    document_id: str = Field(serialization_alias="documentId")
    status: str
    attempt_number: int = Field(serialization_alias="attemptNumber")
    ledger_sha256: str | None = Field(default=None, serialization_alias="ledgerSha256")
    source_review_snapshot_sha256: str = Field(
        serialization_alias="sourceReviewSnapshotSha256"
    )
    created_at: datetime = Field(serialization_alias="createdAt")


class PolicyUsagePseudonymSummaryResponse(BaseModel):
    total_entries: int = Field(serialization_alias="totalEntries")
    active_entries: int = Field(serialization_alias="activeEntries")
    retired_entries: int = Field(serialization_alias="retiredEntries")
    alias_strategy_versions: list[str] = Field(serialization_alias="aliasStrategyVersions")
    salt_version_refs: list[str] = Field(serialization_alias="saltVersionRefs")


class PolicyUsageResponse(BaseModel):
    policy: PolicyResponse
    runs: list[PolicyUsageRunResponse]
    manifests: list[PolicyUsageManifestResponse]
    ledgers: list[PolicyUsageLedgerResponse]
    pseudonym_summary: PolicyUsagePseudonymSummaryResponse = Field(
        serialization_alias="pseudonymSummary"
    )


class PolicyExplainabilityCategoryRuleResponse(BaseModel):
    id: str
    action: str
    review_required_below: float | None = Field(
        default=None,
        serialization_alias="reviewRequiredBelow",
    )
    auto_apply_above: float | None = Field(
        default=None,
        serialization_alias="autoApplyAbove",
    )
    confidence_threshold: float | None = Field(
        default=None,
        serialization_alias="confidenceThreshold",
    )
    requires_reviewer: bool = Field(serialization_alias="requiresReviewer")
    escalation_flags: list[str] = Field(serialization_alias="escalationFlags")


class PolicyExplainabilityTraceResponse(BaseModel):
    category_id: str = Field(serialization_alias="categoryId")
    sample_confidence: float = Field(serialization_alias="sampleConfidence")
    selected_action: str = Field(serialization_alias="selectedAction")
    outcome: str
    rationale: str


class PolicyExplainabilityResponse(BaseModel):
    policy: PolicyResponse
    rules_sha256: str = Field(serialization_alias="rulesSha256")
    category_rules: list[PolicyExplainabilityCategoryRuleResponse] = Field(
        serialization_alias="categoryRules"
    )
    defaults: dict[str, object]
    reviewer_requirements: bool | dict[str, object] | None = Field(
        default=None,
        serialization_alias="reviewerRequirements",
    )
    escalation_flags: bool | dict[str, object] | None = Field(
        default=None,
        serialization_alias="escalationFlags",
    )
    pseudonymisation: dict[str, object] | None = None
    generalisation: dict[str, object] | list[object] | None = None
    reviewer_explanation_mode: str | None = Field(
        default=None,
        serialization_alias="reviewerExplanationMode",
    )
    deterministic_traces: list[PolicyExplainabilityTraceResponse] = Field(
        serialization_alias="deterministicTraces"
    )


class PolicySnapshotResponse(BaseModel):
    policy: PolicyResponse
    event: PolicyEventResponse
    rules_sha256: str = Field(serialization_alias="rulesSha256")
    rules_snapshot_key: str = Field(serialization_alias="rulesSnapshotKey")
    rules_json: dict[str, object] = Field(serialization_alias="rulesJson")
    snapshot_created_at: datetime = Field(serialization_alias="snapshotCreatedAt")


class CreatePolicyRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str = Field(min_length=3, max_length=180)
    rules_json: dict[str, object] = Field(alias="rulesJson", serialization_alias="rulesJson")
    seeded_from_baseline_snapshot_id: str | None = Field(
        default=None,
        alias="seededFromBaselineSnapshotId",
        serialization_alias="seededFromBaselineSnapshotId",
    )
    supersedes_policy_id: str | None = Field(
        default=None,
        alias="supersedesPolicyId",
        serialization_alias="supersedesPolicyId",
    )
    reason: str | None = Field(default=None, max_length=800)


class UpdatePolicyRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    version_etag: str = Field(
        alias="versionEtag",
        serialization_alias="versionEtag",
        min_length=1,
        max_length=200,
    )
    name: str | None = Field(default=None, min_length=3, max_length=180)
    rules_json: dict[str, object] | None = Field(
        default=None,
        alias="rulesJson",
        serialization_alias="rulesJson",
    )
    reason: str | None = Field(default=None, max_length=800)


class PolicyReasonRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    reason: str | None = Field(default=None, max_length=800)


def _as_policy_response(record: RedactionPolicyRecord) -> PolicyResponse:
    return PolicyResponse(
        id=record.id,
        project_id=record.project_id,
        policy_family_id=record.policy_family_id,
        name=record.name,
        version=record.version,
        seeded_from_baseline_snapshot_id=record.seeded_from_baseline_snapshot_id,
        supersedes_policy_id=record.supersedes_policy_id,
        superseded_by_policy_id=record.superseded_by_policy_id,
        rules_json=record.rules_json,
        version_etag=record.version_etag,
        status=record.status,
        created_by=record.created_by,
        created_at=record.created_at,
        activated_by=record.activated_by,
        activated_at=record.activated_at,
        retired_by=record.retired_by,
        retired_at=record.retired_at,
        validation_status=record.validation_status,
        validated_rules_sha256=record.validated_rules_sha256,
        last_validated_by=record.last_validated_by,
        last_validated_at=record.last_validated_at,
    )


def _as_projection_response(record: ProjectPolicyProjectionRecord) -> PolicyProjectionResponse:
    return PolicyProjectionResponse(
        project_id=record.project_id,
        active_policy_id=record.active_policy_id,
        active_policy_family_id=record.active_policy_family_id,
        updated_at=record.updated_at,
    )


def _as_event_response(record: PolicyEventRecord) -> PolicyEventResponse:
    return PolicyEventResponse(
        id=record.id,
        policy_id=record.policy_id,
        event_type=record.event_type,
        actor_user_id=record.actor_user_id,
        reason=record.reason,
        rules_sha256=record.rules_sha256,
        rules_snapshot_key=record.rules_snapshot_key,
        created_at=record.created_at,
    )


def _as_active_policy_response(view: ActiveProjectPolicyView) -> ActivePolicyResponse:
    return ActivePolicyResponse(
        projection=(
            _as_projection_response(view.projection)
            if view.projection is not None
            else None
        ),
        policy=_as_policy_response(view.policy) if view.policy is not None else None,
    )


def _as_validation_response(result: PolicyValidationResult) -> PolicyValidationResponse:
    return PolicyValidationResponse(
        policy=_as_policy_response(result.policy),
        issues=list(result.issues),
    )


def _as_compare_response(result: PolicyCompareResult) -> PolicyCompareResponse:
    return PolicyCompareResponse(
        source_policy=_as_policy_response(result.source_policy),
        target_kind=result.target_kind,
        target_policy=(
            _as_policy_response(result.target_policy)
            if result.target_policy is not None
            else None
        ),
        target_baseline_snapshot_id=result.target_baseline_snapshot_id,
        source_rules_sha256=result.source_rules_sha256,
        target_rules_sha256=result.target_rules_sha256,
        difference_count=len(result.differences),
        differences=[
            PolicyCompareDifferenceResponse(
                path=difference.path,
                before=difference.before,
                after=difference.after,
            )
            for difference in result.differences
        ],
    )


def _as_lineage_response(snapshot: PolicyLineageSnapshot) -> PolicyLineageResponse:
    validation_event_types = {"POLICY_VALIDATED_VALID", "POLICY_VALIDATED_INVALID"}
    activation_event_types = {"POLICY_ACTIVATED"}
    retirement_event_types = {"POLICY_RETIRED"}
    events = [_as_event_response(event) for event in snapshot.events]
    return PolicyLineageResponse(
        policy=_as_policy_response(snapshot.policy),
        projection=(
            _as_projection_response(snapshot.projection)
            if snapshot.projection is not None
            else None
        ),
        active_policy_differs=snapshot.active_policy_differs,
        seeded_baseline_snapshot_id=snapshot.policy.seeded_from_baseline_snapshot_id,
        lineage=[_as_policy_response(item) for item in snapshot.lineage],
        events=events,
        validation_events=[
            _as_event_response(item)
            for item in snapshot.events
            if item.event_type in validation_event_types
        ],
        activation_events=[
            _as_event_response(item)
            for item in snapshot.events
            if item.event_type in activation_event_types
        ],
        retirement_events=[
            _as_event_response(item)
            for item in snapshot.events
            if item.event_type in retirement_event_types
        ],
    )


def _as_usage_response(snapshot: PolicyUsageSnapshot) -> PolicyUsageResponse:
    return PolicyUsageResponse(
        policy=_as_policy_response(snapshot.policy),
        runs=[
            PolicyUsageRunResponse(
                run_id=item.run_id,
                project_id=item.project_id,
                document_id=item.document_id,
                run_kind=item.run_kind,
                run_status=item.run_status,
                supersedes_redaction_run_id=item.supersedes_redaction_run_id,
                policy_family_id=item.policy_family_id,
                policy_version=item.policy_version,
                run_created_at=item.run_created_at,
                run_finished_at=item.run_finished_at,
                governance_readiness_status=item.governance_readiness_status,
                governance_generation_status=item.governance_generation_status,
                governance_manifest_id=item.governance_manifest_id,
                governance_ledger_id=item.governance_ledger_id,
                governance_manifest_sha256=item.governance_manifest_sha256,
                governance_ledger_sha256=item.governance_ledger_sha256,
                governance_ledger_verification_status=item.governance_ledger_verification_status,
            )
            for item in snapshot.runs
        ],
        manifests=[
            PolicyUsageManifestResponse(
                id=item.id,
                run_id=item.run_id,
                project_id=item.project_id,
                document_id=item.document_id,
                status=item.status,
                attempt_number=item.attempt_number,
                manifest_sha256=item.manifest_sha256,
                source_review_snapshot_sha256=item.source_review_snapshot_sha256,
                created_at=item.created_at,
            )
            for item in snapshot.manifests
        ],
        ledgers=[
            PolicyUsageLedgerResponse(
                id=item.id,
                run_id=item.run_id,
                project_id=item.project_id,
                document_id=item.document_id,
                status=item.status,
                attempt_number=item.attempt_number,
                ledger_sha256=item.ledger_sha256,
                source_review_snapshot_sha256=item.source_review_snapshot_sha256,
                created_at=item.created_at,
            )
            for item in snapshot.ledgers
        ],
        pseudonym_summary=PolicyUsagePseudonymSummaryResponse(
            total_entries=snapshot.pseudonym_summary.total_entries,
            active_entries=snapshot.pseudonym_summary.active_entries,
            retired_entries=snapshot.pseudonym_summary.retired_entries,
            alias_strategy_versions=list(snapshot.pseudonym_summary.alias_strategy_versions),
            salt_version_refs=list(snapshot.pseudonym_summary.salt_version_refs),
        ),
    )


def _as_explainability_response(
    snapshot: PolicyExplainabilitySnapshot,
) -> PolicyExplainabilityResponse:
    generalisation_payload: dict[str, object] | list[object] | None
    if isinstance(snapshot.generalisation, tuple):
        generalisation_payload = list(snapshot.generalisation)
    else:
        generalisation_payload = snapshot.generalisation
    return PolicyExplainabilityResponse(
        policy=_as_policy_response(snapshot.policy),
        rules_sha256=snapshot.rules_sha256,
        category_rules=[
            PolicyExplainabilityCategoryRuleResponse(
                id=item.id,
                action=item.action,
                review_required_below=item.review_required_below,
                auto_apply_above=item.auto_apply_above,
                confidence_threshold=item.confidence_threshold,
                requires_reviewer=item.requires_reviewer,
                escalation_flags=list(item.escalation_flags),
            )
            for item in snapshot.category_rules
        ],
        defaults=snapshot.defaults,
        reviewer_requirements=snapshot.reviewer_requirements,
        escalation_flags=snapshot.escalation_flags,
        pseudonymisation=snapshot.pseudonymisation,
        generalisation=generalisation_payload,
        reviewer_explanation_mode=snapshot.reviewer_explanation_mode,
        deterministic_traces=[
            PolicyExplainabilityTraceResponse(
                category_id=item.category_id,
                sample_confidence=item.sample_confidence,
                selected_action=item.selected_action,
                outcome=item.outcome,
                rationale=item.rationale,
            )
            for item in snapshot.deterministic_traces
        ],
    )


def _as_snapshot_response(snapshot: PolicySnapshotView) -> PolicySnapshotResponse:
    return PolicySnapshotResponse(
        policy=_as_policy_response(snapshot.policy),
        event=_as_event_response(snapshot.event),
        rules_sha256=snapshot.snapshot.rules_sha256,
        rules_snapshot_key=snapshot.snapshot.rules_snapshot_key,
        rules_json=snapshot.snapshot.rules_json,
        snapshot_created_at=snapshot.snapshot.created_at,
    )


def _record_audit_event(
    *,
    audit_service: AuditService,
    request_context: AuditRequestContext,
    event_type: AuditEventType,
    actor_user_id: str,
    project_id: str,
    object_type: str | None = None,
    object_id: str | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    audit_service.record_event_best_effort(
        event_type=event_type,
        actor_user_id=actor_user_id,
        project_id=project_id,
        object_type=object_type,
        object_id=object_id,
        metadata=metadata,
        request_context=request_context,
    )


def _handle_policy_exception(
    *,
    error: Exception,
) -> HTTPException:
    if isinstance(error, PolicyAccessDeniedError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error))
    if isinstance(error, PolicyNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, PolicyConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, (PolicyValidationError, PolicyComparisonError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        )
    if isinstance(error, PolicyStoreUnavailableError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Policy store is unavailable.",
        )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unexpected policy failure.",
    )


@router.get("", response_model=PolicyListResponse)
def list_project_policies(
    project_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    policy_service: PolicyService = Depends(get_policy_service),
) -> PolicyListResponse:
    try:
        rows = policy_service.list_policies(
            current_user=current_user,
            project_id=project_id,
        )
    except Exception as error:  # pragma: no cover - exercised via typed branches below
        if isinstance(error, PolicyAccessDeniedError):
            _record_audit_event(
                audit_service=audit_service,
                request_context=request_context,
                event_type="ACCESS_DENIED",
                actor_user_id=current_user.user_id,
                project_id=project_id,
                metadata={
                    "route": request_context.route_template,
                    "required_roles": [
                        "PROJECT_LEAD",
                        "REVIEWER",
                        "ADMIN",
                        "AUDITOR",
                    ],
                    "status_code": status.HTTP_403_FORBIDDEN,
                },
            )
        raise _handle_policy_exception(error=error) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="POLICY_LIST_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        metadata={
            "route": request_context.route_template,
            "returned_count": len(rows),
        },
    )
    return PolicyListResponse(items=[_as_policy_response(row) for row in rows])


@router.get("/active", response_model=ActivePolicyResponse)
def get_project_active_policy(
    project_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    policy_service: PolicyService = Depends(get_policy_service),
) -> ActivePolicyResponse:
    try:
        view = policy_service.get_active_policy(
            current_user=current_user,
            project_id=project_id,
        )
    except Exception as error:  # pragma: no cover - exercised via typed branches below
        if isinstance(error, PolicyAccessDeniedError):
            _record_audit_event(
                audit_service=audit_service,
                request_context=request_context,
                event_type="ACCESS_DENIED",
                actor_user_id=current_user.user_id,
                project_id=project_id,
                metadata={
                    "route": request_context.route_template,
                    "required_roles": [
                        "PROJECT_LEAD",
                        "REVIEWER",
                        "ADMIN",
                        "AUDITOR",
                    ],
                    "status_code": status.HTTP_403_FORBIDDEN,
                },
            )
        raise _handle_policy_exception(error=error) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="POLICY_ACTIVE_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_policy",
        object_id=view.policy.id if view.policy is not None else None,
        metadata={
            "route": request_context.route_template,
            "active_policy_id": view.policy.id if view.policy is not None else "",
        },
    )
    return _as_active_policy_response(view)


@router.post("", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
def create_project_policy(
    project_id: str,
    payload: CreatePolicyRequest,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    policy_service: PolicyService = Depends(get_policy_service),
) -> PolicyResponse:
    try:
        row = policy_service.create_policy(
            current_user=current_user,
            project_id=project_id,
            name=payload.name,
            rules_json=payload.rules_json,
            seeded_from_baseline_snapshot_id=payload.seeded_from_baseline_snapshot_id,
            supersedes_policy_id=payload.supersedes_policy_id,
            reason=payload.reason,
        )
    except Exception as error:  # pragma: no cover
        if isinstance(error, PolicyAccessDeniedError):
            _record_audit_event(
                audit_service=audit_service,
                request_context=request_context,
                event_type="ACCESS_DENIED",
                actor_user_id=current_user.user_id,
                project_id=project_id,
                metadata={
                    "route": request_context.route_template,
                    "required_roles": ["PROJECT_LEAD", "ADMIN"],
                    "status_code": status.HTTP_403_FORBIDDEN,
                },
            )
        raise _handle_policy_exception(error=error) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="POLICY_CREATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_policy",
        object_id=row.id,
        metadata={
            "route": request_context.route_template,
            "policy_id": row.id,
            "policy_family_id": row.policy_family_id,
            "policy_version": row.version,
            "status": row.status,
        },
    )
    return _as_policy_response(row)


@router.get("/{policy_id}", response_model=PolicyResponse)
def get_project_policy(
    project_id: str,
    policy_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    policy_service: PolicyService = Depends(get_policy_service),
) -> PolicyResponse:
    try:
        row = policy_service.get_policy(
            current_user=current_user,
            project_id=project_id,
            policy_id=policy_id,
        )
    except Exception as error:  # pragma: no cover
        if isinstance(error, PolicyAccessDeniedError):
            _record_audit_event(
                audit_service=audit_service,
                request_context=request_context,
                event_type="ACCESS_DENIED",
                actor_user_id=current_user.user_id,
                project_id=project_id,
                metadata={
                    "route": request_context.route_template,
                    "required_roles": [
                        "PROJECT_LEAD",
                        "REVIEWER",
                        "ADMIN",
                        "AUDITOR",
                    ],
                    "status_code": status.HTTP_403_FORBIDDEN,
                },
            )
        raise _handle_policy_exception(error=error) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="POLICY_DETAIL_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_policy",
        object_id=row.id,
        metadata={
            "route": request_context.route_template,
            "policy_id": row.id,
        },
    )
    return _as_policy_response(row)


@router.get("/{policy_id}/events", response_model=PolicyEventsResponse)
def list_project_policy_events(
    project_id: str,
    policy_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    policy_service: PolicyService = Depends(get_policy_service),
) -> PolicyEventsResponse:
    try:
        rows = policy_service.list_policy_events(
            current_user=current_user,
            project_id=project_id,
            policy_id=policy_id,
        )
    except Exception as error:  # pragma: no cover
        if isinstance(error, PolicyAccessDeniedError):
            _record_audit_event(
                audit_service=audit_service,
                request_context=request_context,
                event_type="ACCESS_DENIED",
                actor_user_id=current_user.user_id,
                project_id=project_id,
                metadata={
                    "route": request_context.route_template,
                    "required_roles": [
                        "PROJECT_LEAD",
                        "REVIEWER",
                        "ADMIN",
                        "AUDITOR",
                    ],
                    "status_code": status.HTTP_403_FORBIDDEN,
                },
            )
        raise _handle_policy_exception(error=error) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="POLICY_EVENTS_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_policy",
        object_id=policy_id,
        metadata={
            "route": request_context.route_template,
            "policy_id": policy_id,
            "returned_count": len(rows),
        },
    )
    return PolicyEventsResponse(items=[_as_event_response(row) for row in rows])


@router.get("/{policy_id}/lineage", response_model=PolicyLineageResponse)
def get_project_policy_lineage(
    project_id: str,
    policy_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    policy_service: PolicyService = Depends(get_policy_service),
) -> PolicyLineageResponse:
    try:
        snapshot = policy_service.get_policy_lineage(
            current_user=current_user,
            project_id=project_id,
            policy_id=policy_id,
        )
    except Exception as error:  # pragma: no cover
        if isinstance(error, PolicyAccessDeniedError):
            _record_audit_event(
                audit_service=audit_service,
                request_context=request_context,
                event_type="ACCESS_DENIED",
                actor_user_id=current_user.user_id,
                project_id=project_id,
                metadata={
                    "route": request_context.route_template,
                    "required_roles": [
                        "PROJECT_LEAD",
                        "REVIEWER",
                        "ADMIN",
                        "AUDITOR",
                    ],
                    "status_code": status.HTTP_403_FORBIDDEN,
                },
            )
        raise _handle_policy_exception(error=error) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="POLICY_LINEAGE_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_policy",
        object_id=policy_id,
        metadata={
            "route": request_context.route_template,
            "policy_id": policy_id,
            "lineage_count": len(snapshot.lineage),
            "event_count": len(snapshot.events),
            "active_policy_differs": snapshot.active_policy_differs,
        },
    )
    return _as_lineage_response(snapshot)


@router.get("/{policy_id}/usage", response_model=PolicyUsageResponse)
def get_project_policy_usage(
    project_id: str,
    policy_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    policy_service: PolicyService = Depends(get_policy_service),
) -> PolicyUsageResponse:
    try:
        snapshot = policy_service.get_policy_usage(
            current_user=current_user,
            project_id=project_id,
            policy_id=policy_id,
        )
    except Exception as error:  # pragma: no cover
        if isinstance(error, PolicyAccessDeniedError):
            _record_audit_event(
                audit_service=audit_service,
                request_context=request_context,
                event_type="ACCESS_DENIED",
                actor_user_id=current_user.user_id,
                project_id=project_id,
                metadata={
                    "route": request_context.route_template,
                    "required_roles": [
                        "PROJECT_LEAD",
                        "REVIEWER",
                        "ADMIN",
                        "AUDITOR",
                    ],
                    "status_code": status.HTTP_403_FORBIDDEN,
                },
            )
        raise _handle_policy_exception(error=error) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="POLICY_USAGE_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_policy",
        object_id=policy_id,
        metadata={
            "route": request_context.route_template,
            "policy_id": policy_id,
            "run_count": len(snapshot.runs),
            "manifest_count": len(snapshot.manifests),
            "ledger_count": len(snapshot.ledgers),
            "pseudonym_entry_count": snapshot.pseudonym_summary.total_entries,
        },
    )
    return _as_usage_response(snapshot)


@router.get("/{policy_id}/explainability", response_model=PolicyExplainabilityResponse)
def get_project_policy_explainability(
    project_id: str,
    policy_id: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    policy_service: PolicyService = Depends(get_policy_service),
) -> PolicyExplainabilityResponse:
    try:
        snapshot = policy_service.get_policy_explainability(
            current_user=current_user,
            project_id=project_id,
            policy_id=policy_id,
        )
    except Exception as error:  # pragma: no cover
        if isinstance(error, PolicyAccessDeniedError):
            _record_audit_event(
                audit_service=audit_service,
                request_context=request_context,
                event_type="ACCESS_DENIED",
                actor_user_id=current_user.user_id,
                project_id=project_id,
                metadata={
                    "route": request_context.route_template,
                    "required_roles": [
                        "PROJECT_LEAD",
                        "REVIEWER",
                        "ADMIN",
                        "AUDITOR",
                    ],
                    "status_code": status.HTTP_403_FORBIDDEN,
                },
            )
        raise _handle_policy_exception(error=error) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="POLICY_EXPLAINABILITY_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_policy",
        object_id=policy_id,
        metadata={
            "route": request_context.route_template,
            "policy_id": policy_id,
            "category_rule_count": len(snapshot.category_rules),
            "trace_count": len(snapshot.deterministic_traces),
            "reviewer_explanation_mode": snapshot.reviewer_explanation_mode or "",
        },
    )
    return _as_explainability_response(snapshot)


@router.get(
    "/{policy_id}/snapshots/{rules_sha256}",
    response_model=PolicySnapshotResponse,
)
def get_project_policy_snapshot(
    project_id: str,
    policy_id: str,
    rules_sha256: str,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    policy_service: PolicyService = Depends(get_policy_service),
) -> PolicySnapshotResponse:
    try:
        snapshot = policy_service.get_policy_snapshot(
            current_user=current_user,
            project_id=project_id,
            policy_id=policy_id,
            rules_sha256=rules_sha256,
        )
    except Exception as error:  # pragma: no cover
        if isinstance(error, PolicyAccessDeniedError):
            _record_audit_event(
                audit_service=audit_service,
                request_context=request_context,
                event_type="ACCESS_DENIED",
                actor_user_id=current_user.user_id,
                project_id=project_id,
                metadata={
                    "route": request_context.route_template,
                    "required_roles": [
                        "PROJECT_LEAD",
                        "REVIEWER",
                        "ADMIN",
                        "AUDITOR",
                    ],
                    "status_code": status.HTTP_403_FORBIDDEN,
                },
            )
        raise _handle_policy_exception(error=error) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="POLICY_SNAPSHOT_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_policy",
        object_id=policy_id,
        metadata={
            "route": request_context.route_template,
            "policy_id": policy_id,
            "rules_sha256": snapshot.snapshot.rules_sha256,
            "rules_snapshot_key": snapshot.snapshot.rules_snapshot_key,
            "source_event_type": snapshot.event.event_type,
        },
    )
    return _as_snapshot_response(snapshot)


@router.patch("/{policy_id}", response_model=PolicyResponse)
def patch_project_policy(
    project_id: str,
    policy_id: str,
    payload: UpdatePolicyRequest,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    policy_service: PolicyService = Depends(get_policy_service),
) -> PolicyResponse:
    try:
        row = policy_service.update_policy(
            current_user=current_user,
            project_id=project_id,
            policy_id=policy_id,
            expected_version_etag=payload.version_etag,
            name=payload.name,
            rules_json=payload.rules_json,
            reason=payload.reason,
        )
    except Exception as error:  # pragma: no cover
        if isinstance(error, PolicyAccessDeniedError):
            _record_audit_event(
                audit_service=audit_service,
                request_context=request_context,
                event_type="ACCESS_DENIED",
                actor_user_id=current_user.user_id,
                project_id=project_id,
                metadata={
                    "route": request_context.route_template,
                    "required_roles": ["PROJECT_LEAD", "ADMIN"],
                    "status_code": status.HTTP_403_FORBIDDEN,
                },
            )
        raise _handle_policy_exception(error=error) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="POLICY_UPDATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_policy",
        object_id=row.id,
        metadata={
            "route": request_context.route_template,
            "policy_id": row.id,
            "policy_version": row.version,
            "version_etag": row.version_etag,
        },
    )
    return _as_policy_response(row)


@router.get("/{policy_id}/compare", response_model=PolicyCompareResponse)
def compare_project_policy(
    project_id: str,
    policy_id: str,
    against: str | None = Query(default=None),
    against_baseline_snapshot_id: str | None = Query(
        default=None,
        alias="againstBaselineSnapshotId",
    ),
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    policy_service: PolicyService = Depends(get_policy_service),
) -> PolicyCompareResponse:
    try:
        comparison = policy_service.compare_policy(
            current_user=current_user,
            project_id=project_id,
            policy_id=policy_id,
            against_policy_id=against,
            against_baseline_snapshot_id=against_baseline_snapshot_id,
        )
    except Exception as error:  # pragma: no cover
        if isinstance(error, PolicyAccessDeniedError):
            _record_audit_event(
                audit_service=audit_service,
                request_context=request_context,
                event_type="ACCESS_DENIED",
                actor_user_id=current_user.user_id,
                project_id=project_id,
                metadata={
                    "route": request_context.route_template,
                    "required_roles": [
                        "PROJECT_LEAD",
                        "REVIEWER",
                        "ADMIN",
                        "AUDITOR",
                    ],
                    "status_code": status.HTTP_403_FORBIDDEN,
                },
            )
        raise _handle_policy_exception(error=error) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="POLICY_COMPARE_VIEWED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_policy",
        object_id=policy_id,
        metadata={
            "route": request_context.route_template,
            "policy_id": policy_id,
            "against_policy_id": against or "",
            "against_baseline_snapshot_id": against_baseline_snapshot_id or "",
            "difference_count": len(comparison.differences),
        },
    )
    return _as_compare_response(comparison)


@router.post(
    "/{policy_id}/rollback-draft",
    response_model=PolicyResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_policy_rollback_draft(
    project_id: str,
    policy_id: str,
    from_policy_id: str = Query(alias="fromPolicyId", min_length=1, max_length=160),
    payload: PolicyReasonRequest | None = None,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    policy_service: PolicyService = Depends(get_policy_service),
) -> PolicyResponse:
    reason = payload.reason if payload is not None else None
    try:
        rollback = policy_service.create_rollback_draft(
            current_user=current_user,
            project_id=project_id,
            policy_id=policy_id,
            from_policy_id=from_policy_id,
            reason=reason,
        )
    except Exception as error:  # pragma: no cover
        if isinstance(error, PolicyAccessDeniedError):
            _record_audit_event(
                audit_service=audit_service,
                request_context=request_context,
                event_type="ACCESS_DENIED",
                actor_user_id=current_user.user_id,
                project_id=project_id,
                metadata={
                    "route": request_context.route_template,
                    "required_roles": ["PROJECT_LEAD", "ADMIN"],
                    "status_code": status.HTTP_403_FORBIDDEN,
                },
            )
        raise _handle_policy_exception(error=error) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="POLICY_CREATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_policy",
        object_id=rollback.id,
        metadata={
            "route": request_context.route_template,
            "policy_id": rollback.id,
            "policy_family_id": rollback.policy_family_id,
            "policy_version": rollback.version,
            "status": rollback.status,
            "rollback_anchor_policy_id": policy_id,
            "rollback_from_policy_id": from_policy_id,
        },
    )
    return _as_policy_response(rollback)


@router.post("/{policy_id}/validate", response_model=PolicyValidationResponse)
def validate_project_policy(
    project_id: str,
    policy_id: str,
    payload: PolicyReasonRequest | None = None,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    policy_service: PolicyService = Depends(get_policy_service),
) -> PolicyValidationResponse:
    reason = payload.reason if payload is not None else None
    try:
        result = policy_service.validate_policy(
            current_user=current_user,
            project_id=project_id,
            policy_id=policy_id,
            reason=reason,
        )
    except Exception as error:  # pragma: no cover
        if isinstance(error, PolicyAccessDeniedError):
            _record_audit_event(
                audit_service=audit_service,
                request_context=request_context,
                event_type="ACCESS_DENIED",
                actor_user_id=current_user.user_id,
                project_id=project_id,
                metadata={
                    "route": request_context.route_template,
                    "required_roles": ["PROJECT_LEAD", "ADMIN"],
                    "status_code": status.HTTP_403_FORBIDDEN,
                },
            )
        raise _handle_policy_exception(error=error) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="POLICY_VALIDATION_REQUESTED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_policy",
        object_id=policy_id,
        metadata={
            "route": request_context.route_template,
            "policy_id": policy_id,
            "validation_status": result.policy.validation_status,
            "issue_count": len(result.issues),
        },
    )
    return _as_validation_response(result)


@router.post("/{policy_id}/activate", response_model=PolicyResponse)
def activate_project_policy(
    project_id: str,
    policy_id: str,
    payload: PolicyReasonRequest | None = None,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    policy_service: PolicyService = Depends(get_policy_service),
) -> PolicyResponse:
    reason = payload.reason if payload is not None else None
    try:
        row = policy_service.activate_policy(
            current_user=current_user,
            project_id=project_id,
            policy_id=policy_id,
            reason=reason,
        )
    except Exception as error:  # pragma: no cover
        if isinstance(error, PolicyAccessDeniedError):
            _record_audit_event(
                audit_service=audit_service,
                request_context=request_context,
                event_type="ACCESS_DENIED",
                actor_user_id=current_user.user_id,
                project_id=project_id,
                metadata={
                    "route": request_context.route_template,
                    "required_roles": ["PROJECT_LEAD", "ADMIN"],
                    "status_code": status.HTTP_403_FORBIDDEN,
                },
            )
        raise _handle_policy_exception(error=error) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="POLICY_ACTIVATED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_policy",
        object_id=row.id,
        metadata={
            "route": request_context.route_template,
            "policy_id": row.id,
            "policy_family_id": row.policy_family_id,
            "policy_version": row.version,
            "status": row.status,
        },
    )
    return _as_policy_response(row)


@router.post("/{policy_id}/retire", response_model=PolicyResponse)
def retire_project_policy(
    project_id: str,
    policy_id: str,
    payload: PolicyReasonRequest | None = None,
    current_user: SessionPrincipal = Depends(require_authenticated_user),
    request_context: AuditRequestContext = Depends(get_audit_request_context),
    audit_service: AuditService = Depends(get_audit_service),
    policy_service: PolicyService = Depends(get_policy_service),
) -> PolicyResponse:
    reason = payload.reason if payload is not None else None
    try:
        row = policy_service.retire_policy(
            current_user=current_user,
            project_id=project_id,
            policy_id=policy_id,
            reason=reason,
        )
    except Exception as error:  # pragma: no cover
        if isinstance(error, PolicyAccessDeniedError):
            _record_audit_event(
                audit_service=audit_service,
                request_context=request_context,
                event_type="ACCESS_DENIED",
                actor_user_id=current_user.user_id,
                project_id=project_id,
                metadata={
                    "route": request_context.route_template,
                    "required_roles": ["PROJECT_LEAD", "ADMIN"],
                    "status_code": status.HTTP_403_FORBIDDEN,
                },
            )
        raise _handle_policy_exception(error=error) from error

    _record_audit_event(
        audit_service=audit_service,
        request_context=request_context,
        event_type="POLICY_RETIRED",
        actor_user_id=current_user.user_id,
        project_id=project_id,
        object_type="redaction_policy",
        object_id=row.id,
        metadata={
            "route": request_context.route_template,
            "policy_id": row.id,
            "policy_family_id": row.policy_family_id,
            "policy_version": row.version,
            "status": row.status,
        },
    )
    return _as_policy_response(row)
