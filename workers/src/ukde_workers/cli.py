import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict, replace

from ukde_workers.config import WorkerConfig
from ukde_workers.runtime import run_loop, run_once, status_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="UKDE worker bootstrap CLI")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["status", "run-once", "run"],
        default="status",
        help=(
            "status prints bootstrap metadata; "
            "run-once executes one queue pass; "
            "run executes the polling loop."
        ),
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help=(
            "Optional polling-iteration cap for the run command. "
            "When omitted, WORKER_MAX_ITERATIONS is used."
        ),
    )
    return parser


def run_cli(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = WorkerConfig.from_env()

    if isinstance(args.max_iterations, int) and args.max_iterations >= 0:
        config = replace(config, run_loop_max_iterations=args.max_iterations)

    if args.command == "run-once":
        print(json.dumps(asdict(run_once(config)), sort_keys=True))
        return 0

    if args.command == "run":
        for result in run_loop(config):
            print(json.dumps(asdict(result), sort_keys=True))
        return 0

    print(json.dumps(status_payload(config), indent=2, sort_keys=True))
    return 0
