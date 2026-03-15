from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from app.core.config import get_settings
from app.exports.store import ExportStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a deterministic provenance replay drill over a stored bundle lineage "
            "using pinned candidate/proof references and optional profile validation."
        )
    )
    parser.add_argument("project_id", help="Project identifier.")
    parser.add_argument("export_request_id", help="Export request identifier.")
    parser.add_argument("bundle_id", help="Bundle identifier.")
    parser.add_argument(
        "--profile",
        default=None,
        help="Optional bundle validation profile id (for replayed profile validation).",
    )
    return parser


def run_cli(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = get_settings()
    store = ExportStore(settings)
    payload = store.run_bundle_replay_drill(
        project_id=str(args.project_id).strip(),
        export_request_id=str(args.export_request_id).strip(),
        bundle_id=str(args.bundle_id).strip(),
        profile_id=(str(args.profile).strip() if isinstance(args.profile, str) else None),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if str(payload.get("drillStatus")) == "SUCCEEDED" else 1


if __name__ == "__main__":  # pragma: no cover - exercised by command entry point.
    raise SystemExit(run_cli())

