from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from app.exports.models import (
    BundleProfileRecord,
    DepositBundleKind,
    ReplayFailureClass,
)

BundleProfileValidationResult = Literal["VALID", "INVALID"]

_BASE_REQUIRED_ARCHIVE_ENTRIES = (
    "bundle/metadata.json",
    "bundle/provenance-proof.json",
    "bundle/provenance-signature.json",
    "bundle/provenance-verification-material.json",
)


@dataclass(frozen=True)
class BundleProfileValidationOutput:
    result: BundleProfileValidationResult
    payload: dict[str, object]


_BUNDLE_PROFILE_REGISTRY: dict[str, BundleProfileRecord] = {
    "ARCHIVE_MINIMUM_CORE_V1": BundleProfileRecord(
        id="ARCHIVE_MINIMUM_CORE_V1",
        label="Archive minimum core v1",
        description=(
            "Minimum archive integrity checks: canonical bundle entries, pinned provenance "
            "references, and deterministic metadata completeness."
        ),
        allowed_bundle_kinds=("SAFEGUARDED_DEPOSIT", "CONTROLLED_EVIDENCE"),
        required_archive_entries=_BASE_REQUIRED_ARCHIVE_ENTRIES,
        required_metadata_paths=(
            "bundleId",
            "bundleKind",
            "exportRequest.id",
            "candidateSnapshot.id",
            "provenanceProof.proofId",
            "provenanceProof.rootSha256",
            "provenanceProof.proofArtifactSha256",
        ),
        forbidden_metadata_paths=(),
    ),
    "SAFEGUARDED_DEPOSIT_CORE_V1": BundleProfileRecord(
        id="SAFEGUARDED_DEPOSIT_CORE_V1",
        label="Safeguarded deposit core v1",
        description=(
            "Safeguarded deposit profile with receipt metadata support and strict bundle-kind "
            "alignment for approved Phase 8 request lineages."
        ),
        allowed_bundle_kinds=("SAFEGUARDED_DEPOSIT",),
        required_archive_entries=_BASE_REQUIRED_ARCHIVE_ENTRIES,
        required_metadata_paths=(
            "bundleId",
            "bundleKind",
            "exportRequest.id",
            "candidateSnapshot.id",
            "provenanceProof.proofId",
            "provenanceProof.rootSha256",
            "provenanceProof.proofArtifactSha256",
            "metadata.releasePackSha256",
        ),
        forbidden_metadata_paths=(),
    ),
    "CONTROLLED_EVIDENCE_CORE_V1": BundleProfileRecord(
        id="CONTROLLED_EVIDENCE_CORE_V1",
        label="Controlled evidence core v1",
        description=(
            "Controlled evidence profile requiring canonical proof and lineage payloads while "
            "forbidding public receipt metadata inside internal-only evidence bundles."
        ),
        allowed_bundle_kinds=("CONTROLLED_EVIDENCE",),
        required_archive_entries=_BASE_REQUIRED_ARCHIVE_ENTRIES,
        required_metadata_paths=(
            "bundleId",
            "bundleKind",
            "exportRequest.id",
            "candidateSnapshot.id",
            "provenanceProof.proofId",
            "provenanceProof.rootSha256",
            "provenanceProof.proofArtifactSha256",
            "metadata.releasePackSha256",
        ),
        forbidden_metadata_paths=("exportReceiptMetadata.receiptId",),
    ),
}


def _canonical_json_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_path(payload: dict[str, object], path: str) -> object:
    current: object = payload
    for segment in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(segment)
    return current


def _has_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) > 0
    return True


def list_bundle_profiles() -> tuple[BundleProfileRecord, ...]:
    return tuple(_BUNDLE_PROFILE_REGISTRY[key] for key in sorted(_BUNDLE_PROFILE_REGISTRY))


def get_bundle_profile(*, profile_id: str) -> BundleProfileRecord:
    normalized = profile_id.strip().upper()
    profile = _BUNDLE_PROFILE_REGISTRY.get(normalized)
    if profile is None:
        raise ValueError("Unknown bundle validation profile.")
    return profile


def build_bundle_profile_snapshot(*, profile: BundleProfileRecord) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "profileId": profile.id,
        "label": profile.label,
        "description": profile.description,
        "allowedBundleKinds": list(profile.allowed_bundle_kinds),
        "requiredArchiveEntries": list(profile.required_archive_entries),
        "requiredMetadataPaths": list(profile.required_metadata_paths),
        "forbiddenMetadataPaths": list(profile.forbidden_metadata_paths),
    }


def bundle_profile_snapshot_bytes(*, profile: BundleProfileRecord) -> bytes:
    return _canonical_json_bytes(build_bundle_profile_snapshot(profile=profile))


def bundle_profile_snapshot_sha256(*, profile: BundleProfileRecord) -> str:
    return _sha256_hex(bundle_profile_snapshot_bytes(profile=profile))


