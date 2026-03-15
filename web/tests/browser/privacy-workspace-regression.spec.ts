import { expect, test, type Page } from "@playwright/test";

import { expectNoAxeViolations } from "./helpers/a11y";
import { seedAuthenticatedSession } from "./helpers/session";

const PROJECT_ID = "project-fixture-alpha";
const DOCUMENT_ID = "doc-fixture-002";
const RUN_CANDIDATE_ID = "redaction-run-fixture-002";
const RUN_BASE_ID = "redaction-run-fixture-001";

async function gotoPrivacyWorkspace(
  page: Page,
  options?: {
    findingId?: string;
    lineId?: string;
    mode?: "controlled" | "safeguarded";
    page?: number;
    runId?: string;
    tokenId?: string;
  }
): Promise<void> {
  const query = new URLSearchParams({
    page: String(options?.page ?? 1),
    runId: options?.runId ?? RUN_CANDIDATE_ID
  });
  if (options?.findingId) {
    query.set("findingId", options.findingId);
  }
  if (options?.lineId) {
    query.set("lineId", options.lineId);
  }
  if (options?.tokenId) {
    query.set("tokenId", options.tokenId);
  }
  if (options?.mode) {
    query.set("mode", options.mode);
  }
  await page.goto(
    `/projects/${PROJECT_ID}/documents/${DOCUMENT_ID}/privacy/workspace?${query.toString()}`
  );
  await expect(page.locator(".privacyWorkspaceShell")).toBeVisible();
}

async function gotoPrivacyRun(page: Page, runId: string): Promise<void> {
  await page.goto(
    `/projects/${PROJECT_ID}/documents/${DOCUMENT_ID}/privacy/runs/${runId}`
  );
  await expect(page.getByRole("heading", { name: "Review state" })).toBeVisible();
}

async function gotoPrivacyCompare(page: Page): Promise<void> {
  await page.goto(
    `/projects/${PROJECT_ID}/documents/${DOCUMENT_ID}/privacy/compare?baseRunId=${RUN_BASE_ID}&candidateRunId=${RUN_CANDIDATE_ID}`
  );
  await expect(page.getByRole("heading", { name: "Page deltas" })).toBeVisible();
}

test("privacy workspace visual baselines for default, selected finding, dialog, and controlled mode @privacy @visual", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);

  await gotoPrivacyWorkspace(page);
  await expect(page.locator(".privacyWorkspaceShellCard")).toHaveScreenshot(
    "privacy-workspace-default.png"
  );

  await gotoPrivacyWorkspace(page, { findingId: "red-find-1" });
  await expect(page.locator(".privacyWorkspaceShellCard")).toHaveScreenshot(
    "privacy-workspace-selected-finding.png"
  );

  await page.getByRole("button", { name: "Override" }).click();
  await expect(page.getByRole("dialog", { name: "Override finding" })).toBeVisible();
  await expect(page.locator("body")).toHaveScreenshot(
    "privacy-workspace-override-dialog.png"
  );
  await page.keyboard.press("Escape");

  await gotoPrivacyWorkspace(page, {
    mode: "controlled",
    lineId: "line-privacy-001"
  });
  await expect(page.locator(".privacyWorkspaceShellCard")).toHaveScreenshot(
    "privacy-workspace-controlled-mode.png"
  );
});

test("privacy workspace next-unresolved navigation is deterministic and deep-link-safe @privacy @keyboard", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);

  await gotoPrivacyWorkspace(page, { findingId: "red-find-1" });
  const toolbar = page.getByRole("toolbar", { name: "Privacy review controls" });
  await toolbar.getByRole("button", { name: "Next unresolved" }).click();
  await expect(page).toHaveURL(/page=2/);
  await expect(page).toHaveURL(/findingId=red-find-2/);

  await toolbar.getByRole("button", { name: "Next unresolved" }).click();
  await expect(page).toHaveURL(/page=1/);
  await expect(page).toHaveURL(/findingId=red-find-1/);

  await page.reload();
  await expect(page).toHaveURL(/findingId=red-find-1/);
  await expect(page.locator(".privacyWorkspaceTranscriptList")).toContainText("line-privacy-001");
});

