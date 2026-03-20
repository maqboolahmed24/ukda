import { expect, test } from "@playwright/test";

import { expectNoAxeViolations } from "./helpers/a11y";
import { seedAuthenticatedSession } from "./helpers/session";

const PROJECT_ID = "project-fixture-alpha";
const DOCUMENT_ID = "doc-fixture-002";
const RUN_ID = "redaction-run-fixture-001";

test("reviewer can inspect screening-safe manifest detail and does not get ledger navigation affordances @governance @keyboard @a11y", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL, { profile: "reviewer" });

  await page.goto(
    `/projects/${PROJECT_ID}/documents/${DOCUMENT_ID}/governance?tab=ledger&runId=${RUN_ID}`
  );
  await expect(page.getByText("Ledger access restricted")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Evidence ledger" })
  ).toHaveCount(0);

  await page.goto(
    `/projects/${PROJECT_ID}/documents/${DOCUMENT_ID}/governance/runs/${RUN_ID}/manifest?category=PERSON_NAME&entryId=manifest-entry-001`
  );
  await expect(page.getByRole("heading", { name: "Manifest entries" })).toBeVisible();
  await expect(page.locator("table.auditTable")).toContainText("manifest-entry-001");
  await expect(page.getByRole("heading", { name: "Entry detail" })).toBeVisible();
  await expect(page.locator("main.homeLayout")).toContainText("PERSON_NAME");

  const applyFiltersButton = page.getByRole("button", { name: "Apply filters" });
  await applyFiltersButton.focus();
  await expect(applyFiltersButton).toBeFocused();

  await expectNoAxeViolations(page, {
    includeSelectors: ["main.homeLayout"]
  });
});

test("admin can inspect ledger timeline + verification history and trigger re-verification controls @governance @keyboard @a11y", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL, { profile: "admin" });

  await page.goto(
    `/projects/${PROJECT_ID}/documents/${DOCUMENT_ID}/governance/runs/${RUN_ID}/ledger?view=timeline&rowId=ledger-row-002&verificationRunId=gov-ledger-verify-003`
  );
  await expect(page.getByRole("heading", { name: "Diff summary" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Verification history" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Trigger re-verification" })
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Cancel verification attempt" })
  ).toBeVisible();

  await page.getByRole("link", { name: "List view" }).click();
  await expect(page.getByRole("link", { name: "List view" })).toHaveAttribute(
    "aria-current",
    "page"
  );

  await page.getByRole("button", { name: "Trigger re-verification" }).click();
  await expect(page).toHaveURL(/notice=verify_requested/);

  await expectNoAxeViolations(page, {
    includeSelectors: ["main.homeLayout"]
  });
});

test("auditor ledger view remains read-only and researcher direct ledger access is restricted @governance", async ({
  baseURL,
  browser
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }

  const auditorContext = await browser.newContext();
  await seedAuthenticatedSession(auditorContext, baseURL, { profile: "auditor" });
  const auditorPage = await auditorContext.newPage();
  await auditorPage.goto(
    `/projects/${PROJECT_ID}/documents/${DOCUMENT_ID}/governance/runs/${RUN_ID}/ledger`
  );
  await expect(auditorPage.getByText("Read-only auditor mode")).toBeVisible();
  await expect(
    auditorPage.getByRole("button", { name: "Trigger re-verification" })
  ).toHaveCount(0);
  await auditorContext.close();

  const researcherContext = await browser.newContext();
  await seedAuthenticatedSession(researcherContext, baseURL, { profile: "researcher" });
  const researcherPage = await researcherContext.newPage();
  await researcherPage.goto(
    `/projects/${PROJECT_ID}/documents/${DOCUMENT_ID}/governance/runs/${RUN_ID}/ledger`
  );
  await expect(researcherPage.getByText("Ledger access restricted")).toBeVisible();
  await researcherContext.close();
});
