#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
API_DIR = ROOT_DIR / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.documents.preprocessing_gold_set import regenerate_preprocess_gold_set_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Regenerate preprocessing gold-set baseline hashes using the canonical "
            "fixture pack and explicit approval metadata."
        )
    )
    parser.add_argument(
        "--approved-by",
        required=True,
        help="Reviewer or owner approving this baseline update.",
    )
    parser.add_argument(
        "--approval-reference",
        required=True,
        help="Review reference (ticket/PR/link) for this update.",
    )
    parser.add_argument(
        "--approval-summary",
        required=True,
        help="Short rationale for the approved baseline change.",
    )
    parser.add_argument(
        "--fixture-pack",
        default="api/tests/fixtures/preprocessing-gold-set/fixture-pack.v1.json",
        help="Path to the canonical preprocessing gold-set fixture pack.",
    )
    parser.add_argument(
        "--baseline-manifest",
        default="api/tests/fixtures/preprocessing-gold-set/baseline-manifest.v1.json",
        help="Path to the canonical preprocessing gold-set baseline manifest.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fixture_pack_path = ROOT_DIR / args.fixture_pack
    baseline_manifest_path = ROOT_DIR / args.baseline_manifest

    regenerate_preprocess_gold_set_manifest(
        fixture_pack_path=fixture_pack_path,
        baseline_manifest_path=baseline_manifest_path,
        approved_by=args.approved_by,
        approval_reference=args.approval_reference,
        approval_summary=args.approval_summary,
    )
    print(f"Updated baseline manifest: {baseline_manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
