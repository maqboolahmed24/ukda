# Performance Capacity Evidence And Degraded-State Contract (Prompt 95)

This document defines the Prompt 95 baseline for repeatable performance evidence across uploads, viewer rendering, inference pipelines, review workspaces, and search.

## Capacity Run Model

Persisted table: `capacity_test_runs`

Required columns:

- `id`
- `test_kind` (`LOAD | SOAK | BENCHMARK`)
- `scenario_name`
- `status` (`QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELED`)
- `results_key`
- `results_sha256`
- `started_by`
- `started_at`
- `finished_at`
- `created_at`

Implementation keeps additional structured fields (`scenario_json`, `results_json`, `failure_reason`) for deterministic replay and diagnostics.

## Capacity APIs And RBAC

- `POST /admin/capacity/tests` (`ADMIN` only)
- `GET /admin/capacity/tests` (`ADMIN`, `AUDITOR`)
- `GET /admin/capacity/tests/{testRunId}` (`ADMIN`, `AUDITOR`)
- `GET /admin/capacity/tests/{testRunId}/results` (`ADMIN`, `AUDITOR`)

Server-side handlers enforce role checks independently of web route gating.

## Canonical Scenarios

- `uploads-viewer-search-load-v1`
- `inference-review-soak-v1`
- `end-to-end-benchmark-v1`

Runs are scenario-named deterministically and results are persisted as canonical JSON with SHA-256 content hashes.

## Evidence Payload Contract

Each results payload includes:

- critical-flow p95 latency evidence for upload, viewer render, inference, review workspace, and search
- sustained throughput target and observed jobs/minute
- 24-hour soak requirement evidence and pass/fail state
- GPU utilization and warm-start evidence
- capacity model slices:
  - storage
  - CPU
  - GPU
  - model-service concurrency
  - queue depth/latency
- envelope evidence for:
  - `transcription-vlm`
  - `assist-llm`
  - `privacy-ner`
  - `privacy-rules`
  - `transcription-fallback`
  - `embedding-search`
- explicit gate booleans for critical-flow p95, throughput, soak, GPU SLO, warm-start, envelope conformance, and evidence persistence.

## Performance Tuning Hooks

Prompt 95 baseline hooks are measurable and surfaced in evidence:

- GPU batching controls in transcription worker orchestration
- model warmup attempts for approved VLM paths when warm start is enabled
- in-process thumbnail cache (TTL-bounded)
- in-process overlay cache (TTL-bounded)
- search/index tuning via document-filter indexes plus optional trigram acceleration when `pg_trgm` is available

## Web Admin Surfaces

- `/admin/capacity/tests`
- `/admin/capacity/tests/:testRunId`

Surfaces are operations-grade: dense tabular evidence, deterministic status states, and run-level artifact identifiers (`resultsKey`, `resultsSha256`).

## Degraded-State Rules

Heavy-workflow degraded states must stay distinct from failure states:

- degraded polling means visibility is reduced, not that work stopped
- no fake completion/progress claims
- no full-page blocking for transient polling issues
- failure and data-loss states remain explicit and separate from degraded visibility states

## Cross-Prompt Assumptions

Later hardening/recovery/release prompts can assume:

- capacity evidence is persisted and retrievable through admin APIs
- benchmark/load/soak runs are audit-traced and role-gated
- warmup/batching/cache/search tuning hooks are represented in persisted evidence
- degraded-state messaging semantics are consistent across long-running pipeline status surfaces
