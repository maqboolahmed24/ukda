import { expect, test, type Page } from "@playwright/test";

import { expectNoAxeViolations } from "./helpers/a11y";
import { seedAuthenticatedSession } from "./helpers/session";
import { ShellPage } from "./helpers/shell-page";

const PROJECT_ID = "project-fixture-alpha";

async function setThemePreference(
  page: Page,
  preference: "dark" | "light" | "system"
): Promise<void> {
  await page.addInitScript((value) => {
    window.localStorage.setItem("ukde.theme.preference", value);
  }, preference);
}

test("login visual baselines in dark and light @visual", async ({ page }) => {
  await page.goto("/login");
  await expect(page.locator(".loginCard")).toHaveScreenshot("login-dark.png");

  await setThemePreference(page, "light");
  await page.goto("/login");
  await expect(page.locator(".loginCard")).toHaveScreenshot("login-light.png");
});

test("authenticated shell visual baselines for projects and overview @visual", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);

  const shellPage = new ShellPage(page);
  await shellPage.gotoProjects();
  await expect(page.locator(".authenticatedShell")).toHaveScreenshot(
    "projects-shell-dark.png"
  );

  await shellPage.gotoProjectOverview(PROJECT_ID);
  await expect(page.locator(".authenticatedShell")).toHaveScreenshot(
    "project-overview-shell-dark.png"
  );

  await setThemePreference(page, "light");
  await shellPage.gotoProjects();
  await expect(page.locator(".authenticatedShell")).toHaveScreenshot(
    "projects-shell-light.png"
  );
});

test("design-system, command bar, and project switcher visual baselines @visual", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);

  const shellPage = new ShellPage(page);
  await shellPage.gotoDesignSystem();
  await expect(page.locator(".authenticatedShell")).toHaveScreenshot(
    "design-system-shell-dark.png"
  );

  await shellPage.openCommandBar();
  await expect(page.locator(".globalCommandDialog")).toHaveScreenshot(
    "command-bar-overlay.png"
  );
  await page.keyboard.press("Escape");

  await shellPage.openProjectSwitcher();
  await expect(page.locator(".globalCommandDialog")).toHaveScreenshot(
    "project-switcher-overlay.png"
  );
});

test("forced-colors shell visual baseline @visual @contrast", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);
  await page.emulateMedia({ colorScheme: "light", forcedColors: "active" });
  await page.goto("/projects");
  await expect(page.locator(".authenticatedShell")).toHaveScreenshot(
    "projects-shell-forced-colors.png"
  );
});

test("reduced-motion overlay visual baseline @visual @motion", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/admin/design-system");
  await page.getByTestId("primitives-open-dialog").click();
  await expect(page.locator(".ukde-dialog")).toHaveScreenshot(
    "dialog-overlay-reduced-motion.png"
  );

  const transitionToken = await page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue(
      "--ukde-transition"
    )
  );
  expect(transitionToken.trim()).toMatch(/0(?:ms|s)/);
});

test("route accessibility scans for login, projects, overview, and design-system @a11y", async ({
  baseURL,
  context,
  page
}) => {
  await page.goto("/login");
  await expect(page.locator("main").first()).toBeVisible();
  await expectNoAxeViolations(page, { includeSelectors: ["main"] });

  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);
  await page.addInitScript(() => {
    window.localStorage.setItem("ukde.theme.preference", "light");
  });

  await page.goto("/projects");
  await expect(page.locator("#ukde-shell-work-region")).toBeVisible();
  await expectNoAxeViolations(page, {
    includeSelectors: ["#ukde-shell-work-region"]
  });

  await page.goto(`/projects/${PROJECT_ID}/overview`);
  await expect(page.locator("#ukde-shell-work-region")).toBeVisible();
  await expectNoAxeViolations(page, {
    includeSelectors: ["#ukde-shell-work-region"]
  });

  await page.goto("/admin/design-system");
  await expect(page.locator("#ukde-shell-work-region")).toBeVisible();
  await expectNoAxeViolations(page, {
    includeSelectors: ["#ukde-shell-work-region"]
  });
});

test("overlay accessibility scans for dialog, drawer, and menu @a11y", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);
  await page.goto("/admin/design-system");

  await page.getByTestId("primitives-open-dialog").click();
  await expectNoAxeViolations(page, {
    includeSelectors: [".ukde-dialog"],
    excludeSelectors: ["body > :not(#ukde-overlay-root)"]
  });
  await page.keyboard.press("Escape");

  await page.getByTestId("primitives-open-drawer").click();
  await expectNoAxeViolations(page, {
    includeSelectors: [".ukde-drawer"],
    excludeSelectors: ["body > :not(#ukde-overlay-root)"]
  });
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: "Open menu" }).click();
  await expectNoAxeViolations(page, {
    includeSelectors: [".ukde-menu-surface"],
    excludeSelectors: [
      ".authenticatedShellHeader",
      ".authenticatedShellRail",
      ".authenticatedShellContext",
      ".adminConsoleRail",
      ".ukde-toast-viewport"
    ]
  });
  await page.keyboard.press("Escape");
});

test("single-fold and controlled reflow checks for shell routes @reflow", async ({
  baseURL,
  context,
  page
}) => {
  if (!baseURL) {
    throw new Error("Missing Playwright baseURL.");
  }
  await seedAuthenticatedSession(context, baseURL);

  await page.setViewportSize({ width: 1366, height: 900 });
  await page.goto(`/projects/${PROJECT_ID}/overview`);

  const desktopMetrics = await page.evaluate(() => {
    const shell = document.querySelector<HTMLElement>(".authenticatedShell");
    const workRegion = document.querySelector<HTMLElement>(
      ".authenticatedShellWorkRegion"
    );
    const scroller = document.scrollingElement;

    if (!shell || !workRegion || !scroller) {
      return null;
    }

    return {
      pageOverflow: scroller.scrollHeight - scroller.clientHeight,
      shellHeight: shell.getBoundingClientRect().height,
      viewportHeight: window.innerHeight,
      workRegionOverflow: workRegion.scrollHeight - workRegion.clientHeight
    };
  });

  expect(desktopMetrics).not.toBeNull();
  expect(desktopMetrics?.pageOverflow ?? 0).toBeLessThanOrEqual(4);
  expect(desktopMetrics?.shellHeight ?? 0).toBeLessThanOrEqual(
    (desktopMetrics?.viewportHeight ?? 0) + 2
  );
  expect(desktopMetrics?.workRegionOverflow ?? 0).toBeGreaterThanOrEqual(0);

  await page.setViewportSize({ width: 760, height: 760 });
  await page.goto(`/projects/${PROJECT_ID}/overview?shell=focus`);
  await expect(page.locator(".authenticatedShell")).toHaveAttribute(
    "data-shell-state",
    "Focus"
  );

  const compactMetrics = await page.evaluate(() => {
    const shell = document.querySelector<HTMLElement>(".authenticatedShell");
    const workRegion = document.querySelector<HTMLElement>(
      ".authenticatedShellWorkRegion"
    );
    const shellState = shell?.dataset.shellState ?? null;
    const scroller = document.scrollingElement;

    if (!workRegion || !scroller) {
      return null;
    }

    return {
      pageOverflow: scroller.scrollHeight - scroller.clientHeight,
      shellState,
      workRegionOverflow: workRegion.scrollHeight - workRegion.clientHeight
    };
  });

  expect(compactMetrics).not.toBeNull();
  expect(compactMetrics?.shellState).toBe("Focus");
  expect(compactMetrics?.workRegionOverflow ?? 0).toBeGreaterThanOrEqual(0);
});
