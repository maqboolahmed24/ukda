import { expect, test, type Page } from "@playwright/test";

import { expectNoAxeViolations } from "./helpers/a11y";
import { seedAuthenticatedSession } from "./helpers/session";

const PROJECT_ID = "project-fixture-alpha";
const DOCUMENT_ID = "doc-fixture-002";
const RUN_ID = "layout-run-fixture-002";

async function gotoLayoutWorkspace(
  page: Page,
  options?: { page?: number; runId?: string }
): Promise<void> {
  const query = new URLSearchParams({
    page: String(options?.page ?? 1),
    runId: options?.runId ?? RUN_ID
  });
  await page.goto(
    `/projects/${PROJECT_ID}/documents/${DOCUMENT_ID}/layout/workspace?${query.toString()}`
  );
  await expect(page.locator(".layoutWorkspace")).toBeVisible();
}

test("layout workspace visual baselines for overlay and inspector states @visual", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);
  await gotoLayoutWorkspace(page, { page: 1, runId: RUN_ID });

  await expect(page.locator(".layoutWorkspace")).toHaveScreenshot(
    "layout-workspace-overlay-on.png"
  );

  const toolbar = page.getByRole("toolbar", { name: "Layout overlay controls" });
  await toolbar.getByRole("button", { name: /Regions/ }).click();
  await toolbar.getByRole("button", { name: /Lines/ }).click();
  await expect(page.locator(".layoutWorkspace")).toHaveScreenshot(
    "layout-workspace-overlay-off.png"
  );

  await toolbar.getByRole("button", { name: /Regions/ }).click();
  await toolbar.getByRole("button", { name: /Lines/ }).click();

  const workspaceTools = page.locator("details.layoutWorkspaceOverflowPanel");
  await workspaceTools.locator("summary").click();
  await page.getByRole("button", { name: "Zoom in" }).click();
  await page.getByRole("button", { name: "Zoom in" }).click();
  await page.getByRole("button", { name: "Zoom in" }).click();
  await page.getByRole("button", { name: "Zoom in" }).click();
  await expect(page.locator(".layoutWorkspace")).toHaveScreenshot(
    "layout-workspace-zoom-140.png"
  );
  await workspaceTools.locator("summary").click();

  await page.setViewportSize({ width: 860, height: 900 });
  await expect(page.locator("main.homeLayout")).toHaveScreenshot(
    "layout-workspace-inspector-drawer-closed.png"
  );

  await workspaceTools.locator("summary").click();
  const inspectorDrawerToggle = page.getByRole("button", {
    name: "Inspector drawer"
  });
  await inspectorDrawerToggle.click();
  await expect(page.getByRole("heading", { name: "Layout inspector" })).toBeVisible();
  await expect(page.locator("main.homeLayout")).toHaveScreenshot(
    "layout-workspace-inspector-drawer-open.png"
  );
});

test("layout workspace run switching refreshes overlay counts and inspector summaries @keyboard", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);
  await gotoLayoutWorkspace(page, { page: 1, runId: RUN_ID });

  await expect(page.getByRole("button", { name: /Lines \(6\)/ })).toBeVisible();
  await page.locator("#layout-run-selector").selectOption("layout-run-fixture-001");
  await expect(page).toHaveURL(/runId=layout-run-fixture-001/);
  await expect(page.getByRole("button", { name: /Lines \(5\)/ })).toBeVisible();
  await expect(page.locator(".documentViewerInspector")).toContainText(
    "layout-run-fixture-001"
  );
});

