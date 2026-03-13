import { describe, expect, it } from "vitest";

import { normalizeAuthProviderResponse } from "./providers";

describe("auth provider normalization", () => {
  it("accepts camelCase provider payloads", () => {
    expect(
      normalizeAuthProviderResponse({
        oidcEnabled: false,
        devEnabled: true,
        devSeeds: [
          {
            key: "admin",
            displayName: "Dev Admin",
            email: "admin@local.ukde",
            platformRoles: ["ADMIN"]
          }
        ]
      })
    ).toEqual({
      oidcEnabled: false,
      devEnabled: true,
      devSeeds: [
        {
          key: "admin",
          displayName: "Dev Admin",
          email: "admin@local.ukde",
          platformRoles: ["ADMIN"]
        }
      ]
    });
  });

  it("accepts snake_case provider payloads", () => {
    expect(
      normalizeAuthProviderResponse({
        oidc_enabled: false,
        dev_enabled: true,
        dev_seeds: [
          {
            key: "auditor",
            display_name: "Dev Auditor",
            email: "auditor@local.ukde",
            platform_roles: ["AUDITOR"]
          }
        ]
      })
    ).toEqual({
      oidcEnabled: false,
      devEnabled: true,
      devSeeds: [
        {
          key: "auditor",
          displayName: "Dev Auditor",
          email: "auditor@local.ukde",
          platformRoles: ["AUDITOR"]
        }
      ]
    });
  });
});
