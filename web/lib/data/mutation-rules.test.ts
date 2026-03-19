import { describe, expect, it } from "vitest";

import {
  mutationRules,
  resolveMutationRevalidationPaths
} from "./mutation-rules";

describe("mutation rule policy", () => {
  it("is pessimistic for all governed mutations", () => {
    for (const rule of Object.values(mutationRules)) {
      expect(rule.optimism).toBe("none");
    }
  });

  it("returns project and settings revalidation paths for membership changes", () => {
    const paths = resolveMutationRevalidationPaths("projects.members.add", {
      projectId: "project-1"
    });
    expect(paths).toContain("/projects");
    expect(paths).toContain("/projects/project-1/overview");
    expect(paths).toContain("/projects/project-1/settings");
  });

  it("returns list and detail invalidation paths for job retry/cancel", () => {
    const paths = resolveMutationRevalidationPaths("jobs.retry", {
      projectId: "project-1",
      jobId: "job-1"
    });
    expect(paths).toEqual([
      "/projects/project-1/jobs",
      "/projects/project-1/jobs/job-1"
    ]);
  });

  it("returns index overview and detail paths for index lifecycle mutations", () => {
    const paths = resolveMutationRevalidationPaths("indexes.activate", {
      projectId: "project-1",
      indexKind: "SEARCH",
      indexId: "search-4"
    });
    expect(paths).toEqual([
      "/projects/project-1/indexes",
      "/projects/project-1/indexes/search/search-4"
    ]);
  });

  it("revalidates derivative surfaces and export-candidate list after freeze", () => {
    const paths = resolveMutationRevalidationPaths("derivatives.freeze", {
      projectId: "project-1",
      indexId: "dersnap-1"
    });
    expect(paths).toContain("/projects/project-1/derivatives");
    expect(paths).toContain("/projects/project-1/derivatives/dersnap-1");
    expect(paths).toContain("/projects/project-1/derivatives/dersnap-1/status");
    expect(paths).toContain("/projects/project-1/derivatives/dersnap-1/preview");
    expect(paths).toContain(
      "/projects/project-1/derivatives/dersnap-1?status=frozen"
    );
    expect(paths).toContain(
      "/projects/project-1/derivatives/dersnap-1/preview?status=freeze-existing"
    );
    expect(paths).toContain("/projects/project-1/export-candidates");
  });

  it("revalidates protected shell surfaces when auth boundaries change", () => {
    const paths = resolveMutationRevalidationPaths("auth.logout", {});
    expect(paths).toContain("/projects");
    expect(paths).toContain("/admin");
    expect(paths).toContain("/admin/audit");
    expect(paths).toContain("/activity");
  });

  it("revalidates preprocessing overview, quality, run detail, and viewer defaults after activation", () => {
    const paths = resolveMutationRevalidationPaths(
      "documents.preprocess.activate",
      {
        projectId: "project-1",
        documentId: "doc-1",
        runId: "run-1"
      }
    );
    expect(paths).toContain("/projects/project-1/documents/doc-1");
    expect(paths).toContain("/projects/project-1/documents/doc-1/preprocessing");
    expect(paths).toContain(
      "/projects/project-1/documents/doc-1/preprocessing?tab=runs"
    );
    expect(paths).toContain(
      "/projects/project-1/documents/doc-1/preprocessing/quality"
    );
    expect(paths).toContain("/projects/project-1/documents/doc-1/viewer?page=1");
    expect(paths).toContain(
      "/projects/project-1/documents/doc-1/preprocessing/runs/run-1"
    );
  });

  it("revalidates layout overview, runs, triage, workspace defaults, and run detail after activation", () => {
    const paths = resolveMutationRevalidationPaths("documents.layout.activate", {
      projectId: "project-1",
      documentId: "doc-1",
      runId: "layout-run-9"
    });
    expect(paths).toContain("/projects/project-1/documents/doc-1");
    expect(paths).toContain("/projects/project-1/documents/doc-1/layout");
    expect(paths).toContain("/projects/project-1/documents/doc-1/layout?tab=runs");
    expect(paths).toContain(
      "/projects/project-1/documents/doc-1/layout?tab=triage"
    );
    expect(paths).toContain(
      "/projects/project-1/documents/doc-1/layout/workspace?page=1&runId=layout-run-9"
    );
    expect(paths).toContain(
      "/projects/project-1/documents/doc-1/layout/runs/layout-run-9"
    );
  });

  it("revalidates transcription overview, runs, triage, artefacts, workspace defaults, and run detail after activation", () => {
    const paths = resolveMutationRevalidationPaths(
      "documents.transcription.activate",
      {
        projectId: "project-1",
        documentId: "doc-1",
        runId: "transcription-run-9"
      }
    );
    expect(paths).toContain("/projects/project-1/documents/doc-1");
    expect(paths).toContain("/projects/project-1/documents/doc-1/transcription");
    expect(paths).toContain(
      "/projects/project-1/documents/doc-1/transcription?tab=runs"
    );
    expect(paths).toContain(
      "/projects/project-1/documents/doc-1/transcription?tab=triage"
    );
    expect(paths).toContain(
      "/projects/project-1/documents/doc-1/transcription?tab=artefacts"
    );
    expect(paths).toContain(
      "/projects/project-1/documents/doc-1/transcription/workspace?page=1&runId=transcription-run-9"
    );
    expect(paths).toContain(
      "/projects/project-1/documents/doc-1/transcription/runs/transcription-run-9"
    );
  });
});
