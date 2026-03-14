import { expect, test } from "@playwright/test";

import { seedAuthenticatedSession } from "./helpers/session";

const PROJECT_ID = "project-fixture-alpha";
const READY_DOCUMENT_ID = "doc-fixture-002";
const FAILED_DOCUMENT_ID = "doc-fixture-003";

test("phase-1 ingest and viewer routes cover failure, retry, and auth denial @phase1", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);

  await page.goto(`/projects/${PROJECT_ID}/documents`);
  await expect(page.locator("#documents-search")).toBeVisible();

  const ingestStatusPage = await context.newPage();
  await ingestStatusPage.goto(
    `/projects/${PROJECT_ID}/documents/${FAILED_DOCUMENT_ID}/ingest-status`
  );
  await expect(
    ingestStatusPage.getByRole("heading", { name: "Processing timeline" })
  ).toBeVisible();
  const retryButton = ingestStatusPage.getByRole("button", {
    name: "Retry extraction"
  });
  await expect(retryButton).toBeVisible();
  const retryResponsePromise = ingestStatusPage.waitForResponse((response) => {
    return (
      response.request().method() === "POST" &&
      response
        .url()
        .includes(
          `/projects/${PROJECT_ID}/documents/${FAILED_DOCUMENT_ID}/retry-extraction`
        )
    );
  });
  await retryButton.click();
  const retryResponse = await retryResponsePromise;
  expect(retryResponse.status()).toBe(200);

  const viewerPage = await context.newPage();
  await viewerPage.goto(
    `/projects/${PROJECT_ID}/documents/${READY_DOCUMENT_ID}/viewer?page=1`
  );
  await expect(viewerPage.getByLabel("Canvas", { exact: true })).toBeVisible();
  await expect(
    viewerPage.locator(".documentViewerFilmstripLink", { hasText: "Page 1" })
  ).toBeVisible();

  await context.clearCookies();
  const deniedPage = await context.newPage();
  await deniedPage.goto(
    `/projects/${PROJECT_ID}/documents/${READY_DOCUMENT_ID}/viewer?page=1`
  );
  await expect(deniedPage).toHaveURL(/\/login/);
});

test("controlled upload flow reaches assembled status in import workspace @phase1", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);
  await page.goto(`/projects/${PROJECT_ID}/documents/import`);
  await expect(page.locator("#document-import-file")).toBeVisible();

  const largePayload = Buffer.concat([
    Buffer.from("%PDF-1.7\nfixture\n"),
    Buffer.alloc(512 * 1024, "A")
  ]);
  await page.setInputFiles("#document-import-file", {
    name: "resumable-fixture.pdf",
    mimeType: "application/pdf",
    buffer: largePayload
  });

  await page.getByRole("button", { name: "Next" }).click();
  await expect(
    page.getByRole("heading", { name: "Step 2: Confirm upload metadata" })
  ).toBeVisible();

  await page.getByRole("button", { name: "Upload" }).click();
  await expect(
    page.getByRole("heading", { name: "Step 3: Upload and status" })
  ).toBeVisible();
  const resumeButton = page.getByRole("button", { name: "Resume upload" });
  const assembledMessage = page.getByText(
    "Upload assembled and queued for scanner handoff."
  );
  await expect(resumeButton.or(assembledMessage)).toBeVisible();
});
