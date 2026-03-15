from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

_SHA256_HEX_CHARS = frozenset("0123456789abcdef")
_LAMPORT_SIGNATURE_CHUNK_COUNT = 256
_LAMPORT_PRIVATE_VALUE_COUNT = _LAMPORT_SIGNATURE_CHUNK_COUNT * 2
_LAMPORT_VALUE_SIZE = 32


class ProvenanceComputationError(RuntimeError):
    """Provenance graph material cannot be canonicalized or signed."""


@dataclass(frozen=True)
class ProvenanceLeaf:
    artifact_kind: str
    stable_identifier: str
    immutable_reference: str
    parent_references: tuple[str, ...]

    def as_canonical_dict(self) -> dict[str, object]:
        return {
            "artifact_kind": self.artifact_kind,
            "immutable_reference": self.immutable_reference,
            "parent_references": list(self.parent_references),
            "stable_identifier": self.stable_identifier,
        }


@dataclass(frozen=True)
class MerkleTreeResult:
    ordered_leaves: tuple[ProvenanceLeaf, ...]
    leaf_hashes: tuple[str, ...]
    root_sha256: str


@dataclass(frozen=True)
class LamportSignatureResult:
    algorithm: str
    key_ref: str
    signature_bytes: bytes
    public_key_bytes: bytes
    public_key_sha256: str

    def signature_base64(self) -> str:
        return base64.b64encode(self.signature_bytes).decode("ascii")

    def public_key_base64(self) -> str:
        return base64.b64encode(self.public_key_bytes).decode("ascii")


def canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def normalize_leaf(
    *,
    artifact_kind: str,
    stable_identifier: str,
    immutable_reference: str,
    parent_references: Sequence[str] | None = None,
) -> ProvenanceLeaf:
    kind = artifact_kind.strip()
    identifier = stable_identifier.strip()
    immutable = immutable_reference.strip()
    if not kind or not identifier or not immutable:
        raise ProvenanceComputationError(
            "artifact_kind, stable_identifier, and immutable_reference are required."
        )
    parent_items: list[str] = []
    if parent_references is not None:
        for item in parent_references:
            normalized = item.strip()
            if not normalized or normalized in parent_items:
                continue
            parent_items.append(normalized)
    parent_items.sort()
    return ProvenanceLeaf(
        artifact_kind=kind,
        stable_identifier=identifier,
        immutable_reference=immutable,
        parent_references=tuple(parent_items),
    )


def canonical_leaf_bytes(leaf: ProvenanceLeaf) -> bytes:
    return canonical_json_bytes(leaf.as_canonical_dict())


def build_merkle_tree(leaves: Sequence[ProvenanceLeaf]) -> MerkleTreeResult:
    if not leaves:
        raise ProvenanceComputationError("At least one provenance leaf is required.")
    ordered = tuple(
        sorted(
            leaves,
            key=lambda item: (item.artifact_kind, item.stable_identifier),
        )
    )
    leaf_hashes = tuple(
        hashlib.sha256(canonical_leaf_bytes(item)).hexdigest() for item in ordered
    )
    level = [bytes.fromhex(item) for item in leaf_hashes]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        next_level: list[bytes] = []
        for index in range(0, len(level), 2):
            next_level.append(hashlib.sha256(level[index] + level[index + 1]).digest())
        level = next_level
    return MerkleTreeResult(
        ordered_leaves=ordered,
        leaf_hashes=leaf_hashes,
        root_sha256=level[0].hex(),
    )