def validate_bundle_artifact_against_profile(
    *,
    bundle_id: str,
    bundle_kind: DepositBundleKind,
    bundle_sha256: str,
    bundle_artifact: dict[str, object],
    expected_proof_artifact_sha256: str | None,
    verification_projection_status: str | None,
    profile: BundleProfileRecord,
    checked_at: datetime | None = None,
) -> BundleProfileValidationOutput:
    issues: list[dict[str, object]] = []

    def add_issue(
        *,
        code: str,
        detail: str,
        path: str | None,
        failure_class: ReplayFailureClass,
    ) -> None:
        issues.append(
            {
                "code": code,
                "detail": detail,
                "path": path,
                "failureClass": failure_class,
            }
        )

    if bundle_kind not in set(profile.allowed_bundle_kinds):
        add_issue(
            code="PROFILE_BUNDLE_KIND_MISMATCH",
            detail=(
                f"Profile {profile.id} does not permit bundle kind {bundle_kind}."
            ),
            path="bundleKind",
            failure_class="PROFILE_MISMATCH",
        )

    archive_entries = (
        tuple(item for item in bundle_artifact.get("archiveEntries", []) if isinstance(item, str))
        if isinstance(bundle_artifact.get("archiveEntries"), list)
        else ()
    )
    archive_entry_set = set(archive_entries)
    for entry in profile.required_archive_entries:
        if entry not in archive_entry_set:
            add_issue(
                code="REQUIRED_ARCHIVE_ENTRY_MISSING",
                detail=f"Missing required archive entry: {entry}.",
                path=entry,
                failure_class="MISSING_ARTEFACT",
            )

    metadata = (
        dict(bundle_artifact.get("metadata"))
        if isinstance(bundle_artifact.get("metadata"), dict)
        else {}
    )
    if not metadata:
        add_issue(
            code="METADATA_MISSING",
            detail="Bundle metadata payload is missing or unreadable.",
            path="bundle/metadata.json",
            failure_class="MISSING_ARTEFACT",
        )

    if metadata:
        metadata_bundle_id = metadata.get("bundleId")
        if not isinstance(metadata_bundle_id, str) or metadata_bundle_id.strip() != bundle_id:
            add_issue(
                code="BUNDLE_ID_MISMATCH",
                detail="Metadata bundleId does not match the pinned bundle lineage.",
                path="bundleId",
                failure_class="INVALID_BUNDLE_CONTENTS",
            )
        metadata_bundle_kind = metadata.get("bundleKind")
        if not isinstance(metadata_bundle_kind, str) or metadata_bundle_kind.strip() != bundle_kind:
            add_issue(
                code="BUNDLE_KIND_MISMATCH",
                detail="Metadata bundleKind does not match the pinned bundle kind.",
                path="bundleKind",
                failure_class="INVALID_BUNDLE_CONTENTS",
            )

    for path in profile.required_metadata_paths:
        value = _read_path(metadata, path) if metadata else None
        if not _has_value(value):
            add_issue(
                code="REQUIRED_METADATA_FIELD_MISSING",
                detail=f"Required metadata field is missing: {path}.",
                path=path,
                failure_class="INVALID_BUNDLE_CONTENTS",
            )

    for path in profile.forbidden_metadata_paths:
        value = _read_path(metadata, path) if metadata else None
        if _has_value(value):
            add_issue(
                code="FORBIDDEN_METADATA_FIELD_PRESENT",
                detail=f"Forbidden metadata field is present for profile {profile.id}: {path}.",
                path=path,
                failure_class="PROFILE_MISMATCH",
            )

    provenance_proof = (
        dict(metadata.get("provenanceProof"))
        if isinstance(metadata.get("provenanceProof"), dict)
        else {}
    )
    proof_artifact_sha = provenance_proof.get("proofArtifactSha256")
    if (
        isinstance(expected_proof_artifact_sha256, str)
        and expected_proof_artifact_sha256.strip()
        and (
            not isinstance(proof_artifact_sha, str)
            or proof_artifact_sha.strip().lower()
            != expected_proof_artifact_sha256.strip().lower()
        )
    ):
        add_issue(
            code="PROOF_ARTIFACT_SHA_MISMATCH",
            detail="Pinned proof artifact hash does not match bundle metadata.",
            path="provenanceProof.proofArtifactSha256",
            failure_class="TAMPERED_PROOF",
        )

    normalized_verification_status = (
        verification_projection_status.strip().upper()
        if isinstance(verification_projection_status, str)
        else None
    )
    if normalized_verification_status != "VERIFIED":
        add_issue(
            code="BUNDLE_NOT_VERIFIED",
            detail=(
                "Bundle validation requires a VERIFIED bundle verification projection "
                "before readiness can be asserted."
            ),
            path="verificationProjection.status",
            failure_class="INVALID_BUNDLE_CONTENTS",
        )

    validation_result: BundleProfileValidationResult = "VALID" if not issues else "INVALID"
    failure_class: ReplayFailureClass | None = (
        str(issues[0]["failureClass"]) if issues else None
    )  # type: ignore[assignment]
    checked_time = checked_at or datetime.now(UTC)
    payload: dict[str, object] = {
        "validationResult": validation_result,
        "profileId": profile.id,
        "profileLabel": profile.label,
        "bundleId": bundle_id,
        "bundleKind": bundle_kind,
        "bundleSha256": bundle_sha256,
        "checkedAt": checked_time.isoformat(),
        "verificationProjectionStatus": normalized_verification_status,
        "requiredArchiveEntriesChecked": list(profile.required_archive_entries),
        "requiredMetadataPathsChecked": list(profile.required_metadata_paths),
        "forbiddenMetadataPathsChecked": list(profile.forbidden_metadata_paths),
        "issueCount": len(issues),
        "issues": issues,
        "failures": [str(item.get("detail", "")) for item in issues],
        "failureClass": failure_class,
    }
    return BundleProfileValidationOutput(result=validation_result, payload=payload)

