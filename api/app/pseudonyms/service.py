from __future__ import annotations

import hashlib
import hmac
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from uuid import uuid4

from app.auth.models import SessionPrincipal
from app.core.config import Settings, get_settings
from app.policies.store import PolicyStore
from app.projects.models import ProjectRole, ProjectSummary
from app.projects.store import ProjectStore, ProjectStoreUnavailableError
from app.pseudonyms.models import (
    PseudonymRegistryEntryEventRecord,
    PseudonymRegistryEntryRecord,
)
from app.pseudonyms.store import (
    PseudonymRegistryStore,
    PseudonymRegistryStoreUnavailableError,
)


class PseudonymRegistryAccessDeniedError(RuntimeError):
    """Current session is not permitted for the requested pseudonym action."""


class PseudonymRegistryNotFoundError(RuntimeError):
    """Registry entry or project resource was not found."""


class PseudonymRegistryValidationError(RuntimeError):
    """Pseudonym registry payload failed validation checks."""


class PseudonymRegistryConflictError(RuntimeError):
    """Pseudonym registry operation conflicts with current state."""


@dataclass(frozen=True)
class _ProjectRegistryAccessContext:
    summary: ProjectSummary
    project_role: ProjectRole | None
    is_admin: bool
    is_auditor: bool


def _normalized_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized if normalized else None


def _canonical_source_value(value: str) -> str:
    normalized_unicode = unicodedata.normalize("NFKC", value)
    collapsed = " ".join(normalized_unicode.strip().split())
    canonical = collapsed.casefold()
    if len(canonical) == 0:
        raise PseudonymRegistryValidationError("sourceValue must contain at least one character.")
    return canonical


