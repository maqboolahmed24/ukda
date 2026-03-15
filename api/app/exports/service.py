from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from functools import lru_cache
from typing import Literal, cast
from uuid import uuid4

from app.auth.models import SessionPrincipal
from app.core.config import Settings, get_settings
from app.core.storage_boundaries import resolve_storage_boundary
from app.exports.models import (
    BundleEventRecord,
    BundleProfileRecord,
    BundleValidationProjectionRecord,
    BundleValidationRunRecord,
    BundleVerificationProjectionRecord,
    BundleVerificationRunRecord,
    DepositBundleKind,
    DepositBundleRecord,
    ExportCandidateKind,
    ExportCandidateSnapshotRecord,
    ExportOperationsMaintenanceResult,
    ExportOperationsStatusRecord,
    ProvenanceProofRecord,
    ExportReceiptRecord,
    ExportRequestDecision,
    ExportRequestListPage,
    ExportRequestRecord,
    ExportRequestReviewPath,
    ExportRequestReviewRecord,
    ExportRequestRiskClassification,
    ExportRequestStatus,
    ExportReviewAgingBucket,
    ExportReviewQueueItemRecord,
)
from app.exports.deposit_profiles import get_bundle_profile
from app.exports.store import (
    ExportStore,
    ExportStoreConflictError,
    ExportStoreNotFoundError,
)
from app.exports.validation import build_export_validation_summary
from app.projects.service import (
    ProjectService,
    get_project_service,
)

_ALLOWED_CANDIDATE_VIEW_ROLES = {"RESEARCHER", "PROJECT_LEAD", "REVIEWER", "ADMIN", "AUDITOR"}
_ALLOWED_REQUEST_CREATE_ROLES = {"RESEARCHER", "PROJECT_LEAD", "ADMIN"}
_ALLOWED_REQUEST_PROJECT_READ_ROLES = {"PROJECT_LEAD", "REVIEWER", "ADMIN", "AUDITOR"}
_ALLOWED_REVIEW_QUEUE_ROLES = {"REVIEWER", "ADMIN", "AUDITOR"}
_ALLOWED_REVIEW_MUTATION_ROLES = {"REVIEWER", "ADMIN"}
_OPEN_REVIEWABLE_REQUEST_STATUSES = {"SUBMITTED", "RESUBMITTED", "IN_REVIEW"}
_SPECIAL_CATEGORY_RISK_FLAGS = {"special_category_present", "special-category-present"}
_POLICY_ESCALATION_FLAGS = {"policy_escalation_present", "policy-escalation-present"}
_VALID_REVIEW_DECISIONS = {"APPROVE", "REJECT", "RETURN"}
_VALID_AGING_BUCKETS = {"UNSTARTED", "NO_SLA", "ON_TRACK", "DUE_SOON", "OVERDUE"}
_SHA256_HEX_CHARS = set("0123456789abcdef")
_PROVENANCE_READY_REQUEST_STATUSES = {"APPROVED", "EXPORTED"}
_BUNDLE_MUTATION_SAFE_STATUSES = {"APPROVED", "EXPORTED"}


class ExportAccessDeniedError(RuntimeError):
    """Current role is not authorized for this export action."""


class ExportValidationError(RuntimeError):
    """Payload or filter failed deterministic validation."""


class ExportNotFoundError(RuntimeError):
    """Requested export candidate or request was not found."""


class ExportConflictError(RuntimeError):
    """Export request lineage or status transition is invalid."""


