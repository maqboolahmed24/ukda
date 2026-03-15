from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

import pytest
from fastapi.testclient import TestClient

from app.audit.service import get_audit_service
from app.auth.dependencies import require_authenticated_user
from app.auth.models import SessionPrincipal
from app.documents.governance import (
    GovernanceReadinessProjectionRecord,
    GovernanceRunSummaryRecord,
    LedgerVerificationRunRecord,
    RedactionEvidenceLedgerRecord,
    RedactionManifestRecord,
)
from app.documents.models import DocumentRecord
from app.documents.service import (
    DocumentGovernanceAccessDeniedError,
    DocumentGovernanceEventSnapshot,
    DocumentGovernanceLedgerEntriesSnapshot,
    DocumentGovernanceLedgerSnapshot,
    DocumentGovernanceLedgerStatusSnapshot,
    DocumentGovernanceLedgerSummarySnapshot,
    DocumentGovernanceLedgerVerificationDetailSnapshot,
    DocumentGovernanceLedgerVerificationRunsSnapshot,
    DocumentGovernanceLedgerVerificationStatusSnapshot,
    DocumentGovernanceManifestEntriesSnapshot,
    DocumentGovernanceManifestHashSnapshot,
    DocumentGovernanceManifestSnapshot,
    DocumentGovernanceManifestStatusSnapshot,
    DocumentGovernanceOverviewSnapshot,
    DocumentGovernanceRunNotFoundError,
    DocumentGovernanceRunOverviewSnapshot,
    DocumentGovernanceRunsSnapshot,
    get_document_service,
)
from app.main import app

client = TestClient(app)


class SpyAuditService:
    def __init__(self) -> None:
        self.recorded: list[dict[str, object]] = []

    def record_event_best_effort(self, **kwargs):  # type: ignore[no-untyped-def]
        self.recorded.append(kwargs)
        return None


