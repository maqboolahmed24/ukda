import { describe, expect, it } from "vitest";

import {
  bootstrapSurfaces,
  listShellStates,
  resolveApiOrigin,
  resolveApiOrigins
} from "./bootstrap-content";

describe("bootstrap content", () => {
  it("keeps the default API origin stable", () => {
    expect(resolveApiOrigin()).toBe("http://127.0.0.1:8000");
  });

  it("allows an internal API origin for server-side fetches", () => {
    expect(
      resolveApiOrigins({
        publicOrigin: "http://127.0.0.1:8000/",
        internalOrigin: "http://api:8000/"
      })
    ).toEqual({
      publicOrigin: "http://127.0.0.1:8000",
      internalOrigin: "http://api:8000"
    });
  });

  it("exposes the expected shell states", () => {
    expect(listShellStates().map((entry) => entry.state)).toEqual([
      "Expanded",
      "Balanced",
      "Compact",
      "Focus"
    ]);
  });

  it("keeps route and workspace metadata aligned to the shell scaffold", () => {
    expect(
      bootstrapSurfaces.some(
        (surface) => surface.route === "/admin/design-system"
      )
    ).toBe(true);
    expect(
      bootstrapSurfaces.some((surface) => surface.route === "/health")
    ).toBe(true);
  });
});
