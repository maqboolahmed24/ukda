from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from app.auth.models import SessionPrincipal
from app.core.config import get_settings
from app.policies.models import (
    BaselinePolicySnapshotRecord,
    PolicyEventRecord,
    PolicyRuleSnapshotRecord,
    PolicyUsageLedgerRecord,
    PolicyUsageManifestRecord,
    PolicyUsagePseudonymSummary,
    PolicyUsageRunRecord,
    ProjectPolicyProjectionRecord,
    RedactionPolicyRecord,
)
from app.policies.service import (
    PolicyAccessDeniedError,
    PolicyComparisonError,
    PolicyConflictError,
    PolicyService,
    PolicyValidationError,
)
from app.projects.models import ProjectSummary


def _principal(
    *,
    user_id: str,
    platform_roles: tuple[str, ...] = (),
) -> SessionPrincipal:
    now = datetime.now(UTC)
    return SessionPrincipal(
        session_id=f"session-{user_id}",
        auth_source="cookie",
        user_id=user_id,
        oidc_sub=f"oidc|{user_id}",
        email=f"{user_id}@example.test",
        display_name=user_id,
        platform_roles=platform_roles,  # type: ignore[arg-type]
        issued_at=now - timedelta(minutes=2),
        expires_at=now + timedelta(minutes=58),
        csrf_token="csrf-token",
    )


class InMemoryProjectStore:
    def __init__(self) -> None:
        self.project_id = "project-1"
        self.baseline_id = "baseline-phase0-v1"
        self._base_summary = ProjectSummary(
            id=self.project_id,
            name="Archive One",
            purpose="Policy lifecycle tests",
            status="ACTIVE",
            created_by="user-lead",
            created_at=datetime.now(UTC) - timedelta(days=1),
            intended_access_tier="CONTROLLED",
            baseline_policy_snapshot_id=self.baseline_id,
            current_user_role=None,
        )
        self._roles = {
            "user-lead": "PROJECT_LEAD",
            "user-reviewer": "REVIEWER",
            "user-researcher": "RESEARCHER",
        }

    def get_project_summary_for_user(
        self,
        *,
        project_id: str,
        user_id: str,
    ) -> ProjectSummary | None:
        if project_id != self.project_id:
            return None
        role = self._roles.get(user_id)
        if role is None:
            return None
        return replace(self._base_summary, current_user_role=role)

    def get_project_summary(self, *, project_id: str) -> ProjectSummary | None:
        if project_id != self.project_id:
            return None
        return self._base_summary


