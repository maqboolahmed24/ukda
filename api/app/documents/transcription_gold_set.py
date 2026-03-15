from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping, Sequence

TranscriptionGoldSetSourceKind = Literal["LINE", "RESCUE_CANDIDATE", "PAGE_WINDOW"]


@dataclass(frozen=True)
class TranscriptionGoldSetCase:
    case_id: str
    run_id: str
    page_id: str
    line_id: str | None
    transcript_version_id: str | None
    source_kind: TranscriptionGoldSetSourceKind
    fallback_invoked: bool
    reference_text: str
    hypothesis_text: str


@dataclass(frozen=True)
class TranscriptionGoldSetFixturePack:
    fixture_pack_id: str
    fixture_pack_version: str
    schema_version: int
    cases: tuple[TranscriptionGoldSetCase, ...]


@dataclass(frozen=True)
class TranscriptionGoldSetSliceExpectation:
    slice_name: str
    case_count: int
    expected_cer: float
    expected_wer: float
    tolerance: float


@dataclass(frozen=True)
class TranscriptionGoldSetBaselineManifest:
    schema_version: int
    fixture_pack_id: str
    fixture_pack_version: str
    baseline_version: str
    generated_at: str
    generated_by: str
    expectations: tuple[TranscriptionGoldSetSliceExpectation, ...]


@dataclass(frozen=True)
class TranscriptionGoldSetCaseResult:
    case_id: str
    run_id: str
    page_id: str
    line_id: str | None
    transcript_version_id: str | None
    source_kind: TranscriptionGoldSetSourceKind
    fallback_invoked: bool
    reference_char_count: int
    reference_word_count: int
    char_distance: int
    word_distance: int
    cer: float
    wer: float


@dataclass(frozen=True)
class TranscriptionGoldSetSliceResult:
    slice_name: str
    case_count: int
    reference_char_count: int
    reference_word_count: int
    char_distance: int
    word_distance: int
    cer: float
    wer: float
    run_ids: tuple[str, ...]
    page_ids: tuple[str, ...]
    line_ids: tuple[str, ...]
    transcript_version_ids: tuple[str, ...]


@dataclass(frozen=True)
class TranscriptionGoldSetEvaluation:
    fixture_pack_id: str
    fixture_pack_version: str
    baseline_version: str
    generated_at: str
    case_results: tuple[TranscriptionGoldSetCaseResult, ...]
    slice_results: tuple[TranscriptionGoldSetSliceResult, ...]
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return len(self.failures) == 0

    def format_failure_summary(self) -> str:
        if self.passed:
            return "No transcription CER/WER gold-set regressions detected."
        lines = ["Transcription CER/WER gold-set regression failures:"]
        lines.extend(f"- {failure}" for failure in self.failures)
        return "\n".join(lines)


