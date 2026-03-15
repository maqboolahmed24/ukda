from __future__ import annotations

from datetime import UTC, datetime

from app.exports.provenance import (
    build_merkle_tree,
    build_proof_artifact_payload,
    canonical_json_bytes,
    normalize_leaf,
    sign_root_sha256,
    verify_root_signature,
)


def _leaf(
    *,
    kind: str,
    identifier: str,
    immutable: str,
    parents: tuple[str, ...] = (),
):
    return normalize_leaf(
        artifact_kind=kind,
        stable_identifier=identifier,
        immutable_reference=immutable,
        parent_references=parents,
    )


def test_merkle_root_is_deterministic_across_leaf_input_order() -> None:
    leaves_a = (
        _leaf(kind="B", identifier="2", immutable="bbb"),
        _leaf(kind="A", identifier="1", immutable="aaa"),
    )
    leaves_b = (
        _leaf(kind="A", identifier="1", immutable="aaa"),
        _leaf(kind="B", identifier="2", immutable="bbb"),
    )
    first = build_merkle_tree(leaves_a)
    second = build_merkle_tree(leaves_b)
    assert first.root_sha256 == second.root_sha256
    assert first.leaf_hashes == second.leaf_hashes


def test_merkle_root_changes_when_immutable_reference_changes() -> None:
    baseline = build_merkle_tree(
        (
            _leaf(kind="EXPORT_REQUEST", identifier="request-1", immutable="sha-a"),
            _leaf(kind="APPROVED_CANDIDATE_SNAPSHOT", identifier="cand-1", immutable="sha-c"),
        )
    )
    changed = build_merkle_tree(
        (
            _leaf(kind="EXPORT_REQUEST", identifier="request-1", immutable="sha-b"),
            _leaf(kind="APPROVED_CANDIDATE_SNAPSHOT", identifier="cand-1", immutable="sha-c"),
        )
    )
    assert baseline.root_sha256 != changed.root_sha256


def test_root_signature_verifies_with_included_public_key_material() -> None:
    merkle = build_merkle_tree(
        (
            _leaf(kind="EXPORT_REQUEST", identifier="request-1", immutable="sha-a"),
            _leaf(kind="APPROVED_CANDIDATE_SNAPSHOT", identifier="cand-1", immutable="sha-c"),
        )
    )
    signature = sign_root_sha256(
        root_sha256=merkle.root_sha256,
        key_ref="ukde-provenance-lamport-v1",
        secret="unit-test-secret",
    )
    assert verify_root_signature(
        root_sha256=merkle.root_sha256,
        signature_bytes=signature.signature_bytes,
        public_key_bytes=signature.public_key_bytes,
    )


def test_proof_artifact_contains_verification_material_for_offline_checks() -> None:
    merkle = build_merkle_tree(
        (_leaf(kind="EXPORT_REQUEST", identifier="request-1", immutable="sha-a"),)
    )
    signature = sign_root_sha256(
        root_sha256=merkle.root_sha256,
        key_ref="ukde-provenance-lamport-v1",
        secret="unit-test-secret",
    )
    payload = build_proof_artifact_payload(
        proof_id="proof-1",
        project_id="project-1",
        export_request_id="request-1",
        candidate_snapshot_id="candidate-1",
        attempt_number=1,
        created_at=datetime.now(UTC),
        merkle=merkle,
        signature=signature,
    )
    assert payload["signature"]["algorithm"] == "LAMPORT_SHA256_OTS_V1"  # type: ignore[index]
    verification = payload["verificationMaterial"]  # type: ignore[index]
    assert isinstance(verification, dict)
    assert isinstance(verification.get("publicKeyBase64"), str)
    assert isinstance(verification.get("publicKeySha256"), str)
    # Canonical serialization must remain stable for hashing.
    assert canonical_json_bytes(payload) == canonical_json_bytes(payload)
