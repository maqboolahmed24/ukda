import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { PageHeader } from "../../../../../components/page-header";
import { requirePlatformRole } from "../../../../../lib/auth/session";
import {
  getAdminRunbook,
  getAdminRunbookContent
} from "../../../../../lib/launch-operations";
import {
  adminIncidentsPath,
  adminRunbooksPath
} from "../../../../../lib/routes";

export const dynamic = "force-dynamic";

function statusTone(
  status: "ACTIVE" | "REVIEW_REQUIRED" | "DRAFT" | "ARCHIVED"
): "success" | "warning" | "neutral" | "info" {
  if (status === "ACTIVE") {
    return "success";
  }
  if (status === "REVIEW_REQUIRED") {
    return "warning";
  }
  if (status === "DRAFT") {
    return "info";
  }
  return "neutral";
}

function formatTimestamp(value: string): string {
  return new Date(value).toISOString();
}

export default async function AdminRunbookDetailPage({
  params
}: Readonly<{
  params: Promise<{ runbookId: string }>;
}>) {
  await requirePlatformRole(["ADMIN"]);
  const { runbookId } = await params;
  const [detailResult, contentResult] = await Promise.all([
    getAdminRunbook(runbookId),
    getAdminRunbookContent(runbookId)
  ]);

  if (!detailResult.ok || !detailResult.data) {
    return (
      <main className="homeLayout">
        <PageHeader
          eyebrow="Platform operations"
          secondaryActions={[
            { href: adminRunbooksPath, label: "Back to runbooks" },
            { href: adminIncidentsPath, label: "Incidents" }
          ]}
          summary="Runbook detail retrieval failed for this runbook identifier."
          title="Runbook detail"
        />
        <section className="sectionCard ukde-panel">
          <SectionState
            kind="error"
            title="Runbook unavailable"
            description={detailResult.detail ?? "Unable to load runbook detail."}
          />
        </section>
      </main>
    );
  }

  const runbook = detailResult.data;
  const content = contentResult.ok && contentResult.data ? contentResult.data : null;

  return (
    <main className="homeLayout">
      <PageHeader
        eyebrow="Platform operations"
        meta={
          <StatusChip tone={statusTone(runbook.status)}>
            {runbook.status}
          </StatusChip>
        }
        secondaryActions={[
          { href: adminRunbooksPath, label: "Back to runbooks" },
          { href: adminIncidentsPath, label: "Incidents" }
        ]}
        summary="Rendered runbook content and metadata for launch and rollback operations."
        title={runbook.title}
      />

      <section className="sectionCard ukde-panel">
        <ul className="projectMetaList">
          <li>
            <span>Runbook ID</span>
            <strong>{runbook.id}</strong>
          </li>
          <li>
            <span>Slug</span>
            <strong>{runbook.slug}</strong>
          </li>
          <li>
            <span>Owner</span>
            <strong>{runbook.ownerUserId}</strong>
          </li>
          <li>
            <span>Last reviewed</span>
            <strong>{formatTimestamp(runbook.lastReviewedAt)}</strong>
          </li>
          <li>
            <span>Storage key</span>
            <strong>{runbook.storageKey}</strong>
          </li>
        </ul>
      </section>

      <section className="sectionCard ukde-panel">
        <h2>Runbook content</h2>
        {!content ? (
          <SectionState
            kind="error"
            title="Runbook content unavailable"
            description={contentResult.detail ?? "Unable to load rendered runbook content."}
          />
        ) : (
          <>
            <article
              className="ukde-stack-sm"
              dangerouslySetInnerHTML={{ __html: content.contentHtml }}
            />
            <details>
              <summary>View source markdown</summary>
              <pre className="ukde-json-panel">{content.contentMarkdown}</pre>
            </details>
          </>
        )}
      </section>
    </main>
  );
}
