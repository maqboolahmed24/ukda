import { expect, test, type Page } from "@playwright/test";

import { expectNoAxeViolations } from "./helpers/a11y";
import { seedAuthenticatedSession } from "./helpers/session";

const PROJECT_ID = "project-fixture-alpha";
const READY_DOCUMENT_ID = "doc-fixture-002";
const NOT_READY_DOCUMENT_ID = "doc-fixture-001";
const RUN_ID = "pre-run-fixture-002";
const BASE_RUN_ID = "pre-run-fixture-001";

test.describe.configure({ mode: "serial" });

async function gotoPreprocessingRoute(
  page: Page,
  documentId: string,
  suffix: string
): Promise<void> {
  await page.goto(`/projects/${PROJECT_ID}/documents/${documentId}${suffix}`);
  await expect(page.locator("main.homeLayout")).toBeVisible();
}

async function waitForPipelineLiveStatus(page: Page): Promise<void> {
  const liveStatusSection = page.locator(".documentPipelineLiveStatus");
  await expect(liveStatusSection).toBeVisible();
  await expect(
    liveStatusSection.getByText(/Polling every \d+s using live operations policy\./)
  ).toBeVisible();
}

test("preprocessing route visual baselines for overview, runs, quality, compare, and state variants @visual @preprocess", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);

  await gotoPreprocessingRoute(
    page,
    READY_DOCUMENT_ID,
    "/preprocessing"
  );
  await waitForPipelineLiveStatus(page);
  await expect(page.locator("main.homeLayout")).toHaveScreenshot(
    "preprocessing-overview-pages.png"
  );

  await gotoPreprocessingRoute(
    page,
    READY_DOCUMENT_ID,
    "/preprocessing?tab=runs"
  );
  await expect(page.locator("main.homeLayout")).toHaveScreenshot(
    "preprocessing-runs-table.png"
  );

  await gotoPreprocessingRoute(
    page,
    READY_DOCUMENT_ID,
    `/preprocessing/runs/${RUN_ID}`
  );
  await expect(page.locator("main.homeLayout")).toHaveScreenshot(
    "preprocessing-run-detail-summary.png"
  );

  await gotoPreprocessingRoute(
    page,
    READY_DOCUMENT_ID,
    `/preprocessing/quality?runId=${RUN_ID}`
  );
  await expect(page.locator("main.homeLayout")).toHaveScreenshot(
    "preprocessing-quality-ready.png"
  );

  await page.getByRole("button", { name: "Inspect" }).first().click();
  await expect(page.locator(".qualityDetailsDrawerBody")).toBeVisible();
  await page.evaluate(async () => {
    const previewImages = Array.from(
      document.querySelectorAll<HTMLImageElement>(".qualityDetailsPreviewGrid img")
    );
    await Promise.all(
      previewImages.map((image) => {
        if (image.complete) {
          return Promise.resolve();
        }
        return new Promise<void>((resolve) => {
          image.addEventListener("load", () => resolve(), { once: true });
          image.addEventListener("error", () => resolve(), { once: true });
        });
      })
    );
    const drawerBody = document.querySelector<HTMLElement>(".ukde-drawer-body");
    if (drawerBody) {
      drawerBody.scrollTop = 0;
    }
  });
  await expect(page.locator("main.homeLayout")).toHaveScreenshot(
    "preprocessing-quality-drawer-open.png"
  );
  await page.keyboard.press("Escape");
  await expect(page.locator(".qualityDetailsDrawerBody")).toBeHidden();

  await page.getByRole("button", { name: "Re-run preprocessing" }).click();
  await expect(page.getByRole("heading", { name: "Step 1: Scope" })).toBeVisible();
  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByRole("heading", { name: "Step 2: Profile" })).toBeVisible();
  await page.locator("details.qualityWizardAdvanced summary").click();
  await expect(page.locator("details.qualityWizardAdvanced")).toHaveAttribute(
    "open",
    ""
  );
  await expect(page.locator("main.homeLayout")).toHaveScreenshot(
    "preprocessing-quality-advanced-disclosure.png"
  );
  await page.keyboard.press("Escape");

  await gotoPreprocessingRoute(
    page,
    READY_DOCUMENT_ID,
    `/preprocessing/compare?baseRunId=${BASE_RUN_ID}&candidateRunId=${RUN_ID}&page=2&viewerMode=compare&viewerComparePair=gray_binary&viewerRunId=${RUN_ID}`
  );
  await expect(page.locator("main.homeLayout")).toHaveScreenshot(
    "preprocessing-compare-two-runs.png"
  );

  await gotoPreprocessingRoute(
    page,
    READY_DOCUMENT_ID,
    `/preprocessing/compare?candidateRunId=${RUN_ID}&page=1&viewerMode=preprocessed&viewerRunId=${RUN_ID}`
  );
  await expect(page.locator("main.homeLayout")).toHaveScreenshot(
    "preprocessing-compare-single-run.png"
  );

  await gotoPreprocessingRoute(
    page,
    NOT_READY_DOCUMENT_ID,
    "/preprocessing"
  );
  await expect(page.locator("main.homeLayout")).toHaveScreenshot(
    "preprocessing-not-ready-state.png"
  );

  await gotoPreprocessingRoute(
    page,
    READY_DOCUMENT_ID,
    "/preprocessing/quality?runId=missing-run"
  );
  await expect(page.locator("main.homeLayout")).toHaveScreenshot(
    "preprocessing-quality-error-state.png"
  );
});

