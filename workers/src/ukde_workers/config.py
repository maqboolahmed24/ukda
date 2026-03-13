from dataclasses import dataclass
from os import getenv
from socket import gethostname


def _read_int(env_key: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = getenv(env_key)
    if raw is None:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    if parsed < minimum:
        return minimum
    if parsed > maximum:
        return maximum
    return parsed


def _read_text(env_key: str, default: str) -> str:
    raw = getenv(env_key)
    if raw is None:
        return default
    candidate = raw.strip()
    return candidate if candidate else default


@dataclass(frozen=True)
class WorkerConfig:
    environment: str
    queue_name: str
    heartbeat_seconds: int
    poll_seconds: int
    worker_id: str
    run_loop_max_iterations: int

    @classmethod
    def from_env(cls) -> "WorkerConfig":
        hostname = gethostname().split(".")[0]
        return cls(
            environment=_read_text("APP_ENV", "dev"),
            queue_name=_read_text("WORKER_QUEUE_NAME", "ukde-jobs"),
            heartbeat_seconds=_read_int(
                "WORKER_HEARTBEAT_SECONDS",
                30,
                minimum=5,
                maximum=600,
            ),
            poll_seconds=_read_int(
                "WORKER_POLL_SECONDS",
                2,
                minimum=1,
                maximum=30,
            ),
            worker_id=_read_text("WORKER_ID", f"worker-{hostname}"),
            run_loop_max_iterations=_read_int(
                "WORKER_MAX_ITERATIONS",
                0,
                minimum=0,
                maximum=100000,
            ),
        )
