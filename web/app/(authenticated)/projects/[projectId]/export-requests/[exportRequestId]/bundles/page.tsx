import Link from "next/link";
import { redirect } from "next/navigation";
import { SectionState } from "@ukde/ui/primitives";

import { getExportRequest, listExportRequestBundles } from "../../../../../../../lib/exports";
import { getProjectSummary } from "../../../../../../../lib/projects";

export const dynamic = "force-dynamic";

export default async function ExportRequestBundlesPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string; exportRequestId: string }>;
}>) {
  const { projectId, exportRequestId } = await params;
  const [projectResult, requestResult, bundlesResult] = await Promise.all([
    getProjectSummary(projectId),
    getExportRequest(projectId, exportRequestId),
    listExportRequestBundles(projectId, exportRequestId)
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

  const request = requestResult.data;
  const bundles = bundlesResult.ok && bundlesResult.data ? bundlesResult.data.items : [];

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <h1 className="sectionTitle">Deposit bundles</h1>
        <p className="ukde-muted">
          Export request <code>{request.id}</code> revision {request.requestRevision}
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-requests/${request.id}`}
          >
            Back to request
          </Link>
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-requests/${request.id}/provenance`}
          >
            View provenance
          </Link>
        </div>
      </section>

      {!bundlesResult.ok ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Bundle list unavailable"
            description={bundlesResult.detail ?? "Unable to load deposit bundles."}
          />
        </section>
      ) : bundles.length === 0 ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="loading"
            title="No bundles yet"
            description="Create is idempotent per request/candidate/kind lineage. Use POST /bundles?kind=... to build."
          />
        </section>
      ) : (
        <section className="sectionCard ukde-panel">
          <h2 className="sectionTitle">Bundle attempts</h2>
          <div className="ukde-list">
            {bundles.map((bundle) => (
              <div className="ukde-list-item" key={bundle.id}>
                <p className="ukde-muted">
                  <strong>{bundle.bundleKind}</strong> attempt {bundle.attemptNumber}
                </p>
                <p className="ukde-muted">
                  Status: {bundle.status} | Bundle id <code>{bundle.id}</code>
                </p>
                <p className="ukde-muted">
                  SHA-256: {bundle.bundleSha256 ? <code>{bundle.bundleSha256}</code> : "Pending"}
                </p>
                <p className="ukde-muted">
                  Superseded by: {bundle.supersededByBundleId ? <code>{bundle.supersededByBundleId}</code> : "Current"}
                </p>
                <div className="buttonRow">
                  <Link
                    className="secondaryButton"
                    href={`/projects/${projectId}/export-requests/${request.id}/bundles/${bundle.id}`}
                  >
                    Open detail
                  </Link>
                  <Link
                    className="secondaryButton"
                    href={`/projects/${projectId}/export-requests/${request.id}/bundles/${bundle.id}/verification`}
                  >
                    Verification
                  </Link>
                  <Link
                    className="secondaryButton"
                    href={`/projects/${projectId}/export-requests/${request.id}/bundles/${bundle.id}/validation`}
                  >
                    Validation
                  </Link>
                  <Link
                    className="secondaryButton"
                    href={`/projects/${projectId}/export-requests/${request.id}/bundles/${bundle.id}/events`}
                  >
                    Open events
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="sectionCard ukde-panel">
        <p className="ukde-muted">
          `SAFEGUARDED_DEPOSIT` bundle reads follow export-request permissions. `CONTROLLED_EVIDENCE`
          reads are restricted to `ADMIN` and read-only `AUDITOR`.
        </p>
      </section>
    </main>
  );
}
