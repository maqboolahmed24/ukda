from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from app.auth.models import SessionPrincipal
from app.core.config import get_settings
from app.policies.models import RedactionPolicyRecord
from app.projects.models import ProjectSummary
from app.pseudonyms.models import (
    PseudonymRegistryEntryEventRecord,
    PseudonymRegistryEntryRecord,
)
from app.pseudonyms.service import (
    PseudonymRegistryAccessDeniedError,
    PseudonymRegistryService,
)


def _principal(*, user_id: str, platform_roles: tuple[str, ...] = ()) -> SessionPrincipal:
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
        self.project_ids = ("project-1", "project-2")
        now = datetime.now(UTC) - timedelta(days=1)
        self._summaries = {
            "project-1": ProjectSummary(
                id="project-1",
                name="Project One",
                purpose="Pseudonym registry tests",
                status="ACTIVE",
                created_by="user-lead",
                created_at=now,
                intended_access_tier="CONTROLLED",
                baseline_policy_snapshot_id="baseline-1",
                current_user_role=None,
            ),
            "project-2": ProjectSummary(
                id="project-2",
                name="Project Two",
                purpose="Pseudonym registry tests",
                status="ACTIVE",
                created_by="user-lead-2",
                created_at=now,
                intended_access_tier="CONTROLLED",
                baseline_policy_snapshot_id="baseline-2",
                current_user_role=None,
            ),
        }
        self._roles: dict[tuple[str, str], str] = {
            ("project-1", "user-lead"): "PROJECT_LEAD",
            ("project-1", "user-reviewer"): "REVIEWER",
            ("project-1", "user-researcher"): "RESEARCHER",
            ("project-2", "user-lead-2"): "PROJECT_LEAD",
        }

    def get_project_summary_for_user(
        self,
        *,
        project_id: str,
        user_id: str,
    ) -> ProjectSummary | None:
        summary = self._summaries.get(project_id)
        if summary is None:
            return None
        role = self._roles.get((project_id, user_id))
        if role is None:
            return None
        return replace(summary, current_user_role=role)

    def get_project_summary(self, *, project_id: str) -> ProjectSummary | None:
        return self._summaries.get(project_id)


class InMemoryPolicyStore:
    def __init__(self) -> None:
        now = datetime.now(UTC) - timedelta(hours=4)
        self._policies: dict[tuple[str, str], RedactionPolicyRecord] = {}
        self._policies[("project-1", "policy-p1-v1")] = RedactionPolicyRecord(
            id="policy-p1-v1",
            project_id="project-1",
            policy_family_id="family-p1",
            name="Policy P1",
            version=1,
            seeded_from_baseline_snapshot_id="baseline-1",
            supersedes_policy_id=None,
            superseded_by_policy_id=None,
            rules_json={
                "categories": [{"id": "PERSON_NAME", "action": "PSEUDONYMIZE"}]
            },
            version_etag="etag-p1",
            status="ACTIVE",
            created_by="user-lead",
            created_at=now,
            activated_by="user-lead",
            activated_at=now,
            retired_by=None,
            retired_at=None,
            validation_status="VALID",
            validated_rules_sha256="a" * 64,
            last_validated_by="user-lead",
            last_validated_at=now,
        )
        self._policies[("project-2", "policy-p2-v1")] = RedactionPolicyRecord(
            id="policy-p2-v1",
            project_id="project-2",
            policy_family_id="family-p2",
            name="Policy P2",
            version=1,
            seeded_from_baseline_snapshot_id="baseline-2",
            supersedes_policy_id=None,
            superseded_by_policy_id=None,
            rules_json={
                "categories": [{"id": "PERSON_NAME", "action": "PSEUDONYMIZE"}]
            },
            version_etag="etag-p2",
            status="ACTIVE",
            created_by="user-lead-2",
            created_at=now,
            activated_by="user-lead-2",
            activated_at=now,
            retired_by=None,
            retired_at=None,
            validation_status="VALID",
            validated_rules_sha256="b" * 64,
            last_validated_by="user-lead-2",
            last_validated_at=now,
        )

    def get_policy(self, *, project_id: str, policy_id: str) -> RedactionPolicyRecord | None:
        return self._policies.get((project_id, policy_id))


