import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import type { DocumentStatus } from "@ukde/contracts";
import { SectionState, StatusChip } from "@ukde/ui/primitives";

import { DocumentProcessingTimeline } from "../../../../../../components/document-processing-timeline";
import {
  getProjectDocument,
  listProjectDocumentPages,
  listProjectDocumentProcessingRuns
} from "../../../../../../lib/documents";
import {
  projectDocumentIngestStatusPath,
  projectDocumentLayoutPath,
  projectDocumentPreprocessingPath,
  projectDocumentTranscriptionPath,
  projectDocumentViewerPath,
  projectDocumentsPath,
  projectsPath
} from "../../../../../../lib/routes";

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
      return "The latest ingest attempt failed. Review timeline details before retry.";
    case "CANCELED":
      return "Ingest was canceled before completion.";
    default:
      return "Document status is available.";
  }
}

function formatTimestamp(value: string): string {
  return new Date(value).toISOString();
}

function formatBytes(value: number | null): string {
  if (typeof value !== "number") {
    return "Pending upload verification";
  }
  if (value < 1_024) {
    return `${value} B`;
  }
  if (value < 1_024 * 1_024) {
    return `${(value / 1_024).toFixed(1)} KB`;
  }
  if (value < 1_024 * 1_024 * 1_024) {
    return `${(value / (1_024 * 1_024)).toFixed(1)} MB`;
  }
  return `${(value / (1_024 * 1_024 * 1_024)).toFixed(1)} GB`;
}

export default async function ProjectDocumentDetailPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string; documentId: string }>;
}>) {
  const { projectId, documentId } = await params;
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
          title="Document detail unavailable"
          description={
            documentResult.detail ??
            "Document metadata could not be loaded for this project."
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

  const timelineItems =
    timelineResult.ok && timelineResult.data ? timelineResult.data.items : [];
  const timelineError = !timelineResult.ok
    ? timelineResult.detail ??
      "Processing runs could not be loaded for this document."
    : null;
  const pages = pagesResult.ok && pagesResult.data ? pagesResult.data.items : [];
  const pageCount = pages.length > 0 ? pages.length : (document.pageCount ?? 0);
  const readyPages = pages.filter((page) => page.status === "READY").length;
  const failedPages = pages.filter(
    (page) => page.status === "FAILED" || page.status === "CANCELED"
  ).length;
  const pendingPages = pages.filter((page) => page.status === "PENDING").length;
  const firstReadyPage = pages.find((page) => page.status === "READY");
  const preferredViewerPage = firstReadyPage ? firstReadyPage.pageIndex + 1 : 1;
  const viewerHref = firstReadyPage
    ? projectDocumentViewerPath(projectId, document.id, preferredViewerPage)
    : null;

  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <p className="ukde-eyebrow">Document metadata</p>
        <h2>{document.originalFilename}</h2>
        <p className="ukde-muted">{resolveStatusSummary(document.status)}</p>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Metadata</h3>
        <ul className="projectMetaList">
          <li>
            <span>Original filename</span>
            <strong>{document.originalFilename}</strong>
          </li>
          <li>
            <span>Uploaded by</span>
            <strong>{document.createdBy}</strong>
          </li>
          <li>
            <span>Detected type</span>
            <strong>{document.contentTypeDetected ?? "Pending detection"}</strong>
          </li>
          <li>
            <span>Source size</span>
            <strong>{formatBytes(document.bytes)}</strong>
          </li>
          <li>
            <span>SHA-256</span>
            <strong>{document.sha256 ?? "Pending checksum"}</strong>
          </li>
          <li>
            <span>Pages</span>
            <strong>{pageCount > 0 ? pageCount : "Not available yet"}</strong>
          </li>
          <li>
            <span>Uploaded at</span>
            <strong>{formatTimestamp(document.createdAt)}</strong>
          </li>
          <li>
            <span>Last status update</span>
            <strong>{formatTimestamp(document.updatedAt)}</strong>
          </li>
        </ul>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Derived page readiness</h3>
        {!pagesResult.ok ? (
          <SectionState
            kind="degraded"
            title="Page readiness unavailable"
            description={
              pagesResult.detail ??
              "Page metadata could not be loaded for this document."
            }
          />
        ) : pageCount === 0 ? (
          <SectionState
            kind="loading"
            title="No page rows yet"
            description="Page extraction has not produced page records yet."
          />
        ) : (
          <ul className="projectMetaList">
            <li>
              <span>Total pages</span>
              <strong>{pageCount}</strong>
            </li>
            <li>
              <span>Ready</span>
              <strong>{readyPages}</strong>
            </li>
            <li>
              <span>Pending</span>
              <strong>{pendingPages}</strong>
            </li>
            <li>
              <span>Failed or canceled</span>
              <strong>{failedPages}</strong>
            </li>
          </ul>
        )}
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Current ingest status</h3>
        <div className="auditIntegrityRow">
          <StatusChip tone={DOCUMENT_STATUS_TONES[document.status]}>
            {document.status}
          </StatusChip>
        </div>
        <p className="ukde-muted">{resolveStatusSummary(document.status)}</p>
      </section>

      <section className="sectionCard ukde-panel">
        <h3>Actions</h3>
        <div className="buttonRow">
          {viewerHref ? (
            <Link className="secondaryButton" href={viewerHref}>
              Open document
            </Link>
          ) : (
            <button className="secondaryButton" disabled type="button">
              Open document
            </button>
          )}
          <Link
            className="secondaryButton"
            href={projectDocumentIngestStatusPath(projectId, document.id, {
              page: preferredViewerPage
            })}
          >
            View ingest status
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentPreprocessingPath(projectId, document.id)}
          >
            Open preprocessing
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentLayoutPath(projectId, document.id)}
          >
            Open layout
          </Link>
          <Link
            className="secondaryButton"
            href={projectDocumentTranscriptionPath(projectId, document.id)}
          >
            Open transcription
          </Link>
          <Link className="secondaryButton" href={projectDocumentsPath(projectId)}>
            Back to documents
          </Link>
        </div>
        {!viewerHref ? (
          <p className="ukde-muted">
            Viewer handoff is blocked until at least one page is ready.
          </p>
        ) : null}
      </section>

      <section className="sectionCard ukde-panel" id="ingest-timeline">
        <h3>Timeline</h3>
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
