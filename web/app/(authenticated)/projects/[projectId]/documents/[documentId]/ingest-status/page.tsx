import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import type { DocumentStatus } from "@ukde/contracts";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { DocumentExtractionRetryAction } from "../../../../../../../components/document-extraction-retry-action";
import { DocumentProcessingTimeline } from "../../../../../../../components/document-processing-timeline";
import {
  getProjectDocument,
  listProjectDocumentPages,
  listProjectDocumentProcessingRuns
} from "../../../../../../../lib/documents";
import {
  projectDocumentPath,
  projectDocumentPreprocessingPath,
  projectDocumentViewerPath,
  projectDocumentsPath,
  projectsPath
} from "../../../../../../../lib/routes";
import {
  normalizeViewerPageParam,
  normalizeViewerZoomParam
} from "../../../../../../../lib/url-state";

export const dynamic = "force-dynamic";

const DOCUMENT_STATUS_TONES: Record<
  DocumentStatus,
  "danger" | "info" | "neutral" | "success" | "warning"
> = {
  UPLOADING: "warning",
  QUEUED: "warning",
  SCANNING: "warning",
  EXTRACTING: "warning",
  READY: "success",
  FAILED: "danger",
  CANCELED: "neutral"
};

function resolveStatusSummary(status: DocumentStatus): string {
  switch (status) {
    case "UPLOADING":
      return "Bytes are being transferred into controlled storage.";
    case "QUEUED":
      return "Import is queued for scan and validation.";
    case "SCANNING":
      return "Security and validation scanning is in progress.";
    case "EXTRACTING":
      return "Page extraction is running before viewer readiness.";
    case "READY":
      return "Document pages are available for viewer handoff.";
    case "FAILED":
      return "The latest ingest attempt failed. Review the failed stage and take the safe next step.";
    case "CANCELED":
      return "Ingest was canceled before completion.";
    default:
      return "Document status is available.";
  }
}

function formatTimestamp(value: string): string {
  return new Date(value).toISOString();
}

export default async function ProjectDocumentIngestStatusPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; documentId: string }>;
  searchParams: Promise<{ page?: string; zoom?: string }>;
}>) {
  const { projectId, documentId } = await params;
  const query = await searchParams;
  const viewerPage = normalizeViewerPageParam(query.page).value;
  const viewerZoom = normalizeViewerZoomParam(query.zoom).value;

  const documentResult = await getProjectDocument(projectId, documentId);
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
          title="Ingest status unavailable"
          description={
            documentResult.detail ??
            "Document metadata could not be loaded for this route."
          }
        />
      </main>
    );
  }

  const document = documentResult.data;
  if (!document) {
    notFound();
  }

  const [timelineResult, pagesResult] = await Promise.all([
    listProjectDocumentProcessingRuns(projectId, document.id),
    listProjectDocumentPages(projectId, document.id)
  ]);

  const pages = pagesResult.ok && pagesResult.data ? pagesResult.data.items : [];
  const firstReadyPage = pages.find((page) => page.status === "READY");
  const pageCount = pages.length > 0 ? pages.length : (document.pageCount ?? 0);
  const boundedViewerPage =
    pageCount > 0 ? Math.min(Math.max(viewerPage, 1), pageCount) : viewerPage;
  const requestedPageExists = pages.some(
    (page) => page.pageIndex + 1 === boundedViewerPage
  );
  const viewerTargetPage = requestedPageExists
    ? boundedViewerPage
    : firstReadyPage
      ? Math.min(
          Math.max(firstReadyPage.pageIndex + 1, 1),
          Math.max(pageCount, 1)
        )
      : boundedViewerPage;
  const viewerHref =
    pageCount > 0
      ? projectDocumentViewerPath(projectId, document.id, viewerTargetPage, {
          zoom: viewerZoom
        })
      : null;
  const timelineItems =
    timelineResult.ok && timelineResult.data ? timelineResult.data.items : [];
  const latestExtractionAttempt = timelineItems.find(
    (item) =>
      item.runKind === "EXTRACTION" && item.supersededByProcessingRunId === null
  );
  const extractionRetryEligible =
    latestExtractionAttempt?.status === "FAILED" ||
    latestExtractionAttempt?.status === "CANCELED";
  const timelineError = !timelineResult.ok
    ? timelineResult.detail ??
      "Processing runs could not be loaded for this document."
    : null;

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Ingest status</p>
        <h2>{document.originalFilename}</h2>
        <div className="auditIntegrityRow">
          <StatusChip tone={DOCUMENT_STATUS_TONES[document.status]}>
            {document.status}
          </StatusChip>
          <span className="ukde-muted">
            Updated {formatTimestamp(document.updatedAt)}
          </span>
        </div>
        <p className="ukde-muted">{resolveStatusSummary(document.status)}</p>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Recovery actions</h3>
        <div className="buttonRow">
          {viewerHref ? (
            <Link className="secondaryButton" href={viewerHref}>
              Open viewer
            </Link>
          ) : (
            <button className="secondaryButton" disabled type="button">
              Open viewer
            </button>
          )}
          <Link
            className="secondaryButton"
            href={projectDocumentPath(projectId, document.id)}
          >
            Open document
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentPreprocessingPath(projectId, document.id)}
          >
            Open preprocessing
          </Link>
          <Link className="secondaryButton" href={projectDocumentsPath(projectId)}>
            Back to documents
          </Link>
        </div>
        {!viewerHref ? (
          <p className="ukde-muted">
            Viewer handoff is blocked until page records are materialized.
          </p>
        ) : null}
        {extractionRetryEligible ? (
          <DocumentExtractionRetryAction
            documentId={document.id}
            projectId={projectId}
          />
        ) : (
          <p className="ukde-muted">
            Extraction retry is available only when the latest extraction attempt
            is failed or canceled.
          </p>
        )}
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Processing timeline</h3>
        <DocumentProcessingTimeline
          documentId={document.id}
          documentStatus={document.status}
          initialErrorMessage={timelineError}
          initialItems={timelineItems}
          projectId={projectId}
        />
      </section>
    </main>
  );
}
