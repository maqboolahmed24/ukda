from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import UTC, datetime
from io import BytesIO

from app.exports.bundle_verify_cli import run_cli
from app.exports.provenance import (
    build_merkle_tree,
    build_proof_artifact_payload,
    canonical_json_bytes,
    normalize_leaf,
    sign_root_sha256,
)
from app.exports.verification import verify_bundle_archive_bytes


def _build_bundle_bytes() -> tuple[bytes, str]:
    leaf = normalize_leaf(
        artifact_kind="EXPORT_REQUEST",
        stable_identifier="request-1",
        immutable_reference="f" * 64,
        parent_references=(),
    )
    merkle = build_merkle_tree((leaf,))
    signature = sign_root_sha256(
        root_sha256=merkle.root_sha256,
        key_ref="ukde-provenance-lamport-v1",
        secret="bundle-verification-test-secret",
    )
    proof_artifact = build_proof_artifact_payload(
        proof_id="proof-1",
        project_id="project-1",
        export_request_id="request-1",
        candidate_snapshot_id="candidate-1",
        attempt_number=1,
        created_at=datetime.now(UTC),
        merkle=merkle,
        signature=signature,
    )
    proof_sha = hashlib.sha256(canonical_json_bytes(proof_artifact)).hexdigest()
    metadata = {
        "schemaVersion": 1,
        "bundleId": "bundle-1",
        "bundleKind": "SAFEGUARDED_DEPOSIT",
        "provenanceProof": {
            "proofId": "proof-1",
            "rootSha256": merkle.root_sha256,
            "proofArtifactSha256": proof_sha,
            "signature": dict(proof_artifact["signature"]),
            "verificationMaterial": dict(proof_artifact["verificationMaterial"]),
        },
    }

    output = BytesIO()
    with zipfile.ZipFile(output, mode="w") as archive:
        archive.writestr("bundle/metadata.json", canonical_json_bytes(metadata))
        archive.writestr("bundle/provenance-proof.json", canonical_json_bytes(proof_artifact))
        archive.writestr(
            "bundle/provenance-signature.json",
            canonical_json_bytes(dict(proof_artifact["signature"])),
        )
        archive.writestr(
            "bundle/provenance-verification-material.json",
            canonical_json_bytes(dict(proof_artifact["verificationMaterial"])),
        )
    bundle_bytes = output.getvalue()
    bundle_sha256 = hashlib.sha256(bundle_bytes).hexdigest()
    return bundle_bytes, bundle_sha256


def _tamper_proof_entry(bundle_bytes: bytes) -> bytes:
    output = BytesIO()
    source = zipfile.ZipFile(BytesIO(bundle_bytes), mode="r")
    with source, zipfile.ZipFile(output, mode="w") as target:
        for name in source.namelist():
            payload = source.read(name)
            if name == "bundle/provenance-proof.json":
                proof = json.loads(payload.decode("utf-8"))
                proof["merkle"]["rootSha256"] = "0" * 64
                payload = canonical_json_bytes(proof)
            target.writestr(name, payload)
    return output.getvalue()


def test_verify_bundle_archive_bytes_validates_expected_bundle() -> None:
    bundle_bytes, bundle_sha256 = _build_bundle_bytes()
    output = verify_bundle_archive_bytes(
        bundle_bytes,
        expected_bundle_sha256=bundle_sha256,
    )
    assert output.result == "VALID"
    assert output.payload["verificationResult"] == "VALID"
    assert output.payload["signatureStatus"] == "VALID"
    assert output.payload["bundleSha256"] == bundle_sha256


def test_verify_bundle_archive_bytes_fails_when_one_file_is_tampered() -> None:
    bundle_bytes, bundle_sha256 = _build_bundle_bytes()
    tampered_bytes = _tamper_proof_entry(bundle_bytes)
    output = verify_bundle_archive_bytes(
        tampered_bytes,
        expected_bundle_sha256=bundle_sha256,
    )
    assert output.result == "INVALID"
    assert output.payload["verificationResult"] == "INVALID"
    failures = output.payload.get("failures")
    assert isinstance(failures, list)
    assert len(failures) >= 1


def test_bundle_verify_cli_reports_pass_and_fail(tmp_path) -> None:  # type: ignore[no-untyped-def]
    bundle_bytes, bundle_sha256 = _build_bundle_bytes()
    valid_path = tmp_path / "bundle-valid.zip"
    valid_path.write_bytes(bundle_bytes)

    assert run_cli([str(valid_path), "--expected-sha256", bundle_sha256]) == 0

    tampered_path = tmp_path / "bundle-tampered.zip"
    tampered_path.write_bytes(_tamper_proof_entry(bundle_bytes))
    assert run_cli([str(tampered_path), "--expected-sha256", bundle_sha256]) == 1