def _as_float(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric.")
    return float(value)


def _as_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")
    return int(value)


def _normalize_source_kind(value: str) -> TranscriptionGoldSetSourceKind:
    normalized = value.strip().upper()
    if normalized in {"LINE", "RESCUE_CANDIDATE", "PAGE_WINDOW"}:
        return normalized
    raise ValueError(
        "sourceKind must be LINE, RESCUE_CANDIDATE, or PAGE_WINDOW."
    )


def _parse_case(value: object) -> TranscriptionGoldSetCase:
    if not isinstance(value, Mapping):
        raise ValueError("Fixture case entry must be an object.")
    case_id = str(value.get("caseId", "")).strip()
    if not case_id:
        raise ValueError("Fixture case entry requires caseId.")
    run_id = str(value.get("runId", "")).strip()
    page_id = str(value.get("pageId", "")).strip()
    if not run_id or not page_id:
        raise ValueError(f"{case_id}: runId and pageId are required.")
    line_id_raw = value.get("lineId")
    line_id = str(line_id_raw).strip() if isinstance(line_id_raw, str) and line_id_raw.strip() else None
    transcript_version_raw = value.get("transcriptVersionId")
    transcript_version_id = (
        str(transcript_version_raw).strip()
        if isinstance(transcript_version_raw, str) and transcript_version_raw.strip()
        else None
    )
    source_kind = _normalize_source_kind(str(value.get("sourceKind", "LINE")))
    fallback_invoked = bool(value.get("fallbackInvoked", False))
    reference_text = str(value.get("referenceText", ""))
    hypothesis_text = str(value.get("hypothesisText", ""))
    return TranscriptionGoldSetCase(
        case_id=case_id,
        run_id=run_id,
        page_id=page_id,
        line_id=line_id,
        transcript_version_id=transcript_version_id,
        source_kind=source_kind,
        fallback_invoked=fallback_invoked,
        reference_text=reference_text,
        hypothesis_text=hypothesis_text,
    )


def load_transcription_gold_set_fixture_pack(path: Path) -> TranscriptionGoldSetFixturePack:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("Transcription gold-set fixture pack must be a JSON object.")
    fixture_pack_id = str(raw.get("fixturePackId", "")).strip()
    fixture_pack_version = str(raw.get("fixturePackVersion", "")).strip()
    if not fixture_pack_id or not fixture_pack_version:
        raise ValueError("Fixture pack requires fixturePackId and fixturePackVersion.")
    cases_raw = raw.get("cases")
    if not isinstance(cases_raw, list) or len(cases_raw) == 0:
        raise ValueError("Fixture pack requires a non-empty cases array.")
    return TranscriptionGoldSetFixturePack(
        fixture_pack_id=fixture_pack_id,
        fixture_pack_version=fixture_pack_version,
        schema_version=_as_int(raw.get("schemaVersion", 1), field_name="schemaVersion"),
        cases=tuple(_parse_case(item) for item in cases_raw),
    )


def _parse_expectation(value: object) -> TranscriptionGoldSetSliceExpectation:
    if not isinstance(value, Mapping):
        raise ValueError("Baseline expectation entry must be an object.")
    slice_name = str(value.get("sliceName", "")).strip()
    if not slice_name:
        raise ValueError("Baseline expectation requires sliceName.")
    return TranscriptionGoldSetSliceExpectation(
        slice_name=slice_name,
        case_count=_as_int(value.get("caseCount", 0), field_name=f"{slice_name}.caseCount"),
        expected_cer=_as_float(value.get("expectedCer", 0.0), field_name=f"{slice_name}.expectedCer"),
        expected_wer=_as_float(value.get("expectedWer", 0.0), field_name=f"{slice_name}.expectedWer"),
        tolerance=_as_float(value.get("tolerance", 1e-9), field_name=f"{slice_name}.tolerance"),
    )


def load_transcription_gold_set_baseline_manifest(
    path: Path,
) -> TranscriptionGoldSetBaselineManifest:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("Transcription gold-set baseline manifest must be a JSON object.")
    fixture_pack_id = str(raw.get("fixturePackId", "")).strip()
    fixture_pack_version = str(raw.get("fixturePackVersion", "")).strip()
    baseline_version = str(raw.get("baselineVersion", "")).strip()
    generated_at = str(raw.get("generatedAt", "")).strip()
    generated_by = str(raw.get("generatedBy", "")).strip()
    if not fixture_pack_id or not fixture_pack_version or not baseline_version:
        raise ValueError(
            "Baseline manifest requires fixturePackId, fixturePackVersion, and baselineVersion."
        )
    expectations_raw = raw.get("expectations")
    if not isinstance(expectations_raw, list) or len(expectations_raw) == 0:
        raise ValueError("Baseline manifest requires non-empty expectations.")
    return TranscriptionGoldSetBaselineManifest(
        schema_version=_as_int(raw.get("schemaVersion", 1), field_name="schemaVersion"),
        fixture_pack_id=fixture_pack_id,
        fixture_pack_version=fixture_pack_version,
        baseline_version=baseline_version,
        generated_at=generated_at,
        generated_by=generated_by,
        expectations=tuple(_parse_expectation(item) for item in expectations_raw),
    )


def _levenshtein_distance(left: Sequence[str], right: Sequence[str]) -> int:
    if left == right:
        return 0
    if len(left) == 0:
        return len(right)
    if len(right) == 0:
        return len(left)
    previous = list(range(len(right) + 1))
    for left_index, left_item in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_item in enumerate(right, start=1):
            substitution_cost = 0 if left_item == right_item else 1
            current.append(
                min(
                    previous[right_index] + 1,
                    current[right_index - 1] + 1,
                    previous[right_index - 1] + substitution_cost,
                )
            )
        previous = current
    return previous[-1]


def _character_tokens(value: str) -> tuple[str, ...]:
    return tuple(value)


def _word_tokens(value: str) -> tuple[str, ...]:
    return tuple(part for part in value.strip().split() if part)


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / float(denominator)


def _compute_case_result(case: TranscriptionGoldSetCase) -> TranscriptionGoldSetCaseResult:
    reference_chars = _character_tokens(case.reference_text)
    hypothesis_chars = _character_tokens(case.hypothesis_text)
    reference_words = _word_tokens(case.reference_text)
    hypothesis_words = _word_tokens(case.hypothesis_text)
    char_distance = _levenshtein_distance(reference_chars, hypothesis_chars)
    word_distance = _levenshtein_distance(reference_words, hypothesis_words)
    reference_char_count = len(reference_chars)
    reference_word_count = len(reference_words)
    return TranscriptionGoldSetCaseResult(
        case_id=case.case_id,
        run_id=case.run_id,
        page_id=case.page_id,
        line_id=case.line_id,
        transcript_version_id=case.transcript_version_id,
        source_kind=case.source_kind,
        fallback_invoked=case.fallback_invoked,
        reference_char_count=reference_char_count,
        reference_word_count=reference_word_count,
        char_distance=char_distance,
        word_distance=word_distance,
        cer=_safe_rate(char_distance, reference_char_count),
        wer=_safe_rate(word_distance, reference_word_count),
    )


def _build_slice_result(
    *,
    slice_name: str,
    case_results: Sequence[TranscriptionGoldSetCaseResult],
) -> TranscriptionGoldSetSliceResult:
    sorted_cases = sorted(case_results, key=lambda item: item.case_id)
    char_distance = sum(item.char_distance for item in sorted_cases)
    word_distance = sum(item.word_distance for item in sorted_cases)
    reference_char_count = sum(item.reference_char_count for item in sorted_cases)
    reference_word_count = sum(item.reference_word_count for item in sorted_cases)
    return TranscriptionGoldSetSliceResult(
        slice_name=slice_name,
        case_count=len(sorted_cases),
        reference_char_count=reference_char_count,
        reference_word_count=reference_word_count,
        char_distance=char_distance,
        word_distance=word_distance,
        cer=_safe_rate(char_distance, reference_char_count),
        wer=_safe_rate(word_distance, reference_word_count),
        run_ids=tuple(sorted({item.run_id for item in sorted_cases})),
        page_ids=tuple(sorted({item.page_id for item in sorted_cases})),
        line_ids=tuple(
            sorted(
                {
                    item.line_id
                    for item in sorted_cases
                    if isinstance(item.line_id, str) and item.line_id
                }
            )
        ),
        transcript_version_ids=tuple(
            sorted(
                {
                    item.transcript_version_id
                    for item in sorted_cases
                    if isinstance(item.transcript_version_id, str)
                    and item.transcript_version_id
                }
            )
        ),
    )


def evaluate_transcription_gold_set(
    *,
    fixture_pack_path: Path,
    baseline_manifest_path: Path,
) -> TranscriptionGoldSetEvaluation:
    fixture_pack = load_transcription_gold_set_fixture_pack(fixture_pack_path)
    baseline = load_transcription_gold_set_baseline_manifest(baseline_manifest_path)
    if fixture_pack.fixture_pack_id != baseline.fixture_pack_id:
        raise ValueError("Fixture pack id does not match baseline manifest.")
    if fixture_pack.fixture_pack_version != baseline.fixture_pack_version:
        raise ValueError("Fixture pack version does not match baseline manifest.")

    case_results = tuple(
        sorted(
            (_compute_case_result(case) for case in fixture_pack.cases),
            key=lambda item: item.case_id,
        )
    )
    by_slice_name: dict[str, TranscriptionGoldSetSliceResult] = {
        "overall": _build_slice_result(
            slice_name="overall",
            case_results=case_results,
        ),
        "ordinary_line": _build_slice_result(
            slice_name="ordinary_line",
            case_results=[
                item for item in case_results if item.source_kind == "LINE"
            ],
        ),
        "rescue_source": _build_slice_result(
            slice_name="rescue_source",
            case_results=[
                item for item in case_results if item.source_kind != "LINE"
            ],
        ),
        "fallback_invoked": _build_slice_result(
            slice_name="fallback_invoked",
            case_results=[
                item for item in case_results if item.fallback_invoked
            ],
        ),
    }
    slice_results = tuple(by_slice_name[name] for name in sorted(by_slice_name))

    failures: list[str] = []
    for expectation in baseline.expectations:
        actual = by_slice_name.get(expectation.slice_name)
        if actual is None:
            failures.append(
                f"slice {expectation.slice_name}: missing from computed evaluation."
            )
            continue
        if actual.case_count != expectation.case_count:
            failures.append(
                f"slice {expectation.slice_name}: expected caseCount={expectation.case_count} "
                f"but observed {actual.case_count}."
            )
        if abs(actual.cer - expectation.expected_cer) > expectation.tolerance:
            failures.append(
                f"slice {expectation.slice_name}: CER drift {actual.cer:.12f} "
                f"(expected {expectation.expected_cer:.12f} ± {expectation.tolerance:.3e})."
            )
        if abs(actual.wer - expectation.expected_wer) > expectation.tolerance:
            failures.append(
                f"slice {expectation.slice_name}: WER drift {actual.wer:.12f} "
                f"(expected {expectation.expected_wer:.12f} ± {expectation.tolerance:.3e})."
            )

    return TranscriptionGoldSetEvaluation(
        fixture_pack_id=fixture_pack.fixture_pack_id,
        fixture_pack_version=fixture_pack.fixture_pack_version,
        baseline_version=baseline.baseline_version,
        generated_at=baseline.generated_at,
        case_results=case_results,
        slice_results=slice_results,
        failures=tuple(failures),
    )


def write_transcription_gold_set_artifact(
    *,
    evaluation: TranscriptionGoldSetEvaluation,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fixturePackId": evaluation.fixture_pack_id,
        "fixturePackVersion": evaluation.fixture_pack_version,
        "baselineVersion": evaluation.baseline_version,
        "generatedAt": evaluation.generated_at,
        "passed": evaluation.passed,
        "failures": list(evaluation.failures),
        "slices": [
            {
                "sliceName": item.slice_name,
                "caseCount": item.case_count,
                "referenceCharCount": item.reference_char_count,
                "referenceWordCount": item.reference_word_count,
                "charDistance": item.char_distance,
                "wordDistance": item.word_distance,
                "cer": item.cer,
                "wer": item.wer,
                "runIds": list(item.run_ids),
                "pageIds": list(item.page_ids),
                "lineIds": list(item.line_ids),
                "transcriptVersionIds": list(item.transcript_version_ids),
            }
            for item in evaluation.slice_results
        ],
        "cases": [
            {
                "caseId": item.case_id,
                "runId": item.run_id,
                "pageId": item.page_id,
                "lineId": item.line_id,
                "transcriptVersionId": item.transcript_version_id,
                "sourceKind": item.source_kind,
                "fallbackInvoked": item.fallback_invoked,
                "referenceCharCount": item.reference_char_count,
                "referenceWordCount": item.reference_word_count,
                "charDistance": item.char_distance,
                "wordDistance": item.word_distance,
                "cer": item.cer,
                "wer": item.wer,
            }
            for item in evaluation.case_results
        ],
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
