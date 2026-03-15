from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.audit.service import get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.main import app
from app.policies.models import (
    ActiveProjectPolicyView,
    PolicyCompareResult,
    PolicyEventRecord,
    PolicyExplainabilityCategoryRule,
    PolicyExplainabilitySnapshot,
    PolicyExplainabilityTrace,
    PolicyLineageSnapshot,
    PolicyRulesDiffItem,
    PolicyRuleSnapshotRecord,
    PolicySnapshotView,
    PolicyUsageLedgerRecord,
    PolicyUsageManifestRecord,
    PolicyUsagePseudonymSummary,
    PolicyUsageRunRecord,
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
    PolicyValidationError,
    get_policy_service,
)
from fastapi.testclient import TestClient

client = TestClient(app)


class SpyAuditService:
    def __init__(self) -> None:
        self.recorded: list[dict[str, object]] = []

    def record_event_best_effort(self, **kwargs):  # type: ignore[no-untyped-def]
        self.recorded.append(kwargs)
        return None


class FakePolicyService:
    def __init__(self) -> None:
        self.project_id = "project-1"
        self.baseline_id = "baseline-phase0-v1"
        self._policies: dict[str, RedactionPolicyRecord] = {}
        self._events: list[PolicyEventRecord] = []
        self._snapshots: list[PolicyRuleSnapshotRecord] = []
        self._projection = ProjectPolicyProjectionRecord(
            project_id=self.project_id,
            active_policy_id=None,
            active_policy_family_id=None,
            updated_at=datetime.now(UTC) - timedelta(minutes=10),
        )
        seeded = self._make_policy(
            name="Seeded policy",
            version=1,
            status="ACTIVE",
            validation_status="VALID",
            rules_json={
                "categories": [
                    {
                        "id": "PERSON_NAME",
                        "action": "MASK",
                        "review_required_below": 0.9,
                    }
                ],
                "defaults": {"auto_apply_confidence_threshold": 0.92},
            },
            seeded_from_baseline_snapshot_id=self.baseline_id,
            activated_by="user-lead",
            activated_at=datetime.now(UTC) - timedelta(days=1),
            validated_rules_sha256=self._rules_hash(
                {
                    "categories": [
                        {
                            "id": "PERSON_NAME",
                            "action": "MASK",
                            "review_required_below": 0.9,
                        }
                    ],
                    "defaults": {"auto_apply_confidence_threshold": 0.92},
                }
            ),
        )
        self._policies[seeded.id] = seeded
        self._projection = replace(
            self._projection,
            active_policy_id=seeded.id,
            active_policy_family_id=seeded.policy_family_id,
            updated_at=seeded.activated_at or seeded.created_at,
        )
        self._append_event(seeded, "POLICY_CREATED", actor_user_id="user-lead", reason=None)
        self._append_event(seeded, "POLICY_ACTIVATED", actor_user_id="user-lead", reason=None)

    @staticmethod
    def _rules_hash(rules_json: dict[str, object]) -> str:
        return hashlib.sha256(
            json.dumps(rules_json, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def _role_for_user(self, current_user: SessionPrincipal) -> str:
        if "ADMIN" in set(current_user.platform_roles):
            return "ADMIN"
        if "AUDITOR" in set(current_user.platform_roles):
            return "AUDITOR"
        if current_user.user_id == "user-lead":
            return "PROJECT_LEAD"
        if current_user.user_id == "user-reviewer":
            return "REVIEWER"
        return "RESEARCHER"

    def _require_project(self, project_id: str) -> None:
        if project_id != self.project_id:
            raise PolicyNotFoundError("Project not found.")

    def _require_read(self, *, current_user: SessionPrincipal, project_id: str) -> None:
        self._require_project(project_id)
        role = self._role_for_user(current_user)
        if role in {"PROJECT_LEAD", "REVIEWER", "ADMIN", "AUDITOR"}:
            return
        raise PolicyAccessDeniedError(
            "Current role cannot view Phase 7 policy routes in this project."
        )

    def _require_mutate(self, *, current_user: SessionPrincipal, project_id: str) -> None:
        self._require_project(project_id)
        role = self._role_for_user(current_user)
        if role in {"PROJECT_LEAD", "ADMIN"}:
            return
        raise PolicyAccessDeniedError(
            "Current role cannot create, edit, validate, activate, retire, or rollback policies."
        )

    def _make_policy(
        self,
        *,
        name: str,
        version: int,
        status: str,
        validation_status: str,
        rules_json: dict[str, object],
        seeded_from_baseline_snapshot_id: str,
        supersedes_policy_id: str | None = None,
        activated_by: str | None = None,
        activated_at: datetime | None = None,
        validated_rules_sha256: str | None = None,
    ) -> RedactionPolicyRecord:
        now = datetime.now(UTC)
        return RedactionPolicyRecord(
            id=f"policy-{uuid4()}",
            project_id=self.project_id,
            policy_family_id="family-main",
            name=name,
            version=version,
            seeded_from_baseline_snapshot_id=seeded_from_baseline_snapshot_id,
            supersedes_policy_id=supersedes_policy_id,
            superseded_by_policy_id=None,
            rules_json=rules_json,
            version_etag=str(uuid4()),
            status=status,  # type: ignore[arg-type]
            created_by="user-lead",
            created_at=now,
            activated_by=activated_by,
            activated_at=activated_at,
            retired_by=None,
            retired_at=None,
            validation_status=validation_status,  # type: ignore[arg-type]
            validated_rules_sha256=validated_rules_sha256,
            last_validated_by="user-lead" if validation_status == "VALID" else None,
            last_validated_at=now if validation_status == "VALID" else None,
        )

    def _append_event(
        self,
        policy: RedactionPolicyRecord,
        event_type: str,
        *,
        actor_user_id: str,
        reason: str | None,
    ) -> None:
        created_at = datetime.now(UTC)
        self._events.append(
            PolicyEventRecord(
                id=str(uuid4()),
                policy_id=policy.id,
                event_type=event_type,  # type: ignore[arg-type]
                actor_user_id=actor_user_id,
                reason=reason,
                rules_sha256=self._rules_hash(policy.rules_json),
                rules_snapshot_key=(
                    f"policies/{policy.project_id}/{policy.policy_family_id}/"
                    f"{policy.id}/{created_at.strftime('%Y%m%dT%H%M%SZ')}.json"
                ),
                created_at=created_at,
            )
        )
        self._snapshots.append(
            PolicyRuleSnapshotRecord(
                policy_id=policy.id,
                rules_sha256=self._rules_hash(policy.rules_json),
                rules_snapshot_key=(
                    f"policies/{policy.project_id}/{policy.policy_family_id}/"
                    f"{policy.id}/{created_at.strftime('%Y%m%dT%H%M%SZ')}.json"
                ),
                rules_json=dict(policy.rules_json),
                created_at=created_at,
            )
        )

    def list_policies(self, *, current_user: SessionPrincipal, project_id: str):
        self._require_read(current_user=current_user, project_id=project_id)
        rows = [row for row in self._policies.values() if row.project_id == project_id]
        return sorted(rows, key=lambda row: (-row.version, row.id))

    def get_active_policy(self, *, current_user: SessionPrincipal, project_id: str):
        self._require_read(current_user=current_user, project_id=project_id)
        active = (
            self._policies.get(self._projection.active_policy_id)
            if self._projection.active_policy_id
            else None
        )
        return ActiveProjectPolicyView(projection=self._projection, policy=active)

    def create_policy(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        name: str,
        rules_json: dict[str, object],
        seeded_from_baseline_snapshot_id: str | None,
        supersedes_policy_id: str | None,
        reason: str | None,
    ):
        self._require_mutate(current_user=current_user, project_id=project_id)
        if not isinstance(rules_json.get("categories"), list):
            raise PolicyValidationError(
                "`categories` must be a non-empty array of category rule objects."
            )
        latest_version = max((row.version for row in self._policies.values()), default=0)
        seeded = seeded_from_baseline_snapshot_id or self.baseline_id
        created = self._make_policy(
            name=name,
            version=latest_version + 1,
            status="DRAFT",
            validation_status="NOT_VALIDATED",
            rules_json=rules_json,
            seeded_from_baseline_snapshot_id=seeded,
            supersedes_policy_id=supersedes_policy_id,
        )
        self._policies[created.id] = created
        self._append_event(
            created,
            "POLICY_CREATED",
            actor_user_id=current_user.user_id,
            reason=reason,
        )
        return created

    def create_rollback_draft(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        policy_id: str,
        from_policy_id: str,
        reason: str | None,
    ):
        self._require_mutate(current_user=current_user, project_id=project_id)
        anchor = self._policies.get(policy_id)
        if anchor is None:
            raise PolicyNotFoundError("Policy revision not found.")
        source = self._policies.get(from_policy_id)
        if source is None:
            raise PolicyNotFoundError("Rollback source policy revision not found.")
        if source.policy_family_id != anchor.policy_family_id:
            raise PolicyConflictError("Rollback source must belong to the same policy lineage.")
        if source.version >= anchor.version:
            raise PolicyConflictError("Rollback source must reference a prior policy revision.")
        if source.validation_status != "VALID":
            raise PolicyConflictError("Rollback source must be a VALID policy revision.")
        if source.validated_rules_sha256 != self._rules_hash(source.rules_json):
            raise PolicyConflictError(
                "Rollback source validation hash does not match current rules_json."
            )

        latest = max(
            (
                row
                for row in self._policies.values()
                if row.project_id == project_id and row.policy_family_id == anchor.policy_family_id
            ),
            key=lambda row: row.version,
        )
        created = self._make_policy(
            name=f"{anchor.name} rollback v{source.version}",
            version=latest.version + 1,
            status="DRAFT",
            validation_status="NOT_VALIDATED",
            rules_json=dict(source.rules_json),
            seeded_from_baseline_snapshot_id=anchor.seeded_from_baseline_snapshot_id
            or self.baseline_id,
            supersedes_policy_id=latest.id,
        )
        self._policies[created.id] = created
        self._policies[latest.id] = replace(latest, superseded_by_policy_id=created.id)
        self._append_event(
            created,
            "POLICY_CREATED",
            actor_user_id=current_user.user_id,
            reason=reason,
        )
        return created

    def get_policy(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        policy_id: str,
    ):
        self._require_read(current_user=current_user, project_id=project_id)
        row = self._policies.get(policy_id)
        if row is None:
            raise PolicyNotFoundError("Policy revision not found.")
        return row

    def list_policy_events(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        policy_id: str,
    ):
        _ = self.get_policy(
            current_user=current_user,
            project_id=project_id,
            policy_id=policy_id,
        )
        return [event for event in self._events if event.policy_id == policy_id]

    def get_policy_lineage(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        policy_id: str,
    ) -> PolicyLineageSnapshot:
        policy = self.get_policy(
            current_user=current_user,
            project_id=project_id,
            policy_id=policy_id,
        )
        lineage = sorted(
            [
                row
                for row in self._policies.values()
                if row.project_id == project_id and row.policy_family_id == policy.policy_family_id
            ],
            key=lambda row: (row.version, row.id),
        )
        lineage_events = sorted(
            [
                event
                for event in self._events
                if any(event.policy_id == line.id for line in lineage)
            ],
            key=lambda event: (event.created_at, event.id),
        )
        return PolicyLineageSnapshot(
            policy=policy,
            projection=self._projection,
            lineage=tuple(lineage),
            events=tuple(lineage_events),
            active_policy_differs=self._projection.active_policy_id != policy.id,
        )

    def get_policy_usage(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        policy_id: str,
    ) -> PolicyUsageSnapshot:
        policy = self.get_policy(
            current_user=current_user,
            project_id=project_id,
            policy_id=policy_id,
        )
        now = datetime.now(UTC)
        return PolicyUsageSnapshot(
            policy=policy,
            runs=(
                PolicyUsageRunRecord(
                    run_id="redaction-run-usage-1",
                    project_id=project_id,
                    document_id="doc-usage-1",
                    run_kind="POLICY_RERUN",
                    run_status="SUCCEEDED",
                    supersedes_redaction_run_id="redaction-run-previous",
                    policy_family_id=policy.policy_family_id,
                    policy_version=str(policy.version),
                    run_created_at=now,
                    run_finished_at=now,
                    governance_readiness_status="READY",
                    governance_generation_status="IDLE",
                    governance_manifest_id="manifest-usage-1",
                    governance_ledger_id="ledger-usage-1",
                    governance_manifest_sha256="m" * 64,
                    governance_ledger_sha256="l" * 64,
                    governance_ledger_verification_status="VALID",
                ),
            ),
            manifests=(
                PolicyUsageManifestRecord(
                    id="manifest-usage-1",
                    run_id="redaction-run-usage-1",
                    project_id=project_id,
                    document_id="doc-usage-1",
                    status="SUCCEEDED",
                    attempt_number=1,
                    manifest_sha256="m" * 64,
                    source_review_snapshot_sha256="s" * 64,
                    created_at=now,
                ),
            ),
            ledgers=(
                PolicyUsageLedgerRecord(
                    id="ledger-usage-1",
                    run_id="redaction-run-usage-1",
                    project_id=project_id,
                    document_id="doc-usage-1",
                    status="SUCCEEDED",
                    attempt_number=1,
                    ledger_sha256="l" * 64,
                    source_review_snapshot_sha256="s" * 64,
                    created_at=now,
                ),
            ),
            pseudonym_summary=PolicyUsagePseudonymSummary(
                total_entries=2,
                active_entries=2,
                retired_entries=0,
                alias_strategy_versions=("v1",),
                salt_version_refs=("salt-v1",),
            ),
        )

    def get_policy_explainability(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        policy_id: str,
    ) -> PolicyExplainabilitySnapshot:
        policy = self.get_policy(
            current_user=current_user,
            project_id=project_id,
            policy_id=policy_id,
        )
        rules_hash = self._rules_hash(policy.rules_json)
        category_rules = (
            PolicyExplainabilityCategoryRule(
                id="PERSON_NAME",
                action="MASK",
                review_required_below=0.9,
                auto_apply_above=None,
                confidence_threshold=None,
                requires_reviewer=True,
                escalation_flags=("HIGH_RISK",),
            ),
        )
        traces = (
            PolicyExplainabilityTrace(
                category_id="PERSON_NAME",
                sample_confidence=0.85,
                selected_action="MASK",
                outcome="REVIEW_REQUIRED",
                rationale="Sample confidence 0.85 is below review_required_below 0.90.",
            ),
        )
        return PolicyExplainabilitySnapshot(
            policy=policy,
            rules_sha256=rules_hash,
            category_rules=category_rules,
            defaults={"auto_apply_confidence_threshold": 0.92},
            reviewer_requirements={"dual_review_required": True},
            escalation_flags={"high_risk_categories": ["PERSON_NAME"]},
            pseudonymisation={"mode": "DETERMINISTIC", "aliasing_rules": {"prefix": "ALIAS-"}},
            generalisation={"specificity_ceiling": "district"},
            reviewer_explanation_mode="LOCAL_LLM_RISK_SUMMARY",
            deterministic_traces=traces,
        )

    def get_policy_snapshot(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        policy_id: str,
        rules_sha256: str,
    ) -> PolicySnapshotView:
        policy = self.get_policy(
            current_user=current_user,
            project_id=project_id,
            policy_id=policy_id,
        )
        event = next(
            (
                item
                for item in reversed(self._events)
                if item.policy_id == policy_id and item.rules_sha256 == rules_sha256
            ),
            None,
        )
        if event is None:
            raise PolicyNotFoundError("Policy rule snapshot not found for requested rulesSha256.")
        snapshot = next(
            (
                item
                for item in reversed(self._snapshots)
                if item.policy_id == policy_id and item.rules_sha256 == rules_sha256
            ),
            None,
        )
        if snapshot is None:
            raise PolicyNotFoundError(
                "Policy rule snapshot payload is unavailable for requested rulesSha256."
            )
        return PolicySnapshotView(policy=policy, event=event, snapshot=snapshot)

    def update_policy(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        policy_id: str,
        expected_version_etag: str,
        name: str | None,
        rules_json: dict[str, object] | None,
        reason: str | None,
    ):
        self._require_mutate(current_user=current_user, project_id=project_id)
        row = self._policies.get(policy_id)
        if row is None:
            raise PolicyNotFoundError("Policy revision not found.")
        if row.status != "DRAFT":
            raise PolicyConflictError("Only DRAFT policy revisions may be edited.")
        if row.version_etag != expected_version_etag:
            raise PolicyConflictError("Draft policy update rejected because versionEtag is stale.")
        updated = replace(
            row,
            name=name or row.name,
            rules_json=rules_json or row.rules_json,
            version_etag=str(uuid4()),
            validation_status="NOT_VALIDATED",
            validated_rules_sha256=None,
            last_validated_by=None,
            last_validated_at=None,
        )
        self._policies[policy_id] = updated
        self._append_event(
            updated,
            "POLICY_EDITED",
            actor_user_id=current_user.user_id,
            reason=reason,
        )
        return updated

    def compare_policy(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        policy_id: str,
        against_policy_id: str | None,
        against_baseline_snapshot_id: str | None,
    ):
        source = self.get_policy(
            current_user=current_user,
            project_id=project_id,
            policy_id=policy_id,
        )
        has_policy_target = bool(against_policy_id)
        has_baseline_target = bool(against_baseline_snapshot_id)
        if (has_policy_target and has_baseline_target) or (
            not has_policy_target and not has_baseline_target
        ):
            raise PolicyComparisonError(
                "Provide exactly one comparison target: against or againstBaselineSnapshotId."
            )

        if has_policy_target:
            target = self._policies.get(str(against_policy_id))
            if target is None:
                raise PolicyNotFoundError("Comparison policy revision not found.")
            return PolicyCompareResult(
                source_policy=source,
                target_kind="POLICY",
                target_policy=target,
                target_baseline_snapshot_id=None,
                source_rules_sha256=self._rules_hash(source.rules_json),
                target_rules_sha256=self._rules_hash(target.rules_json),
                differences=tuple(
                    [
                        PolicyRulesDiffItem(
                            path="$.name",
                            before=source.rules_json.get("name"),
                            after=target.rules_json.get("name"),
                        )
                    ]
                    if source.rules_json != target.rules_json
                    else []
                ),
            )

        if source.seeded_from_baseline_snapshot_id != against_baseline_snapshot_id:
            raise PolicyComparisonError(
                "Baseline comparison is allowed only for the lineage's seeded baseline snapshot."
            )
        return PolicyCompareResult(
            source_policy=source,
            target_kind="BASELINE_SNAPSHOT",
            target_policy=None,
            target_baseline_snapshot_id=against_baseline_snapshot_id,
            source_rules_sha256=self._rules_hash(source.rules_json),
            target_rules_sha256="b" * 64,
            differences=(
                PolicyRulesDiffItem(
                    path="$.defaults.auto_apply_confidence_threshold",
                    before=source.rules_json.get("defaults", {}).get(
                        "auto_apply_confidence_threshold"
                    )
                    if isinstance(source.rules_json.get("defaults"), dict)
                    else None,
                    after=0.92,
                ),
            ),
        )

    def validate_policy(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        policy_id: str,
        reason: str | None,
    ):
        self._require_mutate(current_user=current_user, project_id=project_id)
        row = self._policies.get(policy_id)
        if row is None:
            raise PolicyNotFoundError("Policy revision not found.")
        issues: list[str] = []
        if not isinstance(row.rules_json.get("categories"), list):
            issues.append("`categories` must be a non-empty array of category rule objects.")
        validation_status = "VALID" if not issues else "INVALID"
        updated = replace(
            row,
            validation_status=validation_status,
            validated_rules_sha256=(
                self._rules_hash(row.rules_json) if validation_status == "VALID" else None
            ),
            last_validated_by=current_user.user_id,
            last_validated_at=datetime.now(UTC),
        )
        self._policies[policy_id] = updated
        self._append_event(
            updated,
            "POLICY_VALIDATED_VALID" if not issues else "POLICY_VALIDATED_INVALID",
            actor_user_id=current_user.user_id,
            reason=reason,
        )
        return PolicyValidationResult(policy=updated, issues=tuple(issues))

    def activate_policy(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        policy_id: str,
        reason: str | None,
    ):
        self._require_mutate(current_user=current_user, project_id=project_id)
        row = self._policies.get(policy_id)
        if row is None:
            raise PolicyNotFoundError("Policy revision not found.")
        if row.status != "DRAFT":
            raise PolicyConflictError("Only DRAFT policy revisions can be activated.")
        expected_hash = self._rules_hash(row.rules_json)
        if row.validation_status != "VALID" or row.validated_rules_sha256 != expected_hash:
            raise PolicyConflictError("Activation is blocked until validation_status is VALID.")

        for policy in list(self._policies.values()):
            if policy.project_id == project_id and policy.status == "ACTIVE":
                retired = replace(
                    policy,
                    status="RETIRED",
                    retired_by=current_user.user_id,
                    retired_at=datetime.now(UTC),
                )
                self._policies[policy.id] = retired
                self._append_event(
                    retired,
                    "POLICY_RETIRED",
                    actor_user_id=current_user.user_id,
                    reason=reason,
                )

        activated = replace(
            row,
            status="ACTIVE",
            activated_by=current_user.user_id,
            activated_at=datetime.now(UTC),
        )
        self._policies[policy_id] = activated
        self._projection = replace(
            self._projection,
            active_policy_id=activated.id,
            active_policy_family_id=activated.policy_family_id,
            updated_at=datetime.now(UTC),
        )
        self._append_event(
            activated,
            "POLICY_ACTIVATED",
            actor_user_id=current_user.user_id,
            reason=reason,
        )
        return activated

    def retire_policy(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        policy_id: str,
        reason: str | None,
    ):
        self._require_mutate(current_user=current_user, project_id=project_id)
        row = self._policies.get(policy_id)
        if row is None:
            raise PolicyNotFoundError("Policy revision not found.")
        if row.status != "ACTIVE":
            raise PolicyConflictError("Only ACTIVE policy revisions can be retired.")
        if self._projection.active_policy_id != policy_id:
            raise PolicyConflictError(
                "Retire is blocked unless the target is the current projected active policy."
            )

        retired = replace(
            row,
            status="RETIRED",
            retired_by=current_user.user_id,
            retired_at=datetime.now(UTC),
        )
        self._policies[policy_id] = retired
        self._projection = replace(
            self._projection,
            active_policy_id=None,
            active_policy_family_id=None,
            updated_at=datetime.now(UTC),
        )
        self._append_event(
            retired,
            "POLICY_RETIRED",
            actor_user_id=current_user.user_id,
            reason=reason,
        )
        return retired


def _principal(*, user_id: str, platform_roles: tuple[str, ...] = ()) -> SessionPrincipal:
    now = datetime.now(UTC)
    return SessionPrincipal(
        session_id="session-1",
        auth_source="cookie",
        user_id=user_id,
        oidc_sub=f"oidc|{user_id}",
        email=f"{user_id}@example.test",
        display_name=user_id,
        platform_roles=platform_roles,  # type: ignore[arg-type]
        issued_at=now - timedelta(minutes=5),
        expires_at=now + timedelta(hours=1),
        csrf_token="csrf-token",
    )


@pytest.fixture(autouse=True)
def clear_overrides() -> None:
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_reviewer_can_read_policy_surfaces_with_policy_audit_events() -> None:
    fake_service = FakePolicyService()
    spy_audit = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="user-reviewer"
    )
    app.dependency_overrides[get_policy_service] = lambda: fake_service
    app.dependency_overrides[get_audit_service] = lambda: spy_audit

    policies_response = client.get("/projects/project-1/policies")
    assert policies_response.status_code == 200
    policy_id = policies_response.json()["items"][0]["id"]

    active_response = client.get("/projects/project-1/policies/active")
    assert active_response.status_code == 200
    assert active_response.json()["policy"]["id"] == policy_id

    detail_response = client.get(f"/projects/project-1/policies/{policy_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["status"] == "ACTIVE"

    events_response = client.get(f"/projects/project-1/policies/{policy_id}/events")
    assert events_response.status_code == 200
    assert len(events_response.json()["items"]) >= 2

    compare_response = client.get(
        f"/projects/project-1/policies/{policy_id}/compare",
        params={"againstBaselineSnapshotId": "baseline-phase0-v1"},
    )
    assert compare_response.status_code == 200
    assert compare_response.json()["targetKind"] == "BASELINE_SNAPSHOT"

    lineage_response = client.get(f"/projects/project-1/policies/{policy_id}/lineage")
    assert lineage_response.status_code == 200
    assert len(lineage_response.json()["lineage"]) >= 1

    usage_response = client.get(f"/projects/project-1/policies/{policy_id}/usage")
    assert usage_response.status_code == 200
    assert usage_response.json()["runs"]

    explainability_response = client.get(
        f"/projects/project-1/policies/{policy_id}/explainability"
    )
    assert explainability_response.status_code == 200
    assert explainability_response.json()["deterministicTraces"]

    detail_hash = detail_response.json()["validatedRulesSha256"]
    snapshot_response = client.get(
        f"/projects/project-1/policies/{policy_id}/snapshots/{detail_hash}"
    )
    assert snapshot_response.status_code == 200
    assert snapshot_response.json()["rulesSha256"] == detail_hash

    recorded_types = [str(item.get("event_type")) for item in spy_audit.recorded]
    assert "POLICY_LIST_VIEWED" in recorded_types
    assert "POLICY_ACTIVE_VIEWED" in recorded_types
    assert "POLICY_DETAIL_VIEWED" in recorded_types
    assert "POLICY_EVENTS_VIEWED" in recorded_types
    assert "POLICY_COMPARE_VIEWED" in recorded_types
    assert "POLICY_LINEAGE_VIEWED" in recorded_types
    assert "POLICY_USAGE_VIEWED" in recorded_types
    assert "POLICY_EXPLAINABILITY_VIEWED" in recorded_types
    assert "POLICY_SNAPSHOT_VIEWED" in recorded_types


def test_reviewer_cannot_mutate_policy_routes() -> None:
    fake_service = FakePolicyService()
    spy_audit = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="user-reviewer"
    )
    app.dependency_overrides[get_policy_service] = lambda: fake_service
    app.dependency_overrides[get_audit_service] = lambda: spy_audit

    create_response = client.post(
        "/projects/project-1/policies",
        json={
            "name": "Reviewer draft",
            "rulesJson": {
                "categories": [{"id": "PERSON_NAME", "action": "MASK"}],
                "defaults": {"auto_apply_confidence_threshold": 0.9},
            },
        },
    )
    assert create_response.status_code == 403

    policies_response = client.get("/projects/project-1/policies")
    assert policies_response.status_code == 200
    policy_id = policies_response.json()["items"][0]["id"]
    rollback_response = client.post(
        f"/projects/project-1/policies/{policy_id}/rollback-draft",
        params={"fromPolicyId": policy_id},
    )
    assert rollback_response.status_code == 403

    denied_events = [
        item
        for item in spy_audit.recorded
        if str(item.get("event_type")) == "ACCESS_DENIED"
    ]
    assert len(denied_events) >= 1


def test_policy_lineage_usage_and_explainability_respect_read_rbac() -> None:
    fake_service = FakePolicyService()
    app.dependency_overrides[get_policy_service] = lambda: fake_service
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="user-researcher"
    )
    seeded_id = next(iter(fake_service._policies.keys()))
    researcher_denied = client.get(
        f"/projects/project-1/policies/{seeded_id}/lineage"
    )
    assert researcher_denied.status_code == 403

    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="user-auditor",
        platform_roles=("AUDITOR",),
    )
    auditor_usage = client.get(f"/projects/project-1/policies/{seeded_id}/usage")
    assert auditor_usage.status_code == 200
    auditor_explainability = client.get(
        f"/projects/project-1/policies/{seeded_id}/explainability"
    )
    assert auditor_explainability.status_code == 200


