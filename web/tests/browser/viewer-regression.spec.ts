import { expect, test, type Page } from "@playwright/test";

import { expectNoAxeViolations } from "./helpers/a11y";
import { seedAuthenticatedSession } from "./helpers/session";

const PROJECT_ID = "project-fixture-alpha";
const READY_DOCUMENT_ID = "doc-fixture-002";
const LOADING_DOCUMENT_ID = "doc-fixture-001";
const FAILED_DOCUMENT_ID = "doc-fixture-003";

async function gotoViewer(
  page: Page,
  documentId: string,
  pageNumber = 1,
  options?: {
    mode?: "compare" | "original" | "preprocessed";
    runId?: string;
    zoom?: number | string;
  }
): Promise<void> {
  const query = new URLSearchParams({ page: String(pageNumber) });
  if (typeof options?.mode === "string" && options.mode !== "original") {
    query.set("mode", options.mode);
  }
  if (typeof options?.runId === "string" && options.runId.trim().length > 0) {
    query.set("runId", options.runId.trim());
  }
  if (typeof options?.zoom !== "undefined") {
    query.set("zoom", String(options.zoom));
  }
  await page.goto(`/projects/${PROJECT_ID}/documents/${documentId}/viewer?${query.toString()}`);
  await expect(page.locator(".documentViewerWorkspace")).toBeVisible();
}

async function gotoIngestStatus(
  page: Page,
  documentId: string,
  options?: { page?: number; zoom?: number | string }
): Promise<void> {
  const query = new URLSearchParams();
  if (typeof options?.page === "number") {
    query.set("page", String(options.page));
  }
  if (typeof options?.zoom !== "undefined") {
    query.set("zoom", String(options.zoom));
  }
  const suffix = query.toString();
  await page.goto(
    `/projects/${PROJECT_ID}/documents/${documentId}/ingest-status${
      suffix ? `?${suffix}` : ""
    }`
  );
  await expect(page.getByRole("heading", { name: "Processing timeline" })).toBeVisible();
}

test("viewer visual baselines for loading, ready, and error states @visual", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);

  await gotoViewer(page, LOADING_DOCUMENT_ID, 1);
  await expect(page.locator(".documentViewerWorkspace")).toHaveScreenshot(
    "viewer-state-loading.png"
  );

  await gotoViewer(page, READY_DOCUMENT_ID, 1);
  await expect(page.locator(".documentViewerWorkspace")).toHaveScreenshot(
    "viewer-state-ready.png"
  );

  await gotoViewer(page, FAILED_DOCUMENT_ID, 1);
  await expect(page.locator(".documentViewerWorkspace")).toHaveScreenshot(
    "viewer-state-error.png"
  );
});

test("viewer visual baselines include original, preprocessed, compare, and inspector drawer states @visual", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);

  await gotoViewer(page, READY_DOCUMENT_ID, 2);
  const modeSelector = page.locator(".documentViewerModeSelector");

  await modeSelector.getByRole("button", { name: "Preprocessed" }).click();
  await expect(page).toHaveURL(new RegExp(`/viewer\\?.*mode=preprocessed`));
  const preprocessedUrl = new URL(page.url());
  expect(preprocessedUrl.searchParams.get("mode")).toBe("preprocessed");
  expect(preprocessedUrl.searchParams.get("page")).toBe("2");
  expect(preprocessedUrl.searchParams.get("runId")).toBe("pre-run-fixture-002");
  await expect(page.locator(".documentViewerCanvas .documentViewerImage")).toHaveCount(
    1
  );
  await expect(page.locator(".documentViewerWorkspace")).toHaveScreenshot(
    "viewer-mode-preprocessed.png"
  );

  await modeSelector.getByRole("button", { name: "Compare" }).click();
  await expect(page).toHaveURL(new RegExp(`/viewer\\?.*mode=compare`));
  const compareUrl = new URL(page.url());
  expect(compareUrl.searchParams.get("mode")).toBe("compare");
  expect(compareUrl.searchParams.get("page")).toBe("2");
  expect(compareUrl.searchParams.get("runId")).toBe("pre-run-fixture-002");
  const compareImages = page.locator(".documentViewerComparePane .documentViewerImage");
  await expect(compareImages).toHaveCount(2);
  await expect(compareImages.first()).toBeVisible();
  await expect(compareImages.nth(1)).toBeVisible();
  await expect(page.locator(".documentViewerWorkspace")).toHaveScreenshot(
    "viewer-mode-compare.png"
  );

  await page.setViewportSize({ width: 860, height: 900 });
  const inspectorToggle = page.getByRole("button", { name: "Inspector drawer" });
  await expect(inspectorToggle).toBeEnabled();
  await expect(page.locator("main.homeLayout")).toHaveScreenshot(
    "viewer-inspector-drawer-closed.png"
  );

  await inspectorToggle.click();
  await expect(page.getByRole("heading", { name: "Viewer inspector" })).toBeVisible();
  await expect(page.locator("main.homeLayout")).toHaveScreenshot(
    "viewer-inspector-drawer-open.png"
  );
});

