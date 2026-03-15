from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from io import BytesIO

from app.exports.deposit_profiles import (
    BundleProfileValidationOutput,
    validate_bundle_artifact_against_profile,
)
from app.exports.models import BundleProfileRecord, DepositBundleKind, ReplayFailureClass
from app.exports.verification import BundleVerificationOutput, verify_bundle_archive_bytes


def _bundle_artifact_from_bytes(bundle_bytes: bytes) -> dict[str, object]:
    archive_entries: list[str] = []
    metadata: dict[str, object] = {}
    provenance_proof_artifact: dict[str, object] = {}
    provenance_signature: dict[str, object] = {}
    provenance_verification_material: dict[str, object] = {}
    with zipfile.ZipFile(BytesIO(bundle_bytes), mode="r") as archive:
        archive_entries = sorted(archive.namelist())

        def _read_json(name: str) -> dict[str, object]:
            if name not in archive_entries:
                return {}
            decoded = archive.read(name).decode("utf-8")
            parsed = json.loads(decoded)
            return dict(parsed) if isinstance(parsed, dict) else {}

        metadata = _read_json("bundle/metadata.json")
        provenance_proof_artifact = _read_json("bundle/provenance-proof.json")
        provenance_signature = _read_json("bundle/provenance-signature.json")
        provenance_verification_material = _read_json(
            "bundle/provenance-verification-material.json"
        )

    return {
        "archiveEntries": archive_entries,
        "metadata": metadata,
        "provenanceProofArtifact": provenance_proof_artifact,
        "provenanceSignature": provenance_signature,
        "provenanceVerificationMaterial": provenance_verification_material,
    }


def classify_verification_failure(*, failures: tuple[str, ...]) -> ReplayFailureClass:
    lowered = tuple(item.lower() for item in failures if item.strip())
    if any("missing required archive entry" in item for item in lowered):
        return "MISSING_ARTEFACT"
    if any(
        keyword in item
        for item in lowered
        for keyword in (
            "proof",
            "signature",
            "merkle",
            "leafhash",
            "rootsha256",
            "verificationmaterial",
            "publickey",
        )
    ):
        return "TAMPERED_PROOF"
    if any("execution failed" in item for item in lowered):
        return "ENVIRONMENTAL_RUNTIME"
    return "INVALID_BUNDLE_CONTENTS"


def _classify_lineage_failure(*, failures: tuple[str, ...]) -> ReplayFailureClass:
    lowered = tuple(item.lower() for item in failures if item.strip())
    if any("proof" in item or "sha" in item for item in lowered):
        return "TAMPERED_PROOF"
    if any("missing" in item for item in lowered):
        return "MISSING_ARTEFACT"
    return "INVALID_BUNDLE_CONTENTS"


