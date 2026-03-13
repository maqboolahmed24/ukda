import type {
  AuthProviderResponse,
  AuthProviderSeed,
  PlatformRole
} from "@ukde/contracts";

type RawAuthProviderSeed = {
  key?: unknown;
  displayName?: unknown;
  display_name?: unknown;
  email?: unknown;
  platformRoles?: unknown;
  platform_roles?: unknown;
};

type RawAuthProviderResponse = {
  oidcEnabled?: unknown;
  oidc_enabled?: unknown;
  devEnabled?: unknown;
  dev_enabled?: unknown;
  devSeeds?: unknown;
  dev_seeds?: unknown;
};

const PLATFORM_ROLES: PlatformRole[] = ["ADMIN", "AUDITOR"];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function asBoolean(value: unknown, fallback = false): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asPlatformRoles(value: unknown): PlatformRole[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter(
    (role): role is PlatformRole =>
      typeof role === "string" && PLATFORM_ROLES.includes(role as PlatformRole)
  );
}

function normalizeSeed(rawSeed: unknown): AuthProviderSeed | null {
  if (!isRecord(rawSeed)) {
    return null;
  }

  const seed = rawSeed as RawAuthProviderSeed;
  const key = asString(seed.key);
  const email = asString(seed.email);

  if (!key || !email) {
    return null;
  }

  return {
    key,
    email,
    displayName: asString(seed.displayName ?? seed.display_name, email),
    platformRoles: asPlatformRoles(seed.platformRoles ?? seed.platform_roles)
  };
}

export function normalizeAuthProviderResponse(
  payload: unknown
): AuthProviderResponse {
  if (!isRecord(payload)) {
    return {
      oidcEnabled: false,
      devEnabled: false,
      devSeeds: []
    };
  }

  const raw = payload as RawAuthProviderResponse;
  const rawSeeds = raw.devSeeds ?? raw.dev_seeds;

  return {
    oidcEnabled: asBoolean(raw.oidcEnabled ?? raw.oidc_enabled),
    devEnabled: asBoolean(raw.devEnabled ?? raw.dev_enabled),
    devSeeds: Array.isArray(rawSeeds)
      ? rawSeeds
          .map((seed) => normalizeSeed(seed))
          .filter((seed): seed is AuthProviderSeed => seed !== null)
      : []
  };
}