test("viewer supports keyboard and mouse page navigation, zoom, rotate, and page jump @keyboard", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);
  await gotoViewer(page, READY_DOCUMENT_ID, 1);

  const toolbar = page.getByRole("toolbar", {
    name: "Document viewer controls"
  });
  const nextPageButton = toolbar.getByRole("button", { name: "Next page" });
  const canvas = page.locator(".documentViewerCanvas");
  const zoomReadout = page.locator(".documentViewerZoomReadout");
  const pageJump = page.locator("#viewer-page-jump");

  await nextPageButton.focus();
  await page.keyboard.press("ArrowRight");
  await expect(nextPageButton).not.toBeFocused();
  await expect(page).toHaveURL(new RegExp(`/viewer\\?page=1$`));

  await canvas.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page).toHaveURL(new RegExp(`/viewer\\?page=2$`));

  await canvas.focus();
  await page.keyboard.press("Shift+=");
  await expect(zoomReadout).toHaveText("Zoom 110%");
  await page.keyboard.press("Minus");
  await expect(zoomReadout).toHaveText("Zoom 100%");

  await page
    .locator(".documentViewerFilmstrip")
    .getByRole("link", { name: "Page 2" })
    .click();
  await expect(page).toHaveURL(new RegExp(`/viewer\\?page=2(&runId=pre-run-fixture-002)?$`));
  await pageJump.fill("1");
  await page.getByRole("button", { name: "Go" }).click();
  await expect(page).toHaveURL(new RegExp(`/viewer\\?page=1(&runId=pre-run-fixture-002)?$`));
});

test("viewer deep links restore shareable state and normalize malformed params @keyboard", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);

  await gotoViewer(page, READY_DOCUMENT_ID, 2, { zoom: 135 });
  await expect(page.locator("#viewer-page-jump")).toHaveValue("2");
  await expect(page.locator(".documentViewerZoomReadout")).toHaveText("Zoom 135%");

  await page.reload();
  await expect(page.locator("#viewer-page-jump")).toHaveValue("2");
  await expect(page.locator(".documentViewerZoomReadout")).toHaveText("Zoom 135%");

  await page.locator(".documentViewerCanvas").focus();
  await page.keyboard.press("ArrowLeft");
  await expect(page).toHaveURL(new RegExp(`/viewer\\?page=1&zoom=135$`));

  await page.goBack();
  await expect(page).toHaveURL(new RegExp(`/viewer\\?page=2&zoom=135$`));
  await page.goForward();
  await expect(page).toHaveURL(new RegExp(`/viewer\\?page=1&zoom=135$`));

  await page.goto(
    `/projects/${PROJECT_ID}/documents/${READY_DOCUMENT_ID}/viewer?page=0000&zoom=9999`
  );
  await expect(page).toHaveURL(new RegExp(`/viewer\\?page=1&zoom=400$`));

});

