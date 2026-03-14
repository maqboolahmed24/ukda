import { redirect } from "next/navigation";
import { SectionState } from "@ukde/ui/primitives";

import { ThemePreferenceControl } from "../../../components/theme-preference-control";
import { resolveCurrentSession } from "../../../lib/auth/session";
import { healthPath, projectsPath } from "../../../lib/routes";
import { getAuthProviders } from "../../../lib/system";

export const dynamic = "force-dynamic";

export default async function LoginPage() {
  const currentSession = await resolveCurrentSession();
  if (currentSession) {
    redirect(projectsPath);
  }

  const providers = await getAuthProviders();

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
        <ThemePreferenceControl className="loginThemeControl" />
        {providers.oidcEnabled ? (
          <div className="buttonRow">
            <a className="primaryButton" href="/auth/login">
              Sign in with OIDC
            </a>
            <a className="secondaryButton" href={healthPath}>
              View health route
            </a>
          </div>
        ) : (
          <SectionState
            kind="disabled"
            title="OIDC sign-in unavailable"
            description="OIDC is not configured in this environment. Configure `OIDC_*` variables to enable governed SSO."
          />
        )}
        {providers.devEnabled && providers.devSeeds.length > 0 ? (
          <form action="/auth/dev-login" className="loginDevForm" method="post">
            <label className="ukde-eyebrow" htmlFor="seed_key">
              Dev sign-in identity
            </label>
            <select className="ukde-select" id="seed_key" name="seed_key">
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
        ) : providers.devEnabled ? (
          <SectionState
            kind="empty"
            title="No dev identities configured"
            description="Dev auth mode is enabled but no seed identities are available."
          />
        ) : null}
      </section>
    </main>
  );
}
