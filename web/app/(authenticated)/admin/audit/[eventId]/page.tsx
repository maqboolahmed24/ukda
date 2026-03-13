import Link from "next/link";

import { getAuditEvent } from "../../../../../lib/audit";

export const dynamic = "force-dynamic";

export default async function AdminAuditEventPage({
  params
}: Readonly<{
  params: Promise<{ eventId: string }>;
}>) {
  const { eventId } = await params;
  const eventResult = await getAuditEvent(eventId);

  return (
    <main className="homeLayout">
      <section
        className="sectionCard ukde-panel"
        aria-labelledby="audit-detail-title"
      >
        <p className="ukde-eyebrow">Governance surface</p>
        <h1 id="audit-detail-title">Audit event detail</h1>
        <div className="buttonRow">
          <Link className="secondaryButton" href="/admin/audit">
            Back to audit list
          </Link>
        </div>
      </section>

      {!eventResult.ok || !eventResult.data ? (
        <section className="sectionCard ukde-panel">
          <p className="ukde-muted">
            Audit event read failed: {eventResult.detail ?? "unknown"}
          </p>
        </section>
      ) : (
        <section className="sectionCard ukde-panel">
          <div className="auditDetailGrid">
            <div>
              <p className="ukde-eyebrow">Event ID</p>
              <p>{eventResult.data.id}</p>
            </div>
            <div>
              <p className="ukde-eyebrow">Chain index</p>
              <p>{eventResult.data.chainIndex}</p>
            </div>
            <div>
              <p className="ukde-eyebrow">Timestamp</p>
              <p>{new Date(eventResult.data.timestamp).toISOString()}</p>
            </div>
            <div>
              <p className="ukde-eyebrow">Event type</p>
              <p>{eventResult.data.eventType}</p>
            </div>
            <div>
              <p className="ukde-eyebrow">Actor</p>
              <p>{eventResult.data.actorUserId ?? "-"}</p>
            </div>
            <div>
              <p className="ukde-eyebrow">Project</p>
              <p>{eventResult.data.projectId ?? "-"}</p>
            </div>
            <div>
              <p className="ukde-eyebrow">Request ID</p>
              <p>{eventResult.data.requestId}</p>
            </div>
            <div>
              <p className="ukde-eyebrow">Client IP</p>
              <p>{eventResult.data.ip ?? "-"}</p>
            </div>
          </div>

          <div className="auditHashGrid">
            <div>
              <p className="ukde-eyebrow">Previous hash</p>
              <pre className="statusDetail">{eventResult.data.prevHash}</pre>
            </div>
            <div>
              <p className="ukde-eyebrow">Row hash</p>
              <pre className="statusDetail">{eventResult.data.rowHash}</pre>
            </div>
          </div>

          <div>
            <p className="ukde-eyebrow">Metadata</p>
            <pre className="statusDetail">
              {JSON.stringify(eventResult.data.metadataJson, null, 2)}
            </pre>
          </div>
        </section>
      )}
    </main>
  );
}
