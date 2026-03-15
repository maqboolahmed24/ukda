from __future__ import annotations

import concurrent.futures
import re
from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

from app.documents.models import RedactionDecisionStatus, RedactionFindingBasisPrimary

_DIRECT_IDENTIFIER_CATEGORY_ALIASES: dict[str, tuple[str, ...]] = {
    "PERSON_NAME": ("PERSON_NAME",),
    "ORGANIZATION": ("ORGANIZATION", "ORGANISATION"),
    "LOCATION": ("LOCATION", "ADDRESS", "PLACE"),
    "EMAIL": ("EMAIL",),
    "PHONE": ("PHONE",),
    "POSTCODE": ("POSTCODE", "ADDRESS"),
    "URL": ("URL",),
    "ID_NUMBER": ("ID_NUMBER", "GOVERNMENT_ID", "NATIONAL_ID"),
    "NATIONAL_ID": ("NATIONAL_ID", "GOVERNMENT_ID", "ID_NUMBER"),
    "NI_NUMBER": ("NI_NUMBER", "GOVERNMENT_ID", "ID_NUMBER"),
    "NHS_NUMBER": ("NHS_NUMBER", "GOVERNMENT_ID", "ID_NUMBER"),
}

_STRUCTURED_IDENTIFIER_CATEGORIES = {
    "EMAIL",
    "PHONE",
    "POSTCODE",
    "URL",
    "ID_NUMBER",
    "NATIONAL_ID",
    "NI_NUMBER",
    "NHS_NUMBER",
}

_DETECTOR_BASIS_RANK: dict[RedactionFindingBasisPrimary, int] = {
    "RULE": 3,
    "NER": 2,
    "HEURISTIC": 1,
}

_EMAIL_REGEX = re.compile(
    r"(?<![A-Za-z0-9._%+\-])"
    r"([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})"
    r"(?![A-Za-z0-9._%+\-])"
)
_URL_REGEX = re.compile(r"\b(?:https?://|www\.)[^\s<>()]+", re.IGNORECASE)
_PHONE_REGEX = re.compile(
    r"(?:\+44\s?\(?0?\d{2,4}\)?\s?\d{3,4}\s?\d{3,4})"
    r"|(?:\(?0\d{2,4}\)?\s?\d{3,4}\s?\d{3,4})"
)
_POSTCODE_REGEX = re.compile(
    r"\b(?:GIR\s?0AA|[A-PR-UWYZ][A-HK-Y]?\d[A-Z\d]?\s?\d[ABD-HJLNP-UW-Z]{2})\b",
    re.IGNORECASE,
)
_NI_NUMBER_REGEX = re.compile(
    r"\b(?:[A-CEGHJ-PR-TW-Z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D])\b",
    re.IGNORECASE,
)
_NHS_NUMBER_REGEX = re.compile(r"\b\d{3}\s?\d{3}\s?\d{4}\b")
_GENERIC_ID_REGEX = re.compile(
    r"\b(?:[A-Z]{1,4}[\- ]?\d{4,12}|\d{8,12})\b",
    re.IGNORECASE,
)

_NAME_TITLE_REGEX = re.compile(
    r"\b(?:Mr|Mrs|Ms|Miss|Dr|Prof|Professor|Sir|Lady)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b"
)
_ORG_SUFFIX_REGEX = re.compile(
    r"\b[A-Z][A-Za-z&'\-]+(?:\s+[A-Z][A-Za-z&'\-]+)*\s"
    r"(?:Ltd|Limited|PLC|LLP|University|Council|Trust|Agency|Office|Department|Committee)\b"
)

_DICTIONARY_PLACES = {
    "london",
    "birmingham",
    "manchester",
    "leeds",
    "liverpool",
    "bristol",
    "sheffield",
    "edinburgh",
    "glasgow",
    "cardiff",
    "belfast",
    "newcastle",
    "oxford",
    "cambridge",
}

_DICTIONARY_ORGANISATIONS = {
    "nhs",
    "hmrc",
    "cabinet office",
    "home office",
    "national archives",
    "british library",
}


@dataclass(frozen=True)
class RedactionDetectionToken:
    token_id: str
    token_index: int
    token_text: str
    line_id: str | None
    source_ref_id: str
    bbox_json: dict[str, object] | None = None
    polygon_json: dict[str, object] | None = None


@dataclass(frozen=True)
class RedactionDetectionLine:
    page_id: str
    page_index: int
    line_id: str
    text: str
    tokens: tuple[RedactionDetectionToken, ...] = ()


@dataclass(frozen=True)
class RedactionDetectionCandidate:
    page_id: str
    page_index: int
    line_id: str
    category: str
    span_start: int
    span_end: int
    confidence: float | None
    basis_primary: RedactionFindingBasisPrimary
    detector_id: str
    source: str