test("viewer compare mode keeps metrics inspector and deep-link choreography intact @keyboard", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);
  await gotoViewer(page, READY_DOCUMENT_ID, 2, { mode: "compare" });

  const inspector = page.getByLabel("Inspector", { exact: true });
  await expect(page.locator(".documentViewerCompareSplit")).toBeVisible();
  await expect(inspector).toContainText("Run context");
  await inspector.getByRole("tab", { name: "Insights" }).click();
  await expect(inspector).toContainText("Quality gate");
  await expect(inspector).toContainText(
    /No warnings for the resolved preprocess page result\.|LOW_DPI/
  );

  const toolbar = page.getByRole("toolbar", {
    name: "Document viewer controls"
  });
  const previousPageButton = toolbar.getByRole("button", {
    name: "Previous page"
  });
  await previousPageButton.focus();
  await expect(previousPageButton).toBeFocused();
  await page.keyboard.press("ArrowRight");
  const compareViewerUrl = new URL(page.url());
  expect(compareViewerUrl.searchParams.get("mode")).toBe("compare");
  expect(compareViewerUrl.searchParams.get("page")).toBe("2");

  await inspector.getByRole("tab", { name: "Actions" }).click();
  const openCompareLink = inspector.getByRole("link", {
    name: "Open preprocessing compare"
  });
  const compareHref = await openCompareLink.getAttribute("href");
  expect(compareHref).toContain("/preprocessing/compare");
  const compareDiagnosticsUrl = new URL(compareHref ?? "/", "http://ukde.local");
  expect(compareDiagnosticsUrl.searchParams.get("baseRunId")).toBe("pre-run-fixture-001");
  expect(compareDiagnosticsUrl.searchParams.get("candidateRunId")).toBe(
    "pre-run-fixture-002"
  );
  expect(compareDiagnosticsUrl.searchParams.get("page")).toBe("2");
  expect(compareDiagnosticsUrl.searchParams.get("viewerMode")).toBe("compare");
  expect(compareDiagnosticsUrl.searchParams.get("viewerRunId")).toBe(
    "pre-run-fixture-002"
  );

  await expectNoAxeViolations(page, {
    includeSelectors: [".documentViewerToolbar", ".documentViewerWorkspace"]
  });
});

test("viewer deep links fail closed for unauthenticated users @keyboard", async ({
  page
}) => {
  await page.goto(`/projects/${PROJECT_ID}/documents/${READY_DOCUMENT_ID}/viewer?page=1`);
  await expect(page).toHaveURL(/\/login/);
});

test("ingest-status route preserves viewer context and recovery links @keyboard", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);
  await gotoIngestStatus(page, READY_DOCUMENT_ID, { page: 2, zoom: 135 });

  await expect(page.locator(".documentProcessingStageList")).toBeVisible();
  await page.getByRole("link", { name: "Open viewer" }).first().click();
  await expect(page).toHaveURL(new RegExp(`/viewer\\?page=2&zoom=135$`));

  await page.goBack();
  await expect(page).toHaveURL(
    new RegExp(`/ingest-status\\?page=2&zoom=135$`)
  );
});

test("viewer workspace remains bounded while filmstrip can scroll @reflow", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);
  await page.setViewportSize({ width: 1366, height: 900 });
  await gotoViewer(page, READY_DOCUMENT_ID, 1);

  const layoutMetrics = await page.evaluate(() => {
    const workspace = document.querySelector<HTMLElement>(
      ".documentViewerWorkspace"
    );
    const filmstrip = document.querySelector<HTMLElement>(
      ".documentViewerFilmstrip"
    );
    const scroller = document.scrollingElement;
    if (!workspace || !filmstrip || !scroller) {
      return null;
    }

    return {
      pageOverflow: scroller.scrollHeight - scroller.clientHeight,
      workspaceHeight: workspace.getBoundingClientRect().height,
      viewportHeight: window.innerHeight,
      filmstripOverflow: filmstrip.scrollHeight - filmstrip.clientHeight
    };
  });

  expect(layoutMetrics).not.toBeNull();
  expect(layoutMetrics?.pageOverflow ?? 0).toBeLessThanOrEqual(4);
  expect(layoutMetrics?.workspaceHeight ?? 0).toBeLessThanOrEqual(
    (layoutMetrics?.viewportHeight ?? 0) + 2
  );
  expect(layoutMetrics?.filmstripOverflow ?? 0).toBeGreaterThanOrEqual(0);
});