def _assert_sha256_hex(value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(ch not in _SHA256_HEX_CHARS for ch in normalized):
        raise ProvenanceComputationError("Root hash must be a 64-character SHA-256 hex digest.")
    return normalized


def _derive_lamport_seed(*, root_sha256: str, secret: str) -> bytes:
    normalized_root = _assert_sha256_hex(root_sha256)
    if not secret.strip():
        raise ProvenanceComputationError("Signing secret is required.")
    return hmac.new(
        secret.encode("utf-8"),
        bytes.fromhex(normalized_root),
        hashlib.sha256,
    ).digest()


def _derive_lamport_private_values(seed: bytes) -> tuple[bytes, ...]:
    values: list[bytes] = []
    for index in range(_LAMPORT_PRIVATE_VALUE_COUNT):
        value = hmac.new(seed, index.to_bytes(4, "big"), hashlib.sha256).digest()
        if len(value) != _LAMPORT_VALUE_SIZE:
            raise ProvenanceComputationError("Derived Lamport key material has invalid length.")
        values.append(value)
    return tuple(values)


def sign_root_sha256(
    *,
    root_sha256: str,
    key_ref: str,
    secret: str,
) -> LamportSignatureResult:
    normalized_root = _assert_sha256_hex(root_sha256)
    normalized_key_ref = key_ref.strip()
    if not normalized_key_ref:
        raise ProvenanceComputationError("Signing key reference is required.")

    seed = _derive_lamport_seed(root_sha256=normalized_root, secret=secret)
    private_values = _derive_lamport_private_values(seed)
    root_bytes = bytes.fromhex(normalized_root)

    signature_parts: list[bytes] = []
    public_key_parts: list[bytes] = []
    for index in range(_LAMPORT_SIGNATURE_CHUNK_COUNT):
        base = index * 2
        left = private_values[base]
        right = private_values[base + 1]
        public_key_parts.append(hashlib.sha256(left).digest())
        public_key_parts.append(hashlib.sha256(right).digest())
        bit = (root_bytes[index // 8] >> (7 - (index % 8))) & 1
        signature_parts.append(right if bit else left)

    signature_bytes = b"".join(signature_parts)
    public_key_bytes = b"".join(public_key_parts)
    return LamportSignatureResult(
        algorithm="LAMPORT_SHA256_OTS_V1",
        key_ref=normalized_key_ref,
        signature_bytes=signature_bytes,
        public_key_bytes=public_key_bytes,
        public_key_sha256=hashlib.sha256(public_key_bytes).hexdigest(),
    )


def verify_root_signature(
    *,
    root_sha256: str,
    signature_bytes: bytes,
    public_key_bytes: bytes,
) -> bool:
    normalized_root = _assert_sha256_hex(root_sha256)
    expected_signature_size = _LAMPORT_SIGNATURE_CHUNK_COUNT * _LAMPORT_VALUE_SIZE
    expected_public_size = _LAMPORT_PRIVATE_VALUE_COUNT * _LAMPORT_VALUE_SIZE
    if len(signature_bytes) != expected_signature_size:
        return False
    if len(public_key_bytes) != expected_public_size:
        return False

    root_bytes = bytes.fromhex(normalized_root)
    for index in range(_LAMPORT_SIGNATURE_CHUNK_COUNT):
        sig_start = index * _LAMPORT_VALUE_SIZE
        sig_end = sig_start + _LAMPORT_VALUE_SIZE
        signature_chunk = signature_bytes[sig_start:sig_end]
        bit = (root_bytes[index // 8] >> (7 - (index % 8))) & 1
        public_index = index * 2 + bit
        pub_start = public_index * _LAMPORT_VALUE_SIZE
        pub_end = pub_start + _LAMPORT_VALUE_SIZE
        expected_hash = public_key_bytes[pub_start:pub_end]
        if hashlib.sha256(signature_chunk).digest() != expected_hash:
            return False
    return True


def build_proof_artifact_payload(
    *,
    proof_id: str,
    project_id: str,
    export_request_id: str,
    candidate_snapshot_id: str,
    attempt_number: int,
    created_at: datetime,
    merkle: MerkleTreeResult,
    signature: LamportSignatureResult,
) -> dict[str, object]:
    return {
        "attemptNumber": attempt_number,
        "candidateSnapshotId": candidate_snapshot_id,
        "createdAt": created_at.isoformat(),
        "exportRequestId": export_request_id,
        "leafHashes": list(merkle.leaf_hashes),
        "leaves": [leaf.as_canonical_dict() for leaf in merkle.ordered_leaves],
        "merkle": {
            "algorithm": "SHA-256",
            "leafCount": len(merkle.ordered_leaves),
            "rootSha256": merkle.root_sha256,
        },
        "proofId": proof_id,
        "projectId": project_id,
        "schemaVersion": 1,
        "signature": {
            "algorithm": signature.algorithm,
            "keyRef": signature.key_ref,
            "signatureBase64": signature.signature_base64(),
        },
        "verificationMaterial": {
            "publicKeyAlgorithm": signature.algorithm,
            "publicKeyBase64": signature.public_key_base64(),
            "publicKeySha256": signature.public_key_sha256,
            "rootHashAlgorithm": "SHA-256",
        },
    }
