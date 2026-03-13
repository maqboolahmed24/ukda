"use client";

import { usePathname } from "next/navigation";

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
  const sectionKey = pathname.split("/")[4] ?? "overview";
  const section = SECTION_MAP[sectionKey] ?? SECTION_MAP.overview;

  return (
    <section className="projectSectionHeader ukde-panel" aria-live="polite">
      <p className="ukde-eyebrow">
        Projects / {projectName} / {section.title}
      </p>
      <h2>{section.title}</h2>
      <p className="ukde-muted">{section.summary}</p>
    </section>
  );
}
