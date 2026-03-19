# UKDE Workers

This package owns the Phase 0 worker runtime baseline for UKDE jobs.

Current capabilities:

- `ukde-worker status` prints worker/runtime posture and queue-depth visibility
- `ukde-worker run-once` performs one claim/execute/finalize cycle
- `ukde-worker run` performs the polling loop (bounded by `WORKER_MAX_ITERATIONS` or `--max-iterations`)
- Worker handlers cover NOOP, ingest extraction/thumbnail, preprocess orchestration/page/finalize, layout orchestration/page/finalize, and transcription orchestration/page/finalize.
