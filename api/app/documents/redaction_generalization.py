from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Mapping, Sequence

from app.documents.models import RedactionDecisionStatus, RedactionFindingBasisPrimary
from app.documents.redaction_detection import RedactionDetectionLine, RedactionDetectionToken

DateSpecificity = Literal["MONTH_YEAR", "YEAR"]
PlaceSpecificity = Literal["COUNTY", "REGION"]
AgeSpecificity = Literal["FIVE_YEAR_BAND", "TEN_YEAR_BAND"]

_SUPPORTED_ACTIONS: set[str] = {"MASK", "PSEUDONYMIZE", "GENERALIZE", "ESCALATE", "ALLOW", "REVIEW"}
_GENERALIZE_ACTION = "GENERALIZE"

_MONTH_NAME_BY_NUMBER: dict[int, str] = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}

_EXACT_DATE_NUMERIC_REGEX = re.compile(
    r"\b(?P<day>\d{1,2})[/-](?P<month>\d{1,2})[/-](?P<year>\d{4})\b"
)
_EXACT_DATE_ISO_REGEX = re.compile(
    r"\b(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})\b"
)
_EXACT_DATE_DAY_MONTH_NAME_REGEX = re.compile(
    r"\b(?P<day>\d{1,2})(?:st|nd|rd|th)?\s+"
    r"(?P<month_name>January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(?P<year>\d{4})\b",
    re.IGNORECASE,
)
_EXACT_DATE_MONTH_NAME_DAY_REGEX = re.compile(
    r"\b(?P<month_name>January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?(?:,)?\s+(?P<year>\d{4})\b",
    re.IGNORECASE,
)

_RARE_OCCUPATION_REGEX = re.compile(
    r"\b("
    r"chimney\s+sweep|blacksmith|cooper|farrier|wheelwright|thatcher|"
    r"lace\s+maker|rag\s+picker|whaler|midwife|undertaker|miller|"
    r"boatman|saddler|currier"
    r")\b",
    re.IGNORECASE,
)
_UNCOMMON_KINSHIP_REGEX = re.compile(
    r"\b("
    r"goddaughter|goddaughter|godson|godmother|godfather|stepbrother|stepsister|"
    r"half-brother|half-sister|great-aunt|great-uncle|second\s+cousin"
    r")\b",
    re.IGNORECASE,
)
_SMALL_LOCALITY_REGEX = re.compile(r"\b(village|hamlet)\b", re.IGNORECASE)

