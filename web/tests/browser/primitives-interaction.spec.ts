import { expect, test } from "@playwright/test";

import { seedAuthenticatedSession } from "./helpers/session";

const PROJECT_ID = "project-fixture-alpha";

test("shell traversal, route activation, and focus handoff @keyboard", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);
  await page.goto(`/projects/${PROJECT_ID}/overview`);

  await page.keyboard.press("Tab");
  const skipLink = page.getByRole("link", { name: "Skip to work region" });
  await expect(skipLink).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#ukde-shell-work-region")).toBeFocused();

  await expect(
    page.locator(".authenticatedShellContextLink[aria-current='page']")
  ).toHaveText("Overview");

  const documentsLink = page
    .locator(".authenticatedShellContextLink", { hasText: "Documents" })
    .first();
  await documentsLink.focus();
  await expect(documentsLink).toBeFocused();
  await page.keyboard.press("Enter");

  await expect(page).toHaveURL(
    new RegExp(`/projects/${PROJECT_ID}/documents$`)
  );
  await expect(page.locator("#ukde-shell-work-region")).toBeFocused();
});

test("page-header primary and overflow actions are keyboard-safe @keyboard", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);
  await page.goto("/admin/design-system");

  const primaryAction = page.getByRole("link", {
    name: "Open projects workspace"
  });
  await primaryAction.focus();
  await expect(primaryAction).toBeFocused();

  const overflowTrigger = page
    .locator(".pageHeaderActions")
    .first()
    .getByRole("button", { name: "More actions" });
  await overflowTrigger.focus();
  await expect(overflowTrigger).toBeFocused();
  await page.keyboard.press("Enter");

  const overflowMenu = page
    .locator(".pageHeaderActions")
    .first()
    .locator(".ukde-menu-surface");
  await expect(overflowMenu).toBeVisible();

  const firstItem = overflowMenu.getByRole("menuitem").first();
  const lastItem = overflowMenu.getByRole("menuitem").last();
  await expect(firstItem).toBeFocused();
  await page.keyboard.press("End");
  await expect(lastItem).toBeFocused();
  await page.keyboard.press("Home");
  await expect(firstItem).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(overflowMenu).toBeHidden();
  await expect(overflowTrigger).toBeFocused();
});

test("dialog and drawer keep keyboard focus safe and return focus on close @keyboard", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);
  await page.goto("/admin/design-system");

  const openDialogButton = page.getByTestId("primitives-open-dialog");
  await openDialogButton.focus();
  await openDialogButton.click();
  const dialog = page.getByRole("dialog", {
    name: "Confirm project-level action"
  });
  await expect(dialog).toBeVisible();

  for (let index = 0; index < 5; index += 1) {
    await page.keyboard.press("Tab");
    const focusWithinDialog = await page.evaluate(() => {
      const active = document.activeElement;
      return Boolean(active && active.closest(".ukde-dialog"));
    });
    expect(focusWithinDialog).toBe(true);
  }

  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(openDialogButton).toBeFocused();

  const openDrawerButton = page.getByTestId("primitives-open-drawer");
  await openDrawerButton.focus();
  await page.keyboard.press("Enter");
  const drawer = page.getByRole("dialog", { name: "Context drawer" });
  await expect(drawer).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();
  await expect(openDrawerButton).toBeFocused();
});

test("toolbar roving focus and menu flyout keyboard behavior @keyboard", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);
  await page.goto("/admin/design-system");

  const toolbar = page.getByRole("toolbar", { name: "Primitive toolbar" });
  const refresh = toolbar.getByRole("button", { name: "Refresh" });
  const filter = toolbar.getByRole("button", { name: "Filter open only" });

  await refresh.focus();
  await expect(refresh).toBeFocused();
  await page.keyboard.press("ArrowRight");
  await expect(filter).toBeFocused();
  await page.keyboard.press("Home");
  await expect(refresh).toBeFocused();
  await page.keyboard.press("End");
  await expect(filter).toBeFocused();

  const menuTrigger = page.getByRole("button", { name: "Open menu" });
  await menuTrigger.focus();
  await page.keyboard.press("Enter");

  const menu = page.getByRole("menu");
  const createFollowUp = menu.getByRole("menuitem", {
    name: "Create follow-up"
  });
  const flagForReview = menu.getByRole("menuitem", { name: "Flag for review" });
  await expect(createFollowUp).toBeFocused();
  await page.keyboard.press("ArrowDown");
  await expect(flagForReview).toBeFocused();
  await page.keyboard.press("Home");
  await expect(createFollowUp).toBeFocused();
  await page.keyboard.press("End");
  await expect(flagForReview).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(menu).toBeHidden();
  await expect(menuTrigger).toBeFocused();
});

test("command bar and project switcher keyboard flows @keyboard", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);
  await page.goto(`/projects/${PROJECT_ID}/overview`);

  await page.keyboard.press("Control+k");
  await expect(
    page.getByRole("heading", { name: "Global command bar" })
  ).toBeVisible();
  const commandInput = page.locator(".globalCommandInput");
  await expect(commandInput).toBeFocused();
  await commandInput.fill("jobs");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(new RegExp(`/projects/${PROJECT_ID}/jobs$`));

  const commandTrigger = page.getByRole("button", { name: /Command bar/i });
  await commandTrigger.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Global command bar" })
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(commandTrigger).toBeFocused();

  const switcherTrigger = page.getByRole("button", {
    name: "Project switcher"
  });
  await switcherTrigger.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Project switcher" })
  ).toBeVisible();
  await commandInput.fill("estate");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/projects\/project-fixture-beta\/jobs$/);
});

test("focus indicators remain visible and not obscured in dark and forced-colors modes @focus", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);
  await page.goto("/projects");

  const darkSkipLink = page.getByRole("link", { name: "Skip to work region" });
  await darkSkipLink.focus();
  await expect(darkSkipLink).toBeFocused();
  const darkFocusVisible = await darkSkipLink.evaluate((element) => {
    const styles = getComputedStyle(element);
    return styles.outlineStyle !== "none" || styles.boxShadow !== "none";
  });
  expect(darkFocusVisible).toBe(true);

  const projectInputNotObscured = await page.evaluate(() => {
    const input = document.getElementById("project-name");
    const header = document.querySelector(".authenticatedShellHeader");
    if (!(input instanceof HTMLElement) || !(header instanceof HTMLElement)) {
      return false;
    }
    input.focus();
    const inputRect = input.getBoundingClientRect();
    const headerRect = header.getBoundingClientRect();
    return inputRect.top >= headerRect.bottom - 1;
  });
  expect(projectInputNotObscured).toBe(true);

  await page.emulateMedia({ colorScheme: "light", forcedColors: "active" });
  await page.reload();
  const forcedSkipLink = page.getByRole("link", {
    name: "Skip to work region"
  });
  await forcedSkipLink.focus();
  await expect(forcedSkipLink).toBeFocused();
  const forcedFocusVisible = await forcedSkipLink.evaluate((element) => {
    const styles = getComputedStyle(element);
    return styles.outlineStyle !== "none" || styles.boxShadow !== "none";
  });
  expect(forcedFocusVisible).toBe(true);
});
