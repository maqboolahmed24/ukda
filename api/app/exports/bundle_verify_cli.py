from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from app.exports.verification import verify_bundle_archive_bytes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify a deposit bundle archive offline using bundled proof material."
    )
    parser.add_argument(
        "bundle_path",
        help="Path to the deposit bundle zip archive.",
    )
    parser.add_argument(
        "--expected-sha256",
        default=None,
        help="Optional pinned bundle hash to enforce during verification.",
    )
    return parser


def run_cli(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    bundle_path = Path(str(args.bundle_path)).expanduser().resolve()
    if not bundle_path.exists() or not bundle_path.is_file():
        parser.error(f"Bundle file does not exist: {bundle_path}")

    bundle_bytes = bundle_path.read_bytes()
    output = verify_bundle_archive_bytes(
        bundle_bytes,
        expected_bundle_sha256=(
            str(args.expected_sha256).strip() if isinstance(args.expected_sha256, str) else None
        ),
    )
    print(json.dumps(output.payload, indent=2, sort_keys=True))
    return 0 if output.result == "VALID" else 1


if __name__ == "__main__":  # pragma: no cover - exercised as command entry point.
    raise SystemExit(run_cli())
