import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

export async function expectNoAxeViolations(
  page: Page,
  options?: {
    excludeSelectors?: string[];
    includeSelectors?: string[];
  }
): Promise<void> {
  let builder = new AxeBuilder({ page }).withTags([
    "wcag2a",
    "wcag2aa",
    "wcag21a",
    "wcag21aa",
    "wcag22aa"
  ]);

  const includeSelectors: string[] = [];
  for (const selector of options?.includeSelectors ?? []) {
    if ((await page.locator(selector).count()) > 0) {
      includeSelectors.push(selector);
    }
  }

  for (const selector of includeSelectors) {
    builder = builder.include(selector);
  }

  const excludeSelectors = [
    "nextjs-portal",
    ...(options?.excludeSelectors ?? [])
  ];
  for (const selector of excludeSelectors) {
    builder = builder.exclude(selector);
  }

  const results = await builder.analyze();
  expect(results.violations).toEqual([]);
}
