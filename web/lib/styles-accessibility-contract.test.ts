import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const styles = readFileSync(
  new URL("../../packages/ui/src/styles.css", import.meta.url),
  "utf8"
);

describe("shared UI styles accessibility contract", () => {
  it("keeps reduced-motion and reduced-transparency handling explicit", () => {
    expect(styles).toContain("@media (prefers-reduced-motion: reduce)");
    expect(styles).toContain(".ukde-skeleton-line");
    expect(styles).toContain("@media (prefers-reduced-transparency: reduce)");
    expect(styles).toContain(":root[data-theme-transparency=\"reduce\"]");
  });

  it("keeps forced-colors styles for key controls and selected states", () => {
    expect(styles).toContain("@media (forced-colors: active)");
    expect(styles).toContain(".ukde-button[data-state=\"selected\"]");
    expect(styles).toContain(".ukde-button[aria-current=\"page\"]");
    expect(styles).toContain(".ukde-status-chip[data-tone=\"warning\"]");
    expect(styles).toContain(".ukde-badge[data-tone=\"danger\"]");
  });
});
