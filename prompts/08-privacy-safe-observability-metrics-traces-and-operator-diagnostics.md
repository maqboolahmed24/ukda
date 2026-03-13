You are the implementation agent for UKDE. Work directly in the repository. Avoid clarifying questions unless a blocker or conflicting repository state makes a correct implementation impossible. Inspect the repository, read the listed source files, make the changes, run validations, and then return a concise engineering summary.

This prompt is both independent and sequenced:
- Independent: do not rely on chat memory; reread only the relevant repo areas and the listed phase files before changing anything.
- Sequenced: extend existing implementation where present.

The local `/phases` directory is the product source of truth for behavior and acceptance logic. Read the relevant phase files first on each run.

## Mandatory first actions
1. Inspect the relevant repository areas and any existing implementation this prompt may extend.
2. Read these precise local phase files from repo root before making changes:
   - `/phases/README.md`
   - `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md`
   - `/phases/blueprint-ukdataextraction.md`
   - `/phases/ui-premium-dark-blueprint-obsidian-folio.md`
   - `/phases/phase-00-foundation-release.md`
   - `/phases/phase-11-hardening-scale-pentest-readiness.md` for the future-facing observability and SLO shape, without drifting into unrelated late-phase product work
3. Then review the current repo implementation context generally — existing code, configs, docs, scripts, tests, and implementation notes already present in the repo — only to reconcile with what already exists. Treat those as implementation context, not canonical product truth.
4. Reconcile with the current repo state. Do not create a second telemetry stack beside whatever already exists.

## Source-of-truth hierarchy
Use this precedence order when implementing:
1. The specific `/phases` files listed in this prompt for product behavior and acceptance logic.
2. `/phases/WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md` when this prompt depends on web-first execution semantics.
3. `/phases/UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md` when this prompt depends on recall-first, rescue, token-anchor, search-anchoring, or conservative-masking semantics.
4. `/phases/blueprint-ukdataextraction.md`, `/phases/README.md`, and `/phases/ui-premium-dark-blueprint-obsidian-folio.md` as supporting product context when they are listed or clearly relevant.
5. This prompt for task scope and deliverables.
6. Current repository state for reconciling implementation details.
7. Official external docs for implementation mechanics only.

Treat current repository state as implementation context, not as the primary source of product truth.

## Conflict-resolution rule
- `/phases` wins for privacy-safe logging rules, governance boundaries, operator access boundaries, and what telemetry is allowed to exist at all.
- Official docs win only for implementation mechanics such as OpenTelemetry setup, App Router/ASGI instrumentation, and browser/admin-surface mechanics.
- Do not let observability convenience weaken controlled-environment safeguards.

## External official reference pack for mechanics only
Use only official docs, and only for implementation mechanics.

### OpenTelemetry
- https://opentelemetry.io/docs/
- https://opentelemetry.io/docs/languages/python/
- https://opentelemetry.io/docs/languages/python/instrumentation/
- https://opentelemetry.io/docs/languages/python/propagation/
- https://opentelemetry.io/docs/languages/js/
- https://opentelemetry.io/docs/languages/js/propagation/
- https://opentelemetry.io/docs/concepts/context-propagation/
- https://opentelemetry.io/docs/concepts/signals/metrics/

### Next.js
- https://nextjs.org/docs/app/getting-started/layouts-and-pages
- https://nextjs.org/docs/app/getting-started/fetching-data
- https://nextjs.org/docs/app/getting-started/error-handling
- https://nextjs.org/docs/app/api-reference/config/next-config-js/logging

### FastAPI
- https://fastapi.tiangolo.com/tutorial/middleware/
- https://fastapi.tiangolo.com/advanced/middleware/
- https://fastapi.tiangolo.com/tutorial/testing/

### Accessibility
- https://www.w3.org/TR/WCAG22/
- https://www.w3.org/WAI/ARIA/apg/

## Objective
Implement privacy-safe observability, metrics, traces, and operator diagnostics without weakening governance.

This prompt owns:
- structured operational logging hygiene
- metrics baseline
- trace propagation baseline
- safe internal telemetry boundaries
- operator and auditor diagnostics surfaces for the signals that genuinely exist now
- SLO/alert scaffolding that later work can extend
- documentation of telemetry privacy rules

This prompt does not own:
- the full Phase 11 production-hardening program
- jobs framework implementation
- export workflow implementation
- external monitoring SaaS integration
- product analytics or behavior-tracking fluff

## Phase alignment you must preserve
From Phase 0 Iteration 0.3:
- structured logs with `request_id` and safe `project_id`
- metrics:
  - request latency
  - error rate
  - queue size (foundation only if jobs are not yet real)
- logs must not leak tokens, passwords, raw document content, or similarly unsafe material

From Phase 11 Iteration 11.0:
- observability must trend toward end-to-end health, throughput, latency, and alertability
- tracing across API, workers, storage, and model services is the future posture
- admin-managed operations surfaces exist
- auditor read-only visibility is explicit and bounded

Implement the Phase 0 and early Phase 11 foundation only.
Do not jump ahead into unrelated late-phase product features.

## Telemetry privacy and governance rules
These are non-negotiable:
- no raw document content in logs
- no transcript text in logs
- no raw file bytes in logs
- no auth tokens, cookies, secrets, or credentials in logs
- no unrestricted raw request-body dumping
- no raw free-text user inputs as metric labels
- no high-cardinality labels that encode document IDs, user emails, or arbitrary text
- project observability should prefer safe identifiers or coarse aggregation, not human-sensitive labels
- no third-party public telemetry export by default
- any exporter or collector path must be internal-only and explicitly configurable

If the current repo already emits unsafe logs, fix or bound that behavior in this prompt.

## Implementation scope

### 1. Telemetry privacy policy and safe schemas
Create or refine a telemetry privacy contract for the repo.

