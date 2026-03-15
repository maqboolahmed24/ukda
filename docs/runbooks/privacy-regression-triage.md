# Privacy Regression Triage

Status: Prompt 66
Scope: Triage workflow for deterministic privacy regression failures before run activation or release promotion.

## Hard blockers

The following are hard blockers for privacy activation-readiness and release promotion checks:

- disclosure leaks in safeguarded preview text, PNG bytes, or run-level manifest bytes
- missing canonical fixture slices in the privacy regression pack
- missing token-linked or area-mask-backed disclosure coverage
- invalid dual-review override fixture coverage

There is no hidden suppression path in CI. If these checks are red, privacy is not activation-ready.

## Commands

Run canonical privacy regressions:

```bash
make test-privacy-regression
```

Failure artifacts are written to:

- `api/tests/.artifacts/privacy-regression/last-evaluation.json`

## Error codes

### PRIVACY_FIXTURE_METADATA_INCOMPLETE

Fixture ownership metadata is incomplete. Ensure `ownerTeam`, maintainers, and review cadence remain present in the canonical fixture pack.

### PRIVACY_FIXTURE_PUBLIC_DATA_DEPENDENCY

Fixture metadata no longer asserts synthetic-only data (`publicDataDependency=false`). Revert to synthetic fixture content only.

### PRIVACY_FIXTURE_SLICE_MISSING

One or more required fixture slices are missing: `direct_identifier`, `near_miss`, `unreadable_risk`, `overlapping_span`, `dual_review_override`.

### PRIVACY_DISCLOSURE_CASE_INVALID

A disclosure fixture case has invalid structure (missing identifiers, malformed preview fixture rows, or malformed manifest rows).

### PRIVACY_DISCLOSURE_PREVIEW_TEXT_LEAK

A raw original value leaked into safeguarded preview text. Validate masking spans and area-mask fallback behavior for the referenced `caseId` and `sliceId`.

### PRIVACY_DISCLOSURE_PREVIEW_PNG_LEAK

A raw original value leaked into rendered safeguarded preview PNG bytes. Validate preview text generation and PNG rendering source content for the referenced case.

### PRIVACY_DISCLOSURE_MANIFEST_LEAK

A raw original value leaked into run-level manifest bytes. Ensure the manifest contains only stable hashes, IDs, and approved lineage references.

### PRIVACY_DISCLOSURE_COVERAGE_GAP

Disclosure regression coverage is incomplete. Ensure at least one token-linked case and one area-mask-backed case are present and evaluated.

### PRIVACY_DUAL_REVIEW_FIXTURE_INVALID

Dual-review override fixture coverage is invalid. Ensure at least one `dual_review_override` case declares `metadata.dualReviewRequired=true`.

## Baseline and fixture updates

1. Update `api/tests/fixtures/privacy-direct-identifiers-gold-set/fixture-pack.v1.json` with synthetic-only cases.
2. Run `make test-privacy-regression`.
3. Review `api/tests/.artifacts/privacy-regression/last-evaluation.json`.
4. If visual browser states changed intentionally, update browser baselines with `pnpm test:browser:update --project=chromium --grep @privacy --workers=1`.
5. Re-run CI-equivalent checks before merge.
