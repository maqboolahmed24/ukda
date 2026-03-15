from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from uuid import uuid4

from app.auth.models import SessionPrincipal
from app.core.config import Settings, get_settings
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
    PolicyUsageSnapshot,
    PolicyValidationResult,
    RedactionPolicyRecord,
)
from app.policies.store import PolicyStore, PolicyStoreUnavailableError
from app.projects.models import ProjectRole, ProjectSummary
from app.projects.store import ProjectStore, ProjectStoreUnavailableError

_ALLOWED_CATEGORY_ACTIONS = {
    "MASK",
    "PSEUDONYMIZE",
    "GENERALIZE",
    "ESCALATE",
    "ALLOW",
    "REVIEW",
}


class PolicyAccessDeniedError(RuntimeError):
    """Current session is not permitted for the requested policy action."""


class PolicyNotFoundError(RuntimeError):
    """Policy or project resource was not found."""


class PolicyValidationError(RuntimeError):
    """Policy payload failed validation checks."""


class PolicyConflictError(RuntimeError):
    """Policy lifecycle operation conflicts with current state."""


class PolicyComparisonError(RuntimeError):
    """Policy comparison request is malformed or invalid."""


@dataclass(frozen=True)
class _ProjectPolicyAccessContext:
    summary: ProjectSummary
    project_role: ProjectRole | None
    is_admin: bool
    is_auditor: bool


def _normalized_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized if normalized else None


def _as_mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _rules_sha256(rules_json: Mapping[str, object]) -> str:
    return hashlib.sha256(_canonical_json_bytes(dict(rules_json))).hexdigest()


def _is_probability(value: object) -> bool:
    if not isinstance(value, (int, float)):
        return False
    numeric = float(value)
    return 0.0 <= numeric <= 1.0


def _coerce_probability(value: object) -> float | None:
    if not _is_probability(value):
        return None
    return float(value)


def _as_text_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(
            item.strip()
            for item in (str(entry) for entry in value if isinstance(entry, str))
            if item.strip()
        )
    if isinstance(value, Mapping):
        return tuple(
            key.strip()
            for key in sorted(str(raw_key) for raw_key in value.keys())
            if key.strip()
        )
    return tuple()


def _validate_rules_shape(rules_json: Mapping[str, object]) -> list[str]:
    issues: list[str] = []
    if len(rules_json) == 0:
        issues.append("Rules payload must be a non-empty JSON object.")
        return issues

    categories_raw = rules_json.get("categories")
    if not isinstance(categories_raw, Sequence) or isinstance(categories_raw, (str, bytes)):
        issues.append("`categories` must be a non-empty array of category rule objects.")
        return issues
    categories = [item for item in categories_raw if isinstance(item, Mapping)]
    if len(categories) != len(categories_raw) or len(categories) == 0:
        issues.append("Every entry in `categories` must be an object with id/action fields.")
        return issues

    for index, raw_category in enumerate(categories):
        category = _as_mapping(raw_category)
        category_id = _normalized_text(
            str(category.get("id")) if isinstance(category.get("id"), str) else None
        )
        if category_id is None:
            issues.append(f"categories[{index}] is missing a non-empty `id`.")

        action_text = (
            str(category.get("action"))
            if isinstance(category.get("action"), str)
            else ""
        )
        action = action_text.strip().upper()
        if action not in _ALLOWED_CATEGORY_ACTIONS:
            issues.append(
                f"categories[{index}].action must be one of"
                f" {sorted(_ALLOWED_CATEGORY_ACTIONS)}."
            )

        for threshold_field in (
            "review_required_below",
            "auto_apply_above",
            "confidence_threshold",
        ):
            if threshold_field in category and not _is_probability(category[threshold_field]):
                issues.append(
                    f"categories[{index}].{threshold_field} must be a number between 0 and 1."
                )

    defaults_raw = rules_json.get("defaults")
    if defaults_raw is not None:
        defaults = _as_mapping(defaults_raw)
        if len(defaults) == 0 and defaults_raw is not None:
            issues.append("`defaults` must be an object when provided.")
        threshold = defaults.get("auto_apply_confidence_threshold")
        if threshold is not None and not _is_probability(threshold):
            issues.append("defaults.auto_apply_confidence_threshold must be between 0 and 1.")

    reviewer_requirements = rules_json.get("reviewer_requirements")
    if reviewer_requirements is not None and not isinstance(
        reviewer_requirements, (bool, Mapping)
    ):
        issues.append("reviewer_requirements must be a boolean or object when provided.")

    escalation_flags = rules_json.get("escalation_flags")
    if escalation_flags is not None and not isinstance(escalation_flags, (bool, Mapping)):
        issues.append("escalation_flags must be a boolean or object when provided.")

    pseudonymisation = rules_json.get("pseudonymisation")
    if pseudonymisation is not None:
        pseudo_map = _as_mapping(pseudonymisation)
        if len(pseudo_map) == 0:
            issues.append("pseudonymisation must be an object when provided.")
        mode_value = pseudo_map.get("mode")
        if mode_value is not None and not isinstance(mode_value, str):
            issues.append("pseudonymisation.mode must be a string when provided.")
        alias_rules = pseudo_map.get("aliasing_rules")
        if alias_rules is not None and not isinstance(alias_rules, Mapping):
            issues.append("pseudonymisation.aliasing_rules must be an object when provided.")

    generalisation = rules_json.get("generalisation")
    if generalisation is not None and not isinstance(generalisation, (Mapping, Sequence)):
        issues.append("generalisation must be an object or array when provided.")

    reviewer_explanation_mode = rules_json.get("reviewer_explanation_mode")
    if reviewer_explanation_mode is not None and not isinstance(reviewer_explanation_mode, str):
        issues.append("reviewer_explanation_mode must be a string when provided.")

    return issues