Requirements:
- define what may be logged
- define what may never be logged
- define safe metric labels
- define trace attribute allowlists
- define redaction/scrubbing behavior
- document how telemetry differs from append-only audit events
- keep telemetry useful for operators without turning it into a second unsafe data exhaust

### 2. API instrumentation baseline
Instrument the API with a practical baseline.

At minimum support:
- request count
- request latency
- error count/rate
- DB readiness latency
- auth success/failure counts where useful
- audit-write success/failure counts if the audit layer exists
- health/readiness surface timing
- request correlation with `request_id`
- trace context support across incoming and outgoing calls where applicable

Keep instrumentation centralized and minimal.

### 3. Web instrumentation baseline
Instrument the web app only to the degree that it helps operations and debugging without becoming invasive.

Requirements:
- preserve trace context when the web app calls the API through server-side or BFF paths
- support safe server-side logging around major failures
- support a small, safe diagnostics surface for the current shell and auth/project flows
- do not add consumer-style analytics, trackers, or marketing pixels
- do not create noisy client-side telemetry spam

### 4. Worker and future queue foundation
This prompt does not build the jobs system.
It must still lay observability groundwork that later worker and queue implementation can plug into.

Requirements:
- if `/workers` exists, add minimal service instrumentation or heartbeat wiring
- expose queue-depth or worker-health metrics only if there is already a real source; otherwise surface them as unavailable/placeholder through the same contract
- avoid fake precision
- keep the contract extensible for the jobs/runtime layer and later operational work

### 5. Operations and diagnostics surfaces
Implement or refine restrained internal operations surfaces that reflect only the signals that actually exist now.

- `/web/app/(authenticated)/admin/operations/page.tsx`
- `/web/app/(authenticated)/admin/operations/slos/page.tsx`
- `/web/app/(authenticated)/admin/operations/alerts/page.tsx`
- `/web/app/(authenticated)/admin/operations/timelines/page.tsx`

And corresponding API read surfaces as appropriate.

Requirements:
- `ADMIN` can access operations surfaces
- `AUDITOR` may access only the explicitly safe, read-only subsets
- current signals must be accurate; unavailable later-phase signals must be shown as not yet available, not faked
- UI must be minimal, dark, dense, and calm
- avoid flashy graphs for their own sake
- favor legible status blocks, concise charts, and clear thresholds
- the operations UI should feel like a serious internal console, not a NOC-wall gimmick

### 6. SLOs and alert scaffolding
Implement a small but real baseline for:
- service availability target
- health/readiness expectations
- request-latency thresholds
- error-rate thresholds
- audit-write failure alerts if the audit layer exists
- DB readiness degradation thresholds
- worker/queue thresholds only if the underlying signals already exist

This may be config-driven and read-only at this stage.
It does not need to be a full pager system.
It does need to be explicit, testable, and documented.

### 7. Internal metrics/export path
Implement a consistent internal-only metrics/export strategy.

Use the pattern that best suits the repository, such as:
- internal metrics endpoint
- internal OTLP exporter configuration
- internal collector-ready configuration

Requirements:
- no public metrics endpoint by accident
- local dev path is clear
- staging/prod path is configurable
- exporter behavior is documented
- failure modes are explicit

### 8. Documentation
Document:
- telemetry privacy rules
- log/metric/trace boundaries
- available operations surfaces
- current SLOs and alert thresholds
- local validation path
- any not-yet-available signals and why they are deferred

## Required deliverables

### Backend / workers
- telemetry/instrumentation modules
- metrics and tracing setup
- safe logging configuration
- operations read endpoints
- tests

### Web
- `/admin/operations`
- `/admin/operations/slos`
- `/admin/operations/alerts`
- `/admin/operations/timelines`

### Docs
- observability and diagnostics doc
- telemetry privacy rules doc
- any README updates required for local validation

## Allowed touch points
You may modify:
- `/web/**`
- `/api/**`
- `/workers/**`
- `/packages/contracts/**`
- `/packages/ui/**`
- root config/task files
- `README.md`
- `docs/**`

Do not modify `/phases/**`.

## Non-goals
Do not implement any of the following here:
- public analytics or third-party marketing telemetry
- full-blown external observability-vendor lock-in
- jobs framework
- export workflow
- ingest, preprocessing, layout, transcription, privacy, governance, provenance, search, or discovery features
- a noisy dashboard that exposes more than operators actually need

## Testing and validation
Before finishing:
1. Verify request latency and error metrics are emitted.
2. Verify trace propagation or correlation is present across at least the main web-to-API path.
3. Verify unsafe fields are scrubbed from logs and trace attributes.
4. Verify metrics labels remain low-cardinality and privacy-safe.
5. Verify operations surfaces render current signals accurately.
6. Verify admin/auditor access boundaries.
7. Verify local startup and local validation instructions work.
8. Verify docs match the implemented config and commands.
9. Confirm `/phases/**` is untouched.

Where possible, include tests for:
- telemetry presence on critical request paths
- alert-threshold evaluation behavior
- scrubber behavior for secrets/tokens/raw content
- safe failure when an exporter or collector is unavailable

## Acceptance criteria
This prompt is complete only if all are true:
- privacy-safe structured logging baseline exists
- metrics baseline exists
- trace/correlation baseline exists
- operations diagnostics surfaces exist
- SLO and alert scaffolding exists
- no unsafe public telemetry path is introduced
- telemetry does not leak sensitive data
- diagnostics views expose logs/metrics/traces with consistent filters, pagination, and keyboard-accessible controls
- `/phases` remains untouched

## Final response format
Return:
1. What you changed
2. Files created/updated
3. Commands run
4. Validation results
5. Any tightly scoped assumptions, limitations, or follow-up risks
