import Link from "next/link";
import { redirect } from "next/navigation";
import { SectionState } from "@ukde/ui/primitives";

import {
  getExportRequest,
  getExportRequestReceipt,
  listExportRequestReceipts,
  getExportRequestReleasePack,
  getExportRequestStatus,
  getExportRequestValidationSummary
} from "../../../../../../lib/exports";
import { getProjectSummary } from "../../../../../../lib/projects";

export const dynamic = "force-dynamic";

export default async function ProjectExportRequestDetailPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string; exportRequestId: string }>;
}>) {
  const { projectId, exportRequestId } = await params;
  const [
    projectResult,
    requestResult,
    statusResult,
    releasePackResult,
    validationSummaryResult,
    receiptResult,
    receiptsResult
  ] =
    await Promise.all([
      getProjectSummary(projectId),
      getExportRequest(projectId, exportRequestId),
      getExportRequestStatus(projectId, exportRequestId),
      getExportRequestReleasePack(projectId, exportRequestId),
      getExportRequestValidationSummary(projectId, exportRequestId),
      getExportRequestReceipt(projectId, exportRequestId),
      listExportRequestReceipts(projectId, exportRequestId)
    ]);

  if (!projectResult.ok || !projectResult.data) {
    redirect("/projects?error=member-route");
  }

  if (!requestResult.ok || !requestResult.data) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Request not available"
            description={requestResult.detail ?? "Unknown failure"}
          />
          <div className="buttonRow">
            <Link
              className="secondaryButton"
              href={`/projects/${projectId}/export-requests`}
            >
              Back to history
            </Link>
          </div>
        </section>
      </main>
    );
  }

  const request = requestResult.data;
  const statusPayload =
    statusResult.ok && statusResult.data ? statusResult.data : null;
  const releasePackPayload =
    releasePackResult.ok && releasePackResult.data ? releasePackResult.data : null;
  const validationSummaryPayload =
    validationSummaryResult.ok && validationSummaryResult.data
      ? validationSummaryResult.data
      : null;
  const receiptPayload = receiptResult.ok && receiptResult.data ? receiptResult.data : null;
  const receiptHistory =
    receiptsResult.ok && receiptsResult.data ? receiptsResult.data.items : [];
  const isExportBlocked = request.status !== "APPROVED" && request.status !== "EXPORTED";
  const isAwaitingGateway = request.status === "APPROVED" && !receiptPayload;
  const isTerminalLocked = ["APPROVED", "EXPORTED", "REJECTED", "RETURNED"].includes(
    request.status
  );

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <h1 className="sectionTitle">Export request detail</h1>
        <p className="ukde-muted">
          Request <code>{request.id}</code> revision {request.requestRevision}
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-requests`}
          >
            Back to history
          </Link>
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-requests/${request.id}/events`}
          >
            View events
          </Link>
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-requests/${request.id}/reviews`}
          >
            View reviews
          </Link>
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-requests/${request.id}/provenance`}
          >
            View provenance
          </Link>
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-requests/${request.id}/bundles`}
          >
            View bundles
          </Link>
          {request.status === "RETURNED" ? (
            <Link
              className="projectPrimaryButton"
              href={`/projects/${projectId}/export-requests/new?candidateId=${encodeURIComponent(request.candidateSnapshotId)}&supersedesExportRequestId=${encodeURIComponent(request.id)}`}
            >
              Resubmit as successor
            </Link>
          ) : null}
        </div>
      </section>

      <section className="sectionCard ukde-panel">
        <div className="detailGrid">
          <div>
            <h2 className="sectionTitle">Status</h2>
            <p className="ukde-muted">{request.status}</p>
            <p className="ukde-muted">Risk: {request.riskClassification}</p>
            <p className="ukde-muted">Review path: {request.reviewPath}</p>
            <p className="ukde-muted">
              Requires second review: {request.requiresSecondReview ? "Yes" : "No"}
            </p>
            <p className="ukde-muted">
              Submitted: {new Date(request.submittedAt).toLocaleString()}
            </p>
          </div>
          <div>
            <h2 className="sectionTitle">Lineage</h2>
            <p className="ukde-muted">
              Candidate snapshot <code>{request.candidateSnapshotId}</code>
            </p>
            <p className="ukde-muted">
              Supersedes request:{" "}
              {request.supersedesExportRequestId ?? "None"}
            </p>
            <p className="ukde-muted">
              Superseded by: {request.supersededByExportRequestId ?? "None"}
            </p>
            <p className="ukde-muted">
              Release-pack hash <code>{request.releasePackSha256}</code>
            </p>
          </div>
        </div>
      </section>

      {!statusPayload ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Status projection unavailable"
            description={statusResult.detail ?? "Unable to load status projection."}
          />
        </section>
      ) : (
        <section className="sectionCard ukde-panel">
          <h2 className="sectionTitle">Request projection</h2>
          <p className="ukde-muted">
            Queue activity:{" "}
            {statusPayload.lastQueueActivityAt
              ? new Date(statusPayload.lastQueueActivityAt).toLocaleString()
              : "Not started"}
          </p>
          <p className="ukde-muted">
            SLA due:{" "}
            {statusPayload.slaDueAt
              ? new Date(statusPayload.slaDueAt).toLocaleString()
              : "Not scheduled"}
          </p>
          <p className="ukde-muted">
            Final decision at:{" "}
            {statusPayload.finalDecisionAt
              ? new Date(statusPayload.finalDecisionAt).toLocaleString()
              : "Pending"}
          </p>
          <p className="ukde-muted">
            Final decision by: {statusPayload.finalDecisionBy ?? "Pending"}
          </p>
          <p className="ukde-muted">
            Final decision reason: {statusPayload.finalDecisionReason ?? "None"}
          </p>
          <p className="ukde-muted">
            Final return comment: {statusPayload.finalReturnComment ?? "None"}
          </p>
        </section>
      )}

      <section className="sectionCard ukde-panel">
        <h2 className="sectionTitle">Decision and lock state</h2>
        {isTerminalLocked ? (
          <SectionState
            kind="degraded"
            title="This request revision is locked"
            description="Terminal review decisions are immutable. Any further changes require a canonical successor resubmission."
          />
        ) : (
          <SectionState
            kind="loading"
            title="This request revision is still mutable"
            description="Review stage mutations continue through optimistic-lock actions on the active required stage."
          />
        )}
        <p className="ukde-muted">
          Final review id: {request.finalReviewId ?? "Pending"}
        </p>
        <p className="ukde-muted">
          Final decision by: {request.finalDecisionBy ?? "Pending"}
        </p>
        <p className="ukde-muted">
          Final decision reason: {request.finalDecisionReason ?? "None"}
        </p>
        <p className="ukde-muted">
          Final return comment: {request.finalReturnComment ?? "None"}
        </p>
      </section>

      {!releasePackPayload ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Frozen release pack unavailable"
            description={releasePackResult.detail ?? "Unable to load frozen release pack."}
          />
        </section>
      ) : (
        <section className="sectionCard ukde-panel">
          <h2 className="sectionTitle">Frozen release pack</h2>
          <p className="ukde-muted">
            Created at {new Date(releasePackPayload.releasePackCreatedAt).toLocaleString()}
          </p>
          <p className="ukde-muted">
            Hash <code>{releasePackPayload.releasePackSha256}</code>
          </p>
          <p className="ukde-muted">
            Key <code>{releasePackPayload.releasePackKey}</code>
          </p>
        </section>
      )}

      {!validationSummaryPayload ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Validation summary unavailable"
            description={
              validationSummaryResult.detail ??
              "Unable to load release-pack and audit-completeness validation."
            }
          />
        </section>
      ) : (
        <section className="sectionCard ukde-panel">
          <h2 className="sectionTitle">Validation summary</h2>
          <p className="ukde-muted">
            Checked {new Date(validationSummaryPayload.generatedAt).toLocaleString()}
          </p>
          <p className="ukde-muted">
            Request validity: {validationSummaryPayload.isValid ? "Valid" : "Invalid"}
          </p>
          <p className="ukde-muted">
            Release pack:{" "}
            {validationSummaryPayload.releasePack.passed
              ? "passed"
              : `${validationSummaryPayload.releasePack.issueCount} issue(s)`}
          </p>
          <p className="ukde-muted">
            Audit completeness:{" "}
            {validationSummaryPayload.auditCompleteness.passed
              ? "passed"
              : `${validationSummaryPayload.auditCompleteness.issueCount} issue(s)`}
          </p>
        </section>
      )}

      {isExportBlocked ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="disabled"
            title="External egress is blocked"
            description="Only approved requests can move through the export gateway. Direct download is intentionally unavailable."
          />
        </section>
      ) : null}

      {isAwaitingGateway ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="loading"
            title="Awaiting gateway delivery"
            description="This request is approved and queued for internal gateway receipt attachment."
          />
        </section>
      ) : null}

      {receiptPayload ? (
        <section className="sectionCard ukde-panel">
          <h2 className="sectionTitle">Gateway receipt</h2>
          <p className="ukde-muted">
            Receipt <code>{receiptPayload.id}</code> attempt {receiptPayload.attemptNumber}
          </p>
          <p className="ukde-muted">
            Exported at {new Date(receiptPayload.exportedAt).toLocaleString()}
          </p>
          <p className="ukde-muted">
            Receipt hash <code>{receiptPayload.receiptSha256}</code>
          </p>
          <p className="ukde-muted">
            Receipt reference <code>{receiptPayload.receiptKey}</code>
          </p>
          {receiptHistory.length > 0 ? (
            <table className="ukde-data-table">
              <thead>
                <tr>
                  <th>Attempt</th>
                  <th>Receipt</th>
                  <th>Exported</th>
                  <th>Superseded by</th>
                </tr>
              </thead>
              <tbody>
                {receiptHistory.map((item) => (
                  <tr key={item.id}>
                    <td>{item.attemptNumber}</td>
                    <td>
                      <code>{item.id}</code>
                    </td>
                    <td>{new Date(item.exportedAt).toLocaleString()}</td>
                    <td>{item.supersededByReceiptId ?? "Current"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </section>
      ) : null}
    </main>
  );
}