class InMemoryPolicyStore:
    def __init__(self, baseline_id: str) -> None:
        self._policies: dict[str, RedactionPolicyRecord] = {}
        self._events: list[PolicyEventRecord] = []
        self._snapshots: list[PolicyRuleSnapshotRecord] = []
        self._projections: dict[str, ProjectPolicyProjectionRecord] = {}
        self._baseline_snapshots = {
            baseline_id: BaselinePolicySnapshotRecord(
                id=baseline_id,
                snapshot_hash="b" * 64,
                rules_json={
                    "categories": [
                        {
                            "id": "PERSON_NAME",
                            "action": "MASK",
                            "review_required_below": 0.9,
                        }
                    ],
                    "defaults": {
                        "auto_apply_confidence_threshold": 0.92,
                    },
                },
                created_at=datetime.now(UTC) - timedelta(days=10),
                seeded_by="SYSTEM_PHASE_0",
            )
        }
        self.historical_phase5_runs = [
            {
                "run_id": "phase5-run-1",
                "policy_snapshot_id": baseline_id,
            }
        ]

    @staticmethod
    def _usage_now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _sort(rows: list[RedactionPolicyRecord]) -> list[RedactionPolicyRecord]:
        return sorted(rows, key=lambda row: (-row.version, row.created_at, row.id))

    def list_policies(self, *, project_id: str) -> list[RedactionPolicyRecord]:
        rows = [row for row in self._policies.values() if row.project_id == project_id]
        return self._sort(rows)

    def get_policy(
        self,
        *,
        project_id: str,
        policy_id: str,
    ) -> RedactionPolicyRecord | None:
        row = self._policies.get(policy_id)
        if row is None or row.project_id != project_id:
            return None
        return row

    def get_policy_by_id(self, *, policy_id: str) -> RedactionPolicyRecord | None:
        return self._policies.get(policy_id)

    def create_policy(self, *, record: RedactionPolicyRecord) -> None:
        self._policies[record.id] = record

    def set_superseded_by(
        self,
        *,
        policy_id: str,
        superseded_by_policy_id: str,
    ) -> None:
        row = self._policies.get(policy_id)
        if row is None or row.superseded_by_policy_id is not None:
            return
        self._policies[policy_id] = replace(
            row,
            superseded_by_policy_id=superseded_by_policy_id,
        )

    def update_draft_policy(
        self,
        *,
        project_id: str,
        policy_id: str,
        expected_version_etag: str,
        name: str,
        rules_json: dict[str, object],
        new_version_etag: str,
    ) -> RedactionPolicyRecord | None:
        row = self.get_policy(project_id=project_id, policy_id=policy_id)
        if (
            row is None
            or row.status != "DRAFT"
            or row.version_etag != expected_version_etag
        ):
            return None
        updated = replace(
            row,
            name=name,
            rules_json=rules_json,
            version_etag=new_version_etag,
            validation_status="NOT_VALIDATED",
            validated_rules_sha256=None,
            last_validated_by=None,
            last_validated_at=None,
        )
        self._policies[policy_id] = updated
        return updated

    def update_validation(
        self,
        *,
        project_id: str,
        policy_id: str,
        validation_status: str,
        validated_rules_sha256: str | None,
        last_validated_by: str,
        last_validated_at: datetime,
    ) -> RedactionPolicyRecord | None:
        row = self.get_policy(project_id=project_id, policy_id=policy_id)
        if row is None:
            return None
        updated = replace(
            row,
            validation_status=validation_status,
            validated_rules_sha256=validated_rules_sha256,
            last_validated_by=last_validated_by,
            last_validated_at=last_validated_at,
        )
        self._policies[policy_id] = updated
        return updated

    def activate_policy(
        self,
        *,
        project_id: str,
        policy_id: str,
        activated_by: str,
        activated_at: datetime,
    ) -> RedactionPolicyRecord | None:
        row = self.get_policy(project_id=project_id, policy_id=policy_id)
        if row is None or row.status != "DRAFT":
            return None
        updated = replace(
            row,
            status="ACTIVE",
            activated_by=activated_by,
            activated_at=activated_at,
            retired_by=None,
            retired_at=None,
        )
        self._policies[policy_id] = updated
        return updated

    def retire_policy(
        self,
        *,
        project_id: str,
        policy_id: str,
        retired_by: str,
        retired_at: datetime,
    ) -> RedactionPolicyRecord | None:
        row = self.get_policy(project_id=project_id, policy_id=policy_id)
        if row is None or row.status != "ACTIVE":
            return None
        updated = replace(
            row,
            status="RETIRED",
            retired_by=retired_by,
            retired_at=retired_at,
        )
        self._policies[policy_id] = updated
        return updated

    def retire_active_policies(
        self,
        *,
        project_id: str,
        except_policy_id: str,
        retired_by: str,
        retired_at: datetime,
    ) -> list[RedactionPolicyRecord]:
        retired: list[RedactionPolicyRecord] = []
        for row in list(self._policies.values()):
            if (
                row.project_id != project_id
                or row.id == except_policy_id
                or row.status != "ACTIVE"
            ):
                continue
            updated = replace(
                row,
                status="RETIRED",
                retired_by=retired_by,
                retired_at=retired_at,
            )
            self._policies[row.id] = updated
            retired.append(updated)
        return retired

    def get_projection(
        self,
        *,
        project_id: str,
    ) -> ProjectPolicyProjectionRecord | None:
        return self._projections.get(project_id)

    def upsert_projection(
        self,
        *,
        project_id: str,
        active_policy_id: str | None,
        active_policy_family_id: str | None,
        updated_at: datetime,
    ) -> ProjectPolicyProjectionRecord:
        projection = ProjectPolicyProjectionRecord(
            project_id=project_id,
            active_policy_id=active_policy_id,
            active_policy_family_id=active_policy_family_id,
            updated_at=updated_at,
        )
        self._projections[project_id] = projection
        return projection

    def append_event(
        self,
        *,
        event: PolicyEventRecord,
        rules_json: dict[str, object],
    ) -> None:
        self._events.append(event)
        self._snapshots.append(
            PolicyRuleSnapshotRecord(
                policy_id=event.policy_id,
                rules_sha256=event.rules_sha256,
                rules_snapshot_key=event.rules_snapshot_key,
                rules_json=dict(rules_json),
                created_at=event.created_at,
            )
        )

    def list_policy_events(
        self,
        *,
        project_id: str,
        policy_id: str,
    ) -> list[PolicyEventRecord]:
        policy = self.get_policy(project_id=project_id, policy_id=policy_id)
        if policy is None:
            return []
        return [event for event in self._events if event.policy_id == policy_id]

    def list_lineage_policies(
        self,
        *,
        project_id: str,
        policy_family_id: str,
    ) -> list[RedactionPolicyRecord]:
        return sorted(
            [
                row
                for row in self._policies.values()
                if row.project_id == project_id and row.policy_family_id == policy_family_id
            ],
            key=lambda row: (row.version, row.created_at, row.id),
        )

    def get_policy_rule_snapshot(
        self,
        *,
        project_id: str,
        policy_id: str,
        rules_sha256: str,
    ) -> PolicyRuleSnapshotRecord | None:
        policy = self.get_policy(project_id=project_id, policy_id=policy_id)
        if policy is None:
            return None
        matches = [
            snapshot
            for snapshot in self._snapshots
            if snapshot.policy_id == policy_id and snapshot.rules_sha256 == rules_sha256
        ]
        if not matches:
            return None
        return sorted(matches, key=lambda row: (row.created_at, row.rules_snapshot_key))[-1]

    def list_policy_usage_runs(
        self,
        *,
        project_id: str,
        policy_id: str,
    ) -> list[PolicyUsageRunRecord]:
        policy = self.get_policy(project_id=project_id, policy_id=policy_id)
        if policy is None:
            return []
        return [
            PolicyUsageRunRecord(
                run_id="redaction-run-usage-1",
                project_id=project_id,
                document_id="doc-usage-1",
                run_kind="POLICY_RERUN",
                run_status="SUCCEEDED",
                supersedes_redaction_run_id="redaction-run-baseline-1",
                policy_family_id=policy.policy_family_id,
                policy_version=str(policy.version),
                run_created_at=self._usage_now(),
                run_finished_at=self._usage_now(),
                governance_readiness_status="READY",
                governance_generation_status="IDLE",
                governance_manifest_id="manifest-usage-1",
                governance_ledger_id="ledger-usage-1",
                governance_manifest_sha256="m" * 64,
                governance_ledger_sha256="l" * 64,
                governance_ledger_verification_status="VALID",
            )
        ]

    def list_policy_usage_manifests(
        self,
        *,
        project_id: str,
        policy_id: str,
    ) -> list[PolicyUsageManifestRecord]:
        if self.get_policy(project_id=project_id, policy_id=policy_id) is None:
            return []
        return [
            PolicyUsageManifestRecord(
                id="manifest-usage-1",
                run_id="redaction-run-usage-1",
                project_id=project_id,
                document_id="doc-usage-1",
                status="SUCCEEDED",
                attempt_number=1,
                manifest_sha256="m" * 64,
                source_review_snapshot_sha256="s" * 64,
                created_at=self._usage_now(),
            )
        ]

    def list_policy_usage_ledgers(
        self,
        *,
        project_id: str,
        policy_id: str,
    ) -> list[PolicyUsageLedgerRecord]:
        if self.get_policy(project_id=project_id, policy_id=policy_id) is None:
            return []
        return [
            PolicyUsageLedgerRecord(
                id="ledger-usage-1",
                run_id="redaction-run-usage-1",
                project_id=project_id,
                document_id="doc-usage-1",
                status="SUCCEEDED",
                attempt_number=1,
                ledger_sha256="l" * 64,
                source_review_snapshot_sha256="s" * 64,
                created_at=self._usage_now(),
            )
        ]

    def get_policy_pseudonym_summary(
        self,
        *,
        project_id: str,
        policy_id: str,
    ) -> PolicyUsagePseudonymSummary:
        if self.get_policy(project_id=project_id, policy_id=policy_id) is None:
            return PolicyUsagePseudonymSummary(
                total_entries=0,
                active_entries=0,
                retired_entries=0,
                alias_strategy_versions=tuple(),
                salt_version_refs=tuple(),
            )
        return PolicyUsagePseudonymSummary(
            total_entries=3,
            active_entries=2,
            retired_entries=1,
            alias_strategy_versions=("v1",),
            salt_version_refs=("salt-v1",),
        )

    def get_baseline_snapshot(
        self,
        *,
        snapshot_id: str,
    ) -> BaselinePolicySnapshotRecord | None:
        return self._baseline_snapshots.get(snapshot_id)

    @staticmethod
    def utcnow() -> datetime:
        return datetime.now(UTC)


