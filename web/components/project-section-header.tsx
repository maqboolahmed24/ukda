"use client";

import { usePathname, useSearchParams } from "next/navigation";

import { Breadcrumbs } from "@ukde/ui/primitives";

import {
  projectDocumentImportPath,
  projectDocumentIngestStatusPath,
  projectDocumentLayoutPath,
  projectDocumentLayoutRunPath,
  projectDocumentLayoutWorkspacePath,
  projectDocumentPath,
  projectDocumentPreprocessingComparePath,
  projectDocumentPreprocessingPath,
  projectDocumentPreprocessingQualityPath,
  projectDocumentPreprocessingRunPath,
  projectDocumentViewerPath,
  projectModelAssignmentDatasetsPath,
  projectModelAssignmentPath,
  projectModelAssignmentsPath,
  projectDocumentsPath,
  projectJobsPath,
  projectOverviewPath
} from "../lib/routes";
import {
  normalizeViewerPageParam,
  normalizeViewerZoomParam
} from "../lib/url-state";
import { PageHeader } from "./page-header";

const SECTION_MAP: Record<string, { title: string; summary: string }> = {
  overview: {
    title: "Overview",
    summary: "Project context, purpose, and current operational posture."
  },
  documents: {
    title: "Documents",
    summary:
      "Project document library, ingest status visibility, and controlled import entry."
  },
  jobs: {
    title: "Jobs",
    summary: "Project job queue, retry lineage, and worker execution status."
  },
  "model-assignments": {
    title: "Model assignments",
    summary:
      "Stable role-map assignments for transcription primary, fallback, and assist model flows."
  },
  "export-candidates": {
    title: "Export candidates",
    summary: "Candidate documents prepared for controlled export workflows."
  },
  "export-requests": {
    title: "Export requests",
    summary: "Queued and historical export request decisions for this project."
  },
  "export-review": {
    title: "Export review",
    summary: "Governance review surface for export candidate approval outcomes."
  },
  activity: {
    title: "Activity",
    summary:
      "Project-scoped activity timeline, distinct from platform-level /admin/audit governance surfaces."
  },
  settings: {
    title: "Settings",
    summary: "Membership and project-governance controls."
  }
};