class PseudonymRegistryService:
    def __init__(
        self,
        *,
        settings: Settings,
        store: PseudonymRegistryStore | None = None,
        project_store: ProjectStore | None = None,
        policy_store: PolicyStore | None = None,
    ) -> None:
        self._settings = settings
        self._store = store or PseudonymRegistryStore(settings)
        self._project_store = project_store or ProjectStore(settings)
        self._policy_store = policy_store or PolicyStore(settings)

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
    ) -> _ProjectRegistryAccessContext:
        is_admin = self._is_admin(current_user)
        is_auditor = self._is_auditor(current_user)
        try:
            member_summary = self._project_store.get_project_summary_for_user(
                project_id=project_id,
                user_id=current_user.user_id,
            )
            if member_summary is not None:
                return _ProjectRegistryAccessContext(
                    summary=member_summary,
                    project_role=member_summary.current_user_role,
                    is_admin=is_admin,
                    is_auditor=is_auditor,
                )

            if is_admin or is_auditor:
                summary = self._project_store.get_project_summary(project_id=project_id)
                if summary is None:
                    raise PseudonymRegistryNotFoundError("Project not found.")
                return _ProjectRegistryAccessContext(
                    summary=summary,
                    project_role=None,
                    is_admin=is_admin,
                    is_auditor=is_auditor,
                )
        except ProjectStoreUnavailableError as error:
            raise PseudonymRegistryStoreUnavailableError(
                "Project access lookup failed."
            ) from error

        raise PseudonymRegistryAccessDeniedError(
            "Project membership is required for this pseudonym registry route."
        )

    @staticmethod
    def _require_read_access(context: _ProjectRegistryAccessContext) -> None:
        if context.is_admin or context.is_auditor:
            return
        if context.project_role == "PROJECT_LEAD":
            return
        raise PseudonymRegistryAccessDeniedError(
            "Current role cannot view pseudonym registry routes in this project."
        )

    @staticmethod
    def _require_generation_access(context: _ProjectRegistryAccessContext) -> None:
        if context.is_admin:
            return
        if context.project_role == "PROJECT_LEAD":
            return
        raise PseudonymRegistryAccessDeniedError(
            "Current role cannot create or rotate pseudonym registry entries."
        )

    @staticmethod
    def _normalize_scope_token(field_name: str, raw: str, *, max_length: int = 120) -> str:
        normalized = _normalized_text(raw)
        if normalized is None:
            raise PseudonymRegistryValidationError(f"{field_name} is required.")
        if len(normalized) > max_length:
            raise PseudonymRegistryValidationError(
                f"{field_name} must be {max_length} characters or fewer."
            )
        return normalized

    @staticmethod
    def _normalize_run_id(raw: str) -> str:
        return PseudonymRegistryService._normalize_scope_token(
            "sourceRunId",
            raw,
            max_length=200,
        )

    def _master_secret_bytes(self) -> bytes:
        secret = self._settings.pseudonym_registry_master_secret.strip()
        if len(secret) < 16:
            raise PseudonymRegistryValidationError(
                "Pseudonym registry master secret must be at least 16 characters."
            )
        return secret.encode("utf-8")

    def _project_scope_secret(self, *, project_id: str, salt_version_ref: str) -> bytes:
        return hmac.new(
            self._master_secret_bytes(),
            f"project-salt:{project_id}:{salt_version_ref}".encode("utf-8"),
            hashlib.sha256,
        ).digest()

    def _fingerprint_source_value(
        self,
        *,
        project_id: str,
        salt_version_ref: str,
        source_value: str,
    ) -> str:
        canonical_source = _canonical_source_value(source_value)
        scope_secret = self._project_scope_secret(
            project_id=project_id,
            salt_version_ref=salt_version_ref,
        )
        return hmac.new(
            scope_secret,
            canonical_source.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _lineage_fingerprint_source_value(
        self,
        *,
        project_id: str,
        source_value: str,
    ) -> str:
        canonical_source = _canonical_source_value(source_value)
        lineage_secret = hmac.new(
            self._master_secret_bytes(),
            f"lineage:{project_id}".encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return hmac.new(
            lineage_secret,
            canonical_source.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _alias_digest(
        self,
        *,
        project_id: str,
        salt_version_ref: str,
        alias_strategy_version: str,
        source_fingerprint_hmac_sha256: str,
    ) -> str:
        alias_scope_secret = hmac.new(
            self._master_secret_bytes(),
            (
                f"alias-scope:{project_id}:{salt_version_ref}:{alias_strategy_version}"
            ).encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return hmac.new(
            alias_scope_secret,
            source_fingerprint_hmac_sha256.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest().upper()

    @staticmethod
    def _alias_candidate(digest: str, attempt: int) -> str:
        base = f"PSN-{digest[:20]}"
        if attempt == 0:
            return base
        start = 20 + (attempt - 1) * 4
        suffix = digest[start : start + 4]
        if len(suffix) < 4:
            suffix = f"{attempt:04X}"
        return f"{base}-{suffix}"

    def _allocate_alias(
        self,
        *,
        project_id: str,
        salt_version_ref: str,
        alias_strategy_version: str,
        source_fingerprint_hmac_sha256: str,
    ) -> str:
        digest = self._alias_digest(
            project_id=project_id,
            salt_version_ref=salt_version_ref,
            alias_strategy_version=alias_strategy_version,
            source_fingerprint_hmac_sha256=source_fingerprint_hmac_sha256,
        )
        for attempt in range(0, 64):
            candidate = self._alias_candidate(digest, attempt)
            conflict = self._store.find_active_entry_by_alias_scope(
                project_id=project_id,
                salt_version_ref=salt_version_ref,
                alias_strategy_version=alias_strategy_version,
                alias_value=candidate,
            )
            if conflict is None:
                return candidate
            if (
                conflict.source_fingerprint_hmac_sha256
                == source_fingerprint_hmac_sha256
            ):
                return candidate
        raise PseudonymRegistryConflictError(
            "Unable to allocate a unique alias value for this project scope."
        )

    def _append_registry_event(
        self,
        *,
        entry_id: str,
        event_type: str,
        run_id: str,
        actor_user_id: str | None,
    ) -> None:
        self._store.append_event(
            event=PseudonymRegistryEntryEventRecord(
                id=str(uuid4()),
                entry_id=entry_id,
                event_type=event_type,  # type: ignore[arg-type]
                run_id=run_id,
                actor_user_id=actor_user_id,
                created_at=self._store.utcnow(),
            )
        )

    def list_entries(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> list[PseudonymRegistryEntryRecord]:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_read_access(context)
        return self._store.list_entries(project_id=project_id)

    def get_entry(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        entry_id: str,
    ) -> PseudonymRegistryEntryRecord:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_read_access(context)
        entry = self._store.get_entry(project_id=project_id, entry_id=entry_id)
        if entry is None:
            raise PseudonymRegistryNotFoundError("Pseudonym registry entry not found.")
        return entry

    def list_entry_events(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        entry_id: str,
    ) -> list[PseudonymRegistryEntryEventRecord]:
        _ = self.get_entry(
            current_user=current_user,
            project_id=project_id,
            entry_id=entry_id,
        )
        return self._store.list_entry_events(project_id=project_id, entry_id=entry_id)

    def register_or_reuse_entry(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        source_run_id: str,
        source_value: str,
        policy_id: str,
        salt_version_ref: str,
        alias_strategy_version: str,
    ) -> PseudonymRegistryEntryRecord:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_generation_access(context)

        normalized_run_id = self._normalize_run_id(source_run_id)
        normalized_policy_id = self._normalize_scope_token("policyId", policy_id, max_length=120)
        normalized_salt_ref = self._normalize_scope_token(
            "saltVersionRef",
            salt_version_ref,
            max_length=120,
        )
        normalized_alias_strategy = self._normalize_scope_token(
            "aliasStrategyVersion",
            alias_strategy_version,
            max_length=80,
        )

        policy = self._policy_store.get_policy(
            project_id=project_id,
            policy_id=normalized_policy_id,
        )
        if policy is None:
            raise PseudonymRegistryNotFoundError(
                "Policy revision for pseudonym scope was not found."
            )

        fingerprint = self._fingerprint_source_value(
            project_id=project_id,
            salt_version_ref=normalized_salt_ref,
            source_value=source_value,
        )
        lineage_fingerprint = self._lineage_fingerprint_source_value(
            project_id=project_id,
            source_value=source_value,
        )

        existing = self._store.find_active_entry_by_tuple(
            project_id=project_id,
            source_fingerprint_hmac_sha256=fingerprint,
            policy_id=normalized_policy_id,
            salt_version_ref=normalized_salt_ref,
            alias_strategy_version=normalized_alias_strategy,
        )
        if existing is not None:
            touched = self._store.touch_entry_usage(
                project_id=project_id,
                entry_id=existing.id,
                last_used_run_id=normalized_run_id,
                updated_at=self._store.utcnow(),
            )
            resolved = touched or existing
            self._append_registry_event(
                entry_id=resolved.id,
                event_type="ENTRY_REUSED",
                run_id=normalized_run_id,
                actor_user_id=current_user.user_id,
            )
            return resolved

        predecessor = self._store.find_latest_lineage_predecessor(
            project_id=project_id,
            lineage_source_fingerprint_hmac_sha256=lineage_fingerprint,
            policy_id=normalized_policy_id,
            salt_version_ref=normalized_salt_ref,
            alias_strategy_version=normalized_alias_strategy,
        )

        alias_value = self._allocate_alias(
            project_id=project_id,
            salt_version_ref=normalized_salt_ref,
            alias_strategy_version=normalized_alias_strategy,
            source_fingerprint_hmac_sha256=fingerprint,
        )

        now = self._store.utcnow()
        created = PseudonymRegistryEntryRecord(
            id=str(uuid4()),
            project_id=project_id,
            source_run_id=normalized_run_id,
            source_fingerprint_hmac_sha256=fingerprint,
            alias_value=alias_value,
            policy_id=normalized_policy_id,
            salt_version_ref=normalized_salt_ref,
            alias_strategy_version=normalized_alias_strategy,
            created_by=current_user.user_id,
            created_at=now,
            last_used_run_id=normalized_run_id,
            updated_at=now,
            status="ACTIVE",
            retired_at=None,
            retired_by=None,
            supersedes_entry_id=predecessor.id if predecessor is not None else None,
            superseded_by_entry_id=None,
        )
        self._store.create_entry(
            record=created,
            lineage_source_fingerprint_hmac_sha256=lineage_fingerprint,
        )
        if predecessor is not None:
            self._store.set_superseded_by(
                project_id=project_id,
                entry_id=predecessor.id,
                superseded_by_entry_id=created.id,
            )
        self._append_registry_event(
            entry_id=created.id,
            event_type="ENTRY_CREATED",
            run_id=normalized_run_id,
            actor_user_id=current_user.user_id,
        )
        return created

    def retire_entry(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        entry_id: str,
        run_id: str,
    ) -> PseudonymRegistryEntryRecord:
        context = self._resolve_project_access(current_user=current_user, project_id=project_id)
        self._require_generation_access(context)

        normalized_run_id = self._normalize_run_id(run_id)
        current = self._store.get_entry(project_id=project_id, entry_id=entry_id)
        if current is None:
            raise PseudonymRegistryNotFoundError("Pseudonym registry entry not found.")
        if current.status != "ACTIVE":
            raise PseudonymRegistryConflictError(
                "Only ACTIVE pseudonym registry entries can be retired."
            )

        retired = self._store.retire_entry(
            project_id=project_id,
            entry_id=entry_id,
            retired_by=current_user.user_id,
            retired_at=self._store.utcnow(),
        )
        if retired is None:
            raise PseudonymRegistryConflictError(
                "Pseudonym registry retirement failed due to concurrent update."
            )

        self._append_registry_event(
            entry_id=retired.id,
            event_type="ENTRY_RETIRED",
            run_id=normalized_run_id,
            actor_user_id=current_user.user_id,
        )
        return retired


@lru_cache
def get_pseudonym_registry_service() -> PseudonymRegistryService:
    settings = get_settings()
    return PseudonymRegistryService(settings=settings)