def _service() -> tuple[PolicyService, InMemoryPolicyStore, InMemoryProjectStore]:
    projects = InMemoryProjectStore()
    policies = InMemoryPolicyStore(projects.baseline_id)
    service = PolicyService(
        settings=get_settings(),
        store=policies,  # type: ignore[arg-type]
        project_store=projects,  # type: ignore[arg-type]
    )
    return service, policies, projects


def _valid_rules(name: str = "Policy") -> dict[str, object]:
    return {
        "name": name,
        "categories": [
            {
                "id": "PERSON_NAME",
                "action": "MASK",
                "review_required_below": 0.9,
            },
            {
                "id": "ADDRESS",
                "action": "GENERALIZE",
                "review_required_below": 0.88,
            },
        ],
        "defaults": {
            "auto_apply_confidence_threshold": 0.92,
            "require_manual_review_for_uncertain": True,
        },
        "pseudonymisation": {
            "mode": "DETERMINISTIC",
            "aliasing_rules": {"prefix": "ALIAS-"},
        },
        "generalisation": {
            "specificity_ceiling": "district",
            "by_category": {"ADDRESS": "district"},
        },
        "reviewer_explanation_mode": "LOCAL_LLM_RISK_SUMMARY",
    }


def test_malformed_rules_are_rejected_on_create() -> None:
    service, _, projects = _service()

    with pytest.raises(PolicyValidationError):
        service.create_policy(
            current_user=_principal(user_id="user-lead"),
            project_id=projects.project_id,
            name="Invalid",
            rules_json={"categories": "not-a-list"},
            seeded_from_baseline_snapshot_id=None,
            supersedes_policy_id=None,
            reason="bad payload",
        )


