from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import UTC, datetime
from io import BytesIO

from app.exports.deposit_profiles import get_bundle_profile
from app.exports.provenance import (
    build_merkle_tree,
    build_proof_artifact_payload,
    canonical_json_bytes,
    normalize_leaf,
    sign_root_sha256,
)
from app.exports.replay import run_bundle_replay_drill


def _build_bundle_bytes() -> tuple[bytes, str, str, str, str]:
    proof_id = "proof-1"
    candidate_snapshot_id = "candidate-1"
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
        secret="bundle-replay-test-secret",
    )
    proof_artifact = build_proof_artifact_payload(
        proof_id=proof_id,
        project_id="project-1",
        export_request_id="request-1",
        candidate_snapshot_id=candidate_snapshot_id,
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
        "exportRequest": {"id": "request-1"},
        "candidateSnapshot": {
            "id": candidate_snapshot_id,
            "candidateSha256": "e" * 64,
        },
        "metadata": {"releasePackSha256": "f" * 64},
        "provenanceProof": {
            "proofId": proof_id,
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
    return bundle_bytes, bundle_sha256, proof_sha, proof_id, candidate_snapshot_id


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


def _remove_archive_entry(bundle_bytes: bytes, *, entry: str) -> bytes:
    output = BytesIO()
    source = zipfile.ZipFile(BytesIO(bundle_bytes), mode="r")
    with source, zipfile.ZipFile(output, mode="w") as target:
        for name in source.namelist():
            if name == entry:
                continue
            target.writestr(name, source.read(name))
    return output.getvalue()


def _step_signature(payload: dict[str, object]) -> tuple[tuple[str, str, str | None], ...]:
    steps = payload.get("steps")
    if not isinstance(steps, list):
        return ()
    signature: list[tuple[str, str, str | None]] = []
    for item in steps:
        if not isinstance(item, dict):
            continue
        step = str(item.get("step"))
        status = str(item.get("status"))
        failure_class = item.get("failureClass")
        signature.append(
            (step, status, str(failure_class) if isinstance(failure_class, str) else None)
        )
    return tuple(signature)


def test_run_bundle_replay_drill_is_deterministic_for_successful_replay() -> None:
    bundle_bytes, bundle_sha256, proof_sha, proof_id, candidate_snapshot_id = _build_bundle_bytes()
    profile = get_bundle_profile(profile_id="SAFEGUARDED_DEPOSIT_CORE_V1")

    first = run_bundle_replay_drill(
        bundle_id="bundle-1",
        bundle_kind="SAFEGUARDED_DEPOSIT",
        bundle_sha256=bundle_sha256,
        bundle_bytes=bundle_bytes,
        expected_candidate_snapshot_id=candidate_snapshot_id,
        expected_provenance_proof_id=proof_id,
        expected_provenance_proof_artifact_sha256=proof_sha,
        selected_profile=profile,
    )
    second = run_bundle_replay_drill(
        bundle_id="bundle-1",
        bundle_kind="SAFEGUARDED_DEPOSIT",
        bundle_sha256=bundle_sha256,
        bundle_bytes=bundle_bytes,
        expected_candidate_snapshot_id=candidate_snapshot_id,
        expected_provenance_proof_id=proof_id,
        expected_provenance_proof_artifact_sha256=proof_sha,
        selected_profile=profile,
    )

    assert first["drillStatus"] == "SUCCEEDED"
    assert second["drillStatus"] == "SUCCEEDED"
    assert first["failureClass"] is None
    assert second["failureClass"] is None
    assert _step_signature(first) == _step_signature(second)


def test_run_bundle_replay_drill_classifies_tampered_proof() -> None:
    bundle_bytes, _, proof_sha, proof_id, candidate_snapshot_id = _build_bundle_bytes()
    tampered = _tamper_proof_entry(bundle_bytes)
    tampered_sha = hashlib.sha256(tampered).hexdigest()

    payload = run_bundle_replay_drill(
        bundle_id="bundle-1",
        bundle_kind="SAFEGUARDED_DEPOSIT",
        bundle_sha256=tampered_sha,
        bundle_bytes=tampered,
        expected_candidate_snapshot_id=candidate_snapshot_id,
        expected_provenance_proof_id=proof_id,
        expected_provenance_proof_artifact_sha256=proof_sha,
        selected_profile=None,
    )

    assert payload["drillStatus"] == "FAILED"
    assert payload["failureClass"] == "TAMPERED_PROOF"


def test_run_bundle_replay_drill_classifies_missing_artefact() -> None:
    bundle_bytes, _, proof_sha, proof_id, candidate_snapshot_id = _build_bundle_bytes()
    missing_signature = _remove_archive_entry(
        bundle_bytes,
        entry="bundle/provenance-signature.json",
    )
    missing_sha = hashlib.sha256(missing_signature).hexdigest()

    payload = run_bundle_replay_drill(
        bundle_id="bundle-1",
        bundle_kind="SAFEGUARDED_DEPOSIT",
        bundle_sha256=missing_sha,
        bundle_bytes=missing_signature,
        expected_candidate_snapshot_id=candidate_snapshot_id,
        expected_provenance_proof_id=proof_id,
        expected_provenance_proof_artifact_sha256=proof_sha,
        selected_profile=None,
    )

    assert payload["drillStatus"] == "FAILED"
    assert payload["failureClass"] == "MISSING_ARTEFACT"


def test_run_bundle_replay_drill_classifies_profile_mismatch() -> None:
    bundle_bytes, bundle_sha256, proof_sha, proof_id, candidate_snapshot_id = _build_bundle_bytes()
    controlled_profile = get_bundle_profile(profile_id="CONTROLLED_EVIDENCE_CORE_V1")

    payload = run_bundle_replay_drill(
        bundle_id="bundle-1",
        bundle_kind="SAFEGUARDED_DEPOSIT",
        bundle_sha256=bundle_sha256,
        bundle_bytes=bundle_bytes,
        expected_candidate_snapshot_id=candidate_snapshot_id,
        expected_provenance_proof_id=proof_id,
        expected_provenance_proof_artifact_sha256=proof_sha,
        selected_profile=controlled_profile,
    )

    assert payload["drillStatus"] == "FAILED"
    assert payload["failureClass"] == "PROFILE_MISMATCH"
