import { redirect } from "next/navigation";

import { readCsrfToken, resolveCurrentSession } from "../../lib/auth/session";

export const dynamic = "force-dynamic";

export default async function LogoutPage() {
  const session = await resolveCurrentSession();
  if (!session) {
    redirect("/login");
  }
  const csrfToken = await readCsrfToken();

  return (
    <main className="loginShell">
      <section className="loginCard ukde-panel" aria-labelledby="logout-title">
        <p className="ukde-eyebrow">Authenticated route</p>
        <h1 id="logout-title">End secure session</h1>
        <p className="ukde-muted">
          Sign out will invalidate the current server-issued session and remove
          local session cookies.
        </p>
        <form action="/auth/logout" className="buttonRow" method="post">
          <input name="csrf_token" type="hidden" value={csrfToken ?? ""} />
          <button className="primaryButton" type="submit">
            Confirm sign out
          </button>
          <a className="secondaryButton" href="/projects">
            Return to projects
          </a>
        </form>
      </section>
    </main>
  );
}