_TOWN_TO_COUNTY_REGION: dict[str, tuple[str, str]] = {
    "oxford": ("Oxfordshire", "South East"),
    "cambridge": ("Cambridgeshire", "East of England"),
    "bath": ("Somerset", "South West"),
    "keswick": ("Cumbria", "North West"),
    "haworth": ("West Yorkshire", "Yorkshire and the Humber"),
    "st ives": ("Cambridgeshire", "East of England"),
    "ely": ("Cambridgeshire", "East of England"),
    "ripon": ("North Yorkshire", "Yorkshire and the Humber"),
}
_SMALL_LOCALITIES = {"keswick", "haworth", "ely", "ripon", "st ives"}
_TOWN_REGEX = re.compile(
    r"\b(" + "|".join(sorted((re.escape(value) for value in _TOWN_TO_COUNTY_REGION.keys()), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

_AGE_REGEX = re.compile(
    r"\b(?:aged?\s+|age\s+)?(?P<age>\d{1,3})(?:\s*(?:years?\s*old|yrs?\b|yo\b))\b",
    re.IGNORECASE,
)

_DATE_LEVELS: tuple[DateSpecificity, ...] = ("YEAR", "MONTH_YEAR")
_PLACE_LEVELS: tuple[PlaceSpecificity, ...] = ("REGION", "COUNTY")
_AGE_LEVELS: tuple[AgeSpecificity, ...] = ("TEN_YEAR_BAND", "FIVE_YEAR_BAND")


@dataclass(frozen=True)
class IndirectGeneralizationPolicyConfig:
    date_enabled: bool
    place_enabled: bool
    age_enabled: bool
    date_ceiling: DateSpecificity
    place_ceiling: PlaceSpecificity
    age_ceiling: AgeSpecificity
    assist_enabled: bool


@dataclass(frozen=True)
class IndirectGeneralizationFinding:
    page_id: str
    page_index: int
    line_id: str
    category: str
    span_start: int
    span_end: int
    confidence: float
    basis_primary: RedactionFindingBasisPrimary
    basis_secondary_json: dict[str, object]
    token_refs_json: list[dict[str, object]] | None
    bbox_refs: dict[str, object]
    decision_status: RedactionDecisionStatus
    decision_reason: str | None
    action_type: Literal["GENERALIZE"]


@dataclass(frozen=True)
class _DateMatch:
    start: int
    end: int
    year: int
    month: int
    rule_id: str


@dataclass(frozen=True)
class _PlaceMatch:
    start: int
    end: int
    town: str
    county: str
    region: str


@dataclass(frozen=True)
class _AgeMatch:
    start: int
    end: int
    age: int


def _normalize_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def _normalized_upper(value: object) -> str | None:
    normalized = _normalize_text(value)
    if normalized is None:
        return None
    return normalized.upper()


def _normalize_date_specificity(value: object) -> DateSpecificity | None:
    normalized = _normalized_upper(value)
    if normalized is None:
        return None
    if normalized in {"YEAR", "YEAR_ONLY", "YYYY"}:
        return "YEAR"
    if normalized in {"MONTH_YEAR", "MONTH/YEAR", "MONTH-YEAR", "MONTHYEAR", "MMYYYY"}:
        return "MONTH_YEAR"
    return None


def _normalize_place_specificity(value: object) -> PlaceSpecificity | None:
    normalized = _normalized_upper(value)
    if normalized is None:
        return None
    if normalized in {"REGION", "REGIONAL"}:
        return "REGION"
    if normalized in {"COUNTY", "DISTRICT", "PROVINCE"}:
        return "COUNTY"
    return None


def _normalize_age_specificity(value: object) -> AgeSpecificity | None:
    normalized = _normalized_upper(value)
    if normalized is None:
        return None
    if normalized in {"TEN_YEAR_BAND", "10_YEAR_BAND", "DECADE_BAND", "AGE_BAND"}:
        return "TEN_YEAR_BAND"
    if normalized in {"FIVE_YEAR_BAND", "5_YEAR_BAND", "AGE_BAND_5"}:
        return "FIVE_YEAR_BAND"
    return None


def _resolve_assist_enabled(policy_snapshot_json: Mapping[str, object]) -> bool:
    mode = _normalized_upper(policy_snapshot_json.get("reviewer_explanation_mode"))
    if mode is None:
        return True
    if "DISABLED" in mode or mode in {"NONE", "OFF"}:
        return False
    return True


def _category_action_map(policy_snapshot_json: Mapping[str, object]) -> dict[str, str]:
    category_map: dict[str, str] = {}
    categories = policy_snapshot_json.get("categories")
    if not isinstance(categories, Sequence) or isinstance(categories, (str, bytes)):
        return category_map
    for item in categories:
        if not isinstance(item, Mapping):
            continue
        category_id = _normalized_upper(item.get("id"))
        action = _normalized_upper(item.get("action"))
        if category_id is None or action is None or action not in _SUPPORTED_ACTIONS:
            continue
        category_map[category_id] = action
    return category_map


def _candidate_setting(
    *,
    generalisation: Mapping[str, object],
    keys: Sequence[str],
) -> object | None:
    lowered = {key.lower(): value for key, value in generalisation.items()}
    for key in keys:
        if key.lower() in lowered:
            return lowered[key.lower()]
    return None


def _resolve_generalisation_policy_map(
    policy_snapshot_json: Mapping[str, object],
) -> Mapping[str, object]:
    generalisation = policy_snapshot_json.get("generalisation")
    if isinstance(generalisation, Mapping):
        return generalisation
    generalization = policy_snapshot_json.get("generalization")
    if isinstance(generalization, Mapping):
        return generalization
    return {}


def _read_by_category_ceiling(
    *,
    generalisation: Mapping[str, object],
    aliases: Sequence[str],
) -> object | None:
    by_category = generalisation.get("by_category")
    if not isinstance(by_category, Mapping):
        by_category = generalisation.get("byCategory")
    if not isinstance(by_category, Mapping):
        return None
    upper_aliases = {alias.upper() for alias in aliases}
    for key, value in by_category.items():
        key_text = _normalized_upper(key)
        if key_text is None:
            continue
        if key_text in upper_aliases:
            return value
    return None


def _has_generalize_action_for_aliases(
    *,
    category_actions: Mapping[str, str],
    aliases: Sequence[str],
) -> bool:
    alias_set = {alias.upper() for alias in aliases}
    return any(
        action == _GENERALIZE_ACTION and category in alias_set
        for category, action in category_actions.items()
    )


def resolve_indirect_generalization_policy_config(
    *,
    policy_snapshot_json: Mapping[str, object] | None,
) -> IndirectGeneralizationPolicyConfig:
    snapshot = policy_snapshot_json if isinstance(policy_snapshot_json, Mapping) else {}
    category_actions = _category_action_map(snapshot)
    generalisation = _resolve_generalisation_policy_map(snapshot)
    global_ceiling = (
        _normalize_text(generalisation.get("specificity_ceiling"))
        or _normalize_text(generalisation.get("specificityCeiling"))
    )

    date_aliases = (
        "DATE",
        "EXACT_DATE",
        "INDIRECT_DATE",
        "INDIRECT_DATE_EXACT",
    )
    place_aliases = (
        "LOCATION",
        "PLACE",
        "TOWN",
        "ADDRESS",
        "INDIRECT_TOWN",
    )
    age_aliases = (
        "AGE",
        "EXACT_AGE",
        "INDIRECT_AGE",
        "INDIRECT_AGE_EXACT",
    )

    date_by_category_ceiling = _read_by_category_ceiling(
        generalisation=generalisation,
        aliases=date_aliases,
    )
    place_by_category_ceiling = _read_by_category_ceiling(
        generalisation=generalisation,
        aliases=place_aliases,
    )
    age_by_category_ceiling = _read_by_category_ceiling(
        generalisation=generalisation,
        aliases=age_aliases,
    )

    explicit_date_setting = _candidate_setting(
        generalisation=generalisation,
        keys=("date", "dates", "date_specificity_ceiling", "dateSpecificityCeiling"),
    )
    explicit_place_setting = _candidate_setting(
        generalisation=generalisation,
        keys=("place", "places", "town", "location", "place_specificity_ceiling", "placeSpecificityCeiling"),
    )
    explicit_age_setting = _candidate_setting(
        generalisation=generalisation,
        keys=("age", "ages", "age_specificity_ceiling", "ageSpecificityCeiling"),
    )

    date_ceiling = (
        _normalize_date_specificity(date_by_category_ceiling)
        or _normalize_date_specificity(explicit_date_setting)
        or _normalize_date_specificity(global_ceiling)
        or "YEAR"
    )
    place_ceiling = (
        _normalize_place_specificity(place_by_category_ceiling)
        or _normalize_place_specificity(explicit_place_setting)
        or _normalize_place_specificity(global_ceiling)
        or "REGION"
    )
    age_ceiling = (
        _normalize_age_specificity(age_by_category_ceiling)
        or _normalize_age_specificity(explicit_age_setting)
        or _normalize_age_specificity(global_ceiling)
        or "TEN_YEAR_BAND"
    )

    date_enabled = _has_generalize_action_for_aliases(
        category_actions=category_actions,
        aliases=date_aliases,
    ) or date_by_category_ceiling is not None or explicit_date_setting is not None
    place_enabled = _has_generalize_action_for_aliases(
        category_actions=category_actions,
        aliases=place_aliases,
    ) or place_by_category_ceiling is not None or explicit_place_setting is not None
    age_enabled = _has_generalize_action_for_aliases(
        category_actions=category_actions,
        aliases=age_aliases,
    ) or age_by_category_ceiling is not None or explicit_age_setting is not None

    return IndirectGeneralizationPolicyConfig(
        date_enabled=date_enabled,
        place_enabled=place_enabled,
        age_enabled=age_enabled,
        date_ceiling=date_ceiling,
        place_ceiling=place_ceiling,
        age_ceiling=age_ceiling,
        assist_enabled=_resolve_assist_enabled(snapshot),
    )


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def _build_token_offsets(
    *,
    line_text: str,
    tokens: Sequence[RedactionDetectionToken],
) -> dict[str, tuple[int, int]]:
    offsets: dict[str, tuple[int, int]] = {}
    ordered = sorted(tokens, key=lambda item: (item.token_index, item.token_id))
    consumed: list[tuple[int, int]] = []
    cursor = 0
    for token in ordered:
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
        offsets[token.token_id] = (start, end)
    return offsets


def _resolve_span_token_refs(
    *,
    line: RedactionDetectionLine,
    span_start: int,
    span_end: int,
) -> tuple[list[dict[str, object]] | None, dict[str, object]]:
    token_offsets = _build_token_offsets(line_text=line.text, tokens=line.tokens)
    selected_tokens: list[RedactionDetectionToken] = []
    token_refs: list[dict[str, object]] = []
    for token in sorted(line.tokens, key=lambda item: (item.token_index, item.token_id)):
        offsets = token_offsets.get(token.token_id)
        if offsets is None:
            continue
        token_start, token_end = offsets
        if not _overlaps(span_start, span_end, token_start, token_end):
            continue
        selected_tokens.append(token)
        token_refs.append(
            {
                "tokenId": token.token_id,
                "lineId": line.line_id,
                "tokenIndex": token.token_index,
            }
        )
    bbox_refs: dict[str, object] = {"lineId": line.line_id}
    token_bboxes: list[dict[str, object]] = []
    for token in selected_tokens:
        if isinstance(token.bbox_json, Mapping):
            token_bboxes.append(dict(token.bbox_json))
    if token_bboxes:
        bbox_refs["tokenBboxes"] = token_bboxes
    return (token_refs if token_refs else None), bbox_refs


def _clamp_specificity(
    *,
    requested: str,
    ceiling: str,
    levels: Sequence[str],
) -> tuple[str, bool]:
    requested_index = levels.index(requested) if requested in levels else len(levels) - 1
    ceiling_index = levels.index(ceiling) if ceiling in levels else 0
    if requested_index <= ceiling_index:
        return requested, False
    return ceiling, True


def _safe_day_month_year(day: int, month: int, year: int) -> bool:
    if year < 1000 or year > 2200:
        return False
    if month < 1 or month > 12:
        return False
    if day < 1 or day > 31:
        return False
    return True


def _iter_exact_date_matches(text: str) -> list[_DateMatch]:
    matches: list[_DateMatch] = []
    seen_spans: set[tuple[int, int]] = set()
    for regex, rule_id in (
        (_EXACT_DATE_NUMERIC_REGEX, "DATE_NUMERIC_DAY_MONTH_YEAR"),
        (_EXACT_DATE_ISO_REGEX, "DATE_ISO_YEAR_MONTH_DAY"),
        (_EXACT_DATE_DAY_MONTH_NAME_REGEX, "DATE_DAY_MONTH_NAME_YEAR"),
        (_EXACT_DATE_MONTH_NAME_DAY_REGEX, "DATE_MONTH_NAME_DAY_YEAR"),
    ):
        for candidate in regex.finditer(text):
            start, end = candidate.span()
            if (start, end) in seen_spans:
                continue
            day = 0
            month = 0
            year = 0
            try:
                if "month_name" in candidate.groupdict():
                    month_name = str(candidate.group("month_name")).strip().lower()
                    month = next(
                        (key for key, value in _MONTH_NAME_BY_NUMBER.items() if value.lower() == month_name),
                        0,
                    )
                else:
                    month = int(candidate.group("month"))
                day = int(candidate.group("day"))
                year = int(candidate.group("year"))
            except (TypeError, ValueError):
                continue
            if not _safe_day_month_year(day, month, year):
                continue
            seen_spans.add((start, end))
            matches.append(
                _DateMatch(
                    start=start,
                    end=end,
                    year=year,
                    month=month,
                    rule_id=rule_id,
                )
            )
    matches.sort(key=lambda item: (item.start, item.end, item.rule_id))
    return matches


def _iter_place_matches(text: str) -> list[_PlaceMatch]:
    matches: list[_PlaceMatch] = []
    seen_spans: set[tuple[int, int]] = set()
    for candidate in _TOWN_REGEX.finditer(text):
        start, end = candidate.span()
        if (start, end) in seen_spans:
            continue
        town_key = candidate.group(0).strip().lower()
        county_region = _TOWN_TO_COUNTY_REGION.get(town_key)
        if county_region is None:
            continue
        county, region = county_region
        seen_spans.add((start, end))
        matches.append(
            _PlaceMatch(
                start=start,
                end=end,
                town=candidate.group(0).strip(),
                county=county,
                region=region,
            )
        )
    matches.sort(key=lambda item: (item.start, item.end, item.town.lower()))
    return matches


def _iter_age_matches(text: str) -> list[_AgeMatch]:
    matches: list[_AgeMatch] = []
    seen_spans: set[tuple[int, int]] = set()
    for candidate in _AGE_REGEX.finditer(text):
        start, end = candidate.span()
        if (start, end) in seen_spans:
            continue
        try:
            age = int(candidate.group("age"))
        except (TypeError, ValueError):
            continue
        if age < 0 or age > 120:
            continue
        seen_spans.add((start, end))
        matches.append(_AgeMatch(start=start, end=end, age=age))
    matches.sort(key=lambda item: (item.start, item.end, item.age))
    return matches


def _date_transform(
    *,
    match: _DateMatch,
    ceiling: DateSpecificity,
) -> tuple[str, DateSpecificity, bool]:
    requested = "MONTH_YEAR"
    applied, clamped = _clamp_specificity(
        requested=requested,
        ceiling=ceiling,
        levels=_DATE_LEVELS,
    )
    if applied == "MONTH_YEAR":
        month_name = _MONTH_NAME_BY_NUMBER.get(match.month, "Unknown")
        return f"{month_name} {match.year}", applied, clamped
    return str(match.year), applied, clamped


def _place_transform(
    *,
    match: _PlaceMatch,
    ceiling: PlaceSpecificity,
) -> tuple[str, PlaceSpecificity, bool]:
    requested = "COUNTY"
    applied, clamped = _clamp_specificity(
        requested=requested,
        ceiling=ceiling,
        levels=_PLACE_LEVELS,
    )
    if applied == "COUNTY":
        return match.county, applied, clamped
    return match.region, applied, clamped


def _age_band(start: int, width: int) -> str:
    return f"{start}-{start + width - 1}"


def _age_transform(
    *,
    match: _AgeMatch,
    ceiling: AgeSpecificity,
) -> tuple[str, AgeSpecificity, bool]:
    requested = "FIVE_YEAR_BAND"
    applied, clamped = _clamp_specificity(
        requested=requested,
        ceiling=ceiling,
        levels=_AGE_LEVELS,
    )
    if applied == "FIVE_YEAR_BAND":
        start = (match.age // 5) * 5
        return _age_band(start, 5), applied, clamped
    start = (match.age // 10) * 10
    return _age_band(start, 10), applied, clamped


def _build_grouping_metadata(
    *,
    line: RedactionDetectionLine,
    has_exact_date: bool,
    place_matches: Sequence[_PlaceMatch],
) -> list[dict[str, object]]:
    groups: list[dict[str, object]] = []
    line_text = line.text
    has_rare_occupation = _RARE_OCCUPATION_REGEX.search(line_text) is not None
    has_uncommon_kinship = _UNCOMMON_KINSHIP_REGEX.search(line_text) is not None
    has_small_locality = _SMALL_LOCALITY_REGEX.search(line_text) is not None
    if not has_small_locality:
        has_small_locality = any(match.town.lower() in _SMALL_LOCALITIES for match in place_matches)

    if place_matches and has_rare_occupation and has_exact_date:
        groups.append(
            {
                "groupId": f"{line.line_id}:PLACE_RARE_OCCUPATION_EXACT_DATE",
                "rule": "PLACE_RARE_OCCUPATION_EXACT_DATE",
                "evidence": ["PLACE", "RARE_OCCUPATION", "EXACT_DATE"],
                "lineId": line.line_id,
            }
        )
    if place_matches and has_uncommon_kinship and has_small_locality:
        groups.append(
            {
                "groupId": f"{line.line_id}:UNCOMMON_KINSHIP_SMALL_LOCALITY",
                "rule": "UNCOMMON_KINSHIP_SMALL_LOCALITY",
                "evidence": ["UNCOMMON_KINSHIP", "SMALL_LOCALITY"],
                "lineId": line.line_id,
            }
        )
    return groups


def _build_secondary_basis(
    *,
    source_type: Literal["DATE", "PLACE", "AGE"],
    deterministic_rule_id: str,
    transformed_value: str,
    specificity_applied: str,
    specificity_ceiling: str,
    was_clamped: bool,
    grouped_risk_metadata: Sequence[dict[str, object]],
    assist_enabled: bool,
) -> dict[str, object]:
    explanation = (
        f"Policy generalization rule {deterministic_rule_id} reduced {source_type} "
        f"specificity to {specificity_applied} (ceiling {specificity_ceiling})."
    )
    payload: dict[str, object] = {
        "transformation": {
            "kind": "GENERALIZE",
            "sourceType": source_type,
            "deterministicRuleId": deterministic_rule_id,
            "specificityApplied": specificity_applied,
            "specificityCeiling": specificity_ceiling,
            "transformedValue": transformed_value,
            "policyControlled": True,
            "deterministic": True,
        },
        "generalizationExplanation": {
            "summary": explanation,
            "reviewerVisible": True,
        },
    }
    if grouped_risk_metadata:
        payload["indirectRiskGrouping"] = {
            "groups": [dict(item) for item in grouped_risk_metadata],
            "metadataOnly": True,
        }
    if assist_enabled:
        payload["assistSummary"] = {
            "mode": "LOCAL_ASSIST_METADATA_ONLY",
            "explanation": explanation,
            "requestedSpecificity": specificity_applied,
            "specificityClamped": was_clamped,
        }
    return payload


def extract_transformation_value(
    basis_secondary_json: Mapping[str, object] | None,
) -> str | None:
    if not isinstance(basis_secondary_json, Mapping):
        return None
    transformation = basis_secondary_json.get("transformation")
    if not isinstance(transformation, Mapping):
        return None
    transformed = _normalize_text(transformation.get("transformedValue"))
    if transformed is None:
        return None
    return transformed


def detect_indirect_identifier_findings(
    *,
    lines: Sequence[RedactionDetectionLine],
    policy_snapshot_json: Mapping[str, object] | None,
) -> list[IndirectGeneralizationFinding]:
    config = resolve_indirect_generalization_policy_config(
        policy_snapshot_json=policy_snapshot_json,
    )
    if not (config.date_enabled or config.place_enabled or config.age_enabled):
        return []

    findings: list[IndirectGeneralizationFinding] = []
    for line in lines:
        date_matches = _iter_exact_date_matches(line.text) if config.date_enabled else []
        place_matches = _iter_place_matches(line.text) if config.place_enabled else []
        age_matches = _iter_age_matches(line.text) if config.age_enabled else []
        grouped_metadata = _build_grouping_metadata(
            line=line,
            has_exact_date=bool(date_matches),
            place_matches=place_matches,
        )

        for match in date_matches:
            transformed_value, applied_specificity, was_clamped = _date_transform(
                match=match,
                ceiling=config.date_ceiling,
            )
            token_refs_json, bbox_refs = _resolve_span_token_refs(
                line=line,
                span_start=match.start,
                span_end=match.end,
            )
            findings.append(
                IndirectGeneralizationFinding(
                    page_id=line.page_id,
                    page_index=line.page_index,
                    line_id=line.line_id,
                    category="INDIRECT_DATE_EXACT",
                    span_start=match.start,
                    span_end=match.end,
                    confidence=0.97,
                    basis_primary="HEURISTIC",
                    basis_secondary_json=_build_secondary_basis(
                        source_type="DATE",
                        deterministic_rule_id=match.rule_id,
                        transformed_value=transformed_value,
                        specificity_applied=applied_specificity,
                        specificity_ceiling=config.date_ceiling,
                        was_clamped=was_clamped,
                        grouped_risk_metadata=grouped_metadata,
                        assist_enabled=config.assist_enabled,
                    ),
                    token_refs_json=token_refs_json,
                    bbox_refs=bbox_refs,
                    decision_status="AUTO_APPLIED",
                    decision_reason="Policy-driven deterministic date generalization.",
                    action_type="GENERALIZE",
                )
            )

        for match in place_matches:
            transformed_value, applied_specificity, was_clamped = _place_transform(
                match=match,
                ceiling=config.place_ceiling,
            )
            token_refs_json, bbox_refs = _resolve_span_token_refs(
                line=line,
                span_start=match.start,
                span_end=match.end,
            )
            findings.append(
                IndirectGeneralizationFinding(
                    page_id=line.page_id,
                    page_index=line.page_index,
                    line_id=line.line_id,
                    category="INDIRECT_TOWN",
                    span_start=match.start,
                    span_end=match.end,
                    confidence=0.94,
                    basis_primary="HEURISTIC",
                    basis_secondary_json=_build_secondary_basis(
                        source_type="PLACE",
                        deterministic_rule_id="TOWN_TO_COUNTY_REGION",
                        transformed_value=transformed_value,
                        specificity_applied=applied_specificity,
                        specificity_ceiling=config.place_ceiling,
                        was_clamped=was_clamped,
                        grouped_risk_metadata=grouped_metadata,
                        assist_enabled=config.assist_enabled,
                    ),
                    token_refs_json=token_refs_json,
                    bbox_refs=bbox_refs,
                    decision_status="AUTO_APPLIED",
                    decision_reason="Policy-driven deterministic place generalization.",
                    action_type="GENERALIZE",
                )
            )

        for match in age_matches:
            transformed_value, applied_specificity, was_clamped = _age_transform(
                match=match,
                ceiling=config.age_ceiling,
            )
            token_refs_json, bbox_refs = _resolve_span_token_refs(
                line=line,
                span_start=match.start,
                span_end=match.end,
            )
            findings.append(
                IndirectGeneralizationFinding(
                    page_id=line.page_id,
                    page_index=line.page_index,
                    line_id=line.line_id,
                    category="INDIRECT_AGE_EXACT",
                    span_start=match.start,
                    span_end=match.end,
                    confidence=0.95,
                    basis_primary="HEURISTIC",
                    basis_secondary_json=_build_secondary_basis(
                        source_type="AGE",
                        deterministic_rule_id="EXACT_AGE_TO_BAND",
                        transformed_value=transformed_value,
                        specificity_applied=applied_specificity,
                        specificity_ceiling=config.age_ceiling,
                        was_clamped=was_clamped,
                        grouped_risk_metadata=grouped_metadata,
                        assist_enabled=config.assist_enabled,
                    ),
                    token_refs_json=token_refs_json,
                    bbox_refs=bbox_refs,
                    decision_status="AUTO_APPLIED",
                    decision_reason="Policy-driven deterministic age-band generalization.",
                    action_type="GENERALIZE",
                )
            )

    findings.sort(
        key=lambda item: (
            item.page_index,
            item.page_id,
            item.line_id,
            item.span_start,
            item.span_end,
            item.category,
        )
    )
    return findings