def run_bundle_replay_drill(
    *,
    bundle_id: str,
    bundle_kind: DepositBundleKind,
    bundle_sha256: str,
    bundle_bytes: bytes,
    expected_candidate_snapshot_id: str,
    expected_provenance_proof_id: str,
    expected_provenance_proof_artifact_sha256: str,
    selected_profile: BundleProfileRecord | None = None,
) -> dict[str, object]:
    checked_at = datetime.now(UTC)
    steps: list[dict[str, object]] = []

    verification_output = verify_bundle_archive_bytes(
        bundle_bytes,
        expected_bundle_sha256=bundle_sha256,
    )
    verification_failures = tuple(
        item
        for item in verification_output.payload.get("failures", [])
        if isinstance(item, str)
    )
    verification_failure_class: ReplayFailureClass | None = None
    verification_status = "SUCCEEDED"
    if verification_output.result != "VALID":
        verification_status = "FAILED"
        verification_failure_class = classify_verification_failure(
            failures=verification_failures
        )
    steps.append(
        {
            "step": "bundle-verification",
            "status": verification_status,
            "failureClass": verification_failure_class,
            "details": verification_output.payload,
        }
    )

    artifact: dict[str, object] = {}
    lineage_status = "SUCCEEDED"
    lineage_failures: list[str] = []
    lineage_failure_class: ReplayFailureClass | None = None
    try:
        artifact = _bundle_artifact_from_bytes(bundle_bytes)
    except Exception as error:  # pragma: no cover - defensive guard
        lineage_status = "FAILED"
        lineage_failures.append(str(error).strip() or "Bundle archive could not be decoded.")
        lineage_failure_class = "ENVIRONMENTAL_RUNTIME"
    else:
        metadata = (
            dict(artifact.get("metadata"))
            if isinstance(artifact.get("metadata"), dict)
            else {}
        )
        candidate_snapshot = (
            dict(metadata.get("candidateSnapshot"))
            if isinstance(metadata.get("candidateSnapshot"), dict)
            else {}
        )
        provenance_proof = (
            dict(metadata.get("provenanceProof"))
            if isinstance(metadata.get("provenanceProof"), dict)
            else {}
        )
        bundle_id_value = metadata.get("bundleId")
        if not isinstance(bundle_id_value, str) or bundle_id_value.strip() != bundle_id:
            lineage_failures.append("Metadata bundleId does not match pinned bundle lineage.")
        bundle_kind_value = metadata.get("bundleKind")
        if not isinstance(bundle_kind_value, str) or bundle_kind_value.strip() != bundle_kind:
            lineage_failures.append("Metadata bundleKind does not match pinned bundle lineage.")
        candidate_snapshot_id = candidate_snapshot.get("id")
        if (
            not isinstance(candidate_snapshot_id, str)
            or candidate_snapshot_id.strip() != expected_candidate_snapshot_id
        ):
            lineage_failures.append(
                "Metadata candidateSnapshot.id does not match pinned candidate snapshot."
            )
        proof_id = provenance_proof.get("proofId")
        if not isinstance(proof_id, str) or proof_id.strip() != expected_provenance_proof_id:
            lineage_failures.append("Metadata provenanceProof.proofId does not match pinned proof.")
        proof_sha = provenance_proof.get("proofArtifactSha256")
        if (
            not isinstance(proof_sha, str)
            or proof_sha.strip().lower()
            != expected_provenance_proof_artifact_sha256.strip().lower()
        ):
            lineage_failures.append(
                "Metadata provenanceProof.proofArtifactSha256 does not match pinned proof hash."
            )
        if lineage_failures:
            lineage_status = "FAILED"
            lineage_failure_class = _classify_lineage_failure(
                failures=tuple(lineage_failures)
            )
    steps.append(
        {
            "step": "lineage-pinning",
            "status": lineage_status,
            "failureClass": lineage_failure_class,
            "details": {
                "failures": lineage_failures,
                "bundleId": bundle_id,
                "bundleKind": bundle_kind,
                "expectedCandidateSnapshotId": expected_candidate_snapshot_id,
                "expectedProvenanceProofId": expected_provenance_proof_id,
                "expectedProvenanceProofArtifactSha256": expected_provenance_proof_artifact_sha256,
            },
        }
    )

    validation_output: BundleProfileValidationOutput | None = None
    if selected_profile is not None:
        try:
            validation_output = validate_bundle_artifact_against_profile(
                bundle_id=bundle_id,
                bundle_kind=bundle_kind,
                bundle_sha256=bundle_sha256,
                bundle_artifact=artifact,
                expected_proof_artifact_sha256=expected_provenance_proof_artifact_sha256,
                verification_projection_status=(
                    "VERIFIED" if verification_output.result == "VALID" else "FAILED"
                ),
                profile=selected_profile,
                checked_at=checked_at,
            )
            validation_failure_class = (
                str(validation_output.payload.get("failureClass"))
                if isinstance(validation_output.payload.get("failureClass"), str)
                else None
            )
            steps.append(
                {
                    "step": "profile-validation",
                    "status": (
                        "SUCCEEDED"
                        if validation_output.result == "VALID"
                        else "FAILED"
                    ),
                    "failureClass": validation_failure_class,
                    "details": validation_output.payload,
                }
            )
        except Exception as error:  # pragma: no cover - defensive guard
            steps.append(
                {
                    "step": "profile-validation",
                    "status": "FAILED",
                    "failureClass": "ENVIRONMENTAL_RUNTIME",
                    "details": {
                        "validationResult": "INVALID",
                        "failures": [
                            str(error).strip()
                            or "Profile validation execution failed."
                        ],
                        "failureClass": "ENVIRONMENTAL_RUNTIME",
                    },
                }
            )

    failed_step = next((item for item in steps if item.get("status") == "FAILED"), None)
    drill_status = "SUCCEEDED" if failed_step is None else "FAILED"
    failure_class = (
        str(failed_step.get("failureClass"))
        if isinstance(failed_step, dict) and isinstance(failed_step.get("failureClass"), str)
        else None
    )
    operator_summary = (
        "Replay drill completed successfully with deterministic verification and validation evidence."
        if drill_status == "SUCCEEDED"
        else "Replay drill failed; inspect step-local failureClass and details for recovery guidance."
    )
    return {
        "drillStatus": drill_status,
        "failureClass": failure_class,
        "checkedAt": checked_at.isoformat(),
        "bundleId": bundle_id,
        "bundleKind": bundle_kind,
        "bundleSha256": bundle_sha256,
        "steps": steps,
        "operatorSummary": operator_summary,
    }


__all__ = [
    "classify_verification_failure",
    "run_bundle_replay_drill",
]