@dataclass(frozen=True)
class DirectIdentifierPolicyConfig:
    default_auto_apply_threshold: float = 0.92
    category_thresholds: dict[str, float] = field(default_factory=dict)
    direct_identifier_recall_floor: float = 0.99
    ner_timeout_seconds: float = 0.35
    assist_timeout_seconds: float = 0.2
    assist_enabled: bool = True

    def threshold_for_category(self, category: str) -> float:
        normalized = _normalize_category(category)
        for alias in _DIRECT_IDENTIFIER_CATEGORY_ALIASES.get(normalized, (normalized,)):
            if alias in self.category_thresholds:
                return self.category_thresholds[alias]
        return self.default_auto_apply_threshold


@dataclass(frozen=True)
class RedactionFusedFinding:
    page_id: str
    page_index: int
    line_id: str
    category: str
    span_start: int
    span_end: int
    confidence: float | None
    basis_primary: RedactionFindingBasisPrimary
    basis_secondary_json: dict[str, object] | None
    token_refs_json: list[dict[str, object]] | None
    bbox_refs: dict[str, object]
    decision_status: RedactionDecisionStatus
    decision_reason: str | None
    assist_summary: str | None


@dataclass(frozen=True)
class DirectIdentifierRecallExpected:
    category: str
    value: str


@dataclass(frozen=True)
class DirectIdentifierRecallCase:
    case_id: str
    text: str
    expected: tuple[DirectIdentifierRecallExpected, ...]


@dataclass(frozen=True)
class DirectIdentifierRecallEvaluation:
    total_expected: int
    matched_expected: int
    recall: float
    floor: float
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return self.recall >= self.floor

    def format_failure_summary(self) -> str:
        if self.passed:
            return "No direct-identifier recall-floor regressions detected."
        lines = [
            "Direct-identifier recall floor regression failures:",
            f"- Recall {self.recall:.4f} below floor {self.floor:.4f}.",
        ]
        lines.extend(f"- {item}" for item in self.failures)
        return "\n".join(lines)


def _normalize_category(value: str) -> str:
    return value.strip().upper().replace(" ", "_")


def _clamp_probability(value: float) -> float:
    return max(0.0, min(1.0, value))


def _coerce_probability(
    value: object,
    *,
    fallback: float,
) -> float:
    if isinstance(value, bool):
        return fallback
    if isinstance(value, (int, float)):
        return _clamp_probability(float(value))
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return fallback
        try:
            return _clamp_probability(float(candidate))
        except ValueError:
            return fallback
    return fallback