class ExportService:
    def __init__(
        self,
        *,
        settings: Settings,
        store: ExportStore | None = None,
        project_service: ProjectService | None = None,
    ) -> None:
        self._settings = settings
        self._store = store or ExportStore(settings)
        self._project_service = project_service or get_project_service()

    @staticmethod
    def _is_admin(current_user: SessionPrincipal) -> bool:
        return "ADMIN" in set(current_user.platform_roles)

    @staticmethod
    def _is_auditor(current_user: SessionPrincipal) -> bool:
        return "AUDITOR" in set(current_user.platform_roles)

    def _resolve_role(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> str:
        if self._is_admin(current_user):
            # Keep project existence and scope checks consistent with project routes.
            self._project_service.resolve_workspace_context(
                current_user=current_user,
                project_id=project_id,
            )
            return "ADMIN"
        if self._is_auditor(current_user):
            # Auditors are read-only governance observers for requester-side surfaces.
            return "AUDITOR"
        context = self._project_service.resolve_workspace_context(
            current_user=current_user,
            project_id=project_id,
        )
        if not context.is_member:
            raise ExportAccessDeniedError("Membership is required for export routes.")
        role = context.summary.current_user_role
        if role is None:
            raise ExportAccessDeniedError("Membership role is required for export routes.")
        return str(role)

    @staticmethod
    def _sanitize_optional_text(value: str | None, *, max_len: int) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > max_len:
            raise ExportValidationError(f"Value must be {max_len} characters or fewer.")
        return normalized

    @staticmethod
    def _normalize_purpose_statement(value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 12:
            raise ExportValidationError("Purpose statement must be at least 12 characters.")
        if len(normalized) > 3000:
            raise ExportValidationError("Purpose statement must be 3000 characters or fewer.")
        return normalized

    @staticmethod
    def _assert_candidate_kind(value: str | None) -> ExportCandidateKind | None:
        if value is None:
            return None
        if value not in {
            "SAFEGUARDED_PREVIEW",
            "POLICY_RERUN",
            "DEPOSIT_BUNDLE",
            "SAFEGUARDED_DERIVATIVE",
        }:
            raise ExportValidationError("candidateKind is invalid.")
        return cast(ExportCandidateKind, value)

    @staticmethod
    def _assert_request_status(value: str | None) -> ExportRequestStatus | None:
        if value is None:
            return None
        if value not in {
            "SUBMITTED",
            "RESUBMITTED",
            "IN_REVIEW",
            "APPROVED",
            "EXPORTED",
            "REJECTED",
            "RETURNED",
        }:
            raise ExportValidationError("status is invalid.")
        return cast(ExportRequestStatus, value)

    @staticmethod
    def _assert_review_decision(value: str) -> ExportRequestDecision:
        normalized = value.strip().upper()
        if normalized not in _VALID_REVIEW_DECISIONS:
            raise ExportValidationError("decision is invalid.")
        return cast(ExportRequestDecision, normalized)

    @staticmethod
    def _assert_aging_bucket(value: str | None) -> ExportReviewAgingBucket | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if normalized not in _VALID_AGING_BUCKETS:
            raise ExportValidationError("agingBucket is invalid.")
        return cast(ExportReviewAgingBucket, normalized)

    @staticmethod
    def _normalize_review_etag(value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ExportValidationError("reviewEtag is required.")
        return normalized

    @staticmethod
    def _normalize_gateway_receipt_key(value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ExportValidationError("receiptKey is required.")
        if normalized.startswith("/"):
            normalized = normalized.lstrip("/")
        if ".." in normalized.split("/"):
            raise ExportValidationError("receiptKey is invalid.")
        return normalized

    @staticmethod
    def _normalize_gateway_receipt_sha256(value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(ch not in _SHA256_HEX_CHARS for ch in normalized):
            raise ExportValidationError("receiptSha256 must be a 64-character hex digest.")
        return normalized

    def _assert_gateway_export_prefix(self, *, receipt_key: str) -> None:
        boundary = resolve_storage_boundary(self._settings)
        if not boundary.can_write(writer="export_gateway", object_key=receipt_key):
            raise ExportValidationError(
                "receiptKey must resolve under the safeguarded export gateway prefix."
            )
        if boundary.can_write(writer="app", object_key=receipt_key):
            raise ExportValidationError("Non-gateway storage writers cannot attach receipts.")

    @staticmethod
    def _resolve_active_required_review(
        reviews: tuple[ExportRequestReviewRecord, ...],
    ) -> ExportRequestReviewRecord | None:
        ordered = sorted(
            reviews,
            key=lambda item: (
                1 if item.review_stage == "PRIMARY" else 2,
                item.created_at,
                item.id,
            ),
        )
        for review in ordered:
            if not review.is_required:
                continue
            if review.status == "APPROVED":
                continue
            if review.status in {"RETURNED", "REJECTED"}:
                return None
            return review
        return None

    @staticmethod
    def _classify_aging(
        request: ExportRequestRecord,
        *,
        now: datetime,
    ) -> tuple[ExportReviewAgingBucket, int | None, bool]:
        if request.sla_due_at is None:
            if request.first_review_started_at is None:
                return "UNSTARTED", None, False
            return "NO_SLA", None, False
        remaining_seconds = int((request.sla_due_at - now).total_seconds())
        if remaining_seconds < 0:
            return "OVERDUE", remaining_seconds, True
        if request.first_review_started_at is None:
            return "UNSTARTED", remaining_seconds, False
        if remaining_seconds <= 24 * 60 * 60:
            return "DUE_SOON", remaining_seconds, False
        return "ON_TRACK", remaining_seconds, False

    @staticmethod
    def _sanitize_reference(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.startswith("/"):
            return normalized.split("/")[-1] or None
        if ".ukde-storage" in normalized:
            return normalized.split("/")[-1] or None
        return normalized

    @staticmethod
    def _canonical_json_bytes(payload: dict[str, object]) -> bytes:
        return json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    @staticmethod
    def _sha256_hex(payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _extract_manifest_list(payload: dict[str, object], *keys: str) -> list[dict[str, object]]:
        for key in keys:
            raw = payload.get(key)
            if not isinstance(raw, list):
                continue
            items: list[dict[str, object]] = []
            for entry in raw:
                if isinstance(entry, dict):
                    items.append(dict(entry))
            return items
        return []

    def _extract_release_pack_files(
        self,
        *,
        candidate: ExportCandidateSnapshotRecord,
    ) -> list[dict[str, object]]:
        manifest = candidate.artefact_manifest_json
        file_entries = self._extract_manifest_list(manifest, "fileList", "files")
        if not file_entries:
            output_entries = self._extract_manifest_list(manifest, "outputs")
            normalized_outputs: list[dict[str, object]] = []
            for output in output_entries:
                source_ref = self._sanitize_reference(
                    output.get("safeguardedPreviewKey") or output.get("sourceRef")
                )
                sha = output.get("previewSha256") or output.get("sha256")
                if not isinstance(sha, str) or not sha.strip():
                    continue
                page_index = output.get("pageIndex")
                page_label = (
                    f"page-{int(page_index) + 1:04d}.png"
                    if isinstance(page_index, int)
                    else "redacted-page.png"
                )
                normalized_outputs.append(
                    {
                        "fileName": page_label,
                        "fileSizeBytes": 0,
                        "sha256": sha.strip(),
                        "sourceRef": source_ref,
                        "sourceKind": "SAFEGUARDED_PREVIEW_PAGE",
                    }
                )
            file_entries = normalized_outputs

        normalized_files: list[dict[str, object]] = []
        for item in file_entries:
            file_name = (
                str(item.get("fileName")).strip()
                if isinstance(item.get("fileName"), str)
                else (
                    str(item.get("name")).strip() if isinstance(item.get("name"), str) else ""
                )
            )
            if not file_name:
                file_name = "candidate-artifact"
            sha256 = (
                str(item.get("sha256")).strip()
                if isinstance(item.get("sha256"), str)
                else (
                    str(item.get("hash")).strip() if isinstance(item.get("hash"), str) else ""
                )
            )
            if not sha256:
                continue
            size = item.get("fileSizeBytes")
            if not isinstance(size, int):
                size = item.get("sizeBytes")
            if not isinstance(size, int):
                size = item.get("size")
            size_bytes = int(size) if isinstance(size, int) and size >= 0 else 0
            source_ref = self._sanitize_reference(
                item.get("sourceRef")
                or item.get("reference")
                or item.get("objectKey")
                or item.get("key")
            )
            source_kind = (
                str(item.get("sourceKind")).strip()
                if isinstance(item.get("sourceKind"), str)
                else "CANDIDATE_FILE"
            )
            normalized_files.append(
                {
                    "fileName": file_name,
                    "fileSizeBytes": size_bytes,
                    "sha256": sha256,
                    "sourceRef": source_ref,
                    "sourceKind": source_kind,
                }
            )
        return normalized_files

    def _extract_redaction_counts(
        self,
        *,
        candidate: ExportCandidateSnapshotRecord,
    ) -> dict[str, int]:
        manifest = candidate.artefact_manifest_json
        raw_counts = manifest.get("redactionCountsByCategory") or manifest.get("categoryCounts")
        counts: dict[str, int] = {}
        if isinstance(raw_counts, dict):
            for key, value in raw_counts.items():
                if not isinstance(key, str):
                    continue
                if isinstance(value, bool):
                    continue
                if not isinstance(value, int):
                    continue
                if value < 0:
                    continue
                counts[key] = int(value)
            if counts:
                return counts

        entries = self._extract_manifest_list(manifest, "entries", "findings")
        derived: dict[str, int] = {}
        for entry in entries:
            category = entry.get("category")
            if not isinstance(category, str):
                continue
            key = category.strip()
            if not key:
                continue
            derived[key] = derived.get(key, 0) + 1
        return derived

    def _extract_override_count(self, *, candidate: ExportCandidateSnapshotRecord) -> int:
        manifest = candidate.artefact_manifest_json
        raw_value = manifest.get("reviewerOverrideCount") or manifest.get("overrideCount")
        if isinstance(raw_value, int) and raw_value >= 0:
            return int(raw_value)

        entries = self._extract_manifest_list(manifest, "entries", "findings")
        return sum(
            1
            for entry in entries
            if isinstance(entry.get("decisionStatus"), str)
            and str(entry["decisionStatus"]).strip().upper() == "OVERRIDDEN"
        )

    def _extract_conservative_area_mask_count(
        self,
        *,
        candidate: ExportCandidateSnapshotRecord,
    ) -> int:
        manifest = candidate.artefact_manifest_json
        raw_value = manifest.get("conservativeAreaMaskCount") or manifest.get("areaMaskCount")
        if isinstance(raw_value, int) and raw_value >= 0:
            return int(raw_value)

        entries = self._extract_manifest_list(manifest, "entries", "findings")
        count = 0
        for entry in entries:
            if isinstance(entry.get("areaMaskId"), str) and str(entry["areaMaskId"]).strip():
                count += 1
        return count

    def _extract_risk_flags(self, *, candidate: ExportCandidateSnapshotRecord) -> list[str]:
        manifest = candidate.artefact_manifest_json
        flags: list[str] = []
        raw_flags = manifest.get("riskFlags")
        if isinstance(raw_flags, list):
            for value in raw_flags:
                if not isinstance(value, str):
                    continue
                normalized = value.strip().lower()
                if not normalized or normalized in flags:
                    continue
                flags.append(normalized)

        if bool(manifest.get("specialCategoryFlag")) and "special_category_present" not in flags:
            flags.append("special_category_present")
        if bool(manifest.get("indirectRiskFlag")) and "indirect_risk_present" not in flags:
            flags.append("indirect_risk_present")
        if bool(manifest.get("policyEscalationFlag")) and "policy_escalation_present" not in flags:
            flags.append("policy_escalation_present")
        return flags

    def _bundle_profile_requires_dual_review(
        self,
        *,
        bundle_profile: str | None,
        candidate: ExportCandidateSnapshotRecord,
    ) -> bool:
        normalized_profile = self._sanitize_optional_text(bundle_profile, max_len=160)
        if normalized_profile is None:
            return False

        profile_rules = candidate.artefact_manifest_json.get("bundleProfileRules")
        if isinstance(profile_rules, dict):
            raw_profile_rule = profile_rules.get(normalized_profile)
            if isinstance(raw_profile_rule, dict) and bool(
                raw_profile_rule.get("requiresDualReview")
            ):
                return True

        upper = normalized_profile.upper()
        if upper in {"DUAL_REVIEW", "HIGH_RISK", "DEPOSIT_BUNDLE"}:
            return True
        return "DUAL" in upper

    def _classify_risk(
        self,
        *,
        candidate: ExportCandidateSnapshotRecord,
        bundle_profile: str | None,
        reviewer_override_count: int,
        conservative_area_mask_count: int,
        risk_flags: list[str],
    ) -> tuple[ExportRequestRiskClassification, tuple[str, ...], ExportRequestReviewPath, bool]:
        reason_codes: list[str] = []
        if candidate.candidate_kind in {"DEPOSIT_BUNDLE", "SAFEGUARDED_DERIVATIVE"}:
            reason_codes.append("candidate_kind_requires_dual_review")
        if reviewer_override_count > 0:
            reason_codes.append("manual_overrides_present")
        if conservative_area_mask_count > 0:
            reason_codes.append("conservative_area_mask_present")

        lowered_flags = {flag.lower() for flag in risk_flags}
        if any(flag in _SPECIAL_CATEGORY_RISK_FLAGS for flag in lowered_flags):
            reason_codes.append("special_category_flag_present")
        if any("indirect" in flag for flag in lowered_flags):
            reason_codes.append("indirect_risk_flag_present")
        if any(flag in _POLICY_ESCALATION_FLAGS for flag in lowered_flags):
            reason_codes.append("policy_escalation_flag_present")
        if self._bundle_profile_requires_dual_review(
            bundle_profile=bundle_profile,
            candidate=candidate,
        ):
            reason_codes.append("bundle_profile_requires_dual_review")

        deduped_reason_codes: list[str] = []
        for code in reason_codes:
            if code in deduped_reason_codes:
                continue
            deduped_reason_codes.append(code)
        is_high = len(deduped_reason_codes) > 0
        risk_classification: ExportRequestRiskClassification = "HIGH" if is_high else "STANDARD"
        review_path: ExportRequestReviewPath = "DUAL" if is_high else "SINGLE"
        requires_second_review = is_high
        return risk_classification, tuple(deduped_reason_codes), review_path, requires_second_review

    def _build_release_pack(
        self,
        *,
        candidate: ExportCandidateSnapshotRecord,
        request_scope: Literal["CANDIDATE_PREVIEW", "REQUEST_FROZEN"],
        request_revision: int,
        purpose_statement: str,
        bundle_profile: str | None,
        request_id: str | None,
    ) -> tuple[
        dict[str, object],
        str,
        str,
        ExportRequestRiskClassification,
        tuple[str, ...],
        ExportRequestReviewPath,
        bool,
    ]:
        files = self._extract_release_pack_files(candidate=candidate)
        redaction_counts = self._extract_redaction_counts(candidate=candidate)
        reviewer_override_count = self._extract_override_count(candidate=candidate)
        conservative_area_mask_count = self._extract_conservative_area_mask_count(
            candidate=candidate
        )
        risk_flags = self._extract_risk_flags(candidate=candidate)

        (
            risk_classification,
            reason_codes,
            review_path,
            requires_second_review,
        ) = self._classify_risk(
            candidate=candidate,
            bundle_profile=bundle_profile,
            reviewer_override_count=reviewer_override_count,
            conservative_area_mask_count=conservative_area_mask_count,
            risk_flags=risk_flags,
        )

        source_references = self._extract_manifest_list(
            candidate.artefact_manifest_json,
            "sourceArtefactReferences",
            "sourceArtifactReferences",
        )
        approved_models = candidate.artefact_manifest_json.get("approvedModelReferencesByRole")
        approved_model_references = (
            dict(approved_models) if isinstance(approved_models, dict) else {}
        )
        manifest_integrity_sha = self._sha256_hex(
            self._canonical_json_bytes(candidate.artefact_manifest_json)
        )

        payload: dict[str, object] = {
            "schemaVersion": 1,
            "requestScope": request_scope,
            "candidateSnapshotId": candidate.id,
            "candidateSha256": candidate.candidate_sha256,
            "candidateKind": candidate.candidate_kind,
            "candidateSourcePhase": candidate.source_phase,
            "candidateSourceArtifactKind": candidate.source_artifact_kind,
            "candidateSourceArtifactId": candidate.source_artifact_id,
            "candidateSourceRunId": candidate.source_run_id,
            "requestRevision": request_revision,
            "requestPurposeStatement": purpose_statement,
            "bundleProfile": bundle_profile,
            "files": files,
            "fileCount": len(files),
            "sourceArtefactReferences": source_references,
            "manifestIntegrity": {
                "artefactManifestSha256": manifest_integrity_sha,
                "status": "MATCHED_CANDIDATE_SNAPSHOT",
            },
            "policyLineage": {
                "policySnapshotHash": candidate.policy_snapshot_hash,
                "policyId": candidate.policy_id,
                "policyFamilyId": candidate.policy_family_id,
                "policyVersion": candidate.policy_version,
            },
            "approvedModelReferencesByRole": approved_model_references,
            "redactionCountsByCategory": redaction_counts,
            "reviewerOverrideCount": reviewer_override_count,
            "conservativeAreaMaskCount": conservative_area_mask_count,
            "riskFlags": risk_flags,
            "classifierReasonCodes": list(reason_codes),
            "riskClassification": risk_classification,
            "reviewPath": review_path,
            "requiresSecondReview": requires_second_review,
            "governancePins": {
                "governanceRunId": candidate.governance_run_id,
                "governanceManifestId": candidate.governance_manifest_id,
                "governanceLedgerId": candidate.governance_ledger_id,
                "governanceManifestSha256": candidate.governance_manifest_sha256,
                "governanceLedgerSha256": candidate.governance_ledger_sha256,
            },
            "releaseReviewChecklist": [
                "candidate_snapshot_is_immutable",
                "governance_manifest_and_ledger_are_pinned",
                "policy_lineage_is_pinned",
                "risk_classification_is_pinned_at_submission",
            ],
        }
        if request_id is not None:
            payload["requestId"] = request_id

        payload_bytes = self._canonical_json_bytes(payload)
        payload_sha256 = self._sha256_hex(payload_bytes)
        if request_scope == "REQUEST_FROZEN":
            if request_id is None:
                raise ExportValidationError("Request-scoped release packs require requestId.")
            key = f"exports/requests/{request_id}/release-pack/{payload_sha256}.json"
        else:
            key = (
                f"exports/candidates/{candidate.id}/release-pack-preview/{request_revision}/"
                f"{payload_sha256}.json"
            )
        return (
            payload,
            payload_sha256,
            key,
            risk_classification,
            reason_codes,
            review_path,
            requires_second_review,
        )

    def _ensure_request_read_allowed(
        self,
        *,
        role: str,
        current_user: SessionPrincipal,
        request: ExportRequestRecord,
    ) -> None:
        if role in _ALLOWED_REQUEST_PROJECT_READ_ROLES:
            return
        if role == "RESEARCHER" and request.submitted_by == current_user.user_id:
            return
        raise ExportAccessDeniedError("Current role cannot view this export request.")

    def _ensure_request_mutation_allowed(
        self,
        *,
        role: str,
        current_user: SessionPrincipal,
        request: ExportRequestRecord,
    ) -> None:
        if role in {"PROJECT_LEAD", "ADMIN"}:
            return
        if role == "RESEARCHER" and request.submitted_by == current_user.user_id:
            return
        raise ExportAccessDeniedError(
            "Current role cannot mutate this export request revision lineage."
        )

    @staticmethod
    def _ensure_provenance_status_allowed(*, request: ExportRequestRecord) -> None:
        if request.status in _PROVENANCE_READY_REQUEST_STATUSES:
            return
        raise ExportConflictError(
            "Provenance is available only for APPROVED or EXPORTED request lineages."
        )

    def _ensure_provenance_read_allowed(
        self,
        *,
        role: str,
        current_user: SessionPrincipal,
        request: ExportRequestRecord,
    ) -> None:
        self._ensure_request_read_allowed(
            role=role,
            current_user=current_user,
            request=request,
        )
        self._ensure_provenance_status_allowed(request=request)

    @staticmethod
    def _assert_bundle_kind(value: str) -> DepositBundleKind:
        normalized = value.strip().upper()
        if normalized not in {"CONTROLLED_EVIDENCE", "SAFEGUARDED_DEPOSIT"}:
            raise ExportValidationError("bundleKind is invalid.")
        return cast(DepositBundleKind, normalized)

    @staticmethod
    def _ensure_bundle_status_allowed(*, request: ExportRequestRecord) -> None:
        if request.status in _BUNDLE_MUTATION_SAFE_STATUSES:
            return
        raise ExportConflictError(
            "Deposit bundles are available only for APPROVED or EXPORTED request lineages."
        )

    def _ensure_bundle_build_allowed(
        self,
        *,
        role: str,
        bundle_kind: DepositBundleKind,
    ) -> None:
        if bundle_kind == "CONTROLLED_EVIDENCE":
            if role == "ADMIN":
                return
            raise ExportAccessDeniedError(
                "Only ADMIN can build controlled evidence deposit bundles."
            )
        if role in {"PROJECT_LEAD", "REVIEWER", "ADMIN"}:
            return
        raise ExportAccessDeniedError(
            "Only PROJECT_LEAD, REVIEWER, or ADMIN can build safeguarded deposit bundles."
        )

    def _ensure_bundle_read_allowed(
        self,
        *,
        role: str,
        current_user: SessionPrincipal,
        request: ExportRequestRecord,
        bundle_kind: DepositBundleKind,
    ) -> None:
        self._ensure_bundle_status_allowed(request=request)
        if bundle_kind == "CONTROLLED_EVIDENCE":
            if role in {"ADMIN", "AUDITOR"}:
                return
            raise ExportAccessDeniedError(
                "Controlled evidence bundles are limited to ADMIN and AUDITOR."
            )
        self._ensure_request_read_allowed(
            role=role,
            current_user=current_user,
            request=request,
        )

    def _ensure_bundle_mutation_allowed(
        self,
        *,
        role: str,
        bundle_kind: DepositBundleKind,
    ) -> None:
        self._ensure_bundle_build_allowed(role=role, bundle_kind=bundle_kind)

    @staticmethod
    def _ensure_bundle_verification_start_allowed(*, role: str) -> None:
        if role == "ADMIN":
            return
        raise ExportAccessDeniedError("Only ADMIN can start bundle verification.")

    @staticmethod
    def _ensure_bundle_verification_cancel_allowed(*, role: str) -> None:
        if role == "ADMIN":
            return
        raise ExportAccessDeniedError("Only ADMIN can cancel bundle verification runs.")

    @staticmethod
    def _ensure_bundle_validation_start_allowed(*, role: str) -> None:
        if role == "ADMIN":
            return
        raise ExportAccessDeniedError("Only ADMIN can start bundle validation.")

    @staticmethod
    def _ensure_bundle_validation_cancel_allowed(*, role: str) -> None:
        if role == "ADMIN":
            return
        raise ExportAccessDeniedError("Only ADMIN can cancel bundle validation runs.")

    @staticmethod
    def _normalize_bundle_profile_id(value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ExportValidationError("profile is required.")
        try:
            _ = get_bundle_profile(profile_id=normalized)
        except ValueError as error:
            raise ExportValidationError(str(error)) from error
        return normalized

    @staticmethod
    def _ensure_review_mutation_allowed(*, role: str) -> None:
        if role in _ALLOWED_REVIEW_MUTATION_ROLES:
            return
        raise ExportAccessDeniedError("Current role cannot mutate export review stages.")

    @staticmethod
    def _ensure_operations_read_allowed(*, current_user: SessionPrincipal) -> None:
        roles = set(current_user.platform_roles)
        if "ADMIN" in roles or "AUDITOR" in roles:
            return
        raise ExportAccessDeniedError(
            "Current role cannot read export operations status."
        )

    @staticmethod
    def _ensure_operations_maintenance_allowed(*, current_user: SessionPrincipal) -> None:
        if "ADMIN" in set(current_user.platform_roles):
            return
        raise ExportAccessDeniedError(
            "Current role cannot run export operations maintenance."
        )

    def _validate_candidate_eligible(
        self,
        *,
        project_id: str,
        candidate_id: str,
    ) -> ExportCandidateSnapshotRecord:
        try:
            candidate = self._store.get_candidate(
                project_id=project_id,
                candidate_id=candidate_id,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error

        if candidate.eligibility_status != "ELIGIBLE":
            raise ExportValidationError("Only ELIGIBLE candidate snapshots can be requested.")

        visible_eligible_ids = {
            item.id
            for item in self._store.list_candidates(
                project_id=project_id,
                include_superseded=False,
            )
        }
        if candidate.id not in visible_eligible_ids:
            raise ExportValidationError("Candidate snapshot has been superseded.")
        return candidate

    def list_export_candidates(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
    ) -> tuple[ExportCandidateSnapshotRecord, ...]:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        if role not in _ALLOWED_CANDIDATE_VIEW_ROLES:
            raise ExportAccessDeniedError("Current role cannot list export candidates.")
        self._store.sync_phase6_candidate_snapshots(
            project_id=project_id,
            actor_user_id=current_user.user_id,
        )
        return self._store.list_candidates(project_id=project_id, include_superseded=False)

    def get_export_candidate(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        candidate_id: str,
    ) -> ExportCandidateSnapshotRecord:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        if role not in _ALLOWED_CANDIDATE_VIEW_ROLES:
            raise ExportAccessDeniedError("Current role cannot read export candidates.")
        self._store.sync_phase6_candidate_snapshots(
            project_id=project_id,
            actor_user_id=current_user.user_id,
        )
        try:
            return self._store.get_candidate(project_id=project_id, candidate_id=candidate_id)
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error

    def get_candidate_release_pack_preview(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        candidate_id: str,
        purpose_statement: str | None = None,
        bundle_profile: str | None = None,
    ) -> dict[str, object]:
        candidate = self.get_export_candidate(
            current_user=current_user,
            project_id=project_id,
            candidate_id=candidate_id,
        )
        normalized_purpose = (
            self._normalize_purpose_statement(purpose_statement)
            if isinstance(purpose_statement, str)
            else "Preview-only release pack for requester submission planning."
        )
        normalized_bundle_profile = self._sanitize_optional_text(bundle_profile, max_len=160)
        (
            payload,
            sha256,
            key,
            risk_classification,
            reason_codes,
            review_path,
            requires_second_review,
        ) = self._build_release_pack(
            candidate=candidate,
            request_scope="CANDIDATE_PREVIEW",
            request_revision=1,
            purpose_statement=normalized_purpose,
            bundle_profile=normalized_bundle_profile,
            request_id=None,
        )
        return {
            "candidate": candidate,
            "releasePack": payload,
            "releasePackSha256": sha256,
            "releasePackKey": key,
            "riskClassification": risk_classification,
            "riskReasonCodes": reason_codes,
            "reviewPath": review_path,
            "requiresSecondReview": requires_second_review,
        }

    def create_export_request(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        candidate_snapshot_id: str,
        purpose_statement: str,
        bundle_profile: str | None,
    ) -> ExportRequestRecord:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        if role not in _ALLOWED_REQUEST_CREATE_ROLES:
            raise ExportAccessDeniedError("Current role cannot submit export requests.")

        normalized_purpose_statement = self._normalize_purpose_statement(purpose_statement)
        normalized_bundle_profile = self._sanitize_optional_text(bundle_profile, max_len=160)
        self._store.sync_phase6_candidate_snapshots(
            project_id=project_id,
            actor_user_id=current_user.user_id,
        )
        candidate = self._validate_candidate_eligible(
            project_id=project_id,
            candidate_id=candidate_snapshot_id,
        )

        request_id = str(uuid4())
        (
            release_pack_json,
            release_pack_sha256,
            release_pack_key,
            risk_classification,
            risk_reason_codes,
            review_path,
            requires_second_review,
        ) = self._build_release_pack(
            candidate=candidate,
            request_scope="REQUEST_FROZEN",
            request_revision=1,
            purpose_statement=normalized_purpose_statement,
            bundle_profile=normalized_bundle_profile,
            request_id=request_id,
        )

        try:
            return self._store.create_request(
                request_id=request_id,
                project_id=project_id,
                candidate_snapshot_id=candidate.id,
                candidate_origin_phase=candidate.source_phase,
                candidate_kind=candidate.candidate_kind,
                bundle_profile=normalized_bundle_profile,
                risk_classification=risk_classification,
                risk_reason_codes_json=risk_reason_codes,
                review_path=review_path,
                requires_second_review=requires_second_review,
                supersedes_export_request_id=None,
                request_revision=1,
                purpose_statement=normalized_purpose_statement,
                status="SUBMITTED",
                submitted_by=current_user.user_id,
                release_pack_key=release_pack_key,
                release_pack_sha256=release_pack_sha256,
                release_pack_json=release_pack_json,
            )
        except ExportStoreConflictError as error:
            raise ExportConflictError(str(error)) from error

    def resubmit_export_request(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        candidate_snapshot_id: str | None = None,
        purpose_statement: str | None = None,
        bundle_profile: str | None = None,
    ) -> ExportRequestRecord:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        if role not in _ALLOWED_REQUEST_CREATE_ROLES:
            raise ExportAccessDeniedError("Current role cannot resubmit export requests.")

        try:
            predecessor = self._store.get_request(
                project_id=project_id,
                export_request_id=export_request_id,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error

        self._ensure_request_mutation_allowed(
            role=role,
            current_user=current_user,
            request=predecessor,
        )
        if predecessor.status != "RETURNED":
            raise ExportConflictError("Only RETURNED requests can be resubmitted.")
        if predecessor.superseded_by_export_request_id is not None:
            raise ExportConflictError("Returned request has already been superseded.")

        target_candidate_id = candidate_snapshot_id or predecessor.candidate_snapshot_id
        self._store.sync_phase6_candidate_snapshots(
            project_id=project_id,
            actor_user_id=current_user.user_id,
        )
        candidate = self._validate_candidate_eligible(
            project_id=project_id,
            candidate_id=target_candidate_id,
        )
        normalized_purpose_statement = (
            self._normalize_purpose_statement(purpose_statement)
            if isinstance(purpose_statement, str)
            else predecessor.purpose_statement
        )
        normalized_bundle_profile = self._sanitize_optional_text(bundle_profile, max_len=160)
        if normalized_bundle_profile is None:
            normalized_bundle_profile = predecessor.bundle_profile

        request_id = str(uuid4())
        request_revision = predecessor.request_revision + 1
        (
            release_pack_json,
            release_pack_sha256,
            release_pack_key,
            risk_classification,
            risk_reason_codes,
            review_path,
            requires_second_review,
        ) = self._build_release_pack(
            candidate=candidate,
            request_scope="REQUEST_FROZEN",
            request_revision=request_revision,
            purpose_statement=normalized_purpose_statement,
            bundle_profile=normalized_bundle_profile,
            request_id=request_id,
        )
        try:
            return self._store.create_request(
                request_id=request_id,
                project_id=project_id,
                candidate_snapshot_id=candidate.id,
                candidate_origin_phase=candidate.source_phase,
                candidate_kind=candidate.candidate_kind,
                bundle_profile=normalized_bundle_profile,
                risk_classification=risk_classification,
                risk_reason_codes_json=risk_reason_codes,
                review_path=review_path,
                requires_second_review=requires_second_review,
                supersedes_export_request_id=predecessor.id,
                request_revision=request_revision,
                purpose_statement=normalized_purpose_statement,
                status="RESUBMITTED",
                submitted_by=current_user.user_id,
                release_pack_key=release_pack_key,
                release_pack_sha256=release_pack_sha256,
                release_pack_json=release_pack_json,
            )
        except ExportStoreConflictError as error:
            raise ExportConflictError(str(error)) from error

    def list_export_requests(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        status: str | None = None,
        requester_id: str | None = None,
        candidate_kind: str | None = None,
        cursor: int = 0,
        limit: int = 50,
    ) -> ExportRequestListPage:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        if role not in _ALLOWED_CANDIDATE_VIEW_ROLES:
            raise ExportAccessDeniedError("Current role cannot list export requests.")

        normalized_status = self._assert_request_status(
            self._sanitize_optional_text(status, max_len=32)
        )
        normalized_requester_id = self._sanitize_optional_text(requester_id, max_len=128)
        normalized_candidate_kind = self._assert_candidate_kind(
            self._sanitize_optional_text(candidate_kind, max_len=64)
        )
        if role == "RESEARCHER":
            if (
                normalized_requester_id is not None
                and normalized_requester_id != current_user.user_id
            ):
                raise ExportAccessDeniedError(
                    "Researchers can only list their own export requests."
                )
            normalized_requester_id = current_user.user_id

        normalized_limit = max(1, min(limit, 100))
        normalized_cursor = max(0, cursor)
        return self._store.list_requests(
            project_id=project_id,
            status=normalized_status,
            requester_id=normalized_requester_id,
            candidate_kind=normalized_candidate_kind,
            cursor=normalized_cursor,
            limit=normalized_limit,
        )

    def get_export_request(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
    ) -> ExportRequestRecord:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        try:
            record = self._store.get_request(
                project_id=project_id,
                export_request_id=export_request_id,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error
        self._ensure_request_read_allowed(
            role=role,
            current_user=current_user,
            request=record,
        )
        return record

    def get_export_request_status(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
    ) -> dict[str, object]:
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        return {
            "id": request.id,
            "status": request.status,
            "riskClassification": request.risk_classification,
            "reviewPath": request.review_path,
            "requiresSecondReview": request.requires_second_review,
            "requestRevision": request.request_revision,
            "submittedAt": request.submitted_at,
            "lastQueueActivityAt": request.last_queue_activity_at,
            "slaDueAt": request.sla_due_at,
            "retentionUntil": request.retention_until,
            "finalDecisionAt": request.final_decision_at,
            "finalDecisionBy": request.final_decision_by,
            "finalDecisionReason": request.final_decision_reason,
            "finalReturnComment": request.final_return_comment,
            "exportedAt": request.exported_at,
        }

    def get_export_request_release_pack(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
    ) -> dict[str, object]:
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        return {
            "requestId": request.id,
            "requestRevision": request.request_revision,
            "releasePack": request.release_pack_json,
            "releasePackSha256": request.release_pack_sha256,
            "releasePackKey": request.release_pack_key,
            "releasePackCreatedAt": request.release_pack_created_at,
        }

    def get_export_request_validation_summary(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
    ) -> dict[str, object]:
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        candidate: ExportCandidateSnapshotRecord | None
        try:
            candidate = self._store.get_candidate(
                project_id=project_id,
                candidate_id=request.candidate_snapshot_id,
            )
        except ExportStoreNotFoundError:
            candidate = None

        expected_release_pack: dict[str, object] | None = None
        expected_release_pack_sha256: str | None = None
        expected_release_pack_key: str | None = None
        if candidate is not None:
            (
                expected_release_pack,
                expected_release_pack_sha256,
                expected_release_pack_key,
                _,
                _,
                _,
                _,
            ) = self._build_release_pack(
                candidate=candidate,
                request_scope="REQUEST_FROZEN",
                request_revision=request.request_revision,
                purpose_statement=request.purpose_statement,
                bundle_profile=request.bundle_profile,
                request_id=request.id,
            )

        request_events = self._store.list_request_events(export_request_id=request.id)
        reviews = self._store.list_request_reviews(export_request_id=request.id)
        review_events = self._store.list_request_review_events(export_request_id=request.id)
        receipts = self._store.list_request_receipts(
            project_id=project_id,
            export_request_id=request.id,
        )
        summary = build_export_validation_summary(
            request=request,
            candidate=candidate,
            expected_release_pack=expected_release_pack,
            expected_release_pack_sha256=expected_release_pack_sha256,
            expected_release_pack_key=expected_release_pack_key,
            request_events=request_events,
            reviews=reviews,
            review_events=review_events,
            receipts=receipts,
        )
        return summary.to_payload()

    def get_export_request_events(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
    ) -> tuple:
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        return self._store.list_request_events(export_request_id=request.id)

    def get_export_request_reviews(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
    ) -> tuple:
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        return self._store.list_request_reviews(export_request_id=request.id)

    def get_export_request_review_events(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
    ) -> tuple:
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        return self._store.list_request_review_events(export_request_id=request.id)

    def get_export_request_receipt(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
    ) -> ExportReceiptRecord:
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        if request.receipt_id is None:
            raise ExportNotFoundError("Export request has no attached receipt.")
        receipts = self._store.list_request_receipts(
            project_id=project_id,
            export_request_id=export_request_id,
        )
        match = next((item for item in receipts if item.id == request.receipt_id), None)
        if match is None:
            raise ExportNotFoundError("Export request receipt lineage is unavailable.")
        return match

    def list_export_request_receipts(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
    ) -> tuple[ExportReceiptRecord, ...]:
        _ = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        return self._store.list_request_receipts(
            project_id=project_id,
            export_request_id=export_request_id,
        )

    def _extract_lineage_nodes(
        self,
        *,
        proof_artifact: dict[str, object],
    ) -> tuple[dict[str, object], ...]:
        raw = proof_artifact.get("leaves")
        if not isinstance(raw, list):
            return ()
        nodes: list[dict[str, object]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            artifact_kind = item.get("artifact_kind")
            stable_identifier = item.get("stable_identifier")
            immutable_reference = item.get("immutable_reference")
            parent_references = item.get("parent_references")
            if not isinstance(artifact_kind, str):
                continue
            if not isinstance(stable_identifier, str):
                continue
            if not isinstance(immutable_reference, str):
                continue
            parent_items: list[str] = []
            if isinstance(parent_references, list):
                for value in parent_references:
                    if not isinstance(value, str):
                        continue
                    normalized = value.strip()
                    if not normalized or normalized in parent_items:
                        continue
                    parent_items.append(normalized)
            nodes.append(
                {
                    "artifactKind": artifact_kind,
                    "stableIdentifier": stable_identifier,
                    "immutableReference": immutable_reference,
                    "parentReferences": parent_items,
                }
            )
        return tuple(nodes)

    def _read_proof_payload(self, *, proof: ProvenanceProofRecord) -> dict[str, object]:
        return self._store.read_provenance_proof_artifact(proof=proof)

    def _ensure_initial_proof_exists(
        self,
        *,
        project_id: str,
        export_request_id: str,
        actor_user_id: str,
    ) -> tuple[ProvenanceProofRecord, ...]:
        proofs = self._store.list_provenance_proofs(
            project_id=project_id,
            export_request_id=export_request_id,
        )
        if proofs:
            return proofs
        try:
            created = self._store.generate_provenance_proof(
                project_id=project_id,
                export_request_id=export_request_id,
                actor_user_id=actor_user_id,
                force_regenerate=False,
            )
        except ExportStoreConflictError as error:
            raise ExportConflictError(str(error)) from error
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error
        return (created,)

    def get_export_request_provenance_summary(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
    ) -> dict[str, object]:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        self._ensure_provenance_read_allowed(
            role=role,
            current_user=current_user,
            request=request,
        )
        try:
            candidate = self._store.get_candidate(
                project_id=project_id,
                candidate_id=request.candidate_snapshot_id,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error

        proof_attempts = self._ensure_initial_proof_exists(
            project_id=project_id,
            export_request_id=export_request_id,
            actor_user_id=current_user.user_id,
        )
        current_proof: ProvenanceProofRecord | None
        lineage_nodes: tuple[dict[str, object], ...]
        current_proof_generated_at: str | None
        if not proof_attempts:
            current_proof = None
            lineage_nodes = ()
            current_proof_generated_at = None
        else:
            try:
                current_proof = self._store.get_current_provenance_proof(
                    project_id=project_id,
                    export_request_id=export_request_id,
                )
            except ExportStoreNotFoundError:
                current_proof = proof_attempts[0]
            current_payload = self._read_proof_payload(proof=current_proof)
            lineage_nodes = self._extract_lineage_nodes(proof_artifact=current_payload)
            current_proof_generated_at = current_proof.created_at.isoformat()

        return {
            "projectId": project_id,
            "requestId": request.id,
            "requestStatus": request.status,
            "candidateSnapshotId": request.candidate_snapshot_id,
            "proofAttemptCount": len(proof_attempts),
            "currentProofId": current_proof.id if current_proof is not None else None,
            "currentAttemptNumber": (
                current_proof.attempt_number if current_proof is not None else None
            ),
            "currentProofGeneratedAt": current_proof_generated_at,
            "rootSha256": current_proof.root_sha256 if current_proof is not None else None,
            "signatureKeyRef": (
                current_proof.signature_key_ref if current_proof is not None else None
            ),
            "signatureStatus": "SIGNED" if current_proof is not None else "MISSING",
            "lineageNodes": list(lineage_nodes),
            "references": {
                "manifestId": candidate.governance_manifest_id,
                "ledgerId": candidate.governance_ledger_id,
                "policySnapshotHash": candidate.policy_snapshot_hash,
                "policyId": candidate.policy_id,
                "policyVersion": candidate.policy_version,
                "exportApprovalReviewId": request.final_review_id,
                "exportApprovalActorUserId": request.final_decision_by,
                "exportApprovalAt": (
                    request.final_decision_at.isoformat()
                    if request.final_decision_at is not None
                    else None
                ),
                "modelReferencesByRole": (
                    candidate.artefact_manifest_json.get("approvedModelReferencesByRole")
                    if isinstance(
                        candidate.artefact_manifest_json.get("approvedModelReferencesByRole"),
                        dict,
                    )
                    else {}
                ),
            },
        }

    def list_export_request_provenance_proofs(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
    ) -> tuple[ProvenanceProofRecord, ...]:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        self._ensure_provenance_read_allowed(
            role=role,
            current_user=current_user,
            request=request,
        )
        return self._ensure_initial_proof_exists(
            project_id=project_id,
            export_request_id=export_request_id,
            actor_user_id=current_user.user_id,
        )

    def get_export_request_current_provenance_proof(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
    ) -> dict[str, object]:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        self._ensure_provenance_read_allowed(
            role=role,
            current_user=current_user,
            request=request,
        )
        try:
            proof = self._store.get_current_provenance_proof(
                project_id=project_id,
                export_request_id=export_request_id,
            )
        except ExportStoreNotFoundError as error:
            self._ensure_initial_proof_exists(
                project_id=project_id,
                export_request_id=export_request_id,
                actor_user_id=current_user.user_id,
            )
            try:
                proof = self._store.get_current_provenance_proof(
                    project_id=project_id,
                    export_request_id=export_request_id,
                )
            except ExportStoreNotFoundError as nested_error:
                raise ExportNotFoundError(str(nested_error)) from nested_error
        return {
            "proof": proof,
            "artifact": self._read_proof_payload(proof=proof),
        }

    def get_export_request_provenance_proof(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        proof_id: str,
    ) -> dict[str, object]:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        self._ensure_provenance_read_allowed(
            role=role,
            current_user=current_user,
            request=request,
        )
        try:
            proof = self._store.get_provenance_proof(
                project_id=project_id,
                export_request_id=export_request_id,
                proof_id=proof_id,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error
        return {
            "proof": proof,
            "artifact": self._read_proof_payload(proof=proof),
        }

    def regenerate_export_request_provenance_proof(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
    ) -> ProvenanceProofRecord:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        if role != "ADMIN":
            raise ExportAccessDeniedError("Only ADMIN can regenerate provenance proofs.")
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        self._ensure_provenance_status_allowed(request=request)
        try:
            return self._store.generate_provenance_proof(
                project_id=project_id,
                export_request_id=export_request_id,
                actor_user_id=current_user.user_id,
                force_regenerate=True,
            )
        except ExportStoreConflictError as error:
            raise ExportConflictError(str(error)) from error
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error

    def list_export_request_bundles(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
    ) -> tuple[DepositBundleRecord, ...]:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        self._ensure_bundle_status_allowed(request=request)
        try:
            bundles = self._store.list_deposit_bundles(
                project_id=project_id,
                export_request_id=export_request_id,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error
        if role in {"ADMIN", "AUDITOR"}:
            return bundles
        return tuple(item for item in bundles if item.bundle_kind == "SAFEGUARDED_DEPOSIT")

    def create_export_request_bundle(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        bundle_kind: str,
    ) -> DepositBundleRecord:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        self._ensure_bundle_status_allowed(request=request)
        normalized_kind = self._assert_bundle_kind(bundle_kind)
        self._ensure_bundle_build_allowed(role=role, bundle_kind=normalized_kind)
        try:
            return self._store.create_or_get_deposit_bundle(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_kind=normalized_kind,
                actor_user_id=current_user.user_id,
            )
        except ExportStoreConflictError as error:
            raise ExportConflictError(str(error)) from error
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error

    def get_export_request_bundle(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
    ) -> dict[str, object]:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        try:
            bundle = self._store.get_deposit_bundle(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle_id,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error
        self._ensure_bundle_read_allowed(
            role=role,
            current_user=current_user,
            request=request,
            bundle_kind=bundle.bundle_kind,
        )
        attempts = self._store.list_deposit_bundles(
            project_id=project_id,
            export_request_id=export_request_id,
        )
        lineage_attempts = tuple(
            item
            for item in attempts
            if item.bundle_kind == bundle.bundle_kind
            and item.candidate_snapshot_id == bundle.candidate_snapshot_id
        )
        verification_projection = self._store.get_bundle_verification_projection(
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle.id,
        )
        artifact: dict[str, object] = {}
        if bundle.status == "SUCCEEDED":
            try:
                artifact = self._store.read_deposit_bundle_artifact(bundle=bundle)
            except ExportStoreConflictError:
                artifact = {}
        return {
            "bundle": bundle,
            "lineageAttempts": lineage_attempts,
            "verificationProjection": verification_projection,
            "artifact": artifact,
        }

    def get_export_request_bundle_status(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
    ) -> dict[str, object]:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        try:
            bundle = self._store.get_deposit_bundle_status(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle_id,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error
        self._ensure_bundle_read_allowed(
            role=role,
            current_user=current_user,
            request=request,
            bundle_kind=bundle.bundle_kind,
        )
        return {
            "bundle": bundle,
            "verificationProjection": self._store.get_bundle_verification_projection(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle.id,
            ),
        }

    def list_export_request_bundle_events(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
    ) -> tuple[BundleEventRecord, ...]:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        try:
            bundle = self._store.get_deposit_bundle(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle_id,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error
        self._ensure_bundle_read_allowed(
            role=role,
            current_user=current_user,
            request=request,
            bundle_kind=bundle.bundle_kind,
        )
        return self._store.list_deposit_bundle_events(
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
        )

    def cancel_export_request_bundle(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
    ) -> DepositBundleRecord:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        self._ensure_bundle_status_allowed(request=request)
        try:
            target = self._store.get_deposit_bundle(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle_id,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error
        self._ensure_bundle_mutation_allowed(role=role, bundle_kind=target.bundle_kind)
        try:
            return self._store.cancel_deposit_bundle(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle_id,
                actor_user_id=current_user.user_id,
            )
        except ExportStoreConflictError as error:
            raise ExportConflictError(str(error)) from error
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error

    def rebuild_export_request_bundle(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
    ) -> DepositBundleRecord:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        self._ensure_bundle_status_allowed(request=request)
        try:
            target = self._store.get_deposit_bundle(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle_id,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error
        self._ensure_bundle_mutation_allowed(role=role, bundle_kind=target.bundle_kind)
        try:
            return self._store.rebuild_deposit_bundle(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle_id,
                actor_user_id=current_user.user_id,
            )
        except ExportStoreConflictError as error:
            raise ExportConflictError(str(error)) from error
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error

    def start_export_request_bundle_verification(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
    ) -> BundleVerificationRunRecord:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        self._ensure_bundle_verification_start_allowed(role=role)
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        self._ensure_bundle_status_allowed(request=request)
        try:
            bundle = self._store.get_deposit_bundle(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle_id,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error
        self._ensure_bundle_read_allowed(
            role=role,
            current_user=current_user,
            request=request,
            bundle_kind=bundle.bundle_kind,
        )
        try:
            return self._store.create_bundle_verification_run(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle.id,
                actor_user_id=current_user.user_id,
            )
        except ExportStoreConflictError as error:
            raise ExportConflictError(str(error)) from error
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error

    def get_export_request_bundle_verification(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
    ) -> dict[str, object]:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        try:
            bundle = self._store.get_deposit_bundle(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle_id,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error
        self._ensure_bundle_read_allowed(
            role=role,
            current_user=current_user,
            request=request,
            bundle_kind=bundle.bundle_kind,
        )
        runs = self._store.list_bundle_verification_runs(
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
        )
        latest_attempt = runs[0] if runs else None
        latest_completed_attempt = next(
            (
                item
                for item in runs
                if item.status in {"SUCCEEDED", "FAILED"}
            ),
            None,
        )
        projection = self._store.get_bundle_verification_projection(
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
        )
        return {
            "bundle": bundle,
            "projection": projection,
            "latestAttempt": latest_attempt,
            "latestCompletedAttempt": latest_completed_attempt,
        }

    def get_export_request_bundle_verification_status(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
    ) -> dict[str, object]:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        try:
            bundle = self._store.get_deposit_bundle(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle_id,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error
        self._ensure_bundle_read_allowed(
            role=role,
            current_user=current_user,
            request=request,
            bundle_kind=bundle.bundle_kind,
        )
        return {
            "bundle": bundle,
            "projection": self._store.get_bundle_verification_projection(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle_id,
            ),
            "latestAttempt": self._store.get_current_bundle_verification_run(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle_id,
            ),
        }

    def list_export_request_bundle_verification_runs(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
    ) -> tuple[BundleVerificationRunRecord, ...]:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        try:
            bundle = self._store.get_deposit_bundle(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle_id,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error
        self._ensure_bundle_read_allowed(
            role=role,
            current_user=current_user,
            request=request,
            bundle_kind=bundle.bundle_kind,
        )
        return self._store.list_bundle_verification_runs(
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
        )

    def get_export_request_bundle_verification_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        verification_run_id: str,
    ) -> BundleVerificationRunRecord:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        try:
            bundle = self._store.get_deposit_bundle(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle_id,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error
        self._ensure_bundle_read_allowed(
            role=role,
            current_user=current_user,
            request=request,
            bundle_kind=bundle.bundle_kind,
        )
        try:
            return self._store.get_bundle_verification_run(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle_id,
                verification_run_id=verification_run_id,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error

    def get_export_request_bundle_verification_run_status(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        verification_run_id: str,
    ) -> dict[str, object]:
        run = self.get_export_request_bundle_verification_run(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
            verification_run_id=verification_run_id,
        )
        return {
            "verificationRun": run,
        }

    def cancel_export_request_bundle_verification_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        verification_run_id: str,
    ) -> BundleVerificationRunRecord:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        self._ensure_bundle_verification_cancel_allowed(role=role)
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        self._ensure_bundle_status_allowed(request=request)
        try:
            bundle = self._store.get_deposit_bundle(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle_id,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error
        self._ensure_bundle_read_allowed(
            role=role,
            current_user=current_user,
            request=request,
            bundle_kind=bundle.bundle_kind,
        )
        try:
            return self._store.cancel_bundle_verification_run(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle_id,
                verification_run_id=verification_run_id,
                actor_user_id=current_user.user_id,
            )
        except ExportStoreConflictError as error:
            raise ExportConflictError(str(error)) from error
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error

    def list_export_request_bundle_profiles(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        bundle_id: str | None = None,
    ) -> tuple[BundleProfileRecord, ...]:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        self._ensure_bundle_status_allowed(request=request)
        if isinstance(bundle_id, str) and bundle_id.strip():
            try:
                bundle = self._store.get_deposit_bundle(
                    project_id=project_id,
                    export_request_id=export_request_id,
                    bundle_id=bundle_id,
                )
            except ExportStoreNotFoundError as error:
                raise ExportNotFoundError(str(error)) from error
            self._ensure_bundle_read_allowed(
                role=role,
                current_user=current_user,
                request=request,
                bundle_kind=bundle.bundle_kind,
            )
        return self._store.list_bundle_profiles()

    def start_export_request_bundle_validation(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        profile_id: str,
    ) -> BundleValidationRunRecord:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        self._ensure_bundle_validation_start_allowed(role=role)
        normalized_profile_id = self._normalize_bundle_profile_id(profile_id)
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        self._ensure_bundle_status_allowed(request=request)
        try:
            bundle = self._store.get_deposit_bundle(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle_id,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error
        self._ensure_bundle_read_allowed(
            role=role,
            current_user=current_user,
            request=request,
            bundle_kind=bundle.bundle_kind,
        )
        try:
            return self._store.create_bundle_validation_run(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle.id,
                profile_id=normalized_profile_id,
                actor_user_id=current_user.user_id,
            )
        except ExportStoreConflictError as error:
            raise ExportConflictError(str(error)) from error
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error

    def get_export_request_bundle_validation_status(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        profile_id: str,
    ) -> dict[str, object]:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        normalized_profile_id = self._normalize_bundle_profile_id(profile_id)
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        try:
            bundle = self._store.get_deposit_bundle(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle_id,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error
        self._ensure_bundle_read_allowed(
            role=role,
            current_user=current_user,
            request=request,
            bundle_kind=bundle.bundle_kind,
        )
        runs = self._store.list_bundle_validation_runs(
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle.id,
            profile_id=normalized_profile_id,
        )
        latest_attempt = runs[0] if runs else None
        in_flight_attempt = next(
            (item for item in runs if item.status in {"QUEUED", "RUNNING"}),
            None,
        )
        last_successful_attempt = next(
            (item for item in runs if item.status == "SUCCEEDED"),
            None,
        )
        return {
            "bundleId": bundle.id,
            "bundleStatus": bundle.status,
            "profileId": normalized_profile_id,
            "verificationProjection": self._store.get_bundle_verification_projection(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle.id,
            ),
            "projection": self._store.get_bundle_validation_projection(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle.id,
                profile_id=normalized_profile_id,
            ),
            "latestAttempt": latest_attempt,
            "inFlightAttempt": in_flight_attempt,
            "lastSuccessfulAttempt": last_successful_attempt,
        }

    def list_export_request_bundle_validation_runs(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        profile_id: str,
    ) -> tuple[BundleValidationRunRecord, ...]:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        normalized_profile_id = self._normalize_bundle_profile_id(profile_id)
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        try:
            bundle = self._store.get_deposit_bundle(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle_id,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error
        self._ensure_bundle_read_allowed(
            role=role,
            current_user=current_user,
            request=request,
            bundle_kind=bundle.bundle_kind,
        )
        return self._store.list_bundle_validation_runs(
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle.id,
            profile_id=normalized_profile_id,
        )

    def get_export_request_bundle_validation_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        profile_id: str | None,
        validation_run_id: str,
    ) -> BundleValidationRunRecord:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        normalized_profile_id = (
            self._normalize_bundle_profile_id(profile_id)
            if isinstance(profile_id, str) and profile_id.strip()
            else None
        )
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        try:
            bundle = self._store.get_deposit_bundle(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle_id,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error
        self._ensure_bundle_read_allowed(
            role=role,
            current_user=current_user,
            request=request,
            bundle_kind=bundle.bundle_kind,
        )
        if normalized_profile_id is not None:
            try:
                return self._store.get_bundle_validation_run(
                    project_id=project_id,
                    export_request_id=export_request_id,
                    bundle_id=bundle.id,
                    profile_id=normalized_profile_id,
                    validation_run_id=validation_run_id,
                )
            except ExportStoreNotFoundError as error:
                raise ExportNotFoundError(str(error)) from error

        for profile in self._store.list_bundle_profiles():
            try:
                return self._store.get_bundle_validation_run(
                    project_id=project_id,
                    export_request_id=export_request_id,
                    bundle_id=bundle.id,
                    profile_id=profile.id,
                    validation_run_id=validation_run_id,
                )
            except ExportStoreNotFoundError:
                continue
        raise ExportNotFoundError("Bundle validation run not found.")

    def get_export_request_bundle_validation_run_status(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        profile_id: str | None,
        validation_run_id: str,
    ) -> dict[str, object]:
        run = self.get_export_request_bundle_validation_run(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
            profile_id=profile_id,
            validation_run_id=validation_run_id,
        )
        return {"validationRun": run}

    def cancel_export_request_bundle_validation_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        profile_id: str | None,
        validation_run_id: str,
    ) -> BundleValidationRunRecord:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        self._ensure_bundle_validation_cancel_allowed(role=role)
        normalized_profile_id = (
            self._normalize_bundle_profile_id(profile_id)
            if isinstance(profile_id, str) and profile_id.strip()
            else None
        )
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        self._ensure_bundle_status_allowed(request=request)
        try:
            bundle = self._store.get_deposit_bundle(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle_id,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error
        self._ensure_bundle_read_allowed(
            role=role,
            current_user=current_user,
            request=request,
            bundle_kind=bundle.bundle_kind,
        )
        run = self.get_export_request_bundle_validation_run(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
            bundle_id=bundle_id,
            profile_id=normalized_profile_id,
            validation_run_id=validation_run_id,
        )
        try:
            return self._store.cancel_bundle_validation_run(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle.id,
                profile_id=run.profile_id,
                validation_run_id=validation_run_id,
                actor_user_id=current_user.user_id,
            )
        except ExportStoreConflictError as error:
            raise ExportConflictError(str(error)) from error
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error

    def run_export_request_bundle_replay_drill(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        bundle_id: str,
        profile_id: str | None,
    ) -> dict[str, object]:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        if role != "ADMIN":
            raise ExportAccessDeniedError("Only ADMIN can run bundle replay drills.")
        normalized_profile_id = (
            self._normalize_bundle_profile_id(profile_id)
            if isinstance(profile_id, str) and profile_id.strip()
            else None
        )
        try:
            return self._store.run_bundle_replay_drill(
                project_id=project_id,
                export_request_id=export_request_id,
                bundle_id=bundle_id,
                profile_id=normalized_profile_id,
            )
        except ExportStoreConflictError as error:
            raise ExportConflictError(str(error)) from error
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error

    def attach_gateway_export_request_receipt(
        self,
        *,
        export_request_id: str,
        gateway_user_id: str,
        gateway_oidc_sub: str,
        gateway_email: str,
        gateway_display_name: str,
        receipt_key: str,
        receipt_sha256: str,
        exported_at: datetime,
    ) -> tuple[ExportRequestRecord, ExportReceiptRecord]:
        normalized_receipt_key = self._normalize_gateway_receipt_key(receipt_key)
        self._assert_gateway_export_prefix(receipt_key=normalized_receipt_key)
        normalized_receipt_sha256 = self._normalize_gateway_receipt_sha256(receipt_sha256)
        self._store.ensure_service_account_user(
            user_id=gateway_user_id,
            oidc_sub=gateway_oidc_sub,
            email=gateway_email,
            display_name=gateway_display_name,
        )
        try:
            return self._store.attach_request_receipt(
                export_request_id=export_request_id,
                actor_user_id=gateway_user_id,
                receipt_key=normalized_receipt_key,
                receipt_sha256=normalized_receipt_sha256,
                exported_at=exported_at,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error
        except ExportStoreConflictError as error:
            raise ExportConflictError(str(error)) from error

    def list_export_review_queue(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        status: str | None = None,
        aging_bucket: str | None = None,
        reviewer_user_id: str | None = None,
    ) -> tuple[ExportReviewQueueItemRecord, ...]:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        if role not in _ALLOWED_REVIEW_QUEUE_ROLES:
            raise ExportAccessDeniedError("Current role cannot view the export review queue.")

        normalized_status = self._assert_request_status(
            self._sanitize_optional_text(status, max_len=32)
        )
        normalized_aging_bucket = self._assert_aging_bucket(
            self._sanitize_optional_text(aging_bucket, max_len=32)
        )
        normalized_reviewer_user_id = self._sanitize_optional_text(
            reviewer_user_id,
            max_len=128,
        )
        page = self._store.list_requests(
            project_id=project_id,
            status=normalized_status,
            requester_id=None,
            candidate_kind=None,
            cursor=0,
            limit=200,
        )
        now = datetime.now(UTC)
        queue_rows: list[ExportReviewQueueItemRecord] = []
        for request in page.items:
            if (
                normalized_status is None
                and request.status not in _OPEN_REVIEWABLE_REQUEST_STATUSES
            ):
                continue
            reviews = self._store.list_request_reviews(export_request_id=request.id)
            active_review = self._resolve_active_required_review(reviews)
            if normalized_reviewer_user_id is not None:
                active_assignee = (
                    active_review.assigned_reviewer_user_id if active_review is not None else None
                )
                if active_assignee != normalized_reviewer_user_id:
                    continue
            computed_aging_bucket, sla_seconds_remaining, is_sla_breached = self._classify_aging(
                request,
                now=now,
            )
            if (
                normalized_aging_bucket is not None
                and computed_aging_bucket != normalized_aging_bucket
            ):
                continue
            queue_rows.append(
                ExportReviewQueueItemRecord(
                    request=request,
                    reviews=reviews,
                    active_review_id=active_review.id if active_review else None,
                    active_review_stage=active_review.review_stage if active_review else None,
                    active_review_status=active_review.status if active_review else None,
                    active_review_assigned_reviewer_user_id=(
                        active_review.assigned_reviewer_user_id if active_review else None
                    ),
                    aging_bucket=computed_aging_bucket,
                    sla_seconds_remaining=sla_seconds_remaining,
                    is_sla_breached=is_sla_breached,
                )
            )

        far_future = datetime(9999, 12, 31, tzinfo=UTC)

        def _sort_key(item: ExportReviewQueueItemRecord) -> tuple[object, ...]:
            status_rank = {
                "IN_REVIEW": 0,
                "RESUBMITTED": 1,
                "SUBMITTED": 2,
                "APPROVED": 3,
                "EXPORTED": 4,
                "RETURNED": 5,
                "REJECTED": 6,
            }.get(item.request.status, 99)
            return (
                0 if item.is_sla_breached else 1,
                item.request.sla_due_at or far_future,
                status_rank,
                item.request.submitted_at,
                item.request.id,
            )

        queue_rows.sort(key=_sort_key)
        return tuple(queue_rows)

    def claim_export_request_review(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        review_id: str,
        review_etag: str,
    ) -> tuple[ExportRequestRecord, ExportRequestReviewRecord]:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        self._ensure_review_mutation_allowed(role=role)
        try:
            return self._store.claim_request_review(
                project_id=project_id,
                export_request_id=export_request_id,
                review_id=review_id,
                expected_review_etag=self._normalize_review_etag(review_etag),
                actor_user_id=current_user.user_id,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error
        except ExportStoreConflictError as error:
            raise ExportConflictError(str(error)) from error

    def release_export_request_review(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        review_id: str,
        review_etag: str,
    ) -> tuple[ExportRequestRecord, ExportRequestReviewRecord]:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        self._ensure_review_mutation_allowed(role=role)
        try:
            return self._store.release_request_review(
                project_id=project_id,
                export_request_id=export_request_id,
                review_id=review_id,
                expected_review_etag=self._normalize_review_etag(review_etag),
                actor_user_id=current_user.user_id,
                allow_admin_release=self._is_admin(current_user),
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error
        except ExportStoreConflictError as error:
            raise ExportConflictError(str(error)) from error

    def start_export_request_review(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        review_id: str,
        review_etag: str,
    ) -> tuple[ExportRequestRecord, ExportRequestReviewRecord]:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        self._ensure_review_mutation_allowed(role=role)
        try:
            return self._store.start_request_review(
                project_id=project_id,
                export_request_id=export_request_id,
                review_id=review_id,
                expected_review_etag=self._normalize_review_etag(review_etag),
                actor_user_id=current_user.user_id,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error
        except ExportStoreConflictError as error:
            raise ExportConflictError(str(error)) from error

    def decide_export_request(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        export_request_id: str,
        review_id: str,
        review_etag: str,
        decision: str,
        decision_reason: str | None,
        return_comment: str | None,
    ) -> tuple[ExportRequestRecord, ExportRequestReviewRecord]:
        role = self._resolve_role(current_user=current_user, project_id=project_id)
        self._ensure_review_mutation_allowed(role=role)
        request = self.get_export_request(
            current_user=current_user,
            project_id=project_id,
            export_request_id=export_request_id,
        )
        normalized_decision = self._assert_review_decision(decision)
        normalized_decision_reason = self._sanitize_optional_text(decision_reason, max_len=3000)
        normalized_return_comment = self._sanitize_optional_text(return_comment, max_len=3000)
        if normalized_decision == "REJECT" and normalized_decision_reason is None:
            raise ExportValidationError("decisionReason is required for REJECT.")
        if normalized_decision == "RETURN" and normalized_return_comment is None:
            raise ExportValidationError("returnComment is required for RETURN.")
        if normalized_decision == "APPROVE" and request.submitted_by == current_user.user_id:
            raise ExportAccessDeniedError("Requester cannot approve their own export request.")
        try:
            request_record, review_record = self._store.decide_request_review(
                project_id=project_id,
                export_request_id=export_request_id,
                review_id=review_id,
                expected_review_etag=self._normalize_review_etag(review_etag),
                actor_user_id=current_user.user_id,
                decision=normalized_decision,
                decision_reason=normalized_decision_reason,
                return_comment=normalized_return_comment,
            )
        except ExportStoreNotFoundError as error:
            raise ExportNotFoundError(str(error)) from error
        except ExportStoreConflictError as error:
            raise ExportConflictError(str(error)) from error
        if request_record.status == "APPROVED":
            try:
                self._store.generate_provenance_proof(
                    project_id=project_id,
                    export_request_id=request_record.id,
                    actor_user_id=current_user.user_id,
                    force_regenerate=False,
                )
            except ExportStoreConflictError as error:
                raise ExportConflictError(str(error)) from error
            except ExportStoreNotFoundError as error:
                raise ExportNotFoundError(str(error)) from error
        return request_record, review_record

    def get_export_operations_status(
        self,
        *,
        current_user: SessionPrincipal,
    ) -> ExportOperationsStatusRecord:
        self._ensure_operations_read_allowed(current_user=current_user)
        return self._store.get_operations_export_status()

    def run_export_operations_maintenance(
        self,
        *,
        current_user: SessionPrincipal,
        batch_limit: int = 200,
    ) -> ExportOperationsMaintenanceResult:
        self._ensure_operations_maintenance_allowed(current_user=current_user)
        normalized_batch_limit = max(1, min(batch_limit, 500))
        return self._store.run_operations_maintenance(
            actor_user_id=current_user.user_id,
            batch_limit=normalized_batch_limit,
        )


@lru_cache
def get_export_service() -> ExportService:
    settings = get_settings()
    return ExportService(settings=settings)