class FakeDocumentService:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.document = DocumentRecord(
            id="doc-1",
            project_id="project-1",
            original_filename="governance-fixture.pdf",
            stored_filename="controlled/raw/project-1/doc-1/original.bin",
            content_type_detected="application/pdf",
            bytes=1024,
            sha256="a" * 64,
            page_count=2,
            status="READY",
            created_by="user-lead",
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(hours=1),
        )
        self.run = GovernanceRunSummaryRecord(
            run_id="run-1",
            project_id="project-1",
            document_id="doc-1",
            run_status="SUCCEEDED",
            review_status="APPROVED",
            approved_snapshot_key="controlled/derived/project-1/doc-1/redaction/run-1/approved.json",
            approved_snapshot_sha256="b" * 64,
            run_output_status="READY",
            run_output_manifest_sha256="c" * 64,
            run_created_at=now - timedelta(days=1),
            run_finished_at=now - timedelta(days=1, minutes=-10),
            readiness_status="READY",
            generation_status="IDLE",
            ready_manifest_id="manifest-1",
            ready_ledger_id="ledger-1",
            latest_manifest_sha256="d" * 64,
            latest_ledger_sha256="f" * 64,
            ledger_verification_status="VALID",
            ready_at=now - timedelta(minutes=18),
            last_error_code=None,
            updated_at=now - timedelta(minutes=5),
        )
        self.readiness = GovernanceReadinessProjectionRecord(
            run_id="run-1",
            project_id="project-1",
            document_id="doc-1",
            status="READY",
            generation_status="IDLE",
            manifest_id="manifest-1",
            ledger_id="ledger-1",
            last_ledger_verification_run_id="verify-1",
            last_manifest_sha256="d" * 64,
            last_ledger_sha256="f" * 64,
            ledger_verification_status="VALID",
            ledger_verified_at=now - timedelta(minutes=19),
            ready_at=now - timedelta(minutes=18),
            last_error_code=None,
            updated_at=now - timedelta(minutes=5),
        )
        self.manifest_attempt = RedactionManifestRecord(
            id="manifest-1",
            run_id="run-1",
            project_id="project-1",
            document_id="doc-1",
            source_review_snapshot_key="controlled/derived/project-1/doc-1/redaction/run-1/approved.json",
            source_review_snapshot_sha256="b" * 64,
            attempt_number=1,
            supersedes_manifest_id=None,
            superseded_by_manifest_id=None,
            status="SUCCEEDED",
            manifest_key="controlled/derived/project-1/doc-1/governance/run-1/manifest.v1.json",
            manifest_sha256="d" * 64,
            format_version=1,
            started_at=now - timedelta(minutes=40),
            finished_at=now - timedelta(minutes=35),
            canceled_by=None,
            canceled_at=None,
            failure_reason=None,
            created_by="user-reviewer",
            created_at=now - timedelta(minutes=35),
        )
        self.ledger_attempt = RedactionEvidenceLedgerRecord(
            id="ledger-1",
            run_id="run-1",
            project_id="project-1",
            document_id="doc-1",
            source_review_snapshot_key="controlled/derived/project-1/doc-1/redaction/run-1/approved.json",
            source_review_snapshot_sha256="b" * 64,
            attempt_number=1,
            supersedes_ledger_id=None,
            superseded_by_ledger_id=None,
            status="SUCCEEDED",
            ledger_key="controlled/derived/project-1/doc-1/governance/run-1/ledger/f.json",
            ledger_sha256="f" * 64,
            hash_chain_version="v1",
            started_at=now - timedelta(minutes=31),
            finished_at=now - timedelta(minutes=30),
            canceled_by=None,
            canceled_at=None,
            failure_reason=None,
            created_by="user-reviewer",
            created_at=now - timedelta(minutes=30),
        )
        self._event_time = now - timedelta(minutes=20)
        self.manifest_payload: dict[str, object] = {
            "manifestSchemaVersion": 1,
            "runId": "run-1",
            "internalOnly": True,
            "exportApproved": False,
            "exportApprovalStatus": "NOT_EXPORT_APPROVED",
            "entries": [
                {
                    "entryId": "finding-1",
                    "appliedAction": "MASK",
                    "category": "EMAIL",
                    "pageId": "page-1",
                    "pageIndex": 1,
                    "lineId": "line-1",
                    "locationRef": {"spanStart": 0, "spanEnd": 12},
                    "basisPrimary": "NER",
                    "confidence": 0.97,
                    "secondaryBasisSummary": {"summaryMode": "COMPACT_SCREENING_SAFE"},
                    "finalDecisionState": "APPROVED",
                    "reviewState": "APPROVED",
                    "policySnapshotHash": "policy-hash-1",
                    "policyId": "policy-main",
                    "policyFamilyId": "family-main",
                    "policyVersion": "v1",
                    "decisionTimestamp": now.isoformat(),
                    "decisionBy": "user-reviewer",
                    "decisionEtag": "etag-1",
                }
            ],
        }
        self.ledger_payload: dict[str, object] = {
            "ledgerSchemaVersion": 1,
            "ledgerKind": "CONTROLLED_REDACTION_EVIDENCE_LEDGER",
            "runId": "run-1",
            "approvedSnapshotSha256": "b" * 64,
            "hashChainVersion": "v1",
            "internalOnly": True,
            "rowCount": 1,
            "headHash": "f" * 64,
            "rows": [
                {
                    "rowId": "finding-1:1",
                    "rowIndex": 1,
                    "findingId": "finding-1",
                    "pageId": "page-1",
                    "pageIndex": 1,
                    "lineId": "line-1",
                    "category": "EMAIL",
                    "actionType": "MASK",
                    "beforeTextRef": {"lineId": "line-1", "spanStart": 0, "spanEnd": 12},
                    "afterTextRef": {"actionType": "MASK", "redactionState": "REDACTED_REFERENCE"},
                    "detectorEvidence": {
                        "basisPrimary": "NER",
                        "basisSecondaryJson": {"signal": "rule-email"},
                    },
                    "assistExplanationKey": "assist/key-1",
                    "assistExplanationSha256": "e" * 64,
                    "actorUserId": "user-reviewer",
                    "decisionTimestamp": now.isoformat(),
                    "overrideReason": None,
                    "finalDecisionState": "APPROVED",
                    "policySnapshotHash": "policy-hash-1",
                    "policyId": "policy-main",
                    "policyFamilyId": "family-main",
                    "policyVersion": "v1",
                    "prevHash": "GENESIS",
                    "rowHash": "f" * 64,
                }
            ],
        }
        self.verification_attempt = LedgerVerificationRunRecord(
            id="verify-1",
            run_id="run-1",
            attempt_number=1,
            supersedes_verification_run_id=None,
            superseded_by_verification_run_id=None,
            status="SUCCEEDED",
            verification_result="VALID",
            result_json={
                "isValid": True,
                "detail": "VALID",
                "rowCount": 1,
                "checkedRows": 1,
                "ledgerSha256": "f" * 64,
            },
            started_at=now - timedelta(minutes=20),
            finished_at=now - timedelta(minutes=19),
            canceled_by=None,
            canceled_at=None,
            failure_reason=None,
            created_by="user-admin",
            created_at=now - timedelta(minutes=20),
        )

    @staticmethod
    def _resolve_role(current_user: SessionPrincipal) -> str:
        roles = set(current_user.platform_roles)
        if "ADMIN" in roles:
            return "ADMIN"
        if "AUDITOR" in roles:
            return "AUDITOR"
        if current_user.user_id == "user-lead":
            return "PROJECT_LEAD"
        if current_user.user_id == "user-reviewer":
            return "REVIEWER"
        return "RESEARCHER"

    def _require_governance_view(
        self, *, current_user: SessionPrincipal, project_id: str, document_id: str, run_id: str | None
    ) -> str:
        if project_id != self.document.project_id or document_id != self.document.id:
            raise DocumentGovernanceRunNotFoundError("Document not found in project scope.")
        if run_id is not None and run_id != self.run.run_id:
            raise DocumentGovernanceRunNotFoundError("Governance run was not found in project scope.")
        role = self._resolve_role(current_user)
        if role in {"PROJECT_LEAD", "REVIEWER", "ADMIN", "AUDITOR"}:
            return role
        raise DocumentGovernanceAccessDeniedError(
            "Current role cannot access governance routes in this project."
        )

    def _require_governance_ledger_view(
        self, *, current_user: SessionPrincipal, project_id: str, document_id: str, run_id: str
    ) -> None:
        role = self._require_governance_view(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if role not in {"ADMIN", "AUDITOR"}:
            raise DocumentGovernanceAccessDeniedError(
                "Current role cannot access controlled evidence-ledger routes."
            )

    def get_governance_overview(
        self, *, current_user: SessionPrincipal, project_id: str, document_id: str
    ) -> DocumentGovernanceOverviewSnapshot:
        _ = self._require_governance_view(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=None,
        )
        return DocumentGovernanceOverviewSnapshot(
            document=self.document,
            active_run_id=self.run.run_id,
            total_runs=1,
            approved_runs=1,
            ready_runs=0,
            pending_runs=1,
            failed_runs=0,
            latest_run_id=self.run.run_id,
            latest_ready_run_id=None,
            latest_run=self.run,
            latest_ready_run=None,
        )

    def list_governance_runs(
        self, *, current_user: SessionPrincipal, project_id: str, document_id: str
    ) -> DocumentGovernanceRunsSnapshot:
        _ = self._require_governance_view(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=None,
        )
        return DocumentGovernanceRunsSnapshot(
            document=self.document,
            active_run_id=self.run.run_id,
            runs=(self.run,),
        )

    def get_governance_run_overview(
        self, *, current_user: SessionPrincipal, project_id: str, document_id: str, run_id: str
    ) -> DocumentGovernanceRunOverviewSnapshot:
        _ = self._require_governance_view(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        return DocumentGovernanceRunOverviewSnapshot(
            document=self.document,
            active_run_id=self.run.run_id,
            run=self.run,
            readiness=self.readiness,
            manifest_attempts=(self.manifest_attempt,),
            ledger_attempts=(self.ledger_attempt,),
        )

    def list_governance_run_events(
        self, *, current_user: SessionPrincipal, project_id: str, document_id: str, run_id: str
    ) -> tuple[DocumentGovernanceEventSnapshot, ...]:
        role = self._require_governance_view(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        ledger_reason = (
            "Raw ledger payload digest chain started."
            if role in {"ADMIN", "AUDITOR"}
            else "Controlled ledger transition recorded."
        )
        return (
            DocumentGovernanceEventSnapshot(
                id="event-1",
                run_id=run_id,
                event_type="RUN_CREATED",
                actor_user_id="user-reviewer",
                from_status=None,
                to_status="PENDING",
                reason="Governance scaffold initialized.",
                created_at=self._event_time - timedelta(minutes=2),
                screening_safe=True,
            ),
            DocumentGovernanceEventSnapshot(
                id="event-2",
                run_id=run_id,
                event_type="LEDGER_STARTED",
                actor_user_id="user-reviewer",
                from_status="IDLE",
                to_status="QUEUED",
                reason=ledger_reason,
                created_at=self._event_time,
                screening_safe=False,
            ),
        )

    def get_governance_run_manifest(
        self, *, current_user: SessionPrincipal, project_id: str, document_id: str, run_id: str
    ) -> DocumentGovernanceManifestSnapshot:
        overview = self.get_governance_run_overview(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        return DocumentGovernanceManifestSnapshot(
            overview=overview,
            latest_attempt=self.manifest_attempt,
            manifest_payload=self.manifest_payload,
            stream_sha256=self.manifest_attempt.manifest_sha256,
            hash_matches=True,
            internal_only=True,
            export_approved=False,
            not_export_approved=True,
        )

    def get_governance_run_manifest_status(
        self, *, current_user: SessionPrincipal, project_id: str, document_id: str, run_id: str
    ) -> DocumentGovernanceManifestStatusSnapshot:
        _ = self._require_governance_view(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        return DocumentGovernanceManifestStatusSnapshot(
            run_id=run_id,
            status="SUCCEEDED",
            latest_attempt=self.manifest_attempt,
            attempt_count=1,
            ready_manifest_id=self.manifest_attempt.id,
            latest_manifest_sha256=self.manifest_attempt.manifest_sha256,
            generation_status=self.readiness.generation_status,
            readiness_status=self.readiness.status,
            updated_at=self.readiness.updated_at,
        )

    def list_governance_run_manifest_entries(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        category: str | None = None,
        page: int | None = None,
        review_state: str | None = None,
        from_timestamp: datetime | None = None,
        to_timestamp: datetime | None = None,
        cursor: int = 0,
        limit: int = 100,
    ) -> DocumentGovernanceManifestEntriesSnapshot:
        _ = self._require_governance_view(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        del category, page, review_state, from_timestamp, to_timestamp
        items = tuple(self.manifest_payload.get("entries", []))[cursor : cursor + limit]
        next_cursor = cursor + limit if cursor + limit < len(self.manifest_payload["entries"]) else None
        return DocumentGovernanceManifestEntriesSnapshot(
            run_id=run_id,
            status="SUCCEEDED",
            manifest_id=self.manifest_attempt.id,
            manifest_sha256=self.manifest_attempt.manifest_sha256,
            source_review_snapshot_sha256=self.manifest_attempt.source_review_snapshot_sha256,
            items=tuple(dict(item) for item in items),
            next_cursor=next_cursor,
            total_count=len(self.manifest_payload["entries"]),
            internal_only=True,
            export_approved=False,
            not_export_approved=True,
        )

    def get_governance_run_manifest_hash(
        self, *, current_user: SessionPrincipal, project_id: str, document_id: str, run_id: str
    ) -> DocumentGovernanceManifestHashSnapshot:
        _ = self._require_governance_view(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        return DocumentGovernanceManifestHashSnapshot(
            run_id=run_id,
            status="SUCCEEDED",
            manifest_id=self.manifest_attempt.id,
            manifest_sha256=self.manifest_attempt.manifest_sha256,
            stream_sha256=self.manifest_attempt.manifest_sha256,
            hash_matches=True,
            internal_only=True,
            export_approved=False,
            not_export_approved=True,
        )

    def get_governance_run_ledger(
        self, *, current_user: SessionPrincipal, project_id: str, document_id: str, run_id: str
    ) -> DocumentGovernanceLedgerSnapshot:
        self._require_governance_ledger_view(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        overview = self.get_governance_run_overview(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        return DocumentGovernanceLedgerSnapshot(
            overview=overview,
            latest_attempt=self.ledger_attempt,
            ledger_payload=self.ledger_payload,
            stream_sha256=self.ledger_attempt.ledger_sha256,
            hash_matches=True,
            internal_only=True,
        )

    def get_governance_run_ledger_status(
        self, *, current_user: SessionPrincipal, project_id: str, document_id: str, run_id: str
    ) -> DocumentGovernanceLedgerStatusSnapshot:
        self._require_governance_ledger_view(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        return DocumentGovernanceLedgerStatusSnapshot(
            run_id=run_id,
            status="SUCCEEDED",
            latest_attempt=self.ledger_attempt,
            attempt_count=1,
            ready_ledger_id=self.ledger_attempt.id,
            latest_ledger_sha256=self.ledger_attempt.ledger_sha256,
            generation_status=self.readiness.generation_status,
            readiness_status=self.readiness.status,
            ledger_verification_status=self.readiness.ledger_verification_status,
            updated_at=self.readiness.updated_at,
        )

    def list_governance_run_ledger_entries(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        view: Literal["list", "timeline"] = "list",
        cursor: int = 0,
        limit: int = 100,
    ) -> DocumentGovernanceLedgerEntriesSnapshot:
        self._require_governance_ledger_view(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        rows = list(self.ledger_payload["rows"])
        projected = rows if view == "list" else list(reversed(rows))
        items = tuple(projected[cursor : cursor + limit])
        next_cursor = cursor + limit if cursor + limit < len(projected) else None
        return DocumentGovernanceLedgerEntriesSnapshot(
            run_id=run_id,
            status="SUCCEEDED",
            view=view,
            ledger_id=self.ledger_attempt.id,
            ledger_sha256=self.ledger_attempt.ledger_sha256,
            hash_chain_version=self.ledger_attempt.hash_chain_version,
            total_count=len(projected),
            next_cursor=next_cursor,
            verification_status="VALID",
            items=tuple(dict(item) for item in items),
        )

    def get_governance_run_ledger_summary(
        self, *, current_user: SessionPrincipal, project_id: str, document_id: str, run_id: str
    ) -> DocumentGovernanceLedgerSummarySnapshot:
        self._require_governance_ledger_view(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        return DocumentGovernanceLedgerSummarySnapshot(
            run_id=run_id,
            status="SUCCEEDED",
            ledger_id=self.ledger_attempt.id,
            ledger_sha256=self.ledger_attempt.ledger_sha256,
            hash_chain_version=self.ledger_attempt.hash_chain_version,
            row_count=1,
            hash_chain_head=self.ledger_payload["headHash"],  # type: ignore[index]
            hash_chain_valid=True,
            verification_status="VALID",
            category_counts={"EMAIL": 1},
            action_counts={"MASK": 1},
            override_count=0,
            assist_reference_count=1,
            internal_only=True,
        )

    def request_governance_run_ledger_verification(
        self, *, current_user: SessionPrincipal, project_id: str, document_id: str, run_id: str
    ) -> DocumentGovernanceLedgerVerificationDetailSnapshot:
        role = self._resolve_role(current_user)
        if role != "ADMIN":
            raise DocumentGovernanceAccessDeniedError(
                "Current role cannot trigger ledger verification mutations."
            )
        return DocumentGovernanceLedgerVerificationDetailSnapshot(
            run_id=run_id,
            verification_status="VALID",
            attempt=self.verification_attempt,
        )

    def get_governance_run_ledger_verification_status(
        self, *, current_user: SessionPrincipal, project_id: str, document_id: str, run_id: str
    ) -> DocumentGovernanceLedgerVerificationStatusSnapshot:
        self._require_governance_ledger_view(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        return DocumentGovernanceLedgerVerificationStatusSnapshot(
            run_id=run_id,
            verification_status="VALID",
            attempt_count=1,
            latest_attempt=self.verification_attempt,
            latest_completed_attempt=self.verification_attempt,
            ready_ledger_id=self.ledger_attempt.id,
            latest_ledger_sha256=self.ledger_attempt.ledger_sha256,
            last_verified_at=self.verification_attempt.finished_at,
        )

    def list_governance_run_ledger_verification_runs(
        self, *, current_user: SessionPrincipal, project_id: str, document_id: str, run_id: str
    ) -> DocumentGovernanceLedgerVerificationRunsSnapshot:
        self._require_governance_ledger_view(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        return DocumentGovernanceLedgerVerificationRunsSnapshot(
            run_id=run_id,
            verification_status="VALID",
            items=(self.verification_attempt,),
        )

    def get_governance_run_ledger_verification_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        verification_run_id: str,
    ) -> DocumentGovernanceLedgerVerificationDetailSnapshot:
        self._require_governance_ledger_view(
            current_user=current_user,
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        if verification_run_id != self.verification_attempt.id:
            raise DocumentGovernanceRunNotFoundError("Governance run was not found in project scope.")
        return DocumentGovernanceLedgerVerificationDetailSnapshot(
            run_id=run_id,
            verification_status="VALID",
            attempt=self.verification_attempt,
        )

    def cancel_governance_run_ledger_verification_run(
        self,
        *,
        current_user: SessionPrincipal,
        project_id: str,
        document_id: str,
        run_id: str,
        verification_run_id: str,
    ) -> DocumentGovernanceLedgerVerificationDetailSnapshot:
        role = self._resolve_role(current_user)
        if role != "ADMIN":
            raise DocumentGovernanceAccessDeniedError(
                "Current role cannot trigger ledger verification mutations."
            )
        if verification_run_id != self.verification_attempt.id:
            raise DocumentGovernanceRunNotFoundError("Governance run was not found in project scope.")
        canceled = LedgerVerificationRunRecord(
            **{
                **self.verification_attempt.__dict__,
                "status": "CANCELED",
                "verification_result": None,
                "result_json": None,
            }
        )
        return DocumentGovernanceLedgerVerificationDetailSnapshot(
            run_id=run_id,
            verification_status="PENDING",
            attempt=canceled,
        )


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:
    yield
    app.dependency_overrides.clear()


def _principal(
    *,
    user_id: str = "user-lead",
    roles: tuple[Literal["ADMIN", "AUDITOR"], ...] = (),
) -> SessionPrincipal:
    return SessionPrincipal(
        session_id="session-governance",
        auth_source="bearer",
        user_id=user_id,
        oidc_sub=f"oidc-{user_id}",
        email=f"{user_id}@test.local",
        display_name="Governance User",
        platform_roles=roles,
        issued_at=datetime.now(UTC) - timedelta(minutes=5),
        expires_at=datetime.now(UTC) + timedelta(minutes=55),
        csrf_token="csrf-governance",
    )


def test_governance_overview_and_runs_routes_return_data() -> None:
    fake_service = FakeDocumentService()
    spy = SpyAuditService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(user_id="user-lead")
    app.dependency_overrides[get_document_service] = lambda: fake_service
    app.dependency_overrides[get_audit_service] = lambda: spy

    overview_response = client.get("/projects/project-1/documents/doc-1/governance/overview")
    runs_response = client.get("/projects/project-1/documents/doc-1/governance/runs")

    assert overview_response.status_code == 200
    assert runs_response.status_code == 200

    overview_payload = overview_response.json()
    runs_payload = runs_response.json()
    assert overview_payload["activeRunId"] == "run-1"
    assert overview_payload["totalRuns"] == 1
    assert runs_payload["items"][0]["runId"] == "run-1"
    assert any(entry.get("event_type") == "GOVERNANCE_OVERVIEW_VIEWED" for entry in spy.recorded)
    assert any(entry.get("event_type") == "GOVERNANCE_RUNS_VIEWED" for entry in spy.recorded)


def test_governance_run_routes_return_manifest_and_masked_events_for_reviewer() -> None:
    fake_service = FakeDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="user-reviewer"
    )
    app.dependency_overrides[get_document_service] = lambda: fake_service
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()

    run_overview_response = client.get(
        "/projects/project-1/documents/doc-1/governance/runs/run-1/overview"
    )
    events_response = client.get(
        "/projects/project-1/documents/doc-1/governance/runs/run-1/events"
    )
    manifest_response = client.get(
        "/projects/project-1/documents/doc-1/governance/runs/run-1/manifest"
    )
    manifest_status_response = client.get(
        "/projects/project-1/documents/doc-1/governance/runs/run-1/manifest/status"
    )
    manifest_entries_response = client.get(
        "/projects/project-1/documents/doc-1/governance/runs/run-1/manifest/entries?limit=50"
    )
    manifest_hash_response = client.get(
        "/projects/project-1/documents/doc-1/governance/runs/run-1/manifest/hash"
    )

    assert run_overview_response.status_code == 200
    assert events_response.status_code == 200
    assert manifest_response.status_code == 200
    assert manifest_status_response.status_code == 200
    assert manifest_entries_response.status_code == 200
    assert manifest_hash_response.status_code == 200

    events_payload = events_response.json()
    manifest_payload = manifest_response.json()
    entries_payload = manifest_entries_response.json()
    hash_payload = manifest_hash_response.json()
    ledger_event = next(item for item in events_payload["items"] if item["eventType"] == "LEDGER_STARTED")
    assert ledger_event["screeningSafe"] is False
    assert ledger_event["reason"] == "Controlled ledger transition recorded."
    assert manifest_payload["internalOnly"] is True
    assert manifest_payload["notExportApproved"] is True
    assert isinstance(manifest_payload["manifestJson"], dict)
    assert entries_payload["items"][0]["entryId"] == "finding-1"
    assert hash_payload["hashMatches"] is True


def test_governance_ledger_routes_require_admin_or_auditor() -> None:
    fake_service = FakeDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="user-reviewer"
    )
    app.dependency_overrides[get_document_service] = lambda: fake_service
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()

    ledger_response = client.get("/projects/project-1/documents/doc-1/governance/runs/run-1/ledger")
    ledger_status_response = client.get(
        "/projects/project-1/documents/doc-1/governance/runs/run-1/ledger/status"
    )

    assert ledger_response.status_code == 403
    assert ledger_status_response.status_code == 403


def test_governance_ledger_routes_allow_auditor() -> None:
    fake_service = FakeDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="user-auditor",
        roles=("AUDITOR",),
    )
    app.dependency_overrides[get_document_service] = lambda: fake_service
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()

    ledger_response = client.get("/projects/project-1/documents/doc-1/governance/runs/run-1/ledger")
    ledger_status_response = client.get(
        "/projects/project-1/documents/doc-1/governance/runs/run-1/ledger/status"
    )
    events_response = client.get("/projects/project-1/documents/doc-1/governance/runs/run-1/events")

    assert ledger_response.status_code == 200
    assert ledger_status_response.status_code == 200
    assert ledger_status_response.json()["status"] == "SUCCEEDED"
    assert isinstance(ledger_response.json()["ledgerJson"], dict)
    ledger_event = next(
        item for item in events_response.json()["items"] if item["eventType"] == "LEDGER_STARTED"
    )
    assert ledger_event["reason"] == "Raw ledger payload digest chain started."


def test_governance_ledger_entries_summary_and_verify_reads_allow_auditor() -> None:
    fake_service = FakeDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="user-auditor",
        roles=("AUDITOR",),
    )
    app.dependency_overrides[get_document_service] = lambda: fake_service
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()

    entries_response = client.get(
        "/projects/project-1/documents/doc-1/governance/runs/run-1/ledger/entries?view=timeline&limit=10"
    )
    summary_response = client.get(
        "/projects/project-1/documents/doc-1/governance/runs/run-1/ledger/summary"
    )
    verify_status_response = client.get(
        "/projects/project-1/documents/doc-1/governance/runs/run-1/ledger/verify/status"
    )
    verify_runs_response = client.get(
        "/projects/project-1/documents/doc-1/governance/runs/run-1/ledger/verify/runs"
    )
    verify_detail_response = client.get(
        "/projects/project-1/documents/doc-1/governance/runs/run-1/ledger/verify/verify-1"
    )
    verify_detail_status_response = client.get(
        "/projects/project-1/documents/doc-1/governance/runs/run-1/ledger/verify/verify-1/status"
    )
    verify_mutation_response = client.post(
        "/projects/project-1/documents/doc-1/governance/runs/run-1/ledger/verify"
    )

    assert entries_response.status_code == 200
    assert summary_response.status_code == 200
    assert verify_status_response.status_code == 200
    assert verify_runs_response.status_code == 200
    assert verify_detail_response.status_code == 200
    assert verify_detail_status_response.status_code == 200
    assert verify_mutation_response.status_code == 403

    assert entries_response.json()["view"] == "timeline"
    assert entries_response.json()["items"][0]["rowId"] == "finding-1:1"
    assert summary_response.json()["hashChainValid"] is True
    assert verify_status_response.json()["verificationStatus"] == "VALID"
    assert verify_runs_response.json()["items"][0]["id"] == "verify-1"
    assert verify_detail_response.json()["attempt"]["status"] == "SUCCEEDED"


def test_governance_ledger_verify_mutations_allow_admin() -> None:
    fake_service = FakeDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="user-admin",
        roles=("ADMIN",),
    )
    app.dependency_overrides[get_document_service] = lambda: fake_service
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()

    verify_mutation_response = client.post(
        "/projects/project-1/documents/doc-1/governance/runs/run-1/ledger/verify"
    )
    cancel_mutation_response = client.post(
        "/projects/project-1/documents/doc-1/governance/runs/run-1/ledger/verify/verify-1/cancel"
    )

    assert verify_mutation_response.status_code == 200
    assert verify_mutation_response.json()["attempt"]["id"] == "verify-1"
    assert cancel_mutation_response.status_code == 200
    assert cancel_mutation_response.json()["attempt"]["status"] == "CANCELED"


def test_governance_overview_denies_researcher() -> None:
    fake_service = FakeDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="user-researcher"
    )
    app.dependency_overrides[get_document_service] = lambda: fake_service
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()

    response = client.get("/projects/project-1/documents/doc-1/governance/overview")

    assert response.status_code == 403


def test_governance_manifest_entries_and_hash_deny_researcher() -> None:
    fake_service = FakeDocumentService()
    app.dependency_overrides[require_authenticated_user] = lambda: _principal(
        user_id="user-researcher"
    )
    app.dependency_overrides[get_document_service] = lambda: fake_service
    app.dependency_overrides[get_audit_service] = lambda: SpyAuditService()

    entries_response = client.get(
        "/projects/project-1/documents/doc-1/governance/runs/run-1/manifest/entries"
    )
    hash_response = client.get(
        "/projects/project-1/documents/doc-1/governance/runs/run-1/manifest/hash"
    )

    assert entries_response.status_code == 403
    assert hash_response.status_code == 403