test("preprocessing routes pass accessibility checks on overview, quality, runs, and compare surfaces @preprocess", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);

  await gotoPreprocessingRoute(
    page,
    READY_DOCUMENT_ID,
    "/preprocessing?tab=runs"
  );
  await expectNoAxeViolations(page, { includeSelectors: ["main.homeLayout"] });

  await gotoPreprocessingRoute(
    page,
    READY_DOCUMENT_ID,
    `/preprocessing/quality?runId=${RUN_ID}`
  );
  await expectNoAxeViolations(page, {
    includeSelectors: [".qualityTriageActionBar", ".qualityTriageTableWrap"]
  });

  await gotoPreprocessingRoute(
    page,
    READY_DOCUMENT_ID,
    `/preprocessing/runs/${RUN_ID}`
  );
  await expectNoAxeViolations(page, { includeSelectors: ["main.homeLayout"] });

  await gotoPreprocessingRoute(
    page,
    READY_DOCUMENT_ID,
    `/preprocessing/compare?baseRunId=${BASE_RUN_ID}&candidateRunId=${RUN_ID}`
  );
  await expectNoAxeViolations(page, { includeSelectors: ["main.homeLayout"] });
});

test("preprocessing keyboard and focus flows cover tabs, tables, drawers, compare route, and advanced disclosure @keyboard @preprocess", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);

  await gotoPreprocessingRoute(
    page,
    READY_DOCUMENT_ID,
    "/preprocessing?tab=runs"
  );
  const pagesTab = page.getByRole("link", { name: "Pages" });
  await pagesTab.focus();
  await expect(pagesTab).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Quality" })).toBeFocused();

  await gotoPreprocessingRoute(
    page,
    READY_DOCUMENT_ID,
    `/preprocessing/quality?runId=${RUN_ID}`
  );
  const selectAll = page.getByLabel("Select all filtered pages");
  await selectAll.focus();
  await expect(selectAll).toBeFocused();
  await page.keyboard.press("Space");
  await expect(selectAll).toBeChecked();

  const inspectButton = page.getByRole("button", { name: "Inspect" }).first();
  await inspectButton.focus();
  await expect(inspectButton).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator(".qualityDetailsDrawerBody")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator(".qualityDetailsDrawerBody")).toBeHidden();

  const rerunButton = page.getByRole("button", { name: "Re-run preprocessing" });
  await rerunButton.focus();
  await expect(rerunButton).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Step 1: Scope" })).toBeVisible();
  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByRole("heading", { name: "Step 2: Profile" })).toBeVisible();
  const advancedSummary = page.locator("details.qualityWizardAdvanced summary");
  await advancedSummary.focus();
  await expect(advancedSummary).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("details.qualityWizardAdvanced")).toHaveAttribute(
    "open",
    ""
  );
  await page.keyboard.press("Escape");

  await gotoPreprocessingRoute(
    page,
    READY_DOCUMENT_ID,
    `/preprocessing/compare?baseRunId=${BASE_RUN_ID}&candidateRunId=${RUN_ID}`
  );
  const compareBackLink = page.getByRole("link", { name: "Back to preprocessing" });
  await compareBackLink.focus();
  await expect(compareBackLink).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Open quality table" })).toBeFocused();
});