export function ProjectSectionHeader({ projectName }: { projectName: string }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const pathSegments = pathname.split("/").filter(Boolean);
  const projectId = pathSegments[1] ?? "";
  const sectionKey = pathSegments[2] ?? "overview";
  const section = SECTION_MAP[sectionKey] ?? SECTION_MAP.overview;
  const sectionDetail = pathSegments[3];
  const sectionLeaf = pathSegments[4];
  const sectionSubLeaf = pathSegments[5];
  const sectionTail = pathSegments[6];
  const viewerPage = normalizeViewerPageParam(
    searchParams.get("page") ?? undefined
  ).value;
  const viewerZoom = normalizeViewerZoomParam(
    searchParams.get("zoom") ?? undefined
  ).value;
  const compareBaseRunId = searchParams.get("baseRunId") ?? undefined;
  const compareCandidateRunId = searchParams.get("candidateRunId") ?? undefined;
  const layoutRunId = searchParams.get("runId") ?? undefined;
  const layoutPageRaw = searchParams.get("page");
  const layoutPage =
    typeof layoutPageRaw === "string" && layoutPageRaw.trim().length > 0
      ? Math.max(1, Number.parseInt(layoutPageRaw, 10) || 1)
      : 1;

  let title = section.title;
  let summary = section.summary;
  const breadcrumbs: Array<{ href?: string; label: string }> = [
    { href: "/projects", label: "Projects" },
    { href: projectOverviewPath(projectId), label: projectName }
  ];
  let primaryAction: { href: string; label: string } | undefined;
  let secondaryActions: Array<{ href: string; label: string }> = [];

  if (sectionKey === "documents") {
    breadcrumbs.push({
      href: projectDocumentsPath(projectId),
      label: SECTION_MAP.documents.title
    });

    if (sectionDetail === "import") {
      title = "Import";
      summary =
        "Dedicated route for controlled ingest and scan validation workflows.";
      breadcrumbs.push({ label: "Import" });
      secondaryActions = [
        { href: projectDocumentsPath(projectId), label: "Back to documents" }
      ];
    } else if (sectionDetail && sectionLeaf === "preprocessing") {
      const preprocessingPath = projectDocumentPreprocessingPath(
        projectId,
        sectionDetail
      );
      title = "Preprocessing";
      summary =
        "Deterministic preprocessing overview, quality diagnostics, and run administration.";
      breadcrumbs.push({
        href: projectDocumentPath(projectId, sectionDetail),
        label: "Document"
      });
      breadcrumbs.push({
        href: preprocessingPath,
        label: "Preprocessing"
      });

      if (sectionSubLeaf === "quality") {
        title = "Preprocessing quality";
        summary =
          "Quality triage for active or selected preprocessing runs with filterable page diagnostics.";
        breadcrumbs.push({
          href: projectDocumentPreprocessingQualityPath(projectId, sectionDetail),
          label: "Quality"
        });
      } else if (sectionSubLeaf === "compare") {
        title = "Preprocessing compare";
        summary =
          "Canonical diagnostics surface for before/after run comparison and warning deltas.";
        if (compareBaseRunId && compareCandidateRunId) {
          breadcrumbs.push({
            href: projectDocumentPreprocessingComparePath(
              projectId,
              sectionDetail,
              compareBaseRunId,
              compareCandidateRunId
            ),
            label: "Compare"
          });
        } else {
          breadcrumbs.push({ label: "Compare" });
        }
      } else if (sectionSubLeaf === "runs" && sectionTail) {
        title = `Preprocessing run ${sectionTail}`;
        summary =
          "Run detail with status lineage, parameters, and per-page preprocess results.";
        breadcrumbs.push({
          href: projectDocumentPreprocessingRunPath(
            projectId,
            sectionDetail,
            sectionTail
          ),
          label: `Run ${sectionTail}`
        });
      }

      secondaryActions = [
        {
          href: projectDocumentViewerPath(projectId, sectionDetail, viewerPage, {
            zoom: viewerZoom
          }),
          label: "Open viewer"
        },
        {
          href: projectDocumentPath(projectId, sectionDetail),
          label: "Document detail"
        }
      ];
    } else if (sectionDetail && sectionLeaf === "layout") {
      const layoutPath = projectDocumentLayoutPath(projectId, sectionDetail);
      title = "Layout";
      summary =
        "Layout analysis overview, page triage, and run lineage for segmentation workspaces.";
      breadcrumbs.push({
        href: projectDocumentPath(projectId, sectionDetail),
        label: "Document"
      });
      breadcrumbs.push({
        href: layoutPath,
        label: "Layout"
      });

      if (sectionSubLeaf === "runs" && sectionTail) {
        title = `Layout run ${sectionTail}`;
        summary =
          "Run detail for document-scoped layout analysis, including page-level segmentation status.";
        breadcrumbs.push({
          href: projectDocumentLayoutRunPath(projectId, sectionDetail, sectionTail),
          label: `Run ${sectionTail}`
        });
      } else if (sectionSubLeaf === "workspace") {
        title = "Layout workspace";
        summary =
          "Read-only segmentation workspace with filmstrip, page canvas, and inspector panes.";
        breadcrumbs.push({
          href: projectDocumentLayoutWorkspacePath(projectId, sectionDetail, {
            page: layoutPage,
            runId: layoutRunId
          }),
          label: "Workspace"
        });
      }

      secondaryActions = [
        {
          href: projectDocumentLayoutPath(projectId, sectionDetail, {
            tab: "triage",
            runId: layoutRunId
          }),
          label: "Open triage"
        },
        {
          href: projectDocumentViewerPath(projectId, sectionDetail, viewerPage, {
            zoom: viewerZoom
          }),
          label: "Open viewer"
        },
        {
          href: projectDocumentPath(projectId, sectionDetail),
          label: "Document detail"
        }
      ];
    } else if (sectionDetail && sectionLeaf === "ingest-status") {
      title = "Ingest status";
      summary =
        "Append-only processing timeline and safe recovery actions for this document.";
      breadcrumbs.push({
        href: projectDocumentPath(projectId, sectionDetail),
        label: "Document"
      });
      breadcrumbs.push({
        href: projectDocumentIngestStatusPath(projectId, sectionDetail, {
          page: viewerPage,
          zoom: viewerZoom
        }),
        label: "Ingest status"
      });
      secondaryActions = [
        {
          href: projectDocumentViewerPath(projectId, sectionDetail, viewerPage, {
            zoom: viewerZoom
          }),
          label: "Open viewer"
        }
      ];
    } else if (sectionDetail && sectionLeaf === "viewer") {
      title = "Viewer";
      summary =
        "Deep-linkable document viewer route. Browser `page` query remains 1-based.";
      breadcrumbs.push({
        href: projectDocumentPath(projectId, sectionDetail),
        label: "Document"
      });
      breadcrumbs.push({
        href: projectDocumentViewerPath(projectId, sectionDetail, viewerPage, {
          zoom: viewerZoom
        }),
        label: "Viewer"
      });
      breadcrumbs.push({ label: `Page ${viewerPage}` });
      secondaryActions = [
        {
          href: projectDocumentIngestStatusPath(projectId, sectionDetail, {
            page: viewerPage,
            zoom: viewerZoom
          }),
          label: "View ingest status"
        }
      ];
    } else if (sectionDetail) {
      title = `Document ${sectionDetail}`;
      summary =
        "Stable document detail anchor for metadata, run history, and viewer access.";
      breadcrumbs.push({ label: "Document" });
      secondaryActions = [
        {
          href: projectDocumentViewerPath(projectId, sectionDetail, 1),
          label: "Open viewer"
        }
      ];
    } else {
      primaryAction = {
        href: projectDocumentImportPath(projectId),
        label: "Import document"
      };
    }
  } else if (sectionKey === "jobs" && sectionDetail) {
    title = `Job ${sectionDetail}`;
    summary = "Job lineage, status, and append-only event detail.";
    breadcrumbs.push({
      href: projectJobsPath(projectId),
      label: SECTION_MAP.jobs.title
    });
    breadcrumbs.push({ label: `Job ${sectionDetail}` });
    secondaryActions = [
      { href: projectJobsPath(projectId), label: "Back to jobs" }
    ];
  } else if (sectionKey === "model-assignments") {
    breadcrumbs.push({
      href: projectModelAssignmentsPath(projectId),
      label: SECTION_MAP["model-assignments"].title
    });
    if (sectionDetail) {
      title = `Assignment ${sectionDetail}`;
      summary =
        "Assignment status, role compatibility, and project-level lifecycle detail.";
      breadcrumbs.push({
        href: projectModelAssignmentPath(projectId, sectionDetail),
        label: `Assignment ${sectionDetail}`
      });
      if (sectionLeaf === "datasets") {
        title = "Assignment datasets";
        summary =
          "Training dataset lineage connected to the selected project model assignment.";
        breadcrumbs.push({
          href: projectModelAssignmentDatasetsPath(projectId, sectionDetail),
          label: "Datasets"
        });
      }
    }
  } else if (sectionKey === "settings") {
    breadcrumbs.push({ label: section.title });
  } else {
    breadcrumbs.push({ label: section.title });
  }

  return (
    <PageHeader
      eyebrow={`Projects / ${projectName}`}
      meta={projectId ? <Breadcrumbs items={breadcrumbs} /> : undefined}
      primaryAction={primaryAction}
      secondaryActions={secondaryActions}
      summary={summary}
      title={title}
    />
  );
}