def test_patch_draft_invalidates_prior_validation() -> None:
    service, _, projects = _service()
    lead = _principal(user_id="user-lead")
    created = service.create_policy(
        current_user=lead,
        project_id=projects.project_id,
        name="Initial policy",
        rules_json=_valid_rules("Initial policy"),
        seeded_from_baseline_snapshot_id=None,
        supersedes_policy_id=None,
        reason=None,
    )

    validated = service.validate_policy(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=created.id,
        reason=None,
    ).policy
    assert validated.validation_status == "VALID"
    assert validated.validated_rules_sha256 is not None

    updated = service.update_policy(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=created.id,
        expected_version_etag=validated.version_etag,
        name="Initial policy v2",
        rules_json={
            **_valid_rules("Initial policy v2"),
            "defaults": {
                "auto_apply_confidence_threshold": 0.95,
            },
        },
        reason="adjust threshold",
    )

    assert updated.validation_status == "NOT_VALIDATED"
    assert updated.validated_rules_sha256 is None
    assert updated.version_etag != created.version_etag


def test_only_one_active_policy_per_project() -> None:
    service, store, projects = _service()
    lead = _principal(user_id="user-lead")

    first = service.create_policy(
        current_user=lead,
        project_id=projects.project_id,
        name="Policy v1",
        rules_json=_valid_rules("Policy v1"),
        seeded_from_baseline_snapshot_id=None,
        supersedes_policy_id=None,
        reason=None,
    )
    service.validate_policy(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=first.id,
        reason=None,
    )
    first_active = service.activate_policy(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=first.id,
        reason=None,
    )
    assert first_active.status == "ACTIVE"

    second = service.create_policy(
        current_user=lead,
        project_id=projects.project_id,
        name="Policy v2",
        rules_json={
            **_valid_rules("Policy v2"),
            "defaults": {
                "auto_apply_confidence_threshold": 0.97,
            },
        },
        seeded_from_baseline_snapshot_id=projects.baseline_id,
        supersedes_policy_id=first.id,
        reason=None,
    )
    service.validate_policy(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=second.id,
        reason=None,
    )
    second_active = service.activate_policy(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=second.id,
        reason=None,
    )

    rows = service.list_policies(
        current_user=lead,
        project_id=projects.project_id,
    )
    assert sum(1 for row in rows if row.status == "ACTIVE") == 1
    assert second_active.status == "ACTIVE"
    assert store.get_policy(project_id=projects.project_id, policy_id=first.id).status == "RETIRED"
    projection = store.get_projection(project_id=projects.project_id)
    assert projection is not None
    assert projection.active_policy_id == second.id
    assert projection.active_policy_family_id == second.policy_family_id


