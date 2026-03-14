import { describe, expect, test } from "vitest";

import { routeStateCopyCatalog } from "./route-state-copy";

describe("route state copy contract", () => {
  test("keeps route-level copy stable", () => {
    expect(routeStateCopyCatalog).toMatchSnapshot();
  });
});
