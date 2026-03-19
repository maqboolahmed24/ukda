import { expect, test } from "@playwright/test";

import { seedAuthenticatedSession } from "./helpers/session";
import {
  assertWithinBudget,
  phase1PerformanceBudgetsMs
} from "./performance-budgets";

const PROJECT_ID = "project-fixture-alpha";
const READY_DOCUMENT_ID = "doc-fixture-002";

function elapsedMs(startTime: number): number {
  return Math.round(performance.now() - startTime);
}

test("phase-1 performance budgets for library, viewer, and upload wizard @phase1 @perf", async ({
  baseURL,
  context,
  page
}, testInfo) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);

  const metrics: Record<string, number> = {};

  // Prime route compilation/hydration in dev-mode runs before budget timing.
  await page.goto(`/projects/${PROJECT_ID}/documents`);
  await expect(page.locator("#documents-search")).toBeVisible();

  let start = performance.now();
  await page.reload();
  await expect(page.locator("#documents-search")).toBeVisible();
  metrics.documentLibraryInitialRender = elapsedMs(start);
  assertWithinBudget(
    "Document library initial render",
    metrics.documentLibraryInitialRender,
    phase1PerformanceBudgetsMs.documentLibraryInitialRender
  );

  await page.selectOption("#documents-sort", "created");
  start = performance.now();
  await page.getByRole("button", { name: "Apply filters" }).click();
  await expect(page).toHaveURL(/sort=created/);
  metrics.documentLibraryFilterApply = elapsedMs(start);
  assertWithinBudget(
    "Document library filter apply",
    metrics.documentLibraryFilterApply,
    phase1PerformanceBudgetsMs.documentLibraryFilterApply
  );

  start = performance.now();
  await page.goto(
    `/projects/${PROJECT_ID}/documents/${READY_DOCUMENT_ID}/viewer?page=1`
  );
  await expect(page.getByLabel("Canvas", { exact: true })).toBeVisible();
  metrics.viewerFirstPageRender = elapsedMs(start);
  assertWithinBudget(
    "Viewer first page render",
    metrics.viewerFirstPageRender,
    phase1PerformanceBudgetsMs.viewerFirstPageRender
  );

  start = performance.now();
  await expect(
    page.locator(".documentViewerFilmstripLink", { hasText: "Page 1" })
  ).toBeVisible();
  metrics.viewerThumbnailStripReady = elapsedMs(start);
  assertWithinBudget(
    "Viewer thumbnail strip readiness",
    metrics.viewerThumbnailStripReady,
    phase1PerformanceBudgetsMs.viewerThumbnailStripReady
  );

  await page.goto(`/projects/${PROJECT_ID}/documents/import`);
  start = performance.now();
  await page.setInputFiles("#document-import-file", {
    name: "budget-fixture.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.concat([
      Buffer.from("%PDF-1.7\n"),
      Buffer.alloc(512 * 1024, "B")
    ])
  });
  await expect(page.getByRole("button", { name: "Next" })).toBeEnabled();
  metrics.uploadWizardFileSelection = elapsedMs(start);
  assertWithinBudget(
    "Upload wizard file selection",
    metrics.uploadWizardFileSelection,
    phase1PerformanceBudgetsMs.uploadWizardFileSelection
  );

  await testInfo.attach("phase1-performance-metrics.json", {
    body: JSON.stringify(
      {
        metrics,
        budgets: phase1PerformanceBudgetsMs
      },
      null,
      2
    ),
    contentType: "application/json"
  });
});
