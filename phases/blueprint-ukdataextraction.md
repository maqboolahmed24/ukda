# UKDataExtraction (UKDE) Product Blueprint

> A secure, audit-first platform for transcribing difficult archival handwriting, applying conservative de-identification, and producing screened export candidates inside a controlled research environment.

This document sits above the numbered phase specifications in this folder. It defines the product vision, governance posture, architecture boundaries, and delivery logic that the implementation phases are expected to follow.

Canonical product-wide experience layer reference:

- [Obsidian Folio: Premium Dark Experience Blueprint](./ui-premium-dark-blueprint-obsidian-folio.md)

Normative architecture override reference:

- [Updated System: Smarter Recall-First Patch](./UPDATED-SYSTEM-SMARTER-RECALL-FIRST-PATCH.md)
- [Web-First Normative Execution Patch](./WEB-FIRST-NORMATIVE-EXECUTION-PATCH.md)

## At a Glance

| Dimension | Blueprint |
| --- | --- |
| Mission | Turn hard-to-read archival scans into reviewable, governed text products without weakening controlled-environment safeguards. |
| Core users | Researchers (`RESEARCHER`), reviewers (`REVIEWER`), project leads (`PROJECT_LEAD`), administrators (`ADMIN`), and auditors (`AUDITOR`). |
| Operating posture | Process in place, keep evidence, route uncertainty to humans, and allow release only through screening. |
| Success signal | Better throughput than manual handling, conservative privacy protection, and auditable export readiness. |

## 1. Product Goal and Definition of Success

### Primary outcomes

1. Transcribe handwriting, marginalia, stamps, crossings-out, and other difficult archival material where conventional OCR fails.
2. Preserve layout and provenance so every transcript can be reviewed against the source image.
3. De-identify by default and prepare safeguarded or open export candidates with a defensible audit trail.

### Definition of success

| Area | What success looks like |
| --- | --- |
| Transcription quality | Character and word error rates improve against a curated gold set; confidence scores reliably separate auto-accepted lines from review-required lines. |
| Reviewer efficiency | Reviewer time per page drops meaningfully relative to fully manual transcription. |
| Redaction quality | Direct-identifier recall is conservatively high, with low residual disclosure findings during output checking. |
| Governance quality | Every released file carries purpose scope, lineage, manifest data, and reviewer sign-off. |
| Operational safety | No unscreened export path exists, and no processing depends on external model APIs. |

## 2. Guiding Principles

1. **Process in place.** All model inference, review, storage, and packaging stay inside the secure environment.
2. **Evidence over assertion.** Model outputs are hypotheses with confidence and provenance, never silent truth.
3. **Confidence drives workflow.** Low-certainty transcription and privacy findings are routed to humans instead of hidden by automation.
4. **Safe outputs are product functionality.** Release screening is not a manual side process; it is part of the core system.
5. **Version everything.** Artefacts, models, policies, and reviewer decisions must remain reproducible and immutable.
6. **Web-first execution contract.** The active prompt program builds a secure browser-delivered product surface first, translating older desktop-only interaction language into equivalent web patterns without changing workflow or governance intent.
7. **Adaptive workspace contract.** High-density workspaces use state-based adaptive composition with bounded overflow, keyboard-first controls, deep-linkable routes, and accessibility-safe reflow behavior.

## 3. Users and Operating Model

### User roles

| Role | Responsibilities |
| --- | --- |
| `RESEARCHER` | Upload scans, inspect transcripts, request reviewable output candidates, and work within the declared project purpose. |
| `REVIEWER` | Resolve low-confidence transcription segments, perform privacy and disclosure review tasks assigned in workflow, and approve reviewer-governed stages. |
| `PROJECT_LEAD` | Define project purpose, scope, and access intent; approve policy configuration and governance choices. |
| `ADMIN` | Manage infrastructure, identity, keys, models, audit controls, and operational hardening. |
| `AUDITOR` | Hold read-only governance access to audit trails, policy and pseudonym-registry governance views, evidence ledgers, proof verification, release-review records, and later index-quality or operations export-status surfaces. |

### End-to-end workflow

