import Link from "next/link";
import { redirect } from "next/navigation";
import { SectionState } from "@ukde/ui/primitives";

import { getExportRequest, getExportRequestBundle } from "../../../../../../../../lib/exports";
import { getProjectSummary } from "../../../../../../../../lib/projects";

export const dynamic = "force-dynamic";

export default async function ExportRequestBundleDetailPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string; exportRequestId: string; bundleId: string }>;
}>) {
  const { projectId, exportRequestId, bundleId } = await params;
  const [projectResult, requestResult, bundleResult] = await Promise.all([
    getProjectSummary(projectId),
    getExportRequest(projectId, exportRequestId),
    getExportRequestBundle(projectId, exportRequestId, bundleId)
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
  if (!bundleResult.ok || !bundleResult.data) {
    return (
      <main className="homeLayout">
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Bundle detail unavailable"
            description={bundleResult.detail ?? "Bundle detail could not be loaded."}
          />
          <div className="buttonRow">
            <Link
              className="secondaryButton"
              href={`/projects/${projectId}/export-requests/${request.id}/bundles`}
            >
              Back to bundles
            </Link>
          </div>
        </section>
      </main>
    );
  }

  const payload = bundleResult.data;
  const bundle = payload.bundle;
  const projection = payload.verificationProjection;
  const archiveEntries = Array.isArray(payload.artifact.archiveEntries)
    ? payload.artifact.archiveEntries.filter((item): item is string => typeof item === "string")
    : [];

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <h1 className="sectionTitle">Bundle detail</h1>
        <p className="ukde-muted">
          Bundle <code>{bundle.id}</code> ({bundle.bundleKind})
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-requests/${request.id}/bundles`}
          >
            Back to bundles
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
            View events
          </Link>
        </div>
      </section>

      <section className="sectionCard ukde-panel">
        <h2 className="sectionTitle">Status</h2>
        <p className="ukde-muted">
          Attempt {bundle.attemptNumber} | Status: {bundle.status}
        </p>
        <p className="ukde-muted">
          SHA-256: {bundle.bundleSha256 ? <code>{bundle.bundleSha256}</code> : "Pending"}
        </p>
        <p className="ukde-muted">
          Verification projection: {projection ? projection.status : "PENDING"}
        </p>
        <p className="ukde-muted">
          Proof id <code>{bundle.provenanceProofId}</code>
        </p>
        <p className="ukde-muted">
          Proof artifact SHA-256 <code>{bundle.provenanceProofArtifactSha256}</code>
        </p>
      </section>

      <section className="sectionCard ukde-panel">
        <h2 className="sectionTitle">Attempt lineage</h2>
        {payload.lineageAttempts.length === 0 ? (
          <SectionState
            kind="loading"
            title="No lineage attempts"
            description="No prior attempts are currently linked to this bundle lineage."
          />
        ) : (
          <div className="ukde-list">
            {payload.lineageAttempts.map((attempt) => (
              <div className="ukde-list-item" key={attempt.id}>
                <p className="ukde-muted">
                  Attempt {attempt.attemptNumber} <code>{attempt.id}</code>
                </p>
                <p className="ukde-muted">
                  Status {attempt.status} | Superseded by:{" "}
                  {attempt.supersededByBundleId ? <code>{attempt.supersededByBundleId}</code> : "Current"}
                </p>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="sectionCard ukde-panel">
        <h2 className="sectionTitle">Artifact preview</h2>
        <p className="ukde-muted">
          Archive entries: {archiveEntries.length > 0 ? archiveEntries.join(", ") : "Unavailable"}
        </p>
        <pre className="ukde-json-panel">{JSON.stringify(payload.artifact, null, 2)}</pre>
      </section>
    </main>
  );
}