class InMemoryRegistryStore:
    def __init__(self) -> None:
        self._entries: dict[str, PseudonymRegistryEntryRecord] = {}
        self._events: list[PseudonymRegistryEntryEventRecord] = []
        self._lineage_fingerprints: dict[str, str] = {}

    def list_entries(self, *, project_id: str) -> list[PseudonymRegistryEntryRecord]:
        rows = [entry for entry in self._entries.values() if entry.project_id == project_id]
        return sorted(rows, key=lambda row: (row.created_at, row.id), reverse=True)

    def get_entry(
        self,
        *,
        project_id: str,
        entry_id: str,
    ) -> PseudonymRegistryEntryRecord | None:
        row = self._entries.get(entry_id)
        if row is None or row.project_id != project_id:
            return None
        return row

    def find_active_entry_by_tuple(
        self,
        *,
        project_id: str,
        source_fingerprint_hmac_sha256: str,
        policy_id: str,
        salt_version_ref: str,
        alias_strategy_version: str,
    ) -> PseudonymRegistryEntryRecord | None:
        for row in self._entries.values():
            if (
                row.project_id == project_id
                and row.source_fingerprint_hmac_sha256 == source_fingerprint_hmac_sha256
                and row.policy_id == policy_id
                and row.salt_version_ref == salt_version_ref
                and row.alias_strategy_version == alias_strategy_version
                and row.status == "ACTIVE"
            ):
                return row
        return None

    def find_active_entry_by_alias_scope(
        self,
        *,
        project_id: str,
        salt_version_ref: str,
        alias_strategy_version: str,
        alias_value: str,
    ) -> PseudonymRegistryEntryRecord | None:
        for row in self._entries.values():
            if (
                row.project_id == project_id
                and row.salt_version_ref == salt_version_ref
                and row.alias_strategy_version == alias_strategy_version
                and row.alias_value == alias_value
                and row.status == "ACTIVE"
            ):
                return row
        return None

    def find_latest_lineage_predecessor(
        self,
        *,
        project_id: str,
        lineage_source_fingerprint_hmac_sha256: str,
        policy_id: str,
        salt_version_ref: str,
        alias_strategy_version: str,
    ) -> PseudonymRegistryEntryRecord | None:
        candidates = [
            row
            for row in self._entries.values()
            if row.project_id == project_id
            and self._lineage_fingerprints.get(row.id)
            == lineage_source_fingerprint_hmac_sha256
            and row.policy_id == policy_id
            and (
                row.salt_version_ref != salt_version_ref
                or row.alias_strategy_version != alias_strategy_version
            )
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda row: (row.updated_at, row.created_at, row.id))

    def create_entry(
        self,
        *,
        record: PseudonymRegistryEntryRecord,
        lineage_source_fingerprint_hmac_sha256: str,
    ) -> None:
        self._entries[record.id] = record
        self._lineage_fingerprints[record.id] = lineage_source_fingerprint_hmac_sha256

    def touch_entry_usage(
        self,
        *,
        project_id: str,
        entry_id: str,
        last_used_run_id: str,
        updated_at: datetime,
    ) -> PseudonymRegistryEntryRecord | None:
        row = self.get_entry(project_id=project_id, entry_id=entry_id)
        if row is None or row.status != "ACTIVE":
            return None
        updated = replace(
            row,
            last_used_run_id=last_used_run_id,
            updated_at=updated_at,
        )
        self._entries[entry_id] = updated
        return updated

    def set_superseded_by(
        self,
        *,
        project_id: str,
        entry_id: str,
        superseded_by_entry_id: str,
    ) -> None:
        row = self.get_entry(project_id=project_id, entry_id=entry_id)
        if row is None:
            return
        if row.superseded_by_entry_id is not None:
            return
        self._entries[entry_id] = replace(row, superseded_by_entry_id=superseded_by_entry_id)

    def retire_entry(
        self,
        *,
        project_id: str,
        entry_id: str,
        retired_by: str,
        retired_at: datetime,
    ) -> PseudonymRegistryEntryRecord | None:
        row = self.get_entry(project_id=project_id, entry_id=entry_id)
        if row is None or row.status != "ACTIVE":
            return None
        retired = replace(
            row,
            status="RETIRED",
            retired_by=retired_by,
            retired_at=retired_at,
            updated_at=retired_at,
        )
        self._entries[entry_id] = retired
        return retired

    def append_event(self, *, event: PseudonymRegistryEntryEventRecord) -> None:
        self._events.append(event)

    def list_entry_events(
        self,
        *,
        project_id: str,
        entry_id: str,
    ) -> list[PseudonymRegistryEntryEventRecord]:
        if self.get_entry(project_id=project_id, entry_id=entry_id) is None:
            return []
        return sorted(
            [event for event in self._events if event.entry_id == entry_id],
            key=lambda event: (event.created_at, event.id),
        )

    @staticmethod
    def utcnow() -> datetime:
        return datetime.now(UTC)


def _service() -> tuple[PseudonymRegistryService, InMemoryRegistryStore]:
    store = InMemoryRegistryStore()
    service = PseudonymRegistryService(
        settings=get_settings(),
        store=store,  # type: ignore[arg-type]
        project_store=InMemoryProjectStore(),  # type: ignore[arg-type]
        policy_store=InMemoryPolicyStore(),  # type: ignore[arg-type]
    )
    return service, store


def _canonical_for_assert(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).strip().split()).casefold()