1. A project is created with a declared purpose, dataset scope, and intended access tier.
2. Scans are imported into a controlled workspace with immutable source capture.
3. The transcription pipeline produces diplomatic text, optional normalised text, layout alignment, and confidence metadata.
4. The sensitivity pipeline detects direct and indirect disclosure risks and applies policy-driven masking, pseudonymisation, or generalisation.
5. Human reviewers resolve uncertainty, approve or override decisions, and create a governed review trail.
6. The system generates governance artefacts, controlled master records, and immutable candidate snapshots for any artefact that may later enter release review.
7. Nothing leaves the environment unless a candidate snapshot passes through output screening and release approval.

## 4. Product Architecture

### Deployment model

UKDataExtraction (UKDE) is SecureLab-native by design:

- No external AI APIs.
- Approved internal model services and rule-native services are the only supported processing path.
- Model weights are vetted, stored internally, version-pinned, and loaded from approved local or internal artefact storage.
- Processing happens inside the secure environment.
- Export screening is the only egress route.

### Logical components

| Component | Responsibility |
| --- | --- |
| Secure UI | Project dashboard, document viewer, transcript editor, redaction review workspace, and export request flows, delivered as a secure web application and aligned to the shared adaptive workspace contract for dense operational surfaces. |
| Orchestration layer | Job queue, workflow engine, retries, provenance capture, and status tracking. |
| Internal model service map | Approved routing layer that binds stable model roles to internal endpoints, artefact roots, and response contracts without changing workflow routes. |
| GPU workers | Stage-specific adapters for transcription, assist, NER, and embedding workloads, using OpenAI-compatible chat or embedding services where appropriate and native adapters where required. |
| CPU workers | Image preprocessing, layout analysis, packaging, hashing, manifest generation, policy evaluation, and rule-native privacy services such as Presidio. |
| Object storage | Immutable images, derivatives, overlays, packages, and signed artefacts. |
| Metadata database | Projects, documents, pages, regions, runs, findings, reviewer actions, and package state. |
| Ledger store | Append-only audit and redaction evidence with tamper-evident design. |
| Governance services | Policy engine, RBAC, training or agreement gates, key management, and export gateway controls. |

## 5. Data Model and Versioning

### Core entities

| Entity | What must be persisted |
| --- | --- |
| Project | Purpose statement, dataset scope, intended access tier, retention policy, approvals, and membership. |
| Document | Source information, ingest timestamp, checksum, page inventory, and import lineage. |
| Page | Original image reference, preprocessing versions, quality metrics, and layout version links. |
| Region | Type, reading-order relationships, polygon geometry, and page anchors. |
| Transcript segment | Diplomatic text, optional normalised text, confidence, alignment data, model version, and reviewer state. |
| Redaction event | Category, basis, confidence, location, before and after values in Controlled space, and reviewer decisions. |
| Manifest | Package contents, file hashes, model versions, policy versions, reviewer sign-offs, and release state. |

### Versioning rules

1. Every pipeline stage creates a new immutable artefact version.
2. Every manifest references exact artefact hashes and exact model or policy versions.
3. Reviewer overrides never overwrite history; they append new decisions and new derived outputs.
4. Controlled evidence and safeguarded derivatives remain linked, but tier boundaries are never collapsed.
5. Any artefact submitted for external release is frozen as an immutable candidate snapshot before Phase 8 review begins.

## 6. Transcription Pipeline

### Stage 1: Ingest and preprocessing

Purpose:

- stabilise difficult scans before downstream analysis
- improve readability for both models and reviewers

Typical steps:

- de-skew
- de-noise
- contrast equalisation
- bleed-through reduction
- resolution and orientation checks

Outputs:

- preprocessed page assets
- page quality metrics
- preprocessing run metadata

### Stage 2: Layout mapping

Purpose:

- preserve non-linear reading order across columns, margins, inserts, and stamps

Core design choice:

- represent reading order as a graph, not a flat list

Outputs:

- region polygons
- layout graph
- overlay artefacts for the viewer

### Stage 3: Handwriting transcription

Requirements:

- read handwriting and layout together
- use a layout-aware VLM as the primary transcription path while retaining audited fallback engines
- emit diplomatic transcript as written
- optionally emit a normalised transcript
- provide confidence and region alignment

Operating rule:

- transcript output is a machine hypothesis with uncertainty, not an unquestioned final record

### Stage 4: Constrained language assistance

Purpose:

- support consistency checking without free-form rewriting
- run through approved internal LLM services only

Allowed behaviour:

- suggest alternatives for ambiguous characters
- use local context to resolve likely readings
- flag low-confidence segments for review

Outputs:

- review queue
- quality report
- confidence-based triage signals

## 7. Sensitivity, Redaction, and Provenance

### Detection

UKDE uses detector fusion rather than a single model:

- pattern rules for emails, phone numbers, postcodes, IDs, and structured identifiers
- local NER for people, places, and organisations
- optional local LLM assistance for conservative triage and reviewer explanation, never as a silent release decision path
- context cues for sensitive subject matter
- linkage-risk heuristics for disclosive combinations

### Decision engine

Per-project policy determines:

- which categories are in scope
- whether each category is masked, pseudonymised, or generalised
- confidence thresholds for auto-application versus review
- depositor or project-specific exceptions

### Proof and reviewability

The system produces two governance artefacts:

| Artefact | Purpose |
| --- | --- |
| Redaction manifest | Screening-safe summary of what was changed, where, why, and under which policy or confidence rule; later included in release packs when approved. |
| Redaction ledger | Controlled-only evidence store containing before and after values, rationale, model or rule basis, timestamps, and actor identity. |

The ledger exists to demonstrate due diligence without relying on vague anonymisation claims.

## 8. Access Tiers and Safe Outputs

### Package types

| Tier | Contents | Rules |
| --- | --- | --- |
| Controlled | Images, diplomatic transcript, optional normalised transcript, alignments, annotations, full evidence ledger, full-fidelity indexes. | Never leaves the secure environment. |
| Safeguarded | Redacted transcript, redaction manifest, and only non-disclosive derivatives. | Eligible for output review only through the export gateway; proof-enriched bundles remain internal until that same gateway releases them. |
| Open | Material with no personal data or unacceptable residual disclosure risk. | Requires the strongest confidence in de-identification and release suitability. |

### Safe Outputs workflow

The export gateway is the sole egress route. Every export request produces an Output Release Pack containing:

- requested files and purpose statement
- transformation summary
- redaction counts by category
- line-change or diff metadata
- model and policy versions
- reviewer decisions and comments

Reviewer actions must support:

- approve release
- approve amended release
- reject release
- request changes before re-submission

## 9. Five Safes as Product Features

| Safe | Product implementation |
| --- | --- |
| Safe Data | Conservative redaction defaults, indirect-identifier heuristics, manifest and ledger separation, and personal-data treatment until effective anonymisation is established. |
| Safe Projects | Purpose-bound project workspaces, scoped browsing, and export requests tied to the declared research purpose. |
| Safe People | RBAC, training and agreement gates, role separation, and dual control for high-risk review paths. |
| Safe Settings | Secure-environment deployment, blocked external APIs, segmented services, and no uncontrolled download routes. |
| Safe Outputs | Output Release Packs, reviewer screening queue, signed approval trail, and provider-controlled final release decisions. |

## 10. Security and Governance Controls

### Required controls

- encryption at rest and in transit
- strong identity and least-privilege RBAC
- append-only or tamper-evident audit logging
- key management with separation of signing and encryption duties
- deny-by-default network posture and tight egress control
- vulnerability management, patching, penetration testing, and incident response drills

### Cryptographic lineage model

To prove derivation without leaking content:

1. Build a Merkle tree over the controlled master transcript at line or segment granularity.
2. Sign the Merkle root with an internal system key.
3. Include only the signed root and allowed proof material in safeguarded release packages.
4. Keep any keyed HMAC evidence strictly inside Controlled space.

This preserves auditability while avoiding reversible or guessable disclosure from exported hashes.

## 11. ML Governance and Evaluation

### Model selection criteria

- deployable on premises
- license-compatible with archive operations
- fine-tunable for handwriting and archival scans
- deterministic or tightly controlled inference settings
- usable without internet access
- assignable to an approved internal role such as transcription VLM, assist LLM, privacy NER, or discovery model

### Data strategy

- maintain a gold set with line polygons, diplomatic ground truth, and difficulty tags
- use active learning to sample low-confidence or high-disagreement cases
- retain previous model versions for reproducibility and rollback

### Evaluation dimensions

| Dimension | Why it matters |
| --- | --- |
| Accuracy | Transcription quality must improve over manual baselines in realistic archive material. |
| Calibration | Confidence should predict error so reviewer routing is meaningful. |
| Robustness | Performance must hold across scripts, eras, ink types, and scan quality. |
| Privacy impact | Transcription error must not quietly reduce redaction recall or disclosure safety. |