def _diff_policy_rules(
    before: object,
    after: object,
    *,
    path: str = "$",
) -> list[PolicyRulesDiffItem]:
    if isinstance(before, Mapping) and isinstance(after, Mapping):
        differences: list[PolicyRulesDiffItem] = []
        keys = sorted(set(before.keys()) | set(after.keys()), key=str)
        for key in keys:
            key_text = str(key)
            next_path = f"{path}.{key_text}"
            in_before = key in before
            in_after = key in after
            if not in_before:
                differences.append(
                    PolicyRulesDiffItem(
                        path=next_path,
                        before=None,
                        after=after[key],
                    )
                )
                continue
            if not in_after:
                differences.append(
                    PolicyRulesDiffItem(
                        path=next_path,
                        before=before[key],
                        after=None,
                    )
                )
                continue
            differences.extend(_diff_policy_rules(before[key], after[key], path=next_path))
        return differences

    if (
        isinstance(before, Sequence)
        and isinstance(after, Sequence)
        and not isinstance(before, (str, bytes))
        and not isinstance(after, (str, bytes))
    ):
        differences = []
        max_length = max(len(before), len(after))
        for index in range(max_length):
            next_path = f"{path}[{index}]"
            if index >= len(before):
                differences.append(
                    PolicyRulesDiffItem(path=next_path, before=None, after=after[index])
                )
                continue
            if index >= len(after):
                differences.append(
                    PolicyRulesDiffItem(path=next_path, before=before[index], after=None)
                )
                continue
            differences.extend(_diff_policy_rules(before[index], after[index], path=next_path))
        return differences

    if before != after:
        return [PolicyRulesDiffItem(path=path, before=before, after=after)]

    return []


