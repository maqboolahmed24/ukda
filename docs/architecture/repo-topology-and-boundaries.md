# Repo Topology And Boundaries

> Status: Normative target topology
> Scope: Repository layout to build toward from Prompt 02 onward

The directory structure below is normative even before every directory exists. It defines ownership, not current completeness.

## Top-Level Ownership Map

| Directory             | Owns                                                                                                                                                | Must contain                                                                                                        | Must not contain                                                                             |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `/web`                | Browser application, routes, layouts, page composition, accessible interaction, authenticated asset access, and review workspaces                   | Next.js App Router code, route layouts, page-level data fetching, client/server components, browser tests           | Direct database access, long-running jobs, raw model-service calls, infrastructure manifests |
| `/api`                | HTTP API, auth/session boundaries, RBAC enforcement, orchestration endpoints, read/write domain services, audit emission, and secure asset proxying | FastAPI app, routers, domain services, persistence adapters, request validation, API tests                          | Browser UI code, background worker loops, direct public egress paths                         |
| `/workers`            | Asynchronous jobs, deterministic pipeline execution, model-service adapters, packaging, scheduled maintenance, and retryable background work        | Worker runtime, job modules, stage adapters, queue integration, worker tests                                        | Route handlers for the main browser app, ad hoc UI helpers, direct user-session logic        |
| `/packages/ui`        | Shared design tokens, themes, primitives, accessibility-safe browser components, and shell/workspace building blocks                                | Tokens, theme contracts, CSS variable exports, component primitives, visual test helpers                            | Domain-specific business workflows, API clients, project-specific page logic                 |
| `/packages/contracts` | Shared DTOs, schemas, enums, typed IDs, API contract helpers, and cross-service type definitions                                                    | Versioned contracts, validation schemas, shared types, generated or hand-authored contract helpers                  | Secrets, environment-specific endpoints, UI styling, persistence implementations             |
| `/infra`              | Deployment and runtime skeletons for secure environments                                                                                            | Containerization, environment overlays for `dev`, `staging`, `prod`, cluster/manifests templates, operational notes | Product business logic, domain policy code, UI assets                                        |

## Cross-Cutting Boundaries

### Internal-Only Model Execution

- Approved model calls originate from `/api` or `/workers`, never from `/web`.
- All model execution must route through an approved internal service map.
- No directory owns a direct external AI egress path.
- `/infra` may define how internal model services are deployed, but not change workflow semantics.

### Single Export Gateway

- Release outside the secure environment can only happen through the export-gateway capability defined in later phases.
- `/web` may expose export-request UI, `/api` may manage request state, and `/workers` may build release packs.
- No directory may introduce side-channel download or sync behavior that bypasses the governed export door.

### Append-Only Audit And Evidence Posture

- Audit events and evidence records are append-only by contract.
- `/api` and `/workers` may append events; `/web` reads derived views and never becomes a source of truth for audit state.
- Mutating workflow logic must emit auditable events instead of overwriting history in place.

## Boundary Discipline By Layer

### `/web`

- Owns user-facing navigation, deep links, zero-state handling, and bounded-scroll workspace composition.
- Can cache or derive presentation state, but not redefine domain truth.
- Must not talk directly to databases, object stores, or model endpoints.

### `/api`

- Owns request-level authorization, canonical mutations, and stable API contracts.
- Should be the first write boundary for project, document, review, manifest, and export state.
- Must not absorb worker-only execution loops or frontend-only presentational concerns.

### `/workers`

- Own deterministic background execution and compute-heavy phase pipelines.
- Must preserve provenance, run lineage, and retry semantics.
- Must not become a second ad hoc API surface.

### `/packages/ui`

- Own visual tokens and reusable shell/workspace primitives for the Obsidian web experience.
- Should stay generic enough to be reused across routes without carrying page-specific assumptions.
- Must not hide workflow rules inside presentational components.

### `/packages/contracts`

- Own shared language between browser, API, and workers.
- Should be the place for stable IDs, enums, request/response schemas, and shared validation helpers.
- Must not accumulate runtime secrets, deployment configuration, or side effects.

### `/infra`

- Owns runtime packaging and environment separation only.
- Must reflect the no-egress, internal-only, audit-first posture.
- Must not encode product behavior that belongs in application code or phase contracts.

## Current Scaffold Rule

Prompt 02 established the first scaffold for these directories. Future prompts must extend the existing `/web`, `/api`, `/workers`, `/packages/ui`, `/packages/contracts`, and `/infra` boundaries instead of creating parallel roots or alternate ownership paths.
