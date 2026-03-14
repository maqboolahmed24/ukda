import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { SectionState } from "@ukde/ui/primitives";

import { DocumentQualityTriageSurface } from "../../../../../../../../components/document-quality-triage-surface";
import {
  getProjectDocument,
  getProjectDocumentPreprocessQuality,
  listProjectDocumentPreprocessRuns
} from "../../../../../../../../lib/documents";
import { getProjectWorkspace } from "../../../../../../../../lib/projects";
import {
  projectDocumentPreprocessingPath,
  projectDocumentPreprocessingQualityPath,
  projectDocumentViewerPath,
  projectsPath
} from "../../../../../../../../lib/routes";

export const dynamic = "force-dynamic";

function parseOptionalFloat(value: string | undefined): number | null {
  if (!value) {
    return null;
  }
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function parseOptionalBool(value: string | undefined): boolean {
  if (!value) {
    return false;
  }
  return value === "1" || value.toLowerCase() === "true";
}

export default async function ProjectDocumentPreprocessingQualityPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; documentId: string }>;
  searchParams: Promise<{
    blurMax?: string;
    compareBaseRunId?: string;
    failedOnly?: string;
    runId?: string;
    skewMax?: string;
    skewMin?: string;
    warning?: string;
  }>;
}>) {
  const { projectId, documentId } = await params;
  const query = await searchParams;

  const [documentResult, workspaceResult, runsResult, qualityResult] = await Promise.all([
    getProjectDocument(projectId, documentId),
    getProjectWorkspace(projectId),
    listProjectDocumentPreprocessRuns(projectId, documentId, { pageSize: 50 }),
    getProjectDocumentPreprocessQuality(projectId, documentId, {
      runId: query.runId,
      pageSize: 500
    })
  ]);

  if (!documentResult.ok) {
    if (documentResult.status === 404) {
      notFound();
    }
    if (documentResult.status === 403) {
      redirect(projectsPath);
    }
    return (
      <main className="homeLayout">
        <SectionState
          className="sectionCard ukde-panel"
          kind="error"
          title="Preprocessing quality unavailable"
          description={
            documentResult.detail ??
            "Document metadata could not be loaded for quality view."
          }
        />
      </main>
    );
  }

  const document = documentResult.data;
  if (!document) {
    notFound();
  }

  const canMutate =
    workspaceResult.ok &&
    workspaceResult.data &&
    (workspaceResult.data.currentUserRole === "PROJECT_LEAD" ||
      workspaceResult.data.currentUserRole === "REVIEWER" ||
      (!workspaceResult.data.isMember && workspaceResult.data.canAccessSettings));

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Preprocessing quality</p>
        <h2>{document.originalFilename}</h2>
        <p className="ukde-muted">
          Operator triage queue for weak pages, hotspot filtering, selective reruns, and
          compare handoff.
        </p>
        <div className="buttonRow">
          <Link
            className="secondaryButton"
            href={projectDocumentPreprocessingPath(projectId, document.id)}
          >
            Pages
          </Link>
          <Link
            className="secondaryButton"
            aria-current="page"
            href={projectDocumentPreprocessingQualityPath(projectId, document.id, {
              runId: query.runId,
              warning: query.warning,
              skewMin: parseOptionalFloat(query.skewMin),
              skewMax: parseOptionalFloat(query.skewMax),
              blurMax: parseOptionalFloat(query.blurMax),
              failedOnly: parseOptionalBool(query.failedOnly),
              compareBaseRunId: query.compareBaseRunId
            })}
          >
            Quality
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentPreprocessingPath(projectId, document.id, {
              tab: "runs"
            })}
          >
            Processing runs
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentViewerPath(projectId, document.id, 1)}
          >
            Open viewer
          </Link>
        </div>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Document quality triage</h3>
        {!qualityResult.ok ? (
          <SectionState
            kind="degraded"
            title="Quality results unavailable"
            description={qualityResult.detail ?? "Quality data could not be loaded."}
          />
        ) : !qualityResult.data?.run ? (
          <SectionState
            kind="empty"
            title="No selected run"
            description="No active run was found. Select a run from Processing runs."
          />
        ) : (
          <DocumentQualityTriageSurface
            canMutate={Boolean(canMutate)}
            documentId={document.id}
            items={qualityResult.data.items}
            projectId={projectId}
            run={qualityResult.data.run}
            runs={runsResult.ok && runsResult.data ? runsResult.data.items : []}
            searchState={{
              runId: query.runId ?? null,
              warning: query.warning ?? null,
              skewMin: parseOptionalFloat(query.skewMin),
              skewMax: parseOptionalFloat(query.skewMax),
              blurMax: parseOptionalFloat(query.blurMax),
              failedOnly: parseOptionalBool(query.failedOnly),
              compareBaseRunId: query.compareBaseRunId ?? null
            }}
          />
        )}
      </section>
    </main>
  );
}