class PolicyService:
    def __init__(
        self,
        *,
        settings: Settings,
        store: PolicyStore | None = None,
        project_store: ProjectStore | None = None,
    ) -> None:
        self._settings = settings
        self._store = store or PolicyStore(settings)
        self._project_store = project_store or ProjectStore(settings)

    @staticmethod
    def _is_admin(current_user: SessionPrincipal) -> bool:
        return "ADMIN" in set(current_user.platform_roles)

    @staticmethod
    def _is_auditor(current_user: SessionPrincipal) -> bool:
        return "AUDITOR" in set(current_user.platform_roles)

    def _resolve_project_access(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> _ProjectPolicyAccessContext:
        is_admin = self._is_admin(current_user)
        is_auditor = self._is_auditor(current_user)
        try:
            member_summary = self._project_store.get_project_summary_for_user(
                project_id=project_id,
                user_id=current_user.user_id,
            )
            if member_summary is not None:
                return _ProjectPolicyAccessContext(
                    summary=member_summary,
                    project_role=member_summary.current_user_role,
                    is_admin=is_admin,
                    is_auditor=is_auditor,
                )

            if is_admin or is_auditor:
                summary = self._project_store.get_project_summary(project_id=project_id)
                if summary is None:
                    raise PolicyNotFoundError("Project not found.")
                return _ProjectPolicyAccessContext(
                    summary=summary,
                    project_role=None,
                    is_admin=is_admin,
                    is_auditor=is_auditor,
                )
        except ProjectStoreUnavailableError as error:
            raise PolicyStoreUnavailableError("Project access lookup failed.") from error

        raise PolicyAccessDeniedError("Project membership is required for this policy route.")

    @staticmethod
    def _require_read_access(context: _ProjectPolicyAccessContext) -> None:
        if context.is_admin or context.is_auditor:
            return
        if context.project_role in {"PROJECT_LEAD", "REVIEWER"}:
            return
        raise PolicyAccessDeniedError(
            "Current role cannot view Phase 7 policy routes in this project."
        )

    @staticmethod
    def _require_mutation_access(context: _ProjectPolicyAccessContext) -> None:
        if context.is_admin:
            return
        if context.project_role == "PROJECT_LEAD":
            return
        raise PolicyAccessDeniedError(
            "Current role cannot create, edit, validate, activate, retire, or rollback policies."
        )

    @staticmethod
    def _normalize_policy_name(name: str) -> str:
        normalized = name.strip()
        if len(normalized) < 3:
            raise PolicyValidationError("Policy name must be at least 3 characters.")
        if len(normalized) > 180:
            raise PolicyValidationError("Policy name must be 180 characters or fewer.")
        return normalized

    @staticmethod
    def _normalize_reason(reason: str | None) -> str | None:
        normalized = _normalized_text(reason)
        if normalized is None:
            return None
        return normalized[:800]

    @staticmethod
    def _normalize_rules(rules_json: Mapping[str, Any]) -> dict[str, object]:
        normalized = dict(rules_json)
        issues = _validate_rules_shape(normalized)
        if issues:
            raise PolicyValidationError(issues[0])
        return normalized

    def _append_policy_event(
        self,
        *,
        policy: RedactionPolicyRecord,
        event_type: str,
        actor_user_id: str,
        reason: str | None,
    ) -> None:
        created_at = self._store.utcnow()
        event_id = str(uuid4())
        snapshot_key = (
            f"policies/{policy.project_id}/{policy.policy_family_id}/{policy.id}/"
            f"{created_at.strftime('%Y%m%dT%H%M%SZ')}-{event_id}.json"
        )
        self._store.append_event(
            event=PolicyEventRecord(
                id=event_id,
                policy_id=policy.id,
                event_type=event_type,  # type: ignore[arg-type]
                actor_user_id=actor_user_id,
                reason=reason,
                rules_sha256=_rules_sha256(policy.rules_json),
                rules_snapshot_key=snapshot_key,
                created_at=created_at,
            ),
            rules_json=policy.rules_json,
        )

    def list_policies(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> list[RedactionPolicyRecord]:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_read_access(context)
        return self._store.list_policies(project_id=project_id)

    def get_policy(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        policy_id: str,
    ) -> RedactionPolicyRecord:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_read_access(context)
        record = self._store.get_policy(project_id=project_id, policy_id=policy_id)
        if record is None:
            raise PolicyNotFoundError("Policy revision not found.")
        return record

    def list_policy_events(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        policy_id: str,
    ) -> list[PolicyEventRecord]:
        _ = self.get_policy(
            current_user=current_user,
            project_id=project_id,
            policy_id=policy_id,
        )
        return self._store.list_policy_events(project_id=project_id, policy_id=policy_id)

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
        projection = self._store.get_projection(project_id=project_id)
        lineage_rows = tuple(
            self._store.list_lineage_policies(
                project_id=project_id,
                policy_family_id=policy.policy_family_id,
            )
        )
        lineage_events: list[PolicyEventRecord] = []
        for row in lineage_rows:
            lineage_events.extend(
                self._store.list_policy_events(
                    project_id=project_id,
                    policy_id=row.id,
                )
            )
        lineage_events.sort(key=lambda item: (item.created_at, item.id))
        return PolicyLineageSnapshot(
            policy=policy,
            projection=projection,
            lineage=lineage_rows,
            events=tuple(lineage_events),
            active_policy_differs=(
                projection is not None
                and isinstance(projection.active_policy_id, str)
                and projection.active_policy_id != policy.id
            ),
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
        return PolicyUsageSnapshot(
            policy=policy,
            runs=tuple(
                self._store.list_policy_usage_runs(
                    project_id=project_id,
                    policy_id=policy_id,
                )
            ),
            manifests=tuple(
                self._store.list_policy_usage_manifests(
                    project_id=project_id,
                    policy_id=policy_id,
                )
            ),
            ledgers=tuple(
                self._store.list_policy_usage_ledgers(
                    project_id=project_id,
                    policy_id=policy_id,
                )
            ),
            pseudonym_summary=self._store.get_policy_pseudonym_summary(
                project_id=project_id,
                policy_id=policy_id,
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
        rules = policy.rules_json
        categories_raw = rules.get("categories")
        category_rules: list[PolicyExplainabilityCategoryRule] = []
        traces: list[PolicyExplainabilityTrace] = []
        if isinstance(categories_raw, Sequence) and not isinstance(
            categories_raw, (str, bytes)
        ):
            for category in categories_raw:
                if not isinstance(category, Mapping):
                    continue
                category_id = _normalized_text(
                    str(category.get("id")) if isinstance(category.get("id"), str) else None
                )
                if category_id is None:
                    continue
                action_value = (
                    str(category.get("action"))
                    if isinstance(category.get("action"), str)
                    else "UNSPECIFIED"
                )
                action = action_value.strip().upper() or "UNSPECIFIED"
                review_required_below = _coerce_probability(
                    category.get("review_required_below")
                )
                auto_apply_above = _coerce_probability(category.get("auto_apply_above"))
                confidence_threshold = _coerce_probability(
                    category.get("confidence_threshold")
                )
                requires_reviewer = bool(
                    category.get("requires_reviewer")
                    or category.get("requiresReviewer")
                )
                escalation_flags = _as_text_tuple(
                    category.get("escalation_flags")
                    if "escalation_flags" in category
                    else category.get("escalationFlags")
                )
                category_rules.append(
                    PolicyExplainabilityCategoryRule(
                        id=category_id,
                        action=action,
                        review_required_below=review_required_below,
                        auto_apply_above=auto_apply_above,
                        confidence_threshold=confidence_threshold,
                        requires_reviewer=requires_reviewer,
                        escalation_flags=escalation_flags,
                    )
                )
                sample_confidence = (
                    review_required_below
                    if review_required_below is not None
                    else auto_apply_above
                    if auto_apply_above is not None
                    else confidence_threshold
                    if confidence_threshold is not None
                    else 0.75
                )
                if review_required_below is not None and sample_confidence < review_required_below:
                    outcome = "REVIEW_REQUIRED"
                    rationale = (
                        f"Sample confidence {sample_confidence:.2f} is below "
                        f"review_required_below {review_required_below:.2f}."
                    )
                elif auto_apply_above is not None and sample_confidence >= auto_apply_above:
                    outcome = "AUTO_APPLY"
                    rationale = (
                        f"Sample confidence {sample_confidence:.2f} meets "
                        f"auto_apply_above {auto_apply_above:.2f}."
                    )
                elif confidence_threshold is not None:
                    if sample_confidence >= confidence_threshold:
                        outcome = "AUTO_APPLY"
                        rationale = (
                            f"Sample confidence {sample_confidence:.2f} meets "
                            f"confidence_threshold {confidence_threshold:.2f}."
                        )
                    else:
                        outcome = "REVIEW_REQUIRED"
                        rationale = (
                            f"Sample confidence {sample_confidence:.2f} is below "
                            f"confidence_threshold {confidence_threshold:.2f}."
                        )
                elif action in {"ALLOW", "REVIEW"}:
                    outcome = "UNSPECIFIED"
                    rationale = "No deterministic confidence gate is configured for this rule."
                else:
                    outcome = "AUTO_APPLY"
                    rationale = (
                        "Category action applies directly because no confidence gate exists."
                    )
                traces.append(
                    PolicyExplainabilityTrace(
                        category_id=category_id,
                        sample_confidence=float(sample_confidence),
                        selected_action=action,
                        outcome=outcome,
                        rationale=rationale,
                    )
                )
        defaults = dict(_as_mapping(rules.get("defaults")))
        reviewer_requirements_raw = rules.get("reviewer_requirements")
        reviewer_requirements: bool | dict[str, object] | None
        if isinstance(reviewer_requirements_raw, bool):
            reviewer_requirements = reviewer_requirements_raw
        elif isinstance(reviewer_requirements_raw, Mapping):
            reviewer_requirements = dict(reviewer_requirements_raw)
        else:
            reviewer_requirements = None
        escalation_flags_raw = rules.get("escalation_flags")
        escalation_flags: bool | dict[str, object] | None
        if isinstance(escalation_flags_raw, bool):
            escalation_flags = escalation_flags_raw
        elif isinstance(escalation_flags_raw, Mapping):
            escalation_flags = dict(escalation_flags_raw)
        else:
            escalation_flags = None
        pseudonymisation_raw = rules.get("pseudonymisation")
        pseudonymisation = (
            dict(pseudonymisation_raw) if isinstance(pseudonymisation_raw, Mapping) else None
        )
        generalisation_raw = rules.get("generalisation")
        generalisation: dict[str, object] | tuple[object, ...] | None
        if isinstance(generalisation_raw, Mapping):
            generalisation = dict(generalisation_raw)
        elif isinstance(generalisation_raw, Sequence) and not isinstance(
            generalisation_raw, (str, bytes)
        ):
            generalisation = tuple(generalisation_raw)
        else:
            generalisation = None
        reviewer_explanation_mode = (
            rules.get("reviewer_explanation_mode")
            if isinstance(rules.get("reviewer_explanation_mode"), str)
            else None
        )
        return PolicyExplainabilitySnapshot(
            policy=policy,
            rules_sha256=_rules_sha256(policy.rules_json),
            category_rules=tuple(category_rules),
            defaults=defaults,
            reviewer_requirements=reviewer_requirements,
            escalation_flags=escalation_flags,
            pseudonymisation=pseudonymisation,
            generalisation=generalisation,
            reviewer_explanation_mode=reviewer_explanation_mode,
            deterministic_traces=tuple(traces),
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
        normalized_rules_sha = _normalized_text(rules_sha256)
        if normalized_rules_sha is None:
            raise PolicyValidationError("rulesSha256 is required.")
        if len(normalized_rules_sha) != 64:
            raise PolicyValidationError("rulesSha256 must be a 64-character SHA-256 hex digest.")
        normalized_rules_sha = normalized_rules_sha.lower()

        events = self._store.list_policy_events(project_id=project_id, policy_id=policy_id)
        matching_events = [event for event in events if event.rules_sha256 == normalized_rules_sha]
        if not matching_events:
            raise PolicyNotFoundError("Policy rule snapshot not found for requested rulesSha256.")
        event = matching_events[-1]
        snapshot = self._store.get_policy_rule_snapshot(
            project_id=project_id,
            policy_id=policy_id,
            rules_sha256=normalized_rules_sha,
        )
        if snapshot is None:
            current_hash = _rules_sha256(policy.rules_json)
            if current_hash != normalized_rules_sha:
                raise PolicyNotFoundError(
                    "Policy rule snapshot payload is unavailable for requested rulesSha256."
                )
            snapshot = PolicyRuleSnapshotRecord(
                policy_id=policy.id,
                rules_sha256=normalized_rules_sha,
                rules_snapshot_key=event.rules_snapshot_key,
                rules_json=dict(policy.rules_json),
                created_at=event.created_at,
            )
        return PolicySnapshotView(
            policy=policy,
            event=event,
            snapshot=snapshot,
        )

    def get_active_policy(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> ActiveProjectPolicyView:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_read_access(context)

        projection = self._store.get_projection(project_id=project_id)
        if projection is None or projection.active_policy_id is None:
            return ActiveProjectPolicyView(projection=projection, policy=None)

        policy = self._store.get_policy_by_id(policy_id=projection.active_policy_id)
        if policy is None or policy.project_id != project_id:
            return ActiveProjectPolicyView(projection=projection, policy=None)

        return ActiveProjectPolicyView(projection=projection, policy=policy)

    def create_policy(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        name: str,
        rules_json: Mapping[str, Any],
        seeded_from_baseline_snapshot_id: str | None,
        supersedes_policy_id: str | None,
        reason: str | None,
    ) -> RedactionPolicyRecord:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_mutation_access(context)

        normalized_name = self._normalize_policy_name(name)
        normalized_rules = self._normalize_rules(rules_json)
        normalized_reason = self._normalize_reason(reason)

        existing = self._store.list_policies(project_id=project_id)
        now = self._store.utcnow()

        normalized_seed = _normalized_text(seeded_from_baseline_snapshot_id)
        normalized_supersedes = _normalized_text(supersedes_policy_id)

        if not existing:
            if normalized_supersedes is not None:
                raise PolicyValidationError(
                    "supersedesPolicyId is not allowed when creating the first policy revision."
                )
            baseline_id = context.summary.baseline_policy_snapshot_id
            if normalized_seed is not None and normalized_seed != baseline_id:
                raise PolicyValidationError(
                    "First explicit policy lineage must seed from the project's baseline snapshot."
                )
            policy_family_id = str(uuid4())
            version = 1
            supersedes = None
            seeded_from_baseline_snapshot_id_resolved = baseline_id
        else:
            families = {row.policy_family_id for row in existing}
            if len(families) != 1:
                raise PolicyConflictError(
                    "Project already has multiple policy families; v1 allows exactly one lineage."
                )
            policy_family_id = next(iter(families))
            seeded_from_baseline_snapshot_id_resolved = existing[0].seeded_from_baseline_snapshot_id
            if (
                normalized_seed is not None
                and normalized_seed != seeded_from_baseline_snapshot_id_resolved
            ):
                raise PolicyValidationError(
                    "New revisions must keep the existing seeded baseline origin."
                )

            supersedes: RedactionPolicyRecord | None = None
            if normalized_supersedes is not None:
                supersedes = next(
                    (row for row in existing if row.id == normalized_supersedes),
                    None,
                )
                if supersedes is None:
                    raise PolicyNotFoundError("Superseded policy revision was not found.")
            else:
                supersedes = max(existing, key=lambda row: row.version)
            max_version = max(row.version for row in existing)
            version = max_version + 1

        record = RedactionPolicyRecord(
            id=str(uuid4()),
            project_id=project_id,
            policy_family_id=policy_family_id,
            name=normalized_name,
            version=version,
            seeded_from_baseline_snapshot_id=seeded_from_baseline_snapshot_id_resolved,
            supersedes_policy_id=supersedes.id if existing else None,
            superseded_by_policy_id=None,
            rules_json=normalized_rules,
            version_etag=str(uuid4()),
            status="DRAFT",
            created_by=current_user.user_id,
            created_at=now,
            activated_by=None,
            activated_at=None,
            retired_by=None,
            retired_at=None,
            validation_status="NOT_VALIDATED",
            validated_rules_sha256=None,
            last_validated_by=None,
            last_validated_at=None,
        )
        self._store.create_policy(record=record)
        if record.supersedes_policy_id is not None:
            self._store.set_superseded_by(
                policy_id=record.supersedes_policy_id,
                superseded_by_policy_id=record.id,
        )
        self._append_policy_event(
            policy=record,
            event_type="POLICY_CREATED",
            actor_user_id=current_user.user_id,
            reason=normalized_reason,
        )
        return record

    def create_rollback_draft(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        policy_id: str,
        from_policy_id: str,
        reason: str | None,
    ) -> RedactionPolicyRecord:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_mutation_access(context)

        anchor_policy = self._store.get_policy(project_id=project_id, policy_id=policy_id)
        if anchor_policy is None:
            raise PolicyNotFoundError("Policy revision not found.")

        source_policy = self._store.get_policy(project_id=project_id, policy_id=from_policy_id)
        if source_policy is None:
            raise PolicyNotFoundError("Rollback source policy revision not found.")
        if source_policy.policy_family_id != anchor_policy.policy_family_id:
            raise PolicyConflictError(
                "Rollback source must belong to the same policy lineage."
            )
        if source_policy.version >= anchor_policy.version:
            raise PolicyConflictError(
                "Rollback source must reference a prior policy revision."
            )
        if source_policy.validation_status != "VALID":
            raise PolicyConflictError(
                "Rollback source must be a VALID policy revision."
            )
        source_hash = _rules_sha256(source_policy.rules_json)
        if source_policy.validated_rules_sha256 != source_hash:
            raise PolicyConflictError(
                "Rollback source validation hash does not match current rules_json."
            )

        family_rows = [
            row
            for row in self._store.list_policies(project_id=project_id)
            if row.policy_family_id == anchor_policy.policy_family_id
        ]
        if not family_rows:
            raise PolicyConflictError("Policy lineage is unavailable for rollback.")
        latest_in_family = max(family_rows, key=lambda row: row.version)
        next_version = latest_in_family.version + 1
        rollback_name = self._normalize_policy_name(
            f"{anchor_policy.name} rollback v{source_policy.version}"[:180]
        )
        now = self._store.utcnow()
        rollback_draft = RedactionPolicyRecord(
            id=str(uuid4()),
            project_id=project_id,
            policy_family_id=anchor_policy.policy_family_id,
            name=rollback_name,
            version=next_version,
            seeded_from_baseline_snapshot_id=anchor_policy.seeded_from_baseline_snapshot_id,
            supersedes_policy_id=latest_in_family.id,
            superseded_by_policy_id=None,
            rules_json=dict(source_policy.rules_json),
            version_etag=str(uuid4()),
            status="DRAFT",
            created_by=current_user.user_id,
            created_at=now,
            activated_by=None,
            activated_at=None,
            retired_by=None,
            retired_at=None,
            validation_status="NOT_VALIDATED",
            validated_rules_sha256=None,
            last_validated_by=None,
            last_validated_at=None,
        )
        self._store.create_policy(record=rollback_draft)
        self._store.set_superseded_by(
            policy_id=latest_in_family.id,
            superseded_by_policy_id=rollback_draft.id,
        )
        self._append_policy_event(
            policy=rollback_draft,
            event_type="POLICY_CREATED",
            actor_user_id=current_user.user_id,
            reason=(
                self._normalize_reason(reason)
                or f"Rollback draft seeded from {source_policy.id}."
            ),
        )
        return rollback_draft

    def update_policy(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        policy_id: str,
        expected_version_etag: str,
        name: str | None,
        rules_json: Mapping[str, Any] | None,
        reason: str | None,
    ) -> RedactionPolicyRecord:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_mutation_access(context)

        normalized_etag = _normalized_text(expected_version_etag)
        if normalized_etag is None:
            raise PolicyConflictError("Current versionEtag is required to patch a draft policy.")

        current = self._store.get_policy(project_id=project_id, policy_id=policy_id)
        if current is None:
            raise PolicyNotFoundError("Policy revision not found.")
        if current.status != "DRAFT":
            raise PolicyConflictError("Only DRAFT policy revisions may be edited.")

        next_name = self._normalize_policy_name(name) if name is not None else current.name
        if rules_json is None:
            next_rules = current.rules_json
        else:
            next_rules = self._normalize_rules(rules_json)

        updated = self._store.update_draft_policy(
            project_id=project_id,
            policy_id=policy_id,
            expected_version_etag=normalized_etag,
            name=next_name,
            rules_json=next_rules,
            new_version_etag=str(uuid4()),
        )
        if updated is None:
            latest = self._store.get_policy(project_id=project_id, policy_id=policy_id)
            if latest is None:
                raise PolicyNotFoundError("Policy revision not found.")
            raise PolicyConflictError(
                "Draft policy update rejected because versionEtag is stale or status changed."
            )

        self._append_policy_event(
            policy=updated,
            event_type="POLICY_EDITED",
            actor_user_id=current_user.user_id,
            reason=self._normalize_reason(reason),
        )
        return updated

    def validate_policy(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        policy_id: str,
        reason: str | None,
    ) -> PolicyValidationResult:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_mutation_access(context)

        current = self._store.get_policy(project_id=project_id, policy_id=policy_id)
        if current is None:
            raise PolicyNotFoundError("Policy revision not found.")
        if current.status != "DRAFT":
            raise PolicyConflictError("Only DRAFT policy revisions can be validated.")

        issues = _validate_rules_shape(current.rules_json)
        rules_hash = _rules_sha256(current.rules_json)
        validation_status = "VALID" if not issues else "INVALID"

        updated = self._store.update_validation(
            project_id=project_id,
            policy_id=policy_id,
            validation_status=validation_status,
            validated_rules_sha256=rules_hash if validation_status == "VALID" else None,
            last_validated_by=current_user.user_id,
            last_validated_at=self._store.utcnow(),
        )
        if updated is None:
            raise PolicyNotFoundError("Policy revision not found.")

        self._append_policy_event(
            policy=updated,
            event_type=(
                "POLICY_VALIDATED_VALID"
                if validation_status == "VALID"
                else "POLICY_VALIDATED_INVALID"
            ),
            actor_user_id=current_user.user_id,
            reason=self._normalize_reason(reason),
        )
        return PolicyValidationResult(policy=updated, issues=tuple(issues))

    def activate_policy(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        policy_id: str,
        reason: str | None,
    ) -> RedactionPolicyRecord:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_mutation_access(context)

        current = self._store.get_policy(project_id=project_id, policy_id=policy_id)
        if current is None:
            raise PolicyNotFoundError("Policy revision not found.")
        if current.status != "DRAFT":
            raise PolicyConflictError("Only DRAFT policy revisions can be activated.")

        current_rules_hash = _rules_sha256(current.rules_json)
        if (
            current.validation_status != "VALID"
            or current.validated_rules_sha256 != current_rules_hash
        ):
            raise PolicyConflictError(
                "Activation is blocked until validation_status is VALID and"
                " hash matches current rules_json."
            )

        now = self._store.utcnow()
        retired_rows = self._store.retire_active_policies(
            project_id=project_id,
            except_policy_id=policy_id,
            retired_by=current_user.user_id,
            retired_at=now,
        )
        normalized_reason = self._normalize_reason(reason)
        for retired in retired_rows:
            self._append_policy_event(
                policy=retired,
                event_type="POLICY_RETIRED",
                actor_user_id=current_user.user_id,
                reason=normalized_reason,
            )

        activated = self._store.activate_policy(
            project_id=project_id,
            policy_id=policy_id,
            activated_by=current_user.user_id,
            activated_at=now,
        )
        if activated is None:
            raise PolicyConflictError(
                "Activation failed because the draft revision was modified by another request."
            )

        self._store.upsert_projection(
            project_id=project_id,
            active_policy_id=activated.id,
            active_policy_family_id=activated.policy_family_id,
            updated_at=now,
        )
        self._append_policy_event(
            policy=activated,
            event_type="POLICY_ACTIVATED",
            actor_user_id=current_user.user_id,
            reason=normalized_reason,
        )
        return activated

    def retire_policy(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        policy_id: str,
        reason: str | None,
    ) -> RedactionPolicyRecord:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_mutation_access(context)

        current = self._store.get_policy(project_id=project_id, policy_id=policy_id)
        if current is None:
            raise PolicyNotFoundError("Policy revision not found.")
        if current.status != "ACTIVE":
            raise PolicyConflictError("Only ACTIVE policy revisions can be retired.")

        projection = self._store.get_projection(project_id=project_id)
        if projection is None or projection.active_policy_id != policy_id:
            raise PolicyConflictError(
                "Retire is blocked unless the target is the current projected active policy."
            )

        now = self._store.utcnow()
        retired = self._store.retire_policy(
            project_id=project_id,
            policy_id=policy_id,
            retired_by=current_user.user_id,
            retired_at=now,
        )
        if retired is None:
            raise PolicyConflictError("Active policy retirement failed due to concurrent update.")

        self._store.upsert_projection(
            project_id=project_id,
            active_policy_id=None,
            active_policy_family_id=None,
            updated_at=now,
        )
        self._append_policy_event(
            policy=retired,
            event_type="POLICY_RETIRED",
            actor_user_id=current_user.user_id,
            reason=self._normalize_reason(reason),
        )
        return retired

    def compare_policy(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        policy_id: str,
        against_policy_id: str | None,
        against_baseline_snapshot_id: str | None,
    ) -> PolicyCompareResult:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_read_access(context)

        source = self._store.get_policy(project_id=project_id, policy_id=policy_id)
        if source is None:
            raise PolicyNotFoundError("Policy revision not found.")

        target_policy = _normalized_text(against_policy_id)
        target_baseline = _normalized_text(against_baseline_snapshot_id)
        if (target_policy is None and target_baseline is None) or (
            target_policy is not None and target_baseline is not None
        ):
            raise PolicyComparisonError(
                "Provide exactly one comparison target: against or againstBaselineSnapshotId."
            )

        source_hash = _rules_sha256(source.rules_json)

        if target_policy is not None:
            comparison = self._store.get_policy(project_id=project_id, policy_id=target_policy)
            if comparison is None:
                raise PolicyNotFoundError("Comparison policy revision not found.")
            if comparison.policy_family_id != source.policy_family_id:
                raise PolicyComparisonError(
                    "Cross-family comparisons are not allowed in Phase 7 v1."
                )
            differences = tuple(
                _diff_policy_rules(source.rules_json, comparison.rules_json)
            )
            return PolicyCompareResult(
                source_policy=source,
                target_kind="POLICY",
                target_policy=comparison,
                target_baseline_snapshot_id=None,
                source_rules_sha256=source_hash,
                target_rules_sha256=_rules_sha256(comparison.rules_json),
                differences=differences,
            )

        assert target_baseline is not None
        if source.seeded_from_baseline_snapshot_id != target_baseline:
            raise PolicyComparisonError(
                "Baseline comparison is allowed only for the lineage's seeded baseline snapshot."
            )

        baseline = self._store.get_baseline_snapshot(snapshot_id=target_baseline)
        if baseline is None:
            raise PolicyNotFoundError("Baseline policy snapshot not found.")

        differences = tuple(_diff_policy_rules(source.rules_json, baseline.rules_json))
        return PolicyCompareResult(
            source_policy=source,
            target_kind="BASELINE_SNAPSHOT",
            target_policy=None,
            target_baseline_snapshot_id=target_baseline,
            source_rules_sha256=source_hash,
            target_rules_sha256=baseline.snapshot_hash,
            differences=differences,
        )


@lru_cache
def get_policy_service() -> PolicyService:
    settings = get_settings()
    return PolicyService(settings=settings)