def test_same_entity_same_project_scope_reuses_alias_and_appends_reuse_event() -> None:
    service, store = _service()
    lead = _principal(user_id="user-lead")

    first = service.register_or_reuse_entry(
        current_user=lead,
        project_id="project-1",
        source_run_id="run-1",
        source_value="  Ada   Lovelace ",
        policy_id="policy-p1-v1",
        salt_version_ref="salt-v1",
        alias_strategy_version="v1",
    )
    second = service.register_or_reuse_entry(
        current_user=lead,
        project_id="project-1",
        source_run_id="run-2",
        source_value="ada lovelace",
        policy_id="policy-p1-v1",
        salt_version_ref="salt-v1",
        alias_strategy_version="v1",
    )

    assert first.id == second.id
    assert first.alias_value == second.alias_value
    assert len(store.list_entries(project_id="project-1")) == 1
    resolved = store.get_entry(project_id="project-1", entry_id=first.id)
    assert resolved is not None
    assert resolved.last_used_run_id == "run-2"

    events = store.list_entry_events(project_id="project-1", entry_id=first.id)
    assert [event.event_type for event in events] == ["ENTRY_CREATED", "ENTRY_REUSED"]


def test_same_entity_across_projects_maps_to_different_aliases() -> None:
    service, _ = _service()

    first = service.register_or_reuse_entry(
        current_user=_principal(user_id="user-lead"),
        project_id="project-1",
        source_run_id="run-1",
        source_value="John Smith",
        policy_id="policy-p1-v1",
        salt_version_ref="salt-v1",
        alias_strategy_version="v1",
    )
    second = service.register_or_reuse_entry(
        current_user=_principal(user_id="user-lead-2"),
        project_id="project-2",
        source_run_id="run-1",
        source_value="John Smith",
        policy_id="policy-p2-v1",
        salt_version_ref="salt-v1",
        alias_strategy_version="v1",
    )

    assert first.alias_value != second.alias_value
    assert first.source_fingerprint_hmac_sha256 != second.source_fingerprint_hmac_sha256


def test_different_sources_in_same_scope_do_not_share_active_alias() -> None:
    service, _ = _service()
    lead = _principal(user_id="user-lead")

    first = service.register_or_reuse_entry(
        current_user=lead,
        project_id="project-1",
        source_run_id="run-1",
        source_value="Jane Roe",
        policy_id="policy-p1-v1",
        salt_version_ref="salt-v1",
        alias_strategy_version="v1",
    )
    second = service.register_or_reuse_entry(
        current_user=lead,
        project_id="project-1",
        source_run_id="run-1",
        source_value="John Roe",
        policy_id="policy-p1-v1",
        salt_version_ref="salt-v1",
        alias_strategy_version="v1",
    )

    assert first.alias_value != second.alias_value
    assert first.source_fingerprint_hmac_sha256 != second.source_fingerprint_hmac_sha256


def test_persisted_fingerprint_is_keyed_hmac_not_plain_sha256() -> None:
    service, _ = _service()
    lead = _principal(user_id="user-lead")

    entry = service.register_or_reuse_entry(
        current_user=lead,
        project_id="project-1",
        source_run_id="run-1",
        source_value="Elizabeth Bennet",
        policy_id="policy-p1-v1",
        salt_version_ref="salt-v1",
        alias_strategy_version="v1",
    )

    plain_sha = hashlib.sha256(
        _canonical_for_assert("Elizabeth Bennet").encode("utf-8")
    ).hexdigest()
    assert entry.source_fingerprint_hmac_sha256 != plain_sha
    assert len(entry.source_fingerprint_hmac_sha256) == 64


def test_salt_version_change_requires_new_lineage_entry() -> None:
    service, store = _service()
    lead = _principal(user_id="user-lead")

    v1 = service.register_or_reuse_entry(
        current_user=lead,
        project_id="project-1",
        source_run_id="run-1",
        source_value="Grace Hopper",
        policy_id="policy-p1-v1",
        salt_version_ref="salt-v1",
        alias_strategy_version="v1",
    )
    v2 = service.register_or_reuse_entry(
        current_user=lead,
        project_id="project-1",
        source_run_id="run-2",
        source_value="Grace Hopper",
        policy_id="policy-p1-v1",
        salt_version_ref="salt-v2",
        alias_strategy_version="v1",
    )

    assert v1.id != v2.id
    assert v2.supersedes_entry_id == v1.id
    prior = store.get_entry(project_id="project-1", entry_id=v1.id)
    assert prior is not None
    assert prior.superseded_by_entry_id == v2.id


def test_read_access_allows_lead_admin_auditor_and_denies_reviewer_researcher() -> None:
    service, _ = _service()

    service.list_entries(
        current_user=_principal(user_id="user-lead"),
        project_id="project-1",
    )
    service.list_entries(
        current_user=_principal(user_id="user-admin", platform_roles=("ADMIN",)),
        project_id="project-1",
    )
    service.list_entries(
        current_user=_principal(user_id="user-auditor", platform_roles=("AUDITOR",)),
        project_id="project-1",
    )

    with pytest.raises(PseudonymRegistryAccessDeniedError):
        service.list_entries(
            current_user=_principal(user_id="user-reviewer"),
            project_id="project-1",
        )
    with pytest.raises(PseudonymRegistryAccessDeniedError):
        service.list_entries(
            current_user=_principal(user_id="user-researcher"),
            project_id="project-1",
        )