def test_stale_draft_edits_are_rejected_without_current_version_etag() -> None:
    service, _, projects = _service()
    lead = _principal(user_id="user-lead")

    created = service.create_policy(
        current_user=lead,
        project_id=projects.project_id,
        name="Draft v1",
        rules_json=_valid_rules("Draft v1"),
        seeded_from_baseline_snapshot_id=None,
        supersedes_policy_id=None,
        reason=None,
    )

    updated = service.update_policy(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=created.id,
        expected_version_etag=created.version_etag,
        name="Draft v1 edited",
        rules_json=_valid_rules("Draft v1 edited"),
        reason=None,
    )

    with pytest.raises(PolicyConflictError):
        service.update_policy(
            current_user=lead,
            project_id=projects.project_id,
            policy_id=created.id,
            expected_version_etag=created.version_etag,
            name="Second stale edit",
            rules_json=_valid_rules("Second stale edit"),
            reason=None,
        )

    assert updated.version_etag != created.version_etag


def test_activation_requires_latest_validated_hash_match() -> None:
    service, store, projects = _service()
    lead = _principal(user_id="user-lead")

    created = service.create_policy(
        current_user=lead,
        project_id=projects.project_id,
        name="Hash gate policy",
        rules_json=_valid_rules("Hash gate policy"),
        seeded_from_baseline_snapshot_id=None,
        supersedes_policy_id=None,
        reason=None,
    )
    service.validate_policy(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=created.id,
        reason=None,
    )

    tampered = store.update_validation(
        project_id=projects.project_id,
        policy_id=created.id,
        validation_status="VALID",
        validated_rules_sha256="0" * 64,
        last_validated_by=lead.user_id,
        last_validated_at=datetime.now(UTC),
    )
    assert tampered is not None

    with pytest.raises(PolicyConflictError):
        service.activate_policy(
            current_user=lead,
            project_id=projects.project_id,
            policy_id=created.id,
            reason=None,
        )