## 12. Delivery Roadmap Crosswalk

The implementation roadmap in this folder breaks the product into twelve practical delivery phases.

| Phase | Focus | File |
| --- | --- | --- |
| 00 | Foundation, secure environment, identity, audit, jobs, and no-egress baseline | [phase-00-foundation-release.md](./phase-00-foundation-release.md) |
| 01 | Controlled ingest, document library, and secure viewer UX | [phase-01-ingest-document-viewer-v1.md](./phase-01-ingest-document-viewer-v1.md) |
| 02 | Deterministic preprocessing and derived image assets | [phase-02-preprocessing-pipeline-v1.md](./phase-02-preprocessing-pipeline-v1.md) |
| 03 | Layout segmentation, region overlays, and reading-order structure | [phase-03-layout-segmentation-overlays-v1.md](./phase-03-layout-segmentation-overlays-v1.md) |
| 04 | Handwriting transcription, confidence scoring, and correction workflow foundations | [phase-04-handwriting-transcription-v1.md](./phase-04-handwriting-transcription-v1.md) |
| 05 | Privacy and redaction workflow, triage, review workspace, and safeguarded preview | [phase-05-privacy-redaction-workflow-v1.md](./phase-05-privacy-redaction-workflow-v1.md) |
| 06 | Redaction manifests, controlled evidence ledgers, and governance artefacts | [phase-06-redaction-manifest-ledger-v1.md](./phase-06-redaction-manifest-ledger-v1.md) |
| 07 | Policy engine, indirect-identifier handling, and pseudonymisation controls | [phase-07-policy-engine-v1.md](./phase-07-policy-engine-v1.md) |
| 08 | Safe Outputs workflow, export gateway, and release decisions | [phase-08-safe-outputs-export-gateway.md](./phase-08-safe-outputs-export-gateway.md) |
| 09 | Provenance proofs, signatures, and deposit-ready packaging without a second egress path | [phase-09-provenance-proof-bundles.md](./phase-09-provenance-proof-bundles.md) |
| 10 | Granular data products, controlled search, and safeguarded derivative indexes | [phase-10-granular-data-products.md](./phase-10-granular-data-products.md) |
| 11 | Hardening, scale, observability, security remediation, and production readiness | [phase-11-hardening-scale-pentest-readiness.md](./phase-11-hardening-scale-pentest-readiness.md) |

## 13. Product Decisions to Lock Early

1. Reading order is represented as a graph, not flattened text.
2. Confidence is exposed in the UI and drives routing, not hidden inside model internals.
3. Redaction behaviour is policy-driven and versioned, not hard-coded into pipelines.
4. The export gateway is the only path out of the environment.
5. Artefact versioning and manifests are immutable by default.

## 14. Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Transcription errors hide identifiers | Use conservative thresholds, multi-detector fusion, and mandatory review for low-confidence zones. |
| Indirect identifiers remain disclosive in combination | Support generalisation, combination-risk heuristics, and reviewer-enforced coarsening. |
| Provenance proof leaks sensitive information | Avoid plain hashes of short values; export only signed high-level proofs and keep keyed evidence internal. |
| Shadow exports through screenshots or copy and paste | Reinforce secure-environment controls, role separation, and output governance in both product and policy. |
| Automation outruns governance maturity | Treat manifests, audit events, reviewer checkpoints, and release controls as part of the definition of done for every phase. |

## 15. Proposal-Ready Positioning

UKDataExtraction (UKDE) can be described as:

- a tier-aware archival transcription platform aligned to controlled, safeguarded, and open release models
- a Five Safes implementation expressed through real product controls rather than policy statements alone
- a compliance-by-design workflow in which anonymisation, provenance, and release screening are enforced technically
- a secure, auditable environment for handwriting transcription and disclosure-managed derivative creation

## 16. What This Blueprint Means for the Phase Specs

Each numbered phase file should be read as an implementation contract for one slice of this blueprint. No phase may:

- introduce a bypass around controlled storage
- export artefacts outside the Safe Outputs workflow
- treat model output as unreviewable truth
- weaken provenance, auditability, or policy traceability

The product succeeds only if usability, privacy, and governance advance together.


