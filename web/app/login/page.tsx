import type { AuthProviderResponse } from "@ukde/contracts";
import { redirect } from "next/navigation";

import { resolveApiOrigins } from "../../lib/bootstrap-content";
import { normalizeAuthProviderResponse } from "../../lib/auth/providers";
import { resolveCurrentSession } from "../../lib/auth/session";

async function fetchAuthProviders(): Promise<AuthProviderResponse> {
  const { internalOrigin } = resolveApiOrigins();
  try {
    const response = await fetch(`${internalOrigin}/auth/providers`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return {
        oidcEnabled: false,
        devEnabled: false,
        devSeeds: []
      };
    }
    return normalizeAuthProviderResponse(await response.json());
  } catch {
    return {
      oidcEnabled: false,
      devEnabled: false,
      devSeeds: []
    };
  }
}

export const dynamic = "force-dynamic";

export default async function LoginPage() {
  const currentSession = await resolveCurrentSession();
  if (currentSession) {
    redirect("/projects");
  }

  const providers = await fetchAuthProviders();

  return (
    <main className="loginShell">
      <section className="loginCard ukde-panel" aria-labelledby="login-title">
        <p className="ukde-eyebrow">Authentication</p>
        <h1 id="login-title">Session boundaries start here.</h1>
        <p className="ukde-muted">
          Use a governed sign-in path. Sessions are issued server-side, stored
          in secure HttpOnly cookies, and checked on every protected route.
        </p>
        <div className="loginMeta">
          <span className="ukde-badge">Public route</span>
          <span className="ukde-badge">Keyboard-first</span>
          <span className="ukde-badge">Dark-first</span>
          <span className="ukde-badge">
            Env {process.env.NEXT_PUBLIC_APP_ENV ?? "dev"}
          </span>
        </div>
        {providers.oidcEnabled ? (
          <div className="buttonRow">
            <a className="primaryButton" href="/auth/login">
              Sign in with OIDC
            </a>
            <a className="secondaryButton" href="/health">
              View health route
            </a>
          </div>
        ) : (
          <p className="ukde-muted">
            OIDC is not configured. Set `OIDC_*` environment variables to enable
            real SSO.
          </p>
        )}
        {providers.devEnabled && providers.devSeeds.length > 0 ? (
          <form action="/auth/dev-login" className="loginDevForm" method="post">
            <label className="ukde-eyebrow" htmlFor="seed_key">
              Dev sign-in identity
            </label>
            <select className="ukde-shell-button" id="seed_key" name="seed_key">
              {providers.devSeeds.map((seed) => (
                <option key={seed.key} value={seed.key}>
                  {seed.displayName} (
                  {seed.platformRoles.length > 0
                    ? seed.platformRoles.join(", ")
                    : "No platform role"}
                  )
                </option>
              ))}
            </select>
            <button className="secondaryButton" type="submit">
              Sign in with dev fixture
            </button>
          </form>
        ) : null}
      </section>
    </main>
  );
}
