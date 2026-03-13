import Link from "next/link";

import type { ProjectSummary, SessionResponse } from "@ukde/contracts";
import {
  accessTierBadgeTones,
  accessTierLabels,
  environmentLabels
} from "@ukde/ui";

interface WorkspaceHeaderProps {
  session: SessionResponse;
  csrfToken: string | null;
  projects: ProjectSummary[];
  currentProject?: ProjectSummary | null;
}

function resolveEnvironmentLabel(): string {
  const raw = process.env.NEXT_PUBLIC_APP_ENV ?? process.env.APP_ENV ?? "dev";
  const normalized = raw.toLowerCase();
  if (normalized in environmentLabels) {
    return environmentLabels[normalized as keyof typeof environmentLabels];
  }
  return raw;
}

export function WorkspaceHeader({
  session,
  csrfToken,
  projects,
  currentProject
}: WorkspaceHeaderProps) {
  const hasPlatformRoles = session.user.platformRoles.length > 0;
  const tier = currentProject?.intendedAccessTier ?? null;

  return (
    <header className="workspaceHeader ukde-panel">
      <div className="workspaceIdentity">
        <h1>{currentProject?.name ?? "Projects workspace"}</h1>
      </div>

      <div className="workspaceUtilities">
        <details className="workspaceMenu">
          <summary className="workspaceMenuTrigger">Project switcher</summary>
          <div className="workspaceMenuPanel">
            <Link href="/projects">Projects index</Link>
            {projects.length > 0 ? (
              projects.map((project) => (
                <Link
                  href={`/projects/${project.id}/overview`}
                  key={project.id}
                >
                  {project.name}
                </Link>
              ))
            ) : (
              <span className="ukde-muted">
                No memberships yet. Create a project first.
              </span>
            )}
          </div>
        </details>

        <div className="workspaceBadges">
          <span className="ukde-badge">Env {resolveEnvironmentLabel()}</span>
          <span
            className="ukde-badge"
            data-tone={tier ? accessTierBadgeTones[tier] : "default"}
          >
            Tier {tier ? accessTierLabels[tier] : "Not selected"}
          </span>
        </div>

        <Link className="workspaceHelpLink" href="/health">
          Help
        </Link>

        <details className="workspaceMenu">
          <summary className="workspaceMenuTrigger">
            {session.user.displayName}
          </summary>
          <div className="workspaceMenuPanel">
            <span className="ukde-muted">{session.user.email}</span>
            <span className="ukde-muted">
              {hasPlatformRoles
                ? session.user.platformRoles.join(", ")
                : "No platform-role override"}
            </span>
            <Link href="/activity">My activity</Link>
            <form action="/auth/logout" method="post">
              <input name="csrf_token" type="hidden" value={csrfToken ?? ""} />
              <button className="workspaceSignOutButton" type="submit">
                Sign out
              </button>
            </form>
          </div>
        </details>
      </div>
    </header>
  );
}
