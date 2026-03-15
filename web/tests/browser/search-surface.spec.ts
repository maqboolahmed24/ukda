import { expect, test, type Page } from "@playwright/test";

import { expectNoAxeViolations } from "./helpers/a11y";
import { seedAuthenticatedSession } from "./helpers/session";

const PROJECT_ID = "project-fixture-alpha";

async function gotoProjectSearch(
  page: Page,
  query?: {
    cursor?: number;
    documentId?: string;
    pageNumber?: number;
    q?: string;
    runId?: string;
  }
): Promise<void> {
  const params = new URLSearchParams();
  if (query?.q) {
    params.set("q", query.q);
  }
  if (query?.documentId) {
    params.set("documentId", query.documentId);
  }
  if (query?.runId) {
    params.set("runId", query.runId);
  }
  if (typeof query?.pageNumber === "number") {
    params.set("pageNumber", String(query.pageNumber));
  }
  if (typeof query?.cursor === "number") {
    params.set("cursor", String(query.cursor));
  }
  const suffix = params.toString();
  const path = suffix
    ? `/projects/${PROJECT_ID}/search?${suffix}`
    : `/projects/${PROJECT_ID}/search`;
  await page.goto(path);
  await expect(page.getByRole("heading", { name: "Project full-text search" })).toBeVisible();
}

test("search surface visual baselines for zero-state and results @search @visual", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL, { profile: "reviewer" });

  await gotoProjectSearch(page);
  await expect(page.locator("#ukde-shell-work-region")).toHaveScreenshot(
    "search-zero-state.png"
  );

  await gotoProjectSearch(page, { q: "adams" });
  await expect(page.locator(".projectSearchResultsCard")).toHaveScreenshot(
    "search-results.png"
  );
});

test("search surface preserves keyboard-open jump context and back navigation @search @keyboard @a11y", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL, { profile: "researcher" });

  await gotoProjectSearch(page, { q: "adams" });
  await expectNoAxeViolations(page, {
    includeSelectors: ["#ukde-shell-work-region"]
  });

  const openLink = page
    .getByRole("link", { name: /Open hit in workspace/i })
    .first();
  await openLink.focus();
  await expect(openLink).toBeFocused();
  const openHref = await openLink.getAttribute("href");
  if (!openHref) {
    throw new Error("Expected open link href to be present.");
  }
  await page.goto(openHref);

  await expect(page).toHaveURL(/\/transcription\/workspace\?/);
  await expect(page).toHaveURL(/page=1/);
  await expect(page).toHaveURL(/runId=transcription-run-fixture-002/);
  await expect(page).toHaveURL(/sourceKind=LINE/);
  await expect(page).toHaveURL(/sourceRefId=line-privacy-001/);
  await expect(page).toHaveURL(/tokenId=token-privacy-001/);

  await page.goBack();
  await expect(page).toHaveURL(
    new RegExp(`/projects/${PROJECT_ID}/search\\?q=adams`)
  );
  await expect(page.getByRole("heading", { name: "Results" })).toBeVisible();
});

test("auditor is blocked from interactive project search route @search", async ({
  baseURL,
  browser
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  const auditorContext = await browser.newContext();
  await seedAuthenticatedSession(auditorContext, baseURL, { profile: "auditor" });
  const auditorPage = await auditorContext.newPage();
  await auditorPage.goto(`/projects/${PROJECT_ID}/search?q=adams`);
  await expect(auditorPage).toHaveURL(
    new RegExp(`/projects/${PROJECT_ID}/overview`)
  );
  await auditorContext.close();
});
