import Link from "next/link";
import { redirect } from "next/navigation";
import { SectionState } from "@ukde/ui/primitives";

import { listExportRequests } from "../../../../../lib/exports";
import { getProjectSummary } from "../../../../../lib/projects";
import { normalizeOptionalTextParam } from "../../../../../lib/url-state";

export const dynamic = "force-dynamic";

function parseCursor(raw: string | undefined): number | undefined {
  if (!raw) {
    return undefined;
  }
  const parsed = Number.parseInt(raw, 10);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return undefined;
  }
  return parsed;
}

function parseLimit(raw: string | undefined): number | undefined {
  if (!raw) {
    return undefined;
  }
  const parsed = Number.parseInt(raw, 10);
  if (!Number.isFinite(parsed) || parsed < 1) {
    return undefined;
  }
  return Math.min(parsed, 100);
}

export default async function ProjectExportRequestsPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{
    status?: string;
    requesterId?: string;
    candidateKind?: string;
    cursor?: string;
    limit?: string;
  }>;
}>) {
  const { projectId } = await params;
  const rawFilters = await searchParams;
  const filters = {
    status: normalizeOptionalTextParam(rawFilters.status),
    requesterId: normalizeOptionalTextParam(rawFilters.requesterId),
    candidateKind: normalizeOptionalTextParam(rawFilters.candidateKind),
    cursor: parseCursor(rawFilters.cursor),
    limit: parseLimit(rawFilters.limit)
  };
  const [projectResult, requestsResult] = await Promise.all([
    getProjectSummary(projectId),
    listExportRequests(projectId, filters)
  ]);

  if (!projectResult.ok || !projectResult.data) {
    redirect("/projects?error=member-route");
  }

  const items = requestsResult.ok && requestsResult.data ? requestsResult.data.items : [];
  const nextCursor = requestsResult.ok && requestsResult.data
    ? requestsResult.data.nextCursor
    : null;

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <h1 className="sectionTitle">Export requests</h1>
        <p className="ukde-muted">
          Request history is revisioned. Resubmissions create successor requests and
          preserve frozen release packs.
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={`/projects/${projectId}/export-candidates`}
          >
            Browse candidates
          </Link>
        </div>
      </section>

      {!requestsResult.ok ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Request history unavailable"
            description={requestsResult.detail ?? "Unknown failure"}
          />
        </section>
      ) : items.length === 0 ? (
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="empty"
            title="No export requests yet"
            description="Create a request from an eligible candidate snapshot."
          />
        </section>
      ) : (
        <section className="sectionCard ukde-panel">
          <table className="ukde-data-table">
            <thead>
              <tr>
                <th>Request</th>
                <th>Status</th>
                <th>Revision</th>
                <th>Risk</th>
                <th>Candidate</th>
                <th>Submitted</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <Link
                      className="secondaryButton"
                      href={`/projects/${projectId}/export-requests/${item.id}`}
                    >
                      {item.id}
                    </Link>
                  </td>
                  <td>{item.status}</td>
                  <td>{item.requestRevision}</td>
                  <td>{item.riskClassification}</td>
                  <td>
                    <code>{item.candidateSnapshotId}</code>
                  </td>
                  <td>{new Date(item.submittedAt).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {typeof nextCursor === "number" ? (
            <div className="buttonRow">
              <Link
                className="secondaryButton"
                href={`/projects/${projectId}/export-requests?cursor=${nextCursor}`}
              >
                Next page
              </Link>
            </div>
          ) : null}
        </section>
      )}
    </main>
  );
}
