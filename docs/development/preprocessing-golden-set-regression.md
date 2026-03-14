# Preprocessing Golden Set Regression

> Status: Active (Prompt 38)
> Scope: Canonical preprocessing determinism harness, baseline approval workflow, and CI drift evidence

## Canonical Assets

- Fixture pack: `api/tests/fixtures/preprocessing-gold-set/fixture-pack.v1.json`
- Baseline manifest: `api/tests/fixtures/preprocessing-gold-set/baseline-manifest.v1.json`
- Harness implementation: `api/app/documents/preprocessing_gold_set.py`
- Gate tests: `api/tests/test_preprocessing_gold_set.py`
- Baseline update script: `scripts/update_preprocessing_gold_set_baseline.py`
- Failure artifact output: `api/tests/.artifacts/preprocessing-gold-set/last-evaluation.json`

These files are the single canonical preprocessing gold-set system. Do not create a second fixture pack or second baseline manifest for the same Phase 2 preprocessing tranche.

## Fixture-Pack Ownership

The fixture pack contains deterministic synthetic pages representing real failure patterns:

- low DPI and unknown DPI
- skew and high skew
- blur-heavy input
- low contrast and faded ink
- binarization-helpful and binarization-harmful cases
- bleed-through paired/unpaired cases

Each fixture must keep:

- stable `fixtureId`
- explicit scenario and seed
- fixed dimensions and source DPI declaration
- concise notes/tags that explain why the case exists

When adding fixtures, keep the pack small and CI-friendly. Prefer additive changes over replacing existing IDs.

## Baseline Manifest Contract

Each baseline record binds:

- fixture identity (`fixtureId`, optional `pairedFixtureId`)
- profile identity and revision (`profileId`, `profileVersion`, `profileRevision`)
- expanded canonical params (`paramsJson`) and `paramsHash`
- `pipelineVersion` and `containerDigest`
- expected output hashes (`expectedGraySha256`, optional `expectedBinSha256`)
- comparison mode (`HASH` or `SSIM`)
- quality-floor assertions:
  - expected quality gate status
  - required and forbidden warnings
  - metric floors/ceilings
  - binary-output requirement where applicable

`HASH` is the default comparison mode. `SSIM` is supported only for explicitly approved non-canonical exceptions and requires a recorded threshold plus reference payload in the manifest.

## Determinism Rules Enforced

The gate fails when any of the following drift without approved baseline update:

- canonical expanded params differ or `paramsHash` no longer matches
- pipeline version binding changes unexpectedly
- output hashes drift from manifest values
- required warnings disappear or forbidden warnings appear
- metric floors/ceilings regress
- output key pattern escapes the canonical preprocess-derived prefix

Unapproved drift is surfaced with record-level failure messages that include fixture/profile identifiers.

## Running the Gate

Run only preprocessing gold-set gate:

```bash
make test-preprocess-gold
```

Run full Python CI gate (includes preprocessing gold-set first):

```bash
make ci-python
```

## Baseline Update Workflow (Approved Changes Only)

When preprocessing behavior changes intentionally:

1. Confirm change intent and impact with reviewer.
2. Regenerate baseline with explicit approval metadata:

```bash
source .venv/bin/activate
python scripts/update_preprocessing_gold_set_baseline.py \
  --approved-by "Name/Team" \
  --approval-reference "ticket-or-pr" \
  --approval-summary "why baseline changed"
```

3. Re-run `make test-preprocess-gold`.
4. Include rationale in PR and review manifest diff carefully.

Never refresh baselines to silence unexplained drift.

## CI Failure Artifacts

- Python CI uploads `api/tests/.artifacts/preprocessing-gold-set` on failure.
- The JSON artifact includes:
  - per-record hashes and metrics
  - warnings and quality status
  - exact failure reasons

This artifact is the canonical drift triage input for reviewers.

## Adding New Profiles or Compare Variants

Whenever preprocessing profile behavior expands:

1. Add or update fixture cases in `fixture-pack.v1.json`.
2. Add corresponding records in `baseline-manifest.v1.json` with explicit quality floors.
3. Regenerate baseline with approval metadata.
4. Extend browser regression coverage for impacted preprocessing routes/states.
