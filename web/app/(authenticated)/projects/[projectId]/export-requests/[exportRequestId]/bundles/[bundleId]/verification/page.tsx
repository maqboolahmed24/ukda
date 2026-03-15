import Link from "next/link";
import { redirect } from "next/navigation";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { requireCurrentSession } from "../../../../../../../../../lib/auth/session";
import {
  cancelExportRequestBundleVerificationRun,
  getExportRequest,
  getExportRequestBundle,
  getExportRequestBundleVerification,
  getExportRequestBundleVerificationRun,
  getExportRequestBundleVerificationStatus,
  listExportRequestBundleVerificationRuns,
  startExportRequestBundleVerification
} from "../../../../../../../../../lib/exports";
import { getProjectSummary } from "../../../../../../../../../lib/projects";

export const dynamic = "force-dynamic";

function resolveStatusTone(
  status: "CANCELED" | "FAILED" | "PENDING" | "QUEUED" | "RUNNING" | "SUCCEEDED" | "VERIFIED"
): "danger" | "neutral" | "success" | "warning" {
  if (status === "SUCCEEDED" || status === "VERIFIED") {
    return "success";
  }
  if (status === "FAILED") {
    return "danger";
  }
  if (status === "CANCELED") {
    return "neutral";
  }
  return "warning";
}

function parseOptionalText(value: string | undefined): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function buildVerificationHref(
  projectId: string,
  exportRequestId: string,
  bundleId: string,
  options?: {
    error?: string;
    notice?: string;
    runId?: string;
  }
): string {
  const params = new URLSearchParams();
  if (options?.runId && options.runId.trim().length > 0) {
    params.set("runId", options.runId.trim());
  }
  if (options?.notice && options.notice.trim().length > 0) {
    params.set("notice", options.notice.trim());
  }
  if (options?.error && options.error.trim().length > 0) {
    params.set("error", options.error.trim());
  }
  const query = params.toString();
  const base = `/projects/${projectId}/export-requests/${exportRequestId}/bundles/${bundleId}/verification`;
  return query.length > 0 ? `${base}?${query}` : base;
}

function toFailureList(resultJson: Record<string, unknown> | null): string[] {
  if (!resultJson) {
    return [];
  }
  const failures = resultJson.failures;
  if (!Array.isArray(failures)) {
    return [];
  }
  return failures.filter((item): item is string => typeof item === "string");
}

function canCancel(status: string): boolean {
  return status === "QUEUED" || status === "RUNNING";
}

export default async function ExportRequestBundleVerificationPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; exportRequestId: string; bundleId: string }>;
  searchParams: Promise<{ error?: string; notice?: string; runId?: string }>;
}>) {
  const { projectId, exportRequestId, bundleId } = await params;
  const query = await searchParams;
  const session = await requireCurrentSession();
  const isAdmin = session.user.platformRoles.includes("ADMIN");
  const isAuditor = session.user.platformRoles.includes("AUDITOR");

  const selectedRunId = parseOptionalText(query.runId);
  const notice = parseOptionalText(query.notice);
  const error = parseOptionalText(query.error);

  const [
    projectResult,
    requestResult,
    bundleResult,
    verificationResult,
    statusResult,
    runsResult,
    selectedRunResult
  ] = await Promise.all([
    getProjectSummary(projectId),
    getExportRequest(projectId, exportRequestId),
    getExportRequestBundle(projectId, exportRequestId, bundleId),
    getExportRequestBundleVerification(projectId, exportRequestId, bundleId),
    getExportRequestBundleVerificationStatus(projectId, exportRequestId, bundleId),
    listExportRequestBundleVerificationRuns(projectId, exportRequestId, bundleId),
    selectedRunId
      ? getExportRequestBundleVerificationRun(
          projectId,
          exportRequestId,
          bundleId,
          selectedRunId
        )
      : Promise.resolve(null)
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
            title="Export request unavailable"
            description={requestResult.detail ?? "Request could not be loaded."}
          />
        </section>
      </main>
    );
  }

  if (!bundleResult.ok || !bundleResult.data) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Bundle unavailable"
            description={bundleResult.detail ?? "Bundle detail could not be loaded."}
          />
        </section>
      </main>
    );
  }

  if (!verificationResult.ok || !verificationResult.data || !statusResult.ok || !statusResult.data) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Verification details unavailable"
            description={
              verificationResult.detail ??
              statusResult.detail ??
              "Verification detail could not be loaded."
            }
          />
        </section>
      </main>
    );
  }

  const request = requestResult.data;
  const bundleDetail = bundleResult.data;
  const verification = verificationResult.data;
  const verificationStatus = statusResult.data;
  const runs = runsResult.ok && runsResult.data ? runsResult.data.items : [];
  const selectedRun =
    (selectedRunResult && selectedRunResult.ok && selectedRunResult.data
      ? selectedRunResult.data.verificationRun
      : null) ??
    verification.latestAttempt ??
    null;

  const provenanceArtifact = bundleDetail.artifact.provenanceProofArtifact;
  const proofArtifact =
    provenanceArtifact && typeof provenanceArtifact === "object"
      ? (provenanceArtifact as Record<string, unknown>)
      : null;
  const proofMerkle =
    proofArtifact?.merkle && typeof proofArtifact.merkle === "object"
      ? (proofArtifact.merkle as Record<string, unknown>)
      : null;
  const proofVerificationMaterial =
    bundleDetail.artifact.provenanceVerificationMaterial &&
    typeof bundleDetail.artifact.provenanceVerificationMaterial === "object"
      ? (bundleDetail.artifact.provenanceVerificationMaterial as Record<string, unknown>)
      : null;
  const proofRoot =
    typeof proofMerkle?.rootSha256 === "string" ? proofMerkle.rootSha256 : "Unavailable";

  async function triggerVerificationAction() {
    "use server";
    if (!isAdmin) {
      redirect(
        buildVerificationHref(projectId, exportRequestId, bundleId, {
          error: "admin_only"
        })
      );
    }
    const result = await startExportRequestBundleVerification(
      projectId,
      exportRequestId,
      bundleId
    );
    if (!result.ok || !result.data) {
      redirect(
        buildVerificationHref(projectId, exportRequestId, bundleId, {
          error: "verify_failed"
        })
      );
    }
    redirect(
      buildVerificationHref(projectId, exportRequestId, bundleId, {
        notice: "verify_requested",
        runId: result.data.verificationRun.id
      })
    );
  }

  async function cancelVerificationAction(formData: FormData) {
    "use server";
    if (!isAdmin) {
      redirect(
        buildVerificationHref(projectId, exportRequestId, bundleId, {
          error: "admin_only"
        })
      );
    }
    const runId = String(formData.get("runId") ?? "").trim();
    if (!runId) {
      redirect(
        buildVerificationHref(projectId, exportRequestId, bundleId, {
          error: "run_required"
        })
      );
    }
    const result = await cancelExportRequestBundleVerificationRun(
      projectId,
      exportRequestId,
      bundleId,
      runId
    );
    if (!result.ok || !result.data) {
      redirect(
        buildVerificationHref(projectId, exportRequestId, bundleId, {
          runId,
          error: "cancel_failed"
        })
      );
    }
    redirect(
      buildVerificationHref(projectId, exportRequestId, bundleId, {
        runId: result.data.verificationRun.id,
        notice: "run_canceled"
      })
    );
  }

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <h1 className="sectionTitle">Bundle verification</h1>
        <p className="ukde-muted">
          Request <code>{request.id}</code> | Bundle <code>{bundleId}</code>
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-requests/${request.id}/bundles/${bundleId}`}
          >
            Back to bundle
          </Link>
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-requests/${request.id}/bundles/${bundleId}/events`}
          >
            Bundle events
          </Link>
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-requests/${request.id}/bundles/${bundleId}/validation`}
          >
            Validation
          </Link>
        </div>
        {notice === "verify_requested" ? (
          <p className="ukde-muted">Verification request accepted.</p>
        ) : null}
        {notice === "run_canceled" ? (
          <p className="ukde-muted">Verification run canceled.</p>
        ) : null}
        {error ? (
          <p className="ukde-muted">Action error: {error.replaceAll("_", " ")}</p>
        ) : null}
      </section>

      <section className="sectionCard ukde-panel">
        <h2 className="sectionTitle">Verification status</h2>
        <div className="buttonRow" role="toolbar" aria-label="Bundle verification controls">
          <StatusChip tone={resolveStatusTone(verification.bundle.status)}>
            Bundle {verification.bundle.status}
          </StatusChip>
          <StatusChip
            tone={resolveStatusTone(
              verificationStatus.verificationProjection?.status ?? "PENDING"
            )}
          >
            Projection {verificationStatus.verificationProjection?.status ?? "PENDING"}
          </StatusChip>
          <StatusChip
            tone={resolveStatusTone(verificationStatus.latestAttempt?.status ?? "PENDING")}
          >
            Latest attempt {verificationStatus.latestAttempt?.status ?? "PENDING"}
          </StatusChip>
          {isAdmin ? (
            <form action={triggerVerificationAction}>
              <button className="secondaryButton" type="submit">
                Trigger verification
              </button>
            </form>
          ) : null}
        </div>
        {isAuditor ? <p className="ukde-muted">Read-only auditor mode.</p> : null}
      </section>

      <section className="sectionCard ukde-panel">
        <h2 className="sectionTitle">Proof material</h2>
        <p className="ukde-muted">
          Root hash: <code>{proofRoot}</code>
        </p>
        <p className="ukde-muted">
          Signature status:{" "}
          <strong>{String(selectedRun?.resultJson?.signatureStatus ?? "PENDING")}</strong>
        </p>
        <p className="ukde-muted">
          Verification material algorithm:{" "}
          <strong>
            {typeof proofVerificationMaterial?.publicKeyAlgorithm === "string"
              ? proofVerificationMaterial.publicKeyAlgorithm
              : "Unavailable"}
          </strong>
        </p>
        <p className="ukde-muted">
          Verification material key SHA-256:{" "}
          <code>
            {typeof proofVerificationMaterial?.publicKeySha256 === "string"
              ? proofVerificationMaterial.publicKeySha256
              : "Unavailable"}
          </code>
        </p>
      </section>

      {!runsResult.ok ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Verification history unavailable"
            description={runsResult.detail ?? "Verification attempts could not be listed."}
          />
        </section>
      ) : runs.length === 0 ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="loading"
            title="No verification attempts yet"
            description="Verification history appears once an ADMIN starts a verification run."
          />
        </section>
      ) : (
        <section className="sectionCard ukde-panel">
          <h2 className="sectionTitle">Verification history</h2>
          <div className="ukde-list">
            {runs.map((run) => (
              <div className="ukde-list-item" key={run.id}>
                <p className="ukde-muted">
                  Attempt {run.attemptNumber} <code>{run.id}</code>
                </p>
                <p className="ukde-muted">
                  Status <strong>{run.status}</strong> | Created{" "}
                  {new Date(run.createdAt).toLocaleString()}
                </p>
                <div className="buttonRow">
                  <Link
                    className="secondaryButton"
                    href={buildVerificationHref(projectId, exportRequestId, bundleId, {
                      runId: run.id
                    })}
                  >
                    Open run detail
                  </Link>
                  {isAdmin && canCancel(run.status) ? (
                    <form action={cancelVerificationAction}>
                      <input name="runId" type="hidden" value={run.id} />
                      <button className="secondaryButton" type="submit">
                        Cancel run
                      </button>
                    </form>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="sectionCard ukde-panel">
        <h2 className="sectionTitle">Selected run detail</h2>
        {!selectedRun ? (
          <SectionState
            kind="loading"
            title="Select a verification run"
            description="Run detail shows pass/fail reasons and proof integrity checks."
          />
        ) : (
          <>
            <p className="ukde-muted">
              Run <code>{selectedRun.id}</code> | Status <strong>{selectedRun.status}</strong>
            </p>
            <p className="ukde-muted">
              Verification result:{" "}
              <strong>
                {String(selectedRun.resultJson?.verificationResult ?? selectedRun.status)}
              </strong>
            </p>
            <p className="ukde-muted">
              Signature status: <strong>{String(selectedRun.resultJson?.signatureStatus ?? "n/a")}</strong>
            </p>
            {toFailureList(
              selectedRun.resultJson && typeof selectedRun.resultJson === "object"
                ? (selectedRun.resultJson as Record<string, unknown>)
                : null
            ).length > 0 ? (
              <div className="ukde-list">
                {toFailureList(
                  selectedRun.resultJson && typeof selectedRun.resultJson === "object"
                    ? (selectedRun.resultJson as Record<string, unknown>)
                    : null
                ).map((item) => (
                  <div className="ukde-list-item" key={item}>
                    <p className="ukde-muted">{item}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="ukde-muted">No verification failures reported.</p>
            )}
            <pre className="ukde-json-panel">{JSON.stringify(selectedRun.resultJson, null, 2)}</pre>
          </>
        )}
      </section>
    </main>
  );
}
