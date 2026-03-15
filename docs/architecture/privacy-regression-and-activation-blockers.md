# Privacy Regression And Activation Blockers

Status: Prompt 66
Scope: Canonical privacy regression pack, disclosure leak gates, reviewer-safety browser checks, and activation-blocking policy.

## Canonical regression pack

Canonical fixture pack:

- `api/tests/fixtures/privacy-direct-identifiers-gold-set/fixture-pack.v1.json`

Required slices:

- `direct_identifier`
- `near_miss`
- `unreadable_risk`
- `overlapping_span`
- `dual_review_override`

The pack is synthetic-only and owned under declared fixture metadata. No public data dependencies are allowed.

## Hard-blocking gates

The following gates are hard blockers for privacy activation-ready claims in CI and local release checks:

1. Direct-identifier recall gate (`api/tests/test_redaction_detection.py`).
2. Disclosure leak gate for safeguarded preview text/PNG/manifest (`api/tests/test_privacy_regression_pack.py`).
3. Deterministic masking and overlap resolution (`api/tests/test_redaction_preview.py`).
4. Decision/review/lock lifecycle invariants (`api/tests/test_documents_redaction_routes.py`).
5. Browser reviewer-safety regression (`web/tests/browser/privacy-workspace-regression.spec.ts`).

If these gates are red, privacy output is not activation-safe and must not be represented as production-ready.

## Reviewer-safety expectations in browser checks

The browser suite covers:

- privacy workspace default, selected-finding, override modal, and controlled/safeguarded states
- deterministic next-unresolved navigation and deep-link stability
- run-review page gating states (start-review and complete-review blockers)
- compare route state rendering with decision/review/preview deltas
- approved/locked state conflict surfaces
- keyboard-only flow, focus visibility, no keyboard traps, and bounded reflow behavior

## CI and artifacts

Primary command:

```bash
make test-privacy-regression
```

Artifacts:

- `api/tests/.artifacts/privacy-regression/last-evaluation.json`
- Playwright `playwright-report` and `test-results` for browser privacy failures

The privacy regression artifact includes stable error codes and runbook links in:

- `docs/runbooks/privacy-regression-triage.md`

## Baseline and fixture updates

1. Update fixture pack content and metadata.
2. Run `make test-privacy-regression`.
3. Inspect `api/tests/.artifacts/privacy-regression/last-evaluation.json`.
4. If privacy browser visuals changed intentionally, run:
   - `pnpm test:browser:update --project=chromium --grep @privacy --workers=1`
5. Re-run gate commands before merge.

## Cross-phase prerequisite

Later governance, manifest, and export prompts treat these privacy gates as prerequisites. Phase 6+ work must not bypass or suppress privacy regression failures.
