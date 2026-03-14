import { expect, type Page } from "@playwright/test";

export class ShellPage {
  readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  async gotoProjects(): Promise<void> {
    await this.page.goto("/projects");
    await expect(
      this.page.getByRole("heading", { name: "Projects workspace" })
    ).toBeVisible();
  }

  async gotoProjectOverview(projectId: string): Promise<void> {
    await this.page.goto(`/projects/${projectId}/overview`);
    await expect(
      this.page.getByRole("heading", { name: "Overview" })
    ).toBeVisible();
  }

  async gotoDesignSystem(): Promise<void> {
    await this.page.goto("/admin/design-system");
    await expect(
      this.page.getByRole("heading", {
        name: "Obsidian web design-system gallery"
      })
    ).toBeVisible();
  }

  async openCommandBar(): Promise<void> {
    await this.page.locator(".globalCommandTrigger").click();
    await expect(
      this.page.getByRole("heading", {
        name: "Global command bar",
        exact: true
      })
    ).toBeVisible();
  }

  async openProjectSwitcher(): Promise<void> {
    await this.page.locator(".globalCommandControls button").first().click();
    await expect(
      this.page.getByRole("heading", { name: "Project switcher", exact: true })
    ).toBeVisible();
  }
}