def test_retire_requires_target_to_match_projection_active_policy() -> None:
    service, store, projects = _service()
    lead = _principal(user_id="user-lead")

    created = service.create_policy(
        current_user=lead,
        project_id=projects.project_id,
        name="Retire gate policy",
        rules_json=_valid_rules("Retire gate policy"),
        seeded_from_baseline_snapshot_id=None,
        supersedes_policy_id=None,
        reason=None,
    )
    service.validate_policy(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=created.id,
        reason=None,
    )
    active = service.activate_policy(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=created.id,
        reason=None,
    )
    store.upsert_projection(
        project_id=projects.project_id,
        active_policy_id="different-policy",
        active_policy_family_id=active.policy_family_id,
        updated_at=datetime.now(UTC),
    )

    with pytest.raises(PolicyConflictError):
        service.retire_policy(
            current_user=lead,
            project_id=projects.project_id,
            policy_id=active.id,
            reason=None,
        )


def test_history_timeline_reconstructs_append_only_policy_events() -> None:
    service, _, projects = _service()
    lead = _principal(user_id="user-lead")

    created = service.create_policy(
        current_user=lead,
        project_id=projects.project_id,
        name="Timeline policy",
        rules_json=_valid_rules("Timeline policy"),
        seeded_from_baseline_snapshot_id=None,
        supersedes_policy_id=None,
        reason="create",
    )
    updated = service.update_policy(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=created.id,
        expected_version_etag=created.version_etag,
        name="Timeline policy edited",
        rules_json=_valid_rules("Timeline policy edited"),
        reason="edit",
    )
    service.validate_policy(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=updated.id,
        reason="validate",
    )
    active = service.activate_policy(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=updated.id,
        reason="activate",
    )
    service.retire_policy(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=active.id,
        reason="retire",
    )

    events = service.list_policy_events(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=created.id,
    )
    event_types = [event.event_type for event in events]
    assert event_types == [
        "POLICY_CREATED",
        "POLICY_EDITED",
        "POLICY_VALIDATED_VALID",
        "POLICY_ACTIVATED",
        "POLICY_RETIRED",
    ]
    assert all(event.rules_snapshot_key for event in events)
    assert all(len(event.rules_sha256) == 64 for event in events)
    assert len({event.id for event in events}) == len(events)


def test_compare_requires_exactly_one_target() -> None:
    service, _, projects = _service()
    lead = _principal(user_id="user-lead")

    created = service.create_policy(
        current_user=lead,
        project_id=projects.project_id,
        name="Compare policy",
        rules_json=_valid_rules("Compare policy"),
        seeded_from_baseline_snapshot_id=None,
        supersedes_policy_id=None,
        reason=None,
    )

    with pytest.raises(PolicyComparisonError):
        service.compare_policy(
            current_user=lead,
            project_id=projects.project_id,
            policy_id=created.id,
            against_policy_id=None,
            against_baseline_snapshot_id=None,
        )

    with pytest.raises(PolicyComparisonError):
        service.compare_policy(
            current_user=lead,
            project_id=projects.project_id,
            policy_id=created.id,
            against_policy_id=created.id,
            against_baseline_snapshot_id=projects.baseline_id,
        )


def test_policy_lineage_snapshot_is_reconstructable_from_append_only_events() -> None:
    service, _, projects = _service()
    lead = _principal(user_id="user-lead")

    created = service.create_policy(
        current_user=lead,
        project_id=projects.project_id,
        name="Lineage policy",
        rules_json=_valid_rules("Lineage policy"),
        seeded_from_baseline_snapshot_id=None,
        supersedes_policy_id=None,
        reason="create",
    )
    service.validate_policy(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=created.id,
        reason="validate",
    )
    service.activate_policy(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=created.id,
        reason="activate",
    )

    lineage = service.get_policy_lineage(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=created.id,
    )
    assert lineage.policy.id == created.id
    assert len(lineage.lineage) >= 1
    assert any(event.event_type == "POLICY_CREATED" for event in lineage.events)
    assert any(event.event_type == "POLICY_ACTIVATED" for event in lineage.events)
    assert lineage.projection is not None
    assert lineage.projection.active_policy_id == created.id


