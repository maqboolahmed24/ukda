import Link from "next/link";
import { redirect } from "next/navigation";
import { SectionState } from "@ukde/ui/primitives";

import {
  getExportRequest,
  getExportRequestBundleStatus,
  listExportRequestBundleEvents
} from "../../../../../../../../../lib/exports";
import { getProjectSummary } from "../../../../../../../../../lib/projects";

export const dynamic = "force-dynamic";

export default async function ExportRequestBundleEventsPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string; exportRequestId: string; bundleId: string }>;
}>) {
  const { projectId, exportRequestId, bundleId } = await params;
  const [projectResult, requestResult, statusResult, eventsResult] = await Promise.all([
    getProjectSummary(projectId),
    getExportRequest(projectId, exportRequestId),
    getExportRequestBundleStatus(projectId, exportRequestId, bundleId),
    listExportRequestBundleEvents(projectId, exportRequestId, bundleId)
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
  const bundleStatus = statusResult.ok && statusResult.data ? statusResult.data.bundle : null;
  const events = eventsResult.ok && eventsResult.data ? eventsResult.data.items : [];

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <h1 className="sectionTitle">Bundle events</h1>
        <p className="ukde-muted">
          Request <code>{request.id}</code> | Bundle <code>{bundleId}</code>
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-requests/${request.id}/bundles/${bundleId}`}
          >
            Back to detail
          </Link>
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-requests/${request.id}/bundles/${bundleId}/verification`}
          >
            Verification
          </Link>
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-requests/${request.id}/bundles/${bundleId}/validation`}
          >
            Validation
          </Link>
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-requests/${request.id}/bundles`}
          >
            Back to bundles
          </Link>
        </div>
      </section>

      {!bundleStatus ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Bundle status unavailable"
            description={statusResult.detail ?? "Bundle status could not be loaded."}
          />
        </section>
      ) : (
        <section className="sectionCard ukde-panel">
          <h2 className="sectionTitle">Current status</h2>
          <p className="ukde-muted">
            {bundleStatus.bundleKind} attempt {bundleStatus.attemptNumber} is {bundleStatus.status}
          </p>
        </section>
      )}

      {!eventsResult.ok ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Bundle events unavailable"
            description={eventsResult.detail ?? "Event timeline could not be loaded."}
          />
        </section>
      ) : events.length === 0 ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="loading"
            title="No events yet"
            description="Bundle history events are appended as build, verification, and validation actions occur."
          />
        </section>
      ) : (
        <section className="sectionCard ukde-panel">
          <h2 className="sectionTitle">Event timeline</h2>
          <div className="ukde-list">
            {events.map((event) => (
              <div className="ukde-list-item" key={event.id}>
                <p className="ukde-muted">
                  <strong>{event.eventType}</strong>
                </p>
                <p className="ukde-muted">
                  {new Date(event.createdAt).toLocaleString()} | Actor:{" "}
                  {event.actorUserId ?? "system"}
                </p>
                <p className="ukde-muted">
                  Verification run: {event.verificationRunId ?? "None"} | Validation run:{" "}
                  {event.validationRunId ?? "None"}
                </p>
                <p className="ukde-muted">Reason: {event.reason ?? "None"}</p>
              </div>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