test("privacy workspace finding/page decisions, stale-etag conflict handling, and approval gating @privacy @a11y @keyboard @reflow", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);

  await gotoPrivacyWorkspace(page, { findingId: "red-find-1" });

  const approvePageButton = page.getByRole("button", { name: "Approve page" });
  await expect(approvePageButton).toBeDisabled();

  const decisionEtagInput = page.locator('input[name="decisionEtag"]').first();
  await decisionEtagInput.evaluate((node) => {
    (node as HTMLInputElement).value = "stale-etag";
  });
  await page.getByRole("button", { name: "Approve finding" }).click();
  await expect(page.locator("main.homeLayout")).toContainText("Workspace update blocked");
  await expect(page.locator("main.homeLayout")).toContainText(
    "conflicts with a newer change"
  );

  await gotoPrivacyWorkspace(page, { findingId: "red-find-1" });
  await page.getByRole("button", { name: "Approve finding" }).click();
  await expect(page.locator("main.homeLayout")).toContainText("Workspace updated");
  await expect(page.locator("main.homeLayout")).toContainText("Unresolved 0");

  await expect(approvePageButton).toBeEnabled();
  await approvePageButton.click();
  await expect(page.locator("main.homeLayout")).toContainText("Page review status is now APPROVED.");

  const toolbar = page.getByRole("toolbar", { name: "Privacy review controls" });
  const controlledButton = toolbar.getByRole("button", { name: "Controlled view" });
  const safeguardedButton = toolbar.getByRole("button", { name: "Safeguarded preview" });
  await controlledButton.focus();
  await page.keyboard.press("ArrowRight");
  await expect(safeguardedButton).toBeFocused();

  await page.getByRole("button", { name: "Override" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog", { name: "Override finding" })).toBeVisible();
  await page.keyboard.press("Tab");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: "Override" })).toBeFocused();

  const layoutMetrics = await page.evaluate(() => {
    const shell = document.querySelector<HTMLElement>(".privacyWorkspaceShell");
    const scroller = document.scrollingElement;
    if (!shell || !scroller) {
      return null;
    }
    return {
      pageOverflow: scroller.scrollHeight - scroller.clientHeight,
      shellHeight: shell.getBoundingClientRect().height,
      viewportHeight: window.innerHeight
    };
  });
  expect(layoutMetrics).not.toBeNull();
  expect(layoutMetrics?.pageOverflow ?? 0).toBeLessThanOrEqual(8);
  expect(layoutMetrics?.shellHeight ?? 0).toBeLessThanOrEqual(
    (layoutMetrics?.viewportHeight ?? 0) + 2
  );

  await expectNoAxeViolations(page, {
    includeSelectors: [
      ".privacyWorkspaceShell",
      ".privacyWorkspaceToolbarCard",
      ".privacyWorkspaceInspector"
    ]
  });
});

test("privacy run review and compare surfaces expose blockers, lock states, and keyboard-safe focus behavior @privacy @visual @a11y @keyboard @reflow", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);

  await gotoPrivacyRun(page, RUN_CANDIDATE_ID);
  await expect(page.getByRole("heading", { name: "Completion blockers" })).toBeVisible();
  await expect(page.getByText("PAGE_REVIEW_NOT_APPROVED")).toBeVisible();
  await expect(page.getByRole("button", { name: "Complete review" })).toBeDisabled();
  await expect(page.locator("main.homeLayout")).toHaveScreenshot(
    "privacy-run-review-blockers.png"
  );

  await gotoPrivacyRun(page, RUN_BASE_ID);
  await expect(page.locator("main.homeLayout")).toContainText("REVIEW APPROVED");
  await expect(page.locator("main.homeLayout")).toContainText("Locked at");
  await expect(page.getByRole("button", { name: "Start review" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Complete review" })).toBeDisabled();
  await expect(page.locator("main.homeLayout")).toHaveScreenshot(
    "privacy-run-approved-locked.png"
  );

  await gotoPrivacyWorkspace(page, {
    runId: RUN_BASE_ID,
    page: 1,
    findingId: "red-find-base-1"
  });
  await page.getByRole("button", { name: "Override" }).click();
  await expect(page.getByRole("dialog", { name: "Override finding" })).toBeVisible();
  await page.getByLabel("Decision reason").fill("Locked-run mutation attempt.");
  await page.getByRole("button", { name: "Save decision" }).click();
  await expect(page.locator("main.homeLayout")).toContainText("Workspace update blocked");
  await expect(page.locator("main.homeLayout")).toContainText(
    "Approved runs are locked and cannot be mutated."
  );

  await gotoPrivacyCompare(page);
  await expect(page.locator("main.homeLayout")).toContainText("Changed pages");
  await expect(page.locator("main.homeLayout")).toContainText("Preview ready delta");
  await expect(page.locator("main.homeLayout")).toHaveScreenshot(
    "privacy-compare-route-states.png"
  );

  const backToRunsLink = page.getByRole("link", { name: "Back to runs" });
  await backToRunsLink.focus();
  await expect(backToRunsLink).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Base run detail" })
  ).toBeFocused();

  const compareLayoutMetrics = await page.evaluate(() => {
    const scroller = document.scrollingElement;
    const table = document.querySelector<HTMLElement>("table");
    if (!scroller || !table) {
      return null;
    }
    return {
      bodyHorizontalOverflow: scroller.scrollWidth - scroller.clientWidth,
      tableHorizontalOverflow: table.scrollWidth - table.clientWidth
    };
  });
  expect(compareLayoutMetrics).not.toBeNull();
  expect(compareLayoutMetrics?.bodyHorizontalOverflow ?? 0).toBeLessThanOrEqual(8);
  expect(compareLayoutMetrics?.tableHorizontalOverflow ?? 0).toBeGreaterThanOrEqual(0);

  await expectNoAxeViolations(page, {
    includeSelectors: [".homeLayout"]
  });
});