def _coerce_bool(value: object, *, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return fallback


def _read_mapping(value: object) -> Mapping[str, object] | None:
    return value if isinstance(value, Mapping) else None


def resolve_direct_identifier_policy_config(
    *,
    policy_snapshot_json: Mapping[str, object] | None,
    pinned_recall_floor: float,
    pinned_default_threshold: float = 0.92,
    pinned_ner_timeout_seconds: float = 0.35,
    pinned_assist_timeout_seconds: float = 0.2,
    pinned_assist_enabled: bool = True,
) -> DirectIdentifierPolicyConfig:
    snapshot = policy_snapshot_json if isinstance(policy_snapshot_json, Mapping) else {}
    defaults = _read_mapping(snapshot.get("defaults")) or {}
    quality_gates = _read_mapping(snapshot.get("qualityGates")) or {}

    default_threshold = _coerce_probability(
        defaults.get(
            "auto_apply_confidence_threshold",
            defaults.get("autoApplyConfidenceThreshold", pinned_default_threshold),
        ),
        fallback=pinned_default_threshold,
    )

    category_thresholds: dict[str, float] = {}
    raw_categories = snapshot.get("categories")
    if isinstance(raw_categories, Sequence) and not isinstance(raw_categories, (str, bytes)):
        for item in raw_categories:
            if not isinstance(item, Mapping):
                continue
            raw_id = item.get("id")
            if not isinstance(raw_id, str) or not raw_id.strip():
                continue
            normalized_id = _normalize_category(raw_id)
            threshold = _coerce_probability(
                item.get(
                    "review_required_below", item.get("reviewRequiredBelow", default_threshold)
                ),
                fallback=default_threshold,
            )
            category_thresholds[normalized_id] = threshold

    recall_floor = _coerce_probability(
        snapshot.get(
            "directIdentifierRecallFloor",
            snapshot.get(
                "direct_identifier_recall_floor",
                defaults.get(
                    "directIdentifierRecallFloor",
                    defaults.get(
                        "direct_identifier_recall_floor",
                        quality_gates.get(
                            "directIdentifierRecallFloor",
                            quality_gates.get(
                                "direct_identifier_recall_floor",
                                pinned_recall_floor,
                            ),
                        ),
                    ),
                ),
            ),
        ),
        fallback=pinned_recall_floor,
    )

    ner_timeout = _coerce_probability(
        snapshot.get(
            "nerTimeoutSeconds", defaults.get("nerTimeoutSeconds", pinned_ner_timeout_seconds)
        ),
        fallback=pinned_ner_timeout_seconds,
    )
    assist_timeout = _coerce_probability(
        snapshot.get(
            "assistTimeoutSeconds",
            defaults.get("assistTimeoutSeconds", pinned_assist_timeout_seconds),
        ),
        fallback=pinned_assist_timeout_seconds,
    )
    assist_enabled = _coerce_bool(
        snapshot.get("assistEnabled", defaults.get("assistEnabled", pinned_assist_enabled)),
        fallback=pinned_assist_enabled,
    )

    return DirectIdentifierPolicyConfig(
        default_auto_apply_threshold=default_threshold,
        category_thresholds=category_thresholds,
        direct_identifier_recall_floor=recall_floor,
        ner_timeout_seconds=max(0.05, ner_timeout),
        assist_timeout_seconds=max(0.05, assist_timeout),
        assist_enabled=assist_enabled,
    )


def _append_match_as_candidate(
    *,
    out: list[RedactionDetectionCandidate],
    seen: set[tuple[str, str, int, int, str]],
    line: RedactionDetectionLine,
    category: str,
    basis_primary: RedactionFindingBasisPrimary,
    detector_id: str,
    source: str,
    confidence: float,
    match_start: int,
    match_end: int,
) -> None:
    if match_start < 0 or match_end <= match_start or match_end > len(line.text):
        return
    normalized_category = _normalize_category(category)
    key = (line.line_id, normalized_category, match_start, match_end, detector_id)
    if key in seen:
        return
    seen.add(key)
    out.append(
        RedactionDetectionCandidate(
            page_id=line.page_id,
            page_index=line.page_index,
            line_id=line.line_id,
            category=normalized_category,
            span_start=match_start,
            span_end=match_end,
            confidence=_clamp_probability(confidence),
            basis_primary=basis_primary,
            detector_id=detector_id,
            source=source,
        )
    )


def detect_rule_candidates(
    lines: Sequence[RedactionDetectionLine],
) -> list[RedactionDetectionCandidate]:
    candidates: list[RedactionDetectionCandidate] = []
    seen: set[tuple[str, str, int, int, str]] = set()

    for line in lines:
        text = line.text
        for match in _EMAIL_REGEX.finditer(text):
            _append_match_as_candidate(
                out=candidates,
                seen=seen,
                line=line,
                category="EMAIL",
                basis_primary="RULE",
                detector_id="PRESIDIO_EMAIL",
                source="presidio.email",
                confidence=0.995,
                match_start=match.start(1),
                match_end=match.end(1),
            )

        for match in _URL_REGEX.finditer(text):
            _append_match_as_candidate(
                out=candidates,
                seen=seen,
                line=line,
                category="URL",
                basis_primary="RULE",
                detector_id="PRESIDIO_URL",
                source="presidio.url",
                confidence=0.965,
                match_start=match.start(),
                match_end=match.end(),
            )

        for match in _POSTCODE_REGEX.finditer(text):
            _append_match_as_candidate(
                out=candidates,
                seen=seen,
                line=line,
                category="POSTCODE",
                basis_primary="RULE",
                detector_id="PRESIDIO_POSTCODE",
                source="presidio.postcode",
                confidence=0.98,
                match_start=match.start(),
                match_end=match.end(),
            )

        for match in _PHONE_REGEX.finditer(text):
            raw = match.group(0)
            digits = "".join(ch for ch in raw if ch.isdigit())
            if len(digits) < 10:
                continue
            _append_match_as_candidate(
                out=candidates,
                seen=seen,
                line=line,
                category="PHONE",
                basis_primary="RULE",
                detector_id="PRESIDIO_PHONE",
                source="presidio.phone",
                confidence=0.972,
                match_start=match.start(),
                match_end=match.end(),
            )

        for match in _NI_NUMBER_REGEX.finditer(text):
            _append_match_as_candidate(
                out=candidates,
                seen=seen,
                line=line,
                category="NI_NUMBER",
                basis_primary="RULE",
                detector_id="PRESIDIO_NI",
                source="presidio.id_like.ni",
                confidence=0.992,
                match_start=match.start(),
                match_end=match.end(),
            )

        for match in _NHS_NUMBER_REGEX.finditer(text):
            _append_match_as_candidate(
                out=candidates,
                seen=seen,
                line=line,
                category="NHS_NUMBER",
                basis_primary="RULE",
                detector_id="PRESIDIO_NHS",
                source="presidio.id_like.nhs",
                confidence=0.992,
                match_start=match.start(),
                match_end=match.end(),
            )

        for match in _GENERIC_ID_REGEX.finditer(text):
            span_text = text[match.start() : match.end()]
            if _POSTCODE_REGEX.fullmatch(span_text) or _PHONE_REGEX.fullmatch(span_text):
                continue
            _append_match_as_candidate(
                out=candidates,
                seen=seen,
                line=line,
                category="ID_NUMBER",
                basis_primary="RULE",
                detector_id="PRESIDIO_ID_LIKE",
                source="presidio.id_like.generic",
                confidence=0.93,
                match_start=match.start(),
                match_end=match.end(),
            )

    return candidates


def detect_dictionary_candidates(
    lines: Sequence[RedactionDetectionLine],
) -> list[RedactionDetectionCandidate]:
    candidates: list[RedactionDetectionCandidate] = []
    seen: set[tuple[str, str, int, int, str]] = set()

    for line in lines:
        text = line.text
        lowered = text.lower()

        for match in _NAME_TITLE_REGEX.finditer(text):
            _append_match_as_candidate(
                out=candidates,
                seen=seen,
                line=line,
                category="PERSON_NAME",
                basis_primary="HEURISTIC",
                detector_id="DICT_NAME_TITLES",
                source="dictionary.name_titles",
                confidence=0.64,
                match_start=match.start(),
                match_end=match.end(),
            )

        for place in _DICTIONARY_PLACES:
            search_from = 0
            while True:
                index = lowered.find(place, search_from)
                if index < 0:
                    break
                end = index + len(place)
                if (index == 0 or not lowered[index - 1].isalnum()) and (
                    end >= len(lowered) or not lowered[end].isalnum()
                ):
                    _append_match_as_candidate(
                        out=candidates,
                        seen=seen,
                        line=line,
                        category="LOCATION",
                        basis_primary="HEURISTIC",
                        detector_id="DICT_PLACE_NAMES",
                        source="dictionary.place_names",
                        confidence=0.6,
                        match_start=index,
                        match_end=end,
                    )
                search_from = end

        for organisation in _DICTIONARY_ORGANISATIONS:
            search_from = 0
            while True:
                index = lowered.find(organisation, search_from)
                if index < 0:
                    break
                end = index + len(organisation)
                if (index == 0 or not lowered[index - 1].isalnum()) and (
                    end >= len(lowered) or not lowered[end].isalnum()
                ):
                    _append_match_as_candidate(
                        out=candidates,
                        seen=seen,
                        line=line,
                        category="ORGANIZATION",
                        basis_primary="HEURISTIC",
                        detector_id="DICT_ORGANISATIONS",
                        source="dictionary.organisations",
                        confidence=0.62,
                        match_start=index,
                        match_end=end,
                    )
                search_from = end

        for match in _ORG_SUFFIX_REGEX.finditer(text):
            _append_match_as_candidate(
                out=candidates,
                seen=seen,
                line=line,
                category="ORGANIZATION",
                basis_primary="HEURISTIC",
                detector_id="DICT_ORG_SUFFIX",
                source="dictionary.organisation_suffix",
                confidence=0.61,
                match_start=match.start(),
                match_end=match.end(),
            )

    return candidates


def _run_with_timeout[T](
    fn: Callable[[], T],
    *,
    timeout_seconds: float,
) -> T:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn)
        try:
            return future.result(timeout=max(0.01, timeout_seconds))
        except concurrent.futures.TimeoutError as error:
            future.cancel()
            raise TimeoutError from error