def test_policy_snapshot_returns_immutable_rules_payload_for_event_hash() -> None:
    service, _, projects = _service()
    lead = _principal(user_id="user-lead")

    created = service.create_policy(
        current_user=lead,
        project_id=projects.project_id,
        name="Snapshot policy",
        rules_json=_valid_rules("Snapshot policy"),
        seeded_from_baseline_snapshot_id=None,
        supersedes_policy_id=None,
        reason="create",
    )
    validate_result = service.validate_policy(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=created.id,
        reason="validate",
    )
    snapshot = service.get_policy_snapshot(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=created.id,
        rules_sha256=validate_result.policy.validated_rules_sha256 or "",
    )
    assert snapshot.policy.id == created.id
    assert snapshot.snapshot.rules_sha256 == validate_result.policy.validated_rules_sha256
    assert snapshot.snapshot.rules_json["name"] == "Snapshot policy"
    assert snapshot.event.rules_snapshot_key == snapshot.snapshot.rules_snapshot_key


def test_policy_usage_links_reruns_governance_and_pseudonym_summary() -> None:
    service, _, projects = _service()
    lead = _principal(user_id="user-lead")

    created = service.create_policy(
        current_user=lead,
        project_id=projects.project_id,
        name="Usage policy",
        rules_json=_valid_rules("Usage policy"),
        seeded_from_baseline_snapshot_id=None,
        supersedes_policy_id=None,
        reason="create",
    )

    usage = service.get_policy_usage(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=created.id,
    )
    assert usage.policy.id == created.id
    assert len(usage.runs) == 1
    assert usage.runs[0].governance_manifest_id == "manifest-usage-1"
    assert len(usage.manifests) == 1
    assert len(usage.ledgers) == 1
    assert usage.pseudonym_summary.total_entries == 3


def test_policy_explainability_is_deterministic_and_bounded() -> None:
    service, _, projects = _service()
    lead = _principal(user_id="user-lead")

    created = service.create_policy(
        current_user=lead,
        project_id=projects.project_id,
        name="Explainability policy",
        rules_json=_valid_rules("Explainability policy"),
        seeded_from_baseline_snapshot_id=None,
        supersedes_policy_id=None,
        reason="create",
    )

    first = service.get_policy_explainability(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=created.id,
    )
    second = service.get_policy_explainability(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=created.id,
    )
    assert first.rules_sha256 == second.rules_sha256
    assert first.category_rules == second.category_rules
    assert first.deterministic_traces == second.deterministic_traces
    assert all(trace.rationale for trace in first.deterministic_traces)


def test_rollback_creates_new_draft_seeded_from_prior_validated_revision() -> None:
    service, store, projects = _service()
    lead = _principal(user_id="user-lead")

    first = service.create_policy(
        current_user=lead,
        project_id=projects.project_id,
        name="Policy v1",
        rules_json=_valid_rules("Policy v1"),
        seeded_from_baseline_snapshot_id=None,
        supersedes_policy_id=None,
        reason=None,
    )
    service.validate_policy(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=first.id,
        reason=None,
    )
    service.activate_policy(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=first.id,
        reason=None,
    )

    second = service.create_policy(
        current_user=lead,
        project_id=projects.project_id,
        name="Policy v2",
        rules_json={
            **_valid_rules("Policy v2"),
            "defaults": {"auto_apply_confidence_threshold": 0.98},
        },
        seeded_from_baseline_snapshot_id=projects.baseline_id,
        supersedes_policy_id=first.id,
        reason=None,
    )

    rollback = service.create_rollback_draft(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=second.id,
        from_policy_id=first.id,
        reason="rollback test",
    )

    assert rollback.status == "DRAFT"
    assert rollback.supersedes_policy_id == second.id
    assert rollback.rules_json == first.rules_json
    assert rollback.validation_status == "NOT_VALIDATED"
    assert store.get_policy(project_id=projects.project_id, policy_id=second.id) is not None


