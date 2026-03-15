from __future__ import annotations

from app.documents.redaction_detection import RedactionDetectionLine
from app.documents.redaction_generalization import (
    detect_indirect_identifier_findings,
    extract_transformation_value,
)


def _line(text: str, *, line_id: str = "line-1") -> RedactionDetectionLine:
    return RedactionDetectionLine(
        page_id="page-1",
        page_index=0,
        line_id=line_id,
        text=text,
        tokens=(),
    )


def test_date_generalization_is_deterministic() -> None:
    policy = {
        "categories": [{"id": "DATE", "action": "GENERALIZE"}],
        "generalisation": {"by_category": {"DATE": "MONTH_YEAR"}},
    }
    lines = [_line("Birth recorded on 14/03/1901.")]
    first = detect_indirect_identifier_findings(lines=lines, policy_snapshot_json=policy)
    second = detect_indirect_identifier_findings(lines=lines, policy_snapshot_json=policy)

    first_dates = [finding for finding in first if finding.category == "INDIRECT_DATE_EXACT"]
    second_dates = [finding for finding in second if finding.category == "INDIRECT_DATE_EXACT"]
    assert len(first_dates) == 1
    assert len(second_dates) == 1
    assert first_dates[0].span_start == second_dates[0].span_start
    assert first_dates[0].span_end == second_dates[0].span_end
    assert extract_transformation_value(first_dates[0].basis_secondary_json) == "March 1901"
    assert extract_transformation_value(second_dates[0].basis_secondary_json) == "March 1901"


def test_place_generalization_respects_region_ceiling() -> None:
    policy = {
        "categories": [{"id": "LOCATION", "action": "GENERALIZE"}],
        "generalisation": {"by_category": {"LOCATION": "REGION"}},
    }
    findings = detect_indirect_identifier_findings(
        lines=[_line("Last known residence: Keswick.")],
        policy_snapshot_json=policy,
    )
    place_findings = [finding for finding in findings if finding.category == "INDIRECT_TOWN"]
    assert len(place_findings) == 1
    transformed = place_findings[0].basis_secondary_json["transformation"]
    assert isinstance(transformed, dict)
    assert transformed["specificityApplied"] == "REGION"
    assert transformed["specificityCeiling"] == "REGION"
    assert transformed["transformedValue"] == "North West"


def test_age_generalization_is_deterministic() -> None:
    policy = {
        "categories": [{"id": "AGE", "action": "GENERALIZE"}],
        "generalisation": {"by_category": {"AGE": "FIVE_YEAR_BAND"}},
    }
    findings = detect_indirect_identifier_findings(
        lines=[_line("Patient aged 47 years old.")],
        policy_snapshot_json=policy,
    )
    age_findings = [finding for finding in findings if finding.category == "INDIRECT_AGE_EXACT"]
    assert len(age_findings) == 1
    transformed = extract_transformation_value(age_findings[0].basis_secondary_json)
    assert transformed == "45-49"


def test_assist_specificity_is_clamped_to_policy_ceiling() -> None:
    policy = {
        "categories": [{"id": "DATE", "action": "GENERALIZE"}],
        "generalisation": {"by_category": {"DATE": "YEAR"}},
    }
    findings = detect_indirect_identifier_findings(
        lines=[_line("Event date: 23 March 1899.")],
        policy_snapshot_json=policy,
    )
    date_findings = [finding for finding in findings if finding.category == "INDIRECT_DATE_EXACT"]
    assert len(date_findings) == 1
    metadata = date_findings[0].basis_secondary_json
    transformation = metadata.get("transformation")
    assist_summary = metadata.get("assistSummary")
    assert isinstance(transformation, dict)
    assert isinstance(assist_summary, dict)
    assert transformation["specificityApplied"] == "YEAR"
    assert transformation["specificityCeiling"] == "YEAR"
    assert assist_summary["requestedSpecificity"] == "YEAR"
    assert assist_summary["specificityClamped"] is True
    assert transformation["transformedValue"] == "1899"


def test_indirect_risk_grouping_remains_metadata_only() -> None:
    policy = {
        "categories": [
            {"id": "DATE", "action": "GENERALIZE"},
            {"id": "LOCATION", "action": "GENERALIZE"},
        ],
        "generalisation": {"by_category": {"DATE": "MONTH_YEAR", "LOCATION": "COUNTY"}},
    }
    findings = detect_indirect_identifier_findings(
        lines=[
            _line(
                "Keswick village midwife present on 14/03/1901 with stepbrother witness."
            )
        ],
        policy_snapshot_json=policy,
    )
    assert findings
    grouped = [
        finding
        for finding in findings
        if isinstance(finding.basis_secondary_json.get("indirectRiskGrouping"), dict)
    ]
    assert grouped
    group_payload = grouped[0].basis_secondary_json["indirectRiskGrouping"]
    assert isinstance(group_payload, dict)
    assert group_payload.get("metadataOnly") is True
    assert "chainOfThought" not in group_payload