def test_project_lead_can_create_update_validate_activate_and_retire_policy() -> None:
    fake_service = FakePolicyService()
    spy_audit = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-lead")
    app.dependency_overrides[get_policy_service] = lambda: fake_service
    app.dependency_overrides[get_audit_service] = lambda: spy_audit

    create_response = client.post(
        "/projects/project-1/policies",
        json={
            "name": "Lead draft",
            "rulesJson": {
                "categories": [{"id": "PERSON_NAME", "action": "MASK"}],
                "defaults": {"auto_apply_confidence_threshold": 0.91},
            },
            "reason": "create",
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["status"] == "DRAFT"

    patch_response = client.patch(
        f"/projects/project-1/policies/{created['id']}",
        json={
            "versionEtag": created["versionEtag"],
            "name": "Lead draft edited",
            "rulesJson": {
                "categories": [{"id": "PERSON_NAME", "action": "MASK"}],
                "defaults": {"auto_apply_confidence_threshold": 0.94},
            },
            "reason": "edit",
        },
    )
    assert patch_response.status_code == 200
    patched = patch_response.json()
    assert patched["validationStatus"] == "NOT_VALIDATED"

    validate_response = client.post(
        f"/projects/project-1/policies/{created['id']}/validate",
        json={"reason": "validate"},
    )
    assert validate_response.status_code == 200
    assert validate_response.json()["policy"]["validationStatus"] == "VALID"

    activate_response = client.post(
        f"/projects/project-1/policies/{created['id']}/activate",
        json={"reason": "activate"},
    )
    assert activate_response.status_code == 200
    assert activate_response.json()["status"] == "ACTIVE"

    retire_response = client.post(
        f"/projects/project-1/policies/{created['id']}/retire",
        json={"reason": "retire"},
    )
    assert retire_response.status_code == 200
    assert retire_response.json()["status"] == "RETIRED"

    recorded_types = [str(item.get("event_type")) for item in spy_audit.recorded]
    assert "POLICY_CREATED" in recorded_types
    assert "POLICY_UPDATED" in recorded_types
    assert "POLICY_VALIDATION_REQUESTED" in recorded_types
    assert "POLICY_ACTIVATED" in recorded_types
    assert "POLICY_RETIRED" in recorded_types


def test_project_lead_can_create_rollback_draft_from_prior_validated_revision() -> None:
    fake_service = FakePolicyService()
    spy_audit = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-lead")
    app.dependency_overrides[get_policy_service] = lambda: fake_service
    app.dependency_overrides[get_audit_service] = lambda: spy_audit

    policies_response = client.get("/projects/project-1/policies")
    assert policies_response.status_code == 200
    anchor_policy_id = policies_response.json()["items"][0]["id"]

    draft_response = client.post(
        "/projects/project-1/policies",
        json={
            "name": "Forward revision",
            "rulesJson": {
                "categories": [{"id": "PERSON_NAME", "action": "MASK"}],
                "defaults": {"auto_apply_confidence_threshold": 0.91},
            },
            "supersedesPolicyId": anchor_policy_id,
        },
    )
    assert draft_response.status_code == 201
    anchor_draft_id = draft_response.json()["id"]

    rollback_response = client.post(
        f"/projects/project-1/policies/{anchor_draft_id}/rollback-draft",
        params={"fromPolicyId": anchor_policy_id},
    )
    assert rollback_response.status_code == 201
    payload = rollback_response.json()
    assert payload["status"] == "DRAFT"
    assert payload["supersedesPolicyId"] == anchor_draft_id
    assert payload["rulesJson"] == policies_response.json()["items"][0]["rulesJson"]

    recorded_types = [str(item.get("event_type")) for item in spy_audit.recorded]
    assert "POLICY_CREATED" in recorded_types


def test_compare_route_rejects_ambiguous_targets() -> None:
    fake_service = FakePolicyService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-lead")
    app.dependency_overrides[get_policy_service] = lambda: fake_service

    policies_response = client.get("/projects/project-1/policies")
    assert policies_response.status_code == 200
    policy_id = policies_response.json()["items"][0]["id"]

    ambiguous_response = client.get(
        f"/projects/project-1/policies/{policy_id}/compare",
        params={
            "against": policy_id,
            "againstBaselineSnapshotId": "baseline-phase0-v1",
        },
    )
    assert ambiguous_response.status_code == 422

    missing_target_response = client.get(f"/projects/project-1/policies/{policy_id}/compare")
    assert missing_target_response.status_code == 422
