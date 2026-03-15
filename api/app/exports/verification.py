from __future__ import annotations

import base64
import hashlib
import json
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from typing import Literal

from app.exports.provenance import (
    build_merkle_tree,
    canonical_json_bytes,
    normalize_leaf,
    verify_root_signature,
)

BundleVerificationResult = Literal["VALID", "INVALID"]

_REQUIRED_ARCHIVE_ENTRIES = (
    "bundle/metadata.json",
    "bundle/provenance-proof.json",
    "bundle/provenance-signature.json",
    "bundle/provenance-verification-material.json",
)


@dataclass(frozen=True)
class BundleVerificationOutput:
    result: BundleVerificationResult
    payload: dict[str, object]


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _decode_json_entry(archive: zipfile.ZipFile, entry_name: str) -> dict[str, object]:
    decoded = archive.read(entry_name).decode("utf-8")
    parsed = json.loads(decoded)
    if not isinstance(parsed, dict):
        raise ValueError(f"{entry_name} must contain a canonical JSON object.")
    return dict(parsed)


def verify_bundle_archive_bytes(
    bundle_bytes: bytes,
    *,
    expected_bundle_sha256: str | None = None,
) -> BundleVerificationOutput:
    failures: list[str] = []
    bundle_sha256 = _sha256_hex(bundle_bytes)

    if isinstance(expected_bundle_sha256, str) and expected_bundle_sha256.strip():
        if bundle_sha256 != expected_bundle_sha256.strip().lower():
            failures.append("Bundle archive hash does not match the pinned immutable hash.")

    metadata: dict[str, object] = {}
    proof_artifact: dict[str, object] = {}
    proof_signature: dict[str, object] = {}
    verification_material: dict[str, object] = {}
    archive_entries: list[str] = []

    try:
        archive = zipfile.ZipFile(BytesIO(bundle_bytes), mode="r")
    except zipfile.BadZipFile:
        failures.append("Bundle archive is not a valid zip file.")
        result_payload = {
            "verificationResult": "INVALID",
            "bundleSha256": bundle_sha256,
            "checkedAt": datetime.now(UTC).isoformat(),
            "failures": failures,
        }
        return BundleVerificationOutput(result="INVALID", payload=result_payload)

    with archive:
        archive_entries = sorted(archive.namelist())
        for required in _REQUIRED_ARCHIVE_ENTRIES:
            if required not in archive_entries:
                failures.append(f"Missing required archive entry: {required}.")
        if not failures:
            try:
                metadata = _decode_json_entry(archive, "bundle/metadata.json")
                proof_artifact = _decode_json_entry(archive, "bundle/provenance-proof.json")
                proof_signature = _decode_json_entry(archive, "bundle/provenance-signature.json")
                verification_material = _decode_json_entry(
                    archive, "bundle/provenance-verification-material.json"
                )
            except (UnicodeDecodeError, json.JSONDecodeError, KeyError, ValueError) as error:
                failures.append(str(error))

    proof_sha256 = _sha256_hex(canonical_json_bytes(proof_artifact)) if proof_artifact else None
    metadata_sha256 = _sha256_hex(canonical_json_bytes(metadata)) if metadata else None
    signature_sha256 = (
        _sha256_hex(canonical_json_bytes(proof_signature)) if proof_signature else None
    )
    verification_material_sha256 = (
        _sha256_hex(canonical_json_bytes(verification_material))
        if verification_material
        else None
    )

    root_sha256: str | None = None
    signature_status: Literal["VALID", "INVALID", "MISSING"] = "MISSING"
    leaf_count = 0

    if proof_artifact:
        proof_merkle = (
            dict(proof_artifact.get("merkle"))
            if isinstance(proof_artifact.get("merkle"), dict)
            else {}
        )
        root_value = proof_merkle.get("rootSha256")
        if isinstance(root_value, str) and root_value.strip():
            root_sha256 = root_value.strip().lower()
        else:
            failures.append("Provenance proof is missing merkle.rootSha256.")

        metadata_proof = (
            dict(metadata.get("provenanceProof"))
            if isinstance(metadata.get("provenanceProof"), dict)
            else {}
        )
        if metadata_proof:
            metadata_root = metadata_proof.get("rootSha256")
            if isinstance(metadata_root, str) and root_sha256 is not None:
                if metadata_root.strip().lower() != root_sha256:
                    failures.append("Metadata provenance root hash does not match proof root hash.")
            metadata_artifact_sha = metadata_proof.get("proofArtifactSha256")
            if isinstance(metadata_artifact_sha, str) and proof_sha256 is not None:
                if metadata_artifact_sha.strip().lower() != proof_sha256:
                    failures.append(
                        "Metadata proofArtifactSha256 does not match bundled proof artifact hash."
                    )

        proof_signature_from_artifact = (
            dict(proof_artifact.get("signature"))
            if isinstance(proof_artifact.get("signature"), dict)
            else {}
        )
        if proof_signature_from_artifact != proof_signature:
            failures.append(
                "Bundled provenance-signature payload does not match the signature in the proof artifact."
            )

        verification_from_artifact = (
            dict(proof_artifact.get("verificationMaterial"))
            if isinstance(proof_artifact.get("verificationMaterial"), dict)
            else {}
        )
        if verification_from_artifact != verification_material:
            failures.append(
                "Bundled provenance-verification-material payload does not match proof verificationMaterial."
            )

        leaves_raw = proof_artifact.get("leaves")
        leaves = []
        if isinstance(leaves_raw, list):
            for item in leaves_raw:
                if not isinstance(item, dict):
                    continue
                try:
                    leaves.append(
                        normalize_leaf(
                            artifact_kind=str(item.get("artifact_kind") or ""),
                            stable_identifier=str(item.get("stable_identifier") or ""),
                            immutable_reference=str(item.get("immutable_reference") or ""),
                            parent_references=[
                                str(value)
                                for value in item.get("parent_references", [])
                                if isinstance(value, str)
                            ],
                        )
                    )
                except Exception:
                    failures.append("Proof leaf canonicalization failed.")
                    leaves = []
                    break
        if not leaves:
            failures.append("Proof artifact does not include a valid canonical leaf set.")
        else:
            leaf_count = len(leaves)
            try:
                merkle = build_merkle_tree(leaves)
                if root_sha256 is not None and merkle.root_sha256 != root_sha256:
                    failures.append("Merkle root derived from proof leaves does not match rootSha256.")
                leaf_hashes_raw = proof_artifact.get("leafHashes")
                if isinstance(leaf_hashes_raw, list):
                    expected_leaf_hashes = [
                        value.strip().lower()
                        for value in leaf_hashes_raw
                        if isinstance(value, str) and value.strip()
                    ]
                    if expected_leaf_hashes != list(merkle.leaf_hashes):
                        failures.append("Proof leafHashes do not match canonical leaf hashing output.")
            except Exception:
                failures.append("Merkle root reconstruction failed.")

        signature_base64 = proof_signature.get("signatureBase64")
        public_key_base64 = verification_material.get("publicKeyBase64")
        public_key_sha256 = verification_material.get("publicKeySha256")

        if (
            isinstance(signature_base64, str)
            and signature_base64.strip()
            and isinstance(public_key_base64, str)
            and public_key_base64.strip()
            and root_sha256 is not None
        ):
            try:
                signature_bytes = base64.b64decode(signature_base64, validate=True)
                public_key_bytes = base64.b64decode(public_key_base64, validate=True)
            except Exception:
                signature_status = "INVALID"
                failures.append("Signature material is not valid base64.")
            else:
                if isinstance(public_key_sha256, str) and public_key_sha256.strip():
                    computed_public_key_sha256 = _sha256_hex(public_key_bytes)
                    if computed_public_key_sha256 != public_key_sha256.strip().lower():
                        signature_status = "INVALID"
                        failures.append(
                            "verificationMaterial.publicKeySha256 does not match public key bytes."
                        )
                signature_valid = verify_root_signature(
                    root_sha256=root_sha256,
                    signature_bytes=signature_bytes,
                    public_key_bytes=public_key_bytes,
                )
                if not signature_valid:
                    signature_status = "INVALID"
                    failures.append("Root signature verification failed.")
                elif signature_status != "INVALID":
                    signature_status = "VALID"
        else:
            signature_status = "MISSING"
            failures.append("Bundle proof signature material is missing or incomplete.")

    result: BundleVerificationResult = "VALID" if not failures else "INVALID"
    result_payload: dict[str, object] = {
        "verificationResult": result,
        "bundleSha256": bundle_sha256,
        "rootSha256": root_sha256,
        "signatureStatus": signature_status,
        "checkedAt": datetime.now(UTC).isoformat(),
        "archiveEntries": archive_entries,
        "leafCount": leaf_count,
        "metadataSha256": metadata_sha256,
        "proofArtifactSha256": proof_sha256,
        "signatureSha256": signature_sha256,
        "verificationMaterialSha256": verification_material_sha256,
        "failures": failures,
    }
    return BundleVerificationOutput(result=result, payload=result_payload)