def test_rollback_rejects_unvalidated_or_non_prior_source_revision() -> None:
    service, _, projects = _service()
    lead = _principal(user_id="user-lead")

    first = service.create_policy(
        current_user=lead,
        project_id=projects.project_id,
        name="Policy v1",
        rules_json=_valid_rules("Policy v1"),
        seeded_from_baseline_snapshot_id=None,
        supersedes_policy_id=None,
        reason=None,
    )
    second = service.create_policy(
        current_user=lead,
        project_id=projects.project_id,
        name="Policy v2",
        rules_json=_valid_rules("Policy v2"),
        seeded_from_baseline_snapshot_id=projects.baseline_id,
        supersedes_policy_id=first.id,
        reason=None,
    )

    with pytest.raises(PolicyConflictError):
        service.create_rollback_draft(
            current_user=lead,
            project_id=projects.project_id,
            policy_id=second.id,
            from_policy_id=first.id,
            reason=None,
        )

    service.validate_policy(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=first.id,
        reason=None,
    )
    with pytest.raises(PolicyConflictError):
        service.create_rollback_draft(
            current_user=lead,
            project_id=projects.project_id,
            policy_id=first.id,
            from_policy_id=first.id,
            reason=None,
        )


def test_rbac_enforces_read_and_mutate_boundaries() -> None:
    service, _, projects = _service()
    lead = _principal(user_id="user-lead")
    reviewer = _principal(user_id="user-reviewer")
    researcher = _principal(user_id="user-researcher")
    auditor = _principal(user_id="user-auditor", platform_roles=("AUDITOR",))

    created = service.create_policy(
        current_user=lead,
        project_id=projects.project_id,
        name="RBAC policy",
        rules_json=_valid_rules("RBAC policy"),
        seeded_from_baseline_snapshot_id=None,
        supersedes_policy_id=None,
        reason=None,
    )

    reviewer_rows = service.list_policies(
        current_user=reviewer,
        project_id=projects.project_id,
    )
    assert reviewer_rows[0].id == created.id

    auditor_rows = service.list_policies(
        current_user=auditor,
        project_id=projects.project_id,
    )
    assert auditor_rows[0].id == created.id

    with pytest.raises(PolicyAccessDeniedError):
        service.list_policies(
            current_user=researcher,
            project_id=projects.project_id,
        )

    with pytest.raises(PolicyAccessDeniedError):
        service.create_policy(
            current_user=reviewer,
            project_id=projects.project_id,
            name="Reviewer policy",
            rules_json=_valid_rules("Reviewer policy"),
            seeded_from_baseline_snapshot_id=None,
            supersedes_policy_id=None,
            reason=None,
        )

    with pytest.raises(PolicyAccessDeniedError):
        service.create_policy(
            current_user=auditor,
            project_id=projects.project_id,
            name="Auditor policy",
            rules_json=_valid_rules("Auditor policy"),
            seeded_from_baseline_snapshot_id=None,
            supersedes_policy_id=None,
            reason=None,
        )


def test_historical_phase5_runs_remain_pinned_to_baseline_snapshots() -> None:
    service, store, projects = _service()
    lead = _principal(user_id="user-lead")
    before = list(store.historical_phase5_runs)

    created = service.create_policy(
        current_user=lead,
        project_id=projects.project_id,
        name="Pin test policy",
        rules_json=_valid_rules("Pin test policy"),
        seeded_from_baseline_snapshot_id=None,
        supersedes_policy_id=None,
        reason=None,
    )
    service.validate_policy(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=created.id,
        reason=None,
    )
    service.activate_policy(
        current_user=lead,
        project_id=projects.project_id,
        policy_id=created.id,
        reason=None,
    )

    assert store.historical_phase5_runs == before
    assert all(
        row["policy_snapshot_id"] == projects.baseline_id
        for row in store.historical_phase5_runs
    )
