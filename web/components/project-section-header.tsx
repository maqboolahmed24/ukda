"use client";

import { usePathname } from "next/navigation";

import { PageHeader } from "./page-header";

const SECTION_MAP: Record<string, { title: string; summary: string }> = {
  overview: {
    title: "Overview",
    summary: "Project context, purpose, and current operational posture."
  },
  documents: {
    title: "Documents",
    summary: "Document library route contract reserved for Phase 1 ingest work."
  },
  jobs: {
    title: "Jobs",
    summary: "Project job queue, retry lineage, and worker execution status."
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
      "Project-scoped activity feed surface reserved for audit integration."
  },
  settings: {
    title: "Settings",
    summary: "Membership and project-governance controls."
  }
};

export function ProjectSectionHeader({ projectName }: { projectName: string }) {
  const pathname = usePathname();
  const pathSegments = pathname.split("/").filter(Boolean);
  const projectId = pathSegments[1] ?? "";
  const sectionKey = pathSegments[2] ?? "overview";
  const section = SECTION_MAP[sectionKey] ?? SECTION_MAP.overview;
  const secondaryActions =
    sectionKey === "documents" && projectId
      ? [
          {
            href: `/projects/${projectId}/documents/import`,
            label: "Import documents"
          }
        ]
      : [];

  return (
    <PageHeader
      eyebrow={`Projects / ${projectName}`}
      secondaryActions={secondaryActions}
      summary={section.summary}
      title={section.title}
    />
  );
}
