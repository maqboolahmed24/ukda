from __future__ import annotations

import json
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from app.auth.models import SessionPrincipal
from app.core.config import Settings
from app.documents.models import (
    DocumentPageRecord,
    DocumentRecord,
    LineTranscriptionResultRecord,
    RedactionFindingRecord,
    RedactionOutputRecord,
    RedactionRunRecord,
    TokenTranscriptionResultRecord,
)
from app.documents.redaction_detection import (
    BoundedAssistExplainer,
    DirectIdentifierRecallCase,
    DirectIdentifierRecallExpected,
    LocalNERDetector,
    RedactionDetectionCandidate,
    RedactionDetectionLine,
    detect_direct_identifier_findings,
    detect_rule_candidates,
    evaluate_direct_identifier_recall,
    fuse_detection_candidates,
    resolve_direct_identifier_policy_config,
)
from app.documents.service import DocumentService

FIXTURE_PACK_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "privacy-direct-identifiers-gold-set"
    / "fixture-pack.v1.json"
)


class _FakeRedactionProjectService:
    @staticmethod
    def resolve_workspace_context(*, current_user: SessionPrincipal, project_id: str):  # type: ignore[no-untyped-def]
        del current_user
        del project_id
        return SimpleNamespace(
            is_member=True,
            can_access_settings=False,
            summary=SimpleNamespace(current_user_role="PROJECT_LEAD"),
        )


