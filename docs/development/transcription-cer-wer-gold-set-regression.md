# Transcription CER/WER Gold Set Regression

Status: Added in Prompt 58  
Scope: Deterministic internal CER/WER harness with rescue and fallback slices

## Canonical assets

- Harness implementation: `api/app/documents/transcription_gold_set.py`
- Fixture pack: `api/tests/fixtures/transcription-gold-set/fixture-pack.v1.json`
- Baseline manifest: `api/tests/fixtures/transcription-gold-set/baseline-manifest.v1.json`
- Gate tests: `api/tests/test_transcription_gold_set.py`
- Failure artifact output: `api/tests/.artifacts/transcription-gold-set/last-evaluation.json`

Do not create a second transcription CER/WER harness for the same phase scope.

## Slice model

The harness reports CER and WER for:

- `overall`
- `ordinary_line` (`sourceKind = LINE`)
- `rescue_source` (`sourceKind = RESCUE_CANDIDATE | PAGE_WINDOW`)
- `fallback_invoked` (`fallbackInvoked = true`)

Each slice reports:

- case count
- total reference char/word counts
- total char/word edit distances
- CER and WER
- run/page/line/version identifiers present in the slice

## Determinism contract

- Inputs are local fixture + baseline files only.
- Evaluation output ordering is stable (case IDs and slice names sorted).
- Artifact JSON is written with canonical key order and UTF-8 newline termination.
- Baseline drift checks use strict tolerance from manifest expectations.

No public benchmark upload path or external evaluation service is used.

## Running the gate

Run only the transcription CER/WER gate:

```bash
./.venv/bin/pytest -q api/tests/test_transcription_gold_set.py
```

Run transcription route/service coverage used by activation and rescue readiness:

```bash
./.venv/bin/pytest -q api/tests/test_documents_routes.py
```

## Baseline update expectations

If model behavior intentionally changes:

1. Update fixture cases or expected slice values deliberately.
2. Keep rescue-vs-ordinary and fallback slices separate.
3. Document the reason in PR notes with impacted slice names.

Do not refresh expected CER/WER values to hide unexplained regressions.