class LocalNERDetector:
    def __init__(
        self,
        *,
        predictor: Callable[[str], Sequence[Mapping[str, object] | tuple[object, ...]]]
        | None = None,
        timeout_seconds: float = 0.35,
    ) -> None:
        self._predictor = predictor
        self._timeout_seconds = max(0.01, timeout_seconds)
        self._gliner_model: object | None = None
        self._gliner_unavailable = False

    def _load_gliner_model(self) -> object | None:
        if self._gliner_unavailable:
            return None
        if self._gliner_model is not None:
            return self._gliner_model
        try:
            from gliner import GLiNER  # type: ignore[import-not-found]

            self._gliner_model = GLiNER.from_pretrained(
                "urchade/gliner_small-v2.1",
                local_files_only=True,
            )
        except Exception:
            self._gliner_unavailable = True
            return None
        return self._gliner_model

    def _predict_with_gliner(self, text: str) -> Sequence[Mapping[str, object]]:
        model = self._load_gliner_model()
        if model is None:
            return ()
        labels = ["person", "location", "organization"]
        try:
            raw = model.predict_entities(text, labels=labels, threshold=0.3)
        except Exception:
            return ()
        return [item for item in raw if isinstance(item, Mapping)]

    def _fallback_predict(self, text: str) -> Sequence[Mapping[str, object]]:
        outputs: list[Mapping[str, object]] = []
        for match in re.finditer(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b", text):
            outputs.append(
                {
                    "label": "person",
                    "start": match.start(),
                    "end": match.end(),
                    "score": 0.68,
                }
            )
        lowered = text.lower()
        for place in _DICTIONARY_PLACES:
            index = lowered.find(place)
            if index >= 0:
                outputs.append(
                    {
                        "label": "location",
                        "start": index,
                        "end": index + len(place),
                        "score": 0.7,
                    }
                )
        for match in _ORG_SUFFIX_REGEX.finditer(text):
            outputs.append(
                {
                    "label": "organization",
                    "start": match.start(),
                    "end": match.end(),
                    "score": 0.69,
                }
            )
        return outputs

    @staticmethod
    def _normalize_label(value: object) -> str | None:
        if isinstance(value, str):
            normalized = value.strip().lower()
        else:
            return None
        if normalized in {"person", "person_name", "name"}:
            return "PERSON_NAME"
        if normalized in {"location", "place", "geo"}:
            return "LOCATION"
        if normalized in {"organization", "organisation", "org"}:
            return "ORGANIZATION"
        return None

    @staticmethod
    def _parse_span(
        *,
        item: Mapping[str, object] | tuple[object, ...],
        text: str,
    ) -> tuple[str, int, int, float] | None:
        label: str | None = None
        start: int | None = None
        end: int | None = None
        score: float = 0.65

        if isinstance(item, Mapping):
            label = LocalNERDetector._normalize_label(item.get("label") or item.get("entity"))
            if isinstance(item.get("start"), int):
                start = int(item["start"])
            if isinstance(item.get("end"), int):
                end = int(item["end"])
            if start is None and isinstance(item.get("text"), str):
                needle = str(item["text"])
                index = text.find(needle)
                if index >= 0:
                    start = index
                    end = index + len(needle)
            if isinstance(item.get("score"), (int, float)):
                score = float(item["score"])
            elif isinstance(item.get("confidence"), (int, float)):
                score = float(item["confidence"])
        else:
            values = tuple(item)
            if len(values) >= 4:
                label = LocalNERDetector._normalize_label(values[0])
                start = int(values[1]) if isinstance(values[1], int) else None
                end = int(values[2]) if isinstance(values[2], int) else None
                if isinstance(values[3], (int, float)):
                    score = float(values[3])

        if label is None or start is None or end is None:
            return None
        if start < 0 or end <= start or end > len(text):
            return None
        return label, start, end, _clamp_probability(score)

    def detect(self, lines: Sequence[RedactionDetectionLine]) -> list[RedactionDetectionCandidate]:
        candidates: list[RedactionDetectionCandidate] = []
        seen: set[tuple[str, str, int, int, str]] = set()

        for line in lines:
            if not line.text:
                continue

            def predict() -> Sequence[Mapping[str, object] | tuple[object, ...]]:
                if self._predictor is not None:
                    return self._predictor(line.text)
                outputs = self._predict_with_gliner(line.text)
                if outputs:
                    return outputs
                return self._fallback_predict(line.text)

            try:
                raw_items = _run_with_timeout(
                    predict,
                    timeout_seconds=self._timeout_seconds,
                )
            except TimeoutError:
                continue
            except Exception:
                continue

            for item in raw_items:
                parsed = self._parse_span(item=item, text=line.text)
                if parsed is None:
                    continue
                category, span_start, span_end, confidence = parsed
                _append_match_as_candidate(
                    out=candidates,
                    seen=seen,
                    line=line,
                    category=category,
                    basis_primary="NER",
                    detector_id="GLINER",
                    source="gliner.local",
                    confidence=confidence,
                    match_start=span_start,
                    match_end=span_end,
                )

        return candidates


class BoundedAssistExplainer:
    def __init__(
        self,
        *,
        timeout_seconds: float = 0.2,
        explain_fn: Callable[[RedactionFusedFinding], str | None] | None = None,
    ) -> None:
        self._timeout_seconds = max(0.01, timeout_seconds)
        self._explain_fn = explain_fn

    def _default_explanation(self, finding: RedactionFusedFinding) -> str:
        reasons: list[str] = []
        basis = finding.basis_secondary_json or {}
        fusion = basis.get("fusion") if isinstance(basis.get("fusion"), Mapping) else {}
        if isinstance(fusion, Mapping):
            raw_reasons = fusion.get("reviewReasons")
            if isinstance(raw_reasons, Sequence) and not isinstance(raw_reasons, (str, bytes)):
                reasons = [str(item) for item in raw_reasons if isinstance(item, str)]
        if finding.confidence is not None:
            confidence_copy = f"confidence={finding.confidence:.3f}"
            reasons.append(confidence_copy)
        if not reasons:
            reasons = ["bounded_assist_review_route"]
        return "Routed to review because " + ", ".join(sorted(set(reasons))) + "."

    def explain(self, finding: RedactionFusedFinding) -> str | None:
        def run() -> str | None:
            if self._explain_fn is not None:
                return self._explain_fn(finding)
            return self._default_explanation(finding)

        try:
            output = _run_with_timeout(run, timeout_seconds=self._timeout_seconds)
        except TimeoutError:
            return None
        except Exception:
            return None
        if not isinstance(output, str):
            return None
        normalized = output.strip()
        return normalized if normalized else None


@dataclass(frozen=True)
class _TokenOffset:
    token: RedactionDetectionToken
    span_start: int
    span_end: int


@dataclass(frozen=True)
class _NormalizedCandidate:
    candidate: RedactionDetectionCandidate
    token_refs_json: list[dict[str, object]] | None
    bbox_refs: dict[str, object]


@dataclass
class _MergedBucket:
    page_id: str
    page_index: int
    line_id: str
    category: str
    span_start: int
    span_end: int
    confidence: float | None
    basis_primary: RedactionFindingBasisPrimary
    basis_secondary_json: dict[str, object]
    token_refs_json: list[dict[str, object]] | None
    bbox_refs: dict[str, object]
    review_reasons: set[str] = field(default_factory=set)


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def _build_token_offsets(
    *,
    line_text: str,
    tokens: Sequence[RedactionDetectionToken],
) -> tuple[_TokenOffset, ...]:
    ordered_tokens = sorted(tokens, key=lambda item: (item.token_index, item.token_id))
    offsets: list[_TokenOffset] = []
    consumed: list[tuple[int, int]] = []
    cursor = 0

    for token in ordered_tokens:
        needle = token.token_text.strip()
        if not needle:
            continue

        start = line_text.find(needle, cursor)
        if start < 0:
            start = line_text.find(needle)
            while start >= 0 and any(
                _overlaps(start, start + len(needle), used_start, used_end)
                for used_start, used_end in consumed
            ):
                start = line_text.find(needle, start + 1)
        if start < 0:
            continue

        end = start + len(needle)
        consumed.append((start, end))
        cursor = end
        offsets.append(_TokenOffset(token=token, span_start=start, span_end=end))

    return tuple(offsets)


def _build_token_refs_for_span(
    *,
    span_start: int,
    span_end: int,
    token_offsets: Sequence[_TokenOffset],
) -> tuple[list[dict[str, object]] | None, dict[str, object]]:
    refs: list[dict[str, object]] = []
    token_bboxes: list[dict[str, object]] = []

    for offset in token_offsets:
        if not _overlaps(span_start, span_end, offset.span_start, offset.span_end):
            continue
        ref: dict[str, object] = {
            "tokenId": offset.token.token_id,
            "tokenIndex": offset.token.token_index,
            "sourceRefId": offset.token.source_ref_id,
        }
        if offset.token.line_id is not None:
            ref["lineId"] = offset.token.line_id
        if isinstance(offset.token.bbox_json, Mapping):
            bbox = dict(offset.token.bbox_json)
            ref["bboxJson"] = bbox
            token_bboxes.append(bbox)
        if isinstance(offset.token.polygon_json, Mapping):
            ref["polygonJson"] = dict(offset.token.polygon_json)
        refs.append(ref)

    bbox_refs: dict[str, object] = {}
    if token_bboxes:
        bbox_refs["tokenBboxes"] = token_bboxes
    return (refs if refs else None), bbox_refs


def _normalize_candidates(
    *,
    lines: Sequence[RedactionDetectionLine],
    candidates: Sequence[RedactionDetectionCandidate],
) -> list[_NormalizedCandidate]:
    by_line = {line.line_id: line for line in lines}
    offsets_by_line = {
        line.line_id: _build_token_offsets(line_text=line.text, tokens=line.tokens)
        for line in lines
    }

    normalized: list[_NormalizedCandidate] = []
    for candidate in candidates:
        line = by_line.get(candidate.line_id)
        if line is None:
            continue
        if candidate.span_start < 0 or candidate.span_end <= candidate.span_start:
            continue
        if candidate.span_end > len(line.text):
            continue

        token_refs, bbox_refs = _build_token_refs_for_span(
            span_start=candidate.span_start,
            span_end=candidate.span_end,
            token_offsets=offsets_by_line.get(candidate.line_id, ()),
        )
        if not bbox_refs:
            bbox_refs = {"lineId": candidate.line_id}
        else:
            bbox_refs["lineId"] = candidate.line_id

        normalized.append(
            _NormalizedCandidate(
                candidate=candidate,
                token_refs_json=token_refs,
                bbox_refs=bbox_refs,
            )
        )

    return normalized


def _coerce_detector_confidence(value: float | None) -> float:
    return -1.0 if value is None else _clamp_probability(value)


def _choose_primary_candidate(
    *,
    category: str,
    members: Sequence[_NormalizedCandidate],
) -> _NormalizedCandidate:
    if category in _STRUCTURED_IDENTIFIER_CATEGORIES:
        rule_candidates = [item for item in members if item.candidate.basis_primary == "RULE"]
        if rule_candidates:
            return max(
                rule_candidates,
                key=lambda item: (
                    _coerce_detector_confidence(item.candidate.confidence),
                    item.candidate.span_end - item.candidate.span_start,
                    item.candidate.detector_id,
                ),
            )

    return max(
        members,
        key=lambda item: (
            _coerce_detector_confidence(item.candidate.confidence),
            _DETECTOR_BASIS_RANK[item.candidate.basis_primary],
            item.candidate.span_end - item.candidate.span_start,
            item.candidate.detector_id,
        ),
    )


def _merge_same_category_overlaps(
    *,
    items: Sequence[_NormalizedCandidate],
) -> list[_MergedBucket]:
    grouped: dict[tuple[str, str, str], list[_NormalizedCandidate]] = {}
    for item in items:
        key = (
            item.candidate.page_id,
            item.candidate.line_id,
            item.candidate.category,
        )
        grouped.setdefault(key, []).append(item)

    merged: list[_MergedBucket] = []

    for (_, _, category), members in grouped.items():
        ordered = sorted(
            members,
            key=lambda item: (
                item.candidate.span_start,
                item.candidate.span_end,
                item.candidate.detector_id,
            ),
        )

        clusters: list[list[_NormalizedCandidate]] = []
        for item in ordered:
            if not clusters:
                clusters.append([item])
                continue
            current = clusters[-1]
            current_end = max(member.candidate.span_end for member in current)
            if item.candidate.span_start <= current_end:
                current.append(item)
            else:
                clusters.append([item])

        for cluster in clusters:
            primary = _choose_primary_candidate(category=category, members=cluster)
            span_start = min(item.candidate.span_start for item in cluster)
            span_end = max(item.candidate.span_end for item in cluster)
            confidence = max(
                (_coerce_detector_confidence(item.candidate.confidence) for item in cluster),
                default=-1.0,
            )
            confidence_value = None if confidence < 0 else confidence

            unique_spans = {
                (item.candidate.span_start, item.candidate.span_end) for item in cluster
            }
            review_reasons: set[str] = set()
            if len(unique_spans) > 1:
                review_reasons.add("same_category_span_disagreement")

            has_rule = any(item.candidate.basis_primary == "RULE" for item in cluster)
            has_ner = any(item.candidate.basis_primary == "NER" for item in cluster)
            if has_rule and has_ner and len(unique_spans) > 1:
                review_reasons.add("rule_ner_disagreement")

            corroborating: list[dict[str, object]] = []
            for item in cluster:
                if item is primary:
                    continue
                corroborating.append(
                    {
                        "detectorId": item.candidate.detector_id,
                        "basis": item.candidate.basis_primary,
                        "confidence": item.candidate.confidence,
                        "spanStart": item.candidate.span_start,
                        "spanEnd": item.candidate.span_end,
                        "source": item.candidate.source,
                    }
                )

            token_refs: list[dict[str, object]] = []
            token_seen: set[str] = set()
            for item in cluster:
                if item.token_refs_json is None:
                    continue
                for ref in item.token_refs_json:
                    token_id = str(ref.get("tokenId") or "")
                    if not token_id or token_id in token_seen:
                        continue
                    token_seen.add(token_id)
                    token_refs.append(dict(ref))

            bbox_refs: dict[str, object] = {"lineId": primary.candidate.line_id}
            token_bboxes: list[dict[str, object]] = []
            for item in cluster:
                bbox_value = item.bbox_refs.get("tokenBboxes")
                if isinstance(bbox_value, Sequence) and not isinstance(bbox_value, (str, bytes)):
                    token_bboxes.extend(
                        dict(entry) for entry in bbox_value if isinstance(entry, Mapping)
                    )
            if token_bboxes:
                bbox_refs["tokenBboxes"] = token_bboxes

            basis_secondary_json: dict[str, object] = {
                "corroboratingDetectors": corroborating,
                "fusion": {
                    "clusterSize": len(cluster),
                    "reviewReasons": sorted(review_reasons),
                },
            }

            merged.append(
                _MergedBucket(
                    page_id=primary.candidate.page_id,
                    page_index=primary.candidate.page_index,
                    line_id=primary.candidate.line_id,
                    category=category,
                    span_start=span_start,
                    span_end=span_end,
                    confidence=confidence_value,
                    basis_primary=primary.candidate.basis_primary,
                    basis_secondary_json=basis_secondary_json,
                    token_refs_json=(token_refs if token_refs else None),
                    bbox_refs=bbox_refs,
                    review_reasons=review_reasons,
                )
            )

    return merged


def _apply_cross_category_conflict_flags(
    *,
    buckets: Sequence[_MergedBucket],
) -> None:
    per_line: dict[tuple[str, str], list[_MergedBucket]] = {}
    for bucket in buckets:
        per_line.setdefault((bucket.page_id, bucket.line_id), []).append(bucket)

    for members in per_line.values():
        ordered = sorted(members, key=lambda item: (item.span_start, item.span_end, item.category))
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                if right.span_start >= left.span_end:
                    break
                if not _overlaps(left.span_start, left.span_end, right.span_start, right.span_end):
                    continue
                if left.category == right.category:
                    continue
                left.review_reasons.add(f"cross_category_overlap:{right.category}")
                right.review_reasons.add(f"cross_category_overlap:{left.category}")


def fuse_detection_candidates(
    *,
    lines: Sequence[RedactionDetectionLine],
    candidates: Sequence[RedactionDetectionCandidate],
    policy_config: DirectIdentifierPolicyConfig,
    assist_explainer: BoundedAssistExplainer | None = None,
) -> list[RedactionFusedFinding]:
    normalized = _normalize_candidates(lines=lines, candidates=candidates)
    buckets = _merge_same_category_overlaps(items=normalized)
    _apply_cross_category_conflict_flags(buckets=buckets)

    fused: list[RedactionFusedFinding] = []
    for bucket in sorted(
        buckets,
        key=lambda item: (
            item.page_index,
            item.line_id,
            item.span_start,
            item.span_end,
            item.category,
        ),
    ):
        threshold = policy_config.threshold_for_category(bucket.category)
        needs_review = False
        if bucket.review_reasons:
            needs_review = True
        elif bucket.confidence is None:
            needs_review = True
        elif bucket.confidence < threshold:
            needs_review = True

        decision_status: RedactionDecisionStatus = (
            "NEEDS_REVIEW" if needs_review else "AUTO_APPLIED"
        )

        assist_summary: str | None = None
        if needs_review and assist_explainer is not None and policy_config.assist_enabled:
            finding_preview = RedactionFusedFinding(
                page_id=bucket.page_id,
                page_index=bucket.page_index,
                line_id=bucket.line_id,
                category=bucket.category,
                span_start=bucket.span_start,
                span_end=bucket.span_end,
                confidence=bucket.confidence,
                basis_primary=bucket.basis_primary,
                basis_secondary_json=dict(bucket.basis_secondary_json),
                token_refs_json=(list(bucket.token_refs_json) if bucket.token_refs_json else None),
                bbox_refs=dict(bucket.bbox_refs),
                decision_status=decision_status,
                decision_reason=None,
                assist_summary=None,
            )
            assist_summary = assist_explainer.explain(finding_preview)
            if assist_summary is not None:
                bucket.basis_secondary_json["assist"] = {
                    "summary": assist_summary,
                    "mode": "BOUNDED_REVIEW_EXPLANATION",
                }

        if bucket.review_reasons:
            bucket.basis_secondary_json.setdefault("fusion", {})
            fusion = bucket.basis_secondary_json.get("fusion")
            if isinstance(fusion, Mapping):
                bucket.basis_secondary_json["fusion"] = {
                    **dict(fusion),
                    "reviewReasons": sorted(bucket.review_reasons),
                }

        decision_reason = (
            "Auto-applied by direct-identifier threshold."
            if decision_status == "AUTO_APPLIED"
            else None
        )

        fused.append(
            RedactionFusedFinding(
                page_id=bucket.page_id,
                page_index=bucket.page_index,
                line_id=bucket.line_id,
                category=bucket.category,
                span_start=bucket.span_start,
                span_end=bucket.span_end,
                confidence=bucket.confidence,
                basis_primary=bucket.basis_primary,
                basis_secondary_json=(
                    dict(bucket.basis_secondary_json) if bucket.basis_secondary_json else None
                ),
                token_refs_json=(list(bucket.token_refs_json) if bucket.token_refs_json else None),
                bbox_refs=dict(bucket.bbox_refs),
                decision_status=decision_status,
                decision_reason=decision_reason,
                assist_summary=assist_summary,
            )
        )

    return fused


def detect_direct_identifier_findings(
    *,
    lines: Sequence[RedactionDetectionLine],
    policy_config: DirectIdentifierPolicyConfig,
    ner_detector: LocalNERDetector | None = None,
    assist_explainer: BoundedAssistExplainer | None = None,
) -> list[RedactionFusedFinding]:
    if not lines:
        return []
    detector = ner_detector or LocalNERDetector(timeout_seconds=policy_config.ner_timeout_seconds)

    candidates: list[RedactionDetectionCandidate] = []
    candidates.extend(detect_rule_candidates(lines))
    candidates.extend(detect_dictionary_candidates(lines))
    candidates.extend(detector.detect(lines))

    return fuse_detection_candidates(
        lines=lines,
        candidates=candidates,
        policy_config=policy_config,
        assist_explainer=assist_explainer,
    )


def evaluate_direct_identifier_recall(
    *,
    cases: Sequence[DirectIdentifierRecallCase],
    policy_config: DirectIdentifierPolicyConfig,
    ner_detector: LocalNERDetector | None = None,
) -> DirectIdentifierRecallEvaluation:
    total_expected = 0
    matched_expected = 0
    failures: list[str] = []

    detector = ner_detector or LocalNERDetector(timeout_seconds=policy_config.ner_timeout_seconds)

    for case in cases:
        lines = (
            RedactionDetectionLine(
                page_id="eval-page",
                page_index=0,
                line_id=f"line-{case.case_id}",
                text=case.text,
                tokens=(),
            ),
        )
        findings = detect_direct_identifier_findings(
            lines=lines,
            policy_config=policy_config,
            ner_detector=detector,
            assist_explainer=None,
        )
        for expected in case.expected:
            total_expected += 1
            expected_category = _normalize_category(expected.category)
            expected_value = expected.value
            matched = False
            for finding in findings:
                if _normalize_category(finding.category) != expected_category:
                    continue
                if finding.span_start < 0 or finding.span_end > len(case.text):
                    continue
                candidate_value = case.text[finding.span_start : finding.span_end]
                if candidate_value == expected_value:
                    matched = True
                    break
            if matched:
                matched_expected += 1
            else:
                failures.append(
                    f"{case.case_id}: expected {expected_category}='{expected_value}' not detected"
                )

    recall = 1.0 if total_expected == 0 else matched_expected / float(total_expected)
    return DirectIdentifierRecallEvaluation(
        total_expected=total_expected,
        matched_expected=matched_expected,
        recall=recall,
        floor=policy_config.direct_identifier_recall_floor,
        failures=tuple(failures),
    )


__all__ = [
    "BoundedAssistExplainer",
    "DirectIdentifierPolicyConfig",
    "DirectIdentifierRecallCase",
    "DirectIdentifierRecallEvaluation",
    "DirectIdentifierRecallExpected",
    "LocalNERDetector",
    "RedactionDetectionCandidate",
    "RedactionDetectionLine",
    "RedactionDetectionToken",
    "RedactionFusedFinding",
    "detect_dictionary_candidates",
    "detect_direct_identifier_findings",
    "detect_rule_candidates",
    "evaluate_direct_identifier_recall",
    "fuse_detection_candidates",
    "resolve_direct_identifier_policy_config",
]