test("layout workspace keyboard toolbar and inspector-canvas selection sync @a11y @keyboard @reflow", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);
  await gotoLayoutWorkspace(page, { page: 1, runId: RUN_ID });

  const toolbar = page.getByRole("toolbar", { name: "Layout overlay controls" });
  const regionsToggle = toolbar.getByRole("button", { name: /Regions/ });
  const linesToggle = toolbar.getByRole("button", { name: /Lines/ });
  await regionsToggle.focus();
  await page.keyboard.press("ArrowRight");
  await expect(linesToggle).toBeFocused();

  await page.locator("polygon.layoutOverlayLine").first().click({ force: true });

  await page
    .locator(".layoutInspectorList")
    .first()
    .getByRole("button", { name: /r-0001-0001/ })
    .click();
  await expect(page.locator(".documentViewerInspector")).toContainText(
    "filtered by r-0001-0001"
  );

  await page
    .locator(".layoutInspectorList")
    .nth(1)
    .getByRole("button", { name: /l-0001-0002/ })
    .click();
  await expect(page.locator("polygon.layoutOverlayLine[data-selected='true']")).toHaveCount(1);

  const layoutMetrics = await page.evaluate(() => {
    const workspace = document.querySelector<HTMLElement>(".layoutWorkspace");
    const filmstrip = document.querySelector<HTMLElement>(".documentViewerFilmstrip");
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

  await expectNoAxeViolations(page, {
    includeSelectors: [".documentViewerToolbar", ".layoutWorkspace"]
  });
});

test("layout workspace mode choreography remains deterministic across inspect, reading-order, and edit @keyboard", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);
  await gotoLayoutWorkspace(page, { page: 1, runId: RUN_ID });

  const modeGroup = page.getByRole("group", { name: "Workspace mode" });
  await modeGroup.getByRole("button", { name: "Reading order" }).click();
  await expect(page.locator(".documentViewerToolbar")).toContainText("Reading-order mode");
  await expect(page.locator("#reading-order-mode")).toBeVisible();

  await modeGroup.getByRole("button", { name: "Inspect" }).click();
  await expect(page.locator(".documentViewerToolbar")).toContainText("Inspect mode");
  await expect(page.locator("#reading-order-mode")).toHaveCount(0);

  await modeGroup.getByRole("button", { name: "Edit" }).click();
  await expect(page.locator(".documentViewerToolbar")).toContainText("Edit mode");
  await expect(
    page.getByRole("toolbar", { name: "Layout edit tools" })
  ).toBeVisible();
});

test("layout workspace guards navigation when unsaved reading-order changes exist @keyboard", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);
  await gotoLayoutWorkspace(page, { page: 1, runId: RUN_ID });

  const modeGroup = page.getByRole("group", { name: "Workspace mode" });
  await modeGroup.getByRole("button", { name: "Reading order" }).click();
  await page.locator("#reading-order-mode").selectOption("UNORDERED");

  await page
    .locator(".layoutFilmstripButton")
    .nth(1)
    .click();
  await expect(page.locator(".layoutWorkspacePendingTransition")).toContainText(
    "Unsaved changes are staged."
  );
  await expect(page).toHaveURL(/page=1/);

  await page.getByRole("button", { name: "Discard and continue" }).click();
  await expect(page).toHaveURL(/page=2/);
});

test("layout workspace conflict surface is actionable for edit save collisions @a11y", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);
  await gotoLayoutWorkspace(page, { page: 1, runId: RUN_ID });

  await page.route(
    "**/projects/project-fixture-alpha/documents/doc-fixture-002/layout-runs/layout-run-fixture-002/pages/page-fixture-001/elements",
    async (route) => {
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({
          detail: "Layout changed in another session.",
          error: {
            code: "CONFLICT",
            detail: "Layout changed in another session.",
            retryable: false
          }
        })
      });
    }
  );

  const modeGroup = page.getByRole("group", { name: "Workspace mode" });
  await modeGroup.getByRole("button", { name: "Edit" }).click();
  await page
    .locator(".layoutInspectorList")
    .first()
    .getByRole("button", { name: /r-0001-0001/ })
    .click();
  await page.locator("#region-type-input").selectOption("HEADER");

  await page.getByRole("button", { name: "Save edits" }).click();
  await expect(page.locator(".documentViewerToolbar")).toContainText("Conflict detected");
  await expect(page.getByRole("button", { name: "Reload latest overlay" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Discard local edits" })).toBeVisible();

  await page.getByRole("button", { name: "Discard local edits" }).click();
  await expect(page.locator(".documentViewerToolbar")).toContainText("No unsaved changes");
});