class _FakeRedactionStore:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.document = DocumentRecord(
            id="doc-1",
            project_id="project-1",
            original_filename="register-1880.pdf",
            stored_filename="controlled/raw/project-1/doc-1/original.bin",
            content_type_detected="application/pdf",
            bytes=1024,
            sha256="a" * 64,
            page_count=1,
            status="READY",
            created_by="user-1",
            created_at=now,
            updated_at=now,
        )
        self.page = DocumentPageRecord(
            id="page-1",
            document_id="doc-1",
            page_index=0,
            width=1000,
            height=1400,
            dpi=300,
            source_width=1000,
            source_height=1400,
            source_dpi=300,
            source_color_mode="GRAY",
            status="READY",
            derived_image_key=None,
            derived_image_sha256=None,
            thumbnail_key=None,
            thumbnail_sha256=None,
            failure_reason=None,
            canceled_by=None,
            canceled_at=None,
            viewer_rotation=0,
            created_at=now,
            updated_at=now,
        )
        self.line = LineTranscriptionResultRecord(
            run_id="transcription-run-1",
            page_id="page-1",
            line_id="line-1",
            text_diplomatic="Mr John Smith email jane.doe@example.org",
            conf_line=0.98,
            confidence_band="HIGH",
            confidence_basis="MODEL_NATIVE",
            confidence_calibration_version="v1",
            alignment_json_key=None,
            char_boxes_key=None,
            schema_validation_status="VALID",
            flags_json={},
            machine_output_sha256=None,
            active_transcript_version_id=None,
            version_etag="line-etag",
            token_anchor_status="CURRENT",
            created_at=now,
            updated_at=now,
        )
        self.tokens = [
            TokenTranscriptionResultRecord(
                run_id="transcription-run-1",
                page_id="page-1",
                line_id="line-1",
                token_id="tok-1",
                token_index=0,
                token_text="Mr",
                token_confidence=0.99,
                bbox_json={"x": 10, "y": 10, "w": 10, "h": 10},
                polygon_json=None,
                source_kind="LINE",
                source_ref_id="line-1",
                projection_basis="ENGINE_OUTPUT",
                created_at=now,
                updated_at=now,
            ),
            TokenTranscriptionResultRecord(
                run_id="transcription-run-1",
                page_id="page-1",
                line_id="line-1",
                token_id="tok-2",
                token_index=1,
                token_text="John",
                token_confidence=0.99,
                bbox_json={"x": 30, "y": 10, "w": 20, "h": 10},
                polygon_json=None,
                source_kind="LINE",
                source_ref_id="line-1",
                projection_basis="ENGINE_OUTPUT",
                created_at=now,
                updated_at=now,
            ),
            TokenTranscriptionResultRecord(
                run_id="transcription-run-1",
                page_id="page-1",
                line_id="line-1",
                token_id="tok-3",
                token_index=2,
                token_text="Smith",
                token_confidence=0.99,
                bbox_json={"x": 55, "y": 10, "w": 25, "h": 10},
                polygon_json=None,
                source_kind="LINE",
                source_ref_id="line-1",
                projection_basis="ENGINE_OUTPUT",
                created_at=now,
                updated_at=now,
            ),
            TokenTranscriptionResultRecord(
                run_id="transcription-run-1",
                page_id="page-1",
                line_id="line-1",
                token_id="tok-4",
                token_index=3,
                token_text="email",
                token_confidence=0.99,
                bbox_json={"x": 90, "y": 10, "w": 26, "h": 10},
                polygon_json=None,
                source_kind="LINE",
                source_ref_id="line-1",
                projection_basis="ENGINE_OUTPUT",
                created_at=now,
                updated_at=now,
            ),
            TokenTranscriptionResultRecord(
                run_id="transcription-run-1",
                page_id="page-1",
                line_id="line-1",
                token_id="tok-5",
                token_index=4,
                token_text="jane.doe@example.org",
                token_confidence=0.99,
                bbox_json={"x": 130, "y": 10, "w": 120, "h": 10},
                polygon_json=None,
                source_kind="LINE",
                source_ref_id="line-1",
                projection_basis="ENGINE_OUTPUT",
                created_at=now,
                updated_at=now,
            ),
        ]
        self.runs: dict[str, RedactionRunRecord] = {}
        self.replaced_rows: list[dict[str, object]] = []
        self.findings_by_run_page: dict[tuple[str, str], list[RedactionFindingRecord]] = {}
        self.outputs: dict[tuple[str, str], RedactionOutputRecord] = {}

    def get_document(self, *, project_id: str, document_id: str) -> DocumentRecord | None:
        if project_id != self.document.project_id or document_id != self.document.id:
            return None
        return self.document

    def create_redaction_run(
        self,
        *,
        project_id: str,
        document_id: str,
        created_by: str,
        input_transcription_run_id: str | None = None,
        input_layout_run_id: str | None = None,
        run_kind: str = "BASELINE",
        supersedes_redaction_run_id: str | None = None,
        detectors_version: str = "phase-5.0-scaffold",
    ) -> RedactionRunRecord:
        del supersedes_redaction_run_id
        now = datetime.now(UTC)
        run_id = f"redaction-run-{len(self.runs) + 1}"
        run = RedactionRunRecord(
            id=run_id,
            project_id=project_id,
            document_id=document_id,
            input_transcription_run_id=input_transcription_run_id or "transcription-run-1",
            input_layout_run_id=input_layout_run_id,
            run_kind=run_kind,  # type: ignore[arg-type]
            supersedes_redaction_run_id=None,
            superseded_by_redaction_run_id=None,
            policy_snapshot_id="baseline-phase0-v1",
            policy_snapshot_json={
                "defaults": {"auto_apply_confidence_threshold": 0.9},
                "categories": [
                    {"id": "EMAIL", "review_required_below": 0.85},
                    {"id": "PERSON_NAME", "review_required_below": 0.9},
                ],
                "directIdentifierRecallFloor": 0.99,
            },
            policy_snapshot_hash="b" * 64,
            policy_id=None,
            policy_family_id=None,
            policy_version=None,
            detectors_version=detectors_version,
            status="SUCCEEDED",
            created_by=created_by,
            created_at=now,
            started_at=now,
            finished_at=now,
            failure_reason=None,
        )
        self.runs[run_id] = run
        return run

    def get_redaction_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> RedactionRunRecord | None:
        run = self.runs.get(run_id)
        if run is None:
            return None
        if run.project_id != project_id or run.document_id != document_id:
            return None
        return run

    def list_document_pages(self, *, project_id: str, document_id: str) -> list[DocumentPageRecord]:
        assert project_id == self.document.project_id
        assert document_id == self.document.id
        return [self.page]

    def list_line_transcription_results(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> list[LineTranscriptionResultRecord]:
        assert project_id == self.document.project_id
        assert document_id == self.document.id
        assert run_id == self.line.run_id
        assert page_id == self.page.id
        return [self.line]

    def list_token_transcription_results(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
    ) -> list[TokenTranscriptionResultRecord]:
        assert project_id == self.document.project_id
        assert document_id == self.document.id
        assert run_id == self.line.run_id
        assert page_id == self.page.id
        return list(self.tokens)

    def get_transcript_version(self, **kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        return None

    def replace_redaction_findings(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        findings: list[dict[str, object]],
    ) -> list[RedactionFindingRecord]:
        assert project_id == self.document.project_id
        assert document_id == self.document.id
        assert run_id in self.runs
        self.replaced_rows = [dict(item) for item in findings]
        now = datetime.now(UTC)
        outputs: list[RedactionFindingRecord] = []
        for index, row in enumerate(findings, start=1):
            outputs.append(
                RedactionFindingRecord(
                    id=f"finding-{index}",
                    run_id=run_id,
                    page_id=str(row["page_id"]),
                    line_id=str(row["line_id"]) if isinstance(row.get("line_id"), str) else None,
                    category=str(row["category"]),
                    span_start=int(row["span_start"])
                    if isinstance(row.get("span_start"), int)
                    else None,
                    span_end=int(row["span_end"]) if isinstance(row.get("span_end"), int) else None,
                    span_basis_kind=str(row["span_basis_kind"]),  # type: ignore[arg-type]
                    span_basis_ref=str(row["span_basis_ref"])
                    if isinstance(row.get("span_basis_ref"), str)
                    else None,
                    confidence=float(row["confidence"])
                    if isinstance(row.get("confidence"), (int, float))
                    else None,
                    basis_primary=str(row["basis_primary"]),  # type: ignore[arg-type]
                    basis_secondary_json=dict(row["basis_secondary_json"])
                    if isinstance(row.get("basis_secondary_json"), dict)
                    else None,
                    assist_explanation_key=None,
                    assist_explanation_sha256=None,
                    bbox_refs=dict(row.get("bbox_refs") or {}),
                    token_refs_json=[dict(item) for item in row["token_refs_json"]]
                    if isinstance(row.get("token_refs_json"), list)
                    else None,
                    area_mask_id=None,
                    decision_status=str(row["decision_status"]),  # type: ignore[arg-type]
                    override_risk_classification=None,
                    override_risk_reason_codes_json=None,
                    decision_by=None,
                    decision_at=now if row.get("decision_status") == "AUTO_APPLIED" else None,
                    decision_reason=str(row["decision_reason"])
                    if isinstance(row.get("decision_reason"), str)
                    else None,
                    decision_etag=f"etag-{index}",
                    updated_at=now,
                    created_at=now,
                )
            )
        grouped: dict[tuple[str, str], list[RedactionFindingRecord]] = {}
        for finding in outputs:
            grouped.setdefault((finding.run_id, finding.page_id), []).append(finding)
        self.findings_by_run_page.update(grouped)
        return outputs

    def list_redaction_findings(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str | None = None,
        category: str | None = None,
        unresolved_only: bool = False,
    ) -> list[RedactionFindingRecord]:
        del project_id
        del document_id
        rows: list[RedactionFindingRecord] = []
        for (candidate_run_id, candidate_page_id), findings in self.findings_by_run_page.items():
            if candidate_run_id != run_id:
                continue
            if page_id is not None and candidate_page_id != page_id:
                continue
            rows.extend(findings)
        if category is not None:
            rows = [row for row in rows if row.category == category]
        if unresolved_only:
            rows = [
                row
                for row in rows
                if row.decision_status in {"NEEDS_REVIEW", "OVERRIDDEN", "FALSE_POSITIVE"}
            ]
        return rows

    def set_redaction_output_projection(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_id: str,
        status: str,
        safeguarded_preview_key: str | None,
        preview_sha256: str | None,
        failure_reason: str | None,
    ) -> RedactionOutputRecord:
        del project_id
        del document_id
        now = datetime.now(UTC)
        existing = self.outputs.get((run_id, page_id))
        output = RedactionOutputRecord(
            run_id=run_id,
            page_id=page_id,
            status=status,  # type: ignore[arg-type]
            safeguarded_preview_key=safeguarded_preview_key,
            preview_sha256=preview_sha256,
            started_at=existing.started_at if existing is not None else now,
            generated_at=now if status == "READY" else None,
            canceled_by=None,
            canceled_at=None,
            failure_reason=failure_reason,
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
        )
        self.outputs[(run_id, page_id)] = output
        return output

    def cancel_redaction_run(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        canceled_by: str,
    ) -> RedactionRunRecord:
        del canceled_by
        run = self.runs[run_id]
        canceled = replace(run, status="CANCELED", failure_reason="canceled")
        self.runs[run_id] = canceled
        return canceled


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        APP_ENV="test",
        DATABASE_URL="postgresql://ukde:ukde@127.0.0.1:5432/ukde",
        STORAGE_CONTROLLED_ROOT=str(tmp_path),
    )


def _principal() -> SessionPrincipal:
    return SessionPrincipal(
        session_id="session-test",
        auth_source="bearer",
        user_id="user-1",
        oidc_sub="oidc-user-1",
        email="user-1@test.local",
        display_name="User One",
        platform_roles=(),
        issued_at=datetime.now(UTC) - timedelta(minutes=5),
        expires_at=datetime.now(UTC) + timedelta(minutes=55),
        csrf_token="csrf-test",
    )


def _line(text: str) -> RedactionDetectionLine:
    return RedactionDetectionLine(
        page_id="page-1",
        page_index=0,
        line_id="line-1",
        text=text,
        tokens=(),
    )


def test_rule_detector_extracts_exact_spans_without_off_by_one() -> None:
    line = _line("Email jane.doe@example.org and visit https://example.org now")
    candidates = detect_rule_candidates([line])

    email = next(item for item in candidates if item.category == "EMAIL")
    assert line.text[email.span_start : email.span_end] == "jane.doe@example.org"

    url = next(item for item in candidates if item.category == "URL")
    assert line.text[url.span_start : url.span_end] == "https://example.org"


def test_uk_format_detectors_cover_postcode_and_id_patterns() -> None:
    line = _line("SW1A 1AA AB123456C 943 476 5919")
    categories = {item.category for item in detect_rule_candidates([line])}
    assert "POSTCODE" in categories
    assert "NI_NUMBER" in categories
    assert "NHS_NUMBER" in categories


def test_local_ner_detector_handles_timeout_and_empty_output() -> None:
    line = _line("John Smith")

    def slow_predictor(_: str):
        time.sleep(0.05)
        return [{"label": "person", "start": 0, "end": 10, "score": 0.95}]

    timeout_detector = LocalNERDetector(predictor=slow_predictor, timeout_seconds=0.01)
    assert timeout_detector.detect([line]) == []

    empty_detector = LocalNERDetector(predictor=lambda _: [], timeout_seconds=0.2)
    assert empty_detector.detect([line]) == []


def test_assist_timeout_falls_back_to_detector_only_status() -> None:
    line = _line("jane.doe@example.org")
    candidates = [
        RedactionDetectionCandidate(
            page_id=line.page_id,
            page_index=line.page_index,
            line_id=line.line_id,
            category="EMAIL",
            span_start=0,
            span_end=len(line.text),
            confidence=0.5,
            basis_primary="RULE",
            detector_id="PRESIDIO_EMAIL",
            source="presidio.email",
        )
    ]
    policy = resolve_direct_identifier_policy_config(
        policy_snapshot_json={"defaults": {"auto_apply_confidence_threshold": 0.9}},
        pinned_recall_floor=0.99,
    )

    explainer = BoundedAssistExplainer(
        timeout_seconds=0.01,
        explain_fn=lambda _: time.sleep(0.05) or "slow response",
    )
    findings = fuse_detection_candidates(
        lines=[line],
        candidates=candidates,
        policy_config=policy,
        assist_explainer=explainer,
    )

    assert len(findings) == 1
    assert findings[0].decision_status == "NEEDS_REVIEW"
    assert findings[0].assist_summary is None


def test_same_category_overlap_merges_preserves_secondary_basis() -> None:
    line = _line("Contact jane.doe@example.org now")
    start = line.text.index("jane.doe@example.org")
    end = start + len("jane.doe@example.org")
    candidates = [
        RedactionDetectionCandidate(
            page_id=line.page_id,
            page_index=line.page_index,
            line_id=line.line_id,
            category="EMAIL",
            span_start=start,
            span_end=end,
            confidence=0.99,
            basis_primary="RULE",
            detector_id="PRESIDIO_EMAIL",
            source="presidio.email",
        ),
        RedactionDetectionCandidate(
            page_id=line.page_id,
            page_index=line.page_index,
            line_id=line.line_id,
            category="EMAIL",
            span_start=start,
            span_end=end,
            confidence=0.7,
            basis_primary="NER",
            detector_id="GLINER",
            source="gliner.local",
        ),
    ]
    policy = resolve_direct_identifier_policy_config(
        policy_snapshot_json={"defaults": {"auto_apply_confidence_threshold": 0.9}},
        pinned_recall_floor=0.99,
    )

    findings = fuse_detection_candidates(
        lines=[line],
        candidates=candidates,
        policy_config=policy,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.basis_primary == "RULE"
    assert finding.decision_status == "AUTO_APPLIED"
    assert finding.basis_secondary_json is not None
    corroborating = finding.basis_secondary_json.get("corroboratingDetectors")
    assert isinstance(corroborating, list)
    assert any(item.get("basis") == "NER" for item in corroborating if isinstance(item, dict))


def test_cross_category_overlap_routes_to_needs_review() -> None:
    line = _line("John 07123 456 789")
    candidates = [
        RedactionDetectionCandidate(
            page_id=line.page_id,
            page_index=line.page_index,
            line_id=line.line_id,
            category="PERSON_NAME",
            span_start=0,
            span_end=9,
            confidence=0.9,
            basis_primary="NER",
            detector_id="GLINER",
            source="gliner.local",
        ),
        RedactionDetectionCandidate(
            page_id=line.page_id,
            page_index=line.page_index,
            line_id=line.line_id,
            category="PHONE",
            span_start=5,
            span_end=18,
            confidence=0.97,
            basis_primary="RULE",
            detector_id="PRESIDIO_PHONE",
            source="presidio.phone",
        ),
    ]
    policy = resolve_direct_identifier_policy_config(
        policy_snapshot_json={"defaults": {"auto_apply_confidence_threshold": 0.8}},
        pinned_recall_floor=0.99,
    )

    findings = fuse_detection_candidates(
        lines=[line],
        candidates=candidates,
        policy_config=policy,
    )

    assert len(findings) == 2
    assert all(item.decision_status == "NEEDS_REVIEW" for item in findings)
    assert any(
        "cross_category_overlap" in str(item.basis_secondary_json)
        for item in findings
        if item.basis_secondary_json is not None
    )


def test_assist_cannot_create_auto_applied_without_detector_evidence() -> None:
    policy = resolve_direct_identifier_policy_config(
        policy_snapshot_json={"defaults": {"auto_apply_confidence_threshold": 0.8}},
        pinned_recall_floor=0.99,
    )
    findings = detect_direct_identifier_findings(
        lines=[],
        policy_config=policy,
        assist_explainer=BoundedAssistExplainer(explain_fn=lambda _: "assist only"),
    )
    assert findings == []


def _load_recall_fixture_pack() -> tuple[dict[str, object], list[DirectIdentifierRecallCase]]:
    raw = json.loads(FIXTURE_PACK_PATH.read_text(encoding="utf-8"))
    policy_snapshot = dict(raw.get("policySnapshot") or {})
    cases: list[DirectIdentifierRecallCase] = []
    for row in raw.get("cases", []):
        if row.get("includeInRecallGate") is False:
            continue
        expected_rows = row.get("expected", [])
        expected = tuple(
            DirectIdentifierRecallExpected(
                category=str(item.get("category") or ""),
                value=str(item.get("value") or ""),
            )
            for item in expected_rows
            if isinstance(item, dict)
        )
        cases.append(
            DirectIdentifierRecallCase(
                case_id=str(row.get("caseId") or ""),
                text=str(row.get("text") or ""),
                expected=expected,
            )
        )
    return policy_snapshot, cases


def test_direct_identifier_recall_floor_gate_uses_policy_snapshot_floor() -> None:
    policy_snapshot, cases = _load_recall_fixture_pack()
    policy = resolve_direct_identifier_policy_config(
        policy_snapshot_json=policy_snapshot,
        pinned_recall_floor=0.8,
    )
    assert policy.direct_identifier_recall_floor == 0.99

    evaluation = evaluate_direct_identifier_recall(
        cases=cases,
        policy_config=policy,
        ner_detector=LocalNERDetector(predictor=lambda _: [], timeout_seconds=0.05),
    )
    assert evaluation.passed, evaluation.format_failure_summary()


def test_direct_identifier_recall_gate_fails_when_recall_drops() -> None:
    policy_snapshot, cases = _load_recall_fixture_pack()
    policy = resolve_direct_identifier_policy_config(
        policy_snapshot_json=policy_snapshot,
        pinned_recall_floor=0.8,
    )
    degraded_cases = list(cases)
    degraded_cases.append(
        DirectIdentifierRecallCase(
            case_id="missing-expected",
            text="No identifier on this line",
            expected=(
                DirectIdentifierRecallExpected(
                    category="EMAIL",
                    value="unseen@example.org",
                ),
            ),
        )
    )

    evaluation = evaluate_direct_identifier_recall(
        cases=degraded_cases,
        policy_config=policy,
        ner_detector=LocalNERDetector(predictor=lambda _: [], timeout_seconds=0.05),
    )

    assert not evaluation.passed
    assert "missing-expected" in evaluation.format_failure_summary()


def test_document_service_create_redaction_run_materializes_detection_findings(
    tmp_path: Path,
) -> None:
    service = DocumentService(
        settings=_settings(tmp_path),
        store=_FakeRedactionStore(),  # type: ignore[arg-type]
        project_service=_FakeRedactionProjectService(),  # type: ignore[arg-type]
    )

    run = service.create_redaction_run(
        current_user=_principal(),
        project_id="project-1",
        document_id="doc-1",
    )

    assert run.id == "redaction-run-1"

    store = service._store  # noqa: SLF001
    assert isinstance(store, _FakeRedactionStore)
    assert len(store.replaced_rows) >= 1
    assert any(
        row.get("category") == "EMAIL" and row.get("decision_status") == "AUTO_APPLIED"
        for row in store.replaced_rows
    )
    assert any(row.get("decision_status") == "NEEDS_REVIEW" for row in store.replaced_rows)
    assert any(
        isinstance(row.get("token_refs_json"), list) and len(row.get("token_refs_json") or []) > 0
        for row in store.replaced_rows
    )
